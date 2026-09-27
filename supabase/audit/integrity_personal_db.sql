-- ============================================================================
-- Data integrity checks for the PERSONAL database (APP_MODE=personal).
-- For you to run; the audit never connects to this database.
-- READ ONLY: every statement is a SELECT, inside a read-only transaction.
-- Run in Supabase → SQL Editor. Each check returns: check | problems | example
-- problems = 0 everywhere means the data is consistent.
-- (If a check says a table doesn't exist, that part of the app was never set
--  up there; delete that block and run the rest.)
-- ============================================================================
begin transaction read only;

with checks as (

  -- 1. Dates
  select 'learning_entries dated in the future (> today + 1)' as check_name,
         count(*) as problems, min(date::text) as example
  from public.learning_entries where date > current_date + 1

  -- 2. Entries: shape and consistency
  union all
  select 'entries whose lessons is not a JSON array', count(*), min(date::text)
  from public.learning_entries where jsonb_typeof(lessons) <> 'array'
  union all
  select 'entries with session_number < 1', count(*), min(date::text)
  from public.learning_entries where session_number < 1
  union all
  select 'entries with an unknown topic', count(*), min(topic)
  from public.learning_entries
  where topic not in ('philosophy', 'cosmos', 'investing', 'business', 'fashion', 'jewelry', 'free', 'reading')
  union all
  select 'entries with an unknown level (old Chinese names are fine: 入門/中階/進階)', count(*), min(level)
  from public.learning_entries
  where level not in ('Beginner', 'Intermediate', 'Advanced', '入門', '中階', '進階')
  union all
  select 'entries marked completed with a lesson not passed', count(*), min(date::text)
  from public.learning_entries
  where completed and jsonb_typeof(lessons) = 'array' and jsonb_array_length(lessons) > 0
    and exists (select 1 from jsonb_array_elements(lessons) s where coalesce((s ->> 'completed')::boolean, false) = false)
  union all
  select 'entries not completed although every lesson passed', count(*), min(date::text)
  from public.learning_entries
  where not completed and jsonb_typeof(lessons) = 'array' and jsonb_array_length(lessons) > 0
    and not exists (select 1 from jsonb_array_elements(lessons) s where coalesce((s ->> 'completed')::boolean, false) = false)
  union all
  select 'entries with the same lesson number twice', count(*), min(date::text)
  from public.learning_entries
  where jsonb_typeof(lessons) = 'array'
    and (select count(*) from jsonb_array_elements(lessons)) <>
        (select count(distinct s ->> 'n') from jsonb_array_elements(lessons) s)
  union all
  select 'quiz scores outside 0-100', count(*), min(e.date::text)
  from public.learning_entries e, jsonb_array_elements(case when jsonb_typeof(e.lessons) = 'array' then e.lessons else '[]' end) s
  where jsonb_typeof(s -> 'quiz') = 'object'
    and ((s -> 'quiz' ->> 'score')::numeric not between 0 and 100 or (s -> 'quiz' ->> 'best')::numeric not between 0 and 100)
  union all
  select 'the same lesson number passed on two different days (same subject)', count(*), min(k)
  from (
    select e.topic || ' #' || (s ->> 'n') as k
    from public.learning_entries e, jsonb_array_elements(case when jsonb_typeof(e.lessons) = 'array' then e.lessons else '[]' end) s
    where coalesce((s ->> 'completed')::boolean, false)
    group by 1 having count(distinct e.date) > 1
  ) d

  -- 3. Books
  union all
  select 'books whose data.id differs from the row id', count(*), min(id)
  from public.reading_books where data ->> 'id' is distinct from id
  union all
  select 'books with an unknown status', count(*), min(data ->> 'status')
  from public.reading_books where data ->> 'status' not in ('setup', 'planning', 'reading', 'finished', 'switched')
  union all
  select 'books being read with a plan that is not 14 days', count(*), min(id)
  from public.reading_books
  where data ->> 'status' in ('reading', 'finished')
    and (jsonb_typeof(data -> 'plan') <> 'array' or jsonb_array_length(data -> 'plan') <> 14)
  union all
  select 'more than one book being read', greatest(count(*) - 1, 0), min(id)
  from public.reading_books where data ->> 'status' = 'reading'

  -- 4. Security settings
  union all
  select 'app tables without row level security', count(*), min(c.relname)
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r'
    and c.relname in ('learning_entries', 'reading_books', 'user_settings')
    and not c.relrowsecurity
  union all
  select 'anon or authenticated role can use an app table', count(*), min(grantee || ' ' || table_name)
  from information_schema.role_table_grants
  where grantee in ('anon', 'authenticated') and table_schema = 'public'
    and table_name in ('learning_entries', 'reading_books', 'user_settings')
)
select check_name as "check", problems, example from checks order by problems desc, check_name;

rollback;
