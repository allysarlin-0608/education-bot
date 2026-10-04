-- ============================================================================
-- Phase 1: a learner's own goals, and the few numbers that say whether
-- GNOSIS works. TEST database only. Run after accounts.sql.
-- One transaction: all of it applies, or none. Adds only: no existing row is
-- changed or deleted.
--
-- What it does:
--   1. learning_paths: each learner's goals (the path the AI designed for
--      it). Each person reads and writes only their own rows.
--   2. usage_events: per person, per day, how many times something happened
--      ("visit", "setup_done", "goal_created", "lesson_passed"). No lesson
--      content, no answers, no goal text: only the event's name and a count.
--      A person can read their own; only add_usage_event() adds.
--   3. gnosis_metrics(since): the key numbers for people who signed up since
--      a date, for admins only (app_admins), as totals: never anyone's rows.
--   4. delete_my_account() also deletes the two new tables' rows (the same
--      function as before, with two lines added).
-- ============================================================================
begin;

-- 1. goals -------------------------------------------------------------------
create table if not exists public.learning_paths (
  user_id text not null default (auth.uid())::text,
  id text not null check (id ~ '^g-[0-9a-f]{8}$'),
  data jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, id)
);
alter table public.learning_paths enable row level security;
drop policy if exists own_rows on public.learning_paths;
create policy own_rows on public.learning_paths for all to authenticated
  using (user_id = (select auth.uid())::text)
  with check (user_id = (select auth.uid())::text);
revoke all on public.learning_paths from anon;
grant select, insert, update, delete on public.learning_paths to authenticated;

-- 2. usage events --------------------------------------------------------------
create table if not exists public.usage_events (
  user_id text not null,
  day date not null,
  event text not null check (event in ('visit', 'setup_done', 'goal_created', 'lesson_passed')),
  count integer not null default 1 check (count >= 0),
  primary key (user_id, day, event)
);
alter table public.usage_events enable row level security;
drop policy if exists own_events on public.usage_events;
create policy own_events on public.usage_events for select to authenticated
  using (user_id = (select auth.uid())::text);
revoke all on public.usage_events from anon;
grant select on public.usage_events to authenticated;

create or replace function public.add_usage_event(p_day date, p_event text)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  insert into public.usage_events as u (user_id, day, event, count)
  values (uid::text, p_day, p_event, 1)
  on conflict (user_id, day, event) do update
    set count = case when excluded.event = 'visit' then u.count else u.count + 1 end;
end;
$$;

-- 3. the numbers, for admins ---------------------------------------------------
create or replace function public.gnosis_metrics(p_since date)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare result jsonb;
begin
  if not public.is_app_admin() then raise exception 'admins only'; end if;
  with joined as (
    select u.user_id, (u.created_at at time zone 'Asia/Taipei')::date as day0
    from public.users u
    where (u.created_at at time zone 'Asia/Taipei')::date >= p_since
  ), per as (
    select j.user_id, j.day0,
      exists (select 1 from public.usage_events e where e.user_id = j.user_id and e.event in ('setup_done', 'goal_created')) as set_up,
      exists (select 1 from public.usage_events e where e.user_id = j.user_id and e.event = 'lesson_passed') as first_lesson,
      exists (select 1 from public.usage_events e where e.user_id = j.user_id and e.event = 'visit' and e.day = j.day0 + 1) as next_day,
      exists (select 1 from public.usage_events e where e.user_id = j.user_id and e.event = 'visit' and e.day >= j.day0 + 7) as after_week
    from joined j
  ), weeks as (
    select e.user_id, date_trunc('week', e.day)::date as week, sum(e.count) as lessons
    from public.usage_events e
    where e.event = 'lesson_passed' and e.day >= p_since
    group by 1, 2
  )
  select jsonb_build_object(
    'since', p_since,
    'signed_up', (select count(*) from per),
    'set_up', (select count(*) from per where set_up),
    'first_lesson', (select count(*) from per where first_lesson),
    'came_back_next_day', (select count(*) from per where next_day),
    'eligible_next_day', (select count(*) from per where day0 + 1 <= (now() at time zone 'Asia/Taipei')::date),
    'active_after_a_week', (select count(*) from per where after_week),
    'eligible_week', (select count(*) from per where day0 + 7 <= (now() at time zone 'Asia/Taipei')::date),
    'lessons_per_learner_week', (select coalesce(round(avg(lessons)::numeric, 1), 0) from weeks)
  ) into result;
  return result;
end;
$$;

-- 4. deleting an account deletes these too --------------------------------------
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
  delete from public.learning_paths where user_id = uid::text;
  delete from public.usage_events where user_id = uid::text;
  delete from public.user_settings where user_id = uid::text;
  delete from public.ai_usage where user_id = uid::text;
  delete from public.users where user_id = uid::text;
  delete from auth.users where id = uid;
end;
$$;

revoke all on function public.add_usage_event(date, text) from public, anon;
grant execute on function public.add_usage_event(date, text) to authenticated;
revoke all on function public.gnosis_metrics(date) from public, anon;
grant execute on function public.gnosis_metrics(date) to authenticated;
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;

commit;

-- check: both tables with row level security on
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in ('learning_paths', 'usage_events')
order by 1;
