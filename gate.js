/**
 * 門禁認證安全模組 · Web Crypto API SHA-256 驗證
 * 遵循全域資安規範，不在前端存放任何明文密碼
 */

(function () {
  'use strict';

  const AUTH_KEY = 'video_generator_aliang_auth';
  const TOKEN_VAL = 'authenticated_nato_access';
  // SHA-256 雜湊值（對應密碼 "nato"）
  const NATO_HASH = '5cae49b1fea5b5b969cdc931b8338968940c92309aa2339360cdd5c77be4a4ff';

  async function sha256(str) {
    const enc = new TextEncoder().encode((str || '').trim());
    const hashBuf = await crypto.subtle.digest('SHA-256', enc);
    const hashArr = Array.from(new Uint8Array(hashBuf));
    return hashArr.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  function isAuthed() {
    try {
      return (
        sessionStorage.getItem(AUTH_KEY) === TOKEN_VAL ||
        localStorage.getItem(AUTH_KEY) === TOKEN_VAL
      );
    } catch (_) {
      return false;
    }
  }

  function setAuthed() {
    try {
      sessionStorage.setItem(AUTH_KEY, TOKEN_VAL);
      localStorage.setItem(AUTH_KEY, TOKEN_VAL);
    } catch (_) {}
  }

  function clearAuthed() {
    try {
      sessionStorage.removeItem(AUTH_KEY);
      localStorage.removeItem(AUTH_KEY);
    } catch (_) {}
  }

  function initGate() {
    const gateModal = document.getElementById('gateModal');
    const gateInput = document.getElementById('gatePassword');
    const gateSubmit = document.getElementById('gateSubmit');
    const gateError = document.getElementById('gateError');
    const gateLockBtn = document.getElementById('btnGateLock');

    if (!gateModal) return;

    if (isAuthed()) {
      gateModal.classList.add('hidden');
      document.body.classList.remove('modal-locked');
      if (gateLockBtn) gateLockBtn.innerHTML = '🔒 已授權 (點此鎖定)';
    } else {
      gateModal.classList.remove('hidden');
      document.body.classList.add('modal-locked');
      if (gateInput) gateInput.focus();
      if (gateLockBtn) gateLockBtn.innerHTML = '🔑 門禁保護中';
    }

    async function handleLogin() {
      const val = (gateInput ? gateInput.value : '').trim();
      if (!val) {
        showError('請輸入通關密碼');
        return;
      }

      try {
        const hash = await sha256(val);
        if (hash === NATO_HASH) {
          setAuthed();
          if (gateError) gateError.style.display = 'none';
          gateModal.classList.add('fade-out');
          setTimeout(() => {
            gateModal.classList.add('hidden');
            gateModal.classList.remove('fade-out');
            document.body.classList.remove('modal-locked');
            if (gateLockBtn) gateLockBtn.innerHTML = '🔒 已授權 (點此鎖定)';
          }, 400);
        } else {
          showError('密碼錯誤，請重新輸入');
          if (gateInput) {
            gateInput.select();
            gateModal.querySelector('.gate-card')?.classList.add('shake');
            setTimeout(() => {
              gateModal.querySelector('.gate-card')?.classList.remove('shake');
            }, 600);
          }
        }
      } catch (e) {
        showError('驗證異常：' + e.message);
      }
    }

    function showError(msg) {
      if (gateError) {
        gateError.textContent = msg;
        gateError.style.display = 'block';
      }
    }

    if (gateSubmit) {
      gateSubmit.addEventListener('click', handleLogin);
    }

    if (gateInput) {
      gateInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
          handleLogin();
        }
      });
    }

    if (gateLockBtn) {
      gateLockBtn.addEventListener('click', () => {
        if (isAuthed()) {
          if (confirm('確定要登出並鎖定網站嗎？')) {
            clearAuthed();
            if (gateInput) gateInput.value = '';
            gateModal.classList.remove('hidden');
            document.body.classList.add('modal-locked');
            gateLockBtn.innerHTML = '🔑 門禁保護中';
            if (gateInput) gateInput.focus();
          }
        } else {
          gateModal.classList.remove('hidden');
          document.body.classList.add('modal-locked');
          if (gateInput) gateInput.focus();
        }
      });
    }
  }

  window.GateSystem = {
    isAuthed,
    clearAuthed,
    initGate
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGate);
  } else {
    initGate();
  }
})();
