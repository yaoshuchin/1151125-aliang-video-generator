---
name: liang-emotional-short
description: >-
  情感/教學短影音一條龍 — 給一段文案（旁白腳本），自動分鏡、用免費素材庫(Pixabay/Pexels)
  挑台灣/無臉場景畫面、生成童聲旁白、金句加重字卡、兩段式 BGM，輸出成品 MP4。
  觸發：把文案做成影片、情感短影音、語錄影片、療癒短片、金句影片、文案配畫面、
  emotional short、把這段話做成片。適用：60~120 秒旁白型情感/教學短影音。
  依附 `liang-stock-footage`（搜圖/下載）。完整教學長片走 ai-teaching-video、
  兩人對話走 ai-dialogue-video、既有素材精剪走 video-use。
author: 阿亮老師・3A科技研究社
version: 1.0.0
tags: [短影音, 情感影片, 語錄, 金句字卡, 童聲, 免費素材, 一條龍]
---

# 情感短影音一條龍

> **學員精簡版（影片製作包專用）**：旁白一律用免費 edge-tts。在「校園形象（Google Flow）」裡這是**備援路線**——只有 Flow 點數全部用完、使用者同意後，才改用免費實景素材（要搭配 `skills/liang-stock-footage`，使用者自己申請免費 Pexels／Pixabay 金鑰）做溫暖風校園片，不要放可辨識的學生臉孔。在「實景素材快剪」短影音裡它是主技能。

> 丟一段文案 → 出一支有台灣共鳴畫面、童聲旁白、金句字卡、兩段 BGM 的成品 MP4。

## 六大原則（務必遵守）
1. **文化共鳴優先**：台灣觀眾影片避免歐美臉；情感類優先無臉場景（風景/人流/車水馬龍/城市光影），能鎖台灣就鎖（夜市、福德宮燈籠、台北101、台北街景）。
2. **不重複素材**：每個分鏡用不同片段。
3. **金句加重字卡**：關鍵句做成置中大字卡（暗底色塊、淡入淡出），非只有底部小字幕。
4. **先縮圖再挑片**：先下候選縮圖拼對照表、看圖再選，不盲選第一名。
5. **改版沿用旁白**：`build_short.py` 已對旁白做快取（同文字同語音不重生），改畫面/字卡不再花錢。
6. **免費素材優先**：畫面一律走免費庫（Pixabay／Pexels）；配樂用使用者 `素材/` 裡的 mp3，沒有就用製作包內附的 CC BY 曲（`skills/flow-bgm-cc/`，有附才用），片尾或說明欄標示作者。

## 環境需求
- `PEXELS_KEY`、`PIXABAY_KEY`（搜圖，見 `liang-stock-footage`）
- 旁白：學員版預設免費 `edge`（微軟台灣語音 `zh-TW-HsiaoYuNeural`）。`fal_minimax` 童聲要付費 FAL_KEY，製作包不使用
- Python3（urllib/subprocess）＋ ffmpeg ＋ Pillow

## 標準流程
1. **分鏡**：把文案按語意切成句子清單，標出「金句」（emph）與每句對應的畫面意圖。
2. **挑片**（用 `liang-stock-footage`）：
   - 每個分鏡 `python <stock>/scripts/stock.py thumbs "關鍵字" --n 5 --out _挑片/Gx`
   - `python <SKILL_DIR>/scripts/make_sheet.py _挑片` 產生對照表 → 看圖挑最貼的（每段不同、鎖台灣/無臉）
   - `stock.py download <rid> --out _精選` 下載選定片段
3. **寫 spec**：照 `references/spec-example.json` 填 title/voice/bgm/lines（每句 say/emph/clip）。
4. **出片**：`python <SKILL_DIR>/scripts/build_short.py spec.json`
   - 先 `--check` 驗證 spec 與素材齊全、印時間軸，不花錢；OK 再正式跑。
5. **驗收**：抽畫格確認字卡渲染、畫面對題；附成品路徑給使用者。

## build_short.py 重點
- `voice.engine`：用 `edge`（免費，voice 如 `zh-TW-HsiaoChenNeural`、`zh-TW-HsiaoYuNeural`）。
- 旁白快取在 `_build/tts_cache/`，key=引擎+語音+文字雜湊 → 改版沿用、不重花。
- `orient`：`landscape`(1920×1080) 或 `portrait`(1080×1920，Reels/Shorts)。
- `bgm.phase1`/`phase2`/`transition`：兩段式，在 transition 秒交叉溶接；只給 phase2 則單段。
- 金句(emph)自動渲染成加重字卡；開頭 title/subtitle 做標題卡。

## 分工
| 需求 | 走哪支 |
|------|--------|
| 旁白型情感/語錄/療癒短影音 | **本技能** |
| 完整教學長片（含章節） | `ai-teaching-video` |
| 兩人對話 | `ai-dialogue-video` |
| 既有素材精剪 | `video-use` |
| 只搜/下載免費素材 | `liang-stock-footage` |
