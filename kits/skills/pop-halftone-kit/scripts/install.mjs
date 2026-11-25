#!/usr/bin/env node
// install.mjs — 把 pop-halftone-kit 資產複製進一個 HyperFrames 專案（跨平台：Windows / macOS / Linux）
// 任何 AI agent（Claude Code、Codex、Gemini CLI、Antigravity、Cursor…）或人工都用同一個指令：
//
//   node <kit>/scripts/install.mjs <專案資料夾> [--template ai-fatigue-satire|showcase-60s]
//
// 只用 Node 內建模組，不需要 npm install。
import { cpSync, existsSync, mkdirSync, readdirSync, statSync, copyFileSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { homedir, platform } from "node:os";

const kit = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const project = args.find((a) => !a.startsWith("--"));
const ti = args.indexOf("--template");
const template = ti >= 0 ? args[ti + 1] : null;

if (!project) {
  console.error("用法：node scripts/install.mjs <專案資料夾> [--template ai-fatigue-satire|showcase-60s]");
  process.exit(1);
}
const proj = resolve(project);
if (!existsSync(join(proj, "hyperframes.json"))) {
  console.error(`找不到 ${join(proj, "hyperframes.json")} — 請先執行：npx hyperframes init <name> --non-interactive --example=blank`);
  process.exit(1);
}

const pp = join(proj, "assets", "pp");
const fonts = join(proj, "assets", "fonts");
mkdirSync(pp, { recursive: true });
mkdirSync(fonts, { recursive: true });

for (const f of readdirSync(join(kit, "assets"))) {
  if (/\.(js|css)$/.test(f)) copyFileSync(join(kit, "assets", f), join(pp, f));
}
copyFileSync(join(kit, "assets", "fonts", "IBMPlexMono-Bold.ttf"), join(fonts, "IBMPlexMono-Bold.ttf"));

// 中文字型：Noto Sans TC（OFL）。依序找系統字型位置，找不到就提示下載
const notoCandidates = [
  "C:\\Windows\\Fonts\\NotoSansTC-VF.ttf",
  join(homedir(), "AppData", "Local", "Microsoft", "Windows", "Fonts", "NotoSansTC-VF.ttf"),
  "/Library/Fonts/NotoSansTC-VF.ttf",
  join(homedir(), "Library", "Fonts", "NotoSansTC-VF.ttf"),
  "/usr/share/fonts/truetype/noto/NotoSansTC-VF.ttf",
  join(homedir(), ".local", "share", "fonts", "NotoSansTC-VF.ttf"),
  join(kit, "assets", "fonts", "NotoSansTC-VF.ttf"),
];
const noto = notoCandidates.find((p) => existsSync(p));
if (noto) {
  copyFileSync(noto, join(fonts, "NotoSansTC-VF.ttf"));
  console.log(`✓ 已複製中文字型 ${noto}`);
} else {
  console.warn(
    `⚠ 找不到 NotoSansTC-VF.ttf（${platform()}）。請從 https://fonts.google.com/noto/specimen/Noto+Sans+TC 下載可變字型，\n  放到 ${join(fonts, "NotoSansTC-VF.ttf")}`,
  );
}

if (template) {
  const src = join(kit, "templates", template, "index.html");
  if (!existsSync(src)) {
    const list = readdirSync(join(kit, "templates")).filter((d) => statSync(join(kit, "templates", d)).isDirectory());
    console.error(`找不到範本 ${template}；可用：${list.join(", ")}`);
    process.exit(1);
  }
  const dst = join(proj, "index.html");
  if (existsSync(dst)) {
    cpSync(dst, dst + ".bak");
    console.log("已備份原 index.html → index.html.bak");
  }
  copyFileSync(src, dst);
  console.log(`✓ 已套用範本 ${template}`);
  // 範本附配樂時間表 → 複製並直接生成音樂（assets/audio/bgm.wav）
  const score = join(kit, "templates", template, "score.json");
  if (existsSync(score)) {
    copyFileSync(score, join(proj, "score.json"));
    mkdirSync(join(proj, "assets", "audio"), { recursive: true });
    execFileSync(process.execPath, [join(kit, "scripts", "gen-music.mjs"), join(proj, "score.json"), join(proj, "assets", "audio", "bgm.wav")], { stdio: "inherit" });
  }
}

for (const d of [pp, fonts]) for (const f of readdirSync(d)) console.log(`  ${join(d, f)}  ${statSync(join(d, f)).size} B`);
console.log("完成。下一步：npx hyperframes check .");
