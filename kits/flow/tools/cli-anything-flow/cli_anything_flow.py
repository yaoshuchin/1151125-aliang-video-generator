"""cli-anything-flow：讓 AI（Claude Code／Codex／Antigravity）透過「Flow 小幫手」在你平常的 Chrome 用 Google Flow 生成影片。

前提：
  1. Chrome 已安裝並啟用「Flow 小幫手」擴充功能。
  2. 生成器（或 flow_bridge.py）已啟動，本機 127.0.0.1:8840 在跑。
  3. Chrome 裡已開好 Google Flow 分頁，並登入要用的帳號（每個帳號一個分頁）。

指令（輸出一律 JSON，給 AI 讀）：
  python cli_anything_flow.py status
  python cli_anything_flow.py credits  [--account 信箱]
  python cli_anything_flow.py gen --prompt "…" --out 檔名.mp4 [--account 信箱] [--seconds 5] [--res 360p] [--ratio 16:9]
                                  [--model "Omni 1.2 Flash"] [--max-cost 30] [--project 專案網址]
       [--ref 角色設定圖.png ...] [--ref-media 媒體編號] [--ref-cache 快取.json]
       （加 --ref：先把圖片當「素材」附進提示詞，讓人物外觀照參考圖；不加就是原本的純文字生成）
       [--first 首幀.png [--last 尾幀.png]]
       （2026-11-15 首尾幀：上傳首幀、尾幀附進提示詞，請 Omni 用「畫面轉影片（Frames to Video）：首幀和尾幀」生成，
        影片從首幀開始、停在尾幀；只給 --first 就是「只有首幀」）
  python cli_anything_flow.py gen-image --prompt "…" --out 圖.png [--account 信箱] [--ratio 16:9] [--image-model "Nano Banana 2.1"] [--max-cost 0]
       [--ref 參考圖.png ...] [--ref-cache 快取.json]（2026-11-15：附參考圖生圖，例如尾幀附首幀＋角色設定圖，讓構圖和人物一致）
       （用 Flow 代理生成 1 張圖並下載；送出前代理回報的點數超過 --max-cost 就按「拒絕」）
  python cli_anything_flow.py ref-check [--account 信箱] [--project 專案網址]
       （不花點數：打開「在提示詞輸入框新增素材」面板，檢查上傳／圖像／新增至提示詞等按鈕還在，再關掉）
  python cli_anything_flow.py gen-rotate --accounts 帳號一@gmail.com,帳號二@gmail.com --prompt … --out …
       （依序試帳號，點數不夠就換下一個；全部不夠回傳 need_api，交給 B 路）
  python cli_anything_flow.py login --account 信箱 [--password 密碼]
       （AI 自己開登入頁、填帳號密碼；Google 要求手機驗證或擋自動登入時，回傳 need_human，請學員在跳出的分頁按一下）

2026-11-21 Flow 新功能（gen／gen-image 每次都會先做「花錢安全門」：代理設定『生成前需確認』一定是「一律」，否則不生成）：
  python cli_anything_flow.py safety                       檢查（必要時改回）生成前需確認＝一律
  python cli_anything_flow.py memory --title 標題 --text 內容   代理記憶（專案規則寫一次，0 點）
  python cli_anything_flow.py character --name 女主角 --image 定妝.png [--voice Autonoe --voice-style "臺灣口音…" --info "外型個性"]
       （建立 Flow 角色：臉＋服裝＋聲音綁在一起，0 點；已存在回傳 exists）
  gen 另可加：
       --character 女主角            附上 Flow 角色（取代每鏡上傳定妝照；首尾幀模式也可加，聲音一致）
       --voice Autonoe               附上語音（只對素材類生成有效）
       --extend title:卡片標題 | 媒體編號   把專案裡那支影片往後延伸 --seconds 秒（可加 --ref 最多 3 張、--character；實測 5 秒＝15 點）
       --edit   title:卡片標題 | 媒體編號   用代理修改既有影片（不整鏡重生；費用同生成）
       （影片卡標題會記在回傳的 "title"；Flow 縮圖代碼重新載入會變，之後要延伸／修改請用 title:）
"""
import argparse, json, os, re, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flowctl as fc

MODEL_DEFAULT = "Omni 1.2 Flash"
IMAGE_MODEL_DEFAULT = "Nano Banana 2.1"   # 2026-11-13 Flow 代理設定的圖像預設模型（另有 Nano Banana Pro、Nano Banana 2 Lite）


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=1))
    sys.exit(code)


# ---------- 分頁與帳號 ----------
def flow_tabs(auto_open=True):
    tabs = fc.call("tabs", timeout=20)
    if not tabs and auto_open:      # 2026-11-15：Chrome 沒開 Flow 分頁 → AI 自己在背景開一個（不搶前景），等它載入
        try:
            fc.call("open", {"url": "https://flow.google.com/", "active": False}, timeout=30)
        except Exception:
            pass
        t0 = time.time()
        while time.time() - t0 < 40:
            time.sleep(3)
            tabs = fc.call("tabs", timeout=20)
            if tabs and all("@" in (fc.js(t["id"], "([...document.querySelectorAll('[aria-label]')].map(e=>e.getAttribute('aria-label')).find(s=>s.includes('@'))||'')", 20) or "") for t in tabs):
                break
    res = []
    for t in tabs:
        try:
            lab = fc.js(t["id"], "([...document.querySelectorAll('[aria-label]')].map(e=>e.getAttribute('aria-label')).find(s=>s.includes('@'))||'')", 20)
        except Exception:
            lab = ""
        m = re.search(r"\(([^()\s]+@[^()\s]+)\)", lab or "")
        t["account"] = m.group(1) if m else None
        t["paid"] = "會員方案" in (lab or "")
        res.append(t)
    if res and auto_open and not any(t["account"] for t in res):
        # 2026-11-15 實測：分頁被別的除錯工具佔住（Another debugger is already attached）或停在登入頁 → 背景另開一個新分頁再試一次
        try:
            fc.call("open", {"url": "https://flow.google.com/", "active": False}, timeout=30)
            time.sleep(15)
        except Exception:
            pass
        return flow_tabs(auto_open=False)
    return res


def tab_for(account=None):
    tabs = [t for t in flow_tabs() if t["account"]]
    if not tabs:
        raise RuntimeError("找不到已登入的 Google Flow 分頁。請在 Chrome 打開 https://flow.google.com 並登入。")
    if account:
        for t in tabs:
            if t["account"].lower() == account.lower():
                return t
        raise RuntimeError(f"Chrome 裡沒有登入 {account} 的 Flow 分頁。先執行 login，或在 Chrome 切換帳戶開一個分頁。")
    return tabs[0]


# ---------- 畫面小工具 ----------
def items(tab):
    return fc.dump(tab)["items"]


def find(tab, label=None, text=None, endswith=None, wait=0):
    t0 = time.time()
    while True:
        for i in items(tab):
            if label and i["label"] == label: return i
            if text and text in i["text"]: return i
            if endswith and i["text"].strip().endswith(endswith): return i
        if time.time() - t0 >= wait:
            return None
        time.sleep(1)


def click_item(tab, it):
    fc.click(tab, it["x"], it["y"])


def to_project(tab):
    """如果停在某支影片的編輯畫面（網址 /project/<id>/…），回到專案主畫面。"""
    url = fc.js(tab, "location.href") or ""
    m = re.match(r"(.*?/project/[0-9a-f-]{36})", url)
    if m and url.rstrip("/") != m.group(1):
        fc.call("navigate", {"tabId": tab, "url": m.group(1)}); time.sleep(6)
        return True
    return False


def credits(tab):
    """打開帳戶面板讀「N 點 Google Flow 點數」，再關掉。"""
    to_project(tab)
    av = find(tab, label="帳戶詳細資料", wait=10)
    if not av:
        return None
    click_item(tab, av); time.sleep(1.5)
    n = None
    for i in items(tab):
        m = re.search(r"([\d,]+)\s*點\s*Google Flow", i["text"])
        if m: n = int(m.group(1).replace(",", "")); break
    close = find(tab, label="選擇帳戶面板")
    if close: click_item(tab, close); time.sleep(0.8)
    return n


def media_ids(tab):
    """專案裡媒體卡縮圖的代號。2026-11-13 中午起 Flow 縮圖改成 https://flow.google.com/asb/<代碼>（舊的是 flow-content.google/image/<編號>），兩種都收。
    排除使用者自己上傳的圖（alt＝顯示使用者圖像的圖塊），避免把上傳的參考圖當成新生成的作品。"""
    return fc.js(tab, """[...new Set([...document.querySelectorAll('img')].filter(i=>i.alt!=='顯示使用者圖像的圖塊').map(i=>i.src).map(s=>
        s.includes('flow-content.google/image/')?s.split('/image/')[1].split('?')[0]:
        (s.includes('flow.google.com/asb/')?s.split('/asb/')[1].split('?')[0].slice(0,80):null)).filter(Boolean))]""") or []


