import json
from datetime import date

import streamlit as st

from coach import books, core, ui

log = st.session_state.coach_log
today = ui.today()

STATUS_MARK = {"done": "●", "started": "○", "none": "·", "future": ""}

st.markdown("## 學習紀錄")

if not log["entries"]:
    st.info("還沒有任何紀錄。上完第一課之後，這裡就會開始累積。")

# ============================================================
# OVERVIEW
# ============================================================
col1, col2, col3, col4 = st.columns(4)
col1.metric("目前連續", f"{core.current_streak(log, today)} 天")
col2.metric("最長連續", f"{core.longest_streak(log)} 天")
col3.metric("完成天數", f"{len(core.completed_dates(log))} 天")
col4.metric("上課次數", f"{len(log['entries'])} 次")

# ============================================================
# LAST FOUR WEEKS
# ============================================================
st.markdown("#### 最近四週")
weeks = core.calendar_weeks(log, today, weeks=4)
header = "| 週 | " + " | ".join(d[-1] for d in core.WEEKDAY_ZH) + " |"
rows = [header, "|" + " --- |" * 8]
for week in weeks:
    start = week[0][0]
    cells = [STATUS_MARK[status] for _, status in week]
    rows.append(f"| {start.month}/{start.day} | " + " | ".join(cells) + " |")
st.markdown("\n".join(rows))
st.caption("● 完成　○ 有上課、還沒打勾　· 沒有紀錄")

# ============================================================
# PER-TOPIC PROGRESS
# ============================================================
st.markdown("#### 各主題進度")
st.caption("等級看的是上課次數：同一主題上第 1–3 次是入門、第 4–7 次中階、第 8 次以後進階，有沒有打勾都算一次。")
for key, label in core.TOPICS.items():
    p = core.topic_progress(log, key)
    if p["sessions"] == 0:
        st.markdown(f"**{label}**　還沒開始")
        continue
    st.markdown(
        f"**{label}**　上課 {p['sessions']} 次（其中打勾 {p['completed']} 次）・目前 {p['level']}"
    )
    if p["next_level"]:
        st.progress(p["fraction"], text=f"再上 {p['remaining']} 次課進入{p['next_level']}")
    else:
        st.progress(1.0, text="已經到進階")

# ============================================================
# BOOKSHELF
# ============================================================
shelf = [b for b in log["books"] if b["status"] in ("reading", "finished", "switched")]
if shelf:
    st.markdown("#### 書架")
    for b in reversed(shelf):
        passed = len(b["checks"])
        reading_days = len([d for d in b["plan"] if d])
        status = {
            "setup": "設定中",
            "planning": "排進度中",
            "reading": f"閱讀中・已確認 {passed} / {reading_days} 個閱讀日",
            "finished": f"{b['finished_on']} 讀完",
            "switched": f"換了別本・讀到第 {passed} 天",
        }[b["status"]]
        author = f"　{b['author']}" if b["author"] else ""
        with st.expander(f"《{b['title'] or '（還沒有書名）'}》{author}・{status}"):
            if b["plan"]:
                st.markdown(books.plan_table(b))
            for day, check in sorted(b["checks"].items(), key=lambda kv: int(kv[0])):
                st.markdown(f"**第{day}天**（{check['passed_on']}）：{check['summary']}")
            if b.get("final_summary"):
                with st.container(border=True):
                    st.markdown(b["final_summary"])

# ============================================================
# HISTORY
# ============================================================
st.markdown("#### 每一次的紀錄")
topic_filter = st.selectbox(
    "主題",
    ["all", *core.TOPICS],
    format_func=lambda k: "全部" if k == "all" else core.TOPICS[k],
)
entries = [e for e in reversed(log["entries"])
           if topic_filter == "all" or e["topic"] == topic_filter]
if log["entries"] and not entries:
    st.caption("這個主題還沒有紀錄。")

for e in entries:
    day = date.fromisoformat(e["date"])
    mark = "●" if e.get("completed") else "○"
    title = e.get("title") or core.TOPICS[e["topic"]]
    with st.expander(f"{mark} {e['date']}（{core.weekday_zh(day)}）{title}"):
        st.caption(f"{core.TOPICS[e['topic']]}・第 {e['session_number']} 次・{e['level']}")
        key = f"{e['date']}_{e['topic']}"
        done = st.checkbox(
            "任務完成了（補打勾也算數）",
            value=e.get("completed", False),
            key=f"rec_done_{key}",
        )
        if done != e.get("completed", False):
            e["completed"] = done
            ui.save_entry(log, e)
            st.rerun()
        if e.get("followup_question"):
            st.markdown(f"**延伸提問**：{e['followup_question']}")
        reflection = st.text_area(
            "我的想法",
            value=e.get("reflection", ""),
            key=f"rec_reflection_{key}",
            placeholder="對延伸提問的想法，下次教練會接著聊",
        )
        if st.button("儲存想法", key=f"rec_save_{key}"):
            e["reflection"] = reflection.strip()
            if ui.save_entry(log, e):
                st.toast("存好了。")
            else:
                ui.show_pending_error()
        if e.get("lesson") and st.toggle("顯示當天的課程", key=f"rec_lesson_{key}"):
            with st.container(border=True):
                st.markdown(e["lesson"])

# ============================================================
# BACKUP
# ============================================================
st.divider()
st.markdown("#### 備份")
if ui.using_cloud():
    st.caption("紀錄存在 Supabase 雲端資料庫，app 重新啟動也不會不見。想留一份在自己手邊的話可以下載備份。")
else:
    st.caption("紀錄目前存在 app 的伺服器上，Streamlit Cloud 重新啟動時可能會被清掉，偶爾下載一份備份比較安心。")
st.download_button(
    "下載學習紀錄備份",
    data=json.dumps(log, ensure_ascii=False, indent=2),
    file_name=f"learning_log_{today.isoformat()}.json",
    mime="application/json",
)
uploaded = st.file_uploader("匯入學習紀錄", type="json")
if uploaded is not None and st.button("用這份紀錄取代目前紀錄"):
    try:
        new_log = core.parse_log(json.load(uploaded))
    except (ValueError, json.JSONDecodeError) as err:
        st.error(f"匯入失敗：{err}")
    else:
        if ui.replace_log(new_log):
            st.session_state.coach_log = new_log
            ui.reset_chat()
            st.rerun()
