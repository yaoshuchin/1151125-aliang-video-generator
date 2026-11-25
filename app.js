/* 影片製作包生成器 主程式（本機版會接 AI 引擎；線上版 AI 按鈕播放真實錄製的回放） */
(() => {
  const V = window.VG;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const el = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') e.className = v; else if (k === 'html') e.innerHTML = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v !== undefined && v !== null) e.setAttribute(k, v);
    }
    for (const c of kids.flat()) if (c !== null && c !== undefined) e.append(c.nodeType ? c : document.createTextNode(c));
    return e;
  };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* ---------- 狀態 ---------- */
  const KEY = 'vg-state-v1';
  let S = null, step = 1, LOCAL = false, BRIDGE = false, ENGINES = [], assets = [];
  let pickedEngine = '';
  /* ⚙ 設定（vg-settings）：底色、字體、新影片的預設路線／帳號／金鑰；只影響「新開的影片」 */
  const VERSION = 'v2026.11.13';
  const SET_KEY = 'vg-settings';
  let SET = {};
  try { SET = JSON.parse(localStorage.getItem(SET_KEY) || '{}') || {}; } catch (e) { SET = {}; }
  const saveSet = () => { try { localStorage.setItem(SET_KEY, JSON.stringify(SET)); } catch (e) {} };
  const hasDefaults = () => !!(SET.route || SET.email || SET.apiKey);
  function applyDefaults(s) {   // 只用在剛 newState 出來的影片
    if (!s || s.category === 'short') return s;
    if (SET.route) s.engine.route = SET.route;
    if (SET.email) s.engine.accounts = [{ email: SET.email, password: '' }];
    if (SET.apiKey) s.engine.apiKey = SET.apiKey;
    return s;
  }
  const fresh = cat => applyDefaults(V.newState(cat));
  try { S = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { S = null; }
  if (!S || S.version !== 1) S = fresh('promo');
  try { pickedEngine = localStorage.getItem('vg-engine') || ''; } catch (e) {}
  if (SET.engine && !pickedEngine) pickedEngine = SET.engine;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };
  const toast = (m, ms = 3200) => { const t = $('#toast'); t.textContent = m; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, ms); };
  const busy = (on, text = 'AI 生成中…', sub = '') => { $('#busy').hidden = !on; $('#busyText').textContent = text; $('#busySub').textContent = sub; };

  /* ---------- AI 引擎偵測 ---------- */
  // 2026-11-13 老師：生成器只放線上，學員電腦跑「AI 串接器」（127.0.0.1:8899），線上網頁透過它叫學員自己的 CLI；提示詞在伺服器端組（/api/gen）
  const BRIDGE_URL = 'http://127.0.0.1:8899';
  async function detectEngines() {
    LOCAL = false; BRIDGE = false; ENGINES = [];
    const onSite = /netlify\.app$/.test(location.hostname);
    if (!onSite) {
      try {
        const r = await fetch('api/engines', { cache: 'no-store' });
        if (r.ok) { ENGINES = (await r.json()).engines; LOCAL = true; }
      } catch (e) {}
    }
    if (!LOCAL) {
      try {
        const ac = new AbortController(); const tm = setTimeout(() => ac.abort(), 2500);
        const r = await fetch(BRIDGE_URL + '/engines', { cache: 'no-store', signal: ac.signal, targetAddressSpace: 'loopback' });
        clearTimeout(tm);
        if (r.ok) { const j = await r.json(); ENGINES = j.engines || []; LOCAL = true; BRIDGE = true; }
      } catch (e) {}
    }
    renderEngines();
    if (!$('#setOverlay').hidden) renderSetAI();
  }
  const DEMO_ENG = [{ id: 'claude', name: 'Claude Code', cmd: 'claude' }, { id: 'codex', name: 'Codex', cmd: 'codex' }, { id: 'agy', name: 'Antigravity', cmd: 'agy' }];
  const BRIDGE_ZIP = 'download/AI串接包.zip';
  function renderEngines() {
    const box = $('#engines'); box.innerHTML = '';
    if (!LOCAL) {
      $('#enginePill').textContent = '還沒串接 AI（✨ 播放示範）';
      $('#engineHint').textContent = '還沒接上你電腦裡的 AI：先開「AI 串接器」，再按「🔄 重新偵測」。';
      $('#engineNote').innerHTML = '要讓 ✨ 叫你電腦裡的 Claude Code／Codex／Antigravity：① 下載「AI 串接包」並解壓縮；② 對 Codex 或 Claude 說「請照 SKILL.md 幫我串接生成器」，或自己雙擊「開啟AI串接器.cmd」；③ 回到這裡按「🔄 重新偵測」，亮綠燈就接好了（Chrome 問「允許存取本機網路」請按允許）。還沒串接時按 ✨ 會播放老師實際用 AI 生成的示範；填表、下載製作包都照常能用。';
      // 2026-11-13 老師：線上版也要按得到。三張卡可以選「等一下要交給哪個 AI」（記住選擇，第四步提示要打的指令）；燈號只有本機版才偵測
      if (!DEMO_ENG.find(e => e.id === pickedEngine)) pickedEngine = 'claude';
      for (const e of DEMO_ENG) {
        box.append(el('button', { class: 'eng' + (e.id === pickedEngine ? ' on' : ''), onclick: () => { pickEngine(e.id); toast(`之後交給 AI：在製作包資料夾的終端機打 ${e.cmd}`); } },
          el('span', { class: 'dot' }),
          el('div', {}, el('b', {}, e.name), el('small', {}, '線上版不偵測燈號；終端機指令：' + e.cmd))));
      }
      box.append(el('a', { class: 'btn primary', href: BRIDGE_ZIP, download: '', style: 'align-self:center;text-decoration:none' }, '⬇ 下載 AI 串接包'),
        el('button', { class: 'btn', style: 'align-self:center', onclick: async (ev) => { ev.target.textContent = '偵測中…'; await detectEngines(); toast(BRIDGE ? '已接上你電腦裡的 AI' : '還沒偵測到 AI 串接器：先開「開啟AI串接器.cmd」'); } }, '🔄 重新偵測'));
      $('#enginePill').textContent = '還沒串接 AI｜之後交給 ' + (DEMO_ENG.find(e => e.id === pickedEngine) || DEMO_ENG[0]).name + '（三個都能選）';
      return;
    }
    const ok = ENGINES.filter(e => e.ok);
    if (!pickedEngine || !ok.find(e => e.id === pickedEngine)) pickedEngine = ok[0]?.id || '';
    for (const e of ENGINES) {
      const b = el('button', { class: 'eng' + (e.id === pickedEngine ? ' on' : ''), ...(e.ok ? {} : { disabled: '' }), onclick: () => pickEngine(e.id) },
        el('span', { class: 'dot ' + (e.ok ? 'ok' : 'no') }),
        el('div', {}, el('b', {}, e.name), el('small', {}, e.ok ? ('已安裝 ' + (e.version || '')) : '沒偵測到（U01 有安裝教學）')));
      box.append(b);
    }
    const cur = ENGINES.find(e => e.id === pickedEngine);
    $('#enginePill').textContent = cur ? ((BRIDGE ? `已串接 ${ok.length} 個 AI｜目前用 ` : 'AI 引擎：') + cur.name + (ok.length > 1 ? '（點卡片可換）' : '')) : '沒有可用的 AI 引擎（可用手動模式）';
    if (BRIDGE) box.append(el('button', { class: 'btn sm', style: 'align-self:center', onclick: async () => { await detectEngines(); toast('已重新偵測'); } }, '🔄 重新偵測'));
    $('#engineNote').textContent = ok.length ? '生成一區大約 10～60 秒（Antigravity 比較慢）。' : '目前沒有 AI 引擎，可以先用手動模式，或照 U01 安裝。';
  }

  function pickEngine(id) {
    pickedEngine = id; SET.engine = id; saveSet();
    try { localStorage.setItem('vg-engine', id); } catch (x) {}
    renderEngines();
    if (!$('#setOverlay').hidden) renderSetAI();
  }

  /* ---------- ⚙ 設定面板 ---------- */
  function applyLook() {
    const r = document.documentElement;
    if (SET.theme && SET.theme !== 'auto') r.dataset.theme = SET.theme; else delete r.dataset.theme;
    if (SET.font === 'large') r.dataset.font = 'large'; else delete r.dataset.font;
    $$('#setTheme button').forEach(b => b.classList.toggle('on', b.dataset.v === (SET.theme || 'auto')));
    $$('#setFont button').forEach(b => b.classList.toggle('on', b.dataset.v === (SET.font || 'normal')));
  }
  $$('#setTheme button').forEach(b => b.onclick = () => { SET.theme = b.dataset.v; saveSet(); applyLook(); });
  $$('#setFont button').forEach(b => b.onclick = () => { SET.font = b.dataset.v; saveSet(); applyLook(); });

  function renderSetAI() {
    const box = $('#setAIBody'); box.innerHTML = '';
    if (!LOCAL) {
      box.append(el('p', { class: 'set-note' }, '還沒串接你電腦裡的 AI。'),
        el('p', { class: 'hint' }, '照課程 U03：下載「AI 串接包」→ 解壓縮 → 對 Codex 或 Claude 說「請照 SKILL.md 幫我串接生成器」（或雙擊「開啟AI串接器.cmd」）→ 回到生成器按「🔄 重新偵測」。接好後這裡就能選預設 AI 引擎、出片路線、Google 帳號和 Gemini API 金鑰。'),
        el('a', { class: 'btn', href: BRIDGE_ZIP, download: '' }, '⬇ 下載 AI 串接包'));
      return;
    }
    const engs = el('div', { class: 'set-eng', id: 'setEngines' });
    for (const e of ENGINES) {
      engs.append(el('button', { class: 'eng' + (e.id === pickedEngine ? ' on' : ''), 'data-id': e.id, ...(e.ok ? {} : { disabled: '' }), onclick: () => pickEngine(e.id) },
        el('span', { class: 'dot ' + (e.ok ? 'ok' : 'no') }),
        el('div', {}, el('b', {}, e.name), el('small', {}, e.ok ? ('已安裝 ' + (e.version || '')) : '沒偵測到（U01 有安裝教學）'))));
    }
    const redo = el('button', { class: 'btn sm', id: 'setRedetect', onclick: async () => { redo.disabled = true; redo.textContent = '偵測中…'; await detectEngines(); toast('已重新偵測 AI 引擎'); } }, '🔄 重新偵測');
    box.append(el('div', { class: 'set-row' }, el('span', { class: 'set-lab' }, '預設 AI 引擎'), el('div', {}, engs, el('div', { style: 'margin-top:8px' }, redo))));
    const route = el('select', { id: 'setRoute' });
    [['', '不指定（照類別預設：auto）'], ['auto', 'auto：先 Flow，換帳號；全用完先問你'], ['A', 'A：只用 Google Flow'], ['B', 'B：只用 Gemini API'], ['F', 'F：FAL（付費，按秒計費）'], ['manual', 'manual：只整理提示詞，自己貼']].forEach(([v, t]) => route.append(el('option', { value: v }, t)));
    route.value = SET.route || '';
    route.onchange = () => { SET.route = route.value; saveSet(); };
    const email = el('input', { id: 'setEmail', type: 'email', placeholder: '你的帳號@gmail.com', autocomplete: 'off' });
    email.value = SET.email || ''; email.oninput = () => { SET.email = email.value.trim(); saveSet(); };
    const key = el('input', { id: 'setApiKey', type: 'password', placeholder: '選填，B 路才用得到', autocomplete: 'off' });
    key.value = SET.apiKey || ''; key.oninput = () => { SET.apiKey = key.value.trim(); saveSet(); };
    box.append(el('div', { class: 'set-row' }, el('span', { class: 'set-lab' }, '新影片出片路線'), route),
      el('div', { class: 'set-row' }, el('span', { class: 'set-lab' }, '預設 Google 帳號'), email),
      el('div', { class: 'set-row' }, el('span', { class: 'set-lab' }, 'Gemini API 金鑰'), key),
      el('p', { class: 'set-note' }, '路線、帳號、金鑰會帶進「新開的影片」的 ⑨ 生成引擎；已經在填的影片不會被改。密碼請留空：先在 Chrome 手動登入 Google Flow。'));
  }

  function openSettings() {
    applyLook(); renderSetAI();
    $('#setConfirm').hidden = true;
    $('#setVer').textContent = `影片製作包生成器 ${VERSION}（${BRIDGE ? '線上版＋AI 串接' : (LOCAL ? '本機開發版' : '線上版，尚未串接 AI')}）`;
    $('#setOverlay').hidden = false;
    $('#setClose').focus();
  }
  const closeSettings = () => { $('#setOverlay').hidden = true; $('#btnSettings').focus(); };
  $('#btnSettings').onclick = openSettings;
  $('#setClose').onclick = closeSettings; $('#setDone').onclick = closeSettings;
  $('#setOverlay').addEventListener('click', e => { if (e.target.id === 'setOverlay') closeSettings(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#setOverlay').hidden) closeSettings(); });
  $('#setClear').onclick = () => { $('#setConfirm').hidden = false; $('#setClearYes').focus(); };
  $('#setClearNo').onclick = () => { $('#setConfirm').hidden = true; };
  $('#setClearYes').onclick = () => {
    try {
      const del = [];
      for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (k === KEY || k === 'vg-tpl' || k.startsWith('vg-cat-')) del.push(k); }
      del.forEach(k => localStorage.removeItem(k));
    } catch (e) {}
    const mode = S.mode;
    S = fresh('promo'); S.mode = mode; assets = []; save();
    $('#setConfirm').hidden = true;
    renderMode(); markTpl();
    toast('已清除所有填寫內容，回到預設範例（設定保留）', 5000);
  };
  applyLook();

  /* ---------- 步驟切換 ---------- */
  function go(n) {
    step = n;
    for (let i = 1; i <= 4; i++) $('#page' + i).hidden = i !== n;
    $$('#steps li').forEach(li => { const k = +li.dataset.step; li.classList.toggle('on', k === n); li.classList.toggle('done', k < n); });
    if (n === 1) renderMode();
    if (n === 2) renderCats();
    if (n === 3) renderFill();
    if (n === 4) renderCheck();
    window.scrollTo(0, 0);
  }
  $$('#steps li').forEach(li => li.addEventListener('click', () => go(+li.dataset.step)));
  $('#to2').onclick = () => go(2); $('#back1').onclick = () => go(1);
  $('#to3').onclick = () => go(3); $('#back2').onclick = () => go(2);
  $('#to4').onclick = () => go(4); $('#back3').onclick = () => go(3);

  /* ---------- 步驟 1：模式 ---------- */
  function renderMode() {
    $$('.mode-card').forEach(c => c.classList.toggle('on', c.dataset.mode === S.mode));
    document.body.classList.toggle('manual', S.mode === 'manual');
    $('#engineBox').hidden = S.mode === 'manual';
    $('#modeToggle').textContent = S.mode === 'ai' ? '✨ AI 模式（按這裡改手動）' : '✍️ 手動模式（按這裡改 AI）';
  }
  $$('.mode-card').forEach(c => c.onclick = () => { S.mode = c.dataset.mode; save(); renderMode(); });
  $('#modeToggle').onclick = () => { S.mode = S.mode === 'ai' ? 'manual' : 'ai'; save(); renderMode(); renderFill(); };

  /* ---------- 步驟 2：類別 ---------- */
  function renderCats() {
    const box = $('#cats'); box.innerHTML = '';
    V.CATS.forEach((c, i) => {
      const card = el('button', { class: 'cat' + (c.open ? '' : ' locked') + (S.category === c.id ? ' on' : '') + (i === 0 ? ' first' : ''), ...(c.open ? {} : { disabled: '', title: '建置中，敬請期待' }) },
        el('span', { class: 'tag' }, c.open ? c.tag : '🔒 建置中，敬請期待'),
        el('div', { class: 'ic' }, c.icon), el('b', {}, c.name), c.open ? el('p', {}, c.desc) : null,
        c.id === 'manju' ? el('span', { class: 'manju-link', onclick: e => { e.stopPropagation(); window.open(manjuUrl, '_blank'); } }, '🎭 去紅果漫劇角色生成器挑角色 ↗') : null);
      if (c.open) card.onclick = () => {
        if (S.category !== c.id) {
          const keep = { mode: S.mode, engine: S.engine };
          // 每個類別各存一份：換類別前先收好目前內容，切回來就還在
          try { localStorage.setItem('vg-cat-' + S.category, JSON.stringify(S)); } catch (e) {}
          let back = null;
          try { back = JSON.parse(localStorage.getItem('vg-cat-' + c.id) || 'null'); } catch (e) { back = null; }
          const isNew = !(back && back.version === 1 && back.category === c.id);
          S = isNew ? V.newState(c.id) : back;
          S.mode = keep.mode;
          // 新開的影片：有 ⚙ 設定的預設值就用預設值，沒有就照舊沿用上一支的 ⑨；切回舊影片：保留它自己的 ⑨，不被改掉
          if (c.id !== 'short' && isNew) {
            if (hasDefaults()) applyDefaults(S);
            else S.engine = { ...keep.engine, route: keep.engine.route === 'local' ? 'auto' : keep.engine.route };
          }
          save();
          if (back) toast('已切回「' + c.name + '」，上次填的內容都還在');
        }
        renderCats();
      };
      box.append(card);
    });
    $('#shortStyles').hidden = S.category !== 'short';
    if (S.category === 'short') {
      const sb = $('#styles'); sb.innerHTML = '';
      V.SHORT_STYLES.forEach(st => sb.append(el('button', { class: 'sty' + (S.shortStyle === st.id ? ' on' : ''), onclick: () => { S.shortStyle = st.id; save(); renderCats(); } },
        el('b', {}, st.icon + ' ' + st.name), el('p', {}, st.desc),
        el('div', { class: 'need' }, st.needs.length ? ('需要：' + st.needs.join('、')) : '不需要任何帳號或金鑰'),
        el('small', { class: 'badge' }, '附技能包：' + st.skills.join('、')))));
    }
  }

  /* ---------- 步驟 3：填寫 ---------- */
  const cat = () => V.CATS.find(c => c.id === S.category);
  function field(label, obj, key, type = 'text', opts = {}) {
    const id = 'f_' + Math.random().toString(36).slice(2, 8);
    let inp;
    if (type === 'textarea') inp = el('textarea', { id, rows: opts.rows || 3, placeholder: opts.ph || '' });
    else if (type === 'select') { inp = el('select', { id }); (opts.list || []).forEach(v => inp.append(el('option', { value: v }, v))); }
    else inp = el('input', { id, type, placeholder: opts.ph || '', ...(opts.list ? { list: id + '_l' } : {}) });
    inp.value = obj[key] ?? '';
    inp.addEventListener('input', () => { obj[key] = type === 'number' ? +inp.value : inp.value; save(); markSections(); });
    inp.addEventListener('change', () => { obj[key] = type === 'number' ? +inp.value : inp.value; save(); markSections(); });
    const lab = el('label', { class: 'f' + (opts.full ? ' full' : ''), for: id }, label, inp);
    if (opts.list && type !== 'select') { const dl = el('datalist', { id: id + '_l' }); opts.list.forEach(v => dl.append(el('option', { value: v }))); lab.append(dl); }
    return lab;
  }
  // 2026-11-15 旁白／字幕語言改下拉（英文、臺語…）；舊資料「繁體中文（臺灣）」自動對到臺灣國語
  function langField(b) {
    if (!V.LANGS.includes(b.lang)) b.lang = /英/.test(b.lang || '') ? '英文' : /臺語|台語|閩南/.test(b.lang || '') ? '臺語（臺灣台語）' : V.LANGS[0];
    const lab = field('旁白／字幕／對白語言', b, 'lang', 'select', { list: V.LANGS });
    const note = el('small', { class: 'hint lang-note' }, V.LANG_NOTE[b.lang] || '');
    lab.querySelector('select').addEventListener('change', e => { note.textContent = V.LANG_NOTE[e.target.value] || ''; });
    lab.append(note); return lab;
  }
  const openSecs = new Set(['basic', 'shots']);

  function renderFill() {
    renderMode();
    const c = cat();
    const style = c.id === 'short' ? V.SHORT_STYLES.find(s => s.id === S.shortStyle) : null;
    $('#fillTitle').textContent = `${c.icon} ${c.name}${style ? '｜' + style.name : ''}：填寫內容`;
    $('#fillHint').textContent = S.mode === 'ai' ? '先填「快速開始」，再按 ✨。生成後每一欄都可以自己改；不滿意就按該區的 ✨ 重新生成。' : '手動模式：每一欄自己填。分鏡表是最重要的一區。';
    $('#q_summary').value = S.quick.summary; $('#q_keywords').value = S.quick.keywords;
    $('#q_summary').oninput = e => { S.quick.summary = e.target.value; save(); };
    $('#q_keywords').oninput = e => { S.quick.keywords = e.target.value; save(); };
    $$('#q_shots button').forEach(b => { b.classList.toggle('on', +b.dataset.v === +S.quick.shots); b.onclick = () => { S.quick.shots = +b.dataset.v; resizeShots(S.quick.shots); save(); renderFill(); }; });
    const box = $('#sections'); box.innerHTML = '';
    for (const sec of V.SECTIONS) box.append(renderSection(sec));
    markSections(); markTpl();
  }

  function resizeShots(n) {
    while (S.shots.length < n) S.shots.push(V.blankShot(S.shots.length + 1));
    if (S.shots.length > n && S.shots.slice(n).every(s => !s.visual && !s.prompt)) S.shots.length = n;
    S.shots.forEach((s, i) => s.no = i + 1);
  }

  function renderSection(sec) {
    const wrap = el('div', { class: 'sec' + (openSecs.has(sec.id) ? '' : ' closed'), id: 'sec_' + sec.id });
    const head = el('header', {}, el('b', {}, sec.no + ' ' + sec.name), el('span', { class: 'st', id: 'st_' + sec.id }));
    if (sec.ai) head.append(el('button', { class: 'btn sm ai ai-only ai-btn', onclick: ev => { ev.stopPropagation(); runAI(sec.id); } }, '✨ AI 生成' + sec.name));
    head.addEventListener('click', () => { wrap.classList.toggle('closed'); wrap.classList.contains('closed') ? openSecs.delete(sec.id) : openSecs.add(sec.id); });
    const body = el('div', { class: 'body' });
    const b = S.basic, a = S.audience, st = S.style, so = S.sound, br = S.brand, o = S.output, en = S.engine;
    switch (sec.id) {
      case 'basic':
        body.append(field('片名', b, 'title'), field('主題（一句話）', b, 'topic'), field('學校／單位', b, 'org'),
          field('片長（秒）', b, 'seconds', 'number'), field('上線平台', b, 'platform', 'text', { list: V.PLATFORMS }), langField(b));
        break;
      case 'audience':
        body.append(field('目標觀眾', a, 'target', 'text', { ph: '例：國中家長、全校教師' }), field('核心訊息（一句話）', a, 'message'),
          field('看完希望觀眾做什麼', a, 'action', 'text', { ph: '例：掃 QR 報名' }), field('三個關鍵字', a, 'keywords'), field('要避免的內容', a, 'avoid', 'text', { ph: '例：學生正臉、品牌商標' }));
        break;
      case 'style':
        body.append(field('畫風', st, 'look', 'text', { list: V.LOOKS }), field('主色調', st, 'palette', 'text', { ph: '例：暖橘＋天藍' }), field('情緒氣氛', st, 'mood'),
          field('參考影片或圖片（網址或描述）', st, 'reference'), field('一致性要求（每鏡都要一樣的東西）', st, 'consistency', 'textarea', { full: true, rows: 2 }));
        break;
      case 'shots': {
        const tw = el('div', { class: 'tbl-wrap' });
        const t = el('table', { class: 'shot-table' });
        t.append(el('tr', {}, ['#', '景別', '運鏡', '畫面描述', '角色', '動作', '秒', '轉場', '音效', '給 AI 的影片提示詞', ''].map(h => el('th', {}, h))));
        S.shots.forEach((s, i) => {
          const tr = el('tr');
          const cell = (k, type, list) => {
            let x;
            if (type === 'select') { x = el('select'); list.forEach(v => x.append(el('option', { value: v }, v))); }
            else if (type === 'ta') x = el('textarea');
            else x = el('input', { type: type || 'text' });
            x.value = s[k] ?? ''; x.oninput = () => { s[k] = type === 'number' ? +x.value : x.value; save(); markSections(); };
            return el('td', {}, x);
          };
          tr.append(el('td', {}, String(s.no)), cell('size', 'select', V.SIZES), cell('camera', 'select', V.CAMS), cell('visual', 'ta'), cell('character', 'ta'), cell('action', 'ta'),
            cell('sec', 'number'), cell('transition', 'select', V.TRANS), cell('sfx', 'ta'), cell('prompt', 'ta'),
            el('td', {}, el('button', { class: 'btn sm', title: '刪除這一鏡', onclick: () => { S.shots.splice(i, 1); S.shots.forEach((q, j) => q.no = j + 1); S.quick.shots = S.shots.length; save(); renderFill(); } }, '✕')));
          t.append(tr);
        });
        tw.append(t); body.append(tw);
        body.append(el('div', { class: 'row-tools' },
          el('button', { class: 'btn sm', onclick: () => { S.shots.push(V.blankShot(S.shots.length + 1)); S.quick.shots = S.shots.length; save(); renderFill(); } }, '＋ 加一鏡'),
          el('button', { class: 'btn sm ai ai-only', onclick: () => runAI('prompts') }, '✨ 只生成每鏡的影片提示詞'),
          el('button', { class: 'btn sm ai ai-only', title: 'Google Flow「畫面轉影片」：給第一張和最後一張畫面，AI 補中間的動作，動作和構圖最好控制', onclick: () => runAI('frames') }, '✨ 生成首尾幀圖片提示詞'),
          el('span', { class: 'hint' }, '秒數加總：', el('b', { id: 'secSum' }, ''))));
        body.append(framesBox(), hooksBox());
        break;
      }
      case 'characters': {
        { // 2026-11-15 老師：Flow 原本可以「參考我上傳的人像做角色」，入口太深學員找不到 → 放到最上面
          const pick = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', hidden: true });
          pick.onchange = e => { const file = e.target.files[0]; if (!file) return;
            const ch = { ...(V.blankChar ? V.blankChar() : {}), name: file.name.replace(/\.[^.]+$/, '').slice(0, 12) || '照片角色', sheet_source: 'upload', sheet_file: file.name,
              look: '（依照片：請填外觀，或按 ✨ AI 生成角色設定；照片會保留當參考圖）' };
            S.characters.push(ch); charFiles.set(ch, file); save(); renderFill(); toast('已用你的照片建立角色：出片時每一鏡會拿這張照片當 Flow 參考圖。記得改角色名，並在分鏡的「角色」欄寫上這個名字。', 8000); };
          body.append(el('div', { class: 'photo-char full' }, el('button', { class: 'btn primary', onclick: () => pick.click() }, '📷 用我的人像照片建立角色'), pick,
            el('span', { class: 'hint' }, '上傳一張清楚的半身或全身照，Flow 會拿它當參考圖，讓每一鏡都是同一個人。只上傳你自己或已經同意的人的照片；學生照片要有家長同意。')));
        }
        if (!S.characters.length) body.append(el('p', { class: 'hint full' }, '還沒有角色。知識短片、字卡類可以不需要角色。'));
        S.characters.forEach((ch, i) => {
          if (!ch.sheet_source) ch.sheet_source = 'codex';
          if (ch.sheet_prompt === undefined) ch.sheet_prompt = '';
          body.append(el('div', { class: 'char' }, field('角色名', ch, 'name'), field('外觀（年齡、髮型、體型）', ch, 'look'), field('服裝', ch, 'outfit'), field('個性', ch, 'personality'),
            field('一致性描述詞（每鏡都貼這段，讓人長得一樣）', ch, 'anchor', 'textarea', { full: true, rows: 2 }),
            sheetBox(ch, i),
            el('button', { class: 'btn sm', onclick: () => { charFiles.delete(ch); S.characters.splice(i, 1); save(); renderFill(); } }, '刪除這個角色')));
        });
        body.append(el('div', { class: 'row-tools' }, el('button', { class: 'btn sm', onclick: () => { S.characters.push(V.blankChar ? V.blankChar() : { name: '', look: '', outfit: '', personality: '', anchor: '', sheet_prompt: '', sheet_source: 'codex' }); save(); renderFill(); } }, '＋ 加角色')));
        if (S.characters.length && S.category !== 'short') body.append(el('p', { class: 'hint full' }, '🧍 角色設定圖＝同一個人的正面、四分之三側、全身並排的「定裝照」。出片前 AI 會先做好給你看，你說外觀 OK 才開始出片；之後每一鏡都拿它當參考，人物比較不會換臉。'));
        break;
      }
      case 'sound':
        body.append(field('旁白稿（整支片）', so, 'narration', 'textarea', { full: true, rows: 4 }), field('字幕（一行一句，空白＝用旁白）', so, 'subtitles', 'textarea', { full: true, rows: 3 }),
          field('旁白聲音', so, 'voice', 'text', { list: ['溫暖女聲', '沉穩男聲', '活潑童聲', '不要旁白'] }), field('配樂風格', so, 'music', 'text', { ph: '例：輕快木吉他、溫暖鋼琴' }),
          field('音效清單', so, 'sfx'), field('字幕樣式', so, 'subtitleStyle'));
        break;
      case 'brand':
        body.append(field('學校／單位名稱', br, 'org'), field('Logo 文字', br, 'logoText'), field('標語', br, 'slogan'), field('行動呼籲', br, 'cta', 'text', { ph: '例：立即掃碼報名' }),
          field('QR／網址', br, 'url'), field('結尾畫面秒數', br, 'endSec', 'number'));
        body.append(assetBox());
        break;
      case 'output':
        body.append(field('畫面比例', o, 'ratio', 'select', { list: ['16:9', '9:16'] }), field('試做畫質', o, 'res', 'select', { list: ['360p', '720p'] }),
          field('定稿畫質', o, 'final', 'select', { list: ['720p', '1080p'] }), field('檔名', o, 'filename'));
        body.append(el('p', { class: 'hint full' }, '建議先用 360p 試做（點數最省），滿意再用 720p 出定稿。'));
        break;
      case 'engine': {
        if (S.category === 'short') {
          const sty = V.SHORT_STYLES.find(x => x.id === S.shortStyle);
          body.append(el('p', { class: 'full' }, '⚡ 短影音用本機技能包製作，不用 Google Flow、不用點數。製作包會附上：', el('b', {}, sty.skills.join('、'))));
          if (S.shortStyle === 'stock') body.append(field('Pixabay 金鑰（選填）', en, 'pixabayKey'), field('Pexels 金鑰（選填）', en, 'pexelsKey'));
          break;
        }
        // 2026-11-13 F 路（FAL）：選了才顯示 FAL 金鑰、模型、預估費用；auto 永遠不會自己改走 FAL
        const rsel = el('select', { id: 'engRoute' });
        ROUTES.forEach(([v, t]) => rsel.append(el('option', { value: v }, t)));
        rsel.value = en.route || 'auto';
        rsel.onchange = () => { en.route = rsel.value; save(); renderFill(); setTimeout(() => { const x = $('#sec_engine'); if (x) x.classList.remove('closed'); }); };
        body.append(el('label', { class: 'f', for: 'engRoute' }, '出片路線', rsel));
        if (en.route === 'F') {
          en.falModel = en.falModel || 'kling';
          const msel = el('select', { id: 'engFalModel' });
          Object.entries(FAL_MODELS).forEach(([v, m]) => msel.append(el('option', { value: v }, m.label)));
          msel.value = en.falModel;
          const estBox = el('p', { class: 'fal-est full', id: 'falEst' });
          const upd = () => { const e = falEstimate(); estBox.innerHTML = `💰 預估 <b>US$${e.total.toFixed(2)}</b>（${e.detail}）<br><span class="hint">從你的 FAL 額度扣；實扣以 fal.ai 帳單為準。AI 出片前還會先列「要花錢，請確認」的框。</span>`; };
          msel.onchange = () => { en.falModel = msel.value; save(); upd(); markSections(); };
          body.append(el('label', { class: 'f', for: 'engFalModel' }, 'FAL 影片模型', msel));
          body.append(el('p', { class: 'hint full' }, 'F＝用 FAL（fal.ai）付費出片，按秒計費（Kling 每秒約 US$0.07、Wan 每秒約 US$0.05；一鏡只能 5 或 10 秒）。有角色的鏡頭會先用角色設定圖做出這一鏡的第一張畫面（每張約 US$0.04），再讓它動起來。不用 Google 帳號、不扣 Flow 點數。'));
          const fk = field('FAL 金鑰（只存進製作包的 帳號與金鑰.json，不要傳給別人）', en, 'falKey', 'password', { full: true, ph: '到 fal.ai 的 Keys 頁建立後貼上' });
          fk.querySelector('input').setAttribute('autocomplete', 'off');
          body.append(fk, estBox);
          upd();
          break;
        }
        body.append(field('每鏡最多花幾點（超過就停）', en, 'maxCostPerShot', 'number'));
        body.append(el('p', { class: 'hint full' }, 'auto＝先用 A 路（Google Flow，帳號點數），點數用完換下一個帳號；全部用完會先停下來問你，你確認了才改走付費的 B 路（Gemini API，要金鑰），不會自己改。A＝只用 Flow；B＝只用 API；F＝FAL 付費出片（要選了才會用，auto 不會自己改走 FAL）；manual＝AI 只整理提示詞，你自己貼進 Flow。'));
        en.accounts = en.accounts || [];
        en.accounts.forEach((ac, i) => body.append(el('div', { class: 'acc' }, field(`Google 帳號 ${i + 1}`, ac, 'email', 'email', { ph: '你的帳號@gmail.com' }), field('密碼（請留空：先在 Chrome 手動登入 Flow）', ac, 'password', 'password'),
          el('button', { class: 'btn sm', onclick: () => { en.accounts.splice(i, 1); save(); renderFill(); } }, '移除'))));
        if (en.accounts.length < 3) body.append(el('div', { class: 'row-tools' }, el('button', { class: 'btn sm', onclick: () => { en.accounts.push({ email: '', password: '' }); save(); renderFill(); } }, '＋ 加一個帳號（最多 3 個）')));
        body.append(field('Gemini API 金鑰（B 路用，選填）', en, 'apiKey', 'password', { full: true }));
        if (S.characters.some(c => c.sheet_source === 'fal')) body.append(field('FAL 金鑰（角色設定圖選 FAL 才需要；只存進 帳號與金鑰.json）', en, 'falKey', 'password', { full: true }));
        break;
      }
    }
    wrap.append(head, body);
    return wrap;
  }

  /* 2026-11-13 F 路（FAL）：路線選單、模型單價（FAL 價目查詢端點 2026-11-13 的值）、即時預估 */
  const ROUTES = [['auto', 'auto：先 Flow，換帳號；全用完先問你'], ['A', 'A：只用 Google Flow'], ['B', 'B：只用 Gemini API'], ['F', 'FAL（付費，按秒計費）'], ['manual', 'manual：只整理提示詞，自己貼']];
  const FAL_MODELS = { kling: { label: 'Kling（品質優先）', name: 'Kling', usd: 0.07 }, wan: { label: 'Wan（省錢）', name: 'Wan', usd: 0.05 } };
  const FAL_FRAME = 0.04, FAL_SHEET = 0.025;
  const nameKeys = n => { n = String(n || '').trim(); const k = new Set([n]); const m = n.match(/^(.*?)[（(](.*?)[)）]\s*$/); if (m) { k.add(m[1].trim()); k.add(m[2].trim()); } return [...k].filter(x => x.length >= 2); };
  const shotHasChar = sh => { const hay = [sh.character, sh.visual, sh.action].join(' '); return S.characters.some(c => c.name && nameKeys(c.name).some(k => hay.includes(k))); };
  function falEstimate() {
    const m = FAL_MODELS[S.engine.falModel] || FAL_MODELS.kling;
    let total = 0, sec = 0, nRef = 0;
    for (const sh of S.shots) { const b = (+sh.sec || 5) <= 7 ? 5 : 10; sec += b; const ref = shotHasChar(sh); if (ref) nRef++; total += b * m.usd + (ref ? FAL_FRAME : 0); }
    const nSheet = S.characters.filter(c => c.name && c.sheet_source === 'fal' && !charFiles.get(c)).length;
    total += nSheet * FAL_SHEET;
    const parts = [`${m.name} ${S.shots.length} 鏡、計費共 ${sec} 秒 × US$${m.usd.toFixed(2)}`];
    if (nRef) parts.push(`${nRef} 鏡有角色，首幀 ${nRef} × US$${FAL_FRAME.toFixed(2)}`);
    if (nSheet) parts.push(`角色設定圖 ${nSheet} 張 × US$${FAL_SHEET.toFixed(3)}`);
    return { total, detail: parts.join('；'), sec, model: m };
  }

  /* 2026-11-15 首尾幀（參考 ai-video-formula 方式 3）：每鏡兩張圖 p01-1（首）／p01-2（尾）＋影片提示詞 */
  const pad2 = n => String(n).padStart(2, '0');
  function framesBox() {
    const has = S.shots.some(s => s.frameFirst || s.frameLast);
    const d = el('details', { class: 'frames-box full', ...(has ? { open: '' } : {}) },
      el('summary', {}),
      el('p', { class: 'hint' }, '每一鏡先生兩張圖：首幀（動作開始前）、尾幀（動作完成後），出片時 AI 會自己在 Flow 生這兩張圖、上傳、指定首尾幀（「畫面轉影片」），人物動作和構圖最好控制，不用你手動操作。檔名規則：首幀 p01-1、尾幀 p01-2、影片片段 片段/shot_01.mp4（第 2 鏡就是 p02-1、p02-2、shot_02）。不填就照一般方式只用文字出片。'));
    // 2026-11-15 冷測：計數要即時更新（兩格都填才算一鏡）
    const sum = () => { const k = S.shots.filter(s => s.frameFirst && s.frameLast).length; d.querySelector('summary').textContent = '🖼 首尾幀模式（Flow「畫面轉影片」）' + (S.shots.some(s => s.frameFirst || s.frameLast) ? '｜已填 ' + k + '／' + S.shots.length + ' 鏡（首幀、尾幀兩格都填才算）' : '｜選用'); };
    sum();
    S.shots.forEach(s => {
      const n = pad2(s.no);
      const ta = (k, label) => { const x = el('textarea', { rows: 2, placeholder: '英文生圖提示詞（可按上面 ✨ 生成）' }); x.value = s[k] || ''; x.oninput = () => { s[k] = x.value; save(); sum(); }; return el('label', { class: 'f' }, label, x); };
      d.append(el('div', { class: 'frame-row' }, el('b', {}, '第 ' + s.no + ' 鏡'), ta('frameFirst', '首幀 p' + n + '-1'), ta('frameLast', '尾幀 p' + n + '-2')));
    });
    return d;
  }
  function hooksBox() {
    const d = el('details', { class: 'hooks-box full' }, el('summary', {}, '🪝 開場鉤子句型（第 1 鏡用；按 ✨ 生成分鏡時 AI 會自動挑一種）'),
      el('ul', { class: 'hint' }, V.HOOK_RULES.map(r => el('li', {}, r))));
    const t = el('table', { class: 'hook-table' }, el('tr', {}, ['句型', '公式', '例子', '畫面字卡'].map(h => el('th', {}, h))));
    V.HOOKS.forEach(h => t.append(el('tr', {}, h.map(c => el('td', {}, c)))));
    d.append(el('div', { class: 'tbl-wrap' }, t)); return d;
  }

  /* 2026-11-13 角色設定圖：每位角色選「用什麼產生」＋英文定裝圖提示詞＋（可選）上傳自己的照片／設定圖 → 打包進 01_人物/ */
  const SHEET_SOURCES = [
    ['codex', 'Codex 生圖（推薦，不扣 Flow 點數）'],
    ['flow', 'Google Flow 生圖（Nano Banana，出圖前會報點數）'],
    ['upload', '自己上傳照片或設定圖'],
    ['fal', 'FAL（FLUX，要自己的 FAL 金鑰，每張約 US$0.025）'],
  ];
  const SHEET_LABEL = Object.fromEntries(SHEET_SOURCES);
  const SHEET_NOTE = {
    codex: '製作包裡的 AI 會用你電腦上的 Codex 內建生圖畫一張（ChatGPT 方案內含，約 1 分鐘），畫好先給你看。',
    flow: '用 Google Flow 的圖像模型 Nano Banana 2.1 畫一張；送出前 Flow 會報點數，AI 會先跟你確認。',
    upload: '在下面選一張你自己的照片或設定圖（全身或半身、清楚、背景單純最好），會放進製作包的 01_人物 資料夾，出片時直接拿來當參考。',
    fal: '用 FAL 的 FLUX 畫（每張約 US$0.025）。要在 ⑨ 生成引擎填你自己的 FAL 金鑰，AI 會先跟你確認費用。',
  };
  const charFiles = new Map();          // 角色物件 → 使用者選的照片 File（重新整理後要重選）
  const safeName = n => String(n || '角色').trim().replace(/[\\/:*?"<>|\s]+/g, '_') || '角色';
  function sheetBox(ch, i) {
    const box = el('div', { class: 'sheet full' });
    const sel = el('select', { id: `sheet_src_${i}` });
    SHEET_SOURCES.forEach(([v, t]) => sel.append(el('option', { value: v }, t)));
    sel.value = ch.sheet_source || 'codex';
    const note = el('p', { class: 'hint' }, SHEET_NOTE[sel.value]);
    sel.onchange = () => { ch.sheet_source = sel.value; note.textContent = SHEET_NOTE[sel.value]; save(); renderFill(); };
    const fileIn = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', id: `sheet_file_${i}` });
    const f = charFiles.get(ch);
    const info = el('div', { class: 'sheet-info' });
    if (f) {
      info.append(el('img', { src: URL.createObjectURL(f), alt: '角色照片預覽', class: 'sheet-thumb' }), el('span', {}, `📎 ${f.name}（${Math.round(f.size / 1024)} KB）→ 製作包 01_人物/${safeName(ch.name)}_自備${(f.name.match(/\.[a-z0-9]+$/i) || ['.png'])[0].toLowerCase()}`),
        el('button', { class: 'btn sm', onclick: () => { charFiles.delete(ch); ch.sheet_file = ''; if (ch.sheet_source === 'upload') ch.sheet_source = 'codex'; save(); renderFill(); } }, '移除照片'));
    } else if (ch.sheet_file) {
      info.append(el('span', { class: 'warn-text' }, `⚠ 之前選過「${ch.sheet_file.split('/').pop()}」，重新整理後要再選一次才會放進製作包。`));
    }
    fileIn.onchange = e => {
      const file = e.target.files[0]; if (!file) return;
      charFiles.set(ch, file); ch.sheet_source = 'upload'; ch.sheet_file = file.name; save(); renderFill();
      toast(`已加入 ${ch.name || '這個角色'} 的照片，下載時放進 01_人物 資料夾`);
    };
    box.append(
      el('label', { class: 'f', for: `sheet_src_${i}` }, '角色設定圖用什麼產生', sel), note,
      field('角色設定圖提示詞（英文；AI 依一致性描述詞寫，產生定裝圖用）', ch, 'sheet_prompt', 'textarea', { full: true, rows: 3, ph: 'Character turnaround sheet of … front view, three-quarter view, full body … plain light gray background, no text' }),
      el('label', { class: 'f full', for: `sheet_file_${i}` }, '上傳自己的角色照片／設定圖（可選；有放就直接用，不再生成）', fileIn), info);
    return box;
  }

  /* 素材（Logo、參考圖、角色照）：拖曳或選檔，一起打包 */
  function assetBox() {
    const b = el('div', { class: 'assets' }, '把 Logo、參考圖、角色照拖到這裡，或 ', el('label', { class: 'btn sm', for: 'assetInput', tabindex: 0 }, '選擇檔案'),
      el('input', { type: 'file', id: 'assetInput', multiple: '', hidden: '', onchange: e => addAssets(e.target.files) }),
      el('div', { class: 'asset-list', id: 'assetList' }));
    b.addEventListener('dragover', e => { e.preventDefault(); b.classList.add('drag'); });
    b.addEventListener('dragleave', () => b.classList.remove('drag'));
    b.addEventListener('drop', e => { e.preventDefault(); b.classList.remove('drag'); addAssets(e.dataTransfer.files); });
    setTimeout(listAssets);
    return b;
  }
  function addAssets(files) { for (const f of files) assets.push(f); S.assets = assets.map(f => f.name); save(); listAssets(); toast(`已加入 ${files.length} 個素材，會放進製作包的「素材」資料夾`); }
  function listAssets() { const l = $('#assetList'); if (l) l.innerHTML = assets.map((f, i) => `📎 ${esc(f.name)}（${Math.round(f.size / 1024)} KB）`).join('<br>'); }

  function filled(sec) {
    const nz = v => v !== '' && v !== null && v !== undefined && !(Array.isArray(v) && !v.length);
    switch (sec) {
      case 'basic': return [S.basic.title, S.basic.topic, S.basic.seconds].filter(nz).length / 3;
      case 'audience': return Object.values(S.audience).filter(nz).length / 4;
      case 'style': return [S.style.look, S.style.palette, S.style.mood].filter(nz).length / 3;
      case 'shots': return S.shots.length ? S.shots.reduce((t, s) => t + (s.visual ? ((S.category === 'short' || s.prompt) ? 1 : 0.5) : 0), 0) / S.shots.length : 0;   // 有畫面沒提示詞＝一半
      case 'characters': return 1;   // 沒有角色的影片（字卡、知識短片）也算完成
      case 'sound': return [S.sound.narration || S.sound.subtitles, S.sound.music].filter(nz).length / 2;
      case 'brand': return [S.brand.org || S.brand.logoText, S.brand.cta].filter(nz).length / 2;
      case 'output': return 1;
      case 'engine': return S.category === 'short' ? 1 : ((S.engine.route === 'B' && !S.engine.apiKey) || (S.engine.route === 'F' && !S.engine.falKey) ? 0.5 : 1);   // A 路沒填帳號＝用 Chrome 已登入的 Flow 分頁
    }
    return 0;
  }
  function markSections() {
    const fe = $('#falEst');      // F 路：分鏡秒數、角色改了，預估費用跟著變
    if (fe && S.engine.route === 'F') { const e = falEstimate(); const b = fe.querySelector('b'); if (b) b.textContent = `US$${e.total.toFixed(2)}`; const t = fe.firstChild; if (t && t.nextSibling && t.nextSibling.nextSibling) t.nextSibling.nextSibling.textContent = `（${e.detail}）`; }
    for (const sec of V.SECTIONS) {
      const f = filled(sec.id), st = $('#st_' + sec.id); if (!st) continue;
      st.textContent = (sec.id === 'characters' && !S.characters.length) ? '沒有角色（可留白）' : f >= 1 ? '✅ 完成' : f > 0 ? `填了 ${Math.round(f * 100)}%` : '尚未填寫';
      st.className = 'st' + (f >= 1 ? ' full' : '');
    }
    const sum = S.shots.reduce((t, s) => t + (+s.sec || 0), 0);
    const ss = $('#secSum'); if (ss) { const off = Math.abs(sum - S.basic.seconds) > 2; ss.textContent = `${sum} 秒（目標 ${S.basic.seconds} 秒）` + (off ? '　⚠ 對不上：改某一鏡的秒數，或改 ① 基本資料的片長' : '　✓'); ss.style.color = off ? '#d9480f' : ''; }
  }

  /* ---------- AI 生成 ---------- */
  const TASK_NAME = { audience: '觀眾與訊息', style: '風格美術', shots: '腳本與分鏡', characters: '角色設定', sound: '旁白、字幕、配樂', brand: '品牌結尾', prompts: '每鏡影片提示詞', frames: '首尾幀圖片提示詞', all: '全部內容' };
  async function runAI(task) {
    if (!S.quick.summary.trim() && !S.basic.topic.trim()) { toast('先在「快速開始」寫一句故事摘要或主題'); return; }
    if (!LOCAL) return playReplay(task);
    if (!pickedEngine) { toast('沒有可用的 AI 引擎，請改用手動模式，或照 U01 安裝'); return; }
    const order = task === 'all' ? ['audience', 'style', 'shots', 'characters', 'prompts', 'sound', 'brand'] : [task];
    // 2026-11-13 修正：新影片預填的是範例（例如期末成果展）；學員改了故事摘要但沒改片名、主題，就清掉範例值，避免 AI 照範例寫
    const ex = V.EXAMPLES[S.category] || {};
    if (ex.summary && S.quick.summary.trim() !== ex.summary) {
      if (S.basic.topic === ex.topic) S.basic.topic = '';
      if (S.basic.title === ex.title) { S.basic.title = ''; if (S.output.filename === (ex.title || '影片') + '.mp4') S.output.filename = ''; }
      if (S.quick.keywords === ex.keywords) S.quick.keywords = '';
      save();
    }
    for (let i = 0; i < order.length; i++) {
      const t = order[i];
      busy(true, `✨ ${ENGINES.find(e => e.id === pickedEngine).name} 正在生成「${TASK_NAME[t]}」…`, order.length > 1 ? `第 ${i + 1}／${order.length} 區` : '大約 10～60 秒');
      const t0 = Date.now();
      try {
        const j = BRIDGE ? await bridgeAI(t) : await (await fetch('api/ai', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine: pickedEngine, task: t, state: S }) })).json();
        if (j.error) throw new Error(j.error);
        applyPatch(t, j.patch);
        openSecs.add(t === 'prompts' || t === 'frames' ? 'shots' : t); save(); renderFill();   // 先記展開再重畫，生成完那一區直接打開
        toast(`「${TASK_NAME[t]}」生成完成（${Math.round((Date.now() - t0) / 1000)} 秒）`);
      } catch (e) {
        busy(false); toast('生成失敗：' + e.message, 8000); return;
      }
    }
    busy(false); renderFill();
  }
  // 線上版＋AI 串接器：伺服器組提示詞 → 學員電腦的串接器叫 CLI → 伺服器整理回答
  async function bridgeAI(t) {
    const post = (u, b, extra) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b), ...(extra || {}) }).then(r => r.json());
    const b = await post('/api/gen', { op: 'build', task: t, state: S });
    if (b.error) return b;
    let run;
    try { run = await post(BRIDGE_URL + '/run', { engine: pickedEngine, prompt: b.prompt, schema: b.schema }, { targetAddressSpace: 'loopback' }); }
    catch (e) { return { error: 'AI 串接器沒有回應：確認「AI 串接器」黑色視窗還開著，再按 🔄 重新偵測' }; }
    if (run.error) return run;
    return post('/api/gen', { op: 'finish', task: t, raw: run.raw, state: S });
  }
  function applyPatch(task, p) {
    if (!p) return;
    if (task === 'shots' && Array.isArray(p.shots)) {
      S.shots = p.shots.map((s, i) => ({ ...V.blankShot(i + 1), ...s, no: i + 1, prompt: S.shots[i]?.prompt || '' }));
      S.quick.shots = S.shots.length;
      if (p.title) { S.basic.title = p.title; if (!S.output.filename) S.output.filename = p.title + '.mp4'; }
    } else if (task === 'frames' && Array.isArray(p.frames)) {
      p.frames.forEach((f, i) => { if (S.shots[i] && f) { S.shots[i].frameFirst = f.first || ''; S.shots[i].frameLast = f.last || ''; } });
    } else if (task === 'prompts' && Array.isArray(p.prompts)) {
      p.prompts.forEach((pr, i) => { if (S.shots[i]) S.shots[i].prompt = pr; });
    } else if (task === 'characters' && Array.isArray(p.characters)) {
      // 2026-11-13 保留使用者已選的設定圖來源與照片（依角色名對回，名字對不上就依順序）
      const old = S.characters || [];
      S.characters = p.characters.map((c, i) => {
        const o = old.find(x => x.name && x.name === c.name) || old[i];
        const n = { sheet_prompt: '', ...c, sheet_source: (o && o.sheet_source) || 'codex', sheet_file: (o && o.sheet_file) || '' };
        if (o && charFiles.has(o)) { charFiles.set(n, charFiles.get(o)); charFiles.delete(o); }
        return n;
      });
    } else if (S[task] && typeof p === 'object') {
      Object.assign(S[task], p);
    }
  }
  $('#aiAll').onclick = () => runAI('all');

  /* 線上展示版：播放真實錄製的生成結果 */
  async function playReplay(task) {
    try {
      let rep = null;
      if (window.PRELOADED_REPLAYS && window.PRELOADED_REPLAYS[S.category]) {
        rep = window.PRELOADED_REPLAYS[S.category];
      } else {
        try {
          const r = await fetch('replays/' + S.category + '.json', { cache: 'no-store' });
          if (r.ok) rep = await r.json();
        } catch (_) {}
        if (!rep) {
          const r2 = await fetch('https://video-generator-aliang.netlify.app/replays/' + S.category + '.json', { cache: 'no-store' });
          rep = await r2.json();
        }
      }
      // 2026-11-13 修正：學員已經寫了自己的題目，示範回放不可以蓋掉（之前會整個換成範例「期末成果展」）
      const mine = (S.quick.summary || '').trim(), demo = ((rep.quick && rep.quick.summary) || (V.EXAMPLES[S.category] || {}).summary || '').trim();
      if (mine && mine !== demo) {
        toast('還沒串接 AI，所以不能用你的題目生成（你寫的內容都還在，沒有被改）。請先下載「AI 串接包」接上你電腦的 AI，回第一步按 🔄 重新偵測，再按 ✨。', 10000);
        go(1); return;
      }
      const order = task === 'all' ? ['audience', 'style', 'shots', 'characters', 'prompts', 'sound', 'brand'] : [task];
      for (const t of order) {
        const rec = rep.tasks[t]; if (!rec) continue;
        busy(true, `▶ 回放：${rep.engine} 生成「${TASK_NAME[t]}」`, `實際花了 ${rec.seconds} 秒（${rep.date} 錄製）`);
        await new Promise(ok => setTimeout(ok, 1200));
        applyPatch(t, rec.patch);
      }
      if (task === 'all' || task === 'shots') { S.quick = { ...S.quick, ...rep.quick }; }
      save(); busy(false); renderFill();
      toast('這是示範回放。要用你的題目真的生成：下載「AI 串接包」接上你電腦的 AI，再按 🔄 重新偵測。', 7000);
    } catch (e) { busy(false); toast('線上展示版沒有這一類的回放'); }
  }

  /* ---------- Excel 範本 ---------- */
  let XL;
  async function loadXlsx() {
    if (window.XLSX) return window.XLSX;
    XL = XL || new Promise((ok, no) => { const s = el('script', { src: 'lib/xlsx.full.min.js' }); s.onload = () => ok(window.XLSX); s.onerror = () => { XL = null; no(new Error('Excel 元件載入失敗')); }; document.head.append(s); });
    return XL;
  }
  const KV = [['basic', 'title', '片名'], ['basic', 'topic', '主題'], ['basic', 'org', '學校／單位'], ['basic', 'seconds', '片長（秒）'], ['basic', 'platform', '上線平台'],
    ['quick', 'summary', '故事摘要'], ['quick', 'keywords', '關鍵字'],
    ['audience', 'target', '目標觀眾'], ['audience', 'message', '核心訊息'], ['audience', 'action', '看完要做什麼'], ['audience', 'keywords', '三個關鍵字'], ['audience', 'avoid', '要避免的內容'],
    ['style', 'look', '畫風'], ['style', 'palette', '主色調'], ['style', 'mood', '情緒氣氛'], ['style', 'reference', '參考'], ['style', 'consistency', '一致性要求'],
    ['sound', 'narration', '旁白稿'], ['sound', 'subtitles', '字幕'], ['sound', 'voice', '旁白聲音'], ['sound', 'music', '配樂風格'], ['sound', 'sfx', '音效'],
    ['brand', 'org', '結尾單位名稱'], ['brand', 'logoText', 'Logo 文字'], ['brand', 'slogan', '標語'], ['brand', 'cta', '行動呼籲'], ['brand', 'url', 'QR／網址'],
    ['output', 'ratio', '畫面比例'], ['output', 'res', '試做畫質'], ['output', 'filename', '檔名']];
  const SHOT_COLS = [['no', '鏡號'], ['size', '景別'], ['camera', '運鏡'], ['visual', '畫面描述'], ['character', '角色'], ['action', '動作'], ['sec', '秒數'], ['transition', '轉場'], ['sfx', '音效'], ['prompt', '影片提示詞']];
  const CHAR_COLS = [['name', '角色名'], ['look', '外觀'], ['outfit', '服裝'], ['personality', '個性'], ['anchor', '一致性描述詞'], ['sheet_prompt', '角色設定圖提示詞'], ['sheet_source', '設定圖來源']];
  const srcLabel = v => ({ codex: 'Codex 生圖', flow: 'Google Flow 生圖', upload: '自己上傳', fal: 'FAL' }[v] || v || 'Codex 生圖');
  const srcValue = t => { t = String(t || '').trim(); if (/flow/i.test(t)) return 'flow'; if (/fal/i.test(t)) return 'fal'; if (/上傳|upload/i.test(t)) return 'upload'; return 'codex'; };
  const GUIDE = [['影片製作包生成器｜Excel 填寫說明'], [''], ['1. 「基本資料」工作表：B 欄填內容，A 欄名稱不要改。'], ['2. 「分鏡表」：一列一鏡，4～6 鏡最剛好；標「（範例）」的列不會匯入。'],
    ['3. 「角色」：沒有角色可以留白。最後兩欄：「角色設定圖提示詞」寫英文，可留白，上傳後在生成器按 ✨ 補；「設定圖來源」可填 Codex、Flow 或 FAL，留白＝Codex 生圖。'], ['   要用自己的照片當角色設定圖：上傳 Excel 後，到生成器「⑤ 角色設定」按「選擇檔案」。'], ['4. 填好存檔，回到生成器按「③ 上傳填好的 Excel」。'], ['5. 上傳後，空白的欄位還是可以按 ✨ 讓 AI 補。']];
  function markTpl() { let d = false; try { d = localStorage.getItem('vg-tpl') === '1'; } catch (e) {} $('#xl1').classList.toggle('done', d); }
  $('#btnTpl').onclick = async () => {
    try {
      const X = await loadXlsx(); const wb = X.utils.book_new();
      const kv = [['欄位', '內容'], ...KV.map(([g, k, n]) => [n, S[g][k] ?? ''])];
      const s1 = X.utils.aoa_to_sheet(kv); s1['!cols'] = [{ wch: 16 }, { wch: 80 }]; X.utils.book_append_sheet(wb, s1, '基本資料');
      const shots = [SHOT_COLS.map(c => c[1]), ...(S.shots.some(s => s.visual) ? S.shots.map(s => SHOT_COLS.map(c => s[c[0]] ?? '')) : [['（範例）1', '遠景', '緩慢推近', '清晨校門口，陽光灑落', '', '學生陸續走進校門', 5, '淡入淡出', '鳥叫聲', '']])];
      const s2 = X.utils.aoa_to_sheet(shots); s2['!cols'] = SHOT_COLS.map((c, i) => ({ wch: [6, 8, 10, 36, 16, 20, 6, 10, 14, 50][i] })); X.utils.book_append_sheet(wb, s2, '分鏡表');
      const chars = [CHAR_COLS.map(c => c[1]), ...S.characters.map(ch => CHAR_COLS.map(c => c[0] === 'sheet_source' ? srcLabel(ch.sheet_source) : (ch[c[0]] ?? '')))];
      const s3 = X.utils.aoa_to_sheet(chars); s3['!cols'] = [{ wch: 12 }, { wch: 30 }, { wch: 24 }, { wch: 16 }, { wch: 60 }, { wch: 60 }, { wch: 16 }]; X.utils.book_append_sheet(wb, s3, '角色');
      const g = X.utils.aoa_to_sheet(GUIDE); g['!cols'] = [{ wch: 80 }]; X.utils.book_append_sheet(wb, g, '填寫說明');
      X.writeFile(wb, `影片製作包_${cat().name}_範本.xlsx`);
      try { localStorage.setItem('vg-tpl', '1'); } catch (e) {} markTpl();
      toast('① 範本已下載。② 用 Excel 填好存檔 → ③ 按「上傳填好的 Excel」');
    } catch (e) { toast(e.message); }
  };
  $('#xlInput').onchange = async e => {
    const f = e.target.files[0]; e.target.value = ''; if (!f) return;
    try {
      const X = await loadXlsx(); const wb = X.read(await f.arrayBuffer());
      const rows = n => wb.Sheets[n] ? X.utils.sheet_to_json(wb.Sheets[n], { header: 1, defval: '' }) : [];
      let nKV = 0;
      for (const r of rows('基本資料').slice(1)) { const d = KV.find(x => x[2] === String(r[0]).trim()); if (d && String(r[1]).trim()) { S[d[0]][d[1]] = d[1] === 'seconds' ? +r[1] : String(r[1]); nKV++; } }
      const sr = rows('分鏡表').slice(1).filter(r => r.some(c => String(c).trim()) && !String(r[0]).includes('範例'));
      if (sr.length) S.shots = sr.map((r, i) => { const s = V.blankShot(i + 1); SHOT_COLS.forEach(([k], j) => { if (k !== 'no' && r[j] !== '') s[k] = k === 'sec' ? +r[j] : String(r[j]); }); return s; });
      const cr = rows('角色').slice(1).filter(r => r.some(c => String(c).trim()));
      if (cr.length) S.characters = cr.map(r => { const c = Object.fromEntries(CHAR_COLS.map(([k], j) => [k, String(r[j] ?? '')])); c.sheet_source = srcValue(c.sheet_source); return c; });
      S.quick.shots = S.shots.length; save(); renderFill();
      toast(`已匯入：基本資料 ${nKV} 欄、分鏡 ${sr.length} 鏡、角色 ${cr.length} 位`);
    } catch (err) { toast('讀不到這個 Excel：' + err.message, 6000); }
  };

  /* ---------- 步驟 4：檢查與下載 ---------- */
  function checks() {
    const c = [];
    const add = (lvl, t) => c.push([lvl, t]);
    add(S.basic.title ? 'ok' : 'bad', S.basic.title ? `片名：${S.basic.title}` : '還沒有片名');
    const nVis = S.shots.filter(s => s.visual).length;
    add(nVis === S.shots.length && nVis ? 'ok' : 'bad', `分鏡：${nVis}／${S.shots.length} 鏡有畫面描述`);
    if (S.category !== 'short') { const np = S.shots.filter(s => s.prompt).length; add(np === S.shots.length ? 'ok' : 'warn', `影片提示詞：${np}／${S.shots.length} 鏡（沒寫的 AI 會在出片時補）`); }
    const sum = S.shots.reduce((t, s) => t + (+s.sec || 0), 0);
    add(Math.abs(sum - S.basic.seconds) <= 3 ? 'ok' : 'warn', `秒數加總 ${sum} 秒，目標 ${S.basic.seconds} 秒`);
    add(S.sound.narration || S.sound.subtitles ? 'ok' : 'warn', S.sound.narration || S.sound.subtitles ? '有旁白或字幕' : '沒有旁白也沒有字幕（可以，但建議至少有字幕）');
    if (S.category !== 'short') {
      const r = S.engine.route;
      if (r === 'A' || r === 'auto') add(S.engine.accounts.some(a => a.email) ? 'ok' : 'warn', S.engine.accounts.some(a => a.email) ? `Google 帳號 ${S.engine.accounts.filter(a => a.email).length} 個` : '沒填 Google 帳號：AI 會用 Chrome 裡已登入的 Flow 分頁');
      if (r === 'B' || r === 'auto') add(S.engine.apiKey ? 'ok' : (r === 'B' ? 'bad' : 'warn'), S.engine.apiKey ? '有 Gemini API 金鑰（B 路可用）' : 'B 路沒有金鑰（Flow 點數用完就會停）');
      if (r === 'F') {
        add(S.engine.falKey ? 'ok' : 'bad', S.engine.falKey ? '有 FAL 金鑰（F 路，付費）' : '沒有 FAL 金鑰：回 ⑨ 生成引擎貼上（U10B）');
        const e = falEstimate();
        add('warn', `預估 US$${e.total.toFixed(2)}（${e.detail}；從你的 FAL 額度扣，出片前 AI 會再問你）`);
      }
      const named = S.characters.filter(c => c.name);
      if (named.length) {
        const parts = named.map(c => `${c.name}：${c.sheet_source === 'upload' ? (charFiles.get(c) ? '自己上傳的照片' : '選了自己上傳但還沒選照片') : srcLabel(c.sheet_source)}`);
        const missing = named.filter(c => c.sheet_source === 'upload' && !charFiles.get(c));
        add(missing.length ? 'bad' : 'ok', `角色設定圖（出片前先做好給你看）：${parts.join('、')}`);
        const costs = [];
        if (named.some(c => c.sheet_source === 'codex')) costs.push('Codex 不扣 Flow 點數（用 ChatGPT 方案額度）');
        if (named.some(c => c.sheet_source === 'flow')) costs.push('Flow 生圖預估 0 點（Nano Banana 2.1；出圖前會再確認）');
        if (named.some(c => c.sheet_source === 'fal')) costs.push(S.engine.falKey ? 'FAL 每張約 US$0.025' : 'FAL 還沒填金鑰（⑨ 生成引擎）');
        if (costs.length) add(named.some(c => c.sheet_source === 'fal') && !S.engine.falKey ? 'warn' : 'ok', '設定圖花費：' + costs.join('；'));
      }
      const flowShots = S.shots.length, est = flowShots * (S.output.res === '360p' ? 5 : 15);
      if (r !== 'F') add('warn', `預估 Flow 點數：每鏡約 ${S.output.res === '360p' ? '5' : '15～30'} 點，共約 ${est} 點以上（免費帳號每天 50 點）`);
    } else {
      const st = V.SHORT_STYLES.find(x => x.id === S.shortStyle);
      add('ok', `短影音風格：${st.name}（附技能包 ${st.skills.join('、')}）`);
      if (st.needs.length) add('warn', '這個風格需要：' + st.needs.join('、'));
    }
    return c;
  }
  function renderCheck() {
    $('#checks').innerHTML = checks().map(([l, t]) => `<li class="${l}">${esc(t)}</li>`).join('');
    $('#pkgList').innerHTML = pkgPlan().map(p => `<li>${esc(p)}</li>`).join('');
    $('#oneLine').textContent = oneLine();
    $('#dlHint').textContent = LOCAL ? '' : '線上展示版也能下載完整製作包。';
  }
  // 2026-11-13 小白試讀：Flow 類別第一句只做檢查、列提示詞，不直接出片（和製作包 帶做提示詞.txt 第 1 步一致）；短影音照舊
  const ONE_LINE_SHORT = '請先讀這個資料夾的「先讀我.md」和 SKILL.md，完全照裡面的步驟，幫我把這支影片做出來。每完成一鏡就用白話跟我回報。';
  const ONE_LINE_FLOW = '請先讀這個資料夾的「先讀我.md」和 SKILL.md，先做準備就好：檢查環境，告訴我用哪個 Google 帳號、今天剩幾點、每鏡大約幾點，再把每一鏡要送給 Flow 的提示詞列給我看；有角色的話，也告訴我角色設定圖要用什麼產生、大約花多少。先不要出片，等我說「開始出片」再開始。';
  const ONE_LINE_FAL = '請先讀這個資料夾的「先讀我.md」和 SKILL.md，先做準備就好：先幫我做出片前檢查，告訴我 FAL 金鑰能不能用、用哪個模型、每鏡幾秒、預估要花多少美元，再把每一鏡的提示詞列給我看；有角色的話，也告訴我角色設定圖要怎麼做、大約花多少。先不要出片，等我說「開始出片」再開始。';
  const oneLine = () => (S.category === 'short' ? ONE_LINE_SHORT : (S.engine.route === 'F' ? ONE_LINE_FAL : ONE_LINE_FLOW));
  $('#copyLine').onclick = () => { navigator.clipboard.writeText(oneLine()).then(() => toast('已複製'), () => toast('請手動選取複製')); };

  let KITS = null;
  async function kits() { if (!KITS) KITS = await (await fetch('kits/manifest.json', { cache: 'no-store' })).json(); return KITS; }
  // 2026-11-13 類別技能包：依類別（短影音再依風格）決定附哪些技能；清單來自 kits/manifest.json（build_kits.py 產生）
  const kitKey = () => (S.category === 'short' ? 'style:' + S.shortStyle : 'cat:' + S.category);
  function kitSkills() {
    if (!KITS || !KITS.kits) return null;
    return (KITS.kits[kitKey()] || []).map(k => Object.assign({ name: k.name, when: k.when }, KITS.info[k.name] || {}));
  }
  function skillsTableMd(list) {
    if (!list || !list.length) return '（這個類別沒有附額外技能，照下面的流程做即可。）';
    let m = '| 技能（資料夾） | 用途 | 什麼時候用 |\n|---|---|---|\n';
    for (const k of list) m += `| \`skills/${k.name}/\` | ${k.use || ''} | ${k.when || ''} |\n`;
    m += `\n詳細步驟（每支技能用在哪一步、產出放哪裡）見 \`skills/${S.category === 'short' ? '風格說明' : '技能說明'}.md\`。`;
    return m;
  }
  function pkgPlan() {
    const p = ['先讀我.md', 'SKILL.md（做事規範，含「這個製作包附的技能」清單、點數確認門禁、成片驗收報告）', 'CLAUDE.md／AGENTS.md／GEMINI.md（讓三種 AI 都會先讀 SKILL.md）', '影片需求.json（你填的全部內容）', '分鏡表.md（好讀版）', '帶做提示詞.txt', 'tools/make_final.py（接成一支片、加片頭片尾、字幕、配樂）'];
    if (S.category !== 'short' && S.characters.some(c => c.name)) p.push('tools/char_sheet.py（角色設定圖：產生→給你看→你說 OK 才出片）');
    if (S.characters.some(c => charFiles.get(c))) p.push(`01_人物/（你上傳的角色照片 ${S.characters.filter(c => charFiles.get(c)).length} 張）`);
    if (S.category !== 'short' && S.engine.route === 'F') p.push('tools/fal_api.py（F 路：FAL 付費出片，按秒計費）');
    if (S.category !== 'short') p.push('tools/cli-anything-flow/（A 路：操作 Google Flow）', 'tools/Flow小幫手擴充/（A 路要裝一次）', 'tools/gemini-omni-flash-api/（B 路：官方 API，Apache-2.0）', '帳號與金鑰.json（你填的帳號、密碼、金鑰，不要外傳）');
    const ks = kitSkills();
    if (ks) {
      const mb = ks.reduce((a, k) => a + (k.mb || 0), 0);
      p.push(`skills/${S.category === 'short' ? '風格說明' : '技能說明'}.md（附的技能怎麼搭配使用）`);
      p.push(`附的技能 ${ks.length} 支（約 ${mb.toFixed(1)} MB）：`);
      ks.forEach(k => p.push(`　・${k.name}：${k.use}`));
    } else if (S.category === 'short') p.push(`skills/風格說明.md＋技能包（${V.SHORT_STYLES.find(x => x.id === S.shortStyle).skills.join('、')}）`);
    else p.push(`skills/技能說明.md＋技能包（${(cat().skills || []).join('、')}）`);
    if (assets.length) p.push(`素材/（${assets.length} 個檔案）`);
    return p;
  }
  kits().then(() => { if (step === 4) renderCheck(); }).catch(() => {});

  function shotsMd() {
    let m = `# ${S.basic.title}｜分鏡表\n\n- 類別：${cat().name}${S.category === 'short' ? '｜' + V.SHORT_STYLES.find(x => x.id === S.shortStyle).name : ''}\n- 片長：${S.basic.seconds} 秒｜比例 ${S.output.ratio}｜試做 ${S.output.res}\n- 畫風：${S.style.look}｜色調：${S.style.palette}｜氣氛：${S.style.mood}\n\n`;
    m += '| 鏡 | 景別 | 運鏡 | 畫面 | 角色 | 動作 | 秒 | 轉場 | 音效 |\n|---|---|---|---|---|---|---|---|---|\n';
    for (const s of S.shots) m += `| ${s.no} | ${s.size} | ${s.camera} | ${s.visual} | ${s.character} | ${s.action} | ${s.sec} | ${s.transition} | ${s.sfx} |\n`;
    if (S.category !== 'short') { m += '\n## 每鏡影片提示詞\n\n'; for (const s of S.shots) m += `### 第 ${s.no} 鏡\n${s.prompt || '（出片時由 AI 依畫面描述補寫）'}\n\n`; }
    if (S.shots.some(s => s.frameFirst || s.frameLast)) {   // 2026-11-15 首尾幀
      m += '\n## 首尾幀圖片提示詞（Google Flow「畫面轉影片」）\n\n跟 AI 說「出片」就好：AI 會先用 Flow 生首幀、尾幀（0 點，存進「首尾幀/」；想先看圖就跑 python tools/flow_run.py --frames-only），再自己上傳兩張圖、指定首幀和尾幀出片，片段照舊命名 片段/shot_01.mp4…。自己畫的圖照檔名放進「首尾幀/」就會直接用。\n\n';
      for (const s of S.shots) m += '### 第 ' + s.no + ' 鏡\n- 首幀 首尾幀/p' + pad2(s.no) + '-1.png：' + (s.frameFirst || '（未填）') + '\n- 尾幀 首尾幀/p' + pad2(s.no) + '-2.png：' + (s.frameLast || '（未填）') + '\n- 影片 片段/shot_' + pad2(s.no) + '.mp4\n\n';
    }
    if (S.characters.length) {
      m += '## 角色\n\n';
      for (const c of S.characters) {
        m += `- **${c.name}**：${c.look}；${c.outfit}；${c.personality}\n  - 一致性描述詞：${c.anchor}\n`;
        if (S.category !== 'short') m += `  - 角色設定圖：${srcLabel(c.sheet_source)}${c.sheet_file ? '（' + c.sheet_file + '）' : ''}\n  - 設定圖提示詞：${c.sheet_prompt || '（AI 依一致性描述詞自動寫）'}\n`;
      }
    }
    m += `\n## 聲音\n- 語言：${S.basic.lang || '繁體中文（臺灣國語）'}（${V.LANG_NOTE[S.basic.lang] || ''}）\n- 旁白聲音：${S.sound.voice || '溫暖女聲'}\n- 旁白：${S.sound.narration}\n- 字幕：${S.sound.subtitles || '（同旁白）'}\n- 配樂：${S.sound.music}｜音效：${S.sound.sfx}\n\n## 結尾\n- ${S.brand.org} ${S.brand.logoText}｜${S.brand.slogan}｜${S.brand.cta}｜${S.brand.url}\n`;
    return m;
  }

  $('#btnDownload').onclick = async () => {
    if (!window.JSZip) { toast('壓縮元件載入失敗'); return; }
    busy(true, '正在打包製作包…', '');
    try {
      const K = await kits();
      const z = new JSZip();
      const folder = (S.basic.title || '影片').replace(/[\\/:*?"<>|]/g, '_') + '_製作包';
      const root = z.folder(folder);
      const route = S.category === 'short' ? 'local' : S.engine.route;
      const need = new Set(K.common);
      if (S.category !== 'short') K.flow.forEach(x => need.add(x));
      const key = kitKey();
      if (!K.kits || !K.kits[key]) throw new Error('製作包清單沒有這個類別：' + key);
      (K.guides[key] || []).forEach(x => need.add(x));
      for (const k of K.kits[key]) (K.skills[k.name] || []).forEach(x => need.add(x));
      const table = skillsTableMd(kitSkills());
      let n = 0;
      const paths = [...need];
      const one = async path => {
        let r = null;
        try {
          r = await fetch('kits/' + path.split('/').map(encodeURIComponent).join('/'));
        } catch (_) {}
        if (!r || !r.ok) {
          try {
            r = await fetch('https://video-generator-aliang.netlify.app/kits/' + path.split('/').map(encodeURIComponent).join('/'));
          } catch (_) {}
        }
        if (!r || !r.ok) throw new Error('缺少檔案 ' + path);
        const out = path.replace(/^common\//, '').replace(/^flow\//, '').replace(/^(style|cat)_[a-z]+\//, '');
        if (out === 'SKILL.md') root.file(out, (await r.text()).replace('<!--SKILLS_TABLE-->', table));
        else root.file(out, await r.arrayBuffer());
        n++;
        if (n % 20 === 0) $('#busySub').textContent = `已放入 ${n}／${paths.length} 個檔案`;
      };
      for (let i = 0; i < paths.length; i += 8) await Promise.all(paths.slice(i, i + 8).map(one));
      const pub = JSON.parse(JSON.stringify(S));
      const secret = { accounts: (S.engine.accounts || []).filter(a => a.email), apiKey: S.engine.apiKey || '', pixabayKey: S.engine.pixabayKey || '', pexelsKey: S.engine.pexelsKey || '' };
      if (S.engine.falKey) secret.falKey = S.engine.falKey;
      delete pub.engine.accounts; delete pub.engine.apiKey; delete pub.engine.pixabayKey; delete pub.engine.pexelsKey; delete pub.engine.falKey;
      // 2026-11-13 角色設定圖：使用者上傳的照片放 01_人物/，影片需求.json 記 sheet_file
      (pub.characters || []).forEach((c, i) => {
        const f = charFiles.get(S.characters[i]);
        if (f) {
          const ext = ((f.name.match(/\.[a-z0-9]+$/i) || ['.png'])[0]).toLowerCase();
          c.sheet_file = `01_人物/${safeName(c.name)}_自備${ext}`; c.sheet_source = 'upload';
          root.file(c.sheet_file, f);
        } else c.sheet_file = '';
        if (!c.sheet_source) c.sheet_source = 'codex';
        if (c.sheet_prompt === undefined) c.sheet_prompt = '';
      });
      pub.categoryName = cat().name; pub.route = route; pub.generatedAt = new Date().toISOString();
      if (S.category === 'short') pub.shortStyleInfo = V.SHORT_STYLES.find(x => x.id === S.shortStyle);
      root.file('影片需求.json', JSON.stringify(pub, null, 2));
      root.file('分鏡表.md', shotsMd());
      root.file('開場鉤子句型表.md', '# 開場鉤子句型表（第 1 鏡用）\n\n' + V.HOOK_RULES.map(r => '- ' + r).join('\n') + '\n\n| 句型 | 公式 | 例子 | 畫面字卡 |\n|---|---|---|---|\n' + V.HOOKS.map(h => '| ' + h.join(' | ') + ' |').join('\n') + '\n');
      if (S.category !== 'short') root.file('帳號與金鑰.json', JSON.stringify(secret, null, 2));
      else if (secret.pixabayKey || secret.pexelsKey) root.file('帳號與金鑰.json', JSON.stringify(secret, null, 2));
      for (const f of assets) root.file('素材/' + f.name, f);
      const blob = await z.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } },m => $('#busySub').textContent = `壓縮中 ${Math.round(m.percent)}%`);
      const a = el('a', { href: URL.createObjectURL(blob), download: folder + '.zip' }); document.body.append(a); a.click(); a.remove();
      busy(false); toast(`已下載「${folder}.zip」（${(blob.size / 1048576).toFixed(1)} MB）`, 6000);
    } catch (e) { busy(false); toast('打包失敗：' + e.message, 8000); }
  };

  function importManjuCast() {
    let pl = null, from = '';
    const m = location.hash.match(/manju-cast=([A-Za-z0-9_-]+)/);
    if (m) {
      try {
        const b = m[1].replace(/-/g, '+').replace(/_/g, '/');
        pl = JSON.parse(decodeURIComponent(escape(atob(b + '==='.slice((b.length + 3) % 4)))));
        from = 'hash';
      } catch (e) { pl = null; }
      history.replaceState(null, '', location.pathname + location.search);   // 清掉網址上的資料，重新整理不會再匯入一次
    }
    if (!pl) { try { pl = JSON.parse(localStorage.getItem('vg-manju-cast') || 'null'); from = 'storage'; } catch (e) { pl = null; } }
    if (!pl || pl.kind !== 'hg-cast' || !pl.state || pl.state.category !== 'manju') return;
    try { localStorage.removeItem('vg-manju-cast'); } catch (e) {}
    // 先把目前類別收好（跟換類別同一套做法），再換成漫劇
    try { if (S && S.category !== 'manju') localStorage.setItem('vg-cat-' + S.category, JSON.stringify(S)); } catch (e) {}
    const keep = S ? { mode: S.mode, engine: S.engine } : null;
    const base = V.newState('manju');
    S = { ...base, ...pl.state, version: 1, category: 'manju' };
    if (keep) { S.mode = keep.mode; if (keep.engine && keep.engine.route !== 'local') S.engine = { ...S.engine, ...keep.engine }; }
    save();
    try { localStorage.setItem('vg-cat-manju', JSON.stringify(S)); } catch (e) {}
    go(3);
    toast(`已從紅果漫劇角色生成器帶入「${S.basic.title}」：${S.characters.length} 位角色、${S.shots.length} 鏡（${from === 'hash' ? '網址' : '同站暫存'}）`, 7000);
    // 2026-11-15 角色參考圖：漫劇生成器的定妝照／三視圖／學員上傳的照片 → 「自己上傳」的角色設定圖（出片時當 Flow 參考圖）
    let imgs = {};
    try { imgs = JSON.parse(localStorage.getItem('vg-manju-imgs') || '{}') || {}; localStorage.removeItem('vg-manju-imgs'); } catch (e) { imgs = {}; }
    Promise.all(S.characters.map(async ch => {
      const u = imgs[ch.name]; if (!u) return 0;
      try {
        const r = await fetch(u); if (!r.ok) return 0;
        const b = await r.blob(); const ext = ((b.type || 'image/jpeg').split('/')[1] || 'jpg').replace('jpeg', 'jpg');
        const f = new File([b], `${ch.name}_參考圖.${ext}`, { type: b.type || 'image/jpeg' });
        charFiles.set(ch, f); ch.sheet_source = 'upload'; ch.sheet_file = f.name; return 1;
      } catch (e) { return 0; }
    })).then(r => { const n = r.reduce((a, b) => a + b, 0); if (n) { save(); renderFill(); toast(`已帶入 ${n} 位角色的參考圖（定妝照或你上傳的照片），出片時當 Flow 參考圖，臉才會一致`, 7000); } });
  }

  /* 2026-11-13 紅果漫劇角色生成器連結：同網站有 manju-cast/ 就用；本機版沒附（圖片 95 MB）就開線上版，並告訴它送回本機 */
  const MANJU_ONLINE = 'https://video-generator-aliang.netlify.app/manju-cast/';
  let manjuUrl = 'manju-cast/index.html';
  if (location.protocol !== 'file:') fetch('manju-cast/index.html', { method: 'HEAD' }).then(r => { if (!r.ok) throw 0; }).catch(() => { manjuUrl = MANJU_ONLINE + (location.port === '8833' ? '?gen=local' : ''); });
  else manjuUrl = MANJU_ONLINE;
  const mc = document.getElementById('manjuCard'); if (mc) mc.onclick = e => { e.preventDefault(); window.open(manjuUrl, '_blank'); };
  function manjuBtn(text) { return el('a', { class: 'btn manju-go', href: '#', onclick: e => { e.preventDefault(); window.open(manjuUrl, '_blank'); } }, text); }

  { const bh = document.getElementById('brandHome'); if (bh) bh.onclick = e => { e.preventDefault(); go(1); scrollTo({ top: 0, behavior: 'smooth' }); }; }   // 2026-11-13 老師：按 logo 回首頁
  detectEngines().then(() => { go(1); importManjuCast(); });
})();
