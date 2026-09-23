-- 看書進度追蹤用的資料表。已經執行過 schema.sql 的話，只要再執行這一份。
create table public.reading_books (
  id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.reading_books enable row level security;
grant select, insert, update, delete on public.reading_books to service_role;
