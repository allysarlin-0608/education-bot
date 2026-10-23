"""The top of every page: one connected control for the pages of every
day (Home, Practice, Reading when she has a reading plan, Record, Plan) with a
single active surface that travels between them; then Menu, every part of
GNOSIS grouped (menu()), and Search at its end.

Which page is on comes from one place: Streamlit's own navigation (the
page's address). The links are st.page_link, so moving between pages is
Streamlit's routing, unchanged. The script (motion.py) only draws the
travelling surface and hands off to the page."""
import html
import os
from datetime import date

import streamlit as st

from coach import auth, search, settings, ui
from coach import i18n
from coach.i18n import N_, tr, trn


# the bar's short names for the pages of every day (their full names are in the menu)
SHORT = {"Reading Plan": N_("Reading"), "Learning Record": N_("Record"), "Goals & Settings": N_("Goals")}
ICONS = {"Practice": ":material/replay:", "Reading Plan": ":material/menu_book:", "Learning Record": ":material/insights:",
         "Goals & Settings": ":material/tune:"}

# The site's sections, in order: (group, [(label, page title, or None: not built yet)]).
# Pages are found by their title among the ones gnosis.py registered; a part
# GNOSIS doesn't have yet is listed as such, never as a link to an empty page.
# Each name says one thing, and each thing is in one place: Courses (what she
# is learning, and what comes next in each), Goals & Settings (what she learns
# and which day it comes on), Learning Record (her history, and her week).
SECTIONS = (
    (N_("Learn"), ((N_("Home"), "Home"), (N_("Courses"), "Courses"), (N_("Math Curriculum"), "Math Curriculum"),
               (N_("Reading Plan"), "Reading Plan"), (N_("Learning map"), "Course"), (N_("Knowledge Exploration"), None))),
    (N_("Practice"), ((N_("Practice"), "Practice"), (N_("Review cards"), "Review"), (N_("Examinations"), None))),
    (N_("Progress"), ((N_("Learning Record"), "Learning Record"), (N_("Certificates"), None))),
    (N_("Research"), ((N_("Research"), None), (N_("Research Portfolio"), None))),
    (N_("You"), ((N_("Goals & Settings"), "Goals & Settings"), (N_("Account"), "Account"))),
)
NOT_YET = N_("not available yet")
# The parts not built yet are named in the Menu only with GNOSIS_SHOW_COMING=1 (a
# preview of the structure); for everyone else the Menu holds only what works.
SHOW_COMING = os.environ.get("GNOSIS_SHOW_COMING") == "1"


def render(pages: list, log: dict, everything: list = (), here: str = None) -> None:
    with st.container(key="topnav", horizontal=True, vertical_alignment="center", gap=None):
        with st.container(key="topnav_items", horizontal=True, vertical_alignment="center", gap=None):
            for p in pages:                        # (a subject's world isn't in the bar)
                # its name on a wide page; where the bar is narrow, Practice, Reading and
                # Goals become icons (style.py), like Search beside them
                st.page_link(p, label=tr(SHORT.get(p.title, p.title)), icon=ICONS.get(p.title))
        menu(list(pages) + list(everything), here)
        # cards waiting: a quiet dot on Practice (place.py puts it on the link)
        waiting = len(ui.review_due(log))
        st.html(f'<div id="review-due" hidden data-n="{waiting}"></div>')
        if st.button(tr("Search"), icon=":material/search:", key="nav_search"):
            _search(log)
        if auth.is_public():
            auth.account_menu()          # at the right end: who is signed in, Settings, Sign out


def _sections():
    """SECTIONS as shown: Account is "Account & Subscription" once plans are
    shown (coach/plans.SHOWN);
    the parts not built yet only with SHOW_COMING (a group left empty goes)."""
    from coach import plans
    out = SECTIONS if not plans.SHOWN else \
        SECTIONS[:-1] + (("You", ((N_("Goals & Settings"), "Goals & Settings"), (N_("Account & Subscription"), "Account"))),)
    if SHOW_COMING:
        return out
    kept = tuple((g, tuple((label, t) for label, t in items if t)) for g, items in out)
    return tuple((g, items) for g, items in kept if items)


