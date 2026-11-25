// Flow 小幫手：本機橋接（只連 127.0.0.1）
// 本機生成器的 flow_bridge 伺服器放指令 → 這裡取回 → 在 flow.google.com 分頁執行 → 回傳結果。
const PORTS = [8840];
let busy = false;
const attached = new Set();

chrome.alarms.create('keepalive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => loop());
chrome.runtime.onStartup.addListener(() => loop());
chrome.runtime.onInstalled.addListener(() => loop());
chrome.debugger.onDetach.addListener((src) => attached.delete(src.tabId));

async function setStatus(s) {
  try { await chrome.storage.local.set({ status: s, at: Date.now() }); } catch (e) {}
}

async function loop() {
  if (busy) return;
  busy = true;
  try {
    while (true) {
      let cmd = null;
      try {
        const r = await fetch(`http://127.0.0.1:${PORTS[0]}/ext/poll`, { cache: 'no-store' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        await setStatus('已連線');
        cmd = await r.json();
      } catch (e) {
        await setStatus('等待中（出片時會自動接上）');
        await new Promise((ok) => setTimeout(ok, 3000));
        continue;
      }
      if (!cmd || !cmd.id) continue;           // 長輪詢逾時，沒有工作
      let out;
      try { out = { id: cmd.id, result: await run(cmd) }; }
      catch (e) { out = { id: cmd.id, error: String(e && e.message || e) }; }
      try {
        await fetch(`http://127.0.0.1:${PORTS[0]}/ext/result`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(out)
        });
      } catch (e) {}
    }
  } finally { busy = false; }
}

function isFlow(url) { return /^https:\/\/(flow\.google\.com|labs\.google)\//.test(url || ''); }

async function ensureAttached(tabId) {
  if (attached.has(tabId)) return;
  const tab = await chrome.tabs.get(tabId);
  if (!isFlow(tab.url)) throw new Error('只能操作 Google Flow 的分頁');
  await chrome.debugger.attach({ tabId }, '1.3');
  attached.add(tabId);
}

async function run(cmd) {
  const p = cmd.params || {};
  switch (cmd.action) {
    case 'ping':
      return { ok: true, version: chrome.runtime.getManifest().version };
    case 'tabs': {
      const tabs = await chrome.tabs.query({});
      return tabs.filter((t) => isFlow(t.url)).map((t) => ({ id: t.id, windowId: t.windowId, url: t.url, title: t.title, active: t.active }));
    }
    case 'open': {   // 在既有 Flow 分頁所在的視窗開新分頁（視窗位置不變）
      if (!isFlow(p.url)) throw new Error('只能開 Google Flow 網址');
      const opts = { url: p.url, active: p.active !== false };
      if (p.windowId) opts.windowId = p.windowId;
      const t = await chrome.tabs.create(opts);
      return { id: t.id, windowId: t.windowId };
    }
    case 'navigate': {
      const t = await chrome.tabs.get(p.tabId);
      if (!isFlow(t.url) || !isFlow(p.url)) throw new Error('只能在 Google Flow 網址間切換');
      await chrome.tabs.update(p.tabId, { url: p.url });
      return { ok: true };
    }
    case 'close': {
      const t = await chrome.tabs.get(p.tabId);
      if (!isFlow(t.url)) throw new Error('只能關 Google Flow 分頁');
      await chrome.tabs.remove(p.tabId);
      return { ok: true };
    }
    case 'cdp': {    // 對 Flow 分頁送 Chrome 開發者協定指令（點擊、輸入、讀畫面）
      await ensureAttached(p.tabId);
      return await chrome.debugger.sendCommand({ tabId: p.tabId }, p.method, p.params || {});
    }
    case 'detach': {
      if (attached.has(p.tabId)) { await chrome.debugger.detach({ tabId: p.tabId }); attached.delete(p.tabId); }
      return { ok: true };
    }
    case 'download': {   // 用瀏覽器自己的登入狀態下載（存到「下載」資料夾底下的子資料夾）
      const id = await chrome.downloads.download({ url: p.url, filename: p.filename, conflictAction: 'uniquify', saveAs: false });
      return await waitDownload(id, p.timeoutMs || 300000);
    }
    default:
      throw new Error('不認得的指令：' + cmd.action);
  }
}

function waitDownload(id, timeoutMs) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    const tick = async () => {
      const [d] = await chrome.downloads.search({ id });
      if (!d) return reject(new Error('找不到下載項目'));
      if (d.state === 'complete') return resolve({ id, filename: d.filename, bytes: d.fileSize || d.totalBytes });
      if (d.state === 'interrupted') return reject(new Error('下載中斷：' + d.error));
      if (Date.now() - t0 > timeoutMs) return reject(new Error('下載逾時'));
      setTimeout(tick, 1000);
    };
    tick();
  });
}

loop();
