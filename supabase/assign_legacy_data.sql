-- ============================================================================
-- Migration 2 of 2: give the test app's old data ('test-user-1') to YOUR account.
-- For the TEST database only. Run it AFTER migration 1 (multiuser.sql) and
-- AFTER you have signed in once with Google (so your row exists in users).
--
-- Before running: replace you@example.com below with your Google email.
-- One transaction: if your email isn't found, it stops with an error and
-- nothing changes. Where your new account already has a row for the same
-- day/topic, book or settings, the old 'test-user-1' row wins (it's your real
-- history) and the new one is replaced.
-- ============================================================================
begin;

do $$
declare
  v_email text := lower('you@example.com');   -- ← your Google email
  v_uid text;
  v_old text;
begin
  select user_id into v_uid from public.users where email = v_email;
  if v_uid is null then
    raise exception 'No account for %: sign in to the test app once with that Google account, then run this again.', v_email;
  end if;

  -- learning log (lessons, quizzes): old rows replace new ones for the same day/topic
  delete from public.learning_entries n
   using public.learning_entries o
   where n.user_id = v_uid and o.user_id = 'test-user-1'
     and n.date = o.date and n.topic = o.topic;
  update public.learning_entries set user_id = v_uid where user_id = 'test-user-1';

  -- books
  delete from public.reading_books n
   using public.reading_books o
   where n.user_id = v_uid and o.user_id = 'test-user-1' and n.id = o.id;
  update public.reading_books set user_id = v_uid where user_id = 'test-user-1';

  -- settings (one row per person). The test app's row is 'test-user-1'
  -- (its COACH_USER_ID); if COACH_USER_ID was never set it is 'owner'.
  select user_id into v_old from public.user_settings
   where user_id in ('test-user-1', 'owner')
   order by (user_id = 'test-user-1') desc limit 1;
  if v_old is not null then
    delete from public.user_settings where user_id = v_uid;
    update public.user_settings set user_id = v_uid where user_id = v_old;
  end if;

  -- AI usage: add the counts together for the same day
  insert into public.ai_usage as u (user_id, date, request_count, token_count)
    select v_uid, date, request_count, token_count from public.ai_usage where user_id = 'test-user-1'
  on conflict (user_id, date) do update
    set request_count = u.request_count + excluded.request_count,
        token_count = u.token_count + excluded.token_count;
  delete from public.ai_usage where user_id = 'test-user-1';

  raise notice 'Moved test-user-1''s data to % (%).', v_email, v_uid;
end $$;

commit;

-- Check (run after): 'test-user-1' should have 0 rows everywhere.
select 'learning_entries' as t, count(*) from public.learning_entries where user_id = 'test-user-1'
union all select 'reading_books', count(*) from public.reading_books where user_id = 'test-user-1'
union all select 'user_settings', count(*) from public.user_settings where user_id in ('test-user-1', 'owner')
union all select 'ai_usage', count(*) from public.ai_usage where user_id = 'test-user-1';
