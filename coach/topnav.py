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

from coach import auth, review, search, settings, ui


ICONS = {"Review": ":material/replay:", "Reading": ":material/menu_book:", "Progress": ":material/insights:",
         "Settings": ":material/settings:"}


def render(pages: list, log: dict) -> None:
    with st.container(key="topnav", horizontal=True, vertical_alignment="center", gap=None):
        with st.container(key="topnav_items", horizontal=True, vertical_alignment="center", gap=None):
            for p in pages:                        # (a subject's world isn't in the bar)
                # its name on a wide page; where the bar is narrow, Review, Reading and
                # Settings become icons (style.py), like Search beside them
                st.page_link(p, label=p.title, icon=ICONS.get(p.title))
        # cards waiting: a quiet dot on Review (place.py puts it on the link)
        waiting = len(review.due(log, ui.today()))
        st.html(f'<div id="review-due" hidden data-n="{waiting}"></div>')
        if st.button("Search", icon=":material/search:", key="nav_search"):
            _search(log)
        if auth.is_public():
            auth.account_menu()          # at the right end: who is signed in, Settings, Sign out


def _e(text) -> str:
    return html.escape(str(text or ""), quote=True)


SEARCH_PLACEHOLDER = "Lessons, subjects, books, your notes…"


def _enter_after_composition() -> None:
    """An Enter pressed while the keyboard still holds the word as a
    suggestion (autocorrect, predictive text, an input method) is ignored by
    the text box, so the first search did nothing (on an iPad the box could
    even end up empty). Such an Enter is remembered and sent again as soon
    as the keyboard settles the word, so the search runs on the first Enter."""
    st.html('<div id="search-enter-hook" hidden></div>'
            "<script>(function(){"
            "const docs=[document];try{if(window.parent&&window.parent.document!==document)docs.push(window.parent.document)}catch(e){}"
            f"const SEL='input[placeholder=\"{SEARCH_PLACEHOLDER}\"]';"
            "for(const d of docs){if(d.__gnSearchEnter)continue;d.__gnSearchEnter=true;"
            "d.addEventListener('keydown',function(e){const t=e.target;"
            "if(e.key==='Enter'&&(e.isComposing||e.keyCode===229)&&t.matches&&t.matches(SEL))t.__gnEnterLater=true;},true);"
            "d.addEventListener('compositionend',function(e){const t=e.target;"
            "if(!(t.matches&&t.matches(SEL)&&t.__gnEnterLater))return;t.__gnEnterLater=false;"
            "setTimeout(function(){t.dispatchEvent(new KeyboardEvent('keydown',"
            "{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));},0);},true);}"
            # opened again: the last query is selected, so what she types replaces it (not glued to it)
            "(function pick(n){let found=false;for(const d of docs){const i=d.querySelector(SEL);if(!i)continue;found=true;"
            "if(!i.__gnOpened){i.__gnOpened=true;i.focus();i.select();}}"
            "if(!found&&n>0)setTimeout(function(){pick(n-1);},50);})(30);"
            "})();</script>", unsafe_allow_javascript=True)


@st.dialog("Search", width="medium")
def _search(log: dict) -> None:
    query = st.text_input("Search", key="search_q", label_visibility="collapsed",
                          placeholder=SEARCH_PLACEHOLDER)
    _enter_after_composition()
    found = search.find(log, query)
    if not settings.reading_on(ui.config()):      # no Reading page to open a book on
        found = [r for r in found if r["open"][0] != "book"]
    if not query.strip():
        st.caption("Type a word or two and press Enter. Every word has to appear.")
        return
    if not found:
        st.caption(f"No results for ‘{query.strip()}’.")
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
