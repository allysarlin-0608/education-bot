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
