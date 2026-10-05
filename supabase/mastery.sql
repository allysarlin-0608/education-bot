-- ============================================================================
-- Phase 3: is she learning? TEST database only. Run after goals.sql.
-- One transaction: all of it applies, or none. Adds only: no existing row is
-- changed or deleted. (What she knows, idea by idea, is kept with her lessons
-- in learning_entries, as before: no new table is needed for it.)
--
-- What it does:
--   1. learning_signals: per person, per day, how many times something about
--      learning happened ("missed", "recovered", "held", "slipped",
--      "mastered", "practice_done", "explained", "tutor_question",
--      "tutor_confused"). Only the name and a count: no answer, no
--      question, nothing she wrote. A person reads only their own; only
--      add_learning_signal() adds, on the server's date.
--   2. gnosis_metrics(since): the same numbers as before, plus the totals of
--      these, for admins only.
--   3. delete_my_account() also deletes her learning_signals rows (the same
--      function as before, with one line added).
-- ============================================================================
begin;

-- 1. learning signals ------------------------------------------------------------
create table if not exists public.learning_signals (
  user_id text not null,
  day date not null,
  event text not null check (event in ('missed', 'recovered', 'held', 'slipped', 'mastered',
                                       'practice_done', 'explained', 'tutor_question', 'tutor_confused')),
  count integer not null default 1 check (count >= 0),
  primary key (user_id, day, event)
);
alter table public.learning_signals enable row level security;
drop policy if exists own_signals on public.learning_signals;
create policy own_signals on public.learning_signals for select to authenticated
  using (user_id = (select auth.uid())::text);
revoke all on public.learning_signals from anon;
grant select on public.learning_signals to authenticated;

create or replace function public.add_learning_signal(p_event text)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  insert into public.learning_signals as s (user_id, day, event, count)
  values (uid::text, (now() at time zone 'Asia/Taipei')::date, p_event, 1)
  on conflict (user_id, day, event) do update set count = s.count + 1;
end;
$$;

-- 2. the numbers, for admins ---------------------------------------------------
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
  ), sig as (
    select s.event, sum(s.count) as n from public.learning_signals s where s.day >= p_since group by 1
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
    'lessons_per_learner_week', (select coalesce(round(avg(lessons)::numeric, 1), 0) from weeks),
    'reminders_shown', (select coalesce(sum(e.count), 0) from public.usage_events e
                        where e.event = 'reminder_shown' and e.day >= p_since),
    'reminded_sessions', (select coalesce(sum(e.count), 0) from public.usage_events e
                          where e.event = 'reminded_session' and e.day >= p_since),
    'practice_done', (select coalesce(sum(n), 0) from sig where event = 'practice_done'),
    'explained', (select coalesce(sum(n), 0) from sig where event = 'explained'),
    'tutor_question', (select coalesce(sum(n), 0) from sig where event = 'tutor_question'),
    'tutor_confused', (select coalesce(sum(n), 0) from sig where event = 'tutor_confused'),
    'missed', (select coalesce(sum(n), 0) from sig where event = 'missed'),
    'recovered', (select coalesce(sum(n), 0) from sig where event = 'recovered'),
    'held', (select coalesce(sum(n), 0) from sig where event = 'held'),
    'slipped', (select coalesce(sum(n), 0) from sig where event = 'slipped'),
    'mastered', (select coalesce(sum(n), 0) from sig where event = 'mastered')
  ) into result;
  return result;
end;
$$;

-- 3. deleting an account deletes these too --------------------------------------
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
  delete from public.learning_signals where user_id = uid::text;
  delete from public.learner_prefs where user_id = uid::text;
  delete from public.user_settings where user_id = uid::text;
  delete from public.ai_usage where user_id = uid::text;
  delete from public.users where user_id = uid::text;
  delete from auth.users where id = uid;
end;
$$;

revoke all on function public.add_learning_signal(text) from public, anon;
grant execute on function public.add_learning_signal(text) to authenticated;
revoke all on function public.gnosis_metrics(date) from public, anon;
grant execute on function public.gnosis_metrics(date) to authenticated;
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;

commit;

-- check: the new table, with row level security on
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'learning_signals';
