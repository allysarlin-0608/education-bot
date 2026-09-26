"""The top of every page: one connected control for the pages
(Today, Reading when she has a reading plan, Progress, Settings) with a single active surface that travels
between them, and Search at its end.

Which page is on comes from one place: Streamlit's own navigation (the
page's address). The links are st.page_link, so moving between pages is
Streamlit's routing, unchanged. The script (motion.py) only draws the
travelling surface and hands off to the page."""
import html
from datetime import date

import streamlit as st

from coach import search, settings, ui


def render(pages: list, log: dict) -> None:
    with st.container(key="topnav", horizontal=True, vertical_alignment="center", gap=None):
        with st.container(key="topnav_items", horizontal=True, vertical_alignment="center", gap=None):
            for p in pages:
                # Settings: its name on a wide page, a gear where the bar is narrow (style.py)
                st.page_link(p, label=p.title, icon=":material/settings:" if p.title == "Settings" else None)
        if st.button("Search", icon=":material/search:", key="nav_search"):
            _search(log)


def _e(text) -> str:
    return html.escape(str(text or ""), quote=True)


@st.dialog("Search", width="medium")
def _search(log: dict) -> None:
    query = st.text_input("Search", key="search_q", label_visibility="collapsed",
                          placeholder="Lessons, subjects, books, your notes…")
    found = search.find(log, query)
    if not settings.reading_on(ui.config()):      # no Reading page to open a book on
        found = [r for r in found if r["open"][0] != "book"]
    if not query.strip():
        st.caption("Type a word or two and press Enter. Every word has to appear.")
        return
    if not found:
        st.caption("Nothing found for that.")
        return
    st.caption(f"{len(found)} {'result' if len(found) == 1 else 'results'}")
    with st.container(key="search_results", gap=None):
        for i, r in enumerate(found):
            d = date.fromisoformat(r["date"]) if r["date"] else None
            when = f"{d:%b} {d.day}, {d.year}" if d else ""
            with st.container(key=f"sres_{i}", gap=None):
                st.html(f'<div class="sr"><span class="sr-t">{_e(r["title"])}</span>'
                        f'<span class="sr-m">{_e(when)} · {_e(r["meta"])}</span>'
                        + (f'<span class="sr-s">{_e(r["snippet"])}</span>' if r["snippet"] else "") + "</div>")
                # the whole row is the button (style.py stretches it over the row)
                if st.button(f"Open {r['title']}", key=f"sopen_{i}"):
                    _open(r)


def _open(result: dict) -> None:
    """Take her to what she found: the day on Progress, or the book on Reading."""
    kind, target = result["open"]
    if kind == "day":
        day = date.fromisoformat(target)
        st.session_state.prog_day = target
        st.session_state.prog_month = (day.year, day.month)
        st.session_state.prog_way = "none"
        st.session_state.prog_view_next = "Day"
        st.switch_page("views/records.py")
    else:
        st.session_state.shelf_open = target
        st.switch_page("views/reading.py")