def _tile_download_pos(tab, key):
    """找到縮圖網址含 key 的那張媒體卡，回傳它那一列「下載」按鈕的位置。"""
    return fc.js(tab, f"""(()=>{{const i=[...document.querySelectorAll('img')].find(x=>x.src.includes({json.dumps(key)}));if(!i)return null;
      let e=i;for(let k=0;k<12&&e;k++){{e=e.parentElement;const b=e&&e.querySelector('button[aria-label="下載"]');
        if(b){{b.scrollIntoView({{block:'center'}});const r=b.getBoundingClientRect();return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)];}}}}
      return null}})()""")


def page_fetch(tab, url, timeout=180):
    """用 Flow 分頁自己的登入狀態下載（/asb/ 圖片要登入 cookie），回傳 bytes。"""
    import base64
    b64 = fc.js(tab, f"""(async()=>{{const r=await fetch({json.dumps(url)},{{credentials:'include'}});if(!r.ok)return 'ERR'+r.status;
      const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return btoa(s)}})()""", timeout)
    if not b64 or str(b64).startswith("ERR"):
        raise RuntimeError(f"下載失敗：{b64}")
    return base64.b64decode(b64)


def ensure_project(tab, project=None):
    url = fc.js(tab, "location.href")
    if project:
        if project not in url:
            fc.call("navigate", {"tabId": tab, "url": project}); time.sleep(6)
        return fc.js(tab, "location.href")
    if "/project/" in url:
        return url
    home = find(tab, text="新增專案", wait=15)
    if not home:
        raise RuntimeError("找不到「新增專案」按鈕")
    # 2026-11-13：首頁也有代理輸入框，一定要等網址進到 /project/ 才能打字（否則提示詞會打在首頁）
    for attempt in range(3):
        if attempt == 0:
            click_item(tab, home)
        else:
            fc.js(tab, "(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.innerText.includes('新增專案'));if(b)b.click()})()")
        t0 = time.time()
        while time.time() - t0 < 15 and "/project/" not in (fc.js(tab, "location.href") or ""):
            time.sleep(1)
        if "/project/" in (fc.js(tab, "location.href") or ""):
            break
    if "/project/" not in (fc.js(tab, "location.href") or ""):
        raise RuntimeError("按了「新增專案」但沒有進到專案頁")
    time.sleep(4)
    ok = find(tab, text="開始使用", wait=3)        # 第一次進專案會跳公告
    if ok: click_item(tab, ok); time.sleep(1.5)
    return fc.js(tab, "location.href")


def bring_front(tab):
    """把目標 Flow 分頁切到它所在 Chrome 視窗的最前面（分頁被別的分頁蓋住時，畫面不更新、座標點擊會失準）。
    只切分頁；若 Windows 前景視窗因此改變，馬上還給原本的視窗（不搶老師的焦點）。"""
    try:
        if fc.js(tab, "document.visibilityState") == "visible":
            return True
        fg = None
        try:
            import ctypes
            u = ctypes.windll.user32; fg = u.GetForegroundWindow()
        except Exception:
            u = None
        fc.cdp(tab, "Page.bringToFront"); time.sleep(1.5)
        if u and fg and u.GetForegroundWindow() != fg:
            u.SetForegroundWindow(fg)
        return fc.js(tab, "document.visibilityState") == "visible"
    except Exception:
        return False


PROMPT_SEL = "document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]')"


def prompt_text(tab):
    return (fc.js(tab, f"(({PROMPT_SEL})||{{}}).innerText||''") or "").strip()


def clear_prompt(tab):
    """清掉提示詞框殘留的文字和已附上的素材（上次沒送出的）。"""
    for _ in range(8):        # 素材小圖右上角的 ✕（aria-label＝素材、文字 cancel）；2026-11-21 角色／語音小圖文字是「cancel accessibility_new」→ 點裡面的 cancel 圖示
        if not fc.js(tab, """(()=>{const b=[...document.querySelectorAll('.base-prompt-box button')].find(b=>b.innerText.trim()==='cancel'||(b.getAttribute('aria-label')==='素材'&&/^cancel/.test(b.innerText.trim())));
            if(!b)return false;const i=[...b.querySelectorAll('mat-icon,span,i')].find(x=>x.innerText.trim()==='cancel');(i||b).click();return true})()"""):
            break
        time.sleep(0.6)
    if not prompt_text(tab):
        return True
    fc.js(tab, "(()=>{const b=document.querySelector('button[aria-label=\"清除提示詞\"]');if(b)b.click()})()"); time.sleep(1)
    if prompt_text(tab):
        fc.js(tab, f"(()=>{{const e={PROMPT_SEL};e.focus();document.execCommand('selectAll');document.execCommand('delete');}})()"); time.sleep(0.8)
    return not prompt_text(tab)


def send_prompt(tab):
    """按「開始生成」並確認真的送出（輸入框清空）。先用網頁 click()，沒送出再用分頁內滑鼠事件、最後按 Enter。"""
    sel = "document.querySelector('button[aria-label=\"開始生成\"]')"
    t0 = time.time()
    while fc.js(tab, f"(()=>{{const b={sel};return !b||b.disabled||b.getAttribute('aria-disabled')==='true'}})()"):
        if time.time() - t0 > 10:
            raise RuntimeError("「開始生成」按鈕一直不能按")
        time.sleep(0.5)
    for how in ("js", "mouse", "enter"):
        if how == "js":
            fc.js(tab, f"{sel}.click()")
        elif how == "mouse":
            pos = fc.js(tab, f"(()=>{{const r={sel}.getBoundingClientRect();return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)]}})()")
            if pos and 0 <= pos[0] < (fc.js(tab, "innerWidth") or 0):
                fc.click(tab, pos[0], pos[1])
        else:
            fc.js(tab, f"({PROMPT_SEL}).focus()"); fc.key(tab, "Enter", "Enter", 13)
        t1 = time.time()
        while time.time() - t1 < 6:
            if not prompt_text(tab):
                return how
            time.sleep(0.5)
    raise RuntimeError("提示詞沒有送出（按了「開始生成」但輸入框還有字）")


def back_to_chat(tab):
    """2026-11-21：Flow 改版後「設定」會進右側「代理設定」頁，退不出來時提示詞框被藏（寬高 0）。
    用分頁內點擊按右側面板的「返回」，直到提示詞框看得到（不動使用者的滑鼠鍵盤）。"""
    for _ in range(4):
        if fc.js(tab, "(()=>{const e=document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]');if(!e)return false;const r=e.getBoundingClientRect();return r.width>2&&r.height>2})()"):
            return True
        fc.js(tab, "(()=>{const bs=[...document.querySelectorAll('button')].filter(b=>/arrow_back/.test(b.innerText)||b.getAttribute('aria-label')==='返回').filter(b=>{const r=b.getBoundingClientRect();return r.width>2&&r.height>2});bs.sort((a,b)=>b.getBoundingClientRect().x-a.getBoundingClientRect().x);if(bs[0])bs[0].click()})()"); time.sleep(1.2)
    return False


def open_agent_settings(tab):
    """2026-11-21 新版：右側代理面板上方的「代理設定」（settings_2）。打開後有「生成前需確認」「預設設定」「記憶」。"""
    back_to_chat(tab)
    if not _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')==='代理設定')"):
        return False
    t0 = time.time()
    while time.time() - t0 < 8:
        if fc.js(tab, "/生成前需確認/.test(document.body.innerText)"):
            return True
        time.sleep(0.5)
    return False


def confirm_mode(tab):
    """讀「生成前需確認」目前選哪個：'一律'／'永不'／None。"""
    return fc.js(tab, """(()=>{const r=[...document.querySelectorAll('[role=radio]')].find(e=>e.getAttribute('aria-checked')==='true'&&/^(一律|永不)/.test(e.innerText.trim()));
      return r?r.innerText.trim().split(/\\s/)[0]:null})()""")


def ensure_confirm_always(tab):
    """2026-11-21 花錢安全：代理設定的「生成前需確認」一定要是「一律」——是「永不」時代理會不報價直接扣點，工具的點數上限就擋不住。
    不是「一律」就改成「一律」並再讀一次確認；讀不到就拒絕生成（寧可停，不可亂扣點）。"""
    if not open_agent_settings(tab):
        raise RuntimeError("打不開「代理設定」，無法確認『生成前需確認＝一律』，為了安全先不生成（Flow 介面可能改版）")
    mode = confirm_mode(tab)
    if mode != "一律":
        _jsclick(tab, "[...document.querySelectorAll('[role=radio]')].find(e=>/^一律/.test(e.innerText.trim()))"); time.sleep(1.2)
        mode = confirm_mode(tab)
    back_to_chat(tab)
    if mode != "一律":
        raise RuntimeError(f"代理設定『生成前需確認』是「{mode}」且改不回「一律」，為了安全先不生成")
    return True


