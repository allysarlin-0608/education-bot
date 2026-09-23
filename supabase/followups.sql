-- 讓每天課程之後的追問對話也存起來（重新整理不會不見）。已經建好資料表的話，執行這一份就好。
alter table public.learning_entries
  add column if not exists followups jsonb not null default '[]'::jsonb;
