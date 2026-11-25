/**
 * 視覺化多分頁與主題控制核心模組 (portal.js)
 */

(function () {
  'use strict';

  const STORAGE_KEY_THEME = 'vg_theme_pref';
  const STORAGE_KEY_FONT = 'vg_font_pref';

  // 1. 初始化外觀設定（字型與主題）
  function initThemeAndFont() {
    const savedTheme = localStorage.getItem(STORAGE_KEY_THEME) || 'light';
    const savedFont = localStorage.getItem(STORAGE_KEY_FONT) || 'medium';

    setTheme(savedTheme, false);
    setFont(savedFont, false);

    // 綁定頂部布景按鈕
    document.querySelectorAll('.btn-theme-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        const theme = btn.dataset.theme;
        setTheme(theme, true);
      });
    });

    // 綁定頂部字型按鈕
    document.querySelectorAll('.btn-font-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        const font = btn.dataset.font;
        setFont(font, true);
      });
    });
  }

  function setTheme(theme, save = true) {
    document.body.dataset.theme = theme;
    document.documentElement.dataset.theme = theme;
    if (save) {
      try { localStorage.setItem(STORAGE_KEY_THEME, theme); } catch (_) {}
    }
    // 更新按鈕 active 樣式
    document.querySelectorAll('.btn-theme-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.theme === theme);
    });
  }

  function setFont(font, save = true) {
    document.documentElement.dataset.font = font;
    if (save) {
      try { localStorage.setItem(STORAGE_KEY_FONT, font); } catch (_) {}
    }
    // 更新按鈕 active 樣式
    document.querySelectorAll('.btn-font-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.font === font);
    });
  }

  // 2. 初始化分頁切換
  function initTabs() {
    const tabBtns = document.querySelectorAll('.nav-tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetTab = btn.dataset.tab;
        switchTab(targetTab);
      });
    });
  }

  function switchTab(tabId) {
    document.querySelectorAll('.nav-tab-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-pane').forEach(p => {
      p.classList.toggle('active', p.id === tabId);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // 3. 渲染風格與類別圖鑑
  function renderGallery() {
    const container = document.getElementById('galleryGrid');
    if (!container || !window.GALLERY_STYLES) return;

    container.innerHTML = window.GALLERY_STYLES.map(item => `
      <div class="gallery-card">
        <div class="gallery-card-top">
          <div class="gallery-card-icon">${item.icon}</div>
          <span class="gallery-badge badge-${item.badgeType}">${item.badge}</span>
        </div>
        <div class="gallery-card-title">${item.title}</div>
        <div class="gallery-card-desc">${item.desc}</div>
        <div class="gallery-meta">
          <span class="gallery-meta-tag">📐 ${item.ratio}</span>
          <span class="gallery-meta-tag">⏱️ ${item.seconds}</span>
        </div>
        <ul class="gallery-features">
          ${item.features.map(f => `<li>${f}</li>`).join('')}
        </ul>
        <button class="gallery-btn-apply" onclick="window.Portal.applyStyleToGenerator('${item.category}', '${item.id}')">
          ✨ 立即套用此風格製作
        </button>
      </div>
    `).join('');
  }

  // 4. 渲染經典分鏡範例庫
  let currentReplayCat = 'short';
  function renderReplaysShowcase(cat = 'short') {
    currentReplayCat = cat;
    const container = document.getElementById('showcaseContent');
    if (!container || !window.PRELOADED_REPLAYS) return;

    const data = window.PRELOADED_REPLAYS[cat];
    if (!data) return;

    const quick = data.quick || {};
    const shotsPatch = data.tasks?.shots?.patch || {};
    const shotsList = shotsPatch.shots || [];
    const title = shotsPatch.title || quick.topic || '精選分鏡範例';

    container.innerHTML = `
      <div class="showcase-detail-box">
        <div class="showcase-header">
          <div class="showcase-title-area">
            <h3>🎬 ${title}</h3>
            <p style="color: var(--text-muted); margin: 0; font-size: 0.95rem;">
              💡 核心主題：${quick.summary || '專案範例展示'}
            </p>
          </div>
          <button class="gallery-btn-apply" style="width: auto; padding: 0.6rem 1.4rem;" onclick="window.Portal.loadReplayToGenerator('${cat}')">
            📥 一鍵載入此範例至生成器
          </button>
        </div>
        
        <div style="margin-bottom: 1.2rem; display: flex; gap: 0.6rem; flex-wrap: wrap;">
          <span class="gallery-meta-tag">標籤：${quick.keywords || '精選'}</span>
          <span class="gallery-meta-tag">鏡數：${shotsList.length} 鏡</span>
          <span class="gallery-meta-tag">預計長度：${quick.seconds || 20} 秒</span>
        </div>

        <div class="showcase-shots-list">
          ${shotsList.map((s, idx) => `
            <div class="showcase-shot-card">
              <div class="shot-card-head">
                <span class="shot-no-badge">第 ${idx + 1} 鏡</span>
                <div class="shot-props">
                  <span>📐 ${s.size || '中景'}</span>
                  <span>🎥 ${s.camera || '固定'}</span>
                  <span>⏱️ ${s.sec || 5} 秒</span>
                  <span>✂️ ${s.transition || '直接切'}</span>
                </div>
              </div>
              <div class="shot-visual-text"><b>【畫面】</b> ${s.visual}</div>
              ${s.action ? `<div class="shot-visual-text" style="font-size:0.88rem; color:var(--text-muted);"><b>【動作】</b> ${s.action}</div>` : ''}
              ${s.sfx ? `<div class="shot-audio-box">🎵 <b>聲音／音效：</b>${s.sfx}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `;

    document.querySelectorAll('.showcase-cat-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.cat === cat);
    });
  }

  // 套用風格至生成器
  function applyStyleToGenerator(category, styleId) {
    switchTab('tab-generator');
    setTimeout(() => {
      // 觸發原始生成器的切換邏輯
      const catCard = document.querySelector(`.cat[data-cat="${category}"]`);
      if (catCard) {
        catCard.click();
      }
      if (category === 'short' && styleId) {
        setTimeout(() => {
          const styleCard = document.querySelector(`.style[data-style="${styleId}"]`);
          if (styleCard) styleCard.click();
        }, 150);
      }
    }, 100);
  }

  // 載入 Replay 範例至生成器
  function loadReplayToGenerator(category) {
    applyStyleToGenerator(category);
    setTimeout(() => {
      const toStep3 = document.getElementById('to3');
      if (toStep3 && !toStep3.disabled) toStep3.click();
    }, 300);
  }

  // 測試本機 8899 埠連線
  async function testLocalBridge() {
    const resBox = document.getElementById('bridgeTestResult');
    if (!resBox) return;
    resBox.innerHTML = '連線檢測中…';
    resBox.style.color = 'var(--text-muted)';
    try {
      const res = await fetch('http://127.0.0.1:8899', { mode: 'cors', cache: 'no-store' });
      if (res.ok) {
        const text = await res.text();
        resBox.innerHTML = '✅ 本機 AI 串接器運行中 (Port 8899 連線成功！)';
        resBox.style.color = '#10b981';
      } else {
        resBox.innerHTML = '⚠️ 收到回應但狀態異常：' + res.status;
        resBox.style.color = '#f59e0b';
      }
    } catch (e) {
      resBox.innerHTML = '❌ 未偵測到本機 AI 串接器 (請確認是否已雙擊「開啟AI串接器.cmd」)';
      resBox.style.color = '#ef4444';
    }
  }

  // 複製文字工具
  function copyText(text, btnElement) {
    navigator.clipboard.writeText(text).then(() => {
      if (btnElement) {
        const oldText = btnElement.innerText;
        btnElement.innerText = '✓ 已複製！';
        setTimeout(() => { btnElement.innerText = oldText; }, 2000);
      }
    }).catch(err => {
      alert('複製失敗：' + err);
    });
  }

  window.Portal = {
    setTheme,
    setFont,
    switchTab,
    applyStyleToGenerator,
    loadReplayToGenerator,
    renderReplaysShowcase,
    testLocalBridge,
    copyText
  };

  document.addEventListener('DOMContentLoaded', () => {
    initThemeAndFont();
    initTabs();
    renderGallery();
    renderReplaysShowcase('short');

    document.querySelectorAll('.showcase-cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        renderReplaysShowcase(btn.dataset.cat);
      });
    });

    const bridgeTestBtn = document.getElementById('btnTestBridge');
    if (bridgeTestBtn) {
      bridgeTestBtn.addEventListener('click', testLocalBridge);
    }
  });
})();
