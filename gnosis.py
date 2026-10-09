import streamlit as st

import coach

coach.freshen()     # an update that landed while nobody was here: load the new code whole, not half of it
from coach import auth, place, settings, sidebar, style, topnav, ui  # noqa: E402

st.set_page_config(
    page_title="GNOSIS",
    page_icon=":material/school:",
    layout="centered",
    initial_sidebar_state="auto",   # collapsed on phones, so it never covers the page
)
style.inject()
if auth.is_public():
    auth.gate(ui.make_store())    # signed in and invited, before any of their data is loaded
else:
    ui.require_password()      # before any data is loaded
ui.init_state()
ui.refresh_settings()     # as stored now: another tab may have changed the pace or the subjects
if st.session_state.get("coach_visit_day") != ui.today():     # one "visit" a day (coach/metrics.py)
    st.session_state.coach_visit_day = ui.today()
    ui.record("visit")
ui.show_pending_error()

config = ui.config()
if not settings.onboarded(config):
    # first time: the setup, on its own, until she presses Start learning
    st.navigation([st.Page("views/setup.py", title="Welcome", default=True)], position="hidden").run()
    st.stop()

# the pages of every day, in the bar (coach/topnav.py)
pages = [st.Page("views/daily.py", title="Home", default=True),
         st.Page("views/review.py", title="Review", url_path="review")]     # part of every day: in the bar
if settings.reading_on(config):             # no reading plan: no Reading page at all
    pages.append(st.Page("views/reading.py", title="Reading Plan", url_path="reading"))
pages += [
    st.Page("views/records.py", title="Learning Record", url_path="records"),
    st.Page("views/settings.py", title="Learning Plan", url_path="settings"),
]
# every other part, reached from the Menu (coach/topnav.SECTIONS) and from the pages themselves
# the curriculum: every course, hers first (the Menu)
subjects_page = st.Page("views/subjects.py", title="Subjects & Courses", url_path="courses")
# her sequence: the order of her days and where each course goes next (the Menu)
path_page = st.Page("views/path.py", title="Learning Path", url_path="path")
# her profile, plan and data (the Menu, and the account menu)
account_page = st.Page("views/account.py", title="Account", url_path="account")
# each subject's world: one page, reached from the subject (not from the bar)
world = st.Page("views/world.py", title="Subject", url_path="subject")
# each subject's course map: reached wherever a subject is named (Today, Record, Learning Plan, its world)
course_map = st.Page("views/course.py", title="Course", url_path="course")
# a new goal of her own (Learning Plan → Your goals)
new_goal = st.Page("views/goal.py", title="New goal", url_path="goal")
# her week in review (Record, and Home when a week has just ended)
week_page = st.Page("views/week.py", title="Your week", url_path="week")
# what she knows, idea by idea, and practice on what she knows least (Phase 3)
skills_page = st.Page("views/skills.py", title="Knowledge Map", url_path="skills")
practice_page = st.Page("views/practice.py", title="Practice", url_path="practice")
others = [subjects_page, path_page, account_page, world, course_map, new_goal, week_page, skills_page, practice_page]
# Streamlit does the routing; the pages are shown by the connected control
# at the top of every page (coach/topnav.py), not as a list in the sidebar
page = st.navigation(pages + others, position="hidden")
if (entering := st.session_state.pop("enter_world", None)):     # setup just finished: into the first day's subject
    st.switch_page(world, query_params={"subject": entering})
# just signed in after a refresh or a link: back to the page the address named, with its subject
asked = st.session_state.pop("coach_asked_path", None)
target = next((p for p in pages + others if asked and p.url_path == asked), None)
if target is not None and target.url_path != page.url_path:
    st.switch_page(target, query_params=st.query_params.to_dict())
if st.session_state.get("lq_page") != page.url_path:
    st.session_state.account_menu = False      # a menu choice that changed the page closes the menu
    st.session_state.site_menu = False
    st.session_state.pop("data_export", None)  # a data download gathered earlier is out of date once she moves on (ISS-026)
# today's day as stored now (another tab or device may have moved on), read
# before the bar and the sidebar so they and the page show the same day
fresh = st.session_state.pop("coach_log_fresh", False)
if page.url_path == "records" and st.session_state.get("lq_page") != page.url_path and not fresh:
    ui.refresh_log(st.session_state.coach_log)   # arriving at Progress: her whole record as stored now (ISS-030)
ui.refresh_entry(st.session_state.coach_log, ui.today(), ui.topic_for(ui.today()))
topnav.render(pages, st.session_state.coach_log, others, page.url_path)
st.html(place.keep_clear(), unsafe_allow_javascript=True)     # new controls never hide under the chat box
# Progress bars flow in on arriving at a page, not on every rerun.
st.session_state.lq_entering = st.session_state.get("lq_page") != page.url_path
st.session_state.lq_page = page.url_path
sidebar.render(st.session_state.coach_log)     # today's date, subject and progress, on every page
page.run()
