# music-library — 可以一起散布的配樂曲庫

- 來源：Kevin MacLeod（incompetech.com），**CC BY 4.0**
- 學員精簡版只附 2 首（活潑 Wepa、溫暖 Carefree，約 6 MB）；完整 40 首可用 `scripts/fetch_music_library.py` 自己從 incompetech.com 下載

| 資料夾 | 情緒 | 首數 |
|---|---|---|
| `pop_活潑/` | 活潑 | 8 |
| `tech_科技感/` | 科技感 | 8 |
| `hype_熱血/` | 熱血 | 8 |
| `warm_溫暖/` | 溫暖 | 8 |
| `calm_沉穩/` | 沉穩 | 8 |

## 授權（CC BY 4.0）
- **可以**：商用、放進廣告與社群影片、改編剪輯、跟著課程包一起轉傳給學員。
- **條件：標示作者，並註明有剪輯或修改。** 影片用到哪一首，就把那一首的整段標示文字（含修改註記）貼到說明欄；投放廣告沒有說明欄時，放在片尾字卡。
- 每首的標示文字在 `CREDITS_標示作者.txt`。build_ad.py 產生的 `ASSETS.md` 也會自動附上這支影片用到的那一段。
- 標示格式（Kevin MacLeod 官方指定）：
```
"曲名" Kevin MacLeod (incompetech.com)
Licensed under Creative Commons: By Attribution 4.0
https://creativecommons.org/licenses/by/4.0/
（本片使用的片段經剪輯、音量調整）
```
- 不想標示作者的話：改用 `--music synth`（程式合成配樂，沒有任何授權條件）。

## 用法
- `build_ad.py --music auto` 會自動從這裡挑曲並對拍；`--mood tech|warm|hype|calm|pop` 換情緒。
- 曲目、BPM、鼓點清晰度、來源網址、SHA-256 都在 `library.csv`（Excel 可開）／`library.json`。
