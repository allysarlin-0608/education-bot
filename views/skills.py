"""The Knowledge Map is now part of each course's learning map (views/course.py):
what she knows, idea by idea, beside the path itself. An old link or bookmark
to /skills opens the learning map of the subject it named."""
import streamlit as st

from coach import catalog, ui

topic = st.session_state.get("sk_topic")
ui.open_course(topic if topic and catalog.known(topic) else ui.topic_for(ui.today()))
