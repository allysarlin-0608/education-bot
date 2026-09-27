-- ============================================================================
-- Move learning data from the old ids to Supabase Auth user ids. TEST only.
-- Old ids: Google "sub" values (from the st.login version, found in users)
-- and 'test-user-1' (the test app's one user before accounts).
-- Each old id is matched by email to an account in auth.users.
-- Nothing is deleted. A row whose new owner already has a row with the same
-- key (same day and subject, same book, ...) stays where it is and is listed.
--
-- PART A is a dry run: it changes nothing. Run it first and check the list.
-- PART B does the move, in one transaction. Before running it, replace
-- you@example.com (twice) with the email that should own 'test-user-1'.
-- ============================================================================

-- ---------- PART A: dry run (read only) ----------
with old_ids as (
  select u.user_id as old_id, lower(u.email) as email
  from public.users u
  where u.user_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  union
  select 'test-user-1', lower('you@example.com')
),
mapped as (
  select o.old_id, o.email, a.id::text as new_id
  from old_ids o left join auth.users a on lower(a.email) = o.email
)
select m.old_id, m.email, coalesce(m.new_id, '(no account with this email yet)') as new_id,
       (select count(*) from public.learning_entries where user_id = m.old_id) as learning_entries,
       (select count(*) from public.reading_books where user_id = m.old_id) as reading_books,
       (select count(*) from public.user_settings where user_id = m.old_id) as user_settings,
       (select count(*) from public.ai_usage where user_id = m.old_id) as ai_usage,
       (select count(*) from public.users where user_id = m.old_id) as users,
       (select count(*) from public.learning_entries o join public.learning_entries n
          on n.user_id = m.new_id and n.date = o.date and n.topic = o.topic
        where o.user_id = m.old_id) as entries_that_would_stay
from mapped m
order by m.old_id;


-- ---------- PART B: the move (one transaction) ----------
begin;

create temporary table id_map on commit drop as
with old_ids as (
  select u.user_id as old_id, lower(u.email) as email
  from public.users u
  where u.user_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  union
  select 'test-user-1', lower('you@example.com')
)
select o.old_id, a.id::text as new_id
from old_ids o join auth.users a on lower(a.email) = o.email;

update public.learning_entries t set user_id = m.new_id
from id_map m
where t.user_id = m.old_id
  and not exists (select 1 from public.learning_entries n
                  where n.user_id = m.new_id and n.date = t.date and n.topic = t.topic);

update public.reading_books t set user_id = m.new_id
from id_map m
where t.user_id = m.old_id
  and not exists (select 1 from public.reading_books n where n.user_id = m.new_id and n.id = t.id);

update public.user_settings t set user_id = m.new_id
from id_map m
where t.user_id = m.old_id
  and not exists (select 1 from public.user_settings n where n.user_id = m.new_id);

update public.ai_usage t set user_id = m.new_id
from id_map m
where t.user_id = m.old_id
  and not exists (select 1 from public.ai_usage n where n.user_id = m.new_id and n.date = t.date);

update public.users t set user_id = m.new_id
from id_map m
where t.user_id = m.old_id
  and not exists (select 1 from public.users n where n.user_id = m.new_id);

commit;

-- Check (run after): rows still under an old id (0 everywhere unless something was listed above).
select 'learning_entries' as t, user_id, count(*) from public.learning_entries
  where user_id !~ '^[0-9a-f]{8}-' group by user_id
union all select 'reading_books', user_id, count(*) from public.reading_books where user_id !~ '^[0-9a-f]{8}-' group by user_id
union all select 'user_settings', user_id, count(*) from public.user_settings where user_id !~ '^[0-9a-f]{8}-' group by user_id
union all select 'ai_usage', user_id, count(*) from public.ai_usage where user_id !~ '^[0-9a-f]{8}-' group by user_id
union all select 'users', user_id, count(*) from public.users where user_id !~ '^[0-9a-f]{8}-' group by user_id;
