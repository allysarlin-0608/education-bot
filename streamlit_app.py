import streamlit as st

from coach import sidebar, style, topnav, ui

st.set_page_config(
    page_title="Daily Learning Coach",
    page_icon=":material/school:",
    layout="centered",
    initial_sidebar_state="auto",   # collapsed on phones, so it never covers the page
)
style.inject()
ui.require_password()      # before any data is loaded
ui.init_state()
ui.show_pending_error()

pages = [
    st.Page("views/daily.py", title="Today", default=True),
    st.Page("views/reading.py", title="Reading"),
    st.Page("views/records.py", title="Progress"),
]
# Streamlit does the routing; the pages are shown by the connected control
# at the top of every page (coach/topnav.py), not as a list in the sidebar
page = st.navigation(pages, position="hidden")
topnav.render(pages, st.session_state.coach_log)
# Progress bars flow in on arriving at a page, not on every rerun.
st.session_state.lq_entering = st.session_state.get("lq_page") != page.url_path
st.session_state.lq_page = page.url_path
sidebar.render(st.session_state.coach_log)     # today's date, subject and progress, on every page
page.run()
