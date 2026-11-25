// gaussian-field.js — 2D 高斯潑濺（Gaussian splatting）色團背景 + 網點印刷後製
// pop-halftone-kit｜阿亮老師・3A科技研究社
//
// 原理：每個 splat = 一個帶「中心、各向異性尺度、旋轉、顏色、透明度」的 2D 高斯分佈，
// 用 InstancedMesh 一次畫完（pass 1 → RenderTarget），再用全螢幕 shader 做
// 「柔色底 + 旋轉網點（halftone）+ 紙張顆粒 + 暗角」（pass 2）。
// 全部由 time 決定（無 Math.random / 無時鐘），可被 HyperFrames 任意 seek。
//
// 用法：
//   import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.181.2/+esm";
//   import { createGaussianField } from "./gaussian-field.js";
//   const field = createGaussianField(THREE, { canvas, palettes, keys, pulses });
//   window.addEventListener("hf-seek", (e) => field.renderAt(e.detail.time));
//   field.renderAt(window.__hfThreeTime || 0);

export function createGaussianField(THREE, opts = {}) {
  const {
    canvas,
    renderer: externalRenderer = null,
    width = 1920,
    height = 1080,
    seed = 7,
    count = 42,
    // 每組調色盤 = 色團用的顏色（不含紙色）
    palettes = [["#f2c230", "#e8402f", "#2f55c8"]],
    // [{ t: 秒, p: 調色盤索引, paper?: "#hex", clear?: 0..1 }]，在 t 時切到該調色盤
    keys = [{ t: 0, p: 0 }],
    fade = 0.35, // 調色盤切換的交叉淡化秒數
    paper = "#f3ead7",
    pulses = [], // 節拍秒數陣列：色團在這些時間點「彈一下」
    pulseAmount = 0.18,
    drift = 1, // 漂移幅度倍率
    dotSize = 12, // 網點格距（px，輸出解析度）
    dotAngle = 0.785, // 網點角度（弧度，45°）
    dotStrength = 0.92,
    softStrength = 0.62, // 柔色底的濃度
    grain = 0.055,
    vignette = 0.22,
    rtScale = 0.5, // pass 1 解析度比例（模糊本來就是目的，半解析度即可）
    centerClear = 0, // 0..1：中央橢圓留白（放大字的地方保持紙色，文字對比才夠）
    clearSize = [0.42, 0.34], // 留白橢圓半徑（佔畫面寬、高比例）
  } = opts;

  // ---------- 決定性亂數（mulberry32） ----------
  let s = seed >>> 0;
  const rand = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const renderer =
    externalRenderer ||
    new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  renderer.autoClear = false;

  const aspect = width / height;
  const rt = new THREE.WebGLRenderTarget(Math.round(width * rtScale), Math.round(height * rtScale), {
    type: THREE.HalfFloatType,
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
  });

  // ---------- pass 1：高斯 splat ----------
  const quad = new THREE.PlaneGeometry(2, 2);
  const geo = new THREE.InstancedBufferGeometry();
  geo.index = quad.index;
  geo.setAttribute("position", quad.getAttribute("position"));
  geo.instanceCount = count;

  const aBase = new Float32Array(count * 2);
  const aScale = new Float32Array(count * 2);
  const aRot = new Float32Array(count);
  const aAmp = new Float32Array(count * 2);
  const aFreq = new Float32Array(count * 2);
  const aPhase = new Float32Array(count * 2);
  const aAlpha = new Float32Array(count);
  const aColor = new Float32Array(count * 3);
  const slot = new Uint16Array(count);

  for (let i = 0; i < count; i++) {
    aBase[i * 2] = (rand() * 2.4 - 1.2) * aspect;
    aBase[i * 2 + 1] = rand() * 2.4 - 1.2;
    const big = rand() < 0.35;
    const base = big ? 0.55 + rand() * 0.55 : 0.22 + rand() * 0.35;
    aScale[i * 2] = base * (0.7 + rand() * 0.9);
    aScale[i * 2 + 1] = base * (0.6 + rand() * 0.7);
    aRot[i] = rand() * Math.PI;
    aAmp[i * 2] = (0.08 + rand() * 0.22) * drift;
    aAmp[i * 2 + 1] = (0.06 + rand() * 0.18) * drift;
    aFreq[i * 2] = 0.25 + rand() * 0.6;
    aFreq[i * 2 + 1] = 0.2 + rand() * 0.55;
    aPhase[i * 2] = rand() * Math.PI * 2;
    aPhase[i * 2 + 1] = rand() * Math.PI * 2;
    aAlpha[i] = 0.55 + rand() * 0.45;
    slot[i] = Math.floor(rand() * 997);
  }
  const ia = (arr, n) => new THREE.InstancedBufferAttribute(arr, n);
  geo.setAttribute("aBase", ia(aBase, 2));
  geo.setAttribute("aScale", ia(aScale, 2));
  geo.setAttribute("aRot", ia(aRot, 1));
  geo.setAttribute("aAmp", ia(aAmp, 2));
  geo.setAttribute("aFreq", ia(aFreq, 2));
  geo.setAttribute("aPhase", ia(aPhase, 2));
  geo.setAttribute("aAlpha", ia(aAlpha, 1));
  const colorAttr = ia(aColor, 3);
  colorAttr.setUsage(THREE.DynamicDrawUsage);
  geo.setAttribute("aColor", colorAttr);

  const splatMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uAspect: { value: aspect }, uPulse: { value: 1 } },
    vertexShader: /* glsl */ `
      attribute vec2 aBase; attribute vec2 aScale; attribute float aRot;
      attribute vec2 aAmp; attribute vec2 aFreq; attribute vec2 aPhase;
      attribute float aAlpha; attribute vec3 aColor;
      uniform float uTime; uniform float uAspect; uniform float uPulse;
      varying vec2 vUv; varying vec3 vColor; varying float vAlpha;
      void main() {
        vUv = position.xy;                       // -1..1，高斯在 shader 內算
        vColor = aColor; vAlpha = aAlpha;
        vec2 c = aBase + aAmp * sin(aFreq * uTime + aPhase);
        float cs = cos(aRot), sn = sin(aRot);
        vec2 p = position.xy * aScale * uPulse * 1.8;  // 1.8 ≈ 3σ 外框
        p = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs);
        vec2 w = c + p;
        gl_Position = vec4(w.x / uAspect, w.y, 0.0, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      varying vec2 vUv; varying vec3 vColor; varying float vAlpha;
      void main() {
        float r2 = dot(vUv, vUv) * 9.0 * 0.5;     // exp(-½·(d/σ)²)，σ = 1/3 外框
        float a = exp(-r2) * vAlpha;
        if (a < 0.003) discard;
        gl_FragColor = vec4(vColor * a, a);       // premultiplied
      }`,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
  });
  const splatScene = new THREE.Scene();
  const splats = new THREE.Mesh(geo, splatMat);
  splats.frustumCulled = false;
  splatScene.add(splats);
  const orthoCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  // ---------- pass 2：網點 + 紙 + 顆粒 ----------
  const paperColor = new THREE.Color(paper);
  const postMat = new THREE.ShaderMaterial({
    uniforms: {
      tSplat: { value: rt.texture },
      uRes: { value: new THREE.Vector2(width, height) },
      uPaper: { value: paperColor.clone() },
      uTime: { value: 0 },
      uDot: { value: dotSize },
      uAngle: { value: dotAngle },
      uDotStrength: { value: dotStrength },
      uSoft: { value: softStrength },
      uGrain: { value: grain },
      uVig: { value: vignette },
      uClear: { value: centerClear },
      uClearSize: { value: new THREE.Vector2(clearSize[0], clearSize[1]) },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = position.xy * 0.5 + 0.5; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D tSplat; uniform vec2 uRes; uniform vec3 uPaper;
      uniform float uTime, uDot, uAngle, uDotStrength, uSoft, uGrain, uVig, uClear;
      uniform vec2 uClearSize;
      float clearMask(vec2 uv) {
        vec2 e = (uv - 0.5) / uClearSize;
        return mix(1.0 - uClear, 1.0, smoothstep(0.55, 1.25, length(e)));
      }
      varying vec2 vUv;
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      void main() {
        vec4 s = texture2D(tSplat, vUv);
        float cov = clamp(s.a, 0.0, 1.0) * clearMask(vUv);
        vec3 hue = cov > 0.001 ? s.rgb / s.a : uPaper;
        // 柔色底：紙 + 半濃度色團
        vec3 col = mix(uPaper, hue, cov * uSoft);
        // 網點：旋轉格子，點半徑 ∝ √覆蓋率（面積比例正確）
        vec2 px = vUv * uRes;
        float cs = cos(uAngle), sn = sin(uAngle);
        vec2 r = vec2(px.x * cs - px.y * sn, px.x * sn + px.y * cs) / uDot;
        vec2 cell = fract(r) - 0.5;
        // 用格子中心取樣覆蓋率，點才是正圓
        vec2 cr = (floor(r) + 0.5) * uDot;
        vec2 cpx = vec2(cr.x * cs + cr.y * sn, -cr.x * sn + cr.y * cs);
        vec4 sc = texture2D(tSplat, clamp(cpx / uRes, 0.0, 1.0));
        float ccov = clamp(sc.a, 0.0, 1.0) * clearMask(clamp(cpx / uRes, 0.0, 1.0));
        vec3 chue = ccov > 0.001 ? sc.rgb / sc.a : uPaper;
        float rad = 0.62 * sqrt(ccov);
        float d = length(cell);
        float aa = 1.2 / uDot;
        float dotMask = 1.0 - smoothstep(rad - aa, rad + aa, d);
        vec3 ink = chue * 0.78;                   // 網點用同色略深，模擬油墨疊印
        col = mix(col, ink, dotMask * uDotStrength * smoothstep(0.02, 0.18, ccov));
        // 紙張顆粒（每 1/12 秒換一次，可 seek）
        float g = hash(floor(px) + floor(uTime * 12.0) * 17.0) - 0.5;
        col += g * uGrain;
        // 暗角
        vec2 q = vUv - 0.5;
        col *= 1.0 - uVig * dot(q, q) * 2.2;
        gl_FragColor = vec4(col, 1.0);
      }`,
    depthTest: false,
    depthWrite: false,
  });
  const postScene = new THREE.Scene();
  const postQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), postMat);
  postQuad.frustumCulled = false;
  postScene.add(postQuad);

  // ---------- 調色盤時間軸 ----------
  const pal = palettes.map((p) => p.map((h) => new THREE.Color(h)));
  const sortedKeys = [...keys].sort((a, b) => a.t - b.t);
  const tmpA = new THREE.Color();
  const tmpB = new THREE.Color();
  const smooth = (x) => x * x * (3 - 2 * x);

  function paletteAt(t) {
    let i = 0;
    while (i + 1 < sortedKeys.length && sortedKeys[i + 1].t <= t) i++;
    const cur = sortedKeys[i];
    const prev = sortedKeys[Math.max(0, i - 1)];
    const k = i === 0 ? 1 : smooth(Math.min(1, Math.max(0, (t - cur.t) / fade)));
    return { a: prev, b: cur, k };
  }

  function pulseAt(t) {
    let v = 1;
    for (const p of pulses) if (t >= p) v += pulseAmount * Math.exp(-(t - p) * 7) * Math.sin(Math.min(1, (t - p) * 9) * Math.PI * 0.5);
    return v;
  }

  // 外部可以在 post pass 之後再畫東西（例如 3D 道具）
  const overlays = [];

  function renderAt(time) {
    const t = Math.max(0, Number(time) || 0);
    const { a, b, k } = paletteAt(t);
    const pa = pal[a.p], pb = pal[b.p];
    for (let i = 0; i < count; i++) {
      tmpA.copy(pa[slot[i] % pa.length]);
      tmpB.copy(pb[slot[i] % pb.length]);
      tmpA.lerp(tmpB, k);
      aColor[i * 3] = tmpA.r;
      aColor[i * 3 + 1] = tmpA.g;
      aColor[i * 3 + 2] = tmpA.b;
    }
    colorAttr.needsUpdate = true;
    const paperA = new THREE.Color(a.paper || paper);
    const paperB = new THREE.Color(b.paper || paper);
    postMat.uniforms.uPaper.value.copy(paperA.lerp(paperB, k));
    const ca = a.clear ?? centerClear, cb = b.clear ?? centerClear;
    postMat.uniforms.uClear.value = ca + (cb - ca) * k;

    splatMat.uniforms.uTime.value = t;
    splatMat.uniforms.uPulse.value = pulseAt(t);
    postMat.uniforms.uTime.value = t;

    renderer.setRenderTarget(rt);
    renderer.setClearColor(0x000000, 0);
    renderer.clear(true, true, true);
    renderer.render(splatScene, orthoCam);
    renderer.setRenderTarget(null);
    renderer.clear(true, true, true);
    renderer.render(postScene, orthoCam);
    for (const draw of overlays) {
      renderer.clearDepth();
      draw(t, renderer);
    }
  }

  return {
    renderer,
    renderAt,
    addOverlay: (fn) => overlays.push(fn),
    dispose() {
      rt.dispose();
      geo.dispose();
      splatMat.dispose();
      postMat.dispose();
    },
  };
}