def set_memory(tab, title, text):
    """2026-11-21 代理「記憶」（專案指示）：同標題已存在且內容相同就不動；沒有就新增一張記憶卡。0 點。
    用途：臺灣口音、畫面風格、不要配樂等每鏡都要遵守的規則只寫一次。"""
    if not open_agent_settings(tab):
        return False
    have = fc.js(tab, """[...document.querySelectorAll('input[aria-label="記憶卡標題"]')].map(i=>{let e=i;for(let k=0;k<4;k++)e=e.parentElement;
      const t=e.querySelector('textarea[aria-label="記憶卡說明"]');return [i.value,t?t.value:'']})""") or []
    for t, body in have:
        if t == title:
            if body.strip() == text.strip():
                back_to_chat(tab); return "exists"
    if not any(t == title for t, _ in have):
        _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>/^add_2\\s*新增$/.test(b.innerText.trim()))"); time.sleep(1.5)
        idx = len(have)
    else:
        idx = [t for t, _ in have].index(title)
    for sel, val in (("input[aria-label=\"記憶卡標題\"]", title), ("textarea[aria-label=\"記憶卡說明\"]", text)):
        fc.js(tab, f"(()=>{{const e=document.querySelectorAll('{sel}')[{idx}];e.focus();e.select&&e.select()}})()"); time.sleep(0.3)
        fc.js(tab, "document.execCommand('selectAll');document.execCommand('delete')")
        fc.type_text(tab, val); time.sleep(0.6)
    fc.js(tab, "document.activeElement.blur()"); time.sleep(1.5)
    ok = fc.js(tab, f"""(()=>{{const t=document.querySelectorAll('textarea[aria-label="記憶卡說明"]')[{idx}];return !!t&&t.value.trim()==={json.dumps(text.strip())}}})()""")
    back_to_chat(tab)
    return "saved" if ok else False


def set_model(tab, model):
    # 2026-11-21 新版：代理設定 →「影片預設設定」→ 點模型那一列（radio_button_unchecked → checked）
    if open_agent_settings(tab):
        if _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>/影片預設設定/.test(b.innerText))"):
            time.sleep(1.5)
            row = f"""[...document.querySelectorAll('*')].filter(e=>e.children.length<8&&/^radio_button_(un)?checked/.test((e.innerText||'').trim())&&(e.innerText||'').includes({json.dumps(model)})).sort((a,b)=>a.innerText.length-b.innerText.length)[0]"""
            if fc.js(tab, f"(({row})||{{innerText:''}}).innerText.trim().startsWith('radio_button_unchecked')"):
                _jsclick(tab, row); time.sleep(1)
            ok = fc.js(tab, f"(({row})||{{innerText:''}}).innerText.trim().startsWith('radio_button_checked')")
            back_to_chat(tab)
            if ok:
                return True
        back_to_chat(tab)
    back_to_chat(tab)
    tune = find(tab, label="設定", text=None, wait=5)
    # 有兩個「設定」：右上角齒輪(settings_2) 與 提示詞旁(tune)；取 tune
    cand = [i for i in items(tab) if i["label"] == "設定" and i["text"] == "tune"]
    if not cand:
        back_to_chat(tab); return False
    click_item(tab, cand[0]); time.sleep(1.5)
    dd = find(tab, label="影片生成預設模型", wait=5)
    if dd and model not in dd["text"]:
        click_item(tab, dd); time.sleep(1)
        opt = next((i for i in items(tab) if i["role"] == "menuitem" and i["text"].startswith(model)), None)
        if opt: click_item(tab, opt); time.sleep(1)
    save = find(tab, text="儲存", wait=3)
    if save: click_item(tab, save); time.sleep(1.5)
    back = find(tab, label="返回")
    if back: click_item(tab, back); time.sleep(1)
    back_to_chat(tab)
    return True


def click_option(tab, label):
    """點最新一則確認訊息裡的選項（核准／拒絕）。先捲到畫面中央、當下量位置再點，避免版面移動點錯。"""
    for _ in range(3):
        pos = fc.js(tab, f"""(()=>{{
          const els=[...document.querySelectorAll('[role=radio][aria-label="{label}"]')].filter(e=>e.getAttribute('aria-disabled')!=='true');
          const e=els.pop(); if(!e) return null;
          e.scrollIntoView({{block:'center'}});
          const r=e.getBoundingClientRect(); return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)];
        }})()""")
        if not pos:
            return False
        time.sleep(0.6)
        pos2 = fc.js(tab, f"""(()=>{{const els=[...document.querySelectorAll('[role=radio][aria-label="{label}"]')].filter(e=>e.getAttribute('aria-disabled')!=='true');const e=els.pop();if(!e)return null;const r=e.getBoundingClientRect();return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)];}})()""")
        if pos2 == pos:
            fc.click(tab, pos[0], pos[1])
            return True
    return False


def chat_text(tab):
    return fc.js(tab, "document.body.innerText") or ""


def latest_reply(tab, marker=None):
    """代理最新回覆：只取「這次送出的提示詞」之後的文字（marker＝提示詞開頭），再切掉輸入框以後的介面字。
    2026-11-15：同一個專案裡上一次的「失敗」還留在畫面上，不能算到這一次。"""
    t = chat_text(tab)
    if marker:
        j = t.rfind(marker)
        if j >= 0:
            t = t[j + len(marker):]
    i = t.rfind("你想製作什麼內容？")
    t = t[:i] if i > 0 else t
    t = re.sub(r"(thumb_up|thumb_down|content_copy|flag|Google Flow 可能會出錯，請查證生成結果)", "", t)
    return t.strip()[-300:]


def _scroll_grid(tab, to=None):
    """媒體格只畫出畫面附近約 16 張卡（虛擬清單）。往下捲一段；to=0 捲回最上面。回傳是否還能再捲。"""
    return fc.js(tab, f"""(()=>{{const t=document.querySelector('flow-grid-tile-container');let e=t;
      while(e&&e!==document.body){{const s=getComputedStyle(e);if(/(auto|scroll)/.test(s.overflowY)&&e.scrollHeight>e.clientHeight+5)break;e=e.parentElement}}
      if(!e||e===document.body)e=document.scrollingElement;
      if({json.dumps(to)}!==null){{e.scrollTop={json.dumps(to)};return true}}
      const before=e.scrollTop;e.scrollTop=before+e.clientHeight*0.8;return e.scrollTop>before}})()""")


def attach_video(tab, media_id=None, title=None):
    """2026-11-21 延伸用：找到那支影片卡 →「更多選項」→「新增至提示詞」，把影片附進提示詞框。
    比對：縮圖網址含 media_id（同一次開頁才準，重新載入後代碼會變），或卡片標題含 title（Flow 自動取的英文標題）。
    找不到就往下捲（媒體格是虛擬清單，舊卡不在頁面上）。"""
    conds = []
    if media_id: conds.append(f"[...t.querySelectorAll('img,video')].some(m=>((m.currentSrc||m.src)||'').includes({json.dumps(media_id[:60])}))")
    if title: conds.append(f"t.innerText.includes({json.dumps(title)})")
    if not conds: return False
    find_tile = f"""[...document.querySelectorAll('flow-grid-tile-container')].find(t=>/play_circle/.test(t.innerText)&&({'||'.join(conds)}))"""
    _scroll_grid(tab, 0); time.sleep(1.5)
    for _ in range(40):
        if fc.js(tab, f"!!({find_tile})"):
            break
        if not _scroll_grid(tab):
            break
        time.sleep(1.2)
    for _ in range(3):
        if fc.js(tab, f"(()=>{{const t={find_tile};if(!t)return false;t.scrollIntoView({{block:'center'}});const b=[...t.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')==='更多選項');if(!b)return false;b.click();return true}})()"):
            time.sleep(1.2)
            if _jsclick(tab, "[...document.querySelectorAll('[role=menuitem]')].find(e=>e.innerText.includes('新增至提示詞'))"):
                time.sleep(2)
                if prompt_attachments(tab) >= 1:
                    return True
            fc.key(tab, "Escape", "Escape", 27)
        time.sleep(2)
    return False


# ---------- 2026-11-21 Flow「角色」：臉＋服裝＋聲音綁成一個角色，之後每鏡直接選角色，不必每次上傳定妝照 ----------
def character_names(tab):
    """專案裡已有的角色名稱（素材面板「角色」分頁）。"""
    open_picker(tab); picker_tab(tab, "角色")
    names = [o["text"].strip() for o in picker_options(tab)]
    close_picker(tab)
    return names


def attach_character(tab, name):
    """素材面板「角色」分頁 → 點那個角色，附進提示詞（小圖示 accessibility_new）。"""
    open_picker(tab); picker_tab(tab, "角色")
    o = [x for x in picker_options(tab) if x["text"].strip() == name] or [x for x in picker_options(tab) if name in x["text"]]
    if not o:
        close_picker(tab); return False
    return _select_option(tab, o[0]["i"])


