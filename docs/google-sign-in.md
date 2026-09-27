# 測試版：用 Google 登入（APP_MODE = "public"）

只給**測試版**用。正式版不設 `APP_MODE`（或設 `"personal"`），一切照舊，繼續用 `APP_PASSWORD`。
登入交給 Streamlit 內建的 `st.login()`（OIDC），app 本身不處理、不儲存任何密碼。

## 0. 先準備

- 測試版的網址，例如 `https://allysa-coach-test.streamlit.app`（下面都用這個當例子，換成你的）。
- 測試用 Supabase 已經跑過 `supabase/multiuser.sql`（見第 4 步）。

## 1. Google Cloud Console：建專案、設同意畫面

1. 到 https://console.cloud.google.com/ ，最上方專案選單 → **New project**，名字例如 `GNOSIS`（只有你看得到） → **Create**，建好後切到這個專案。
2. 左側選單 → **APIs & Services → OAuth consent screen**（新版介面叫 **Google Auth Platform**），按 **Get started**：
   - App name：`GNOSIS`（測試者登入時會看到）
   - User support email：你的 Gmail
   - Audience：**External**
   - Contact information：你的 Gmail
   - 勾同意條款 → **Create**
3. **Audience** 頁面：Publishing status 保持 **Testing**。在 **Test users** 按 **Add users**，把 5–10 位測試者的 Gmail 加進去（Testing 狀態下最多 100 人，只有名單上的人能完成 Google 登入）。
   > 這是 Google 這一層的名單；app 裡還有自己的邀請名單（第 5 步），兩邊都要有。
4. **Data Access**（Scopes）：按 **Add or remove scopes**，勾 `openid`、`.../auth/userinfo.email`、`.../auth/userinfo.profile` → **Update** → **Save**。這三個都是基本權限，不需要 Google 審核。

## 2. 建 OAuth 用戶端（拿 client_id / client_secret）

1. **APIs & Services → Credentials**（或 Google Auth Platform → **Clients**）→ **Create credentials → OAuth client ID**。
2. Application type：**Web application**，Name：`streamlit-test`。
3. **Authorized redirect URIs** → **Add URI**，填（一個字都不能差，結尾沒有斜線）：
   ```
   https://allysa-coach-test.streamlit.app/oauth2callback
   ```
   要在自己電腦跑的話再加一條 `http://localhost:8501/oauth2callback`。
4. **Create**。畫面會顯示 **Client ID** 和 **Client secret**，按下載 JSON 或先複製起來（secret 之後只能重新產生，不能再看）。

## 3. Streamlit 測試版的 Secrets

share.streamlit.io → 測試版 app → **⋮ → Settings → Secrets**。保留原本的 `GROQ_API_KEY`、`SUPABASE_URL`、`SUPABASE_KEY`（測試專案的），再加：

```toml
APP_MODE = "public"
ADMIN_EMAILS = "你的gmail@gmail.com"          # 多個用逗號分開；管理員不受邀請名單和 AI 用量限制
AI_DAILY_REQUEST_LIMIT = 80                    # 選填，每人每天 AI 次數，預設 80
AI_DAILY_TOKEN_LIMIT = 150000                  # 選填，每人每天 tokens，預設 150000

[auth]
redirect_uri = "https://allysa-coach-test.streamlit.app/oauth2callback"
cookie_secret = "一串隨機長字串"
client_id = "xxxxxxxx.apps.googleusercontent.com"
client_secret = "GOCSPX-xxxxxxxx"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

- `cookie_secret`：自己產生一串隨機字，例如在終端機跑 `python -c "import secrets; print(secrets.token_hex(32))"`，貼上就好，不用記。
- `APP_PASSWORD` 在 public 模式用不到，留著也沒關係。
- **`[auth]` 一定要放在最後**：TOML 裡 `[auth]` 之後的每一行都算在 `[auth]` 裡面。
- 按 **Save**，再按 **Reboot app**。

## 4. 測試 Supabase：跑 migration

在**測試專案**的 SQL Editor（再三確認不是正式專案）：

1. 跑 `supabase/multiuser.sql`：加 user_id 欄位、建 users / allowed_users / ai_usage、兩個函式、開 RLS。
2. 用你的 Google 帳號登入測試版一次（你在 `ADMIN_EMAILS` 裡，所以不用先被邀請），這樣 users 表裡才有你。
3. 把 `supabase/assign_legacy_data.sql` 裡的 `you@example.com` 換成你的 Gmail，再跑，舊的 `test-user-1` 資料就歸到你的帳號。

## 5. 邀請測試者

用管理員帳號登入 → 右上角頭像 → **Settings** → **Invites**：輸入 email（大小寫都可以，會存成小寫）→ **Invite**。
按 **Remove** 移除，對方下一個動作就會看到「This app is invite-only for now…」，但資料會留著。

也要記得把同一個 email 加到第 1 步 Google 的 **Test users**。

## 常見問題

| 看到 | 原因 |
| --- | --- |
| Google 顯示 `redirect_uri_mismatch` | 第 2 步的 URI 和 secrets 的 `redirect_uri` 不完全一樣（http/https、結尾斜線、網址名） |
| Google 顯示「存取遭拒 / 應用程式尚未完成驗證」 | 這個 Gmail 不在第 1 步的 **Test users** |
| App 顯示 “Sign-in isn't set up yet” | secrets 沒有 `[auth]`，或 `[auth]` 後面還接了其他設定 |
| App 顯示 “Sign-in didn't complete” | 在 Google 那邊按了取消或出錯，再按一次 Continue with Google |
| 登入後看到 invite-only | 這個 email 不在 app 的 Invites 名單，也不在 `ADMIN_EMAILS` |
