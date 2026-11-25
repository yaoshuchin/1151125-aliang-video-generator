---
name: liang-cut-broll
description: >-
  Generate broadcast-look animated B-Roll title cards from one line of copy, in a
  complete library of TEN distinct visual styles (Vox 紀錄片, Minimal 極簡, Pop Art
  普普, VHS 錄影帶, Pastel Code 粉彩程式, Dark Terminal 深夜終端, Editorial 雜誌,
  Neon 霓虹, Liquid Glass 液態玻璃, Split-flap 翻牌看板). Use whenever the user wants an animated
  B-Roll, motion-graphics overlay, kinetic text, animated title card, "Vox style" / "Johnny
  Harris style" animation, or shares a punchy line/stat to animate — 「幫我做一張動態
  B-Roll」「把這句話做成動畫」. Produces a self-contained .html (1920×1080 or 1080×1920)
  the creator opens in Chrome, screen-records, and drops into any editor.
---

# liang-cut-broll 動態B-Roll工作室

One line of copy in → a broadcast-look animated title card out. Each style is a complete
motion system (camera moves, staged reveals, drawn ink, film texture) driven by a single
`CONFIG` block — never hand-write markup; copy the style's template and edit CONFIG only.

## Step 0 — Style choice: check the profile, else show the GALLERY (never a text menu)
**Shared profile folder:** this pack keeps all creator memory in `_creator/` — resolve it as `~/.claude/skills/_creator/` first, else a `_creator/` folder in the working folder (create one there if none exists). Read `editing-setup.md` and `creator-profile.md` from it before asking the user anything; save every profile file this skill maintains (`broll-profile.md`) into it.

Look for `broll-profile.md` in `_creator/`. If it names a default style, use it
silently (per-request overrides always win: 「這張用極簡」).

**First-time users choose by WATCHING, not reading:** `gallery.html` loads every style
live in a numbered grid — but it pulls each animation from `templates/` via iframes, so it
**ONLY works opened from disk with `templates/` beside it**.
- **Local install (Claude Code / Cowork):** tell them to open `gallery.html` from the skill
  folder (double-click — Chrome, Safari, or Edge all work).
- **本地安裝（Claude Code 桌面版，預設情境）：** 直接請學員打開技能資料夾裡的
  `gallery.html`（雙擊即可，Chrome／Edge／Safari 都行），十種風格會即時播放。
  資料夾位置：`~/.claude/skills/liang-cut-broll/gallery.html`（或 `.codex`／`.gemini` 對應目錄）。
- **Web chat (claude.ai) — NEVER preview gallery.html as an in-chat artifact; every tile
  will 404** (the sandbox has no template files). Instead, in this order:
  1. 請學員在自己電腦打開本地 `gallery.html`（同上），它需要 `templates/` 在旁邊才會動。
  2. Last resort: build 2–3 fully self-contained single-style preview .html files
     (inline everything, no relative paths) and let them compare those. They reply with a number
(「1 號的剪報卡」「2 號深色」). Then **save to `_creator/broll-profile.md`**: default style, theme,
orientation, accent (brand color if they have one), plus anything learned later (e.g.
「不愛 slam，永遠用 rise」). Never ask about style again unless they raise it.

## Workflow
1. **Get the line** — the punchy sentence/stat to animate, and where it'll be used
   (Reels/Shorts → portrait; YouTube → landscape).
2. **Pick the style** — from the profile or Step 0. Then **read `styles/<style>.md`** for
   that style's directing rules before touching the template.
3. **Copy the template** to the working folder as `broll_NN_<shortname>.html` (numbered so
   clips sort in the editor bin), fill CONFIG per the style card.
4. **Deliver + recording instructions** (every time):
   > 用瀏覽器開檔案（Chrome／Safari／Edge 都可以）→ 全螢幕（Mac: Ctrl-Cmd-F）→ 開始螢幕錄影（QuickTime/OBS）→
   > **按 R**：畫面倒數 3·2·1 後動畫自動從頭跑（不用手忙腳亂按重新整理）→
   > 所有元素定住後再錄約 1-2 秒 → 停止，匯入剪輯軟體。
   > **按 S**：顯示/隱藏 SFX 音效清單（每個動作的精確秒數）——照著在剪輯軟體丟
   > whoosh／thunk／splice 音效，質感直接翻倍。錄影時記得把清單關掉。
   > **按 O**：outro 收尾動畫（每種風格有自己的離場方式）——想把卡片「剪出去」而不是
   > 硬切時，錄到 hold 之後按 O，多錄那 1 秒的離場。
5. If the user wants tweaks (「圈另一個詞」「慢一點」「換直式」), edit CONFIG and re-deliver.

