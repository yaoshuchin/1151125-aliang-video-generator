// prop-rain.js — three.js 3D 道具雨（預設：金幣），疊在 gaussian-field 之上
// pop-halftone-kit｜阿亮老師・3A科技研究社
//
// 決定性：每個物件的落點、轉速、延遲都由 seed 算出；位置只依 time 計算，可任意 seek。
// 卡通感：MeshToonMaterial（3 階色）+ 背面放大的黑色描邊殼，貼近網點印刷風。
//
//   import { createPropRain } from "./prop-rain.js";
//   field.addOverlay(createPropRain(THREE, { start: 2.2, end: 4.6, count: 36 }));

export function createPropRain(THREE, opts = {}) {
  const {
    width = 1920,
    height = 1080,
    seed = 11,
    count = 32,
    start = 0, // 第一顆開始落下（秒）
    end = 3, // 之後不再出現新物件；已在空中的會落完
    spawnWindow = null, // 生成的時間範圍，預設 = end - start - fall
    fall = 1.3, // 每顆從上落到下的秒數
    color = "#f2c230",
    rim = "#c98a12",
    outline = "#1c1a1a",
    radius = 0.42,
    thickness = 0.1,
    geometry = null, // 可傳自訂 geometry（例如 BoxGeometry 當鈔票）
  } = opts;

  let s = seed >>> 0;
  const rand = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, width / height, 0.1, 100);
  camera.position.set(0, 0, 14);
  scene.add(new THREE.AmbientLight(0xffffff, 0.9));
  const key = new THREE.DirectionalLight(0xffffff, 2.2);
  key.position.set(3, 5, 6);
  scene.add(key);

  // 3 階 toon 漸層貼圖（DataTexture，不需外部檔）
  const steps = new Uint8Array([90, 170, 255]);
  const gradientMap = new THREE.DataTexture(steps, steps.length, 1, THREE.RedFormat);
  gradientMap.minFilter = THREE.NearestFilter;
  gradientMap.magFilter = THREE.NearestFilter;
  gradientMap.needsUpdate = true;

  const geo = geometry || new THREE.CylinderGeometry(radius, radius, thickness, 40);
  const faceMat = new THREE.MeshToonMaterial({ color, gradientMap });
  const rimMat = new THREE.MeshToonMaterial({ color: rim, gradientMap });
  // CylinderGeometry 群組：0 = 側面，1 = 上蓋，2 = 下蓋
  const mats = geometry ? faceMat : [rimMat, faceMat, faceMat];
  const outlineMat = new THREE.MeshBasicMaterial({ color: outline, side: THREE.BackSide });

  const span = spawnWindow ?? Math.max(0.1, end - start - fall);
  const halfH = Math.tan((camera.fov * Math.PI) / 360) * camera.position.z;
  const halfW = halfH * (width / height);
  const items = [];
  for (let i = 0; i < count; i++) {
    const g = new THREE.Group();
    const body = new THREE.Mesh(geo, mats);
    const shell = new THREE.Mesh(geo, outlineMat);
    shell.scale.setScalar(1.12);
    g.add(shell, body);
    scene.add(g);
    items.push({
      g,
      x: (rand() * 2 - 1) * halfW * 0.92,
      z: rand() * 3 - 1.5,
      delay: start + rand() * span,
      speed: 0.85 + rand() * 0.4,
      spinX: (rand() * 2 - 1) * 9,
      spinZ: (rand() * 2 - 1) * 6,
      sway: (rand() * 2 - 1) * 0.6,
      size: 0.75 + rand() * 0.6,
    });
  }

  return function draw(t, renderer) {
    let any = false;
    for (const it of items) {
      const local = (t - it.delay) * it.speed;
      const p = local / fall;
      const visible = p >= 0 && p <= 1.05;
      it.g.visible = visible;
      if (!visible) continue;
      any = true;
      // 輕微加速度：y = top - (p^1.35) * 全高
      const y = halfH * 1.15 - Math.pow(p, 1.35) * halfH * 2.4;
      it.g.position.set(it.x + Math.sin(local * 3) * it.sway, y, it.z);
      it.g.rotation.set(local * it.spinX, 0, local * it.spinZ);
      it.g.scale.setScalar(it.size);
    }
    if (any) renderer.render(scene, camera);
  };
}
