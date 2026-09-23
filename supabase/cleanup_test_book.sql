-- 清理：測試時留下、設定到一半的《人類大歷史》（第1章的標題是一整串「第1章 測試一、第2章 測試二……」）。
-- 條件很窄：書名是人類大歷史、還在設定階段（setup / planning）、而且第1章標題裡面含有「第2章」。
-- 真的在讀的同名書（狀態是 reading / finished / switched）不會被選到。

-- 第 1 步：先只執行這一段，確認列出來的就是那一筆（應該只有 1 筆）。
select id,
       data->>'title'  as title,
       data->>'status' as status,
       left(data->'chapters'->>0, 40) as chapter_1
from public.reading_books
where data->>'title' = '人類大歷史'
  and data->>'status' in ('setup', 'planning')
  and data->'chapters'->>0 like '%第2章%';

-- 第 2 步：確認沒問題，再執行這一段刪除。
delete from public.reading_books
where data->>'title' = '人類大歷史'
  and data->>'status' in ('setup', 'planning')
  and data->'chapters'->>0 like '%第2章%';
