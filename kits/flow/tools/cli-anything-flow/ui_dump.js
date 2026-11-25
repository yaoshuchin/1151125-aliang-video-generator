(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2 && r.bottom > 0 && r.top < innerHeight; };
  const out = [];
  document.querySelectorAll('button,a,input,textarea,[role=button],[role=combobox],[role=option],[role=tab],[role=menuitem],[role=radio],[role=switch],[role=checkbox],[contenteditable=true],select,video').forEach((e) => {
    if (!vis(e)) return;
    const r = e.getBoundingClientRect();
    out.push({
      tag: e.tagName.toLowerCase(), role: e.getAttribute('role') || '',
      label: (e.getAttribute('aria-label') || '').slice(0, 60),
      text: (e.innerText || e.value || e.getAttribute('placeholder') || '').replace(/\s+/g, ' ').slice(0, 60),
      x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
      src: e.tagName === 'VIDEO' ? (e.currentSrc || e.src || '').slice(0, 120) : undefined,
    });
  });
  return { url: location.href, w: innerWidth, h: innerHeight, items: out };
})()
