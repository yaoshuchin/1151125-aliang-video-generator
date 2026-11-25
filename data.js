/* 影片製作包生成器：類別、子風格、欄位、範例（全部資料集中在這裡，改這個檔就能加類別） */
window.VG = (() => {
  const CATS = [
    { id: 'short', icon: '⚡', name: '短影音', tag: '最快出片・不用 Flow', open: true, engine: 'local',
      desc: '用我們附上的技能包在你自己的電腦做出影片，不用 Google 帳號點數，幾分鐘就出片。' },
    { id: 'promo', icon: '🎓', name: '課程宣傳', tag: 'Google Flow', open: true, engine: 'flow', skills: ['promo-ad-forge', 'content-to-motion-video', 'emotion-director', 'pixel2motion', 'liang-cut-broll', 'website-to-video'],
      desc: '招生、研習、社團、營隊的宣傳短片，讓人看完想報名。' },
    { id: 'campus', icon: '🏫', name: '校園形象廣告', tag: 'Google Flow', open: true, engine: 'flow', skills: ['emotion-director', 'pixel2motion', 'consistency-checker', 'liang-cut-broll', 'embedded-captions', 'flow-bgm-cc', 'liang-emotional-short', 'liang-stock-footage'],
      desc: '學校特色、校園一天、畢業季、校慶，拍出學校的溫度。' },
    { id: 'concept', icon: '💡', name: '知識概念短片', tag: 'Google Flow', open: true, engine: 'flow', skills: ['content-to-motion-video', 'stickman-story-video', 'guizang-material-illustration', 'manim-composer', 'consistency-checker', 'flow-bgm-cc'],
      desc: '把一個觀念（例如颱風怎麼形成、光合作用）做成 30 秒內的動畫短片，上課直接播。' },
    { id: 'wuxia', icon: '⚔️', name: '武俠', open: false },
    { id: 'manju', icon: '📚', name: '漫劇', tag: 'Google Flow', open: true, engine: 'flow', skills: ['emotion-director', 'consistency-checker', 'embedded-captions', 'liang-cut-broll', 'flow-bgm-cc'],
      desc: '紅果風直式短劇。先到「紅果漫劇角色生成器」挑角色，一鍵帶進來。' },
    { id: 'anime', icon: '🎬', name: '動畫', open: false },
    { id: 'real', icon: '🧑', name: '真人實拍風', open: false },
    { id: 'avatar', icon: '🗣️', name: '數字人主講', open: false },
    { id: 'mv', icon: '🎵', name: 'MV 音樂影片', open: false },
    { id: 'product', icon: '📦', name: '產品廣告', open: false },
    { id: 'greeting', icon: '🎂', name: '節慶賀卡', open: false },
    { id: 'picturebook', icon: '📖', name: '繪本故事', open: false },
    { id: 'game', icon: '🎮', name: '遊戲宣傳', open: false },
    { id: 'adult', icon: '🔞', name: '成人（18+）', open: false },
  ];

  /* 短影音子風格：skills＝製作包要附的技能（顯示用；實際打包以 kits/manifest.json 為準，由 04_技能包/build_kits.py 產生） */
  const SHORT_STYLES = [
    { id: 'kinetic', icon: '🔤', name: '動態字卡快剪', skills: ['hyperframes（官方安裝）', 'liang-cut-broll', 'hyperframes-registry', 'pop-halftone-kit', 'gsap', 'motion-design'],
      desc: '大字標題、數字、重點一句一句跳出來，配節奏音樂。活動公告、招生快訊、金句。', needs: [] },
    { id: 'explainer', icon: '🧪', name: '知識圖解動畫', skills: ['hyperframes（官方安裝）', 'faceless-explainer', 'handwrite-ad', 'hyperframes-registry', 'guizang-material-illustration', 'gsap', 'motion-design'],
      desc: '圖示、箭頭、圖表一步一步長出來，30 秒講清楚一個觀念。', needs: [] },
    { id: 'lecture', icon: '🎤', name: '教學短講（投影片＋配音）', skills: ['ai-teaching-video', 'slideshow', 'caption-doctor'],
      desc: '自動做投影片、配上免費的臺灣腔旁白和字幕。重點複習、課前預告。', needs: [] },
    { id: 'logo', icon: '🏷️', name: '校徽／Logo 動畫開場', skills: ['pixel2motion', 'motion-graphics', 'motion-design'],
      desc: '把校徽或社團 Logo 圖檔變成會動的片頭。', needs: ['Logo 圖檔（PNG/JPG），放在「品牌結尾」區'] },
    { id: 'stock', icon: '🎞️', name: '實景素材快剪', skills: ['liang-stock-footage', 'liang-emotional-short', 'liang-cut-broll', 'hyperframes（官方安裝）'],
      desc: '從 Pixabay／Pexels 免費可商用影片庫找畫面，剪成有字幕的短片。', needs: ['Pixabay 或 Pexels 免費金鑰'] },
    { id: 'handdrawn', icon: '✏️', name: '手繪故事短片（進階）', skills: ['story-to-handdrawn-video', 'imagegen'],
      desc: '像繪本一樣的手繪畫面（3:4 直式）。要 AI 會畫圖，建議用 Codex。', needs: ['Codex（內建生圖）', '第一次要下載約 1GB 的算圖程式'] },
  ];

  const SIZES = ['大遠景', '遠景', '全景', '中景', '近景', '特寫', '大特寫'];
  const CAMS = ['固定', '緩慢推近', '拉遠', '左右搖', '上下搖', '跟拍', '環繞', '空拍俯視', '手持晃動'];
  const TRANS = ['直接切', '淡入淡出', '溶接', '擦去', '閃白', '匹配剪接'];
  const LOOKS = ['寫實電影感', '溫暖紀錄片', '日系清新', '3D 動畫', '水彩手繪', '扁平插畫', '黏土動畫', '剪紙拼貼', '黑白懷舊', '科技藍光'];
  const PLATFORMS = ['YouTube', 'YouTube Shorts', 'Instagram Reels', 'Facebook', '學校網站', '課堂播放', 'LINE 群組'];

  /* 九區欄位（key 對應 state） */
  const SECTIONS = [
    { id: 'basic', no: '①', name: '基本資料', ai: false },
    { id: 'audience', no: '②', name: '觀眾與訊息', ai: true },
    { id: 'style', no: '③', name: '風格美術', ai: true },
    { id: 'shots', no: '④', name: '分鏡表', ai: true },
    { id: 'characters', no: '⑤', name: '角色設定', ai: true },
    { id: 'sound', no: '⑥', name: '聲音', ai: true },
    { id: 'brand', no: '⑦', name: '品牌結尾', ai: true },
    { id: 'output', no: '⑧', name: '輸出', ai: false },
    { id: 'engine', no: '⑨', name: '生成引擎', ai: false },
  ];

  /* 各類別範例（學員一開始看到的預填內容；AI 模式下只預填「快速開始」） */
  const EXAMPLES = {
    short: { title: '期末成果展快訊', topic: '本校 12/20 舉辦期末成果展，歡迎家長參觀', summary: '用大字卡快速介紹成果展的時間、地點、三個亮點，最後邀請家長來看。', keywords: '成果展、家長日、邀請', seconds: 20, shots: 4, look: '扁平插畫', ratio: '9:16' },
    promo: { title: 'AI 影音生成工作坊招生', topic: '寒假教師研習：用 AI 做出第一支影片', summary: '一位老師原本覺得做影片很難，參加工作坊後用 AI 生成器 30 分鐘就做出課程宣傳片，學生看得目不轉睛，最後邀請大家報名。', keywords: '教師研習、AI 影片、寒假', seconds: 24, shots: 5, look: '溫暖紀錄片', ratio: '16:9' },
    campus: { title: '我們的學校一天', topic: '從清晨升旗到放學夕陽，呈現學校的溫度', summary: '清晨校門口的陽光、操場上的晨跑、教室裡專心的眼神、午後社團的笑聲，最後夕陽下的校門，帶出學校的願景。', keywords: '校園、溫暖、成長', seconds: 30, shots: 6, look: '日系清新', ratio: '16:9' },
    manju: { title: '真千金回來了', topic: '真假千金短劇第 1 集', summary: '被調包二十年的女主回到親生家庭，被假千金處處陷害，她決定一層一層揭開真相。', keywords: '真假千金、打臉、豪門', seconds: 25, shots: 5, look: '寫實電影感', ratio: '9:16' },
    concept: { title: '颱風是怎麼形成的？', topic: '國中自然：颱風的形成條件', summary: '溫暖的海面讓水氣上升、地球自轉讓空氣旋轉、越轉越強形成颱風眼，最後提醒防颱準備。', keywords: '颱風、熱帶海洋、地球自轉', seconds: 24, shots: 4, look: '3D 動畫', ratio: '16:9' },
  };

  function blankShot(no) {
    return { no, size: '中景', camera: '固定', visual: '', character: '', action: '', sec: 5, transition: '直接切', sfx: '', prompt: '' };
  }

  /* 2026-11-13 角色：多了角色設定圖提示詞與來源（codex／flow／upload／fal） */
  function blankChar() {
    return { name: '', look: '', outfit: '', personality: '', anchor: '', sheet_prompt: '', sheet_source: 'codex' };
  }

  function newState(cat) {
    const ex = EXAMPLES[cat] || EXAMPLES.promo;
    return {
      version: 1,
      mode: 'ai',
      category: cat,
      shortStyle: cat === 'short' ? 'kinetic' : '',
      quick: { summary: ex.summary, keywords: ex.keywords, shots: ex.shots },
      basic: { title: ex.title, topic: ex.topic, org: '', seconds: ex.seconds, platform: ex.ratio === '9:16' ? 'Instagram Reels' : 'YouTube', lang: '繁體中文（臺灣國語）' },
      audience: { target: '', message: '', action: '', keywords: '', avoid: '' },
      style: { look: ex.look, palette: '', mood: '', reference: '', consistency: '' },
      shots: Array.from({ length: ex.shots }, (_, i) => blankShot(i + 1)),
      characters: [],
      sound: { narration: '', subtitles: '', voice: '溫暖女聲', music: '', sfx: '', subtitleStyle: '白字黑邊，畫面下方' },
      brand: { org: '', logoText: '', slogan: '', cta: '', url: '', endSec: 3 },
      output: { ratio: ex.ratio, res: '360p', final: '720p', filename: (ex.title || '影片') + '.mp4' },
      engine: { route: cat === 'short' ? 'local' : 'auto', accounts: [{ email: '', password: '' }], apiKey: '', falKey: '', falModel: 'kling', falMaxUsdPerShot: 1, maxCostPerShot: 30, maxCostPerImage: 0 },
      assets: [],
    };
  }

  /* 2026-11-15 旁白／字幕／對白語言（學員要英文、臺語） */
  const LANGS = ['繁體中文（臺灣國語）', '臺語（臺灣台語）', '英文', '日文', '韓文', '雙語：中文旁白＋英文字幕'];
  const LANG_NOTE = {
    '繁體中文（臺灣國語）': '旁白用臺灣口音配音（edge-tts 臺灣女聲／男聲）；Flow 有對白時指定臺灣口音，不會變成中國大陸腔。',
    '臺語（臺灣台語）': '旁白稿用教育部臺語漢字寫，字幕附華語。免費配音沒有臺語聲音：請自己（或請長輩）唸一遍錄成 05_旁白/旁白.mp3，合成時會直接用；Flow 角色講臺語效果不穩，建議對白也用錄音。',
    '英文': '旁白、字幕、Flow 對白都用英文（配音 en-US）。畫面上的欄位說明還是中文，方便你檢查。',
    '日文': '旁白、字幕、Flow 對白都用日文（配音 ja-JP）。',
    '韓文': '旁白、字幕、Flow 對白都用韓文（配音 ko-KR）。',
    '雙語：中文旁白＋英文字幕': '旁白用臺灣國語配音，字幕每句兩行：中文一行、英文一行。',
  };
  /* 2026-11-15 開場鉤子句型（參考 ig-reel 的 26 種 Reel 鉤子公式，改寫成中文、校園情境） */
  const HOOKS = [
    ['反差對比', '以前要…，現在只要…', '「以前做一支宣傳片要三天，現在一節課。」', '3 天 → 45 分鐘'],
    ['直接下指令', '別再…了，改成…', '「別再照著投影片念課本了。」', '別再念投影片'],
    ['沒人告訴你', '沒有人告訴你，…其實…', '「沒人告訴你，植物最忙的是早上。」', '植物最忙的時刻'],
    ['數字清單', '…的 3 個方法，第 2 個最多人忽略', '「報告拿高分的 3 招，第 2 招沒人用。」', '高分 3 招'],
    ['提出疑問', '你知道…嗎？', '「你知道一片葉子一天能做多少糖嗎？」', '一片葉子＝？'],
    ['現場直擊', '從做到一半開始，不交代前情', '畫面一開始火山實驗就在噴發', '（畫面本身就是鉤子）'],
    ['結果先給', '先秀成品，再倒敘怎麼做', '「這台機器人，三週前還是一堆零件。」', '三週前 vs 現在'],
    ['點名觀眾', '…的你，注意', '「準備選社團的新生注意。」', '新生注意'],
    ['倒數期限', '…之前一定要…', '「11 月 30 日報名截止。」', '倒數 15 天'],
    ['打破迷思', '其實你不需要…', '「做影片其實不需要會剪輯。」', '不用會剪輯'],
    ['真實數據', '…%的人…', '「全班 8 成的人都算錯這一題。」（數字一定要真的）', '80% 都錯'],
    ['失敗紀錄', '前 3 次都失敗，第 4 次…', '「火箭射了 3 次都翻倒，第 4 次改了一個地方。」', '第 4 次成功'],
    ['正反對照', '錯誤做法 vs 正確做法', '左邊亂丟回收、右邊正確分類', '✗ vs ✓'],
    ['引用提問', '「…？」每週都有人問我', '「老師，這個會考嗎？」——每週都有人問。', '這會考嗎？'],
  ];
  const HOOK_RULES = ['第一個畫面就要有動作或反差，不要片頭、不要「大家好」、不要自我介紹。', '口說的那句和畫面字卡分開寫：字卡 6 個字以內、第 1 格就出現。',
    '數字一定要是真的；不知道就寫 {{你的數字}}，不要編。', '直式 9:16 的字卡放在安全區：避開畫面最上面 12%、最下面 25%、右側 20%（會被平台按鈕和說明文字蓋住）。',
    '最後一鏡呼應第 1 鏡的關鍵字，觀眾重播時會接得剛好。', '一支短片只講一件事；有兩個重點就拆成兩支。'];

  return { CATS, SHORT_STYLES, SIZES, CAMS, TRANS, LOOKS, PLATFORMS, SECTIONS, EXAMPLES, newState, blankShot, blankChar, LANGS, LANG_NOTE, HOOKS, HOOK_RULES };
})();
