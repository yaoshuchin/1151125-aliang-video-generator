"""角色設定圖（定裝圖）：先固定人物外觀，再拿它當每一鏡的參考圖，讓人物長得一樣。

用法（在製作包資料夾執行）：
  python tools/char_sheet.py status                    列出每位角色的設定圖狀態、來源、預估點數（不花點數、不生成）
  python tools/char_sheet.py prompts                   把每位角色的設定圖提示詞寫成 01_人物/角色設定圖提示詞_<角色名>.txt
  python tools/char_sheet.py make --yes [--name 小美] [--source codex|flow|fal]
                                                       產生缺少的設定圖（使用者看過確認框、回覆「確認」後才加 --yes）
  python tools/char_sheet.py approve [--name 小美]     使用者看過設定圖、說外觀 OK 後才執行：記錄確認（出片前會檢查）
  python tools/char_sheet.py redo --name 小美 --yes    不滿意：把舊圖改名保留，重新產生

來源（影片需求.json 的 characters[i].sheet_source；生成器 ⑤ 角色設定可選）：
  codex  （預設推薦）用使用者自己的 Codex CLI 內建生圖（ChatGPT 方案額度，不扣 Flow 點數）
  flow   Google Flow 生圖（Nano Banana 2.1；送出前 Flow 代理會報點數，超過 engine.maxCostPerImage〔預設 0〕自動拒絕）
  upload 使用者自己放照片或設定圖到 01_人物/（不生成）
  fal    FAL 的 FLUX.1 dev（金鑰：帳號與金鑰.json 的 falKey → 環境變數 FAL_KEY；每張約 US$0.025）
學員自己放在 01_人物/ 的照片或設定圖一律優先使用、不重做。
"""
import argparse, glob, hashlib, json, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "01_人物")
FLOW = os.path.join(ROOT, "tools", "cli-anything-flow")
APPROVE = os.path.join(PEOPLE, "角色設定圖確認.json")
LOG = os.path.join(PEOPLE, "角色設定圖紀錄.json")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
SOURCES = {"codex": "Codex 生圖", "flow": "Google Flow 生圖", "upload": "自己上傳照片／設定圖", "fal": "FAL（FLUX）"}
FAL_PRICE = "約 US$0.025／張（FLUX.1 dev，1280×720；以 fal.ai 價目與帳單為準）"


def load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def safe(name):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", (name or "角色").strip()) or "角色"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def sheet_prompt(req, ch):
    """沒有 sheet_prompt 就依 anchor 組一段（學生 teenage、不寫年齡、不寫 eyes、全身／半身中景、不特寫）。"""
    p = (ch.get("sheet_prompt") or "").strip()
    if p:
        return p
    anchor = (ch.get("anchor") or ch.get("look") or ch.get("name") or "a person").strip().rstrip(".")
    anchor = re.sub(r"consistent same person in every shot,?\s*", "", anchor, flags=re.I).strip().rstrip(",")
    look = (req.get("style") or {}).get("look", "")
    style = "realistic cinematic photo style" if not look else f"visual style matching: {look}"
    return (f"Character turnaround reference sheet of {anchor}. Three views side by side on one sheet: front view, "
            f"three-quarter view, and side view, full body in every view, same outfit and hairstyle in all views. "
            f"Plain light gray seamless background, even soft studio lighting, {style}. "
            f"No text, no labels, no watermark, no logo.")


def name_keys(name):
    """角色名比對用：全名、括號前的名字、括號裡的說明（例如「小風（3D科普國中生角色）」→ 小風、3D科普國中生角色）。"""
    name = (name or "").strip()
    keys = {name}
    m = re.match(r"^(.*?)[（(](.*?)[)）]\s*$", name)
    if m:
        keys |= {m.group(1).strip(), m.group(2).strip()}
    return [k for k in keys if len(k) >= 2]


# 2026-11-13 小白總複查：分鏡「角色」欄常寫稱呼（國中學生與父母、學生、教師），不寫角色名 → 也用身分詞比對
ROLE_GROUPS = [
    ("學生", "國中生", "高中生", "小學生", "同學", "學童", "孩子", "小孩", "student", "teenage"),
    ("老師", "教師", "導師", "teacher"),
    ("媽媽", "母親", "家長", "父母", "爸媽", "mother", "mom", "parent"),
    ("爸爸", "父親", "家長", "父母", "爸媽", "father", "dad", "parent"),
    ("校長", "principal"), ("主任",), ("阿嬤", "奶奶", "外婆", "祖母", "grandmother"), ("阿公", "爺爺", "外公", "祖父", "grandfather"),
]
NONE_WORDS = {"", "無", "沒有", "—", "-", "－", "none", "無人", "不出現"}


