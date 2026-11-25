"""一鏡一鏡出片（A 路 Google Flow → 點數用完換帳號 → 全用完改 B 路 Gemini API；或 F 路 FAL 付費出片）。

用法（在製作包資料夾執行）：
  python tools/flow_run.py            依「影片需求.json」把每一鏡生成到 片段/shot_01.mp4 …
  python tools/flow_run.py --only 3   只重做第 3 鏡
  python tools/flow_run.py --dry      只列出每鏡要送出的提示詞，不花點數
  python tools/flow_run.py --res 720p 用 720p 出定稿（預設用需求檔的試做畫質）
  python tools/flow_run.py --no-ref   不用角色設定圖當參考，改回每鏡純文字生成

角色設定圖（2026-11-13）：影片需求.json 有角色時，出片前要先有「角色設定圖」（01_人物/角色設定圖_<角色名>.png，
或學員自己放的照片），而且使用者看過說 OK（python tools/char_sheet.py approve）。之後有該角色出場的鏡頭，
會先把設定圖當「素材」附進 Flow 提示詞再生成；沒有角色的鏡頭照舊純文字。--dry 會列出設定圖狀態、每鏡是否用參考圖、預估點數。

F 路（FAL，2026-11-13）：影片需求.json 的 route 是 "F" 才會走（auto 永遠不會自己改走 FAL，FAL 要花錢）。
  python tools/flow_run.py --dry      列出每鏡模型、計費秒數、預估美元（不花錢）
  python tools/flow_run.py            印出「要花錢，請確認」框就停下來（不花錢）
  python tools/flow_run.py --yes      使用者回覆「確認」後才加 --yes 真的出片；失敗不自動重試
  --fal-model kling|wan               臨時換模型（預設看 engine.falModel，沒填用 kling）
  有角色的鏡頭＝圖生影片：先用 FLUX Kontext 把角色設定圖做成這一鏡的首幀（存 01_人物/首幀/），再交給 Kling／Wan 動起來。

首尾幀（2026-11-15）：分鏡有「首幀／尾幀圖片提示詞」（生成器 ✨ 生成首尾幀圖片提示詞），或 首尾幀/ 資料夾已經有 p01-1.png、p01-2.png，
  那一鏡就走 Flow 的「畫面轉影片（Frames to Video）：首幀和尾幀」，全部由 AI 自己操作 Flow：
  ① 缺圖就用 Flow 生圖（Nano Banana，0 點）：首幀附角色設定圖、尾幀附首幀＋角色設定圖，構圖和人物才會一致
  ② 上傳首幀、尾幀附進提示詞 → 指定首尾幀 → 讀點數、核准 → 下載成 片段/shot_01.mp4
  python tools/flow_run.py --frames-only   只生首尾幀圖片（0 點），先打開 首尾幀/ 給使用者看，OK 再出片
  python tools/flow_run.py --no-frames     不用首尾幀，改回一般出片
  學員自己畫的圖也可以：照檔名放進 首尾幀/（p01-1 首幀、p01-2 尾幀，png／jpg／webp 都可以），AI 就不會重生。

輸出一律有 出片紀錄.json（每鏡用哪條路、哪個帳號、花幾點、幾秒）。
"""
import argparse, json, os, re, socket, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
FLOW = os.path.join(TOOLS, "cli-anything-flow")
OMNI = os.path.join(TOOLS, "gemini-omni-flash-api", "scripts", "video", "generate_video.py")
sys.path.insert(0, FLOW)


