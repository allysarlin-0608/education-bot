-- ============================================================================
-- 重置一個帳號的進度（只用在「測試版」資料庫）：
-- 刪掉這個帳號的課程紀錄、測驗、複習卡、練習、熟練度、閱讀進度、自己的目標、
-- 科目設定和提醒設定。下次登入會從「開始設定」的第一個畫面重新開始。
-- 保留：帳號本身（可以照常登入）、今天的 AI 用量（每日上限照算）、
--       管理員看的統計次數（只是次數，沒有內容）。
--
-- 要換別的帳號，把兩個步驟裡的 email 都改掉。
-- 請分兩步執行：先跑「第 1 步」（只看，不改任何東西），確認數字合理，再跑「第 2 步」。
-- 第 2 步是一次做完的：中間出錯就什麼都不會刪。刪掉就救不回來。
-- ============================================================================


-- ============================================================
-- 第 1 步：預覽（只讀）——會被刪掉的筆數
-- ============================================================
with me as (select id::text as uid from auth.users where lower(email) = lower('allysarlin@gmail.com'))
select 'learning_entries' as table_name, count(*) from public.learning_entries where user_id = (select uid from me)
union all select 'reading_books', count(*) from public.reading_books where user_id = (select uid from me)
union all select 'learning_paths', count(*) from public.learning_paths where user_id = (select uid from me)
union all select 'user_settings', count(*) from public.user_settings where user_id = (select uid from me)
union all select 'learner_prefs', count(*) from public.learner_prefs where user_id = (select uid from me);


-- ============================================================
-- 第 2 步：刪除（確認第 1 步的數字後再跑）
-- ============================================================
begin;
create temporary table reset_me on commit drop as
  select id::text as uid from auth.users where lower(email) = lower('allysarlin@gmail.com');
do $$ begin
  if (select count(*) from reset_me) <> 1 then raise exception 'no such account: nothing deleted'; end if;
end $$;
delete from public.learning_entries where user_id = (select uid from reset_me);
delete from public.reading_books where user_id = (select uid from reset_me);
delete from public.learning_paths where user_id = (select uid from reset_me);
delete from public.user_settings where user_id = (select uid from reset_me);
delete from public.learner_prefs where user_id = (select uid from reset_me);
commit;
