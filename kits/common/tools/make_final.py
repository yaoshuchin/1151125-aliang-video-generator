"""把 片段/shot_01.mp4 … 接成一支成品：統一尺寸 → 加結尾卡 → 燒字幕 → 配旁白（免費 edge-tts）→ 混配樂。

用法（在製作包資料夾執行）：
  python tools/make_final.py                 依 影片需求.json 合成，輸出到 成品/
  python tools/make_final.py --no-voice      不要旁白
  python tools/make_final.py --res 1280x720  指定輸出尺寸（預設依比例：16:9→1280x720、9:16→720x1280）

需要：ffmpeg（U01 有安裝教學）。旁白用 edge-tts（pip install edge-tts，免費），沒裝會自動略過旁白。
配樂：06_配樂/配樂_定稿.mp3 → 06_配樂/*.mp3 → 素材/ 裡第一個 .mp3／.m4a／.wav（都沒有就只用影片原本的聲音）。
  用技能內附的 CC BY 曲時，把標示文字放 06_配樂/標示作者.txt，會自動複製到 成品/配樂標示_貼到說明欄.txt。
片頭／片尾：03_字卡/片頭.mp4（或 片頭.png）、03_字卡/片尾.mp4（或 片尾.png；都沒有就用品牌文字自動做結尾卡）。
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_CANDIDATES = ["C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msjhbd.ttc", "/System/Library/Fonts/PingFang.ttc",
                   "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
VOICES = {"溫暖女聲": "zh-TW-HsiaoChenNeural", "沉穩男聲": "zh-TW-YunJheNeural", "活潑童聲": "zh-TW-HsiaoYuNeural"}
# 2026-11-15 依「影片需求.json」basic.lang 選配音語言（女聲, 男聲）；臺語沒有免費 TTS → 用 05_旁白/旁白.mp3（自己錄）
LANG_VOICES = {"英文": ("en-US-JennyNeural", "en-US-GuyNeural"), "日文": ("ja-JP-NanamiNeural", "ja-JP-KeitaNeural"),
               "韓文": ("ko-KR-SunHiNeural", "ko-KR-InJoonNeural")}


def pick_voice(lang, vname):
    lang = "" if "雙語" in (lang or "") else (lang or "")   # 雙語＝中文旁白＋英文字幕，配音用臺灣國語
    if vname in VOICES and not any(k in lang for k in LANG_VOICES):
        return VOICES[vname]
    v = (vname or "").lower()
    male = ("男" in v or re.search(r"(^|[^a-z])(male|man)([^a-z]|$)", v)) and not re.search(r"female|woman|女", v)
    for k, (f, m) in LANG_VOICES.items():
        if k in lang:
            return m if male else f
    if "童" in (vname or ""):
        return VOICES["活潑童聲"]
    return VOICES["沉穩男聲"] if male else VOICES["溫暖女聲"]


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 失敗：" + r.stderr[-800:])
    return r


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def has_audio(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", p], capture_output=True, text=True)
    return bool(r.stdout.strip())


def font():
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f
    return None


def esc_dt(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def srt_time(t):
    h, m = int(t // 3600), int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(); ap.add_argument("--no-voice", action="store_true"); ap.add_argument("--res"); ap.add_argument("--outdir", default="成品")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        print("找不到 ffmpeg，請照 U01 安裝。"); sys.exit(1)
    req = json.load(open(os.path.join(ROOT, "影片需求.json"), encoding="utf-8"))
    ratio = req.get("output", {}).get("ratio", "16:9")
    W, H = (int(x) for x in (a.res or ("1280x720" if ratio == "16:9" else "720x1280")).split("x"))
    cdir = next((d for d in ("08_片段", "片段") if glob.glob(os.path.join(ROOT, d, "shot_*.mp4"))), "片段")
    clips = [os.path.join(ROOT, cdir, f"shot_{int(s['no']):02d}.mp4") for s in req["shots"]]
    missing = [os.path.basename(c) for c in clips if not os.path.exists(c)]
    if missing:
        print("還缺這些片段：", "、".join(missing)); sys.exit(1)
    fnt = font()
    tmp = tempfile.mkdtemp(prefix="vg_final_")
    # 1) 每段統一尺寸、30fps、有聲音
    norm = []
    for i, c in enumerate(clips):
        o = os.path.join(tmp, f"n{i:02d}.mp4")
        vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
        if has_audio(c):
            sh(["ffmpeg", "-y", "-i", c, "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", o])
        else:
            sh(["ffmpeg", "-y", "-i", c, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", o])
        norm.append(o)
    def still(png, sec, name):
        o = os.path.join(tmp, name)
        sh(["ffmpeg", "-y", "-loop", "1", "-t", f"{sec}", "-i", png, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,fade=t=in:st=0:d=0.4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", o])
        return o
    def clip(mp4, name):  # 技能做的動態片頭／片尾（mp4）統一尺寸、補聲軌
        o = os.path.join(tmp, name)
        vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
        if has_audio(mp4):
            sh(["ffmpeg", "-y", "-i", mp4, "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", o])
        else:
            sh(["ffmpeg", "-y", "-i", mp4, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", o])
        return o
    # 片頭：03_字卡/片頭.mp4（技能做的動態片頭）優先，其次 片頭.png（停 2 秒）
    head_mp4, head_png = os.path.join(ROOT, "03_字卡", "片頭.mp4"), os.path.join(ROOT, "03_字卡", "片頭.png")
    head = None
    if os.path.exists(head_mp4):
        head = clip(head_mp4, "head.mp4")
    elif os.path.exists(head_png):
        head = still(head_png, 2, "head.mp4")
    if head:
        norm.insert(0, head)
    # 2) 結尾卡（03_字卡/片尾.mp4 → 片尾.png → 用文字自動做）
    b = req.get("brand", {}); end_sec = float(b.get("endSec") or 3)
    tail_png = os.path.join(ROOT, "03_字卡", "片尾.png")
    tail_mp4 = os.path.join(ROOT, "03_字卡", "片尾.mp4")
    if os.path.exists(tail_mp4):
        norm.append(clip(tail_mp4, "end.mp4")); end_sec = dur(norm[-1])
    elif end_sec > 0 and os.path.exists(tail_png):
        norm.append(still(tail_png, end_sec, "end.mp4"))
    elif end_sec > 0 and fnt and (b.get("logoText") or b.get("org") or b.get("cta")):
        lines = [x for x in [b.get("logoText") or b.get("org"), b.get("slogan"), b.get("cta"), b.get("url")] if x]
        sizes = [int(H * 0.09), int(H * 0.05), int(H * 0.05), int(H * 0.035)]
        dt = []
        ffont = fnt.replace(":", r"\:")
        heights = [int(sizes[k] * 1.9) for k in range(len(lines))]
        y = H / 2 - sum(heights) / 2
        for k, t in enumerate(lines):
            col = "0xffcf5a" if k == len(lines) - 1 and len(lines) > 2 else "white"
            dt.append(f"drawtext=fontfile='{ffont}':text='{esc_dt(t)}':fontcolor={col}:fontsize={sizes[k]}:x=(w-text_w)/2:y={int(y)}")
            y += heights[k]
        o = os.path.join(tmp, "end.mp4")
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x15202b:s={W}x{H}:d={end_sec}:r=30", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-shortest", "-vf", ",".join(dt) + f",fade=t=in:st=0:d=0.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", o])
        norm.append(o)
    # 3) 接起來
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w", encoding="utf-8").write("".join(f"file '{os.path.basename(p)}'\n" for p in norm))
    joined = os.path.join(tmp, "joined.mp4")
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"], cwd=tmp)
    total = dur(joined)
    # 4) 字幕（字幕欄，沒有就用旁白切句）依各鏡秒數分配
    so = req.get("sound", {})
    subs = [x.strip().replace("｜", "\n") for x in (so.get("subtitles") or "").splitlines() if x.strip()]
    if not subs and so.get("narration"):
        subs = [x.strip() for x in re.split(r"(?<=[。！？!?；])|(?<=[.;])\s+", so["narration"]) if x and x.strip()]
    body_start = dur(head) if head else 0.0
    body_len = sum(dur(p) for p in norm[(1 if head else 0):(1 if head else 0) + len(clips)])
    cur = joined
    # 2026-11-15 台詞模式（漫劇／短劇）：沒有旁白、分鏡畫面描述裡有「台詞」→ 每鏡把台詞當字幕（在那一鏡的時間內），
    # Flow 片段本身的聲音（台詞、音效）保持原音量，配樂在有人講話時自動壓低
    dialog = not subs and not so.get("narration") and any("「" in (x.get("visual") or "") for x in req["shots"])
    srt_items = []
    if dialog:
        t0 = body_start
        for x, c in zip(req["shots"], norm[(1 if head else 0):(1 if head else 0) + len(clips)]):
            d = dur(c); qs = re.findall(r"「([^」]+)」", x.get("visual") or "")
            if qs:
                a0, a1 = t0 + 0.3, t0 + d - 0.15; tot = sum(len(q) for q in qs); cur_t = a0
                for q in qs:
                    e = cur_t + (a1 - a0) * len(q) / tot
                    srt_items.append((cur_t, e, q.rstrip("。")))
                    cur_t = e
            t0 += d
        subs = [q for _, _, q in srt_items]
        print(f"台詞模式：{len(srt_items)} 句台詞字幕；Flow 原音（台詞）保持原音量，配樂在講話時自動壓低")
    # 2026-11-15 人物字卡：角色第一次出場那鏡，左上角顯示「名字｜身分」2.5 秒（老師回報：沒介紹人物，觀眾看不懂劇情）
    cards = []
    if fnt and any((c.get("tag") or "").strip() for c in req.get("characters", [])):
        seen, t0 = set(), body_start
        for x, c in zip(req["shots"], norm[(1 if head else 0):(1 if head else 0) + len(clips)]):
            hay = (x.get("character") or "") + " " + (x.get("visual") or "")
            for ch in req.get("characters", []):
                nm, tag = ch.get("name") or "", (ch.get("tag") or "").strip()
                keys = {nm, re.sub(r"(老師|總裁|小姐|先生|師父|醫師|律師)$", "", nm)} - {""}
                if nm and tag and nm not in seen and any(k in hay for k in keys if len(k) >= 2):
                    seen.add(nm); cards.append((t0 + 0.4 + 0.3 * sum(1 for q in cards if abs(q[0] - t0 - 0.4) < 2), nm, tag))
            t0 += dur(c)
        if cards:
            print("人物字卡：" + "、".join(f"{n}｜{g}" for _, n, g in cards))
    def card_vf():
        ffont = fnt.replace(":", r"\:"); out = []; fs1 = max(20, int(min(W, H) * 0.075)); fs2 = max(15, int(min(W, H) * 0.045))
        for k, (a0, nm, tag) in enumerate(cards):
            y = int(H * 0.12) + int(fs1 * 2.6) * sum(1 for q in cards[:k] if abs(q[0] - a0) < 2.5)
            en = f"enable='between(t,{a0:.2f},{a0 + 2.6:.2f})'"
            out.append(f"drawbox=x={int(W*0.04)}:y={y}:w={int(W*0.012)}:h={int(fs1*2.45)}:color=0xf2c14e@0.95:t=fill:{en}")
            out.append(f"drawtext=fontfile='{ffont}':text='{esc_dt(nm)}':fontcolor=white:fontsize={fs1}:borderw=3:bordercolor=black@0.8:box=1:boxcolor=black@0.45:boxborderw=8:x={int(W*0.07)}:y={y}:{en}")
            out.append(f"drawtext=fontfile='{ffont}':text='{esc_dt(tag)}':fontcolor=0xf2c14e:fontsize={fs2}:borderw=2:bordercolor=black@0.8:box=1:boxcolor=black@0.45:boxborderw=6:x={int(W*0.07)}:y={y + int(fs1*1.45)}:{en}")
        return ",".join(out)
    if cards and not (subs and fnt):
        sh(["ffmpeg", "-y", "-i", "joined.mp4", "-vf", card_vf(), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", "subbed.mp4"], cwd=tmp)
        cur = os.path.join(tmp, "subbed.mp4")
    if subs and fnt:
        per = body_len / len(subs)
        if srt_items:
            srt = "".join(f"{i+1}\n{srt_time(a0)} --> {srt_time(a1 - 0.05)}\n{t}\n\n" for i, (a0, a1, t) in enumerate(srt_items))
        else:
            srt ="".join(f"{i+1}\n{srt_time(body_start + i*per)} --> {srt_time(body_start + (i+1)*per - 0.05)}\n{t}\n\n" for i, t in enumerate(subs))
        open(os.path.join(tmp, "subs.srt"), "w", encoding="utf-8").write(srt)
        if W > H:
            fs, mv = max(16, int(H * 0.028)), int(H * 0.06)
        else:      # 2026-11-15 直式：字幕座標以 288 高為基準（libass 預設），換算後約 58px、離底 14%，一行放得下 12 字
            fs, mv = max(9, round(W * 0.08 * 288 / H)), round(288 * 0.14)
        style = f"FontName=Microsoft JhengHei,FontSize={fs},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,MarginV={mv}"
        sh(["ffmpeg", "-y", "-i", "joined.mp4", "-vf", f"subtitles=subs.srt:force_style='{style}'" + ("," + card_vf() if cards else ""), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", "subbed.mp4"], cwd=tmp)
        cur = os.path.join(tmp, "subbed.mp4")
    # 5) 旁白（edge-tts）＋配樂
    voice_mp3 = None
    ready_voice = os.path.join(ROOT, "05_旁白", "旁白.mp3")
    vname = so.get("voice") or "溫暖女聲"
    lang = (req.get("basic") or {}).get("lang") or ""
    vid = pick_voice(lang, vname)
    if not a.no_voice and os.path.exists(ready_voice):
        voice_mp3 = ready_voice; print("旁白：用 05_旁白/旁白.mp3")
    elif not a.no_voice and so.get("narration") and ("臺語" in lang or "台語" in lang):
        print("旁白：語言是臺語，免費配音沒有臺語聲音。請把旁白稿唸一遍錄成 05_旁白/旁白.mp3（手機錄音轉 mp3 即可），再跑一次 make_final.py；這次先做沒有旁白的版本。")
    elif not a.no_voice and so.get("narration") and vname != "不要旁白":
        try:
            voice_mp3 = os.path.join(tmp, "voice.mp3")
            subprocess.run([sys.executable, "-m", "edge_tts", "--voice", vid, "--text", so["narration"], "--write-media", voice_mp3],
                           check=True, capture_output=True, timeout=180)
            vd = dur(voice_mp3)
            if vd > body_len + 0.3:   # 旁白太長就稍微加快，對齊畫面
                sp = min(1.35, vd / body_len)
                sh(["ffmpeg", "-y", "-i", voice_mp3, "-filter:a", f"atempo={sp:.3f}", os.path.join(tmp, "voice2.mp3")]); voice_mp3 = os.path.join(tmp, "voice2.mp3")
            print("旁白：edge-tts", vid, f"{dur(voice_mp3):.1f} 秒")
        except Exception as e:
            print("（沒有產生旁白：", "請先 pip install edge-tts" if "No module" in str(e) else str(e)[:120], "）"); voice_mp3 = None
    bgm = next(iter(sorted(glob.glob(os.path.join(ROOT, "06_配樂", "配樂_定稿.mp3")) + glob.glob(os.path.join(ROOT, "06_配樂", "*.mp3")) + glob.glob(os.path.join(ROOT, "素材", "*.mp3")) + glob.glob(os.path.join(ROOT, "素材", "*.m4a")) + glob.glob(os.path.join(ROOT, "素材", "*.wav")))), None)
    OUT = os.path.join(ROOT, a.outdir); os.makedirs(OUT, exist_ok=True)
    name = re.sub(r'[\\/:*?"<>|]', "_", req.get("output", {}).get("filename") or (req["basic"]["title"] + ".mp4"))
    if not name.lower().endswith(".mp4"): name += ".mp4"
    final = os.path.join(OUT, name)
    ins = ["-i", cur]; mix = ["[0:a]volume=" + ("1.0" if dialog else ("0.35" if (voice_mp3 or bgm) else "1.0")) + "[a0]"]; labels = ["[a0]"]
    if voice_mp3:
        ins += ["-i", voice_mp3]; dl = int(body_start * 1000 + 300); mix.append(f"[{len(labels)}:a]adelay={dl}|{dl},volume=1.6[a{len(labels)}]"); labels.append(f"[a{len(labels)}]")
    if bgm:
        ins += ["-stream_loop", "-1", "-i", bgm]; k = len(labels)
        if dialog:   # 台詞模式：配樂 sidechain 壓在台詞下面
            mix[0] = "[0:a]asplit=2[a0][sc]"
            mix.append(f"[{k}:a]volume=0.32,afade=t=out:st={max(0,total-2):.2f}:d=2[bgr];[bgr][sc]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=400[a{k}]")
        else:
            mix.append(f"[{k}:a]volume=0.18,afade=t=out:st={max(0,total-2):.2f}:d=2[a{k}]")
        labels.append(f"[a{k}]")
    fc = ";".join(mix) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5[aout]"
    sh(["ffmpeg", "-y"] + ins + ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", final])
    shutil.rmtree(tmp, ignore_errors=True)
    # 配樂若是技能內附的 CC BY 曲：06_配樂/標示作者.txt → 成品/配樂標示_貼到說明欄.txt
    credit = None
    cr = os.path.join(os.path.dirname(bgm), "標示作者.txt") if bgm else ""
    if bgm and os.path.exists(cr):
        credit = os.path.join(OUT, "配樂標示_貼到說明欄.txt")
        shutil.copy2(cr, credit)
        print("⚠ 這支片用了 CC BY 配樂：上傳時把「成品/配樂標示_貼到說明欄.txt」貼到說明欄（沒有說明欄就放片尾字卡）")
    info = {"file": final, "seconds": round(dur(final), 2), "size": f"{W}x{H}", "shots": len(clips), "head": bool(head), "end_card": end_sec if (fnt or os.path.exists(tail_mp4)) else 0,
            "subtitles": len(subs), "voice": bool(voice_mp3), "bgm": os.path.basename(bgm) if bgm else None,
            "bgm_credit": os.path.basename(credit) if credit else None}
    json.dump(info, open(os.path.join(OUT, "成品資訊.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("✅ 成品完成：", json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
