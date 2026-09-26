-- 使用者設定（科目、每天的量、各科起始程度、要不要看書計畫）：每位使用者一列，一律用 user_id 讀寫。
-- 還沒執行這一份之前，app 照舊用原本固定的設定（每週幾一個科目、一天 5 堂、看書頁一直都在），不會出現設定流程。
-- 在 Supabase 的 SQL Editor 執行一次就好。
create table public.user_settings (
  user_id text primary key,
  subjects jsonb not null default '[]'::jsonb,
  units_per_day integer not null default 3 check (units_per_day in (1, 3, 5)),
  subject_levels jsonb not null default '{}'::jsonb,
  reading_enabled boolean not null default false,
  onboarding jsonb,
  onboarded_at timestamptz,
  updated_at timestamptz,
  check (jsonb_array_length(subjects) <= 3),
  check (onboarded_at is null or jsonb_array_length(subjects) >= 1)
);
alter table public.user_settings enable row level security;
revoke all on public.user_settings from anon, authenticated;
grant select, insert, update, delete on public.user_settings to service_role;