def role_words(c):
    """這位角色的身分詞（從名字、外觀、個性、英文描述找）。"""
    text = " ".join(str(c.get(k) or "") for k in ("name", "look", "personality", "anchor")).lower()
    out = set()
    for grp in ROLE_GROUPS:
        if any(w.lower() in text for w in grp):
            out |= set(grp)
    return out


def chars_in_shot(req, s):
    hay = " ".join(str(s.get(k) or "") for k in ("character", "visual", "action"))
    chars = [c for c in req.get("characters", []) if c.get("name")]
    hit = [c for c in chars if any(k in hay for k in name_keys(c["name"]))]
    if hit:
        return hit
    role = str(s.get("character") or "").strip()
    if role.lower() in NONE_WORDS or re.match(r"^(無|沒有|無人|不出現|none)\s*([（(:：,，、].*)?$", role, re.I):   # 2026-11-13「無（字卡畫面）」也算沒有角色
        return []
    low = (role + " " + hay).lower()
    hit = [c for c in chars if any(w.lower() in low for w in role_words(c) if len(w) >= 2)]
    if hit:
        return hit
    if len(chars) == 1 and role:          # 只有一位角色，分鏡角色欄有寫人 → 就是他
        return chars
    return []


def needed_names(req, shots=None):
    """哪些角色有在分鏡出場（角色、畫面、動作欄位提到角色名）。"""
    out = set()
    for s in shots if shots is not None else req.get("shots", []):
        out |= {c["name"] for c in chars_in_shot(req, s)}
    return out


def find_sheet(ch):
    """回傳 (檔案路徑, 種類)。種類：own＝學員自備（直接用）、made＝本工具／AI 產生的設定圖（要使用者確認）。"""
    n = safe(ch.get("name"))
    if ch.get("sheet_file"):
        p = os.path.join(ROOT, ch["sheet_file"].replace("/", os.sep))
        if os.path.exists(p):
            return p, "own"
    for ext in IMG_EXT:
        p = os.path.join(PEOPLE, f"角色設定圖_{n}{ext}")
        if os.path.exists(p):
            src = (ch.get("sheet_source") or "codex")
            log = (load(LOG, {}) or {}).get(ch.get("name"), {})
            return p, ("own" if src == "upload" and not log else "made")
    if os.path.isdir(PEOPLE):     # 學員自己放的照片：檔名含角色名
        for f in sorted(os.listdir(PEOPLE)):
            if f.lower().endswith(IMG_EXT) and ch.get("name") and any(k in f for k in name_keys(ch["name"]) + [safe(ch["name"])])                     and not f.startswith("角色設定圖_") and "_舊版" not in f:
                return os.path.join(PEOPLE, f), "own"
    return None, None


def approved(ch, path):
    rec = (load(APPROVE, {}) or {}).get(ch.get("name"))
    return bool(rec and os.path.exists(path) and rec.get("sha256") == sha(path))


def plan(req, shots=None):
    """每位角色：要不要用、來源、檔案、狀態、預估花費。"""
    need = needed_names(req, shots)
    max_img = int((req.get("engine") or {}).get("maxCostPerImage", 0))
    rows = []
    for ch in req.get("characters", []):
        if not ch.get("name"):
            continue
        src = ch.get("sheet_source") or "codex"
        path, kind = find_sheet(ch)
        if path:
            ok = kind == "own" or approved(ch, path)
            state = "學員自備，直接用" if kind == "own" else ("已確認外觀 OK" if ok else "已產生，等使用者看過說 OK（approve）")
            cost = "0（已有圖，不再生成）"
        else:
            ok = False
            state = "還沒有設定圖，要先產生" if src != "upload" else "選了「自己上傳」但 01_人物/ 沒有找到照片"
            cost = {"codex": "0 Flow 點（用 Codex／ChatGPT 方案額度，約 1 分鐘）",
                    "flow": f"Flow 圖像 Nano Banana 2.1：預估 0 點（Google 公告 Nano Banana 2 在 Flow 為 0 點；送出前代理若報超過 {max_img} 點會自動拒絕）",
                    "fal": "FAL：" + FAL_PRICE, "upload": "0"}.get(src, "?")
        rows.append({"name": ch["name"], "used": ch["name"] in need, "source": src, "source_name": SOURCES.get(src, src),
                     "file": os.path.relpath(path, ROOT) if path else None, "kind": kind, "ready": bool(path) and ok,
                     "state": state, "cost": cost, "prompt": sheet_prompt(req, ch)})
    return rows


