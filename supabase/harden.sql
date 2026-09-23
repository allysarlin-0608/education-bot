-- 資料安全：確認只有 app 自己（secret key）能讀寫。可以重複執行，不會刪任何資料。
alter table public.learning_entries enable row level security;
alter table public.reading_books enable row level security;
revoke all on public.learning_entries from anon, authenticated;
revoke all on public.reading_books from anon, authenticated;
grant select, insert, update, delete on public.learning_entries to service_role;
grant select, insert, update, delete on public.reading_books to service_role;

-- 檢查：兩個資料表的 rls_enabled 都要是 true，policies 都要是 0。
select c.relname as table_name,
       c.relrowsecurity as rls_enabled,
       (select count(*) from pg_policies p where p.tablename = c.relname) as policies
from pg_class c
where c.relname in ('learning_entries', 'reading_books');
