import streamlit as st

from coach import i18n, reading, ui
from coach.i18n import tr

# 看書 is a daily task with its own 14-day book tracker (part 4.3), separate
# from the day's lesson. It always works on the real today.
log = st.session_state.coach_log
today = ui.today()

st.markdown(tr("## Reading Plan"))
st.markdown('<p class="page-sub reading-page">' + i18n.day_long(today) + " · "
            + tr("Read a little every day, then come back and talk about it.") + "</p>", unsafe_allow_html=True)
reading.render(log, today)
