-- ============================================================================
-- Data integrity checks for the TEST database (APP_MODE=public, accounts).
-- READ ONLY: every statement is a SELECT, inside a read-only transaction.
-- Run in Supabase → SQL Editor. Each check returns one row:
--   check | problems | example
-- problems = 0 everywhere means the data is consistent.
-- ============================================================================
begin transaction read only;

with checks as (

  -- 1. Rows whose owner has no sign-in account (left behind by a deletion)
  select 'orphan learning_entries (no auth user)' as check_name,
         count(*) as problems, min(e.user_id || ' ' || e.date) as example
  from public.learning_entries e
  where not exists (select 1 from auth.users u where u.id::text = e.user_id)
  union all
  select 'orphan reading_books (no auth user)', count(*), min(b.user_id || ' ' || b.id)
  from public.reading_books b
  where not exists (select 1 from auth.users u where u.id::text = b.user_id)
  union all
  select 'orphan user_settings (no auth user)', count(*), min(s.user_id)
  from public.user_settings s
  where not exists (select 1 from auth.users u where u.id::text = s.user_id)
  union all
  select 'orphan ai_usage (no auth user)', count(*), min(a.user_id || ' ' || a.date)
  from public.ai_usage a
  where not exists (select 1 from auth.users u where u.id::text = a.user_id)
  union all
  select 'orphan public.users (no auth user)', count(*), min(p.user_id || ' ' || p.email)
  from public.users p
  where not exists (select 1 from auth.users u where u.id::text = p.user_id)
  union all
  select 'auth users without public.users row (never opened the app: info)', count(*), min(u.email)
  from auth.users u
  where not exists (select 1 from public.users p where p.user_id = u.id::text)

  -- 2. Dates
  union all
  select 'learning_entries dated in the future (> today + 1, any time zone)', count(*), min(user_id || ' ' || date)
  from public.learning_entries where date > current_date + 1
  union all
  select 'ai_usage dated in the future', count(*), min(user_id || ' ' || date)
  from public.ai_usage where date > current_date + 1

  -- 3. Entries: shape and consistency
  union all
  select 'entries whose lessons is not a JSON array', count(*), min(user_id || ' ' || date)
  from public.learning_entries where jsonb_typeof(lessons) <> 'array'
  union all
  select 'entries with session_number < 1', count(*), min(user_id || ' ' || date)
  from public.learning_entries where session_number < 1
  union all
  select 'entries with an unknown topic', count(*), min(topic)
  from public.learning_entries
  where topic not in ('philosophy', 'cosmos', 'investing', 'business', 'fashion', 'jewelry', 'free', 'reading')
  union all
  select 'entries with an unknown level', count(*), min(level)
  from public.learning_entries where level not in ('Beginner', 'Intermediate', 'Advanced')
  union all
  select 'entries marked completed with a lesson not passed', count(*), min(user_id || ' ' || date)
  from public.learning_entries
  where completed and jsonb_typeof(lessons) = 'array' and jsonb_array_length(lessons) > 0
    and exists (select 1 from jsonb_array_elements(lessons) s where coalesce((s ->> 'completed')::boolean, false) = false)
  union all
  select 'entries not completed although every lesson passed', count(*), min(user_id || ' ' || date)
  from public.learning_entries
  where not completed and jsonb_typeof(lessons) = 'array' and jsonb_array_length(lessons) > 0
    and not exists (select 1 from jsonb_array_elements(lessons) s where coalesce((s ->> 'completed')::boolean, false) = false)
  union all
  select 'entries with the same lesson number twice', count(*), min(user_id || ' ' || date)
  from public.learning_entries e
  where jsonb_typeof(lessons) = 'array'
    and (select count(*) from jsonb_array_elements(lessons)) <>
        (select count(distinct s ->> 'n') from jsonb_array_elements(lessons) s)
  union all
  select 'lessons passed without a passing quiz score (>= 80)', count(*), min(e.user_id || ' ' || e.date || ' #' || (s ->> 'n'))
  from public.learning_entries e, jsonb_array_elements(case when jsonb_typeof(e.lessons) = 'array' then e.lessons else '[]' end) s
  where coalesce((s ->> 'completed')::boolean, false)
    and s -> 'quiz' is not null and jsonb_typeof(s -> 'quiz') = 'object'
    and coalesce((s -> 'quiz' ->> 'best')::int, (s -> 'quiz' ->> 'score')::int, 0) < 80
  union all
  select 'quiz scores outside 0-100', count(*), min(e.user_id || ' ' || e.date)
  from public.learning_entries e, jsonb_array_elements(case when jsonb_typeof(e.lessons) = 'array' then e.lessons else '[]' end) s
  where jsonb_typeof(s -> 'quiz') = 'object'
    and ((s -> 'quiz' ->> 'score')::numeric not between 0 and 100 or (s -> 'quiz' ->> 'best')::numeric not between 0 and 100)
  union all
  select 'the same lesson number passed on two different days (same person, subject)', count(*), min(k)
  from (
    select e.user_id || ' ' || e.topic || ' #' || (s ->> 'n') as k
    from public.learning_entries e, jsonb_array_elements(case when jsonb_typeof(e.lessons) = 'array' then e.lessons else '[]' end) s
    where coalesce((s ->> 'completed')::boolean, false)
    group by 1 having count(distinct e.date) > 1
  ) d

  -- 4. Books
  union all
  select 'books whose data.id differs from the row id', count(*), min(user_id || ' ' || id)
  from public.reading_books where data ->> 'id' is distinct from id
  union all
  select 'books with an unknown status', count(*), min(data ->> 'status')
  from public.reading_books where data ->> 'status' not in ('setup', 'planning', 'reading', 'finished', 'switched')
  union all
  select 'books being read with a plan that is not 14 days', count(*), min(user_id || ' ' || id)
  from public.reading_books
  where data ->> 'status' in ('reading', 'finished')
    and (jsonb_typeof(data -> 'plan') <> 'array' or jsonb_array_length(data -> 'plan') <> 14)
  union all
  select 'more than one book being read by the same person', count(*), min(user_id)
  from (select user_id from public.reading_books where data ->> 'status' = 'reading'
        group by user_id having count(*) > 1) r
  union all
  select 'finished books without a finished_on date', count(*), min(user_id || ' ' || id)
  from public.reading_books where data ->> 'status' = 'finished' and coalesce(data ->> 'finished_on', '') = ''

  -- 5. Settings
  union all
  select 'settings with 0 or more than 3 subjects after setup', count(*), min(user_id)
  from public.user_settings
  where onboarded_at is not null and (jsonb_array_length(subjects) = 0 or jsonb_array_length(subjects) > 3)
  union all
  select 'settings with an unknown subject', count(*), min(user_id)
  from public.user_settings s, jsonb_array_elements_text(s.subjects) t
  where t not in ('philosophy', 'cosmos', 'investing', 'business', 'fashion', 'jewelry', 'free')
  union all
  select 'people with lessons but no finished setup', count(*), min(e.user_id)
  from (select distinct user_id from public.learning_entries) e
  left join public.user_settings s on s.user_id = e.user_id
  where s.onboarded_at is null

  -- 6. AI usage
  union all
  select 'ai_usage with negative counts', count(*), min(user_id || ' ' || date)
  from public.ai_usage where request_count < 0 or token_count < 0

  -- 7. Invitations and admins
  union all
  select 'invites not in lower case', count(*), min(email) from public.allowed_users where email <> lower(email)
  union all
  select 'accounts whose email is neither invited nor admin (info: invited earlier, since removed)', count(*), min(u.email)
  from auth.users u
  where not exists (select 1 from public.allowed_users a where a.email = lower(u.email))
    and not exists (select 1 from public.app_admins m where m.email = lower(u.email))

  -- 8. Security settings
  union all
  select 'app tables without row level security', count(*), min(c.relname)
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r'
    and c.relname in ('learning_entries', 'reading_books', 'user_settings', 'users', 'ai_usage', 'allowed_users', 'app_admins')
    and not c.relrowsecurity
  union all
  select 'anon role can use an app table', count(*), min(table_name)
  from information_schema.role_table_grants
  where grantee = 'anon' and table_schema = 'public'
    and table_name in ('learning_entries', 'reading_books', 'user_settings', 'users', 'ai_usage', 'allowed_users', 'app_admins')
  union all
  select 'old functions still present (delete_user_data, 4-argument add_ai_usage)', count(*), min(p.proname)
  from pg_proc p join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and (p.proname = 'delete_user_data' or (p.proname = 'add_ai_usage' and p.pronargs = 4))
)
select check_name as "check", problems, example from checks order by problems desc, check_name;

rollback;
