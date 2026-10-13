-- ============================================================================
-- Audit: how often the AI made people wait or failed them, so the Groq plan
-- can be checked before more people are invited. TEST database only. Run
-- after reports.sql.
-- One transaction: all of it applies, or none. Adds only: no existing table,
-- row or function is changed or deleted.
--
-- What it does:
--   1. ai_waits: per person, per day, how many AI calls were "busy" (she
--      was told to try again), "failed", or "slow" (answered, but after
--      more than 15 seconds). Counts only: no lesson text, no question, no
--      answer. Nobody reads or writes the table directly: the app adds
--      through add_ai_wait(), admins read through ai_health_summary(). Her
--      rows are deleted with her account (on delete cascade from auth.users),
--      so delete_my_account() stays as it is.
--   2. add_ai_wait(kind): adds one for the signed-in person, on the server's
--      day (Taipei). At most 500 a day per person.
--   3. ai_health_summary(since): for admins only: AI calls answered (from
--      ai_usage), and how many were busy, failed or slow, how many people
--      met each, and the same day by day.
-- ============================================================================
begin;

-- 1. the counts -----------------------------------------------------------------
create table if not exists public.ai_waits (
  user_id uuid not null references auth.users(id) on delete cascade,
  day date not null,
  kind text not null check (kind in ('busy', 'failed', 'slow')),
  count integer not null default 1 check (count between 0 and 500),
  primary key (user_id, day, kind)
);
alter table public.ai_waits enable row level security;
-- (no policies: only the two functions below reach it)
revoke all on public.ai_waits from anon, authenticated;

-- 2. adding one -------------------------------------------------------------------
create or replace function public.add_ai_wait(p_kind text)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  insert into public.ai_waits as w (user_id, day, kind, count)
  values (uid, (now() at time zone 'Asia/Taipei')::date, p_kind, 1)
  on conflict (user_id, day, kind) do update
    set count = least(w.count + 1, 500);
end;
$$;

-- 3. the numbers, for admins -----------------------------------------------------------
create or replace function public.ai_health_summary(p_since date)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare result jsonb;
begin
  if not coalesce(public.is_app_admin(), false) then raise exception 'admins only'; end if;
  select jsonb_build_object(
    'answered', coalesce((select sum(request_count) from public.ai_usage where date >= p_since), 0),
    'by_kind', coalesce((select jsonb_object_agg(kind, n) from (
                 select kind, sum(count) as n from public.ai_waits where day >= p_since group by kind) k), '{}'::jsonb),
    'people', coalesce((select jsonb_object_agg(kind, n) from (
                 select kind, count(distinct user_id) as n from public.ai_waits where day >= p_since group by kind) k),
               '{}'::jsonb),
    'days', coalesce((select jsonb_agg(d order by d->>'day') from (
                 select jsonb_build_object('day', day, 'busy', sum(count) filter (where kind = 'busy'),
                                           'failed', sum(count) filter (where kind = 'failed'),
                                           'slow', sum(count) filter (where kind = 'slow')) as d
                 from public.ai_waits where day >= p_since group by day) t), '[]'::jsonb)
  ) into result;
  return result;
end;
$$;

revoke all on function public.add_ai_wait(text) from public, anon;
grant execute on function public.add_ai_wait(text) to authenticated;
revoke all on function public.ai_health_summary(date) from public, anon;
grant execute on function public.ai_health_summary(date) to authenticated;

commit;

-- check: the new table, with row level security on
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'ai_waits';