## Style library
| # | Style | Card | Status |
|---|---|---|---|
| 01 | **Vox 紀錄片** — kinetic documentary, FOUR card types: 文字卡 kinetic text ／ 數據卡 animated chart (bar/line + counters) ／ 剪報卡 newspaper-cutout collage ／ 解釋板 evidence board (subjects converge on one idea via red strings). Route by pasted content: numbers→chart, sources/quotes→news, multiple causes→board, punchy line→text — see the style card. | `styles/vox.md` | ★ **LOCKED v1.0** — the quality reference for styles 02–10 |
| 02 | **Minimal 極簡** — corporate clean, THREE card types: 文字卡 ／ 數據卡 (thin bars + pulse) ／ 步驟卡 (framework reveal). Light + dark (keynote) themes. Route: line→text, numbers→chart, method/steps→steps. | `styles/minimal.md` | ★ **LOCKED v1.0** |
| 03 | **Pop Art 普普** — Lichtenstein comic, THREE card types: 文字卡 (starburst key word + ✗ + speech bubble) ／ 分格卡 comic strip (setup→beat→punchline burst) ／ 數據卡 (comic-block bars + burst value). Route: hot take→text, story/反轉→strip, numbers→chart. | `styles/pop.md` | ★ **LOCKED v1.0** |
| 04 | **VHS 錄影帶** — dark CRT camcorder, THREE card types: 文字卡 (tracking-glitch key word, static-eaten strike) ／ 日誌卡 tape index (typed entries + 轉捩點 lock) ／ 訊號表 (LED meters, hl peaks into the red). CRT power-on intro, power-off outro. Route: line→text, journey/timeline→log, numbers→meters. | `styles/vhs.md` | ★ **LOCKED v1.0** |
| 05 | **Pastel Code 粉彩程式** — Claude-language: ivory + drifting saturated pastels, serif × Courier, THREE card types: 文字卡 (typed coral code chip + ✳, linter-squiggle strike + // deprecated tooltip, terminal-prompt tag) ／ 終端機步驟卡 (commands run, ✓ confirms, focus step earns ✳) ／ 提交紀錄卡 (git-log journey, key commit + HEAD badge). Exhale-soft motion. Route: line→text, method→steps, journey→log. | `styles/pastel.md` | ★ **LOCKED v1.0** |
| 06 | **Dark Terminal 深夜終端** — the card IS a terminal session, THREE card types: 文字卡 command narrative (cat → rm backspace-delete strike → echo glowing-green payoff + [✓]) ／ 監控卡 htop monitor (segmented bars fill in discrete ticks, ONE hl row locks green + note) ／ 狀態卡 git status (green 新增 done vs amber 修改中 wip, ONE key item glows). Digital/crisp — NOT VHS-analog. Route: rejected belief + payoff line→text, numbers→top, progress/done-vs-doing→status. | `styles/darkterm.md` | ★ **LOCKED v1.0** |
| 07 | **Editorial 雜誌** — fashion-magazine spread, THREE card types: 文字卡 (oversized oblique olive key word + footnote ＊, proofreader hairline strike) ／ 引言卡 pull-quote (giant olive “ + attribution) ／ 目錄卡 contents (hairline rows + italic page numbers, ONE focus row). Serif-only, typographic poise — no camera, no ink, no texture. Route: claim→text, quote/manifesto→quote, list/framework→contents. | `styles/editorial.md` | ★ **LOCKED v1.0** |
| 08 | **Neon 霓虹** — physical night-sign, THREE card types: 文字卡 (every word a glass tube: buzz-flicker ignition, key = stutter-start → hot pink, out = tube shorts out to dark glass) ／ 菜單卡 night-diner menu (rows ignite down the board, ONE focus = tonight's special) ／ 計分板 scoreboard (tube digits count up, ONE hl pink + script tag, source mandatory). Wet-street reflection, power cable, POWER-CUT outro. Route: rejected idea + payoff→text, list/routine→menu, numbers→score. | `styles/neon.md` | ★ **LOCKED v1.0** |
| 09 | **Liquid Glass 液態玻璃** — macOS glass material, THREE card types: 文字卡 (frosted panels on aurora wallpaper; key word gets a magnifying glass capsule + caustic light; cut word FROSTS OVER behind the glyphs, text flips dark slate) ／ 小工具卡 glass widgets (stats jelly-land + count up, ONE hl in pink glass, source mandatory) ／ 通知卡 notification stack (steps as banners, ONE focus pops pink). Refraction rims, jelly physics, live clock. Route: claim→text, numbers→widgets, list/steps→notif. | `styles/glass.md` | ★ **LOCKED v1.0** |
| 10 | **Split-flap 翻牌看板** — mechanical departure board, THREE card types: 文字卡 (every char a flap tile clattering to its letter; key = word re-locks INVERSE AMBER + frame; out = red 「—」 dashes + 已取消) ／ 時刻表卡 timetable (TIME/SERVICE/STATUS rows, 延誤 red, ONE focus row's status flips last to 登機中 amber) ／ 數字卡 flap digits (ONE hl row all-amber, source mandatory). Live clock, sticky-flap ambience, board-clear outro. Sells on SFX — always deliver the cue sheet. Route: rejected idea + payoff→text, schedule/routine→timetable, numbers→digits. | `styles/flap.md` | ★ **LOCKED v1.0** |

## Hard rules (all styles)
- Canvas exact px (1920×1080 or 1080×1920 via `CONFIG.orientation`), scaled-to-fit window.
- Self-contained single .html; only external dep = Google Fonts. No localStorage.
- Copy in 繁體中文（台灣）unless the user's line is in another language.
- Content fully landed and holding by ~5s; ambient texture (grain/drift) may keep moving.
- One emotional focal point per card (one `key` word). If the user's line has two ideas,
  make two cards.
---

## 相依與離線／隱私說明（2026-08 補充）

- 這些 B-Roll 模板的字型透過 **Google Fonts CDN**（`fonts.googleapis.com`）載入，
  第一次開啟需連網；連網時瀏覽器會向 Google 發出請求（會帶 IP／User-Agent）。這是
  HTML 動態卡的業界標準做法，對本地螢幕錄製用途風險極低。
- **要完全離線／零外部請求**：可把字型下載成 `.woff2` 放進 `fonts/`，模板改用
  本地 `@font-face`。需要時說一聲，我幫你把 10 種模板一次在地化。
- 模板本身**只有靜態 CSS/JS，無 fetch/XHR、不回傳任何資料**。