def ensure_character(tab, name, image, voice=None, voice_style=None, info=None):
    """沒有這個角色就建立（0 點：上傳圖＋選聲音＋角色資訊，不按「製作身體」）。已存在回傳 'exists'。
    流程（2026-11-21 實測）：左側「角色」→（已有角色時按新角色）→「上傳」→ 角色頁出現「編輯名稱／選取語音／角色資訊」→「完成」。"""
    import base64
    to_project(tab); back_to_chat(tab)
    if name in character_names(tab):
        return "exists"
    proj = re.match(r"(.*?/project/[0-9a-f-]{36})", fc.js(tab, "location.href")).group(1)
    fc.call("navigate", {"tabId": tab, "url": proj + "/character"}); time.sleep(5)
    if not fc.js(tab, "[...document.querySelectorAll('button')].some(b=>/^upload\\s*上傳$/.test(b.innerText.trim()))"):
        _jsclick(tab, "[...document.querySelectorAll('button,a')].find(b=>/新角色|新增角色|New Character/.test(b.innerText))"); time.sleep(3)
    data, mime, fname = _image_bytes(image)
    _hook_file_chooser(tab)
    try:
        if not _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>/^upload\\s*上傳$/.test(b.innerText.trim()))"):
            raise RuntimeError("角色頁找不到「上傳」按鈕（介面可能改版）")
        time.sleep(1.5)
        ok = fc.js(tab, "(async()=>{const el=window.__fiEl||document.querySelector('input[type=file]');if(!el)return 'noinput';"
                        f"const b=atob({json.dumps(base64.b64encode(data).decode())});const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);"
                        f"const f=new File([u],{json.dumps(fname)},{{type:{json.dumps(mime)}}});const dt=new DataTransfer();dt.items.add(f);el.files=dt.files;"
                        "el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return 'ok'})()", timeout=120)
    finally:
        _unhook_file_chooser(tab)
    if ok != "ok":
        raise RuntimeError("角色頁的上傳欄位沒有出現")
    t0 = time.time()
    while not fc.js(tab, "!!document.querySelector('button[aria-label=\"編輯名稱\"]')"):
        if time.time() - t0 > 90:
            raise RuntimeError("角色圖片上傳後沒有進到角色編輯畫面")
        time.sleep(2)
    _jsclick(tab, "document.querySelector('button[aria-label=\"編輯名稱\"]')"); time.sleep(1)
    fc.js(tab, "(()=>{const e=document.querySelector('input[aria-label=\"角色名稱\"]');e.focus();e.select()})()"); time.sleep(0.3)
    fc.type_text(tab, name); time.sleep(0.4); fc.key(tab, "Enter", "Enter", 13); time.sleep(1.2)
    if voice:
        _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>/選取語音/.test(b.innerText))"); time.sleep(2)
        if not _jsclick(tab, f"[...document.querySelectorAll('.cdk-overlay-pane button')].find(b=>b.innerText.includes({json.dumps(voice)}))"):
            raise RuntimeError(f"語音清單裡沒有「{voice}」")
        time.sleep(1)
        if voice_style:      # 自訂風格 → 「儲存新聲音」（約 15 秒）→ 才會出現「新增至角色」
            fc.js(tab, "(()=>{const t=document.querySelector('textarea[placeholder=\"描述語音風格...\"]');t.focus();t.click()})()"); time.sleep(0.3)
            fc.type_text(tab, voice_style[:120]); time.sleep(0.6)
            _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.includes('儲存新聲音'))")
        t0 = time.time()
        while not _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.includes('新增至角色'))"):
            if time.time() - t0 > 90:
                raise RuntimeError("語音沒有加進角色（等不到「新增至角色」）")
            time.sleep(2)
        time.sleep(2)
    if info:
        fc.js(tab, "(()=>{const t=document.querySelector('textarea[aria-label=\"角色個性\"]');if(t){t.focus();t.click()}})()"); time.sleep(0.3)
        fc.type_text(tab, info); time.sleep(0.6)
    if not _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='完成')"):
        raise RuntimeError("角色頁找不到「完成」")
    time.sleep(3); to_project(tab); back_to_chat(tab)
    if name not in character_names(tab):
        raise RuntimeError("按了完成，但素材面板的「角色」裡找不到這個角色")
    return "created"


def attach_voice(tab, voice):
    """素材面板「語音」分頁 → 點聲音（預設或自訂）→「新增至提示詞」。只對「素材（Ingredients）」類生成有效（官方說明）。"""
    open_picker(tab); picker_tab(tab, "語音")
    n0 = prompt_attachments(tab)
    if not _jsclick(tab, f"[...document.querySelectorAll('.cdk-overlay-pane button')].find(b=>b.innerText.includes({json.dumps(voice)}))"):
        close_picker(tab); return False
    time.sleep(1)
    _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='新增至提示詞')"); time.sleep(2)
    close_picker(tab)
    return prompt_attachments(tab) > n0


