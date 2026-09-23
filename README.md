# 每日學習教練（Daily Learning Coach）

Allysa 專屬的每日興趣學習教練：每天 15 到 20 分鐘，一個知識點、一個小任務。
用 Streamlit 做成，透過 Groq API 呼叫 AI 模型。

## 功能

- **系統指令分模組送出**：每次呼叫只送「共通核心」（`coach/prompts/core.md`）＋當天主題
  （`coach/prompts/topics/<主題>.md`）＋自動產生的學習紀錄摘要。`coach/system_prompt.md` 是完整原版，
  只當參考，太大（約 7,400 tokens）不會送出。
- **Token 預算**：每次請求（system＋對話＋max_tokens）估算後控制在 4,000 以內（`coach/tokens.py`），
  超過就先丟掉最舊的對話。Groq 免費方案 openai/gpt-oss-120b 每分鐘 8,000 tokens。
- **錯誤處理**：429／連線錯誤會自動等待重試 2 次；還是失敗時畫面只顯示一句中文提示和「重試」按鈕，
  詳細錯誤只寫進 log（Streamlit Cloud：Manage app）。
- **每週行程**：一／五 時尚、材質與珠寶 · 二 哲學 · 三／六 看書 · 四 宇宙學 · 日 自由主題。
  商業計劃、股票投資可以隨時手動選。
- **難度依主題分開計算**：同一主題第 1–3 次入門、第 4–7 次中階、第 8 次以後進階。
- **學習紀錄**：日期、主題、難度、是否完成、今日主題、延伸提問、她的回應。
  有設定 Supabase 時存在雲端資料表 `learning_entries`，沒設定時存在 `data/learning_log.json`。
- **打勾完成與連續天數**：今天還沒打勾時，連續天數會算到昨天為止。
- **看書是 14 天的書籍追蹤**（第四部分 4.3），不是每日一課：
  - 第一階段一次問一個問題（書名、作者、章數、頁數、章節標題），可以直接貼整份目錄，
    接著用固定的 14 天演算法分配章節，可以用聊天或按鈕微調相鄰兩天的份量，確認後開始。
  - 第二階段每天讀完回來用自己的話分享，教練判斷有沒有讀懂：通過才打勾、進到下一天；
    一次讀了好幾天就一天一天確認；全部讀完會有具體的總結。隨時可以換書。
  - 章節分配和進度由程式精確計算（`coach/books.py`），AI 只負責理解她的分享、整理太亂的目錄、
    把「第3天想少一點」這類要求換成調整動作。
- **學習紀錄頁面**：目前／最長連續天數、最近四週打勾表、各主題目前難度和離下一級還差幾次、
  每一次課程的內容、延伸提問與想法（可以補打勾、補寫想法），以及備份下載和匯入。
- **追問不用六個區塊**：只有當天第一次上課用完整格式，之後的追問用自然對話回答
  （說明寫在 `coach/core.py` 的 `FOLLOWUP_NOTE`）。

## 檔案結構

- `streamlit_app.py`：進入點，負責共用設定和兩個頁面的切換。
- `views/daily.py`：每日學習（上課和追問）。
- `views/records.py`：學習紀錄。
- `coach/books.py`：看書的設定流程、14 天分配和驗收邏輯；`coach/reading.py`：看書的畫面；
  `coach/llm.py`：呼叫 Groq。
- `coach/core.py`：排程、難度、連續天數等邏輯；`coach/storage.py`：紀錄存在 Supabase 或檔案；
  `coach/ui.py`：頁面共用的小工具。
- `supabase/schema.sql`：建立所有 Supabase 資料表的 SQL；`supabase/books.sql`：只建立看書用的資料表。

## 在 Streamlit Cloud 部署

1. 到 https://share.streamlit.io 按 **Create app** → 選這個 repo。
2. Branch 選 `main`，Main file path 填 `streamlit_app.py`。
3. 在 **Advanced settings → Secrets** 貼上：
   ```toml
   GROQ_API_KEY = "你的 Groq API key"
   ```
4. 按 **Deploy**。

## 測試版

給測試者用的測試版，請照 [`docs/測試版部署.md`](docs/測試版部署.md) 另外部署：
同一份程式碼，接另一個 Supabase 專案、用另一組密碼，測試資料才不會混進真實紀錄。

## 密碼（必填）

app 的網址是公開的，所以打開時要先輸入密碼，沒輸入之前不會讀取任何紀錄。
在 Streamlit 的 Settings → Secrets 加上 `APP_PASSWORD = "你的密碼"`；沒設定的話 app 會停在提示畫面。

## 把學習紀錄存到 Supabase

沒設定的話，紀錄存在 app 伺服器上，Streamlit Cloud 重新啟動時會被清掉。

1. 到 https://supabase.com 註冊並建立一個新專案（Free 方案即可）。
2. 左邊選 **SQL Editor**，貼上 `supabase/schema.sql` 的內容，按 **Run**。
   （之前已經執行過舊版 schema.sql 的話，只要再執行 `supabase/books.sql`，建立看書用的資料表。）
   （之前已經建好資料表的話，再執行 `supabase/followups.sql` 和 `supabase/kickoff.sql`，
   讓課程之後的追問對話、開頭的完整訊息也存起來。）
3. 到 **Project Settings → API Keys**，複製 **secret key**（`sb_secret_` 開頭）；
   在 **Project Settings → Data API**（或專案首頁）複製 **Project URL**。
4. 在 Streamlit 的 app **Settings → Secrets** 加上：
   ```toml
   SUPABASE_URL = "https://你的專案.supabase.co"
   SUPABASE_KEY = "sb_secret_..."
   ```
5. 如果之前已經有紀錄，先在「學習紀錄」頁下載備份，設定好之後再用「匯入學習紀錄」匯入。

資料表開啟了 RLS 而且沒有任何 policy，所以只有放在 Streamlit Secrets 裡的 secret key 讀寫得到。
已經建好的資料庫請再執行一次 `supabase/harden.sql`（收回公開角色的權限，最後會列出檢查結果）。
secret key 等同資料庫密碼，不要放進程式碼或傳給別人。

## 在自己電腦上跑

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # 填入 API key
streamlit run streamlit_app.py
```

也可以不建 `secrets.toml`，改設環境變數 `GROQ_API_KEY`，或打開 app 後在側邊欄輸入。

## 可調整的環境變數

| 變數 | 預設 | 用途 |
| --- | --- | --- |
| `GROQ_API_KEY` | — | Groq API key |
| `APP_PASSWORD` | — | 打開 app 要輸入的密碼（必填） |
| `COACH_TIMEZONE` | `Asia/Taipei` | 決定「今天」是哪一天 |
| `SUPABASE_URL` / `SUPABASE_KEY` | — | 設定後學習紀錄改存 Supabase |
| `COACH_LOG_PATH` | `data/learning_log.json` | 沒設定 Supabase 時的紀錄檔位置 |

## 測試

```bash
pip install pytest
python -m pytest tests
```