def load(name, default=None):
    p = os.path.join(ROOT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def port_open(port):
    s = socket.socket(); s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def ensure_bridge(wait=40):
    """沒有生成器在跑時，自己開 Flow 小幫手的橋接（埠 8840），等擴充功能連上。"""
    if not port_open(8840):
        import flow_bridge
        threading.Thread(target=flow_bridge.serve, daemon=True).start()
        time.sleep(1)
    import flowctl, urllib.request
    t0 = time.time()
    while time.time() - t0 < wait:
        try:
            if json.loads(urllib.request.urlopen(flowctl.BASE + "/ext/status", timeout=3).read()).get("connected"):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def shot_prompt(req, s):
    if s.get("prompt"):
        return s["prompt"]
    st = req.get("style", {})
    chars = {c.get("name"): c.get("anchor") for c in req.get("characters", [])}
    anchor = "; ".join(a for n, a in chars.items() if n and n in (s.get("character") or "") and a)
    return (f"{s.get('size','')}，{s.get('camera','')}。{s.get('visual','')} {s.get('action','')}。"
            f"畫風：{st.get('look','')}，色調：{st.get('palette','')}，氣氛：{st.get('mood','')}。"
            f"{('角色外觀：' + anchor + '。') if anchor else ''}畫面中不要出現任何文字、字幕或商標。")


sys.path.insert(0, TOOLS)
import char_sheet as cs      # 同資料夾 tools/char_sheet.py


def est_points(res):
    """Flow 每鏡預估點數（2026-11-13 實測：Omni 1.2 Flash 360p 5 秒＝5 點；720p 以上約 15～30 點）。"""
    return (5, "約 5 點") if res == "360p" else (30, "約 15～30 點")


def run_cli(args, timeout=1200):
    r = subprocess.run([sys.executable, os.path.join(FLOW, "cli_anything_flow.py")] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"ok": False, "error": (r.stdout + r.stderr)[-600:]}


FRAME_DIR = os.path.join(ROOT, "首尾幀")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")


def frame_file(no, k):
    """第 no 鏡的首幀（k=1）／尾幀（k=2）檔案；沒有就回傳預設 png 路徑（exists=False）。"""
    base = os.path.join(FRAME_DIR, f"p{int(no):02d}-{k}")
    for e in IMG_EXT:
        if os.path.exists(base + e):
            return base + e, True
    return base + ".png", False


def wants_frames(s, a):
    if a.no_frames:
        return False
    return bool((s.get("frameFirst") and s.get("frameLast")) or (frame_file(s["no"], 1)[1] and frame_file(s["no"], 2)[1]))


def frame_prompt(req, s, which):
    st = req.get("style", {})
    body = s.get("frameFirst" if which == 1 else "frameLast") or ""
    if not body:
        body = f"{s.get('visual','')} {s.get('action','')}" + ("（動作開始前）" if which == 1 else "（動作完成後）")
    tail = (f" Style: {st.get('look','')}; palette: {st.get('palette','')}; mood: {st.get('mood','')}." if st.get("look") else "")
    keep = ("" if which == 1 else " This is the LAST frame of the same shot: keep exactly the same characters, outfits, location, camera angle, framing and lighting as the attached first frame; only the action has progressed.")
    return body + tail + keep + " No text, no subtitles, no logos in the image."


def logged_accounts(accounts):
    status = run_cli(["status"])
    logged = [t["account"] for t in status.get("flow_tabs", []) if t.get("account")]
    order = [a["email"] for a in accounts if a.get("email") and a["email"] in logged]
    return order + [x for x in logged if x not in order]


# ============ 2026-11-15 鎖臉（老師回報：成果片阿亮老師每一鏡長得都不一樣） ============
# 實測原因：① 每鏡首幀都各自從一張小照片重新生，臉每次飄一點；② 提示詞裡 AI 寫的長相（45 歲、鵝蛋臉、劍眉…）
# 跟照片打架，Flow 會照文字畫成另一個人；③ 影片模型動起來臉又再飄。量化：24 鏡和照片的相似度大多 0.0～0.3。
# 修法：先做「定妝照」（照片本人穿這部戲的服裝，相似度過關才用）→ 每鏡首尾幀只拿定妝照當參考、提示詞不再描述長相
# → 首尾幀和影片生完都用 face_check 比對臉，不像就自動重生。
LOCK_PASS, FRAME_PASS, VIDEO_LOW = 0.50, 0.40, 0.27      # VIDEO_LOW：360p 影片實測，有出場的角色 ≥0.31、沒出場的 ≤0.21


def _fc():
    try:
        import face_check
        return face_check if face_check._models() else None
    except Exception:
        return None


def split_anchor(anchor):
    """英文一致性描述詞 → (man/woman, 服裝, 畫風)；用來把「長相描述」換成「照參考圖」。"""
    parts = [p.strip() for p in (anchor or "").strip().rstrip(".").split(",") if p.strip()]
    style = parts.pop() if parts and re.search(r"photograph|photoreal|anime|animation|illustration|render|cartoon|manhua|\b[23]D\b", parts[-1], re.I) else ""
    body = ", ".join(parts)
    outfit = body.split("wearing ", 1)[1] if "wearing " in body else ""
    gender = "woman" if re.search(r"\b(woman|girl|female|lady)\b", body, re.I) else "man"
    return gender, outfit, style


def lock_faces(req, sheet_rows, names, ratio, accounts, log=print):
    """每位出場角色做一張定妝照 01_人物/定妝_<名>.png（0 點）；回傳 {角色名: {lock, src, feats}}。"""
    fc = _fc(); out = {}
    accs = logged_accounts(accounts)
    cache = os.path.join(ROOT, "01_人物", ".flow參考圖快取.json")
    for name in names:
        row = sheet_rows.get(name) or {}
        src = os.path.join(ROOT, row["file"]) if row.get("file") else None
        if not src or not os.path.exists(src):
            continue
        ch = next((c for c in req.get("characters", []) if c.get("name") == name), {})
        dst = os.path.join(ROOT, "01_人物", f"定妝_{cs.safe(name)}.png")
        ref = fc.ref_feature(src) if fc else None
        if not os.path.exists(dst):
            if not accs:
                raise RuntimeError("Chrome 裡沒有登入的 Flow 分頁，沒辦法做定妝照")
            gender, outfit, style = split_anchor(ch.get("anchor"))
            glasses = " and glasses" if "glasses" in (ch.get("anchor") or "").lower() else ""
            prompt = (f"Waist-up portrait, front view, of the exact same {gender} as the reference image: identical face, facial proportions, age, "
                      f"skin tone and hairstyle{glasses}. Now wearing {outfit or 'the same clothes'}. Calm neutral expression, looking at the camera, "
                      f"plain light gray studio background, soft even lighting, {style or 'cinematic photorealistic live-action photography'}. No text, no logo.")
            best = (-9.0, None)
            for i in range(4):
                tmp = dst[:-4] + f"_候選{i + 1}.png"
                log(f"  🔒 做 {name} 的定妝照（照參考照的臉、穿戲服，0 點）｜第 {i + 1} 次")
                r = run_cli(["gen-image", "--account", accs[0], "--prompt", prompt, "--out", tmp, "--ratio", ratio,
                             "--ref", src, "--ref-mode", "person", "--ref-cache", cache], timeout=600)
                if not r.get("ok") or not os.path.exists(tmp):
                    time.sleep(5); continue
                sc = fc.best_match(ref, tmp) if (fc and ref is not None) else None
                if sc is None:
                    best = (0.0, tmp); break
                log(f"     和參考照的相似度 {sc:.2f}（要 ≥ {LOCK_PASS}）")
                if sc > best[0]:
                    best = (sc, tmp)
                if sc >= LOCK_PASS:
                    break
            if not best[1]:
                raise RuntimeError(f"{name} 的定妝照做不出來")
            if best[0] < LOCK_PASS and fc and ref is not None:
                log(f"  ⚠ {name} 定妝照最高只有 {best[0]:.2f}，先用最像的一張；建議換一張更清楚的正面照")
            import shutil
            shutil.copy2(best[1], dst)
            for i in range(4):
                p = dst[:-4] + f"_候選{i + 1}.png"
                if os.path.exists(p):
                    os.remove(p)
            log(f"  ✅ 定妝照：{os.path.relpath(dst, ROOT)}")
        feats = [f for f in (ref, fc.ref_feature(dst) if fc else None) if f is not None]
        out[name] = {"lock": dst, "src": src, "feats": feats}
    return out


def face_score(locks, path):
    """圖裡的臉和定妝照／原照有多像（每位角色取最像的那張臉，多人取最低分）；沒臉可判斷回傳 None。"""
    fc = _fc()
    if not fc or not locks:
        return None
    fs = [x for x in (fc.faces(path) or []) if x[0] >= 90 * 90]     # 臉寬不到約 90 像素（遠景、低頭）比對不準，不判斷
    if not fs:
        return None
    import cv2
    m = fc._models()
    vals = []
    for L in locks:
        if L.get("feats"):
            vals.append(max(float(m["rec"].match(r, f, cv2.FaceRecognizerSF_FR_COSINE)) for r in L["feats"] for _, f in fs))
    if not vals:
        return None
    return min(vals) if len(fs) >= len(vals) else max(vals)


def neutral(text, req, s, locks, mode, offset=0):
    """把提示詞裡角色的英文長相描述換成「照參考圖／照首幀」。mode：ref（附定妝照）、first（影片照首幀）。"""
    if not text or not locks:
        return text
    order = [c for c in cs.chars_in_shot(req, s) if c["name"] in locks]
    for i, c in enumerate(order):
        a = (c.get("anchor") or "").strip().rstrip(".")
        if not a:
            continue
        gender, outfit, style = split_anchor(a)
        w = f", wearing {outfit}" if outfit else ""
        if mode == "first":
            rep = f"the same {gender} as in the first frame ({c['name']}), keeping exactly the same face from the first to the last second{w}"
        else:
            rep = f"{c['name']}: exactly the same {gender} as reference image #{i + 1 + offset} (identical face, age and hairstyle){w}"
        text = text.replace(a, rep + (f", {style}" if style else ""))
    if mode == "ref":
        text += " " + " ".join(f"Reference image #{i + 1 + offset} = {c['name']}, keep the face identical." for i, c in enumerate(order))
    return text


_TAIL_BROKEN = []      # 這次執行尾幀失敗過 → 後面的鏡直接用「只有首幀」，省下每鏡約 5 分鐘的白試


def make_frames(req, s, ratio, accounts, char_refs, log=print, locks=None):
    """缺首幀／尾幀就用 Flow 生圖（0 點；代理若要扣點會自動拒絕）。回傳 (首幀, 尾幀, 說明)。
    2026-11-15 實測修正：首幀的角色參考只取臉和服裝（不帶背景）；尾幀以首幀為場景參考；
    生出來方向不對（要直式卻是橫式）或 Flow 偶發卡住，自動重生，每張最多 3 次。
    鎖臉（locks）：參考圖改用定妝照、提示詞不描述長相；生完比對臉，相似度不到 0.40 就重生（最多 3 次，留最像的）。"""
    os.makedirs(FRAME_DIR, exist_ok=True)
    cache = os.path.join(FRAME_DIR, ".flow參考圖快取.json")
    accs = logged_accounts(accounts)
    if not accs:
        raise RuntimeError("Chrome 裡沒有登入的 Flow 分頁，沒辦法自動生首尾幀")
    want_tall = ratio in ("9:16", "3:4")
    shot_locks = {c["name"]: locks[c["name"]] for c in cs.chars_in_shot(req, s) if locks and c["name"] in locks}
    if shot_locks:
        char_refs = [L["lock"] for L in shot_locks.values()]
    made = []
    for k in (1, 2):
        f, ok = frame_file(s["no"], k)
        if ok:
            continue
        if k == 2 and _TAIL_BROKEN:
            log("  （這次尾幀生圖一直失敗，直接用「只有首幀」出片）")
            return frame_file(s["no"], 1)[0], None, made
        refs = list(char_refs) if k == 1 else [frame_file(s["no"], 1)[0]] + list(char_refs)
        fp = frame_prompt(req, s, k)
        if shot_locks:
            fp = neutral(fp, req, s, shot_locks, "ref", offset=0 if k == 1 else 1)
        args = ["gen-image", "--account", accs[0], "--prompt", fp, "--out", f, "--ratio", ratio, "--ref-cache", cache,
                "--ref-mode", "person" if k == 1 else "scene"]
        for r in refs:
            args += ["--ref", r]
        name = "首" if k == 1 else "尾"
        err = ""; best = (-9.0, None)
        for attempt in range(3):
            if k == 2 and attempt == 1:      # 2026-11-15 實測：首幀＋多張定妝照一起當參考時 Flow 代理常卡住 → 重試只留首幀
                args = [x for x in args[:args.index("--ref")]] + ["--ref", refs[0]]
            log(f"  生{name}幀：{os.path.relpath(f, ROOT)}（Flow 生圖，0 點）" + (f"｜第 {attempt + 1} 次" if attempt else ""))
            r = run_cli(args, timeout=600)
            if not r.get("ok"):
                err = json.dumps(r, ensure_ascii=False)[:300]; time.sleep(5); continue
            try:
                from PIL import Image
                w, h = Image.open(f).size
                if want_tall != (h > w):
                    err = f"方向不對（{w}×{h}，要 {ratio}）"; os.remove(f); log(f"  ⚠ {err}，重生"); continue
            except ImportError:
                pass
            sc = face_score(list(shot_locks.values()), f) if shot_locks else None
            if sc is not None:
                log(f"     臉部相似度 {sc:.2f}（要 ≥ {FRAME_PASS}）")
                keep = f[:-4] + f"_候選{attempt + 1}" + f[-4:]
                import shutil
                shutil.copy2(f, keep)
                if sc > best[0]:
                    best = (sc, keep)
                if sc < FRAME_PASS and attempt < 2:
                    err = f"臉不像（{sc:.2f}）"; os.remove(f); log("  ⚠ 臉跟定妝照不像，重生"); continue
                if sc < FRAME_PASS:
                    shutil.copy2(best[1], f); log(f"  ⚠ 3 次都沒過，用最像的一張（{best[0]:.2f}）")
            err = ""; break
        for p in os.listdir(FRAME_DIR):      # 清掉候選圖
            if p.startswith(os.path.basename(f)[:-4] + "_候選"):
                os.remove(os.path.join(FRAME_DIR, p))
        if err:
            if k == 2 and frame_file(s["no"], 1)[1]:
                _TAIL_BROKEN.append(1)
                log(f"  ⚠ 尾幀做不出來（{err[:120]}），改用「只有首幀」出片（首幀的人物和臉已經比對過）")
                return frame_file(s["no"], 1)[0], None, made
            raise RuntimeError(f"{name}幀生圖失敗（試了 3 次）：{err}")
        made.append(os.path.relpath(f, ROOT))
    return frame_file(s["no"], 1)[0], frame_file(s["no"], 2)[0], made


def video_face(locks, mp4, skip=()):
    """影片抽 3 格比對臉：每位出場角色取 3 格裡最像的那張臉，回傳最低的那位（有人沒出現就會很低）。
    2026-11-15 修正：舊版只要畫面裡「有任一位」角色像就算過，結果主角整個沒出現也放行。
    skip：分鏡寫明背對鏡頭的角色，不檢查。全部都沒臉可判斷回傳 None。"""
    fc = _fc()
    locks = [L for L in (locks or []) if L.get("feats") and L.get("name") not in skip]
    if not locks or not fc or not os.path.exists(mp4):
        return None
    import tempfile, cv2
    try:
        d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).strip())
    except Exception:
        return None
    m = fc._models(); best = [0.0] * len(locks); any_face = False
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate((0.2, 0.5, 0.8)):
            p = os.path.join(td, f"{i}.png")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{d * t:.2f}", "-i", mp4, "-frames:v", "1", p], capture_output=True)
            fs = [x for x in (fc.faces(p) or []) if x[0] >= 30 * 30] if os.path.exists(p) else []
            any_face |= bool(fs)
            for j, L in enumerate(locks):
                for r in L["feats"]:
                    for _, f in fs:
                        best[j] = max(best[j], float(m["rec"].match(r, f, cv2.FaceRecognizerSF_FR_COSINE)))
    return min(best) if any_face else None


