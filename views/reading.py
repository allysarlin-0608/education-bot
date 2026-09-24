import streamlit as st

from coach import core, reading, ui

# 看書 is a daily task with its own 14-day book tracker (part 4.3), separate
# from the day's lesson. It always works on the real today.
log = st.session_state.coach_log
today = ui.today()

st.markdown("## 看書")
st.caption(f"{today:%Y.%m.%d}　{core.weekday_zh(today)}　每天讀一點，讀完回來聊聊。")
reading.render(log, today)
