// pop-themes.js — 配色主題（JS 端：高斯色團調色盤 + 紙色），對應 pop-props-more.css 的 [data-pp-theme]
// pop-halftone-kit｜阿亮老師・3A科技研究社
//
//   import { THEMES, themeKeys } from "./assets/pp/pop-themes.js";
//   createGaussianField(THREE, { paper: THEMES.fluo.paper, palettes: THEMES.fluo.palettes, ... })
//   或多主題混剪：palettes 串接各主題，keys 用 themeKeys() 產生。

export const THEMES = {
  // 預設：油墨三原色（紅黃藍 risograph）
  riso: {
    paper: "#f3ead7", dark: "#231f1d",
    palettes: [["#f2c230", "#2c4fc4", "#e23b2e"], ["#e23b2e", "#f2c230", "#f08a24"], ["#2c4fc4", "#e23b2e", "#7a4fd0"]],
  },
  // 螢光粉＋孔雀綠（riso 螢光墨）
  fluo: {
    paper: "#f6f0e6", dark: "#1f1b3a",
    palettes: [["#ff3d8b", "#00a3a3", "#ffd23f"], ["#00a3a3", "#ff3d8b", "#7b5cff"], ["#ffd23f", "#ff3d8b"]],
  },
  // 報紙：黑白灰＋一個套色紅
  newsprint: {
    paper: "#ece7dc", dark: "#151515",
    palettes: [["#3b3b3b", "#8a8478", "#d1231b"], ["#121212", "#6e6a62"], ["#d1231b", "#3b3b3b", "#a39d90"]],
  },
  // 夕陽：橘、琥珀、紫
  sunset: {
    paper: "#fff1e0", dark: "#2a1636",
    palettes: [["#ff5e3a", "#ffb627", "#6c3fc5"], ["#6c3fc5", "#ff5e3a", "#e83f6f"], ["#ffb627", "#ff5e3a"]],
  },
  // 薄荷：綠、珊瑚紅、芥末黃
  mint: {
    paper: "#eaf4ec", dark: "#14302a",
    palettes: [["#1b7f79", "#f7c548", "#f2545b"], ["#43aa8b", "#1b7f79", "#f7c548"], ["#f2545b", "#1b7f79"]],
  },
};

// 把 [{ t, theme, p?, dark? }] 轉成 gaussian-field 需要的 { palettes, keys }
export function themeKeys(list) {
  const palettes = [];
  const keys = [];
  for (const k of list) {
    const th = THEMES[k.theme] || THEMES.riso;
    palettes.push(th.palettes[(k.p || 0) % th.palettes.length]);
    keys.push({ t: k.t, p: palettes.length - 1, paper: k.dark ? th.dark : th.paper, ...(k.clear != null ? { clear: k.clear } : {}) });
  }
  return { palettes, keys };
}
