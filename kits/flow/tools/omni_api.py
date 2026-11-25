"""B 路：Gemini Omni 1.2 Flash（官方 Interactions API）背景生成＋輪詢，不會卡在一個很長的連線上。
只用 Python 內建功能，金鑰從環境變數 GEMINI_API_KEY 讀（flow_run.py 會從 帳號與金鑰.json 帶進來）。

python tools/omni_api.py "提示詞" --duration 5 --resolution 360p --aspect-ratio 16:9 --output 片段/shot_01.mp4
"""
import argparse, base64, json, os, sys, time, urllib.error, urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "gemini-omni-1.2-flash"


def call(method, path, key, body=None, timeout=120):
    req = urllib.request.Request(f"{API}/{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}：{e.read().decode('utf-8', 'replace')[:400]}")


def find_video(obj):
    """在回應裡找影片（base64 data 或 uri）。"""
    if isinstance(obj, dict):
        if obj.get("type") == "video" or str(obj.get("mime_type", "")).startswith("video"):
            if obj.get("data") or obj.get("uri"):
                return obj
        for v in obj.values():
            r = find_video(v)
            if r: return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_video(v)
            if r: return r
    return None


def _img_part(path):
    ext = os.path.splitext(path)[1].lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")
    return {"type": "image", "data": base64.b64encode(open(path, "rb").read()).decode(), "mime_type": mime}


def generate(prompt, key, duration=5, resolution="360p", ratio="16:9", output="out.mp4", max_wait=1800, log=print, images=None):
    """images＝[首幀] 或 [首幀, 尾幀]（2026-11-15，官方 first and last frames：文字＋兩張圖放同一則 user_input）。"""
    inp = prompt
    if images:
        txt = ("Use the first image as the first frame and the second image as the last frame of the video. " if len(images) > 1
               else "Use the image as the first frame of the video. ") + prompt
        inp = [{"type": "user_input", "content": [{"type": "text", "text": txt}] + [_img_part(x) for x in images]}]
    body = {"model": MODEL, "input": inp, "background": True,
            "response_format": {"type": "video", "duration": f"{int(duration)}s", "resolution": resolution, "aspect_ratio": ratio, "delivery": "uri"}}
    t0 = time.time()
    it = call("POST", "interactions", key, body)
    iid = it.get("id"); log(f"已送出（編號 {iid}），狀態：{it.get('status')}")
    while it.get("status") not in ("completed", "failed", "cancelled", "incomplete") and time.time() - t0 < max_wait:
        time.sleep(15)
        it = call("GET", f"interactions/{iid}", key)
        log(f"  {int(time.time() - t0)} 秒：{it.get('status')}")
    if it.get("status") != "completed":
        raise RuntimeError(f"生成沒有完成（{it.get('status')}）：{json.dumps(it, ensure_ascii=False)[:500]}")
    v = find_video(it)
    if not v:
        raise RuntimeError("回應裡找不到影片：" + json.dumps(it, ensure_ascii=False)[:500])
    os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)
    if v.get("data"):
        open(output, "wb").write(base64.b64decode(v["data"]))
    else:
        uri = v["uri"]
        req = urllib.request.Request(uri + ("&" if "?" in uri else "?") + "alt=media", headers={"x-goog-api-key": key})
        open(output, "wb").write(urllib.request.urlopen(req, timeout=300).read())
    return {"ok": True, "route": "B", "file": os.path.abspath(output), "interaction_id": iid, "seconds_used": int(time.time() - t0),
            "bytes": os.path.getsize(output)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt"); ap.add_argument("--duration", type=int, default=5); ap.add_argument("--resolution", default="360p")
    ap.add_argument("--aspect-ratio", default="16:9"); ap.add_argument("--output", default="out.mp4"); ap.add_argument("--max-wait", type=int, default=1800)
    a = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print(json.dumps({"ok": False, "error": "沒有 GEMINI_API_KEY"}, ensure_ascii=False)); sys.exit(1)
    try:
        r = generate(a.prompt, key, a.duration, a.resolution, a.aspect_ratio, a.output, a.max_wait, log=lambda m: print(m, file=sys.stderr, flush=True))
        print(json.dumps(r, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); sys.exit(1)


if __name__ == "__main__":
    main()
