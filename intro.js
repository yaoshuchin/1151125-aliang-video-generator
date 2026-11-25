/* 2026-11-13 開場頁＋背景音樂（老師指定：一打開就要有音樂、一直播，使用者自己按靜音）。
   - 背景音樂 bgm.mp3：「AI 製片廠」首頁配樂 theme_loop.flac（YuE2 純器樂自產，阿亮老師自有），Web Audio 無縫循環。
   - 一開頁就嘗試播放；瀏覽器（Chrome／Edge／Safari）規定「網頁在使用者第一次點擊或按鍵前不能自己出聲」，
     被擋時就在使用者第一次點畫面任何地方／按任何鍵時立刻開始（不限開場的「進入」按鈕）。
   - 左下角常駐「🔊 音樂／🔇 已靜音」按鈕；靜音不記住，每次打開都重新播。
   - 開場覆蓋層同一分頁只出現一次（sessionStorage）；網址帶 #manju-cast=（紅果角色生成器送回來）直接跳過開場，但音樂照樣播。 */
(function () {
  'use strict';
  var KEY = 'vg-intro-seen', OFF = 'vg-bgm-off', SRC = 'bgm.mp3?v=20261113', VOL = 0.5, root = document.documentElement;
  function sget(store, k) { try { return window[store].getItem(k); } catch (e) { return null; } }
  function sset(store, k, v) { try { window[store].setItem(k, v); } catch (e) {} }
  if (!document.body) return;

  /* ================= 背景音樂 ================= */
  var off = false;   // 11/14 老師指定：每次打開都要播，靜音只算這一次，不記住
  try { localStorage.removeItem(OFF); } catch (e) {}
  var ctx = null, gain = null, node = null, playing = false, starting = false, fallback = null;
  var bytes = null;
  try { bytes = fetch(SRC).then(function (r) { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); }); } catch (e) { bytes = null; }

  var btn = document.createElement('button');
  btn.type = 'button'; btn.id = 'vgBgm'; btn.title = '背景音樂開／關';
  function paint() {   // 老師指定：按鈕只當「靜音」用，不顯示「點一下開始」之類的字
    btn.textContent = off ? '🔇 已靜音' : '🔊 音樂';
    btn.title = off ? '按一下打開音樂' : '按一下靜音';
    btn.setAttribute('aria-pressed', String(!off));
  }
  function ramp(v, sec) {
    if (!ctx) return; var t = ctx.currentTime;
    gain.gain.cancelScheduledValues(t); gain.gain.setValueAtTime(gain.gain.value, t); gain.gain.linearRampToValueAtTime(v, t + sec);
  }
  function play() {
    if (off || playing) return;
    // Chrome：沒有點擊前呼叫的 resume() 會一直等著；使用者點了之後再呼叫一次，前面那個等待就會跟著完成
    if (starting) { try { if (ctx) ctx.resume(); } catch (e) {} return; }
    starting = true;
    (function () {
      try {
        if (!ctx) { ctx = new (window.AudioContext || window.webkitAudioContext)(); gain = ctx.createGain(); gain.gain.value = 0; gain.connect(ctx.destination); }
      } catch (e) { return Promise.reject(e); }
      return ctx.resume().then(function () {
        if (ctx.state !== 'running') throw new Error('blocked');
        if (node) return;
        if (!bytes) throw new Error('nobytes');
        return bytes.then(function (b) { return new Promise(function (ok, bad) { ctx.decodeAudioData(b.slice(0), ok, bad); }); }).then(function (buf) {
          if (node) return; node = ctx.createBufferSource(); node.buffer = buf; node.loop = true; node.connect(gain); node.start();
        });
      });
    })().then(function () {
      starting = false; if (off) return; playing = true; ramp(VOL, 2); paint();
    }, function () {
      starting = false;
      // Web Audio 不行（例如舊瀏覽器）就改用 <audio loop>
      if (ctx && ctx.state === 'running') {
        try { fallback = fallback || new Audio(SRC); fallback.loop = true; fallback.volume = VOL;
          var p = fallback.play(); if (p && p.then) p.then(function () { playing = true; paint(); }, function () { paint(); }); } catch (e) {}
      }
      paint();
    });
  }
  function stop() {
    playing = false; ramp(0, 0.5);
    try { if (fallback) fallback.pause(); } catch (e) {}
    setTimeout(function () { try { if (ctx && !playing) ctx.suspend(); } catch (e) {} }, 600);
    paint();
  }
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (!off) { off = true; stop(); }
    else { off = false; paint(); play(); }
  });
  // 第一次點擊／按鍵／觸控就開始（瀏覽器只認這幾種動作為「使用者允許出聲」）
  function kick() { if (!off && !playing) play(); }
  ['pointerdown', 'keydown', 'touchend', 'click'].forEach(function (ev) { document.addEventListener(ev, kick, true); });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) kick(); });
  document.body.appendChild(btn);
  paint();
  play();   // 一開頁就試：瀏覽器允許的話馬上有聲音

  /* ================= 開場覆蓋層 ================= */
  var skip = /manju-cast=/.test(location.hash) || !!sget('localStorage', 'vg-manju-cast') || sget('sessionStorage', KEY) === '1';
  if (skip) { root.dataset.intro = 'skipped'; return; }

  var title = '影片製作包生成器', spans = '';
  for (var i = 0; i < title.length; i++) spans += '<span style="animation-delay:' + (1.0 + i * 0.09).toFixed(2) + 's;background-size:' + (title.length * 100) + '% 100%;background-position:' + (i / (title.length - 1) * 100).toFixed(1) + '% 0">' + title[i] + '</span>';
  var stars = '';
  for (var s = 0; s < 46; s++) stars += '<i style="left:' + (Math.random() * 100).toFixed(1) + '%;top:' + (Math.random() * 100).toFixed(1) + '%;animation-delay:' + (Math.random() * 3).toFixed(2) + 's"></i>';

  var ov = document.createElement('div');
  ov.id = 'vgIntro';
  ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true'); ov.setAttribute('aria-label', '開場');
  // 封面（11/14 老師指定）：好萊塢片廠開場（地球＋膠卷＋火炬雕像＋金像獎座、探照燈）融合華語影業（紅金祥雲、宮門、毛筆字），右下角毛筆「曾慶良（阿亮老師）出品」
  ov.innerHTML =
    '<div class="vi-bg"></div><div class="vi-shade"></div>' +
    '<div class="vi-beam l"></div><div class="vi-beam r"></div><div class="vi-stars">' + stars + '</div>' +
    '<div class="vi-film top"><i></i></div><div class="vi-film bot"><i></i></div>' +
    '<div class="vi-ctl"><button type="button" id="viSkip">跳過 ⏭</button></div>' +
    '<div class="vi-card">' +
      '<h1>' + spans + '</h1><p class="vi-sub">我用 Skill 建置影片</p>' +
      '<button type="button" class="vi-go" id="viGo">▶ 按一下進入</button>' +
      '<small class="vi-note">背景音樂會一直播放，左下角 🔊 按一下就靜音</small>' +
    '</div>' +
    '<div class="vi-credit"><span class="vi-name">曾慶良</span><span class="vi-alias">（阿亮老師）</span><span class="vi-role">出品</span></div>';
  document.body.prepend(ov);
  root.dataset.intro = 'shown';
  var prevOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';

  var closed = false;
  function close() {
    if (closed) return; closed = true;
    sset('sessionStorage', KEY, '1');
    kick();
    ov.classList.add('vi-out');
    setTimeout(function () {
      ov.remove(); document.body.style.overflow = prevOverflow; root.dataset.intro = 'done';
      document.removeEventListener('keydown', onKey);
    }, 1300);
  }
  function onKey(e) { if (e.key === 'Escape') close(); }
  ov.querySelector('#viGo').addEventListener('click', close);
  ov.querySelector('#viSkip').addEventListener('click', close);
  document.addEventListener('keydown', onKey);
})();
