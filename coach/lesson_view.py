"""Showing a lesson: each 【Block】 as a card with its name as the title
(the brackets are only in the stored text, which the quiz and history read),
markdown inside (tables included) plus any ```dot diagram, drawn with
st.graphviz_chart in the app's grays."""
import hashlib
import re
from html import escape
from urllib.parse import quote_plus

import streamlit as st

from coach import catalog, core

# 【Key Idea】, **【Key Idea】**, ### 【Key Idea】: at the start of a line
BLOCK = re.compile(r"^[ \t]*(?:#+[ \t]*)?(?:\*\*)?【([^】\n]+)】(?:\*\*)?[ \t]*[:：]?[ \t]*", re.MULTILINE)

DOT_BLOCK = re.compile(r"```(?:dot|graphviz)\s*\n(.*?)```", re.DOTALL)
# Colors the model might set; the app draws every diagram in its own grays.
COLOR_ATTR = re.compile(r'\b(?:fill|font|bg|pen)?color\s*=\s*("[^"]*"|[^\s,\];]+)\s*,?', re.IGNORECASE)
FILLED = re.compile(r'\bstyle\s*=\s*"?filled"?\s*,?', re.IGNORECASE)
FONT = "Inter, Noto Sans TC, sans-serif"
# a source the model named in brackets, "(Source: Investopedia)": it can't be
# checked (the model may make it up), so it isn't shown; the lesson links to
# places she can check it herself instead (check_links)
SOURCE = re.compile(r"[ \t]*[(（](?:sources?|來源|出處|参考|參考)\s*[:：][^)）\n]{0,160}[)）]", re.IGNORECASE)
# a node statement: an id, then its attributes
_ID = r'(?:"([^"\n]+)"|([^\W\d]\w*))'          # a node id: "quoted words", or a bare name (any script)
NODE = re.compile(r'(?:(?<=[;{\n])|^)\s*' + _ID + r'\s*\[([^\]]*)\]')
EDGE_IDS = re.compile(_ID + r'\s*-[->]\s*' + _ID)
MAX_NODES = 12
# where she can check a lesson herself: real searches, built here (no model call)
CHECK = (("Wikipedia", "https://en.wikipedia.org/w/index.php?fulltext=1&search={q}"),
         ("Britannica", "https://www.britannica.com/search?query={q}"))


