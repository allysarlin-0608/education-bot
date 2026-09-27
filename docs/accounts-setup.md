# 測試版帳號系統設定（Supabase Auth：Google + Email 密碼）

只給**測試版**（`dev` 分支、測試用 Supabase）。正式版不設 `APP_MODE`，一切照舊用 `APP_PASSWORD`。

下面的 `<專案代碼>` 是測試 Supabase 專案網址裡那一串，例如 `https://abcdefgh.supabase.co` 的 `abcdefgh`
（Project Settings → General → Project ID）。
測試版網址：`https://education-bot-fgcmwuszrzyybm5eduumkb.streamlit.app`

---

## 1. 資料庫（測試專案的 SQL Editor）

1. 跑 `supabase/accounts.sql`（RLS 規則、管理員表、函式、邀請檢查 hook）。
   跑完最後會列出 7 張表，`rls_enabled` 全部是 `true`。
2. 先不要跑 `supabase/map_user_ids.sql`，等第 6 步。

## 2. Supabase → Authentication

1. **Sign In / Providers → Email**
   - Enable Email provider：開
   - **Confirm email：開**（沒點確認信的人不能登入）
   - Minimum password length：**7**
   - Save
2. **Sign In / Providers → Google**
   - Enable：開
   - Client IDs：貼上 Google 用戶端 ID
   - Client Secret：貼上 Google 用戶端密鑰
   - 這頁會顯示 **Callback URL**：`https://<專案代碼>.supabase.co/auth/v1/callback`，複製起來（第 3 步用）
   - Save
3. **URL Configuration**
   - Site URL：`https://education-bot-fgcmwuszrzyybm5eduumkb.streamlit.app`
   - Redirect URLs → Add URL：
     `https://education-bot-fgcmwuszrzyybm5eduumkb.streamlit.app/~/+/auth/**`
4. **Emails → Templates**（只改這兩封的連結，其他文字可以照自己的意思）
   - **Confirm signup**，內容換成：
     ```html
     <h2>Confirm your email</h2>
     <p>Follow this link to finish creating your GNOSIS account:</p>
     <p><a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=email">Confirm your email</a></p>
     ```
   - **Reset Password**，內容換成：
     ```html
     <h2>Reset your password</h2>
     <p>Follow this link to choose a new password for GNOSIS:</p>
     <p><a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=recovery">Choose a new password</a></p>
     ```
   為什麼：Streamlit 的伺服器讀不到網址 `#` 後面的東西，所以連結改成 `?token_hash=`，由 app 的伺服器驗證。
5. **Hooks → Add hook → Before User Created**
   - Hook type：Postgres
   - Schema：`public`，Function：`hook_before_user_created`
   - Enable → Save
   這樣不在邀請名單（或管理員）裡的 email，連帳號都不會建立。

## 3. Google Cloud（之前建好的 GNOSIS 用戶端）

https://console.cloud.google.com/auth/clients → 點 `GNOSIS test` →
「已授權的重新導向 URI」→ **新增 URI**：`https://<專案代碼>.supabase.co/auth/v1/callback` → 儲存。
（之前那條 `…streamlit.app/oauth2callback` 可以刪掉，不刪也沒關係。）

## 4. Streamlit 測試版 Secrets

share.streamlit.io → 測試版 → ⋮ → Settings → Secrets，整份換成（值自己填，不要貼給任何人）：

```toml
APP_MODE = "public"
APP_URL = "https://education-bot-fgcmwuszrzyybm5eduumkb.streamlit.app"
GROQ_API_KEY = "你的 Groq key"
SUPABASE_URL = "https://<專案代碼>.supabase.co"
SUPABASE_KEY = "sb_publishable_..."      # 注意：publishable key，不是 secret key
AI_DAILY_REQUEST_LIMIT = 80              # 選填
AI_DAILY_TOKEN_LIMIT = 150000            # 選填

[auth]
cookie_secret = "一串 40 字以上、只有你知道的隨機英數字"
expose_tokens = "access"
```

- `SUPABASE_KEY` 在 Project Settings → API Keys → **Publishable key**（`sb_publishable_` 開頭）。
  如果誤貼成 secret key，app 會拒絕啟動並提示，因為那把 key 會繞過資料庫的保護。
- `[auth]` 一定放最後。之前的 `client_id`、`client_secret`、`redirect_uri`、`server_metadata_url` 都不用了。
- 不再需要 `APP_PASSWORD`、`ADMIN_EMAILS`（管理員改在資料庫的 `app_admins` 表，`accounts.sql` 已放入你的 email）。

Save → **Reboot app**。

## 5. 試一次

1. 打開測試版 → 看到 GNOSIS 登入頁（Continue with Google / Email / Password）。
2. 按 **Continue with Google** 用你的 Gmail 登入 → 你是管理員，會進入設定流程。
3. Settings → Invites 加入測試者的 email（Google 的 Test users 也要加）。

## 6. 舊資料對應（只有之前真的有人用 st.login 版登入過才需要）

1. 把 `supabase/map_user_ids.sql` 裡的 `you@example.com`（兩處）換成你的 Gmail。
2. **先只跑 PART A（dry run）**，把結果截圖給 Claude 看。它只讀不改。
3. 確認後再跑 PART B。不會刪任何資料；對不上的列會留在原地並在最後列出。

## 7. 寄信：Resend（建議，之後再做也可以）

Supabase 內建寄信一小時只能寄幾封，只適合開發。換成 Resend：

1. https://resend.com 註冊 → **Domains → Add Domain**，加一個你自己的網域（例如 `gnosis.xxx`），
   照畫面把 DNS 紀錄加到網域商，等 Verified。
   （沒有自己的網域時，Resend 只能寄給你自己的信箱，給測試者用不了。）
2. **API Keys → Create API Key**（Sending access），複製。
3. Supabase → Authentication → **Emails → SMTP Settings** → Enable Custom SMTP：
   - Sender email：`no-reply@你的網域`，Sender name：`GNOSIS`
   - Host：`smtp.resend.com`，Port：`465`
   - Username：`resend`，Password：剛剛的 API key
   - Save
4. Authentication → **Rate Limits**：把「emails per hour」調高（例如 30）。

寄信完全由 Supabase 負責，app 的程式和 Secrets 都不用改。

## 常見問題

| 看到 | 原因 |
| --- | --- |
| Google 顯示 `redirect_uri_mismatch` | 第 3 步的 Supabase Callback URL 沒加到 Google 用戶端 |
| 按 Google 後回到登入頁，顯示 Sign-in didn't complete | 在 Google 按了取消，或第 2-3 步 Redirect URLs 沒加 |
| 註冊後一直收不到信 | 內建寄信額度用完（等一小時）或還沒設 Resend；也看看垃圾信件匣 |
| 信裡的連結打開顯示 link has expired | 連結用過了或過期（1 小時），在登入頁重新要一封 |
| 登入後看到 invite-only | 這個 email 不在 Invites，也不在 `app_admins` |
| The app isn't set up correctly: … publishable key | `SUPABASE_KEY` 貼成了 secret key |