def gen(tab_info, prompt, out_path, seconds=5, res="360p", ratio="16:9", model=MODEL_DEFAULT, max_cost=30, project=None, timeout=900,
        refs=None, ref_media=None, ref_cache=None, first=None, last=None, extend=None, edit=None, character=None, voice=None):
    tab = tab_info["id"]
    t_start = time.time()
    bring_front(tab)
    to_project(tab)
    proj = ensure_project(tab, project)
    ensure_confirm_always(tab)      # 2026-11-21 花錢安全門：代理一定要先報價再生成
    set_model(tab, model)
    clear_prompt(tab)
    before = set(media_ids(tab))
    vids_before = set(video_urls(tab))
    box = find(tab, label="你想製作什麼內容？", wait=10)
    if not box:
        raise RuntimeError("找不到 Flow 的提示詞輸入框")
    full = f"請用 {model} 生成 1 支 {seconds} 秒、{res}、{ratio} 的影片（只要 1 支）：{prompt}"
    used_refs = []
    if extend or edit:     # 2026-11-21 延伸／修改：把專案裡那支影片附進提示詞（實測報價：延伸 5 秒＝15 點）
        clear_prompt(tab)
        src = extend or edit
        ex_title = src[6:] if src.startswith("title:") else None
        if not attach_video(tab, None if ex_title else src, ex_title):
            raise RuntimeError("找不到要延伸／修改的那支影片，或附不進提示詞框（介面可能改版）")
        extra = ""
        if refs:       # 官方：延伸可附最多 3 張參考圖維持人物、場景一致
            used_refs = attach_refs(tab, tab_info.get("account"), list(refs)[:3], [], ref_cache)
            extra = "我另外附上的圖片是人物／場景參考，延伸段裡人物的臉、髮型、服裝要和參考圖一致（不要把參考圖本身放進畫面）。"
        if character:
            if not attach_character(tab, character):
                raise RuntimeError(f"專案裡找不到角色「{character}」")
            extra += f"畫面中的她就是我附上的角色「{character}」，臉、服裝、聲音都照角色設定。"
        if extend:
            full = (f"請用 {model} 把我附上的這支影片往後延伸 {seconds} 秒（延伸影片：從原片最後一格接著繼續，畫面、人物、光線、運鏡連續不跳），"
                    f"{res}、{ratio}，只要 1 支。{extra}延伸段的內容：{prompt}")
        else:
            full = (f"請用 {model} 修改我附上的這支影片（保留原本的人物、場景、運鏡、台詞與時間長度，只改下面說的地方），"
                    f"{res}、{ratio}，只要 1 支。{extra}要修改的地方：{prompt}")
        fc.js(tab, "(()=>{const e=document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]');e.click();e.focus();})()")
    elif character and not first:      # 2026-11-21 Flow 角色（臉＋服裝＋聲音）：取代每鏡上傳定妝照
        clear_prompt(tab)
        if not attach_character(tab, character):
            raise RuntimeError(f"專案裡找不到角色「{character}」（先用 character 指令建立）")
        if voice and not attach_voice(tab, voice):
            raise RuntimeError(f"語音清單裡沒有「{voice}」")
        before = set(media_ids(tab))
        full = (f"請用 {model} 生成 1 支 {seconds} 秒、{res}、{ratio} 的影片（只要 1 支）。"
                f"畫面中的人物就是我附上的角色「{character}」：臉、髮型、服裝、聲音都照角色設定。畫面內容：{prompt}")
        fc.js(tab, "(()=>{const e=document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]');e.click();e.focus();})()")
    elif first:      # 2026-11-15 首尾幀：Omni 1.2 Flash 支援 Frames to Video（First／First and last），起始畫面要先在專案裡 → 先上傳再附進提示詞
        clear_prompt(tab)
        used_refs = attach_refs(tab, tab_info.get("account"), [first] + ([last] if last else []), [], ref_cache)
        if prompt_attachments(tab) < (2 if last else 1):
            raise RuntimeError("首尾幀沒有全部附進提示詞框（介面可能改版）")
        if character and not attach_character(tab, character):      # 2026-11-21 首尾幀＋角色（聲音一致）
            raise RuntimeError(f"專案裡找不到角色「{character}」")
        before = set(media_ids(tab))
        if last:
            full = (f"請用 {model} 的「畫面轉影片（Frames to Video）：首幀和尾幀」生成 1 支 {seconds} 秒、{res}、{ratio} 的影片（只要 1 支）。"
                    f"我附上的第 1 張圖是首幀（影片的第一個畫面），第 2 張圖是尾幀（影片的最後一個畫面）："
                    f"影片要從首幀開始，自然做出中間的動作和運鏡，最後停在尾幀；不要把兩張圖並排、淡入淡出或硬切。"
                    + (f"畫面中的她就是我附上的角色「{character}」，說話聲音照角色設定。" if character else "") + f"畫面內容：{prompt}")
        else:
            full = (f"請用 {model} 的「畫面轉影片（Frames to Video）：首幀」生成 1 支 {seconds} 秒、{res}、{ratio} 的影片（只要 1 支）。"
                    f"我附上的圖是首幀（影片的第一個畫面），影片從這張圖開始動起來。畫面內容：{prompt}")
        fc.js(tab, "(()=>{const e=document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]');e.click();e.focus();})()")
    elif refs or ref_media:      # 2026-11-13 角色設定圖：先把參考圖附進提示詞（上傳不扣點）
        clear_prompt(tab)
        used_refs = attach_refs(tab, tab_info.get("account"), refs or [], ref_media or [], ref_cache)
        before = set(media_ids(tab))       # 上傳的圖也會出現在專案裡，重新記一次
        full = (f"請用 {model} 生成 1 支 {seconds} 秒、{res}、{ratio} 的影片（只要 1 支）。"
                f"我附上的圖片是角色設定圖，請當成角色參考（素材）：影片裡人物的臉、髮型、服裝都要和參考圖一致，"
                f"但不要把設定圖本身（多角度並排、灰底）放進畫面。畫面內容：{prompt}")
        fc.js(tab, "(()=>{const e=document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]');e.click();e.focus();})()")
    else:
        click_item(tab, box)
    time.sleep(0.4)
    fc.type_text(tab, full); time.sleep(0.8)
    ERR = r"(失敗|無法生成|違反|不符合政策|點數不足|已取消)"
    base_txt = chat_text(tab)
    n_before = len(re.findall(r"消耗\s*[\d,]+\s*點", base_txt))
    send_prompt(tab)
    # 等代理回覆「會消耗 N 點」並核准
    cost = None
    t0 = time.time()
    while time.time() - t0 < 120:
        txt = chat_text(tab)
        hits = re.findall(r"消耗\s*([\d,]+)\s*點", txt)
        if len(hits) > n_before:
            cost = int(hits[-1].replace(",", "")); break
        time.sleep(2)
    if cost is None:
        raise RuntimeError("Flow 代理沒有回覆點數確認（可能需要人工查看分頁）")
    if cost > max_cost:
        click_option(tab, "拒絕")
        return {"ok": False, "reason": "cost_over_limit", "cost": cost, "max_cost": max_cost}
    time.sleep(1.5)
    n_err = len(re.findall(ERR, chat_text(tab)))
    if not click_option(tab, "核准"):
        raise RuntimeError("找不到「核准」按鈕")
    # 等新影片出現
    new = None
    t0 = time.time()
    strikes = 0
    while time.time() - t0 < timeout:
        time.sleep(8)
        d = [m for m in media_ids(tab) if m not in before]
        if d: new = d[0]; break
        # 2026-11-15：只看代理最新一則回覆（頁面載入舊訊息會讓整頁的錯誤字數變多，造成誤判），連續兩次都看到才算失敗
        tail = latest_reply(tab, full[:40])
        strikes = strikes + 1 if re.search(ERR, tail) else 0
        if strikes >= 2:
            r = {"ok": False, "reason": "flow_error", "message": tail[-200:], "cost": cost}
            if "無法生成音訊" in tail:      # 2026-11-21 實測：多人說話（遠處喊話）常卡在生成聲音；失敗點數會退還
                r["hint"] = ("Flow 生不出這段聲音（點數會退還）。改法：①提示詞只留主角一人說話、其他人聲改後製配 "
                             "②或在專案設定開「傳回無聲影片」，聲音全部後製")
            return r
    if not new:
        raise RuntimeError("等候逾時，影片還沒出現")
    try:      # 2026-11-21 記下 Flow 自動取的卡片標題：之後要延伸這支，用 --extend "title:標題" 找得到（縮圖代碼重新載入會變）
        title = fc.js(tab, f"(()=>{{const t=[...document.querySelectorAll('flow-grid-tile-container')].find(t=>[...t.querySelectorAll('img')].some(m=>(m.src||'').includes({json.dumps(new[:60])})));return t?t.innerText.replace(/play_circle|[0-9]+p/g,'').trim():''}})()")
    except Exception:
        title = ""
    url = download_url(tab, new, vids_before)
    to_project(tab)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    data = urllib.request.urlopen(url, timeout=300).read()
    open(out_path, "wb").write(data)
    r = {"ok": True, "file": os.path.abspath(out_path), "bytes": len(data), "media_id": new, "cost": cost,
         "account": tab_info["account"], "project": proj, "seconds_used": int(time.time() - t_start), "title": title}
    if used_refs:
        r["refs"] = used_refs
    if first:
        r["mode"] = "frames_first_last" if last else "frames_first"
    if extend:
        r["mode"] = "extend"; r["extended_from"] = extend
    if edit:
        r["mode"] = "edit"; r["edited_from"] = edit
    if character:
        r["character"] = character
    return r


def video_urls(tab):
    return fc.js(tab, "performance.getEntriesByType('resource').map(e=>e.name).filter(n=>n.includes('flow-content.google/video/'))") or []


def tile_video_url(tab, key, quality="原始大小", timeout=40):
    """2026-11-13 新版介面（格狀媒體卡）：找到縮圖含 key 的那張卡 →「更多選項」→「下載」→「360p 原始大小」，
    攔下網頁去抓的 flow-content.google/video/… 有簽章網址（同時擋掉網頁自己存檔到「下載」資料夾）。找不到回傳 ""。"""
    find_tile = f"""[...document.querySelectorAll('flow-grid-tile-container')].find(t=>[...t.querySelectorAll('img,video')].some(m=>((m.currentSrc||m.src)||'').includes({json.dumps(key)})))"""
    if not fc.js(tab, f"!!({find_tile})"):
        return ""
    fc.js(tab, """(()=>{if(window.__vgOF)return;window.__vgCap=[];const of=window.fetch;window.__vgOF=of;
      window.fetch=function(u){try{const s=String((u&&u.url)||u);if(s.includes('flow-content.google/video/'))window.__vgCap.push(s)}catch(e){};return of.apply(this,arguments)};
      const ac=HTMLAnchorElement.prototype.click;window.__vgAC=ac;
      HTMLAnchorElement.prototype.click=function(){if(this.href.startsWith('blob:')&&this.download){window.__vgCap.push('saved:'+this.download);return;}return ac.call(this)};})()""")
    try:
        if not fc.js(tab, f"(()=>{{const t={find_tile};const b=t&&[...t.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')==='更多選項');if(!b)return false;b.click();return true}})()"):
            return ""
        time.sleep(1.2)
        if not _jsclick(tab, "[...document.querySelectorAll('[role=menuitem]')].find(e=>e.innerText.trim().endsWith('下載'))"):
            fc.key(tab, "Escape", "Escape", 27); return ""
        time.sleep(1.2)
        if not _jsclick(tab, f"[...document.querySelectorAll('[role=menuitem]')].find(e=>e.innerText.includes({json.dumps(quality)}))"):
            fc.key(tab, "Escape", "Escape", 27); return ""
        t0 = time.time()
        while time.time() - t0 < timeout:
            cap = fc.js(tab, "window.__vgCap||[]") or []
            urls = [u for u in cap if u.startswith("http")]
            if urls:
                return urls[-1]
            time.sleep(1)
        return ""
    finally:
        fc.js(tab, """(()=>{if(!window.__vgOF)return;window.fetch=window.__vgOF;HTMLAnchorElement.prototype.click=window.__vgAC;delete window.__vgOF;})()""")
        fc.key(tab, "Escape", "Escape", 27)



def download_url(tab, media_id, vids_before=()):
    """點選那張媒體卡 → 按「下載」→ 從網頁載入紀錄讀出有簽章的影片網址。
    2026-11-13：影片編號有時和縮圖編號不同 → 只要出現「生成前沒有的」影片網址就採用。"""
    def pick():
        urls = video_urls(tab)
        exact = [u for u in urls if f"/video/{media_id}" in u]
        if exact:
            return exact[-1]
        fresh = [u for u in urls if u not in vids_before and u.split("?")[0] not in {v.split("?")[0] for v in vids_before}]
        return fresh[-1] if fresh else ""
    for attempt in range(3):
        got = tile_video_url(tab, media_id)      # 新版格狀介面：用那張卡自己的「下載 → 原始大小」，最準
        if got: return got
        tp = _tile_download_pos(tab, media_id)      # 2026-11-13 新版介面：直接按那張卡那一列的「下載」
        if tp:
            fc.click(tab, tp[0], tp[1]); time.sleep(5)
            got = pick()
            if got: return got
        pos = fc.js(tab, f"(()=>{{const i=[...document.querySelectorAll('img')].find(x=>x.src.includes('{media_id}'));if(!i)return null;const r=i.getBoundingClientRect();return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)]}})()")
        if pos: fc.click(tab, pos[0], pos[1]); time.sleep(2.5)
        dl = find(tab, label="下載", wait=5)
        if dl: click_item(tab, dl); time.sleep(5)
        got = pick()
        if got: return got
        to_project(tab)
    raise RuntimeError("找不到影片下載網址")


