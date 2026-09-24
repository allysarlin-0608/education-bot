"""Showing a lesson: markdown (tables included) plus any ```dot diagram,
drawn with st.graphviz_chart in the app's grays."""
import re

import streamlit as st

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


def render(text: str) -> None:
    dark = getattr(getattr(st.context, "theme", None), "type", "dark") != "light"
    for kind, content in split(text):
        if kind == "md":
            st.markdown(content)
            continue
        dot = styled(content, dark)
        if dot is not None:
            st.graphviz_chart(dot, width="content")