def humane(name: str) -> str:
    """A diagram id as words: CapitalGains -> Capital gains, risk_reward -> risk reward."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|_+", " ", name).split()
    return " ".join([words[0]] + [x.lower() if x[:1].isupper() and x[1:].islower() else x for x in words[1:]]) if words else name


def unsourced(text: str) -> str:
    return SOURCE.sub("", text)


def split(text: str) -> list:
    """[("md", text) | ("dot", source), ...] in reading order."""
    parts, pos = [], 0
    for m in DOT_BLOCK.finditer(text):
        if text[pos:m.start()].strip():
            parts.append(("md", text[pos:m.start()]))
        parts.append(("dot", m.group(1).strip()))
        pos = m.end()
    if text[pos:].strip():
        parts.append(("md", text[pos:]))
    return parts


def styled(source: str, dark: bool):
    """The diagram with the app's grays and fonts, or None if it isn't a
    single well-formed graph (so a broken one is skipped, not shown raw)."""
    if not re.match(r"^(strict\s+)?(di)?graph\b[^{]*\{", source) or not source.endswith("}"):
        return None
    if source.count("{") != source.count("}"):
        return None
    ink, line = ("#EDEDED", "#8C8C8C") if dark else ("#1A1A1A", "#8C8C8C")
    body = FILLED.sub("", COLOR_ATTR.sub("", source))
    # every node reads as words: an id with no label of its own gets one made from it
    nodes = [(m.group(1) or m.group(2), m.group(3)) for m in NODE.finditer(body)]
    labelled = {n for n, attrs in nodes if re.search(r"\blabel\s*=", attrs)}
    edges = [(m.group(1) or m.group(2), m.group(3) or m.group(4)) for m in EDGE_IDS.finditer(body)]
    ids = list(dict.fromkeys([a for a, _ in edges] + [b for _, b in edges] + [n for n, _ in nodes]))
    ids = [i for i in ids if i not in ("node", "edge", "graph", "digraph", "subgraph", "strict")]
    if not 2 <= len(ids) <= MAX_NODES:
        return None                    # one box, or a tangle: it doesn't help
    extra = "".join(f'"{i}" [label="{humane(i)}"]; ' for i in ids if i not in labelled and humane(i) != i)
    body = body[:body.rindex("}")].rstrip() + ("; " if extra else "") + extra + "}"
    defaults = (
        f'bgcolor="transparent"; fontname="{FONT}"; fontcolor="{ink}"; rankdir=TB; '
        f'node [shape=box, style=rounded, color="{line}", fontcolor="{ink}", fontname="{FONT}", fontsize=12, penwidth=1]; '
        f'edge [color="{line}", fontcolor="{ink}", fontname="{FONT}", fontsize=10, arrowsize=0.6]; '
    )
    head, rest = body.split("{", 1)
    return f"{head}{{ {defaults}{rest}"


def blocks(text: str) -> list:
    """[(title or "", body), ...]: the text before the first block (if any)
    has no title."""
    out, marks = [], list(BLOCK.finditer(text))
    if not marks:
        return [("", text)]
    if text[:marks[0].start()].strip():
        out.append(("", text[:marks[0].start()]))
    for m, nxt in zip(marks, marks[1:] + [None]):
        out.append((m.group(1).strip(), text[m.end():nxt.start() if nxt else len(text)]))
    return out


def _body(text: str, dark: bool) -> None:
    for kind, content in split(text):
        if kind == "md":
            st.markdown(content)
            continue
        dot = styled(content, dark)
        if dot is not None:
            st.graphviz_chart(dot, width="content")


def check_links(title: str, topic: str = None) -> None:
    """Where she can check the lesson herself: searches for it on Wikipedia
    and Britannica (real pages, built here; nothing the model wrote)."""
    if not title:
        return
    q = quote_plus(f"{title} {catalog.name(topic)}" if topic and catalog.is_goal(topic) else title)
    links = " · ".join(f'<a href="{escape(url.format(q=q))}" target="_blank" rel="noopener noreferrer">{name}</a>'
                       for name, url in CHECK)
    st.html(f'<p class="l-check">Check it yourself: {links}</p>')


def render(text: str, topic: str = None, key: str = "", title: str = "") -> None:
    """key names this showing of the lesson (the same lesson can be on a
    page twice, e.g. in the history, and card keys must be unique)."""
    dark = getattr(getattr(st.context, "theme", None), "type", "dark") != "light"
    text = unsourced(text)
    if topic and topic != "investing" and core.has_disclaimer(text):
        text = core.DISCLAIMER_LINE.sub("", text)      # saved before the disclaimer was investing-only
    # the closing line and a disclaimer read as a footnote, not part of the last card
    footer = []
    for line in (core.DISCLAIMER, core.CLOSING_LINE):
        if line in text:
            text = text.replace(line, "")
            footer.append(line)
    tag = hashlib.md5(f"{key}|{text}".encode()).hexdigest()[:10]
    for k, (title, body) in enumerate(blocks(text.strip())):
        if not title:
            if body.strip():
                _body(body, dark)
            continue
        with st.container(key=f"lcard_{tag}_{k}"):
            st.html(f'<div class="lcard-title">{escape(title)}</div>')
            _body(body, dark)
    check_links(title, topic)
    for line in footer:
        st.caption(line)


def render_tabs(text: str, topic: str = None, key: str = "", title: str = "") -> None:
    """The same lesson, one section at a time: a tab per block (Topic, Key
    Idea, ...), so reading an old lesson takes the height of one card, not
    the whole lesson. Switching tabs doesn't rerun the page."""
    dark = getattr(getattr(st.context, "theme", None), "type", "dark") != "light"
    text = unsourced(text)
    if topic and topic != "investing" and core.has_disclaimer(text):
        text = core.DISCLAIMER_LINE.sub("", text)
    footer = [line for line in (core.DISCLAIMER, core.CLOSING_LINE) if line in text]
    for line in footer:
        text = text.replace(line, "")
    parts = [(title or "Intro", body) for title, body in blocks(text.strip()) if title or body.strip()]
    if not parts:
        return
    for (title, body), tab in zip(parts, st.tabs([title for title, _ in parts])):
        with tab:
            _body(body, dark)
    for line in footer:
        st.caption(line)
    check_links(title, topic)
