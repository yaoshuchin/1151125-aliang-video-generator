"""F 路：FAL（fal.ai）付費出片，按秒計費。只用 Python 內建功能（urllib），走 FAL 的佇列 API（送出 → 查進度 → 取結果）。

金鑰順序：帳號與金鑰.json 的 falKey → 環境變數 FAL_KEY。金鑰絕對不印出來、不寫進任何檔案或紀錄。

模型（2026-11-13 依 FAL 價目查詢端點確認的單價；實際以 https://fal.ai/pricing 與你的帳單為準）：
  kling  Kling 2.5 Turbo Pro（品質優先）  每秒 US$0.07，一鏡 5 秒或 10 秒
  wan    Wan 2.5（省錢，480p）            每秒 US$0.05，一鏡 5 秒或 10 秒
有角色的鏡頭＝「圖生影片」：先用 FLUX Kontext 把角色設定圖變成這一鏡的第一張畫面（首幀，每張 US$0.04），
再把首幀交給 Kling／Wan 動起來；沒有角色的鏡頭＝文字生影片。

用法（多半由 flow_run.py 呼叫；也可以單獨用）：
  python tools/fal_api.py check                 只檢查金鑰能不能用（免費的價目查詢，不花錢）
  python tools/fal_api.py price                 列出目前模型單價（免費查詢）
"""
import base64, json, mimetypes, os, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = "https://queue.fal.run"
API = "https://api.fal.ai/v1"

MODELS = {
    "kling": {"name": "Kling 2.5 Turbo Pro（品質優先）", "i2v": "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
              "t2v": "fal-ai/kling-video/v2.5-turbo/pro/text-to-video", "usd_per_sec": 0.07, "extra": {}},
    "wan": {"name": "Wan 2.5（省錢，480p）", "i2v": "fal-ai/wan-25-preview/image-to-video",
            "t2v": "fal-ai/wan-25-preview/text-to-video", "usd_per_sec": 0.05,
            "extra": {"resolution": "480p", "enable_prompt_expansion": False}},
}
FRAME = {"name": "FLUX Kontext（角色設定圖 → 這一鏡的首幀）", "endpoint": "fal-ai/flux-pro/kontext", "usd": 0.04}
FLUX = {"name": "FLUX.1 dev（角色設定圖）", "endpoint": "fal-ai/flux/dev", "usd": 0.025}
NEG = "blur, distort, low quality, text, subtitles, watermark, logo, extra fingers, deformed face"


class FalError(RuntimeError):
    pass


# ---------- 金鑰 ----------
def get_key(root=ROOT):
    """回傳 (金鑰, 來源說明)。來源只會是「帳號與金鑰.json」或「環境變數 FAL_KEY」，不回傳金鑰內容給畫面。"""
    try:
        k = (json.load(open(os.path.join(root, "帳號與金鑰.json"), encoding="utf-8")) or {}).get("falKey", "").strip()
        if k:
            return k, "帳號與金鑰.json 的 falKey"
    except Exception:
        pass
    k = os.environ.get("FAL_KEY", "").strip()
    return (k, "環境變數 FAL_KEY") if k else ("", "")


def _clean(msg, key):
    msg = str(msg)
    if key:
        msg = msg.replace(key, "***")
        for part in key.split(":"):
            if len(part) >= 8:
                msg = msg.replace(part, "***")
    return msg


def explain(code, body):
    """把 FAL 的錯誤翻成白話（附原文）。"""
    low = (body or "").lower()
    if code == 401 or "invalid key" in low or "unauthorized" in low or "authentication" in low:
        return "金鑰錯了或已被刪除（401）：到 https://fal.ai/dashboard/keys 重新建立金鑰，填進 帳號與金鑰.json 的 falKey。"
    if code == 402 or "balance" in low or "exhausted" in low or "insufficient" in low or "locked" in low:
        return "FAL 餘額不足（帳戶被暫停扣款）：到 https://fal.ai/dashboard/billing 儲值後再請 AI 重做這一鏡。"
    if code == 403:
        return "這把金鑰沒有權限做這件事（403）：建立金鑰時權限選 API。"
    if code == 422 and ("content" in low or "policy" in low or "nsfw" in low or "safety" in low):
        return "內容被 FAL 的安全檢查拒絕（422）：改寫提示詞（避開暴力、未成年特寫、真實名人），確認後再送。"
    if code == 422:
        return "參數或圖片不被接受（422）：看下面原文。"
    if code == 429:
        return "送太快被限制（429）：等一分鐘再試。"
    return f"FAL 回應錯誤（HTTP {code}）"


