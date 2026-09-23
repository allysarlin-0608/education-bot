import streamlit as st

from coach import style, ui

st.set_page_config(
    page_title="每日學習教練",
    page_icon=":material/school:",
    layout="centered",
    initial_sidebar_state="collapsed",
)
style.inject()             # the look, before anything is drawn (password screen too)
ui.require_password()      # before any data is loaded
ui.init_state()
ui.show_pending_error()

# Streamlit's own navigation is hidden; each page draws 今天 / 紀錄 at the top.
page = st.navigation([
    st.Page("views/daily.py", title="今天", icon=":material/school:", default=True),
    st.Page("views/records.py", title="紀錄", icon=":material/history:"),
], position="hidden")
page.run()
