---
name: promo-ad-forge
description: 中文「動態設計廣告影片」導演技能：**給一個網址或文件（docx/pdf/pptx/md），自動爬站／解析 → 萃取重點 → 做成活潑輕快、對拍的動態廣告（9:16 或 16:9 或兩者一起出）**；也能把任一類別（課程/講座招生、學校活動、在地店家、公益宣導、App/SaaS、書籍、展覽…）做成 15–120 秒、畫面跟著配樂節拍走的專業動態廣告（MP4）。內建：web-pop 範本（粉彩色塊換場、逐字跳出、貼紙標籤、icon 卡打叉、官網截圖＋游標點擊、數字滾動、彩紙、放射光 CTA，21 種幕型；另有老店紅金 heritage 主題：金框徽章、商品價格卡、品項格、禮盒、會員註冊、店家資訊片尾）、活潑曲庫自動選曲對拍、8 支課程招生範例萃取的 16:9 範本、HyperFrames 影片引擎。當使用者說「把這個網站做成廣告影片」「這份文件做成宣傳影片」「做廣告影片」「動態設計廣告」「招生影片」「宣傳短片」「活動宣傳影片」「做成像這支的廣告」「30 秒廣告」「promo 影片」「產品動畫廣告」「直式/橫式廣告」，或丟一支參考廣告要做同等級但不同主題時使用。預設台灣繁體中文、配樂優先素材網站免版稅曲（無則自製合成）、示意數字標註「數字為示意」。
---
> ## 學員精簡版說明（影片製作包專用，先讀這段）
> - 這是「影片製作包生成器」附的精簡版：只留腳本、範本、參考文件、字型（Noto Sans TC 已縮成常用 5,400 字，罕用字會用電腦內建字型代替）、2 首 CC BY 配樂。原版 40 首曲庫、講師電腦路徑都已拿掉。
> - **在 Google Flow 類（課程宣傳）裡，本技能是「包裝」不是「主角」**：Flow 負責拍出每一鏡畫面（`python tools/flow_run.py`），本技能負責做 **片頭（2～4 秒）、報名資訊字卡、結尾 CTA**。做好的片段輸出成 mp4，放到 `03_字卡/片頭.mp4`、`03_字卡/片尾.mp4`，`python tools/make_final.py` 會自動接在 Flow 片段前後。
>   - 建議用 `templates/course-promo-16x9.html` 的「主標幕」「時間/DAY 幕」「CTA 幕」三幕改成短版（各 3～6 秒），文字只用 `影片需求.json` 裡使用者填的內容（片名、單位、日期、網址、行動呼籲），**不可自己編日期、價格、名額**。
>   - 比例跟 `output.ratio` 一致（16:9＝1920×1080，9:16＝1080×1920）；算圖只用本機 `npx hyperframes render`（免費），不要用任何要付費或登入的指令。
> - **整支改用本技能做動態廣告（web-pop 線、course-promo 72 秒長版）只有在 Flow 點數全部用完、而且使用者同意時才做**，先問使用者。


# promo-ad-forge — 動態設計廣告導演

> 文中 `<SKILL_DIR>` ＝本技能資料夾（在影片製作包裡是 `skills/promo-ad-forge`）。

> 一句提示詞做不出神級動畫；**拉開差距的是 context 與流程**。
> 本技能＝「導演層」：負責蒐集 context、定風格、對節拍、下導演指令；
> 渲染引擎沿用 HyperFrames 技能（`npx hyperframes skills` 安裝）（HTML＋GSAP → MP4），不重造輪子。

## 何時用哪條路