def same_as_other(path):
    """這個片段是不是和同資料夾其他片段完全相同（抓錯影片）。"""
    import hashlib
    if not os.path.exists(path):
        return False
    h = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
    me = h(path); d = os.path.dirname(os.path.abspath(path))
    return any(h(os.path.join(d, f)) == me for f in os.listdir(d)
               if f.endswith(".mp4") and os.path.join(d, f) != os.path.abspath(path))


def back_facing(req, s):
    """分鏡裡寫「背對／背影」的角色（看不到臉，不檢查）。"""
    out = set()
    for cl in re.split(r"[，。；！？]", s.get("visual") or ""):
        if re.search("背對|背影", cl):
            for c in cs.chars_in_shot(req, s):
                nm = c["name"]
                if nm in cl or re.sub(r"(老師|總裁|小姐|先生|師父)$", "", nm) in cl:
                    out.add(nm)
    return out


def gen_flow(prompt, out, sec, res, ratio, accounts, max_cost, refs=None, frames=None, more=None):
    import cli_anything_flow as caf
    tried = []
    status = run_cli(["status"])
    logged = {t["account"] for t in status.get("flow_tabs", []) if t.get("account")}
    order = [a for a in accounts if a.get("email")] or [{"email": e} for e in sorted(logged)]
    for ac in order:
        em = ac["email"]
        if em not in logged:
            r = run_cli(["login", "--account", em] + (["--password", ac["password"]] if ac.get("password") else []), timeout=180)
            if not r.get("ok"):
                tried.append({"account": em, "login": r});
                if r.get("need_human"):
                    print(f"⚠ {em} 需要你本人在 Chrome 完成登入（{r.get('message','')}）", flush=True)
                continue
            logged.add(em)
        c = run_cli(["credits", "--account", em]).get("credits", [{}])
        cr = (c[0] or {}).get("credits") if c else None
        if cr is not None and cr < 5:
            tried.append({"account": em, "credits": cr, "skip": "點數不足"}); continue
        extra = []
        if frames:      # 2026-11-15 首尾幀：不另外附角色設定圖（人物已經在首尾幀裡）
            extra = ["--first", frames[0]] + (["--last", frames[1]] if frames[1] else []) + ["--ref-cache", os.path.join(FRAME_DIR, ".flow參考圖快取.json")]
        for rp in ([] if frames else refs or []):      # 角色設定圖：附進 Flow 提示詞當參考（同帳號同專案上傳過就直接選，不重複上傳）
            extra += ["--ref", rp]
        if extra and not frames:
            extra += ["--ref-cache", os.path.join(ROOT, "01_人物", ".flow參考圖快取.json")]
        r = run_cli(["gen", "--account", em, "--prompt", prompt, "--out", out, "--seconds", str(sec), "--res", res, "--ratio", ratio, "--max-cost", str(max_cost)] + extra + list(more or []))
        if r.get("ok"):
            r["route"] = "A"; r["tried"] = tried; return r
        tried.append({"account": em, "result": r})
    return {"ok": False, "need_api": True, "tried": tried}


