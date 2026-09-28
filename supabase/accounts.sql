-- ============================================================================
-- Accounts with Supabase Auth (APP_MODE=public). TEST database only.
-- Run after multiuser.sql. One transaction: all of it applies, or none.
--
-- What it does:
--   1. users gets avatar_url (the profile picture from Google).
--   2. app_admins: who may manage invitations. Your email is added.
--   3. Row level security policies: each signed-in person reads and writes
--      only their own rows (user_id = their Supabase user id). The app now
--      uses the publishable key plus the person's own token, so these
--      policies are what actually keeps people apart.
--   4. ai_usage: a person can read their count; only add_ai_usage adds to it.
--   5. allowed_users: a person can see whether they themselves are invited;
--      admins can see, add and remove everyone.
--   6. Functions the app calls, each acting only on the caller (auth.uid()):
--        add_ai_usage(date, requests, tokens)
--        delete_my_account()   everything of theirs + their sign-in account
--   7. hook_before_user_created: Supabase Auth calls it before making any new
--      account (email sign-up or first Google sign-in); an email that isn't
--      invited (or an admin) is refused, so no account and no data exist.
--      Turn it on in Authentication → Hooks (see docs/accounts-setup.md).
-- Nothing is deleted.
-- ============================================================================
begin;

-- 1. profile picture ----------------------------------------------------------
alter table public.users add column if not exists avatar_url text not null default '';

-- 2. admins ------------------------------------------------------------------
create table if not exists public.app_admins (
  email text primary key check (email = lower(email))
);
insert into public.app_admins (email) values ('allysarlin@gmail.com') on conflict do nothing;

create or replace function public.my_email() returns text
language sql stable
set search_path = ''
as $$ select lower(coalesce(auth.jwt() ->> 'email', '')) $$;

-- security definer: reads app_admins without going through its own policies
create or replace function public.is_app_admin() returns boolean
language sql stable security definer
set search_path = ''
as $$ select exists (select 1 from public.app_admins where email = public.my_email()) $$;

-- 3. each person, their own rows -------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['learning_entries', 'reading_books', 'user_settings', 'users'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists own_rows on public.%I', t);
    execute format('create policy own_rows on public.%I for all to authenticated '
                   'using (user_id = (select auth.uid())::text) '
                   'with check (user_id = (select auth.uid())::text)', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
  end loop;
end $$;

-- 4. AI usage: read your own; only add_ai_usage writes --------------------------
alter table public.ai_usage enable row level security;
drop policy if exists own_usage on public.ai_usage;
create policy own_usage on public.ai_usage for select to authenticated
  using (user_id = (select auth.uid())::text);
grant select on public.ai_usage to authenticated;

-- 5. invitations -------------------------------------------------------------
alter table public.allowed_users enable row level security;
drop policy if exists see_invite on public.allowed_users;
create policy see_invite on public.allowed_users for select to authenticated
  using (email = public.my_email() or public.is_app_admin());
drop policy if exists admins_add on public.allowed_users;
create policy admins_add on public.allowed_users for insert to authenticated
  with check (public.is_app_admin());
drop policy if exists admins_change on public.allowed_users;
create policy admins_change on public.allowed_users for update to authenticated
  using (public.is_app_admin()) with check (public.is_app_admin());
drop policy if exists admins_remove on public.allowed_users;
create policy admins_remove on public.allowed_users for delete to authenticated
  using (public.is_app_admin());
grant select, insert, update, delete on public.allowed_users to authenticated;

alter table public.app_admins enable row level security;
drop policy if exists see_self on public.app_admins;
create policy see_self on public.app_admins for select to authenticated
  using (email = public.my_email());
grant select on public.app_admins to authenticated;

revoke all on public.learning_entries, public.reading_books, public.user_settings, public.users,
              public.allowed_users, public.ai_usage, public.app_admins from anon;

-- 6. functions that act only on the caller -------------------------------------
drop function if exists public.add_ai_usage(text, date, integer, integer);
drop function if exists public.delete_user_data(text);

create or replace function public.add_ai_usage(p_date date, p_requests integer, p_tokens integer)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  insert into public.ai_usage as u (user_id, date, request_count, token_count)
  values (uid::text, p_date, greatest(p_requests, 0), greatest(p_tokens, 0))
  on conflict (user_id, date) do update
    set request_count = u.request_count + excluded.request_count,
        token_count = u.token_count + excluded.token_count;
end;
$$;

-- one transaction: if any delete fails, none happen
create or replace function public.delete_my_account()
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  delete from public.learning_entries where user_id = uid::text;
  delete from public.reading_books where user_id = uid::text;
  delete from public.user_settings where user_id = uid::text;
  delete from public.ai_usage where user_id = uid::text;
  delete from public.users where user_id = uid::text;
  delete from auth.users where id = uid;
end;
$$;

revoke all on function public.add_ai_usage(date, integer, integer) from public, anon;
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.add_ai_usage(date, integer, integer) to authenticated;
grant execute on function public.delete_my_account() to authenticated;
revoke all on function public.is_app_admin() from public, anon;
grant execute on function public.is_app_admin() to authenticated;
grant execute on function public.my_email() to authenticated;

-- 7. only invited emails can make an account -------------------------------------
create or replace function public.hook_before_user_created(event jsonb)
returns jsonb
language plpgsql security definer
set search_path = ''
as $$
declare e text := lower(coalesce(event -> 'user' ->> 'email', ''));
begin
  if e <> '' and (exists (select 1 from public.allowed_users where email = e)
                  or exists (select 1 from public.app_admins where email = e)) then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('error', jsonb_build_object('http_code', 403, 'message', 'not_invited'));
end;
$$;
revoke all on function public.hook_before_user_created(jsonb) from public, anon, authenticated;
grant usage on schema public to supabase_auth_admin;      -- needed to call a function in public
grant execute on function public.hook_before_user_created(jsonb) to supabase_auth_admin;

commit;

-- Check (run after): every row should say rls_enabled = true, and each table its policies.
select c.relname as table_name, c.relrowsecurity as rls_enabled,
       (select string_agg(p.polname, ', ' order by p.polname) from pg_policy p where p.polrelid = c.oid) as policies
from pg_class c join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
where c.relname in ('learning_entries', 'reading_books', 'user_settings', 'users', 'allowed_users', 'ai_usage', 'app_admins')
order by 1;
