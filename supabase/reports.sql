-- ============================================================================
-- Audit stage 2: "Report a problem" on a lesson or a quiz question, and the
-- numbers that say how often it happens. TEST database only. Run after
-- mastery.sql.
-- One transaction: all of it applies, or none. Adds only: no existing table,
-- row or function is changed or deleted.
--
-- What it does:
--   1. content_reports: one row per report (which lesson, which question,
--      the reason, her optional note). Nobody reads or writes the table
--      directly: a learner adds through add_content_report(), admins read
--      through content_reports_summary(). Her reports are deleted with her
--      account (on delete cascade from auth.users), so delete_my_account()
--      stays as it is.
--   2. add_content_report(...): adds one report for the signed-in person,
--      on the server's clock. At most 30 a day per person.
--   3. content_reports_summary(since): for admins only: how many reports,
--      by reason, per 100 lessons passed, and the latest 20 (never who sent them).
-- ============================================================================
begin;

-- 1. the reports ----------------------------------------------------------------
create table if not exists public.content_reports (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  topic text not null check (length(topic) between 1 and 40),
  lesson_no integer not null check (lesson_no between 1 and 1000),
  lesson_title text not null default '' check (length(lesson_title) <= 200),
  kind text not null check (kind in ('lesson', 'question')),
  reason text not null check (reason in ('wrong', 'unclear', 'not_taught', 'other')),
  excerpt text not null default '' check (length(excerpt) <= 600),
  note text not null default '' check (length(note) <= 500)
);
alter table public.content_reports enable row level security;
-- (no policies: only the two functions below reach it)
revoke all on public.content_reports from anon, authenticated;

-- 2. adding one --------------------------------------------------------------------
create or replace function public.add_content_report(p_topic text, p_lesson_no integer, p_lesson_title text,
                                                     p_kind text, p_reason text, p_excerpt text, p_note text)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  if (select count(*) from public.content_reports
      where user_id = uid and created_at > now() - interval '1 day') >= 30 then
    raise exception 'too many reports today';
  end if;
  insert into public.content_reports (user_id, topic, lesson_no, lesson_title, kind, reason, excerpt, note)
  values (uid, p_topic, p_lesson_no, left(coalesce(p_lesson_title, ''), 200), p_kind, p_reason,
          left(coalesce(p_excerpt, ''), 600), left(coalesce(p_note, ''), 500));
end;
$$;

-- 3. the numbers, for admins -----------------------------------------------------------
create or replace function public.content_reports_summary(p_since date)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare result jsonb;
begin
  if not public.is_app_admin() then raise exception 'admins only'; end if;
  select jsonb_build_object(
    'reports', (select count(*) from public.content_reports
                where (created_at at time zone 'Asia/Taipei')::date >= p_since),
    'by_reason', coalesce((select jsonb_object_agg(reason, n) from (
                   select reason, count(*) as n from public.content_reports
                   where (created_at at time zone 'Asia/Taipei')::date >= p_since group by reason) r), '{}'::jsonb),
    'lessons_passed', coalesce((select sum(count) from public.usage_events
                                where event = 'lesson_passed' and day >= p_since), 0),
    'recent', coalesce((select jsonb_agg(x order by x->>'at' desc) from (
                select jsonb_build_object('at', created_at, 'topic', topic, 'lesson_no', lesson_no,
                                          'lesson_title', lesson_title, 'kind', kind, 'reason', reason,
                                          'excerpt', excerpt, 'note', note) as x
                from public.content_reports
                where (created_at at time zone 'Asia/Taipei')::date >= p_since
                order by created_at desc limit 20) t), '[]'::jsonb)
  ) into result;
  return result;
end;
$$;

revoke all on function public.add_content_report(text, integer, text, text, text, text, text) from public, anon;
grant execute on function public.add_content_report(text, integer, text, text, text, text, text) to authenticated;
revoke all on function public.content_reports_summary(date) from public, anon;
grant execute on function public.content_reports_summary(date) to authenticated;

commit;

-- check: the new table, with row level security on
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'content_reports';
