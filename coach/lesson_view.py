"""Showing a lesson: each 【Block】 as a card with its name as the title
(the brackets are only in the stored text, which the quiz and history read),
markdown inside (tables included) plus any ```dot diagram, drawn with
st.graphviz_chart in the app's grays."""
import hashlib
import re
from html import escape

import streamlit as st

from coach import core

# 【Key Idea】, **【Key Idea】**, ### 【Key Idea】: at the start of a line
BLOCK = re.compile(r"^[ \t]*(?:#+[ \t]*)?(?:\*\*)?【([^】\n]+)】(?:\*\*)?[ \t]*[:：]?[ \t]*", re.MULTILINE)

DOT_BLOCK = re.compile(r"```(?:dot|graphviz)\s*\n(.*?)```", re.DOTALL)
# Colors the model might set; the app draws every diagram in its own grays.
COLOR_ATTR = re.compile(r'\b(?:fill|font|bg|pen)?color\s*=\s*("[^"]*"|[^\s,\];]+)\s*,?', re.IGNORECASE)
FILLED = re.compile(r'\bstyle\s*=\s*"?filled"?\s*,?', re.IGNORECASE)
FONT = "Inter, Noto Sans TC, sans-serif"


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


def render(text: str, topic: str = None, key: str = "") -> None:
    """key names this showing of the lesson (the same lesson can be on a
    page twice, e.g. in the history, and card keys must be unique)."""
    dark = getattr(getattr(st.context, "theme", None), "type", "dark") != "light"
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
    for line in footer:
        st.caption(line)


def render_tabs(text: str, topic: str = None, key: str = "") -> None:
    """The same lesson, one section at a time: a tab per block (Topic, Key
    Idea, ...), so reading an old lesson takes the height of one card, not
    the whole lesson. Switching tabs doesn't rerun the page."""
    dark = getattr(getattr(st.context, "theme", None), "type", "dark") != "light"
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
