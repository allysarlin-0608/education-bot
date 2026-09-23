-- 在 Supabase 的 SQL Editor 貼上並執行一次，建立學習紀錄的資料表。
create table public.learning_entries (
  date date not null,
  topic text not null,
  session_number integer not null,
  level text not null,
  completed boolean not null default false,
  title text not null default '',
  followup_question text not null default '',
  reflection text not null default '',
  lesson text not null default '',
  primary key (date, topic)
);
alter table public.learning_entries enable row level security;
grant select, insert, update, delete on public.learning_entries to service_role;