def gen_api(prompt, out, sec, res, ratio, key, frames=None):
    if not key:
        return {"ok": False, "error": "B 路需要 Gemini API 金鑰（帳號與金鑰.json 的 apiKey）"}
    sys.path.insert(0, TOOLS)
    import omni_api        # 背景生成＋每 15 秒查一次（官方同步呼叫可能卡很久）
    sec = max(3, min(15, int(sec)))
    try:
        return omni_api.generate(prompt, key, sec, res, ratio, out, log=lambda m: print("  " + m, flush=True), images=list(frames or []))
    except Exception as e:
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg:
            msg = "這把 Gemini 金鑰沒有影片生成額度（RESOURCE_EXHAUSTED）：請到 https://aistudio.google.com 確認專案已開通付費。"
        return {"ok": False, "route": "B", "error": msg[:500]}


def run_fal(req, shots, a, refs_for, chars, sheet_rows, use_ref, OUTD, log, logp):
    """F 路：FAL 付費出片。--dry 只列計畫；沒有 --yes 只印確認框；--yes 才真的出片。失敗不自動重試。"""
    import fal_api
    eng = req.get("engine", {}) or {}
    model = a.fal_model or eng.get("falModel") or "kling"
    if model not in fal_api.MODELS:
        model = "kling"
    M = fal_api.MODELS[model]
    ratio = req.get("output", {}).get("ratio", "16:9")
    max_usd = float(eng.get("falMaxUsdPerShot") or 1.0)
    key, ksrc = fal_api.get_key(ROOT)
    rows, total = [], 0.0
    for s in shots:
        no = int(s["no"]); out = os.path.join(OUTD, f"shot_{no:02d}.mp4")
        rr = refs_for(s)
        skip = os.path.exists(out) and not a.only and not a.redo
        b, usd = fal_api.estimate(model, s.get("sec", 5), bool(rr))
        rows.append({"s": s, "no": no, "out": out, "rr": rr, "skip": skip, "billed": b, "usd": usd})
        total += 0 if skip else usd
    todo = [r for r in rows if not r["skip"]]
    if a.dry:
        for r in rows:
            print(f"第 {r['no']} 鏡（{r['s'].get('sec', 5)} 秒）：\n{shot_prompt(req, r['s'])}\n")
        print("======== 出片計畫（F 路 FAL；--dry：不花錢、不生成） ========")
        print(f"【FAL 金鑰】{'有（來源：' + ksrc + '）' if key else '沒有：在生成器 ⑨ 貼 FAL 金鑰重新下載，或在 帳號與金鑰.json 填 falKey'}")
        lp = fal_api.live_prices(key, [M["i2v"]]) if key else {}
        live = lp.get(M["i2v"])
        print(f"【模型】{M['name']}：每秒 US${M['usd_per_sec']:.2f}"
              + (f"（剛剛向 FAL 查到的單價：US${live[0]}／{'秒' if live[1] == 'seconds' else live[1]}）" if live else ""))
        if chars and a.no_ref:
            print("【角色設定圖】已加 --no-ref：每鏡文字生影片。")
        elif chars:
            cs.print_plan(list(sheet_rows.values()))
        else:
            print("【角色設定圖】這支影片沒有角色：每鏡文字生影片。")
        print(f"\n【每鏡】（Kling／Wan 一鏡只能 5 或 10 秒：7 秒以下算 5 秒，超過算 10 秒；每鏡上限 US${max_usd:.2f}）")
        for r in rows:
            if r["skip"]:
                print(f"  第 {r['no']} 鏡：已有片段，跳過（US$0）"); continue
            how = (f"圖生影片（首幀用 {'、'.join(x['name'] for x in r['rr'])} 的設定圖，FLUX Kontext US${fal_api.FRAME['usd']:.2f}）") if r["rr"] else "文字生影片"
            print(f"  第 {r['no']} 鏡：{how}｜{model}｜需求 {r['s'].get('sec', 5)} 秒 → 計費 {r['billed']} 秒｜預估 US${r['usd']:.2f}")
        print(f"\n預估合計 US${total:.2f}，從你的 FAL 額度扣（實扣以 https://fal.ai/dashboard 的帳單為準）。")
        if use_ref:
            miss = [x for x in sheet_rows.values() if x["used"] and not x["ready"]]
            if miss:
                print("⚠ 出片前要先完成：" + "；".join(f"{x['name']}：{x['state']}" for x in miss))
        return
    if not key:
        print("⛔ 沒有 FAL 金鑰（沒有花錢）：在生成器 ⑨ 生成引擎貼上 FAL 金鑰重新下載，或在 帳號與金鑰.json 填 falKey。", flush=True)
        sys.exit(1)
    if not todo:
        print("每一鏡都已經有片段，沒有要出的（要重做用 --only N 或 --redo）。")
        return
    over = [r for r in todo if r["usd"] > max_usd]
    if over:
        print(f"⛔ 第 {'、'.join(str(r['no']) for r in over)} 鏡預估超過每鏡上限 US${max_usd:.2f}（沒有花錢）。"
              "請改短秒數、改用 wan，或在 影片需求.json 的 engine.falMaxUsdPerShot 調高。", flush=True)
        sys.exit(4)
    if not a.yes:
        print("【要花錢，請確認】")
        print(f"要做什麼：F 路 FAL 出片 第 {'、'.join(str(r['no']) for r in todo)} 鏡（共 {len(todo)} 鏡）")
        print(f"平台與模型：FAL｜{M['name']}" + ("；有角色的鏡頭先用 FLUX Kontext 把角色設定圖做成首幀" if any(r["rr"] for r in todo) else ""))
        print(f"預估花費：預估 US${total:.2f}，從你的 FAL 額度扣（實扣以 fal.ai 帳單為準）")
        print("秒數：" + "、".join(f"第 {r['no']} 鏡 {r['billed']} 秒" for r in todo) + "（Kling／Wan 一鏡只能 5 或 10 秒）")
        print("失敗不會自動重試；已經有的片段會跳過、不重複花錢。")
        print("請回覆「確認」開始，或「取消」。（收到「確認」後才執行：python tools/flow_run.py --yes）", flush=True)
        sys.exit(4)
    spent = 0.0
    for r in todo:
        s, no, out = r["s"], r["no"], r["out"]
        p = shot_prompt(req, s)
        ref = os.path.join(ROOT, r["rr"][0]["file"]) if r["rr"] and r["rr"][0].get("file") else None
        print(f"\n▶ 第 {no} 鏡（F 路 FAL、{M['name']}、計費 {r['billed']} 秒、預估 US${r['usd']:.2f}）開始…", flush=True)
        if ref:
            print("  角色設定圖：" + os.path.relpath(ref, ROOT), flush=True)
        try:
            fo = os.path.join(ROOT, "01_人物", "首幀", f"shot_{no:02d}_首幀.png") if ref else None
            res = fal_api.generate_shot(p, out, s.get("sec", 5), ratio, key, model, ref_image=ref, scene=p, frame_out=fo,
                                        log=lambda m: print("  " + m, flush=True))
            if res.get("frame_file"):
                res["frame_file"] = os.path.relpath(res["frame_file"], ROOT)
            res["file"] = os.path.relpath(res["file"], ROOT)
        except Exception as e:
            res = {"ok": False, "route": "F", "model": model, "error": str(e)[:600]}
        log["shots"][str(no)] = res | {"prompt": p, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        if res.get("ok"):
            spent += res.get("cost_usd") or 0
            log["fal_total_usd"] = round((log.get("fal_total_usd") or 0) + (res.get("cost_usd") or 0), 3)
        json.dump(log, open(logp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if res.get("ok"):
            print(f"  ✅ 完成：{res['file']}（F 路、{model}、約 US${res['cost_usd']:.2f}、編號 {res['request_id']}）", flush=True)
        else:
            print(f"  ❌ 第 {no} 鏡失敗（不會自動重試）：{res['error']}", flush=True)
            print(f"     請先跟使用者說明原因，改好後再出一次確認框；確認後用 python tools/flow_run.py --only {no} --yes 重做。", flush=True)
            break
    done = sum(1 for s in req["shots"] if os.path.exists(os.path.join(OUTD, f"shot_{int(s['no']):02d}.mp4")))
    print(f"\n這次約花 US${spent:.2f}（依公開單價計算；實扣看 https://fal.ai/dashboard ）。"
          f"片段完成 {done}／{len(req['shots'])} 鏡。全部完成後執行：python tools/make_final.py", flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int); ap.add_argument("--dry", action="store_true"); ap.add_argument("--res"); ap.add_argument("--outdir", default="片段")
    # 2026-11-13 點數與付費安全門禁：Flow 點數用完不自動改走付費 B 路（要使用者確認後加 --allow-b）；
    # 已經有的片段預設跳過，不重複扣點（要重做某鏡用 --only N，或全部重做加 --redo）
    ap.add_argument("--allow-b", action="store_true", help="使用者已確認可改走付費 B 路（Gemini API）")
    ap.add_argument("--redo", action="store_true", help="已有的片段也重新生成（會扣點數）")
    ap.add_argument("--no-ref", action="store_true", help="不用角色設定圖當參考圖，改回每鏡純文字生成")
    ap.add_argument("--yes", action="store_true", help="F 路：使用者看過「要花錢，請確認」框並回覆「確認」")
    ap.add_argument("--fal-model", choices=["kling", "wan"], help="F 路：臨時換 FAL 模型")
    ap.add_argument("--frames-only", action="store_true", help="只生首尾幀圖片（Flow 生圖 0 點），不出影片")
    ap.add_argument("--no-frames", action="store_true", help="不用首尾幀，改回一般出片")
    ap.add_argument("--no-lock", action="store_true", help="不做定妝照鎖臉（不建議）")
    ap.add_argument("--face-retry", type=int, default=1, help="影片裡的臉不像時自動重做幾次（每次會再扣點數，0＝不重做）")
    # 2026-11-21 Flow 新功能
    ap.add_argument("--edit", type=int, help="用 Flow 代理『修改』第 N 鏡現有影片（不整鏡重生；費用同生成、按秒計），搭配 --edit-prompt")
    ap.add_argument("--edit-prompt", help="要怎麼改（例：最後她的手要完全蓋住鏡頭）")
    ap.add_argument("--no-character", action="store_true", help="不用 Flow 角色（回到每鏡附定妝照）")
    a = ap.parse_args()
    req = load("影片需求.json"); sec_ = load("帳號與金鑰.json", {}) or {}
    if not req:
        print("找不到 影片需求.json"); sys.exit(1)
    route = req.get("route") or req.get("engine", {}).get("route", "auto")
    res = a.res or req.get("output", {}).get("res", "360p"); ratio = req.get("output", {}).get("ratio", "16:9")
    max_cost = int(req.get("engine", {}).get("maxCostPerShot", 30))
    OUTD = os.path.join(ROOT, a.outdir); os.makedirs(OUTD, exist_ok=True)
    logp = os.path.join(ROOT, "出片紀錄.json"); log = load("出片紀錄.json", {"shots": {}}) or {"shots": {}}
    shots = req["shots"] if not a.only else [s for s in req["shots"] if int(s["no"]) == a.only]
    chars = [c for c in req.get("characters", []) if c.get("name")]
    use_ref = bool(chars) and not a.no_ref and route != "manual"
    sheet_rows = {r["name"]: r for r in cs.plan(req)} if chars else {}

    def refs_for(s):
        return [sheet_rows[c["name"]] for c in cs.chars_in_shot(req, s) if c["name"] in sheet_rows] if use_ref else []

    if route == "F" and a.dry:
        return run_fal(req, shots, a, refs_for, chars, sheet_rows, use_ref, OUTD, log, logp)
    if a.dry or route == "manual":
        lines = []
        for s in shots:
            rr = refs_for(s)
            ref_txt = ("（參考圖：" + "、".join(f"{r['name']}→{r['file'] or '01_人物/角色設定圖_' + cs.safe(r['name']) + '.png（待產生）'}" for r in rr) + "）") if rr else ""
            if wants_frames(s, a):
                f1, f2 = frame_file(s["no"], 1), frame_file(s["no"], 2)
                ref_txt = (f"（首尾幀：{os.path.relpath(f1[0], ROOT)}{'' if f1[1] else '（待生成）'}、"
                           f"{os.path.relpath(f2[0], ROOT)}{'' if f2[1] else '（待生成）'}）")
            lines.append(f"第 {s['no']} 鏡（{s.get('sec',5)} 秒）{ref_txt}：\n{shot_prompt(req, s)}\n")
        open(os.path.join(ROOT, "Flow提示詞清單.txt"), "w", encoding="utf-8").write("\n".join(lines))
        print("\n".join(lines)); print("已存成 Flow提示詞清單.txt（可以自己貼進 https://flow.google.com ）")
        if route == "manual":
            if chars:
                print("\n（manual：想讓人物一致，可以先做角色設定圖，再在 Flow 按提示詞框左邊的「＋」（在提示詞輸入框新增素材）→「上傳媒體」附上設定圖。）")
            if any(wants_frames(s, a) for s in shots):
                print("（manual 首尾幀：在 Flow 按「＋」上傳 首尾幀/p01-1、p01-2，提示詞寫「第 1 張是首幀、第 2 張是尾幀，用畫面轉影片：首幀和尾幀生成」。不想手動就把 route 改回 auto，AI 會自己做。）")
            return
        # 2026-11-13 點數門禁：設定圖＋每鏡是否用參考圖＋預估點數
        print("\n======== 出片計畫（--dry：不花點數、不生成） ========")
        if a.frames_only:      # 2026-11-15 冷測：--frames-only 只生圖，下面列的影片點數是「之後正式出片」才會花
            print("（你加了 --frames-only：拿掉 --dry 後只會用 Flow 生首尾幀圖片，0 點、不出影片；下面的影片點數是之後正式出片才會花）")
        if chars and a.no_ref:
            print("【角色設定圖】已加 --no-ref：不用參考圖，每鏡純文字生成（只靠英文描述詞讓人物一致）。")
        elif chars:
            cs.print_plan(list(sheet_rows.values()))
        else:
            print("【角色設定圖】這支影片沒有角色：每鏡純文字生成。")
        n_pt, pt_txt = est_points(res)
        print(f"\n【每鏡】（{res}、Google Flow Omni 1.2 Flash；Flow 送出前會報實際點數，超過每鏡上限 {max_cost} 點自動拒絕）")
        total = 0
        for s in shots:
            no = int(s["no"]); out = os.path.join(OUTD, f"shot_{no:02d}.mp4")
            rr = refs_for(s)
            if os.path.exists(out) and not a.only and not a.redo:
                print(f"  第 {no} 鏡：已有片段，跳過（0 點）"); continue
            total += n_pt
            how = ("用參考圖：" + "、".join(r["name"] for r in rr)) if rr else ("純文字（--no-ref）" if (a.no_ref and cs.chars_in_shot(req, s)) else "純文字（這鏡沒有角色）")
            if wants_frames(s, a):
                miss = [x for x in (1, 2) if not frame_file(no, x)[1]]
                how = "首尾幀（畫面轉影片）" + (f"；先用 Flow 生{'、'.join('首幀' if x == 1 else '尾幀' for x in miss)}（0 點）" if miss else "；首尾幀圖已備好")
            print(f"  第 {no} 鏡：{how}｜{s.get('sec',5)} 秒｜預估 {pt_txt}")
        print(f"\n影片預估合計：約 {total} 點（{res}）。實際點數以 Flow 送出前的確認訊息為準（老師實測：參考圖出片 1 鏡 5 點）。")
        if use_ref:
            miss = [r for r in sheet_rows.values() if r["used"] and not r["ready"]]
            if miss:
                print("⚠ 出片前要先完成：" + "；".join(f"{r['name']}：{r['state']}" for r in miss))
                print("   產生：先出確認框 → python tools/char_sheet.py make --yes → 打開圖給使用者看 → 使用者說 OK：python tools/char_sheet.py approve")
        return
    if use_ref:      # 出片前門禁：有出場的角色都要有設定圖、且使用者確認過外觀
        miss = [r for r in sheet_rows.values() if r["used"] and not r["ready"]]
        if miss:
            print("⛔ 還不能出片：角色設定圖還沒準備好（沒有花任何點數）。", flush=True)
            cs.print_plan(list(sheet_rows.values()))
            print("\n請先：① 出確認框、使用者回覆「確認」後 python tools/char_sheet.py make --yes ② 把 01_人物/ 的設定圖打開給使用者看"
                  "\n③ 使用者說外觀 OK：python tools/char_sheet.py approve ④ 再執行 python tools/flow_run.py"
                  "\n不想用設定圖：python tools/flow_run.py --no-ref（改回純文字）", flush=True)
            sys.exit(3)
    if route == "F":
        return run_fal(req, shots, a, refs_for, chars, sheet_rows, use_ref, OUTD, log, logp)
    if route in ("auto", "A") and not ensure_bridge():
        print("⚠ Chrome 的「Flow 小幫手」沒有連上。請確認：Chrome 開著、擴充功能已啟用、有開 https://flow.google.com 分頁。", flush=True)
        if route == "A":
            sys.exit(2)
    locks = {}
    if use_ref and route in ("auto", "A") and not a.no_lock:      # 2026-11-15 鎖臉：先做定妝照
        names = []
        for s in shots:
            if os.path.exists(os.path.join(OUTD, f"shot_{int(s['no']):02d}.mp4")) and not a.only and not a.redo:
                continue
            names += [r["name"] for r in refs_for(s) if r["name"] not in names]
        if names:
            print("\n🔒 鎖臉：每位角色先做一張定妝照（照參考照的臉、穿這部戲的服裝），之後每一鏡都照它", flush=True)
            locks = lock_faces(req, sheet_rows, names, ratio, sec_.get("accounts", []), log=lambda m: print(m, flush=True))
            if not _fc():
                print("  （沒有 opencv，略過臉部比對；裝了 opencv-python 會自動檢查每鏡的臉像不像）", flush=True)

    def locks_in(s):
        return {c["name"]: locks[c["name"]] for c in cs.chars_in_shot(req, s) if c["name"] in locks}

    # 2026-11-21 Flow 新功能：①花錢安全門（生成前需確認＝一律）②代理記憶（專案規則寫一次）③Flow 角色（臉＋服裝＋聲音）
    flow_chars = {}
    if route in ("auto", "A") and not a.frames_only:
        sr = run_cli(["safety"])
        if not sr.get("ok"):
            print("⛔ 無法確認 Flow 代理設定『生成前需確認＝一律』，為了安全先不出片：" + json.dumps(sr, ensure_ascii=False)[:200], flush=True)
            sys.exit(4)
        print("🔐 代理設定『生成前需確認』＝一律（每次扣點前都會先報價）", flush=True)
        if req.get("flowMemory"):
            mr = run_cli(["memory", "--title", (req.get("flowMemoryTitle") or req.get("title") or "拍攝規則")[:30], "--text", req["flowMemory"]])
            print(f"🧠 代理記憶：{mr.get('result')}", flush=True)
        if not a.no_character:
            for ch in req.get("characters", []):
                fcfg = ch.get("flowCharacter")
                if not fcfg or not ch.get("name"):
                    continue
                img = (locks.get(ch["name"]) or {}).get("lock") or (os.path.join(ROOT, ch["sheet_file"]) if ch.get("sheet_file") else None)
                if not img or not os.path.exists(img):
                    print(f"  ⚠ 角色「{ch['name']}」沒有定妝照，略過建立 Flow 角色", flush=True)
                    continue
                fcfg = fcfg if isinstance(fcfg, dict) else {}
                cr = run_cli(["character", "--name", ch["name"], "--image", img]
                             + (["--voice", fcfg["voice"]] if fcfg.get("voice") else [])
                             + (["--voice-style", fcfg["voiceStyle"]] if fcfg.get("voiceStyle") else [])
                             + (["--info", fcfg["info"]] if fcfg.get("info") else []), timeout=600)
                if cr.get("ok"):
                    flow_chars[ch["name"]] = True
                    print(f"👤 Flow 角色「{ch['name']}」：{'已存在' if cr.get('result') == 'exists' else '已建立（臉＋服裝＋聲音）'}", flush=True)
                else:
                    print(f"  ⚠ Flow 角色「{ch['name']}」建立失敗，這次改回附定妝照：{json.dumps(cr, ensure_ascii=False)[:200]}", flush=True)

    def char_args(s):
        names = [c["name"] for c in cs.chars_in_shot(req, s) if c["name"] in flow_chars]
        return ["--character", names[0]] if names else []

    def video_key(no):
        """第 N 鏡在 Flow 專案裡的影片：優先用卡片標題（重新載入也找得到），沒有才用 media_id。"""
        rec = (log.get("shots") or {}).get(str(no)) or {}
        if rec.get("title"):
            return "title:" + rec["title"]
        return rec.get("media_id")

    def show_hint(r):
        for t in (r or {}).get("tried", []):
            if isinstance(t.get("result"), dict) and t["result"].get("hint"):
                print("  💡 " + t["result"]["hint"], flush=True)
                return

    if a.edit:      # 2026-11-21 修改既有影片（不整鏡重生）
        key = video_key(a.edit)
        if not key or not a.edit_prompt:
            print('用法：python tools/flow_run.py --edit N --edit-prompt "要怎麼改"（第 N 鏡要先有出片紀錄）', flush=True)
            sys.exit(1)
        out = os.path.join(OUTD, f"shot_{a.edit:02d}.mp4")
        if os.path.exists(out):
            import shutil
            shutil.copy2(out, out.replace(".mp4", f"_改前_{time.strftime('%Y%m%d_%H%M')}.mp4"))
        s = next(x for x in req["shots"] if int(x["no"]) == a.edit)
        print(f"\n✏️ 修改第 {a.edit} 鏡：{a.edit_prompt}", flush=True)
        r = gen_flow(a.edit_prompt, out, max(3, min(10, int(s.get("sec") or 5))), res, ratio, sec_.get("accounts", []), max_cost, None, None,
                     ["--edit", key] + char_args(s))
        show_hint(r)
        log["shots"][str(a.edit)] = {**(log["shots"].get(str(a.edit)) or {}), **{k: v for k, v in r.items() if k != "tried"},
                                     "edit_prompt": a.edit_prompt, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        json.dump(log, open(logp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if r.get("ok"):
            print("  ✅ 改好了：" + os.path.relpath(out, ROOT) + f"（{r.get('cost')} 點；原片已備份成 _改前_）", flush=True)
        else:
            print("  ❌ 修改失敗：" + json.dumps(r, ensure_ascii=False)[:300], flush=True)
        return

    if a.frames_only:      # 2026-11-15：只生首尾幀圖片（0 點），給使用者看過再出片
        fs = [s for s in shots if wants_frames(s, a)]
        if not fs:
            print("這支影片的分鏡沒有首尾幀提示詞，首尾幀/ 也沒有圖（生成器分鏡區按「✨ 生成首尾幀圖片提示詞」再重新下載製作包）。"); return
        for s in fs:
            no = int(s["no"]); print(f"\n▶ 第 {no} 鏡首尾幀", flush=True)
            try:
                f1, f2, made = make_frames(req, s, ratio, sec_.get("accounts", []), [os.path.join(ROOT, r["file"]) for r in refs_for(s) if r.get("file")], log=lambda m: print(m, flush=True), locks=locks)
                print(f"  ✅ {os.path.relpath(f1, ROOT)}、{os.path.relpath(f2, ROOT)}" + ("（這次新生：" + "、".join(made) + "）" if made else "（已經有，沒重生）"), flush=True)
            except Exception as e:
                print(f"  ❌ {e}", flush=True)
        print("\n請把 首尾幀/ 的圖打開給使用者看；要重生某張就刪掉那張再跑一次 --frames-only。OK 後執行：python tools/flow_run.py", flush=True)
        return
    api_only = False
    failed = []
    for s in shots:
        no = int(s["no"]); out = os.path.join(OUTD, f"shot_{no:02d}.mp4")
        sec = max(3, min(10, int(s.get("sec") or 5)))
        p = shot_prompt(req, s)
        if os.path.exists(out) and not a.only and not a.redo:
            print(f"\n▷ 第 {no} 鏡已經有片段，跳過（不扣點數；要重做用 --only {no}）", flush=True); continue
        print(f"\n▶ 第 {no} 鏡（{sec} 秒、{res}）開始…", flush=True)
        r = None
        frames = None
        if wants_frames(s, a) and route in ("auto", "A", "B"):
            try:
                cref = [os.path.join(ROOT, x["file"]) for x in refs_for(s) if x.get("file")]
                if route == "B" or api_only:
                    if frame_file(no, 1)[1] and frame_file(no, 2)[1]:
                        frames = (frame_file(no, 1)[0], frame_file(no, 2)[0])
                    else:
                        print("  （B 路不會自己生首尾幀圖；先用 --frames-only 在 Flow 生好，這鏡先照一般方式出片）", flush=True)
                else:
                    f1, f2, made = make_frames(req, s, ratio, sec_.get("accounts", []), cref, log=lambda m: print(m, flush=True), locks=locks)
                    frames = (f1, f2)
                if frames:
                    print(f"  首尾幀：{os.path.relpath(frames[0], ROOT)} → {os.path.relpath(frames[1], ROOT) if frames[1] else '（只有首幀）'}（畫面轉影片）", flush=True)
            except Exception as e:
                print(f"  ⚠ 首尾幀沒做成（{e}），這鏡改用一般方式出片", flush=True); frames = None
        if route in ("auto", "A") and not api_only and s.get("extendFrom"):      # 2026-11-21 一鏡到底：接著第 N 鏡最後一格延伸
            src = int(s["extendFrom"]); key = s.get("extendKey") or video_key(src)
            sl = locks_in(s)
            refs = ([L["lock"] for L in sl.values()] or [os.path.join(ROOT, r["file"]) for r in refs_for(s) if r.get("file")])[:3]
            if not key:
                print(f"  ❌ 第 {src} 鏡還沒有出片紀錄，無法延伸", flush=True)
                failed.append((no, "error"))
                continue
            print(f"  延伸：接在第 {src} 鏡最後一格之後（{key}）" + ("；參考圖：" + "、".join(os.path.relpath(x, ROOT) for x in refs) if refs else ""), flush=True)
            r = gen_flow(neutral(p, req, s, sl, "first"), out, sec, res, ratio, sec_.get("accounts", []), max_cost, refs, None, ["--extend", key] + char_args(s))
            show_hint(r)
        elif route in ("auto", "A") and not api_only:
            sl = locks_in(s)
            refs = [L["lock"] for L in sl.values()] or [os.path.join(ROOT, r["file"]) for r in refs_for(s) if r.get("file")]
            if refs and not frames:
                print("  參考圖：" + "、".join(os.path.relpath(x, ROOT) for x in refs), flush=True)
            pv = neutral(p, req, s, sl, "first" if frames else "ref")      # 鎖臉：提示詞不再描述長相，照首幀／定妝照
            ca = char_args(s)
            if ca and not frames:      # 2026-11-21 有 Flow 角色：不用再附定妝照（角色已含臉＋服裝＋聲音）
                refs = []
            r = gen_flow(pv, out, sec, res, ratio, sec_.get("accounts", []), max_cost, refs, frames, ca)
            if not r.get("ok"):
                show_hint(r)
            if r.get("ok") and same_as_other(r.get("file") or out):      # 2026-11-15 實測：偶爾會下載到專案裡前一支影片
                print("  ↻ 下載到的影片和別鏡一模一樣（抓錯了），重新出片一次", flush=True)
                r = gen_flow(pv, out, sec, res, ratio, sec_.get("accounts", []), max_cost, refs, frames, ca)
                if r.get("ok") and same_as_other(r.get("file") or out):
                    r = {"ok": False, "error": "下載到的影片和別鏡重複", "tried": [{"error": "duplicate"}]}
            if not r.get("ok") and frames and re.search("違反|政策", json.dumps(r.get("tried", []), ensure_ascii=False)):
                # 2026-11-15 實測：Flow 也會審查首尾幀圖片（有人倒地、揮棍的畫面），被擋時點數會退還 → 自動改用純文字＋角色參考圖重試一次
                print("  ↻ 首尾幀被 Flow 安全審查擋下（點數已退還），自動改用文字＋定妝照再試一次", flush=True)
                frames = None; pv = neutral(p, req, s, sl, "ref")
                r = gen_flow(pv, out, sec, res, ratio, sec_.get("accounts", []), max_cost, refs, None)
            for _ in range(a.face_retry if (r.get("ok") and sl and not frames) else 0):     # 用首幀出片：人物已在首幀比對過（側臉在影片裡分數偏低，不再重做）
                # 影片裡的臉跑掉 → 自動重做（會再扣一次點數）
                vf = video_face([dict(L, name=k) for k, L in sl.items()], r.get("file") or out, back_facing(req, s))
                if vf is None or vf >= VIDEO_LOW:
                    if vf is not None:
                        print(f"  臉部相似度 {vf:.2f} ✓", flush=True)
                    r["face"] = vf; break
                print(f"  ↻ 影片裡的臉和定妝照不像（{vf:.2f} < {VIDEO_LOW}），自動重做一次", flush=True)
                r2 = gen_flow(pv, out, sec, res, ratio, sec_.get("accounts", []), max_cost, refs, frames, ca)
                if r2.get("ok"):
                    r2["cost"] = (r.get("cost") or 0) + (r2.get("cost") or 0); r = r2
                    r["face"] = video_face([dict(L, name=k) for k, L in sl.items()], r.get("file") or out, back_facing(req, s))
            if not r.get("ok") and r.get("need_api") and route == "auto":
                why = [t for t in r.get("tried", []) if not t.get("skip") and not (t.get("credits") is not None and t["credits"] < 5)]
                if why:      # 2026-11-15 不是點數問題（政策擋下、橋接中斷、介面改版）就照實說；一鏡失敗不要整批停
                    txt = json.dumps(why, ensure_ascii=False)
                    policy = "違反" in txt or "政策" in txt
                    print("  ❌ Flow 出片失敗（不是點數問題）：" + txt[:400], flush=True)
                    failed.append((no, "policy" if policy else "error"))
                    log["shots"][str(no)] = {"ok": False, "reason": "policy" if policy else "flow_error", "prompt": p, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                    json.dump(log, open(logp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                    if "urlopen error" in txt or "拒絕連線" in txt:
                        print("     Flow 小幫手的連線斷了，先停下來（已完成的鏡不會重做）。", flush=True); break
                    if policy:
                        print("     這鏡被 Flow 安全審查擋下（點數已退還），先繼續做其他鏡。", flush=True)
                    continue
                if not a.allow_b:
                    print("  ⛔ Flow 帳號點數都用完了。依安全門禁不會自動改走付費的 B 路（Gemini API）。\n"
                          "     請先問使用者：①明天點數恢復再繼續 ②同意付費走 B 路（再執行 python tools/flow_run.py --allow-b，已完成的鏡會自動跳過）③改用免費備援技能。", flush=True)
                    break
                print("  Flow 帳號點數都用完了，使用者已同意，改走 B 路（Gemini API）", flush=True); api_only = True; r = None
        if r is None and route in ("auto", "B"):
            r = gen_api(p, out, sec, res, ratio, sec_.get("apiKey"), frames)
        log["shots"][str(no)] = {k: v for k, v in (r or {}).items() if k != "tried"} | {"prompt": p, "time": time.strftime("%Y-%m-%d %H:%M:%S")} \
            | ({"frames": [os.path.relpath(x, ROOT) for x in frames if x]} if frames else {})
        json.dump(log, open(logp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if r and r.get("ok"):
            print(f"  ✅ 完成：{os.path.relpath(r.get('file') or out, ROOT)}（{r.get('route')} 路{('、' + r['account']) if r.get('account') else ''}{('、' + str(r['cost']) + ' 點') if r.get('cost') else ''}）", flush=True)
        else:
            print(f"  ❌ 第 {no} 鏡失敗：{json.dumps(r, ensure_ascii=False)[:400]}", flush=True)
    done = sum(1 for s in req["shots"] if os.path.exists(os.path.join(OUTD, f"shot_{int(s['no']):02d}.mp4")))
    if failed:      # 2026-11-15 整批做完再列失敗清單
        pol = [n for n, k in failed if k == "policy"]; oth = [n for n, k in failed if k != "policy"]
        if pol:
            print(f"\n⚠ 第 {'、'.join(map(str, pol))} 鏡被 Google Flow 安全審查擋下（點數已退還）。請 AI 照 SKILL.md「打鬥鏡被擋」把這幾鏡的 prompt 改成舞台武打寫法"
                  f"（點到為止、輕推、格擋、滑倒坐進水窪，不寫打中身體部位），存回 影片需求.json，再用 python tools/flow_run.py --only N 一鏡一鏡重做。", flush=True)
        if oth:
            print(f"⚠ 第 {'、'.join(map(str, oth))} 鏡出錯（不是政策），請再執行一次 python tools/flow_run.py（已完成的鏡會跳過）。", flush=True)
    print(f"\n片段完成 {done}／{len(req['shots'])} 鏡。全部完成後執行：python tools/make_final.py", flush=True)


if __name__ == "__main__":
    main()
