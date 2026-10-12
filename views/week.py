"""Your week is now a tab of the Learning Record (coach/weekview.py): an
old link or bookmark to /week opens it there."""
import streamlit as st

st.session_state.rec_tab_next = "Your week"
st.switch_page("views/records.py")