def menu(pages: list, here: str = None) -> None:
    """Every part of GNOSIS, grouped (SECTIONS): a link to each page there
    is (the page she is on, `here` (its url_path), marked, not linked), and
    the parts not built yet named as such. Reading Plan, while she has none,
    points to where it is turned on."""
    by_title = {p.title: p for p in pages}
    with st.popover(tr("Menu"), icon=":material/menu:", key="site_menu", on_change="rerun"):
        with st.container(key="site_menu_list", gap=None):
            for group, items in _sections():
                st.html(f'<p class="mn-group">{_e(tr(group))}</p>')
                for label, title in items:
                    page = by_title.get(title) if title else None
                    if page is not None and page.url_path == here:
                        st.html(tr('<p class="mn-here" aria-current="page">{p0}<small>you are here</small></p>', p0=_e(tr(label))))
                    elif page is not None:
                        st.page_link(page, label=tr(label))
                    elif title == "Reading Plan" and "Goals & Settings" in by_title:
                        # straight to its switch (Goals & Settings → Reading), not the top of that page
                        st.page_link(by_title["Goals & Settings"], label=tr("Reading Plan · off, set it up"),
                                     query_params={"open": "reading"})
                    else:
                        st.html(f'<p class="mn-soon">{_e(tr(label))}<small>{tr(NOT_YET)}</small></p>')


def _e(text) -> str:
    return html.escape(str(text or ""), quote=True)


SEARCH_PLACEHOLDER = N_("Lessons, goals, review cards, books, your notes…")


def _enter_after_composition() -> None:
    """An Enter pressed while the keyboard still holds the word as a
    suggestion (autocorrect, predictive text, an input method) is ignored by
    the text box, so the first search did nothing (on an iPad the box could
    even end up empty). Such an Enter is remembered and sent again as soon
    as the keyboard settles the word, so the search runs on the first Enter."""
    st.html('<div id="search-enter-hook" hidden></div>'
            "<script>(function(){"
            "const docs=[document];try{if(window.parent&&window.parent.document!==document)docs.push(window.parent.document)}catch(e){}"
            f"const SEL='input[placeholder=\"{_e(tr(SEARCH_PLACEHOLDER))}\"]';"
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


@st.dialog(tr("Search"), width="medium")
def _search(log: dict) -> None:
    query = st.text_input(tr("Search"), key="search_q", label_visibility="collapsed",
                          placeholder=tr(SEARCH_PLACEHOLDER))
    _enter_after_composition()
    from coach import review
    found = search.find(log, query, topics=settings.chosen_subjects(ui.config()), cards=review.cards(log))
    if not settings.reading_on(ui.config()):      # no Reading page to open a book on
        found = [r for r in found if r["open"][0] != "book"]
    if not query.strip():
        st.caption(tr("Type a word or two and press Enter. Every word has to appear; the best matches come first."))
        return
    if not found:
        st.caption(tr('No results for ‘{p0}’.', p0=query.strip()))
        return
    st.caption(trn("{n} result", "{n} results", len(found)))
    with st.container(key="search_results", gap=None):
        for i, r in enumerate(found):
            d = date.fromisoformat(r["date"]) if r["date"] else None
            when = i18n.day_short(d, year=True) if d else ""
            with st.container(key=f"sres_{i}", gap=None):
                st.html(f'<div class="sr"><span class="sr-t">{_e(r["title"])}</span>'
                        f'<span class="sr-m">{_e(when)} · {_e(r["meta"])}</span>'
                        + (f'<span class="sr-s">{_e(r["snippet"])}</span>' if r["snippet"] else "") + "</div>")
                # the whole row is the button (style.py stretches it over the row)
                if st.button(tr('Open {p0}', p0=r['title']), key=f"sopen_{i}"):
                    _open(r)


def _open(result: dict) -> None:
    """Take her to what she found: the day on Progress, the book on Reading,
    a course map (a goal, a lesson still to come), or her review cards."""
    kind, target = result["open"]
    if kind == "course":
        ui.open_course(target)
    if kind == "review":
        st.session_state.rv_query = target           # (Review's own search, already filled in)
        st.switch_page("views/review.py")
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