| 情境 | 路線 |
|---|---|
| **給網址或文件，要做成活潑輕快的動態廣告**（9:16／16:9／兩者） | **本技能 web-pop 線（首選）**：`ingest_source.py` 抓原料 → Claude 寫 `content.json` → `build_ad.py` 一鍵出兩種比例。**先讀 `references/web-pop.md`** |
| **在地老店／伴手禮／喜餅月餅禮盒／年節商品**（紅金傳統風、商品型錄、會員導購） | **web-pop 線＋`"theme": "heritage"`**：用 `emblem`／`product_card`／`product_grid`／`giftbox`／`member_signup`／`store_info` 幕型。先讀 `references/web-pop.md` 第八節＋`categories.md` 3b |
| 有網址的 SaaS／App 產品、要自動抓站＋旁白＋多幕平行建置 | 交棒 `product-launch-video`（先把本技能的 BRIEF/STYLE_SPEC 做好再交） |
| **課程／講座／工作坊招生**（16:9、60–120 秒） | **本技能長版線**：`templates/course-promo-16x9.html`（9 幕×8 秒，範例級骨架）＋先讀 `references/example-masterclass.md` |
| **其他一切類別**、社群直式 15–30 秒 | **本技能快速線**：單一 HyperFrames composition（`templates/beat-ad.html`，9:16） |
| 只要 10 秒內片頭／logo sting | `hyperframes` → `/motion-graphics` |

## web-pop 線速覽（網址／文件 → 動態廣告）

1. `python <SKILL_DIR>\scripts\ingest_source.py <網址或文件> --out <專案>\source`（網址有登入牆就再餵說明文件）。
2. 讀 `source.md`，萃取 8–12 個重點，依 `references/web-pop.md` 第四節寫 `<專案>\content.json`（只用來源事實；截圖挑過，不放測試資料/個資）。
3. `python <SKILL_DIR>\scripts\build_ad.py <專案>\content.json --out <專案> --aspect both`（使用者只要一種比例就給 `9:16` 或 `16:9`）。
4. 每個比例 `npx hyperframes lint`（error 0）→ `snapshot --at <每幕 85% 處>` 看 contact sheet → 有問題改 content.json 或範本後重建。
5. `npx hyperframes render --quality high --output renders/ad.mp4` → `verify_ad.py`；交付 `v916\renders\ad.mp4`、`h169\renders\ad.mp4`、`ASSETS.md`。

## 六步流程（每步都有產出檔，缺檔不得進下一步）

工作目錄：`<交付根>/<專案名>/`（未指定就用 `<使用者文件夾>\promo-ads\<專案名>`）。

### ① 找參考影片 → `STYLE_SPEC.md`
- 使用者有給參考影片：跑
  `python <SKILL_DIR>\scripts\analyze_reference.py <ref.mp4> --out ref/`
  → 讀 `ref/contact_sheet.png` 與 `reference_spec.json`（BPM、平均鏡頭長、切點對拍比例、主色）。
- 沒給：依類別從 `references/categories.md` 取預設參考風格；需要更多靈感列出 `references/reference-sources.md` 的站（whatships.com 等）。
- 依 `references/reference-analysis.md` 寫 `STYLE_SPEC.md`：版式、字級階層、色票、元件語彙、轉場、節奏密度、**要學的 3 件事 / 不學的 1 件事**。
- 參考影片只學「手法」，**不抄內容、不抄品牌、不抄人像**。

### ② 影片引擎
- `npx -y hyperframes@latest init <dir> --non-interactive --example=blank`，再把範本當 `index.html` 起點：課程招生 16:9 用 `templates/course-promo-16x9.html`（搜尋「【換】」替換文字），直式短版用 `templates/beat-ad.html`。
- 字型：把 `NotoSansTC-VF.ttf`（Windows 字型資料夾或 Google Fonts「Noto Sans TC」下載）複製到 `assets/fonts/`。
- 每一幕都是程式碼 → 改一行就能重渲染；技術契約以 `hyperframes-core` 技能 為準（root `data-start="0"`、單一 paused timeline、禁 `repeat:-1`、禁 CSS transform 與 GSAP 同屬性衝突、中文字型要以 `@font-face` 內嵌）。

### ③ 元件庫（畫面不廉價的關鍵）
- **不要把截圖原封不動放上去**：拆成卡片、按鈕、icon、數字、標籤各自動起來。
- 元件來源優先序：使用者真實素材拆件 → `npx hyperframes catalog`（registry）→ 21st.dev 元件的**視覺結構**（改寫成靜態 HTML/CSS，不引入 React runtime）。細節：`references/reference-sources.md`。