def _req(method, url, key, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    rq = urllib.request.Request(url, data=data, method=method,
                                headers={"Authorization": "Key " + key, "Content-Type": "application/json", "User-Agent": "video-kit/1.0"})
    try:
        return json.loads(urllib.request.urlopen(rq, timeout=timeout).read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:600]
        raise FalError(_clean(f"{explain(e.code, raw)}｜原文：HTTP {e.code} {raw}", key))
    except urllib.error.URLError as e:
        raise FalError(f"連不上 FAL（網路問題）：{e.reason}")


def verify_key(key):
    """免費檢查：用價目查詢端點（不生成、不花錢）。回傳 (ok, 白話說明)。"""
    if not key:
        return False, "沒有 FAL 金鑰"
    try:
        _req("GET", f"{API}/models/pricing?endpoint_id=" + urllib.parse.quote(FLUX["endpoint"], safe="/"), key, timeout=30)
        return True, "金鑰可以用（免費查詢通過，沒有花錢）"
    except FalError as e:
        return False, str(e)


def live_prices(key, endpoints):
    """免費查詢目前單價；查不到（沒網路、被限速）回傳空 dict，呼叫端改用內建單價。"""
    out = {}
    for ep in endpoints:
        try:
            j = _req("GET", f"{API}/models/pricing?endpoint_id=" + urllib.parse.quote(ep, safe="/"), key, timeout=20)
            for p in j.get("prices", []):
                out[p["endpoint_id"]] = (float(p["unit_price"]), p.get("unit"))
        except Exception:
            pass
    return out


# ---------- 費用 ----------
def billed_seconds(sec):
    """Kling／Wan 一鏡只能 5 或 10 秒：7 秒以下算 5 秒，超過算 10 秒。"""
    return 5 if int(sec or 5) <= 7 else 10


def estimate(model, sec, with_frame):
    m = MODELS[model]
    b = billed_seconds(sec)
    return b, round(b * m["usd_per_sec"] + (FRAME["usd"] if with_frame else 0), 3)


# ---------- 佇列 ----------
def _data_uri(path):
    mt = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mt};base64," + base64.b64encode(open(path, "rb").read()).decode()


def run_queue(endpoint, payload, key, log=print, max_wait=1200):
    """送進 FAL 佇列 → 每 10 秒查一次 → 取結果。回傳 (結果 dict, request_id)。失敗丟 FalError（不自動重試）。"""
    sub = _req("POST", f"{QUEUE}/{endpoint}", key, payload)
    rid = sub.get("request_id")
    status_url = sub.get("status_url") or f"{QUEUE}/{endpoint}/requests/{rid}/status"
    resp_url = sub.get("response_url") or f"{QUEUE}/{endpoint}/requests/{rid}"
    log(f"已送出（編號 {rid}）")
    t0, last = time.time(), ""
    while time.time() - t0 < max_wait:
        time.sleep(10)
        st = _req("GET", status_url, key, timeout=60)
        s = st.get("status", "")
        if s != last or s == "IN_QUEUE":
            pos = st.get("queue_position")
            log(f"  {int(time.time() - t0)} 秒：{ {'IN_QUEUE': '排隊中', 'IN_PROGRESS': '生成中', 'COMPLETED': '完成'}.get(s, s) }"
                + (f"（前面還有 {pos} 個）" if pos else ""))
            last = s
        if s == "COMPLETED":
            if st.get("error"):
                raise FalError(_clean(f"生成失敗：{st.get('error')}", key))
            return _req("GET", resp_url, key, timeout=120), rid
    raise FalError(f"等了 {max_wait} 秒還沒完成（編號 {rid}），可以稍後到 https://fal.ai/dashboard/requests 查看")


def _download(url, out):
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    rq = urllib.request.Request(url, headers={"User-Agent": "video-kit/1.0"})
    tmp = out + ".download"
    open(tmp, "wb").write(urllib.request.urlopen(rq, timeout=300).read())
    os.replace(tmp, out)
    return out


