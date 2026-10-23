-- ============================================================================
-- The learning-system redesign (docs/LEARNING_DESIGN.md, ISS-110): measuring
-- learning, and a shared bank of checked questions. TEST database only. Run
-- after reports.sql.
-- One transaction: all of it applies, or none. Adds only: no existing table,
-- row or function is changed or deleted.
--
-- What it does:
--   1. learning_attempts: one row per answer (coach/attempts.py): the day,
--      which idea (subject or goal id, lesson number), where and what kind
--      of exercise, the score, first try or not, how sure she said she was,
--      seconds taken, days since she last practised the idea, the
--      experiment arms. Never the question, her answer or anything she
--      wrote. Deleted with her account (on delete cascade).
--      add_learning_attempts(rows): adds hers (at most 40 a call, 3000 a day).
--      my_learning_attempts(): hers, for her data export.
--      learning_attempts_since(since): admins only, for the learning
--      dashboard; who is never given, only a stand-in (an md5 of the id) so
--      one learner's answers can be followed over time; a goal of hers is
--      named only as "goal:" and a stand-in too (a built-in subject by name).
--   2. shared_items: checked questions on the math curriculum's units (the
--      goal's diagnostic, testing out of a unit), shared by every learner
--      so each is written once (coach/itembank.py). A question reported by
--      two people is no longer given out.
--      shared_items_for(curriculum, lang, units), add_shared_items(...),
--      report_shared_item(id).
-- ============================================================================
begin;

-- 1. answers --------------------------------------------------------------------
create table if not exists public.learning_attempts (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  day date not null,
  topic text not null check (length(topic) between 1 and 60),
  n integer not null check (n between 0 and 100000),
  ctx text not null check (ctx in ('warmup', 'check', 'guided', 'quiz', 'mixed', 'practice', 'review', 'unit',
                                   'diag', 'jol', 'explain', 'step')),
  kind text not null check (length(kind) between 1 and 20),
  score real check (score between 0 and 1),
  first boolean not null default true,
  conf smallint check (conf between 1 and 3),
  secs integer check (secs between 0 and 3600),
  gap integer check (gap between 0 and 10000),
  diff smallint check (diff between 1 and 3),
  variant text not null default '' check (length(variant) <= 120)
);
create index if not exists learning_attempts_day on public.learning_attempts (day);
alter table public.learning_attempts enable row level security;
-- (no policies: only the functions below reach it)
revoke all on public.learning_attempts from anon, authenticated;

create or replace function public.add_learning_attempts(p_rows jsonb)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) > 40 then
    raise exception 'between 0 and 40 rows';
  end if;
  if (select count(*) from public.learning_attempts
      where user_id = uid and created_at > now() - interval '1 day') + jsonb_array_length(p_rows) > 3000 then
    raise exception 'too many answers today';
  end if;
  insert into public.learning_attempts (user_id, day, topic, n, ctx, kind, score, first, conf, secs, gap, diff, variant)
  select uid, (r->>'day')::date, r->>'topic', (r->>'n')::integer, r->>'ctx', r->>'kind',
         (r->>'score')::real, coalesce((r->>'first')::boolean, true), (r->>'conf')::smallint,
         (r->>'secs')::integer, (r->>'gap')::integer, (r->>'diff')::smallint, coalesce(r->>'variant', '')
  from jsonb_array_elements(p_rows) as r;
end;
$$;

create or replace function public.my_learning_attempts()
returns jsonb
language sql stable security definer
set search_path = ''
as $$
  select coalesce(jsonb_agg(jsonb_build_object('day', day, 'topic', topic, 'n', n, 'ctx', ctx, 'kind', kind,
                                               'score', score, 'first', first, 'conf', conf, 'secs', secs,
                                               'gap', gap, 'diff', diff, 'variant', variant) order by id), '[]'::jsonb)
  from public.learning_attempts where user_id = auth.uid();
$$;