### ④ 餵足 context → `BRIEF.md` + `STORYBOARD_ABC.md`
- 依 `references/context-intake.md` 收齊：品牌色、字體、Logo、真實素材、受眾、單一訴求、CTA、日期/價格/網址、必要聲明。**能從對話或檔案推定的就不問**，只問真的缺的那一題。
- 一次產 **3 版分鏡**（A 痛點翻轉／B 數據衝擊／C 情境敘事，格式見 context-intake.md），選一版（使用者沒選就自選並說明理由）。

### ⑤ 先看靜態畫面（改圖只要幾秒）
- **配樂（學員精簡版）**：`素材/` 有使用者自己的 mp3 就用它；沒有就用內附曲庫 `music-library/`（Kevin MacLeod，**CC BY 4.0**，活潑 Wepa、溫暖 Carefree 兩首；`build_ad.py --music auto --mood pop|warm` 自動挑）。**用了內附曲就一定要把 `music-library/CREDITS_標示作者.txt` 裡那一首的整段標示文字放進片尾字卡或影片說明欄**，並寫進 `ASSETS.md`。想要更多曲子：`python <SKILL_DIR>\scripts\fetch_music_library.py`（自己從 incompetech.com 下載，同樣 CC BY）。自備曲子對拍：
  `python <SKILL_DIR>\scripts\music_beats.py <曲子.mp3> --out assets/bgm.wav --beats beats.json --duration <秒> --start <約略起點> --source-url <網址> --license <授權>`
  → 自動精測 BPM、從小節頭裁切（t=0＝重拍）、微調到 120 BPM、-16 LUFS；輸出需顯示 `PASS`。授權資訊寫進 `ASSETS.md`。
- 沒有合適曲目時才用合成備援（音樂與節拍同源）：
  `python <SKILL_DIR>\scripts\synth_bgm.py --out assets/bgm.wav --beats beats.json --bpm <BPM> --duration <秒> --style <pop-bounce|tech-pulse|warm-pluck|hype-trap> --project <專案名>`
  **每支影片配樂自動不同**（專案名決定調性、和弦進行、琶音、音色、鼓型、旋律動機）；同專案重跑音檔完全相同（改畫面不換歌）；使用者說「換一首」加 `--variant 2`、`3`…；**已有 bgm.wav 的專案改畫面時不要重生配樂**。
  使用者要 Suno 或自備配樂時，同樣走 `music_beats.py`（**不要用** `npx hyperframes beats`：實測把 120 BPM 判成 151.9）。
- 把 `beats.json` 的 `beats/downbeats/sections/hits` 貼進 composition 的 `BEAT` 常數；**每幕起點＝重拍、主角進場＝hit、次要元件＝拍點 stagger**。
- 先出靜態：`npx hyperframes snapshot --at <每幕中點>` → Read 檢查版面、字有沒有爆框、對比。
- **預設不停**：自檢通過就繼續；使用者說「分鏡要先給我看」才在此停下等確認。

### ⑥ 像導演一樣下指令
- 動畫化 → `npx hyperframes lint` → `check` → 渲染 `npx hyperframes render --quality high --output renders/ad.mp4`。
- 修改一律用 `references/director-vocab.md` 的中文導演詞（「放慢到 0.7 倍」「更有彈性」「打擊感再重一點」「這拍晚 1 拍進」），**一次只改一個變數**，改完重看該幕 snapshot。
- 驗證：`python <SKILL_DIR>\scripts\verify_ad.py renders/ad.mp4 --beats beats.json --expect-duration <秒>`（時長、解析度、有聲、響度、抽格拼圖、畫面變化點對拍比例）。

