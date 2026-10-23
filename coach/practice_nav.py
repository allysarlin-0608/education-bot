"""The Practice page's three tabs: a practice set on the ideas she knows
least (views/practice.py), her review cards due today and her collection
of cards (views/review.py). One page in the bar; each tab is its own
Streamlit page underneath, switched here."""
import streamlit as st

from coach.i18n import N_, tr

TABS = (N_("Practice"), N_("Review cards"), N_("Collection"))
PAGES = {"Practice": "views/practice.py", "Review cards": "views/review.py", "Collection": "views/review.py"}


def tabs(here: str) -> str:
    """Draw the tabs with `here` on; switch page when she picks another."""
    st.markdown(tr("## Practice"))
    key = f"pn_tabs_{here}"
    picked = st.segmented_control(tr("Show"), TABS, default=here, key=key, required=True,
                                  label_visibility="collapsed", format_func=tr) or here
    if picked != here:
        st.session_state.rv_view = "Collection" if picked == "Collection" else "Today"
        st.session_state.pop(key, None)
        st.switch_page(PAGES[picked])
    return here
