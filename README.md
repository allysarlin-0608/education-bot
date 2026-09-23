# 每日學習教練（Daily Learning Coach）

Allysa 專屬的每日興趣學習教練：每天 15 到 20 分鐘，一個知識點、一個小任務。
用 Streamlit 做成，透過 Groq API 呼叫 AI 模型。

## 功能

- **完整系統指令**：`coach/system_prompt.md`，每次呼叫時會附上自動產生的學習紀錄摘要。
- **每週行程**：一／五 時尚、材質與珠寶 · 二 哲學 · 三／六 看書 · 四 宇宙學 · 日 自由主題。
  商業計劃、股票投資可以隨時手動選。
- **難度依主題分開計算**：同一主題第 1–3 次入門、第 4–7 次中階、第 8 次以後進階。
- **學習紀錄**：日期、主題、難度、是否完成、今日主題、延伸提問、她的回應，
  存在 `data/learning_log.json`，側邊欄可以下載備份和匯入。
- **打勾完成與連續天數**：今天還沒打勾時，連續天數會算到昨天為止。
- **學習紀錄頁面**：目前／最長連續天數、最近四週打勾表、各主題目前難度和離下一級還差幾次、
  每一次課程的內容、延伸提問與想法（可以補打勾、補寫想法），以及備份下載和匯入。
- **追問不用六個區塊**：只有當天第一次上課用完整格式，之後的追問用自然對話回答
  （說明寫在 `coach/core.py` 的 `FOLLOWUP_NOTE`）。

## 檔案結構

- `streamlit_app.py`：進入點，負責共用設定和兩個頁面的切換。
- `views/daily.py`：每日學習（上課和追問）。
- `views/records.py`：學習紀錄。
- `coach/core.py`：排程、難度、連續天數等邏輯；`coach/ui.py`：頁面共用的小工具。

## 在 Streamlit Cloud 部署

1. 到 https://share.streamlit.io 按 **Create app** → 選這個 repo。
2. Branch 選 `main`，Main file path 填 `streamlit_app.py`。
3. 在 **Advanced settings → Secrets** 貼上：
   ```toml
   GROQ_API_KEY = "你的 Groq API key"
   ```
4. 按 **Deploy**。

注意：Streamlit Cloud 重新啟動後，存在上面的學習紀錄會被清掉，
記得偶爾用側邊欄的「下載學習紀錄備份」存一份，需要時再匯入。

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
| `COACH_TIMEZONE` | `Asia/Taipei` | 決定「今天」是哪一天 |
| `COACH_LOG_PATH` | `data/learning_log.json` | 學習紀錄存放位置 |

## 測試

```bash
pip install pytest
python -m pytest tests
```