## 動態設計鐵律（做成作品集等級，不是 demo）
0. **範例級骨架（萃取自 8 支範例，詳見 `references/example-masterclass.md`）**：
   - **一幕＝4 小節＝8 秒**，幕內每 1–2 小節加入新元件、用高亮標「目前步驟」——不是一幕一句就換。
   - **常駐 HUD**（左上課名、右上日期/時間碼、四角括號、章節標、底部進度條）＋**景深背景**（深色漸層＋漂移光暈＋點陣/星塵/放射光），永不死平。
   - **左文右圖兩欄**：眉標 → 兩色大標 → 膠囊 → 兩行說明｜右側真實 UI/程式碼視窗/icon 群/流程節點。**畫面填到安全區 60–75%，不准半個畫面空白。**
   - **大數字當主角**（描邊 01→灌金、DAY 1/2、月曆日期、時數圓環），**真實素材拆件**（logo、截圖、成品縮圖、講師照）。
   - 大轉場用品牌色條擦除／閃光，放在**常駐層**以便跨越幕界；CTA 定格 ≥ 6 秒。
1. **一個節拍陣列驅動全部**：禁止散落的手調秒數。
2. **每個元件都要動**：進場（彈性 `back.out`/`elastic`）→ 停留呼吸（微 scale/float，有限次數）→ 在切場拍被下一幕「推走」。
3. **打擊感＝過衝＋落地回彈＋同拍的閃光/震動/粒子**，只放在 hit 上，不要每拍都炸。閃光／粒子一律「from 透明」起步（`fromTo({opacity:0})` 再亮起），否則 seek 到發射前會殘留在畫面上。
4. **至少 3 種不同進場軸向**（縮放模糊、側滑、上升旋轉、遮罩擦除、數字滾動）；同一招不連用兩幕。
5. **資訊階層**：一幕一個主訊息；主標 ≥ 畫面高 7%（16:9 約 ≥ 76px，9:16 約 ≥ 130px）；說明字 ≥ 28px（1080p）；安全邊距 ≥ 6%。
6. **數字**：示意數字旁或畫面底部標「數字為示意」；真實數字需有來源。
7. **收尾**：最後 2–3 秒 CTA（日期/網址/報名）定格讓人讀得完，配樂 outro 重擊同步落下。
8. **講師／作者署名片尾**：使用者提供講師照片與真實頭銜時，片尾放「講師卡」（照片＋姓名＋2–3 項真實頭銜）＋一句「由 ○○ 帶你…」，在倒數第 2 個 accent 拍登場，outro 重擊再帶 CTA。**頭銜只能用使用者提供的真實資料，不可自編**；沒有照片就不放人像。

## 預設規格（使用者沒指定時）
- 課程／講座招生：**72 秒、16:9（1920×1080）、30fps**（範例皆 16:9；120 秒長版＝每幕延長或補模組幕，仍以 8 秒為單位）。
- 其他類別／社群短版：30 秒、9:16（1080×1920）、30fps。
- web-pop 線（網址／文件）：預設 9:16＋16:9 兩支一起出；片長由幕數決定（預設約 60–90 秒，可用 `bars` 壓到 30 秒）；配樂 `pop_活潑` 曲庫原速（119–135 BPM）、-14 LUFS。
- 畫面文字全部台灣繁體中文；配樂優先素材網站免版稅曲（記錄授權），無則自行合成；示意數字標註「數字為示意」。
- 真實素材優先；沒有素材就用純設計元件（icon、卡片、數字、幾何），**不捏造**真實人物、學校、品牌、評價。

## 交付與驗證（缺一不算完成）
- `renders/ad.mp4`＋`verify/contact_sheet.png`＋`verify/report.json`＋`BRIEF.md`＋`STYLE_SPEC.md`＋`beats.json`。
- 交付前逐幕 snapshot 對照 `references/example-masterclass.md` 第五節檢查清單，未過的幕先修。
- 回報：片長、解析度、音訊響度、切場對拍比例、配樂來源與授權、已知限制、修改單一幕的方法（改 `index.html` 對應 scene 區塊→重渲染）。

