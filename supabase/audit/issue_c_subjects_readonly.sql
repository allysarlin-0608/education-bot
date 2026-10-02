-- Issue C: does any stored subject setting contradict itself? READ ONLY.
-- TEST database only. Run in Supabase → SQL Editor. It changes nothing: the
-- transaction is read-only (any write would fail) and is rolled back at the end.
-- One table of results: check, user_id, detail. No rows = nothing to fix.
--
-- The one source of truth is user_settings.subjects (coach/settings.py
-- chosen_subjects); subject_levels holds each subject's starting level and
-- may keep a removed subject's level on purpose, so adding it back restores it.

begin;
set transaction read only;

with s as (
  select user_id, subjects, subject_levels, onboarded_at from public.user_settings
),
chosen as (
  select s.user_id, t.value as subject from s, jsonb_array_elements_text(case jsonb_typeof(s.subjects) when 'array' then s.subjects else '[]' end) as t(value)
),
levels as (
  select s.user_id, l.key as subject, l.value as level from s, jsonb_each_text(case jsonb_typeof(s.subject_levels) when 'object' then s.subject_levels else '{}' end) as l(key, value)
)
-- 1. a subject the app doesn't know (the app ignores it: chosen_subjects filters it out)
select '1 unknown subject in subjects' as check, user_id, subject as detail
from chosen
where subject not in ('philosophy', 'cosmos', 'investing', 'business', 'fashion', 'jewelry', 'free')
union all
-- 2. the same subject listed twice
select '2 subject listed twice', user_id, subject || ' ×' || count(*)
from chosen group by user_id, subject having count(*) > 1
union all
-- 3. a chosen subject with no starting level (the app starts it at Beginner)
select '3 chosen subject without a level', c.user_id, c.subject
from chosen c left join levels l on l.user_id = c.user_id and l.subject = c.subject
where l.subject is null
union all
-- 4. a level that isn't Beginner / Intermediate / Advanced (the app ignores it)
select '4 unknown level value', user_id, subject || ' = ' || level
from levels where level not in ('Beginner', 'Intermediate', 'Advanced')
union all
-- 5. finished set-up but no subjects (the table's check should prevent it)
select '5 onboarded with no subjects', user_id, onboarded_at::text
from s where onboarded_at is not null and jsonb_array_length(subjects) = 0
union all
-- 6. not a list / not an object (the app reads them as empty)
select '6 malformed column', user_id,
       'subjects is ' || jsonb_typeof(subjects) || ', subject_levels is ' || jsonb_typeof(subject_levels)
from public.user_settings
where jsonb_typeof(subjects) <> 'array' or jsonb_typeof(subject_levels) <> 'object'
union all
-- 7. for information, not an error: a level kept for a subject not chosen now
--    (kept on purpose; the UI shows levels only for chosen subjects)
select '7 (info) level kept for a subject not chosen', l.user_id, l.subject || ' = ' || l.level
from levels l left join chosen c on c.user_id = l.user_id and c.subject = l.subject
where c.subject is null
order by 1, 2, 3;

rollback;
