# AGENTS.md — pop-halftone-kit

給任何 AI coding agent（OpenAI Codex、Cursor、Gemini CLI、Antigravity、Windsurf、Cline、Aider、Claude Code…）的入口。

**完整說明在 `SKILL.md`，動工前先讀它。** 這裡只放最短路徑：

1. 需求：Node.js 18+、可連網（`npx hyperframes` 與 CDN 上的 GSAP / three.js）、Chrome 由 HyperFrames 自動處理。
2. 建專案並套範本：
   ```bash
   npx hyperframes init videos/<name> --non-interactive --example=blank
   node <本資料夾>/scripts/install.mjs videos/<name> --template showcase-60s
   ```
3. 改 `videos/<name>/index.html` 的文案、場景、道具（道具 API 見 SKILL.md 第 4、4b、4c 節）。
4. 配樂：改了畫面時間就同步改 `score.json`，再跑 `node <本資料夾>/scripts/gen-music.mjs score.json assets/audio/bgm.wav`（SKILL.md 第 4e 節）。每支片都要有音樂。
5. 驗證：`npx hyperframes check .`（0 error）→ `npx hyperframes snapshot . --at …` 看圖。
6. 輸出：`npx hyperframes render . -q high -o renders/video.mp4`，再用 `ffprobe` 驗長度與解析度。

規則：時間只能來自 timeline／`hf-seek`；禁止 `Math.random()`、`Date.now()`、`requestAnimationFrame` 驅動動畫。