## 已知坑（實測得來）
- `lint` 的 `nested_structure_needs_subcomposition` / `composition_file_too_large` 是 Studio 可讀性警告，單檔快速線可接受；**error 必須為 0**。
- 中文大標 `line-height` < 1.25 會被 `check` 判 `content_overlap` → 標題行高用 1.3。
- 暖色光暈上的橘色字對比常不足 3:1 → 強調色用深一階（例 `#d6460f`），跑 `check` 看 Contrast。
- 裝飾用描邊大數字加 `data-layout-ignore aria-hidden="true"`；刻意重疊的元素加 `data-layout-allow-overlap`（要加在**元素本身**）。
- 數字滾動、分數跳動用 `tl.to(obj,{v,onUpdate})` 改 textContent；不要 `tl.set(el,{textContent})`。
- 動態設計畫面變化是漸變，`verify_ad.py` 偵測到的切點數會少，看 `motion_on_beat` 比例即可。
- 跨幕轉場元素（色條擦除）若放在下一幕的 clip 裡，幕開始前那 0.3 秒會看不到 → 放常駐 HUD 層。
- `check` 的對比檢查會在閃光那一瞬間取樣：重擊前把同區的小字（眉標）先收掉；白底紅字用深一階紅（`#c8371f`）。
- `inline-block` 逐字落下的標題，未出現的字仍佔位，前幾格會偏左——正常，不要改成 absolute。

## 參考檔索引（按需讀，不要全載）
| 檔 | 何時讀 |
|---|---|
| `references/web-pop.md` | **web-pop 線必讀**：參考片拆解、流程、content.json 規格、15 種幕型、配樂、已知坑 |
| `scripts/ingest_source.py` | 網址（Playwright：截圖/品牌色/logo/標題段落/大圖/子頁）或文件（docx/pdf/pptx/md/html）→ `source.md` |
| `scripts/build_ad.py` | `content.json` → 自動選曲對拍 → 9:16＋16:9 HyperFrames 專案（`--render` 直接出 MP4＋驗證） |
| `templates/web-pop.html` | web-pop 動畫引擎（`S.<幕型>` 函式、轉場、彩紙、heritage 背景特效層）；build_ad.py 會自動套用 |
| `scripts/extend_music_library.py` | 曲庫新增情緒類別（預設 `pop_活潑`），自動分析 BPM／鼓點／彈跳感、排除節慶曲與重複檔 |
| `references/categories.md` | 步驟①④：各類別敘事拍、畫面語彙、配樂風格、BPM |
| `references/reference-analysis.md` | 步驟①：如何把參考影片寫成 STYLE_SPEC.md（含兩支範例拆解） |
| `references/reference-sources.md` | 步驟①③：參考影片站、元件庫、使用原則 |
| `references/context-intake.md` | 步驟④：context 清單、BRIEF 模板、3 版分鏡模板 |
| `references/director-vocab.md` | 步驟⑤⑥：中文導演詞 → GSAP 參數對照 |
| `templates/beat-ad.html` | 步驟②⑤：節拍驅動的 HyperFrames 起始範本（9:16，8 幕；內容為「星火程式社」虛構示範，換內容即用）。已通過 `check` 並實渲 30s MP4 |
| `templates/course-promo-16x9.html` | 課程招生 16:9 範例級範本（9 幕×8 秒＝72s：痛點/主標/路徑/模組/時間/DAY 課表/成果+對象/講師/CTA，HUD＋景深背景）。2026-10-14 `check` 全過（Contrast 66/66）並實渲 72s MP4 |
| `references/example-masterclass.md` | 做課程招生、或使用者嫌品質不夠時必讀：8 支範例萃取的量化結論、視覺系統、動態語法、逐幕檢查清單 |
| `references/music-library.md` | 步驟⑤：素材網站配樂來源與授權、選曲條件、曲庫結構、`music_beats.py` 用法 |
| `scripts/music_beats.py` | 步驟⑤：下載曲 → 精測 BPM、小節頭裁切、微調 120 BPM、響度標準化、輸出 beats.json |
