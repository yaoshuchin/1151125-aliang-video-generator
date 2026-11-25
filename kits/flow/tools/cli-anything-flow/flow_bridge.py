"""Flow 小幫手的本機橋接伺服器（只用 Python 內建功能）。

擴充功能 → GET  /ext/poll   取下一個指令（長輪詢 25 秒）
擴充功能 → POST /ext/result 回傳結果
本機程式 → POST /cmd        {"action":..., "params":{...}}，等到結果才回應

只綁 127.0.0.1，外面的電腦連不進來。
可單獨執行：python flow_bridge.py  （預設埠 8840）
也可被生成器伺服器 import 後掛上同一個埠。
"""
import json, socket, queue, threading, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = 8840


class Bridge:
    def __init__(self):
        self.q = queue.Queue()
        self.waiting = {}          # id -> [Event, result]
        self.last_poll = 0.0

    @property
    def connected(self):
        return time.time() - self.last_poll < 35

    def call(self, action, params=None, timeout=120):
        cid = uuid.uuid4().hex
        ev = threading.Event()
        self.waiting[cid] = [ev, None]
        self.q.put({"id": cid, "action": action, "params": params or {}})
        if not ev.wait(timeout):
            self.waiting.pop(cid, None)
            raise TimeoutError(f"Flow 小幫手沒有回應（{action}）。請確認 Chrome 已安裝並啟用「Flow 小幫手」。")
        res = self.waiting.pop(cid)[1]
        if "error" in res:
            raise RuntimeError(res["error"])
        return res.get("result")

    # --- 給 HTTP handler 用 ---
    def poll(self, wait=25):
        self.last_poll = time.time()
        try:
            cmd = self.q.get(timeout=wait)
        except queue.Empty:
            return {}
        self.last_poll = time.time()
        return cmd

    def deliver(self, res):
        w = self.waiting.get(res.get("id"))
        if w:
            w[1] = res
            w[0].set()


BRIDGE = Bridge()


def _port_busy(port):
    """Windows 上兩個程式可以綁同一個埠，所以啟動前先試連：連得上＝已經有一台在跑。"""
    s = socket.socket(); s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def handle(h, method, path, body):
    """回傳 True 表示已處理。給其他伺服器共用。"""
    if method == "GET" and path == "/ext/poll":
        _json(h, BRIDGE.poll())
        return True
    if method == "POST" and path == "/ext/result":
        BRIDGE.deliver(json.loads(body or b"{}"))
        _json(h, {"ok": True})
        return True
    if method == "GET" and path == "/ext/status":
        _json(h, {"connected": BRIDGE.connected})
        return True
    if method == "POST" and path == "/cmd":
        req = json.loads(body or b"{}")
        try:
            out = {"result": BRIDGE.call(req["action"], req.get("params"), req.get("timeout", 120))}
        except Exception as e:
            out = {"error": str(e)}
        _json(h, out)
        return True
    return False


def _json(h, obj, code=200):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    h.wfile.write(data)


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        if not handle(self, "GET", self.path.split("?")[0], b""):
            _json(self, {"error": "not found"}, 404)

    def do_POST(self):
        if not handle(self, "POST", self.path.split("?")[0], self._body()):
            _json(self, {"error": "not found"}, 404)


def serve(port=PORT):
    if _port_busy(port):
        print(f"Flow 橋接已經在跑（埠 {port}），不用再開。", flush=True)
        return
    ThreadingHTTPServer.allow_reuse_address = False
    srv = ThreadingHTTPServer(("127.0.0.1", port), _H)
    print(f"Flow 橋接伺服器：http://127.0.0.1:{port}  （Ctrl+C 結束）", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    serve()