def print_plan(rows):
    if not rows:
        print("這支影片沒有角色：不用角色設定圖，每鏡照舊用文字生成。")
        return
    print("【角色設定圖】")
    for r in rows:
        mark = "✅" if r["ready"] else ("⏳" if r["file"] else "⬜")
        print(f"  {mark} {r['name']}｜{'有出場' if r['used'] else '分鏡沒提到（不影響出片）'}｜來源：{r['source_name']}｜{r['state']}")
        if r["file"]:
            print(f"      檔案：{r['file']}")
        print(f"      預估花費：{r['cost']}")


# ---------- 產生 ----------
def write_prompt_files(req):
    os.makedirs(PEOPLE, exist_ok=True)
    out = []
    for ch in req.get("characters", []):
        if not ch.get("name"):
            continue
        p = os.path.join(PEOPLE, f"角色設定圖提示詞_{safe(ch['name'])}.txt")
        open(p, "w", encoding="utf-8").write(sheet_prompt(req, ch) + "\n")
        out.append(os.path.relpath(p, ROOT))
    return out


def log_made(name, info):
    d = load(LOG, {}) or {}
    d[name] = info | {"time": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def make_codex(req, ch, out):
    exe = shutil.which("codex")
    if not exe:
        return {"ok": False, "error": "找不到 codex 指令。請改在 Codex 對話裡說：「請用你內建的生圖工具，照 01_人物/角色設定圖提示詞_"
                                      f"{safe(ch['name'])}.txt 畫一張角色設定圖，存成 {os.path.relpath(out, ROOT)}」"}
    rel = os.path.relpath(out, ROOT).replace("\\", "/")
    instr = ("請用你內建的生圖工具（image generation）畫 1 張角色設定圖，只畫一次，不要改寫內容：\n"
             f"{sheet_prompt(req, ch)}\n\n畫好後把圖片檔複製到目前資料夾的 {rel}（PNG），不要改動其他任何檔案，最後只回報檔案路徑與像素大小。")
    t0 = time.time()
    r = subprocess.run([exe, "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", ROOT, "-"], input=instr,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if os.path.exists(out):
        return {"ok": True, "file": out, "seconds": int(time.time() - t0)}
    return {"ok": False, "error": "Codex 沒有產生圖片檔", "detail": (r.stdout + r.stderr)[-500:]}


def make_flow(req, ch, out, account=None):
    sys.path.insert(0, FLOW)
    max_img = int((req.get("engine") or {}).get("maxCostPerImage", 0))
    ratio = "16:9"
    args = [sys.executable, os.path.join(FLOW, "cli_anything_flow.py"), "gen-image", "--prompt", sheet_prompt(req, ch),
            "--out", out, "--ratio", ratio, "--max-cost", str(max_img)]
    if account:
        args += ["--account", account]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"ok": False, "error": (r.stdout + r.stderr)[-500:]}


def make_fal(req, ch, out):
    """FAL 的 FLUX.1 dev 畫角色設定圖（1280×720，每張約 US$0.025）。金鑰：帳號與金鑰.json 的 falKey → 環境變數 FAL_KEY（不印出來）。"""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fal_api
    key, _src = fal_api.get_key(ROOT)
    if not key:
        return {"ok": False, "error": "沒有 FAL 金鑰：請在生成器 ⑨ 生成引擎貼 FAL 金鑰重新下載，或在 帳號與金鑰.json 填 falKey（不要貼到對話裡）"}
    try:
        r = fal_api.flux_image(sheet_prompt(req, ch), out, key, log=lambda m: print("  " + m, flush=True))
        return r | {"cost": f"約 US${r['cost_usd']:.3f}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:400]}


def make(req, names=None, source=None, account=None):
    os.makedirs(PEOPLE, exist_ok=True)
    write_prompt_files(req)
    res = []
    for ch in req.get("characters", []):
        if not ch.get("name") or (names and ch["name"] not in names):
            continue
        path, kind = find_sheet(ch)
        if path:
            res.append({"name": ch["name"], "skip": "已有設定圖或學員自備照片，不重做", "file": os.path.relpath(path, ROOT)}); continue
        src = source or ch.get("sheet_source") or "codex"
        out = os.path.join(PEOPLE, f"角色設定圖_{safe(ch['name'])}.png")
        print(f"▶ 產生 {ch['name']} 的角色設定圖（{SOURCES.get(src, src)}）…", flush=True)
        if src == "upload":
            r = {"ok": False, "error": "選了「自己上傳」：請把照片或設定圖放進 01_人物/，檔名含角色名（例如 01_人物/" + safe(ch["name"]) + "_照片.jpg）"}
        elif src == "codex":
            r = make_codex(req, ch, out)
        elif src == "flow":
            r = make_flow(req, ch, out, account)
        elif src == "fal":
            r = make_fal(req, ch, out)
        else:
            r = {"ok": False, "error": "不認得的來源：" + src}
        if r.get("ok"):
            log_made(ch["name"], {"source": src, "file": os.path.relpath(out, ROOT), "cost": r.get("cost"), "account": r.get("account")}
                     | ({"model": r.get("model"), "request_id": r.get("request_id"), "cost_usd": r.get("cost_usd")} if src == "fal" else {}))
            print(f"  ✅ {os.path.relpath(out, ROOT)}　→ 請打開給使用者看，外觀 OK 再執行 approve", flush=True)
        else:
            print(f"  ❌ {r.get('error') or r.get('reason')}", flush=True)
        if r.get("file"):
            r["file"] = os.path.relpath(r["file"], ROOT)      # 紀錄只寫相對路徑（不留電腦路徑）
        res.append({"name": ch["name"], "source": src} | {k: v for k, v in r.items() if k != "detail"})
    return res


def approve(req, names=None):
    d = load(APPROVE, {}) or {}
    done = []
    for ch in req.get("characters", []):
        if not ch.get("name") or (names and ch["name"] not in names):
            continue
        path, kind = find_sheet(ch)
        if not path:
            print(f"  ⬜ {ch['name']}：還沒有設定圖"); continue
        d[ch["name"]] = {"file": os.path.relpath(path, ROOT), "sha256": sha(path), "kind": kind, "approved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        done.append(ch["name"]); print(f"  ✅ {ch['name']}：已記錄「外觀 OK」（{os.path.relpath(path, ROOT)}）")
    os.makedirs(PEOPLE, exist_ok=True)
    json.dump(d, open(APPROVE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return done


def redo(req, names):
    for ch in req.get("characters", []):
        if ch.get("name") in names:
            path, kind = find_sheet(ch)
            if path and kind == "made":
                b, e = os.path.splitext(path)
                os.replace(path, f"{b}_舊版{time.strftime('%H%M%S')}{e}")
                print(f"  舊圖改名保留：{os.path.basename(b)}_舊版…{e}")
            elif path:
                print(f"  {ch['name']} 用的是學員自備照片（{os.path.relpath(path, ROOT)}），不重做；要換請直接換照片。")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "prompts", "make", "approve", "redo"])
    ap.add_argument("--name", action="append"); ap.add_argument("--source", choices=list(SOURCES)); ap.add_argument("--account")
    ap.add_argument("--yes", action="store_true", help="使用者已看過確認框並回覆「確認」")
    a = ap.parse_args()
    req = load(os.path.join(ROOT, "影片需求.json"))
    if not req:
        print("找不到 影片需求.json"); sys.exit(1)
    if a.cmd == "status":
        print_plan(plan(req)); return
    if a.cmd == "prompts":
        for p in write_prompt_files(req):
            print("  已寫：" + p)
        return
    if a.cmd == "approve":
        approve(req, a.name); return
    if a.cmd in ("make", "redo"):
        if not a.yes:
            print("⛔ 產生角色設定圖前，要先給使用者看確認框（來源、張數、預估點數／費用），使用者回覆「確認」後再加 --yes。")
            print_plan(plan(req)); sys.exit(2)
        if a.cmd == "redo":
            if not a.name:
                print("redo 要指定 --name 角色名"); sys.exit(1)
            redo(req, a.name)
        r = make(req, a.name, a.source, a.account)
        json.dump(r, open(os.path.join(PEOPLE, "角色設定圖_最近一次.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if any(not x.get("ok") and not x.get("skip") for x in r):
            sys.exit(1)


if __name__ == "__main__":
    main()
