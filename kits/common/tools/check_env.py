"""環境檢查：每一項亮綠燈或紅燈，紅燈會寫「怎麼補」。
python tools/check_env.py           檢查這個製作包需要的東西
python tools/check_env.py --all     全部檢查（U01 安裝課用）
"""
import json, os, shutil, socket, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ver(cmd, args=("--version",)):
    p = shutil.which(cmd) or shutil.which(cmd + ".cmd") or shutil.which(cmd + ".exe")
    if not p:
        return None
    try:
        out = subprocess.run([p, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0][:60] or "已安裝"
    except Exception:
        return "已安裝"


def chrome():
    for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"), "/Applications/Google Chrome.app"]:
        if os.path.exists(p):
            return "已安裝"
    return None


def flow_helper():
    s = socket.socket(); s.settimeout(0.5)
    up = s.connect_ex(("127.0.0.1", 8840)) == 0; s.close()
    if not up:
        return None, "（橋接還沒開；出片時 flow_run.py 會自己開，這裡不算錯）"
    try:
        st = json.loads(urllib.request.urlopen("http://127.0.0.1:8840/ext/status", timeout=3).read())
        return ("已連線" if st.get("connected") else None), ""
    except Exception:
        return None, ""


def mod(name):
    try:
        __import__(name); return "已安裝"
    except Exception:
        return None


G, R, Y, N = "[92m", "[91m", "[93m", "[0m"
OK, BAD, OPT = f"{G}● 綠燈{N}", f"{R}● 紅燈{N}", f"{Y}● 黃燈{N}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if os.name == "nt":
        os.system("")   # 讓 Windows 終端機顯示顏色
    req = {}
    p = os.path.join(ROOT, "影片需求.json")
    if os.path.exists(p):
        req = json.load(open(p, encoding="utf-8"))
    route = req.get("route", "auto")
    allc = "--all" in sys.argv
    items = [
        ("Python", sys.version.split()[0], "到 https://www.python.org/downloads/ 下載安裝，安裝時勾「Add python.exe to PATH」"),
        ("ffmpeg", ver("ffmpeg", ("-version",)), "終端機輸入：winget install Gyan.FFmpeg　裝完關掉終端機重開"),
        ("Node.js", ver("node", ("-v",)), "到 https://nodejs.org 下載 LTS 版安裝"),
        ("Chrome", chrome(), "到 https://www.google.com/chrome/ 下載安裝"),
        ("edge-tts（免費旁白）", mod("edge_tts"), "終端機輸入：pip install edge-tts"),
    ]
    if allc or route in ("auto", "A", "B"):
        items.append(("google-genai（B 路＝付費 Gemini API 備援，選配）", mod("google.genai"), "選配：終端機輸入 pip install -U google-genai（只用 Google Flow 可略過）"))
    if allc:
        items += [("Git", ver("git"), "到 https://git-scm.com/download/win 下載安裝"),
                  ("Claude Code", ver("claude"), "選配（AI 引擎三選一）：終端機輸入 npm install -g @anthropic-ai/claude-code（要 Claude 付費方案）"),
                  ("Codex", ver("codex"), "選配（AI 引擎三選一）：終端機輸入 npm install -g @openai/codex，再輸入 codex 選 Sign in with ChatGPT"),
                  ("Antigravity（agy）", ver("agy"), "選配（AI 引擎三選一）：PowerShell 輸入 irm https://antigravity.google/cli/install.ps1 | iex，裝完輸入 agy 用 Google 帳號登入")]
    ok_all = True
    print("=" * 46); print(" 環境檢查"); print("=" * 46)
    for name, v, fix in items:
        optional = "選配" in fix or "略過" in fix
        if v:
            print(f"{OK} {name}：{v}")
        else:
            print(f"{OPT if optional else BAD} {name}：沒有偵測到\n   ➜ 怎麼補：{fix}")
            ok_all = ok_all and optional
    if allc:
        n_ai = sum(1 for k in ("claude", "codex", "agy") if ver(k))
        if n_ai:
            print(f"{OK} AI 引擎：裝了 {n_ai} 個（至少一個就可以上課）")
        else:
            print(f"{BAD} AI 引擎：一個都沒有")
            print("   ➜ 怎麼補：Codex 或 Antigravity 至少裝一個（U01 步驟 5、6）")
            ok_all = False
    if route == "F":     # 2026-11-13 F 路（FAL）：只看有沒有金鑰，不印出、不花錢（能不能用請跑 python tools/flow_ready.py）
        k = ""
        try:
            k = (json.load(open(os.path.join(ROOT, "帳號與金鑰.json"), encoding="utf-8")) or {}).get("falKey", "").strip()
        except Exception:
            pass
        src = "帳號與金鑰.json" if k else ("環境變數 FAL_KEY" if os.environ.get("FAL_KEY", "").strip() else "")
        if src:
            print(f"{OK} FAL 金鑰（F 路）：有（來源：{src}）")
        else:
            print(f"{BAD} FAL 金鑰（F 路）：沒有偵測到\n   ➜ 怎麼補：到 https://fal.ai/dashboard/keys 建立金鑰，貼進生成器 ⑨ 的「FAL 金鑰」重新下載製作包（課程 U10B）")
            ok_all = False
    if allc or route in ("auto", "A"):
        st, note = flow_helper()
        print(f"{OK if st else OPT} Flow 小幫手：{st or '尚未連線'} {note}")
    print("提醒：這裡只檢查「有沒有裝」，AI 有沒有登入要打開它（codex、agy、claude）看看。")
    print("=" * 46)
    print("全部必要項目都到齊了 ✅" if ok_all else "有紅燈，請先照「怎麼補」處理，處理完重新執行這個檢查。")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
