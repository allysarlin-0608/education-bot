-- ============================================================================
-- Migration 1 of 2: accounts and per-person data (APP_MODE=public).
-- For the TEST database only. Run once, in Supabase → SQL Editor.
-- Everything is in one transaction: it all applies, or none of it does.
--
-- What it does:
--   1. learning_entries and reading_books get a user_id column. Rows already
--      there (the test app's one user) are given 'test-user-1', and each
--      table's key becomes (user_id, …), so two people can have the same day
--      or the same book. user_settings already has user_id.
--   2. New tables: users, allowed_users (the invitation list), ai_usage.
--   3. Two functions the app calls:
--        add_ai_usage      adds to a person's count for a day (atomically)
--        delete_user_data  deletes everything of one person, in one transaction
--   4. Row level security on every table; only the app's secret key
--      (service_role) can read or write, as before.
-- ============================================================================
begin;

-- 1. user_id on the learning log and the books ------------------------------
alter table public.learning_entries add column if not exists user_id text;
update public.learning_entries set user_id = 'test-user-1' where user_id is null;
alter table public.learning_entries alter column user_id set not null;
alter table public.learning_entries drop constraint if exists learning_entries_pkey;
alter table public.learning_entries add primary key (user_id, date, topic);

alter table public.reading_books add column if not exists user_id text;
update public.reading_books set user_id = 'test-user-1' where user_id is null;
alter table public.reading_books alter column user_id set not null;
alter table public.reading_books drop constraint if exists reading_books_pkey;
alter table public.reading_books add primary key (user_id, id);

-- (user_settings: its key is already user_id; its row for the test app is
-- the one whose user_id is 'test-user-1')

-- 2. New tables ---------------------------------------------------------------
create table if not exists public.users (
  user_id text primary key,                 -- the Google sign-in's stable id (OIDC "sub")
  email text not null,
  display_name text not null default '',
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists public.allowed_users (
  email text primary key check (email = lower(email)),   -- always lower case
  invited_at timestamptz not null default now(),
  note text not null default ''
);

create table if not exists public.ai_usage (
  user_id text not null,
  date date not null,
  request_count integer not null default 0,
  token_count integer not null default 0,
  primary key (user_id, date)
);

-- 3. Functions ---------------------------------------------------------------
create or replace function public.add_ai_usage(p_user_id text, p_date date, p_requests integer, p_tokens integer)
returns void
language sql
as $$
  insert into public.ai_usage as u (user_id, date, request_count, token_count)
  values (p_user_id, p_date, p_requests, p_tokens)
  on conflict (user_id, date) do update
    set request_count = u.request_count + excluded.request_count,
        token_count = u.token_count + excluded.token_count;
$$;

-- A function runs as one transaction: if any delete fails, none happen.
create or replace function public.delete_user_data(p_user_id text)
returns void
language plpgsql
as $$
begin
  if p_user_id is null or p_user_id = '' then
    raise exception 'no user';
  end if;
  delete from public.learning_entries where user_id = p_user_id;
  delete from public.reading_books where user_id = p_user_id;
  delete from public.user_settings where user_id = p_user_id;
  delete from public.ai_usage where user_id = p_user_id;
  delete from public.users where user_id = p_user_id;
end;
$$;

-- 4. Only the app's secret key -----------------------------------------------
alter table public.learning_entries enable row level security;
alter table public.reading_books enable row level security;
alter table public.user_settings enable row level security;
alter table public.users enable row level security;
alter table public.allowed_users enable row level security;
alter table public.ai_usage enable row level security;

revoke all on public.learning_entries, public.reading_books, public.user_settings,
              public.users, public.allowed_users, public.ai_usage from anon, authenticated;
grant select, insert, update, delete on public.learning_entries, public.reading_books, public.user_settings,
              public.users, public.allowed_users, public.ai_usage to service_role;

revoke all on function public.add_ai_usage(text, date, integer, integer) from public, anon, authenticated;
revoke all on function public.delete_user_data(text) from public, anon, authenticated;
grant execute on function public.add_ai_usage(text, date, integer, integer) to service_role;
grant execute on function public.delete_user_data(text) to service_role;

commit;

-- Check (run after): every table should show rls_enabled = true.
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c
where c.relname in ('learning_entries', 'reading_books', 'user_settings', 'users', 'allowed_users', 'ai_usage')
order by 1;
