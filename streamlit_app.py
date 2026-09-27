# The app's entry point: the Streamlit app (gnosis.py) and, beside it, the
# few HTTP routes sign-in needs (coach/routes.py).
import streamlit as st

from coach import routes

app = st.App("gnosis.py", routes=routes.all_routes())
