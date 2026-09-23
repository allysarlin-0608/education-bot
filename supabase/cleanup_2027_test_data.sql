-- 清除測試資料：2027 年 1 月的全部課程紀錄，以及書《測試用的書》，
-- 並把剩下每一筆紀錄的「第幾次」和等級，依 app 的規則重新算回正確值
-- （同一主題依日期排序：第 1–3 次入門、第 4–7 次中階、第 8 次以後進階）。
--
-- 「完成天數」「最長連續」「各主題次數與進度條」都是 app 每次從剩下的紀錄即時算出來的，
-- 刪掉測試紀錄後就會自動恢復，不需要另外改。
--
-- 請分兩步執行：先執行「第 1 步」全部（只讀，不會改任何資料），確認沒問題再執行「第 2 步」。


-- ============================================================
-- 第 1 步：預覽（只讀）
-- ============================================================

-- 1a. 會被刪除的課程紀錄（2027-01-01 到 2027-01-31）
select date, topic, completed, left(title, 30) as title
from public.learning_entries
where date >= '2027-01-01' and date < '2027-02-01'
order by date, topic;

-- 1b. 會被刪除的書
select id, data->>'title' as title, data->>'status' as status, data->>'started_on' as started_on
from public.reading_books
where data->>'title' = '測試用的書';

-- 1c. 清除之後，每個主題的正確次數與等級（跟目前比較；清除後是 0 次的主題也會列出來）
with now_ as (
  select topic, count(*) as sessions_now from public.learning_entries group by topic
), kept as (
  select topic, count(*) as sessions, count(*) filter (where completed) as completed
  from public.learning_entries
  where not (date >= '2027-01-01' and date < '2027-02-01')
  group by topic
)
select n.topic,
       n.sessions_now                 as 目前上課次數,
       coalesce(k.sessions, 0)        as 清除後上課次數,
       coalesce(k.completed, 0)       as 清除後完成次數,
       case when coalesce(k.sessions, 0) = 0 then '還沒開始'
            when k.sessions <= 3 then '入門' when k.sessions <= 7 then '中階' else '進階' end as 清除後等級
from now_ n left join kept k using (topic)
order by n.topic;

-- 1d. 清除之後，「第幾次／等級」需要更正的紀錄（沒有列出來的就是已經正確）
with kept as (
  select * from public.learning_entries
  where not (date >= '2027-01-01' and date < '2027-02-01')
), renum as (
  select date, topic, session_number, level,
         row_number() over (partition by topic order by date) as n
  from kept
)
select date, topic,
       session_number as 目前第幾次, n as 更正為第幾次,
       level as 目前等級,
       case when n <= 3 then '入門' when n <= 7 then '中階' else '進階' end as 更正為等級
from renum
where session_number <> n
   or level <> case when n <= 3 then '入門' when n <= 7 then '中階' else '進階' end
order by topic, date;


-- ============================================================
-- 第 2 步：執行（在同一個交易裡，最後的 commit 之前隨時可以 rollback）
-- ============================================================

begin;

delete from public.learning_entries
where date >= '2027-01-01' and date < '2027-02-01';

delete from public.reading_books
where data->>'title' = '測試用的書';

with renum as (
  select date, topic, row_number() over (partition by topic order by date) as n
  from public.learning_entries
)
update public.learning_entries e
set session_number = r.n,
    level = case when r.n <= 3 then '入門' when r.n <= 7 then '中階' else '進階' end
from renum r
where e.date = r.date and e.topic = r.topic
  and (e.session_number <> r.n
       or e.level <> case when r.n <= 3 then '入門' when r.n <= 7 then '中階' else '進階' end);

-- 確認結果：數字應該跟第 1 步 1c 的「清除後」一樣，而且不會再有 2027 年的紀錄
select topic, count(*) as 上課次數, count(*) filter (where completed) as 完成次數, max(session_number) as 最大第幾次
from public.learning_entries group by topic order by topic;
select count(*) as 剩下的2027年紀錄 from public.learning_entries where date >= '2027-01-01';

commit;
