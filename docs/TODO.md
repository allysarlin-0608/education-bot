# 待辦清單（需要之後處理的事）

## B：程式碼庫公開、金鑰更換（先跳過）
- [ ] 把 GitHub 上的 education-bot 改成私有，並確認 Streamlit 兩個 app 仍能部署
- [ ] 更換曾在對話裡出現過的金鑰：Groq、Supabase secret key（測試專案）、Google OAuth client secret、cookie_secret
- 已確認（不需要你動手）：歷史紀錄裡沒有真正的金鑰；程式碼沒有寫死的金鑰；.gitignore 已排除 secrets.toml 和 .env

## M2：真實模型實測（這一階段不做）
- [ ] 之後如果測驗又出問題：到 Streamlit 的 Logs 找含 `quiz for` 的那幾行（成功會寫 `ready in X s`，失敗會寫原因和花了多久），貼給 Claude 判斷
- 工具已備好：tools/measure_quiz.py（需要測試用的 Groq key 放在環境變數）

## C：科目設定資料是否矛盾（不急）
- [ ] 這個環境沒有測試資料庫的權限，無法自己查。之後要查時，用唯讀的 supabase/audit/issue_c_subjects_readonly.sql
- 畫面上的顯示錯誤已修好（BUG-028）

## AI 每日使用上限
- [ ] 換成付費 AI 方案時，一起調整每人每天 80 次的上限（目前一次測驗約用 2–4 次）

## 寄信額度（註冊確認信、忘記密碼信）
- [ ] Supabase 內建寄信服務每小時只能寄約 2 封（整個專案共用），朋友一多就會收不到信
- 解法：在 Supabase 接上外部寄信服務（例如 Resend，免費方案每月 3,000 封、每天 100 封）；或請大家用 Google 登入（不需要寄信）

## 等你決定的設計建議
- [ ] Settings：上方大圖的科目展示，改成精簡清單（每個科目一行：名稱、程度、是否選擇），大圖留在各科目自己的頁面（點「Enter」就會看到）
- [ ] Progress：上方 5 個數字減為 3 個（目前連續、最長連續、通過的課數）；「完成天數、學習天數」移到月曆那一行
- [ ] 帳號安全：在 Settings 加「寄一封重設密碼的信給我」（目前只能從登入頁的「忘記密碼」做）
