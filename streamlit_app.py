import streamlit as st

from coach import settings, sidebar, style, topnav, ui

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

config = ui.config()
if not settings.onboarded(config):
    # first time: the setup, on its own, until she presses Start learning
    st.navigation([st.Page("views/setup.py", title="Welcome", default=True)], position="hidden").run()
    st.stop()

pages = [st.Page("views/daily.py", title="Today", default=True)]
if settings.reading_on(config):             # no reading plan: no Reading page at all
    pages.append(st.Page("views/reading.py", title="Reading"))
pages += [
    st.Page("views/records.py", title="Progress"),
    st.Page("views/settings.py", title="Settings"),
]
# each subject's world: one page, reached from the subject (not from the bar)
world = st.Page("views/world.py", title="Subject", url_path="subject")
# Streamlit does the routing; the pages are shown by the connected control
# at the top of every page (coach/topnav.py), not as a list in the sidebar
page = st.navigation(pages + [world], position="hidden")
if (entering := st.session_state.pop("enter_world", None)):     # setup just finished: into the first day's subject
    st.session_state.world_topic = entering
    st.switch_page(world)
topnav.render(pages, st.session_state.coach_log)
# Progress bars flow in on arriving at a page, not on every rerun.
st.session_state.lq_entering = st.session_state.get("lq_page") != page.url_path
st.session_state.lq_page = page.url_path
sidebar.render(st.session_state.coach_log)     # today's date, subject and progress, on every page
page.run()
