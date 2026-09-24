-- 固定課綱（一天 5 堂課）需要的欄位：把當天每一堂課的內容和完成狀態存起來。
-- 到 Supabase 的 SQL Editor 執行一次就好。
alter table public.learning_entries
  add column if not exists lessons jsonb not null default '[]'::jsonb;
