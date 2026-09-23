import streamlit as st

from coach import ui

st.set_page_config(
    page_title="每日學習教練",
    page_icon=":material/school:",
    layout="centered",
    initial_sidebar_state="auto",   # collapsed on phones, so it never covers the page
)
ui.init_state()
ui.show_pending_error()

page = st.navigation([
    st.Page("views/daily.py", title="每日學習", icon=":material/school:", default=True),
    st.Page("views/records.py", title="學習紀錄", icon=":material/history:"),
])
page.run()