def login(account, pw=None):
    """AI 自動登入：開 Google 登入頁、填帳號、（有給密碼就）填密碼。
    Google 若擋自動登入或要手機驗證，回傳 need_human，請學員在分頁上完成。"""
    tabs = fc.call("tabs", timeout=20)
    if not tabs:
        raise RuntimeError("請先在 Chrome 打開任一個 https://flow.google.com 分頁")
    url = "https://accounts.google.com/AddSession?Email=" + urllib.parse.quote(account) + "&continue=https%3A%2F%2Fflow.google.com%2F"
    t = fc.call("open", {"url": url, "windowId": tabs[0]["windowId"]}, timeout=30)
    tab = t["id"]; time.sleep(5)
    for step in range(3):
        u = fc.js(tab, "location.href")
        if "flow.google.com" in u:
            return {"ok": True, "account": account, "tab": tab}
        if fc.js(tab, "!!document.querySelector('input[type=email]:not([aria-hidden=true])')"):
            fc.js(tab, "document.querySelector('input[type=email]').focus()"); fc.type_text(tab, account); fc.key(tab, "Enter", "Enter", 13); time.sleep(5); continue
        if pw and fc.js(tab, "!!document.querySelector('input[type=password]')"):
            fc.js(tab, "document.querySelector('input[type=password]').focus()"); fc.type_text(tab, pw); fc.key(tab, "Enter", "Enter", 13); time.sleep(6); continue
        break
    u = fc.js(tab, "location.href")
    if "flow.google.com" in u:
        return {"ok": True, "account": account, "tab": tab}
    return {"ok": False, "need_human": True, "tab": tab, "url": u[:120],
            "message": "Google 需要你本人確認（輸入密碼、手機驗證或安全檢查）。請在 Chrome 跳出的分頁完成登入，完成後告訴 AI「好了」。"}


# ---------- 2026-11-13 角色設定圖：素材面板、上傳參考圖、生成圖片 ----------
# 介面名稱來自 2026-11-13 實際讀取 Flow 畫面（研究紀錄：06_實測紀錄\20261113_角色設定圖\研究.md）
PICK_BTN = "在提示詞輸入框新增素材"


def _pos(tab, js_find):
    """js_find 是一段回傳元素的 JS 運算式；回傳元素中心座標或 None。"""
    return fc.js(tab, f"(()=>{{const e=({js_find});if(!e)return null;e.scrollIntoView({{block:'center'}});"
                      f"const r=e.getBoundingClientRect();return [Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)]}})()")


def _jsclick(tab, js_find):
    """用網頁自己的 click()（不靠螢幕座標：Chrome 視窗縮小或分頁在背景時座標會不準）。"""
    return bool(fc.js(tab, f"(()=>{{const e=({js_find});if(!e)return false;e.click();return true}})()"))


def picker_open(tab):
    return bool(fc.js(tab, "[...document.querySelectorAll('[role=tab]')].some(e=>e.innerText.includes('上傳的項目'))"))


def open_picker(tab):
    if picker_open(tab):
        return True
    sel = f"document.querySelector('button[aria-label=\"{PICK_BTN}\"]')"
    for _ in range(3):
        t0 = time.time()
        while not _jsclick(tab, sel):
            if time.time() - t0 > 10:
                raise RuntimeError("找不到「在提示詞輸入框新增素材」按鈕（Flow 介面可能改版）")
            time.sleep(1)
        t0 = time.time()
        while time.time() - t0 < 6:
            if picker_open(tab):
                return True
            time.sleep(0.5)
    raise RuntimeError("素材面板沒有打開")


def close_picker(tab):
    if not picker_open(tab):
        return
    if not _jsclick(tab, f"document.querySelector('button[aria-label=\"{PICK_BTN}\"]')"):
        fc.key(tab, "Escape", "Escape", 27)
    time.sleep(1)
    if picker_open(tab):
        fc.key(tab, "Escape", "Escape", 27); time.sleep(1)


def picker_tab(tab, name):
    if not _jsclick(tab, f"[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes({json.dumps(name)}))"):
        raise RuntimeError(f"素材面板沒有「{name}」分頁")
    time.sleep(1.8)


def picker_options(tab):
    """目前分頁的素材清單：[{i, text, media}]（media＝縮圖網址裡的媒體編號）"""
    return fc.js(tab, """[...document.querySelectorAll('[role=option]')].map((e,i)=>{const im=e.querySelector('img');
      const m=im&&(im.src.match(/\\/image\\/([0-9a-f-]{36})/)||im.src.match(/\\/asb\\/([^?]{1,80})/));return {i, text:e.innerText.replace(/\\s+/g,' ').slice(0,60), media:m?m[1]:null}})""") or []


def prompt_attachments(tab):
    """提示詞輸入框所在區塊裡的圖片數（附上素材後會變多）。"""
    # 2026-11-21：只數 .base-prompt-box 裡的（往上找太多層會數到整個代理面板的圖）；角色／語音小圖沒有 img，改數「素材」小圖按鈕
    return fc.js(tab, """(()=>{const t=document.querySelector('[role=textbox][aria-label="你想製作什麼內容？"]');const e=t&&t.closest('.base-prompt-box');
      if(!e)return 0;return Math.max(e.querySelectorAll('img').length,e.querySelectorAll('button[aria-label="素材"]').length)})()""") or 0


def _select_option(tab, i):
    """點素材面板第 i 個項目並附進提示詞。2026-11-13 實測：圖片點一下就直接附上、面板自動關閉；
    影片會先出預覽，要再按「新增至提示詞」。回傳是否多了一個附件。"""
    n0 = prompt_attachments(tab)
    _jsclick(tab, f"document.querySelectorAll('[role=option]')[{i}]")
    t0 = time.time()
    while time.time() - t0 < 4:
        time.sleep(0.8)
        if prompt_attachments(tab) > n0:
            close_picker(tab)
            return True
    if _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='新增至提示詞')"):
        time.sleep(2)
    close_picker(tab)
    return prompt_attachments(tab) > n0


def pick_media(tab, media_id):
    """在素材面板找已在專案裡的圖片（依媒體編號），附進提示詞。找不到回傳 False。"""
    open_picker(tab)
    for t in ("圖像", "上傳的項目", "全部"):
        picker_tab(tab, t)
        for o in picker_options(tab):
            if o["media"] == media_id:
                return _select_option(tab, o["i"])
    close_picker(tab)
    return False


def _hook_file_chooser(tab):
    """攔下 Flow 開檔案視窗的動作（不會跳出 Windows 檔案視窗），把 <input type=file> 留給程式填。"""
    fc.js(tab, """(()=>{if(window.__vgHook)return;window.__vgHook=1;window.__fiEl=null;
      const o=HTMLInputElement.prototype.click;window.__vgClick=o;
      HTMLInputElement.prototype.click=function(){if(this.type==='file'){window.__fiEl=this;return;}return o.call(this)};
      const sp=HTMLInputElement.prototype.showPicker;window.__vgSP=sp;
      if(sp)HTMLInputElement.prototype.showPicker=function(){if(this.type==='file'){window.__fiEl=this;return;}return sp.call(this)};})()""")


def _unhook_file_chooser(tab):
    fc.js(tab, """(()=>{if(!window.__vgHook)return;HTMLInputElement.prototype.click=window.__vgClick;
      if(window.__vgSP)HTMLInputElement.prototype.showPicker=window.__vgSP;window.__vgHook=0;})()""")


def _image_bytes(path, max_side=1536):
    """讀圖；有 Pillow 就縮到長邊 1536、轉 JPEG（上傳比較快）。"""
    try:
        from PIL import Image
        import io
        im = Image.open(path).convert("RGB")
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=92)
        return buf.getvalue(), "image/jpeg", os.path.splitext(os.path.basename(path))[0] + ".jpg"
    except Exception:
        ext = os.path.splitext(path)[1].lower()
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext, "image/png")
        return open(path, "rb").read(), mime, os.path.basename(path)


