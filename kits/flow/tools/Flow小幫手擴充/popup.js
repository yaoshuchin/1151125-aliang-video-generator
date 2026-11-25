chrome.storage.local.get(['status', 'at']).then(({ status, at }) => {
  const fresh = at && Date.now() - at < 40000;
  const ok = fresh && status === '已連線';
  document.getElementById('s').className = ok ? 'ok' : '';
  document.getElementById('t').textContent = ok ? '已連線' : (status || '等待中（出片時會自動接上）');
});
