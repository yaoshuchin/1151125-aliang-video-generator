"""出片前檢查（不花點數、不按任何按鈕，只讀）：Flow 自動出片需要的條件一次看清楚。

用法（在製作包資料夾執行）：
  python tools/flow_ready.py

檢查三件事，全部綠燈才開始出片：
  1. Flow 小幫手已連上（Chrome 要開著、擴充功能要裝好並開啟；橋接 8840 沒開這支會自己開）
  2. Chrome 裡有「已登入」的 Google Flow 分頁（列出登入的帳號）
  3. 製作包填的帳號，在 Chrome 裡有沒有對應的 Flow 分頁（沒有只亮黃燈：出片時會自動開登入頁）
不需要開著影片製作包生成器。

出片路線是 F（FAL 付費）時，改檢查 FAL（不花錢）：
  1. 有沒有 FAL 金鑰（帳號與金鑰.json 的 falKey，或環境變數 FAL_KEY；只說有沒有，不印出金鑰）
  2. 金鑰能不能用（用 FAL 免費的價目查詢端點，不生成、不扣錢）
  3. 角色設定圖準備好了沒有（有角色的影片才看）
"""
import json, os, socket, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOW = os.path.join(ROOT, "tools", "cli-anything-flow")
sys.path.insert(0, FLOW)
G, R, Y, N = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
OK, BAD, WARN = f"{G}● 綠燈{N}", f"{R}● 紅燈{N}", f"{Y}● 黃燈{N}"


def port_open(port):
    s = socket.socket(); s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def fal_ready():
    """F 路（FAL）出片前檢查：只讀、不花錢。"""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fal_api
    print("=" * 46); print(" 出片前檢查（F 路：FAL 付費出片）"); print("=" * 46)
    ok_all, sheet_wait = True, False
    key, src = fal_api.get_key(ROOT)
    if key:
        print(f"{OK} 1. 有 FAL 金鑰（來源：{src}）")
        ok, msg = fal_api.verify_key(key)
        if ok:
            print(f"{OK} 2. {msg}")
        else:
            ok_all = False
            print(f"{BAD} 2. 金鑰不能用：{msg}")
    else:
        ok_all = False
        print(f"{BAD} 1. 沒有 FAL 金鑰")
        print("   ➜ 怎麼補：到 https://fal.ai/dashboard/keys 建立金鑰，貼進生成器 ⑨ 生成引擎的「FAL 金鑰」重新下載製作包（課程 U10B）。")
    try:
        req = json.load(open(os.path.join(ROOT, "影片需求.json"), encoding="utf-8"))
        import char_sheet as cs
        rows = [r for r in cs.plan(req) if r["used"]]
        if not rows:
            print(f"{OK} 3. 這支影片沒有角色出場：每鏡文字生影片")
        elif all(r["ready"] for r in rows):
            print(f"{OK} 3. 角色設定圖都確認過了：{'、'.join(r['name'] for r in rows)}")
        else:
            sheet_wait = True
            print(f"{WARN} 3. 角色設定圖還沒好：" + "；".join(f"{r['name']}（{r['state']}）" for r in rows if not r["ready"]))
            print("   ➜ 出片前先跟 AI 說「先做角色設定圖」，看過說外觀 OK 再出片。")
    except Exception as e:
        print(f"{WARN} 3. 讀不到角色資料：{str(e)[:80]}")
    print("   餘額：到 https://fal.ai/dashboard/billing 看（這個檢查不會查、也不會扣錢）。")
    print("=" * 46)
    if not ok_all:
        print("有紅燈：照「怎麼補」處理後，再執行一次 python tools/flow_ready.py")
    elif sheet_wait:
        print("金鑰沒問題 ✅ 下一步：先做角色設定圖（看過說外觀 OK），再出片")
    else:
        print("可以出片了 ✅（出片前 AI 會先列「要花錢，請確認」的框）")
    sys.stdout.flush()
    os._exit(0 if ok_all else 1)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if os.name == "nt":
        os.system("")
    try:
        _r = json.load(open(os.path.join(ROOT, "影片需求.json"), encoding="utf-8"))
        if (_r.get("route") or (_r.get("engine") or {}).get("route")) == "F":
            return fal_ready()
    except Exception:
        pass
    print("=" * 46); print(" 出片前檢查（Google Flow 自動出片）"); print("=" * 46)
    ok_all = True
    # 1. 小幫手
    if not port_open(8840):
        import flow_bridge
        threading.Thread(target=flow_bridge.serve, daemon=True).start()
        time.sleep(1)
    import flowctl, urllib.request
    conn = False
    t0 = time.time()
    while time.time() - t0 < 25:
        try:
            conn = json.loads(urllib.request.urlopen(flowctl.BASE + "/ext/status", timeout=3).read()).get("connected")
        except Exception:
            conn = False
        if conn:
            break
        time.sleep(2)
    if conn:
        print(f"{OK} 1. Flow 小幫手：已連上")
    else:
        ok_all = False
        print(f"{BAD} 1. Flow 小幫手：沒連上")
        print("   ➜ 怎麼補：打開 Chrome；網址列打 chrome://extensions 確認「Flow 小幫手」開關是開的（還沒裝看 U06B）；按小幫手圖示看燈號，再重新執行這個檢查。")
    # 2、3. Flow 分頁與帳號
    accounts = []
    if conn:
        try:
            import cli_anything_flow as caf
            accounts = [t["account"] for t in caf.flow_tabs() if t.get("account")]
        except Exception as e:
            print(f"   （讀分頁時出錯：{str(e)[:80]}）")
    if accounts:
        print(f"{OK} 2. 已登入的 Flow 分頁：{'、'.join(accounts)}")
    else:
        ok_all = False
        print(f"{BAD} 2. 已登入的 Flow 分頁：沒有")
        print("   ➜ 怎麼補：在同一個 Chrome 開新分頁 https://flow.google.com ，用自己的 Google 帳號登入，這個分頁出片時不要關。")
    want = []
    try:
        want = [a.get("email", "").strip() for a in json.load(open(os.path.join(ROOT, "帳號與金鑰.json"), encoding="utf-8")).get("accounts", []) if a.get("email", "").strip()]
    except Exception:
        pass
    if not want:
        print(f"{WARN} 3. 製作包沒有填帳號：會用第 2 項找到的第一個分頁")
    else:
        miss = [w for w in want if w.lower() not in [a.lower() for a in accounts]]
        if accounts and not miss:
            print(f"{OK} 3. 製作包的帳號都有登入的分頁（{len(want)} 個）")
        elif accounts and len(miss) < len(want):
            print(f"{WARN} 3. 有 {len(miss)} 個帳號還沒開分頁：點數用完要換帳號時才會用到，可以先出片")
        else:
            print(f"{WARN} 3. 製作包填的帳號在 Chrome 裡還沒有登入的 Flow 分頁")
            print("   ➜ 出片時程式會自動打開登入頁（可能要你在手機按確認）；想先處理：在 Flow 分頁按右上角頭像 →「切換帳戶」，登入製作包填的那個帳號。")
    print("=" * 46)
    print("三項都可以，開始出片吧 ✅" if ok_all else "有紅燈：照「怎麼補」處理後，再執行一次 python tools/flow_ready.py")
    sys.stdout.flush()
    os._exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
