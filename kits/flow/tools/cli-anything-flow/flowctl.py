"""開發／除錯用：透過橋接伺服器對 Flow 分頁下指令。
python flowctl.py ping
python flowctl.py tabs
python flowctl.py js <tabId> "<JavaScript 運算式>"
python flowctl.py shot <tabId> 輸出.png
"""
import base64, json, sys, urllib.request

BASE = "http://127.0.0.1:8840"


def call(action, params=None, timeout=120):
    req = urllib.request.Request(BASE + "/cmd", data=json.dumps(
        {"action": action, "params": params or {}, "timeout": timeout}).encode(), headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=timeout + 10).read())
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["result"]


def js(tab, expr, timeout=60):
    r = call("cdp", {"tabId": tab, "method": "Runtime.evaluate",
                     "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}, timeout)
    if r.get("exceptionDetails"):
        raise RuntimeError(json.dumps(r["exceptionDetails"], ensure_ascii=False)[:800])
    return r["result"].get("value")


def cdp(tab, method, params=None, timeout=60):
    return call("cdp", {"tabId": tab, "method": method, "params": params or {}}, timeout)


def click(tab, x, y):
    """真實滑鼠事件（只送進這個分頁，不動實體滑鼠）。"""
    cdp(tab, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    cdp(tab, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    cdp(tab, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})


def type_text(tab, text):
    cdp(tab, "Input.insertText", {"text": text})


def key(tab, k, code=None, vk=None):
    cdp(tab, "Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": code or k, "windowsVirtualKeyCode": vk or 0})
    cdp(tab, "Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": code or k, "windowsVirtualKeyCode": vk or 0})


def dump(tab):
    import os
    return js(tab, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_dump.js"), encoding="utf-8").read())


def shot(tab, path):
    r = call("cdp", {"tabId": tab, "method": "Page.captureScreenshot", "params": {"format": "png"}})
    open(path, "wb").write(base64.b64decode(r["data"]))
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if a[0] == "ping": print(call("ping"))
    elif a[0] == "tabs": print(json.dumps(call("tabs"), ensure_ascii=False, indent=1))
    elif a[0] == "js": print(json.dumps(js(int(a[1]), a[2]), ensure_ascii=False, indent=1))
    elif a[0] == "shot": print(shot(int(a[1]), a[2]))