# ---------- 生圖：角色設定圖 ----------
def flux_image(prompt, out, key, width=1280, height=720, log=print):
    j, rid = run_queue(FLUX["endpoint"], {"prompt": prompt, "image_size": {"width": width, "height": height}, "num_images": 1,
                                          "enable_safety_checker": True, "output_format": "png"}, key, log)
    url = j["images"][0]["url"]
    tmp = out + ".img"
    _download(url, tmp)
    try:
        from PIL import Image
        Image.open(tmp).convert("RGB").save(out, "PNG"); os.remove(tmp)
    except Exception:
        os.replace(tmp, out)
    return {"ok": True, "file": out, "model": FLUX["endpoint"], "request_id": rid, "cost_usd": FLUX["usd"]}


# ---------- 出片：一鏡 ----------
def frame_prompt(scene, ratio):
    return ("Use the character from this reference sheet (keep the exact same face, hairstyle, skin tone, outfit and colors). "
            f"Create ONE single cinematic {ratio} video frame, not a character sheet, only one view of the character, in this scene: {scene} "
            "Natural lighting, realistic proportions. No text, no labels, no watermark, no logo.")


def generate_shot(prompt, out, sec, ratio, key, model="kling", ref_image=None, scene=None, frame_out=None, log=print):
    """產生一鏡。ref_image 有值＝圖生影片（先做首幀再動起來）；沒有＝文字生影片。失敗丟 FalError，不自動重試。"""
    m = MODELS[model]
    b = billed_seconds(sec)
    rec = {"route": "F", "model": model, "model_name": m["name"], "billed_seconds": b}
    t0 = time.time()
    if ref_image:
        log(f"  ① 首幀：{FRAME['name']}（約 US${FRAME['usd']:.2f}）")
        fj, frid = run_queue(FRAME["endpoint"], {"prompt": frame_prompt(scene or prompt, ratio), "image_url": _data_uri(ref_image),
                                                 "aspect_ratio": ratio, "output_format": "png", "safety_tolerance": "2"}, key, log)
        furl = fj["images"][0]["url"]
        if frame_out:
            _download(furl, frame_out); rec["frame_file"] = frame_out
        rec.update({"frame_model": FRAME["endpoint"], "frame_request_id": frid})
        log(f"  ② 影片：{m['name']}，{b} 秒（約 US${b * m['usd_per_sec']:.2f}）")
        payload = {"prompt": prompt, "image_url": furl, "duration": str(b), "negative_prompt": NEG} | m["extra"]
        ep = m["i2v"]
    else:
        log(f"  文字生影片：{m['name']}，{b} 秒（約 US${b * m['usd_per_sec']:.2f}）")
        payload = {"prompt": prompt, "duration": str(b), "aspect_ratio": ratio, "negative_prompt": NEG} | m["extra"]
        ep = m["t2v"]
    vj, rid = run_queue(ep, payload, key, log)
    url = (vj.get("video") or {}).get("url")
    if not url:
        raise FalError("FAL 回應裡沒有影片網址：" + json.dumps(vj, ensure_ascii=False)[:300])
    _download(url, out)
    rec.update({"ok": True, "file": out, "endpoint": ep, "request_id": rid,
                "cost_usd": estimate(model, sec, bool(ref_image))[1], "cost_note": "依 FAL 公開單價計算；實扣以 fal.ai 帳單（Usage）為準",
                "seconds_used": int(time.time() - t0)})
    return rec


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    key, src = get_key()
    if not key:
        print("沒有 FAL 金鑰：在生成器 ⑨ 生成引擎貼上（會寫進 帳號與金鑰.json 的 falKey），或設定環境變數 FAL_KEY。"); sys.exit(1)
    if cmd == "check":
        ok, msg = verify_key(key)
        print(f"FAL 金鑰（來源：{src}）：{msg}"); sys.exit(0 if ok else 1)
    if cmd == "price":
        eps = [m[k] for m in MODELS.values() for k in ("i2v", "t2v")] + [FRAME["endpoint"], FLUX["endpoint"]]
        lp = live_prices(key, eps)
        for ep in eps:
            p = lp.get(ep)
            print(f"{ep}：" + (f"US${p[0]} / {p[1]}" if p else "（查不到，用內建單價）"))


if __name__ == "__main__":
    main()