def upload_ref(tab, path):
    """素材面板 →「上傳媒體」→ 把圖片檔交給 Flow（不扣點）→ 選取剛上傳的那張 →「新增至提示詞」。回傳媒體編號（讀不到就 None）。"""
    import base64
    if not os.path.exists(path):
        raise RuntimeError(f"找不到參考圖：{path}")
    data, mime, name = _image_bytes(path)
    # 2026-11-21：素材面板只列 15 張、新圖縮圖網址常讀不到 → 改用「每次不同的檔名」認新上傳的那張
    stem, ext = os.path.splitext(name)
    name = f"{stem}_{int(time.time())}{ext}"
    open_picker(tab)
    picker_tab(tab, "上傳的項目")
    first = picker_options(tab)
    before = {o["media"] for o in first}
    n_before = len(first)
    _hook_file_chooser(tab)
    try:
        if not _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.includes('上傳媒體'))"):
            raise RuntimeError("找不到「上傳媒體」按鈕")
        time.sleep(1.5)
        ok = fc.js(tab, "(async()=>{const el=window.__fiEl||document.querySelector('input[type=file]');if(!el)return 'noinput';"
                        f"const b=atob({json.dumps(base64.b64encode(data).decode())});const u=new Uint8Array(b.length);"
                        "for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);"
                        f"const f=new File([u],{json.dumps(name)},{{type:{json.dumps(mime)}}});const dt=new DataTransfer();dt.items.add(f);"
                        "el.files=dt.files;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return 'ok'})()",
                   timeout=120)
    finally:
        _unhook_file_chooser(tab)
    if ok != "ok":
        raise RuntimeError("Flow 的上傳欄位沒有出現（介面可能改版）")
    # 等上傳完成：「上傳的項目」多一張
    t0 = time.time(); new = None
    k = 0
    while time.time() - t0 < 240:
        time.sleep(3); k += 1
        if k > 1 and picker_open(tab):      # 2026-11-21：面板開著時清單不會更新 → 關掉重開才看得到新上傳的圖
            close_picker(tab)
        if not picker_open(tab):
            open_picker(tab)
        picker_tab(tab, "上傳的項目")
        opts = picker_options(tab)
        named = [o for o in opts if o["text"].startswith(name)]
        if named:
            new = named[0]
            break
        fresh = [o for o in opts if o["media"] and o["media"] not in before]
        if fresh or len(opts) > n_before:
            new = fresh[0] if fresh else opts[0]
            break
    if not new:
        close_picker(tab)
        raise RuntimeError("圖片上傳逾時（240 秒內沒有出現在「上傳的項目」）")
    t0 = time.time()
    while not new.get("media") and time.time() - t0 < 15:   # 縮圖還沒載入時讀不到媒體編號：再等一下（快取要用）
        time.sleep(2)
        opts = picker_options(tab)
        if len(opts) > new["i"]:
            new = opts[new["i"]]
    if not _select_option(tab, new["i"]):
        raise RuntimeError("參考圖沒有附進提示詞框")
    return new.get("media")


