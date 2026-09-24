import json
from datetime import date

import streamlit as st

from coach import books, core, curriculum, lesson_view, ui

log = st.session_state.coach_log
today = ui.today()

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
first = weeks[0][0][0]
cells = [f'<span class="cal-wd">{d[-1]}</span>' for d in core.WEEKDAY_ZH]
for week in weeks:
    for day, status in week:
        label = f"{day.month}/{day.day}" if day.day == 1 else str(day.day)
        classes = f"cal-day {status}" + (" today" if day == today else "")
        cells.append(f'<span class="{classes}" title="{day.isoformat()}"><b>{label}</b><i></i></span>')
st.html(
    '<div class="cal">'
    f'<div class="cal-head"><span class="cal-month">{today.year}年{today.month}月</span>'
    f'<span class="cal-range">{first.month}月{first.day}日 – {today.month}月{today.day}日</span></div>'
    f'<div class="cal-grid">{"".join(cells)}</div>'
    '<div class="cal-legend"><span><i style="background:var(--label)"></i>完成</span>'
    '<span><i style="border:1px solid var(--label-2)"></i>有上課、還沒打勾</span></div>'
    '</div>'
)

# ============================================================
# PER-TOPIC PROGRESS
# ============================================================
st.markdown("#### 各主題進度")
st.caption(f"每個主題共 {curriculum.TOTAL} 課，照順序上：第 1–{curriculum.LEVEL_SIZE} 課入門、"
           f"第 {curriculum.LEVEL_SIZE + 1}–{2 * curriculum.LEVEL_SIZE} 課中階、之後進階。")
for key, label in core.TOPICS.items():
    if curriculum.has_syllabus(key):
        p = curriculum.progress(log, key)
        st.markdown(f"**{label}**　上完 {p['done']} / {p['total']} 課・目前 {p['level']}")
        st.progress(p["level_done"] / p["level_size"],
                    text=f"{p['level']} {p['level_done']} / {p['level_size']} 課")
        continue
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
        key = f"{e['date']}_{e['topic']}"
        if e.get("lessons"):
            # A syllabus day: done when every lesson is ticked on the daily page.
            done_count = sum(1 for s in e["lessons"] if s["completed"])
            st.caption(f"{core.TOPICS[e['topic']]}・{e['level']}・完成 {done_count} / {len(e['lessons'])} 堂")
            for s in e["lessons"]:
                st.markdown(f"{'●' if s['completed'] else '○'} 第 {s['n']} 課　{s['title']}")
            show = st.toggle("顯示當天的課程內容", key=f"rec_lessons_{key}")
            for s in e["lessons"]:
                if show and s.get("lesson"):
                    with st.container(border=True):
                        st.markdown(f"**第 {s['n']} 課　{s['title']}**")
                        lesson_view.render(s["lesson"])
            if e.get("followup_question"):
                st.markdown(f"**延伸提問**：{e['followup_question']}")
            continue
        st.caption(f"{core.TOPICS[e['topic']]}・第 {e['session_number']} 次・{e['level']}")
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
                lesson_view.render(e["lesson"])

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