create or replace function public.learning_attempts_since(p_since date)
returns jsonb
language plpgsql stable security definer
set search_path = ''
as $$
declare result jsonb;
begin
  if not public.is_app_admin() then raise exception 'admins only'; end if;
  select coalesce(jsonb_agg(x), '[]'::jsonb) into result from (
    select jsonb_build_object('learner', md5(user_id::text), 'day', day, 'topic', case when topic ~ '^[a-z]{2,20}$' then topic else 'goal:' || left(md5(topic), 8) end, 'n', n,
                              'ctx', ctx, 'kind', kind, 'score', score, 'first', first, 'conf', conf,
                              'secs', secs, 'gap', gap, 'diff', diff, 'variant', variant) as x
    from public.learning_attempts where day >= p_since order by id limit 50000) t;
  return result;
end;
$$;

revoke all on function public.add_learning_attempts(jsonb) from public, anon;
grant execute on function public.add_learning_attempts(jsonb) to authenticated;
revoke all on function public.my_learning_attempts() from public, anon;
grant execute on function public.my_learning_attempts() to authenticated;
revoke all on function public.learning_attempts_since(date) from public, anon;
grant execute on function public.learning_attempts_since(date) to authenticated;

-- 2. the shared bank of checked questions ----------------------------------------------
create table if not exists public.shared_items (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  created_by uuid references auth.users(id) on delete set null,
  curriculum text not null check (length(curriculum) between 1 and 80),
  unit text not null check (length(unit) between 1 and 40),
  lang text not null check (length(lang) between 2 and 12),
  item jsonb not null check (length(item::text) <= 4000),
  reports integer not null default 0
);
create index if not exists shared_items_lookup on public.shared_items (curriculum, lang, unit);
create table if not exists public.shared_item_reports (
  item_id bigint not null references public.shared_items(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  primary key (item_id, user_id)
);
alter table public.shared_items enable row level security;
alter table public.shared_item_reports enable row level security;
revoke all on public.shared_items from anon, authenticated;
revoke all on public.shared_item_reports from anon, authenticated;

create or replace function public.shared_items_for(p_curriculum text, p_lang text, p_units text[])
returns jsonb
language sql stable security definer
set search_path = ''
as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', id, 'unit', unit, 'item', item) order by id), '[]'::jsonb)
  from (select id, unit, item from public.shared_items
        where curriculum = p_curriculum and lang = p_lang and unit = any(p_units) and reports < 2
        order by id limit 400) t;
$$;

create or replace function public.add_shared_items(p_curriculum text, p_lang text, p_rows jsonb)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) > 20 then
    raise exception 'between 0 and 20 rows';
  end if;
  if (select count(*) from public.shared_items
      where created_by = uid and created_at > now() - interval '1 day') + jsonb_array_length(p_rows) > 60 then
    raise exception 'too many questions today';
  end if;
  insert into public.shared_items (created_by, curriculum, unit, lang, item)
  select uid, p_curriculum, r->>'unit', p_lang, r->'item' from jsonb_array_elements(p_rows) as r;
end;
$$;

create or replace function public.report_shared_item(p_id bigint)
returns void
language plpgsql security definer
set search_path = ''
as $$
declare uid uuid := auth.uid();
begin
  if uid is null then raise exception 'not signed in'; end if;
  insert into public.shared_item_reports (item_id, user_id) values (p_id, uid) on conflict do nothing;
  if found then
    update public.shared_items set reports = reports + 1 where id = p_id;
  end if;
end;
$$;

revoke all on function public.shared_items_for(text, text, text[]) from public, anon;
grant execute on function public.shared_items_for(text, text, text[]) to authenticated;
revoke all on function public.add_shared_items(text, text, jsonb) from public, anon;
grant execute on function public.add_shared_items(text, text, jsonb) to authenticated;
revoke all on function public.report_shared_item(bigint) from public, anon;
grant execute on function public.report_shared_item(bigint) to authenticated;

commit;

-- check: the new tables, with row level security on
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname in ('learning_attempts', 'shared_items', 'shared_item_reports');
