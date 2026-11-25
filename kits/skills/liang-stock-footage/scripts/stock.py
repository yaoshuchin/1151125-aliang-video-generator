#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
liang-stock-footage — 免費影片素材庫 CLI（Pixabay + Pexels）
只用 Python 標準庫（urllib），不需 pip 安裝。

用法：
  搜尋：  python stock.py search "關鍵字" [--n 8] [--source both|pexels|pixabay] [--orient landscape|portrait|any]
  下載：  python stock.py download <RESULT_ID> [<RESULT_ID> ...] [--out 資料夾]
          RESULT_ID 形如 pexels:12345 或 pixabay:98765（search 結果會標好）

環境變數：
  PEXELS_KEY   — Pexels API 金鑰
  PIXABAY_KEY  — Pixabay API 金鑰
（缺哪個就自動跳過那個來源，並提示。）
"""
import os, sys, json, argparse, urllib.parse, urllib.request

TIMEOUT = 30
# 有些 API（如 Pexels）會擋預設的 Python-urllib UA 回 403，帶一個正常 UA
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) liang-stock-footage/1.0"

def _get(url, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))

# ---------------- Pexels ----------------
def search_pexels(query, n, orient):
    key = os.environ.get("PEXELS_KEY")
    if not key:
        print("  [略過 Pexels] 未設定 PEXELS_KEY", file=sys.stderr)
        return []
    params = {"query": query, "per_page": n}
    if orient in ("landscape", "portrait"):
        params["orientation"] = orient
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(params)
    try:
        data = _get(url, headers={"Authorization": key})
    except Exception as e:
        print(f"  [Pexels 錯誤] {e}", file=sys.stderr)
        return []
    out = []
    for v in data.get("videos", []):
        files = sorted(v.get("video_files", []),
                       key=lambda f: (f.get("width") or 0), reverse=True)
        best = files[0] if files else {}
        out.append({
            "rid": f"pexels:{v['id']}",
            "source": "Pexels",
            "duration": v.get("duration"),
            "w": best.get("width"), "h": best.get("height"),
            "preview": v.get("url"),
            "download": best.get("link"),
            "thumb": v.get("image"),
            "author": (v.get("user") or {}).get("name", ""),
        })
    return out

# ---------------- Pixabay ----------------
def search_pixabay(query, n, orient):
    key = os.environ.get("PIXABAY_KEY")
    if not key:
        print("  [略過 Pixabay] 未設定 PIXABAY_KEY", file=sys.stderr)
        return []
    params = {"key": key, "q": query, "per_page": max(3, n), "safesearch": "true"}
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(params)
    try:
        data = _get(url)
    except Exception as e:
        print(f"  [Pixabay 錯誤] {e}", file=sys.stderr)
        return []
    out = []
    for v in data.get("hits", [])[:n]:
        vids = v.get("videos", {})
        best = vids.get("large") or vids.get("medium") or vids.get("small") or {}
        # Pixabay orientation 需自行用寬高判斷
        w, h = best.get("width"), best.get("height")
        if orient == "landscape" and w and h and w < h:
            continue
        if orient == "portrait" and w and h and w > h:
            continue
        out.append({
            "rid": f"pixabay:{v['id']}",
            "source": "Pixabay",
            "duration": v.get("duration"),
            "w": w, "h": h,
            "preview": v.get("pageURL"),
            "download": best.get("url"),
            "thumb": best.get("thumbnail") or v.get("userImageURL"),
            "author": v.get("user", ""),
        })
    return out

def cmd_search(args):
    results = []
    if args.source in ("both", "pexels"):
        results += search_pexels(args.query, args.n, args.orient)
    if args.source in ("both", "pixabay"):
        results += search_pixabay(args.query, args.n, args.orient)
    if not results:
        print("\n找不到結果（或兩個來源的 API Key 都沒設）。")
        return
    print(f"\n關鍵字「{args.query}」找到 {len(results)} 筆免費可商用素材：\n")
    print(f"{'ID':<16}{'來源':<9}{'秒數':<6}{'解析度':<12}{'作者'}")
    print("-" * 70)
    for r in results:
        res = f"{r['w']}x{r['h']}" if r['w'] else "?"
        print(f"{r['rid']:<16}{r['source']:<9}{str(r['duration'] or '?'):<6}{res:<12}{r['author'][:18]}")
    print("\n預覽頁：")
    for r in results:
        print(f"  {r['rid']:<16} {r['preview']}")
    print(f"\n下載指令範例：python stock.py download {results[0]['rid']} --out ./素材")
    # 存一份 json 供程式化取用
    with open("_stock_last_search.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def _find_download_url(rid):
    """先看上次搜尋快取，找不到就即時重查該來源。"""
    if os.path.exists("_stock_last_search.json"):
        cache = json.load(open("_stock_last_search.json", encoding="utf-8"))
        for r in cache:
            if r["rid"] == rid:
                return r["download"]
    return None

def cmd_download(args):
    os.makedirs(args.out, exist_ok=True)
    for rid in args.rids:
        url = _find_download_url(rid)
        if not url:
            print(f"  [{rid}] 快取中找不到下載網址，請先重新 search 一次。", file=sys.stderr)
            continue
        safe = rid.replace(":", "_")
        path = os.path.join(args.out, f"{safe}.mp4")
        print(f"  下載 {rid} → {path} ...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(path, "wb") as out:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
            print(f"    ✅ 完成（{os.path.getsize(path)//1024} KB）")
        except Exception as e:
            print(f"    ❌ 失敗：{e}", file=sys.stderr)

def cmd_thumbs(args):
    """搜尋並下載每個候選的預覽縮圖，供人工/AI 挑片。"""
    results = []
    if args.source in ("both", "pexels"):
        results += search_pexels(args.query, args.n, args.orient)
    if args.source in ("both", "pixabay"):
        results += search_pixabay(args.query, args.n, args.orient)
    if not results:
        print("找不到結果。")
        return
    os.makedirs(args.out, exist_ok=True)
    manifest = []
    for r in results:
        if not r.get("thumb"):
            continue
        safe = r["rid"].replace(":", "_")
        path = os.path.join(args.out, f"{safe}.jpg")
        try:
            req = urllib.request.Request(r["thumb"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(path, "wb") as f:
                f.write(resp.read())
            manifest.append(r)
            print(f"  {r['rid']:<16} {r['w']}x{r['h']} {r['duration']}s -> {path}")
        except Exception as e:
            print(f"  [{r['rid']}] 縮圖失敗 {e}", file=sys.stderr)
    # 同時把完整清單存起來，之後 download 可直接引用
    with open("_stock_last_search.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

def main():
    p = argparse.ArgumentParser(description="免費影片素材庫 CLI（Pixabay + Pexels）")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("search", help="搜尋免費影片素材")
    ps.add_argument("query")
    ps.add_argument("--n", type=int, default=8)
    ps.add_argument("--source", choices=["both", "pexels", "pixabay"], default="both")
    ps.add_argument("--orient", choices=["landscape", "portrait", "any"], default="any")
    ps.set_defaults(func=cmd_search)

    pd = sub.add_parser("download", help="下載指定素材")
    pd.add_argument("rids", nargs="+")
    pd.add_argument("--out", default="./素材")
    pd.set_defaults(func=cmd_download)

    pt = sub.add_parser("thumbs", help="下載候選預覽縮圖供挑片")
    pt.add_argument("query")
    pt.add_argument("--n", type=int, default=6)
    pt.add_argument("--source", choices=["both", "pexels", "pixabay"], default="both")
    pt.add_argument("--orient", choices=["landscape", "portrait", "any"], default="any")
    pt.add_argument("--out", default="./_thumbs")
    pt.set_defaults(func=cmd_thumbs)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
