-- ============================================================================
-- Fix: "Start learning" did nothing for someone who chose her own goal and
-- three subjects (ISS-061). The settings table still allowed 3 entries in
-- `subjects`, from before goals existed; a goal now counts there too
-- (3 subjects + up to 5 goals). The save was refused, and the message showed
-- at the top of the page, out of sight.
--
-- TEST database first. Changes one rule on one table; no row is changed or
-- deleted. One transaction.
-- ============================================================================
begin;
do $$
declare c text;
begin
  for c in select conname from pg_constraint
           where conrelid = 'public.user_settings'::regclass and contype = 'c'
             and pg_get_constraintdef(oid) like '%jsonb_array_length(subjects) <= 3%'
  loop
    execute format('alter table public.user_settings drop constraint %I', c);
  end loop;
end $$;
alter table public.user_settings drop constraint if exists user_settings_subjects_max;
alter table public.user_settings add constraint user_settings_subjects_max
  check (jsonb_array_length(subjects) <= 8);
commit;

-- check: the rule as it is now (expect: CHECK ((jsonb_array_length(subjects) <= 8)))
select conname, pg_get_constraintdef(oid) from pg_constraint
where conrelid = 'public.user_settings'::regclass and contype = 'c';
