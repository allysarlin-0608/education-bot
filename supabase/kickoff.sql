-- 把課程開頭她說的完整內容（包括「我今天特別想了解：…」）也存起來。已經建好資料表的話，執行這一份就好。
alter table public.learning_entries
  add column if not exists kickoff text not null default '';