def _sha(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def attach_refs(tab, account, refs, ref_media, cache_path=None):
    """把參考圖一張一張附進提示詞框。有快取（同帳號＋同專案＋同一張圖上傳過）就直接從專案選，不重複上傳。"""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            cache = {}
    m = re.match(r"(.*?/project/[0-9a-f-]{36})", fc.js(tab, "location.href") or "")
    proj = m.group(1) if m else ""
    used = []
    for mid in ref_media:
        if not pick_media(tab, mid):
            raise RuntimeError(f"專案裡找不到媒體 {mid}")
        used.append({"media": mid, "how": "pick"})
    for p in refs:
        key = f"{account}|{proj}|{_sha(p)}"
        mid = cache.get(key)
        if mid and pick_media(tab, mid):
            used.append({"file": p, "media": mid, "how": "pick"}); continue
        mid = upload_ref(tab, p)
        used.append({"file": p, "media": mid, "how": "upload"})
        if mid and cache_path:
            cache[key] = mid
            json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return used


def image_tiles(tab):
    """2026-11-15：專案格狀卡裡的「圖片」卡 → {代號: 圖片網址}。代號＝縮圖網址裡的媒體編號／asb 代碼。
    Flow 11/15 起連生成的圖也標成「顯示使用者圖像的圖塊」，不能再靠 alt 分辨；改成：
    排除影片卡（有 play_circle）、排除我們自己上傳的檔案（卡片名稱是 xxx.jpg／.png 等檔名）。"""
    return fc.js(tab, r"""(()=>{const o={};for(const t of document.querySelectorAll('flow-grid-tile-container')){
      if((t.innerText||'').includes('play_circle'))continue;
      if(/\.(jpe?g|png|webp|gif|heic|heif)$/i.test(t.getAttribute('aria-label')||''))continue;
      const im=t.querySelector('img');if(!im)continue;const s=im.currentSrc||im.src||'';
      const k=s.includes('flow-content.google/image/')?s.split('/image/')[1].split('?')[0]:(s.includes('/asb/')?s.split('/asb/')[1].split('?')[0].slice(0,80):null);
      if(k)o[k]=s;}return o})()""") or {}


def new_images(tab, before):
    return [k for k in image_tiles(tab) if k not in before]


def image_src(tab, media_id):
    return fc.js(tab, f"(()=>{{const i=[...document.querySelectorAll('img')].find(x=>x.src.includes({json.dumps(media_id)}));return i?i.src:''}})()") or ""


def gen_image(tab_info, prompt, out_path, ratio="16:9", model=IMAGE_MODEL_DEFAULT, max_cost=0, project=None, timeout=300,
              refs=None, ref_cache=None, ref_mode="all"):
    """用 Flow 代理生成 1 張圖並下載。代理回報「消耗 N 點」超過 max_cost 就拒絕；沒問點數就直接生成的話 cost 記 0。"""
    tab = tab_info["id"]
    t_start = time.time()
    bring_front(tab)
    to_project(tab)
    proj = ensure_project(tab, project)
    ensure_confirm_always(tab)      # 2026-11-21 花錢安全門（圖片若要扣點也要先報價）
    clear_prompt(tab)
    before = set(image_tiles(tab))
    box = find(tab, label="你想製作什麼內容？", wait=10)
    if not box:
        raise RuntimeError("找不到 Flow 的提示詞輸入框")
    full = f"請用 {model} 生成 1 張 {ratio} 的圖像（只要 1 張，不要影片）：{prompt}"
    used_refs = []
    if refs:      # 2026-11-15：附參考圖生圖（尾幀附首幀、角色設定圖），上傳不扣點
        used_refs = attach_refs(tab, tab_info.get("account"), refs, [], ref_cache)
        before = set(image_tiles(tab))
        # 2026-11-15 實測：角色設定圖的背景會把場景帶走（屋頂變大廳）→ 依用途分開說明
        how = {"person": "我附上的圖片只是角色參考：只照圖中人物的臉、髮型、服裝；場景、背景、光線、構圖一律照下面的文字，不要用參考圖的背景。",
               "scene": "第 1 張附圖是同一鏡的首幀：場景、背景、鏡頭角度、光線、人物位置都要和它一樣，只把動作推進到下面描述的樣子；其他附圖是角色參考，只照人物的臉和服裝。",
               }.get(ref_mode, "我附上的圖片是參考圖：人物的臉、髮型、服裝、場景、光線和畫風都要和參考圖一致。")
        full = (f"請用 {model} 生成 1 張 {ratio} 的圖像（只要 1 張，不要影片，比例一定要 {ratio}）。{how}不要把參考圖原樣複製或並排。畫面內容：{prompt}")
    fc.js(tab, "(()=>{const e=document.querySelector('[role=textbox][aria-label=\"你想製作什麼內容？\"]');e.click();e.focus();})()"); time.sleep(0.4)
    fc.type_text(tab, full); time.sleep(0.8)
    ERR = r"(失敗|無法生成|違反|不符合政策|點數不足|已取消)"
    radios = "document.querySelectorAll('[role=radio][aria-label=\"核准\"]:not([aria-disabled=true])').length"
    base_txt = chat_text(tab)
    n_before = len(re.findall(r"消耗\s*[\d,]+\s*點", base_txt))
    n_radio = fc.js(tab, radios) or 0
    send_prompt(tab)
    cost, asked, new = None, False, None
    t0 = time.time()
    while time.time() - t0 < 120:
        time.sleep(2)
        txt = chat_text(tab)
        hits = re.findall(r"消耗\s*([\d,]+)\s*點", txt)
        if len(hits) > n_before:
            cost = int(hits[-1].replace(",", "")); asked = True; break
        if (fc.js(tab, radios) or 0) > n_radio:
            asked = True; cost = 0; break
        d = new_images(tab, before)
        if d:
            new = d[0]; cost = 0; break
    if cost is None:
        raise RuntimeError("Flow 代理沒有回覆（可能需要人工查看分頁）")
    if asked:
        if cost > max_cost:
            click_option(tab, "拒絕")
            return {"ok": False, "reason": "cost_over_limit", "cost": cost, "max_cost": max_cost}
        time.sleep(1.5)
        if not click_option(tab, "核准"):
            raise RuntimeError("找不到「核准」按鈕")
    strikes = 0
    t0 = time.time()
    while not new and time.time() - t0 < timeout:
        time.sleep(5)
        d = new_images(tab, before)
        if d:
            new = d[0]; break
        tail = latest_reply(tab, full[:40])      # 2026-11-15：只看最新回覆、連續兩次才算失敗（避免舊訊息誤判）
        strikes = strikes + 1 if re.search(ERR, tail) else 0
        if strikes >= 2:
            return {"ok": False, "reason": "flow_error", "message": tail[-200:], "cost": cost}
    if not new:
        raise RuntimeError("等候逾時，圖片還沒出現")
    time.sleep(3)
    url = image_tiles(tab).get(new, "") or image_src(tab, new)
    if "flow.google.com/asb/" in url:      # 2026-11-15 縮圖網址結尾 =s512-rw（長邊 512），改 =s0 拿原圖（直式 768×1376）
        url = re.sub(r"=s\d+(-[a-z]+)*$", "=s0", url)
    if not url:
        raise RuntimeError("找不到圖片網址")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    data = page_fetch(tab, url) if "flow.google.com/asb/" in url else urllib.request.urlopen(url, timeout=120).read()
    tmp = out_path + ".download"
    open(tmp, "wb").write(data)
    size = None
    try:                     # Flow 給的可能是 JPEG／WebP：有 Pillow 就統一轉成 PNG
        from PIL import Image
        im = Image.open(tmp); size = im.size
        im.convert("RGB").save(out_path, "PNG"); im.close(); os.remove(tmp)
    except Exception:
        os.replace(tmp, out_path)
    return {"ok": True, "file": os.path.abspath(out_path), "bytes": os.path.getsize(out_path), "size": size, "media_id": new,
            "cost": cost, "asked": asked, "model": model, "account": tab_info["account"], "project": proj,
            "seconds_used": int(time.time() - t_start)} | ({"refs": used_refs} if used_refs else {})


def ref_check(tab_info, project=None):
    """不花點數的介面檢查：素材面板的分頁、上傳按鈕、檔案欄位都還在；檢查完關面板、回到原本網址。"""
    tab = tab_info["id"]
    url0 = fc.js(tab, "location.href")
    res = {"account": tab_info["account"], "start_url": url0}
    try:
        if project:
            fc.call("navigate", {"tabId": tab, "url": project}); time.sleep(7)
        to_project(tab)
        if "/project/" not in (fc.js(tab, "location.href") or ""):
            res["ok"] = False
            res["error"] = "這個分頁不在任何 Flow 專案裡（ref-check 不會自己新增專案）。請先打開一個專案。"
            return res
        res["prompt_box"] = bool(find(tab, label="你想製作什麼內容？", wait=10))
        open_picker(tab)
        res["tabs"] = fc.js(tab, "[...document.querySelectorAll('[role=tab]')].map(e=>e.innerText.replace(/\\s+/g,' ').replace(/^\\S+ /,''))")
        res["upload_button"] = bool(fc.js(tab, "[...document.querySelectorAll('button')].some(b=>b.innerText.includes('上傳媒體'))"))
        _hook_file_chooser(tab)
        try:
            if _jsclick(tab, "[...document.querySelectorAll('button')].find(b=>b.innerText.includes('上傳媒體'))"):
                time.sleep(1.5)
            res["file_input_accept"] = fc.js(tab, "(window.__fiEl||document.querySelector('input[type=file]')||{}).accept||''")
        finally:
            _unhook_file_chooser(tab)
        picker_tab(tab, "圖像")
        res["images_in_project"] = len(picker_options(tab))
        close_picker(tab)
        res["ok"] = bool(res["prompt_box"] and res["upload_button"] and "上傳的項目" in " ".join(res["tabs"] or []) and res["file_input_accept"])
    finally:
        try:
            close_picker(tab)
        except Exception:
            pass
        try:
            if fc.js(tab, "location.href") != url0:
                fc.call("navigate", {"tabId": tab, "url": url0}); time.sleep(4)
        except Exception:
            pass
    return res

import urllib.parse


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--account"); ap.add_argument("--accounts"); ap.add_argument("--password")
    ap.add_argument("--prompt"); ap.add_argument("--out")
    ap.add_argument("--seconds", type=int, default=5); ap.add_argument("--res", default="360p"); ap.add_argument("--ratio", default="16:9")
    ap.add_argument("--model", default=MODEL_DEFAULT); ap.add_argument("--max-cost", type=int, default=30); ap.add_argument("--project")
    ap.add_argument("--ref", action="append", default=[]); ap.add_argument("--ref-media", action="append", default=[]); ap.add_argument("--ref-cache")
    ap.add_argument("--image-model", default=IMAGE_MODEL_DEFAULT)
    ap.add_argument("--first"); ap.add_argument("--last")
    ap.add_argument("--edit", help="要修改的影片：media_id 或 title:卡片標題（用代理修改既有影片，不整鏡重生）")
    ap.add_argument("--character", help="附上專案裡的 Flow 角色（臉＋服裝＋聲音）")
    ap.add_argument("--voice", help="附上語音（預設或自訂聲音名稱；只對素材類生成有效）")
    ap.add_argument("--name"); ap.add_argument("--image"); ap.add_argument("--voice-style"); ap.add_argument("--info")
    ap.add_argument("--title"); ap.add_argument("--text")
    ap.add_argument("--extend", help="要延伸的影片：media_id，或 title:卡片標題（例 title:Woman covers camera in alley）")
    ap.add_argument("--ref-mode", default="all", choices=["all", "person", "scene"])
    a = ap.parse_args()
    try:
        if a.cmd == "status":
            st = json.loads(urllib.request.urlopen(fc.BASE + "/ext/status", timeout=5).read())
            tabs = flow_tabs() if st.get("connected") else []
            out({"bridge": True, "extension_connected": st.get("connected"), "flow_tabs": [{"tab": t["id"], "account": t["account"], "paid": t["paid"]} for t in tabs]})
        if a.cmd == "credits":
            res = []
            for t in [x for x in flow_tabs() if x["account"] and (not a.account or x["account"] == a.account)]:
                res.append({"account": t["account"], "credits": credits(t["id"])})
            out({"credits": res})
        if a.cmd == "safety":      # 2026-11-21 檢查（必要時改回）代理設定「生成前需確認＝一律」
            t = tab_for(a.account)["id"]; bring_front(t); to_project(t)
            out({"ok": ensure_confirm_always(t), "confirm_before_generate": "一律"})
        if a.cmd == "memory":      # 代理記憶（專案指示）：--title 標題 --text 內容
            t = tab_for(a.account)["id"]; bring_front(t); to_project(t)
            m = set_memory(t, a.title, a.text); out({"ok": bool(m), "result": m})
        if a.cmd == "character":   # 建立 Flow 角色：--name --image [--voice Autonoe --voice-style ... --info ...]
            t = tab_for(a.account)["id"]; bring_front(t)
            out({"ok": True, "result": ensure_character(t, a.name, a.image, a.voice, a.voice_style, a.info)})
        if a.cmd == "gen":
            if a.extend or a.edit:
                out(gen(tab_for(a.account), a.prompt, a.out, a.seconds, a.res, a.ratio, a.model, a.max_cost, a.project,
                        refs=a.ref, ref_cache=a.ref_cache, extend=a.extend, edit=a.edit, character=a.character))
            if a.character and not a.first:
                out(gen(tab_for(a.account), a.prompt, a.out, a.seconds, a.res, a.ratio, a.model, a.max_cost, a.project,
                        character=a.character, voice=a.voice))
            if a.first:
                out(gen(tab_for(a.account), a.prompt, a.out, a.seconds, a.res, a.ratio, a.model, a.max_cost, a.project,
                        ref_cache=a.ref_cache, first=a.first, last=a.last, character=a.character))
            if a.ref or a.ref_media:
                out(gen(tab_for(a.account), a.prompt, a.out, a.seconds, a.res, a.ratio, a.model, a.max_cost, a.project,
                        refs=a.ref, ref_media=a.ref_media, ref_cache=a.ref_cache))
            out(gen(tab_for(a.account), a.prompt, a.out, a.seconds, a.res, a.ratio, a.model, a.max_cost, a.project))
        if a.cmd == "gen-image":
            mc = a.max_cost if "--max-cost" in sys.argv else 0      # 圖片預設 0 點上限：要扣點就先拒絕
            out(gen_image(tab_for(a.account), a.prompt, a.out, a.ratio, a.image_model, mc, a.project, refs=a.ref, ref_cache=a.ref_cache, ref_mode=a.ref_mode))
        if a.cmd == "ref-check":
            out(ref_check(tab_for(a.account), a.project))
        if a.cmd == "gen-rotate":
            tried = []
            for acc in [x.strip() for x in (a.accounts or "").split(",") if x.strip()]:
                try:
                    t = tab_for(acc)
                except Exception as e:
                    tried.append({"account": acc, "skip": str(e)}); continue
                c = credits(t["id"])
                if c is not None and c < 5:
                    tried.append({"account": acc, "credits": c, "skip": "點數不足"}); continue
                r = gen(t, a.prompt, a.out, a.seconds, a.res, a.ratio, a.model, a.max_cost)
                if r.get("ok"):
                    r["tried"] = tried; out(r)
                tried.append({"account": acc, "result": r})
            out({"ok": False, "need_api": True, "tried": tried, "message": "所有帳號點數都不夠，請改走 B 路（Gemini API）。"}, 2)
        if a.cmd == "login":
            out(login(a.account, a.password))
        out({"error": "不認得的指令"}, 1)
    except SystemExit:
        raise
    except Exception as e:
        out({"ok": False, "error": str(e)}, 1)


if __name__ == "__main__":
    main()
