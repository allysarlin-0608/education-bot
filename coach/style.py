"""The app's look (Apple Human Interface Guidelines style), in one place.

Only the values from the design brief are used: the type scale, the
light/dark colours, 8-based spacing, radii and the soft shadow. Cards are
Streamlit containers created with key="card_..."; Streamlit gives them the
class .st-key-card_..., which the CSS below styles."""
import html

import streamlit as st

CSS = """
<style>
:root {
  --bg: #F2F2F7; --card: #FFFFFF; --card2: #F2F2F7;
  --label: #000000; --label2: rgba(60,60,67,0.6); --label3: rgba(60,60,67,0.3);
  --sep: rgba(60,60,67,0.29);
  --blue: #007AFF; --green: #34C759; --orange: #FF9500; --red: #FF3B30;
  --shadow: 0 1px 3px rgba(0,0,0,0.06);
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #000000; --card: #1C1C1E; --card2: #2C2C2E;
    --label: #FFFFFF; --label2: rgba(235,235,245,0.6); --label3: rgba(235,235,245,0.6);
    --sep: #2C2C2E;
    --blue: #0A84FF; --green: #30D158; --red: #FF453A;
    --shadow: none;
  }
}

/* ---------- chrome: no Streamlit header, footer or menu ---------- */
header[data-testid="stHeader"], footer, #MainMenu,
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
.stApp { background: var(--bg); }
.block-container, [data-testid="stMainBlockContainer"] {
  padding: 24px 20px 96px !important; max-width: 720px;
}
@media (max-width: 640px) {
  .block-container, [data-testid="stMainBlockContainer"] { padding: 16px 16px 96px !important; }
}

/* ---------- type scale (size/line-height in px) ---------- */
.stApp .t-large, .t-large   { font-size: 34px; line-height: 41px; font-weight: 700; color: var(--label); margin: 0; }
.stApp .t-title1, .t-title1  { font-size: 28px; line-height: 34px; font-weight: 700; color: var(--label); margin: 0; }
.stApp .t-title2, .t-title2  { font-size: 22px; line-height: 28px; font-weight: 700; color: var(--label); margin: 0; }
.stApp .t-title3, .t-title3  { font-size: 20px; line-height: 25px; font-weight: 600; color: var(--label); margin: 0; }
.t-headline{ font-size: 17px; line-height: 22px; font-weight: 600; color: var(--label); margin: 0; }
.stApp .t-body, .t-body    { font-size: 17px; line-height: 22px; color: var(--label); margin: 0; }
.stApp .t-callout, .t-callout { font-size: 16px; line-height: 21px; color: var(--label); margin: 0; }
.stApp .t-subhead, .t-subhead { font-size: 15px; line-height: 20px; color: var(--label2); margin: 0; }
.t-footnote{ font-size: 13px; line-height: 18px; color: var(--label2); margin: 0; }
.stApp .t-caption, .t-caption { font-size: 12px; line-height: 16px; color: var(--label2); margin: 0; }
.stApp .t-section, .t-section { font-size: 13px; line-height: 18px; color: var(--label2); margin: 24px 16px 8px; }
.t-blue { color: var(--blue); } .t-green { color: var(--green); }

/* Streamlit pulls each text block up with a negative bottom margin; our
   typographic lines need their real height so titles don't overlap. */
[data-testid="stMarkdownContainer"]:has(> p[class^="t-"]),
[data-testid="stMarkdownContainer"]:has(> div.stats),
[data-testid="stMarkdownContainer"]:has(> div.group) { margin-bottom: 0 !important; }

/* Streamlit's own text sizes inside the app */
[data-testid="stMarkdownContainer"] p:not([class]), [data-testid="stMarkdownContainer"] li { font-size: 17px; line-height: 22px; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 13px; line-height: 18px; color: var(--label2); }
[data-testid="stWidgetLabel"] p { font-size: 15px; line-height: 20px; color: var(--label2); }
[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p,
[data-testid="stToggle"] [data-testid="stWidgetLabel"] p,
[data-testid="stCheckbox"] label p, [data-testid="stToggle"] label p { font-size: 17px; line-height: 22px; color: var(--label); }

/* ---------- cards ---------- */
[class*="st-key-card"] {
  background: var(--card); border-radius: 14px; padding: 16px; box-shadow: var(--shadow);
  gap: 8px; animation: rise 0.3s var(--ease);
}
[class*="st-key-card"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
[class*="st-key-card"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[class*="st-key-card_concept"] [data-testid="stMarkdownContainer"] p:not([class]) { font-size: 22px; line-height: 28px; font-weight: 600; }
[class*="st-key-card_question"] [data-testid="stMarkdownContainer"] p:not([class]),
[class*="st-key-card_reminder"] [data-testid="stMarkdownContainer"] p:not([class]),
[class*="st-key-card_disclaimer"] [data-testid="stMarkdownContainer"] p:not([class]),
[class*="st-key-card_question"] li, [class*="st-key-card_reminder"] li { font-size: 15px; line-height: 20px; }
[class*="st-key-card_disclaimer"] [data-testid="stMarkdownContainer"] p:not([class]) { color: var(--label2); }
[class*="st-key-card_tasks"] [data-testid="stCheckbox"] p { font-size: 17px; line-height: 22px; }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* grouped list rows (0.5px separators, inset like iOS) */
.group { background: var(--card); border-radius: 14px; box-shadow: var(--shadow); overflow: hidden; }
.row { display: flex; align-items: center; gap: 12px; min-height: 44px; padding: 11px 16px; position: relative; }
.row + .row::before { content: ""; position: absolute; top: 0; left: 16px; right: 0; border-top: 0.5px solid var(--sep); }
.row .grow { flex: 1; min-width: 0; }
.row .value { color: var(--label2); font-size: 17px; line-height: 22px; white-space: nowrap; }
.bar { height: 4px; border-radius: 2px; background: var(--card2); margin-top: 8px; overflow: hidden; }
.bar > span { display: block; height: 100%; background: var(--blue); border-radius: 2px; }

/* stat tiles */
.stat { background: var(--card); border-radius: 14px; padding: 12px 16px; box-shadow: var(--shadow); }
.stat .num { font-size: 28px; line-height: 34px; font-weight: 700; color: var(--label); }
.stat .lbl { font-size: 13px; line-height: 18px; color: var(--label2); }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0 8px; }
.stats.four { grid-template-columns: repeat(4, 1fr); }
@media (max-width: 640px) { .stats.four { grid-template-columns: 1fr 1fr; } }

/* four-week calendar: filled = done, ring = lesson not ticked, dot = none */
.cal { display: grid; grid-template-columns: 48px repeat(7, 1fr); gap: 8px 4px; align-items: center; padding: 12px 16px; }
.cal .h { font-size: 12px; line-height: 16px; color: var(--label2); text-align: center; }
.cal .w { font-size: 12px; line-height: 16px; color: var(--label2); }
.cal .d { width: 20px; height: 20px; border-radius: 50%; margin: 0 auto; }
.cal .done { background: var(--blue); }
.cal .started { border: 2px solid var(--blue); box-sizing: border-box; }
.cal .none { width: 6px; height: 6px; background: var(--label3); }
.legend { display: flex; gap: 16px; flex-wrap: wrap; padding: 0 16px 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; line-height: 16px; color: var(--label2); }
.legend i { display: inline-block; width: 12px; height: 12px; border-radius: 50%; }

/* ---------- controls ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, [data-testid="stPageLink"] a {
  min-height: 44px; border-radius: 12px; font-size: 17px; font-weight: 600;
  transition: transform 0.3s var(--ease), opacity 0.3s var(--ease);
}
.stButton > button:active, .stFormSubmitButton > button:active { transform: scale(0.97); opacity: 0.8; }
.stButton > button[kind="secondary"], .stDownloadButton > button {
  background: var(--card); color: var(--blue); border: none; box-shadow: var(--shadow);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button { background: var(--blue); border: none; }
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-testid="stDateInputField"] {
  border-radius: 10px !important; min-height: 44px; background: var(--card);
}
[data-testid="stExpander"] details {
  background: var(--card); border: none; border-radius: 14px; box-shadow: var(--shadow);
}
[data-testid="stExpander"] summary { min-height: 44px; font-size: 17px; }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stCheckbox"] label, [data-testid="stToggle"] label { min-height: 44px; align-items: center; }

/* top navigation: a two-segment control (white track, selected = blue) */
.st-key-nav { background: var(--card); border-radius: 12px; padding: 2px; box-shadow: var(--shadow); }
.st-key-nav [data-testid="stHorizontalBlock"] { gap: 2px; flex-wrap: nowrap; }
.st-key-nav [data-testid="stColumn"] { min-width: 0; flex: 1 1 0 !important; width: auto !important; }
.st-key-nav [data-testid="stElementContainer"], .st-key-nav [data-testid="stPageLink"],
.st-key-nav [data-testid="stPageLink"] > div { width: 100% !important; }
.st-key-nav [data-testid="stPageLink"] a, .seg-on {
  width: 100%; box-sizing: border-box;
  display: flex; align-items: center; justify-content: center; min-height: 40px; border-radius: 10px;
  background: transparent; box-shadow: none; margin: 0;
}
.st-key-nav [data-testid="stPageLink"] a { justify-content: center !important; }
.st-key-nav [data-testid="stPageLink"] a p { color: var(--blue); font-size: 15px; font-weight: 600; text-align: center; }
.stApp .seg-on { background: var(--blue); color: #FFFFFF; font-size: 15px; line-height: 20px; font-weight: 600; }

/* chat after the lesson: no avatars */
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"],
[data-testid="chatAvatarIcon-user"], [data-testid="chatAvatarIcon-assistant"] { display: none !important; }
[data-testid="stChatMessage"] { background: var(--card); border-radius: 14px; padding: 12px 16px; box-shadow: var(--shadow); gap: 0; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  background: var(--blue); margin-left: auto; width: auto; max-width: calc(100% - 48px);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p { color: #FFFFFF; }
[data-testid="stBottomBlockContainer"] { background: var(--bg); }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def text(content: str, cls: str):
    """One line/paragraph of text in a type-scale style (HTML-escaped)."""
    st.markdown(f'<p class="{cls}">{html.escape(content)}</p>', unsafe_allow_html=True)


def section(title: str):
    """The small grey heading above a grouped list."""
    text(title, "t-section")


PAGES = (("today", "views/daily.py", "今天"), ("records", "views/records.py", "紀錄"))


def nav(current: str):
    """今天 / 紀錄 at the top of every page (the Streamlit header and
    sidebar navigation are hidden). The current page is the selected
    segment; the other one is a link."""
    with st.container(key="nav"):
        for col, (name, path, label) in zip(st.columns(len(PAGES), gap="small"), PAGES):
            if name == current:
                col.markdown(f'<p class="seg-on">{label}</p>', unsafe_allow_html=True)
            else:
                col.page_link(path, label=label, width="stretch")


def stats(items, four=False):
    """Side-by-side stat tiles: items is [(number, label), ...]."""
    tiles = "".join(
        f'<div class="stat"><div class="num">{html.escape(str(n))}</div>'
        f'<div class="lbl">{html.escape(label)}</div></div>'
        for n, label in items
    )
    st.markdown(f'<div class="stats{" four" if four else ""}">{tiles}</div>', unsafe_allow_html=True)


def group(rows):
    """A grouped list: rows is a list of HTML strings built by row()."""
    st.markdown(f'<div class="group">{"".join(rows)}</div>', unsafe_allow_html=True)


def row(title: str, detail: str = "", value: str = "", progress=None) -> str:
    bar = ""
    if progress is not None:
        bar = f'<div class="bar"><span style="width:{max(0.0, min(progress, 1.0)) * 100:.0f}%"></span></div>'
    sub = f'<p class="t-footnote">{html.escape(detail)}</p>' if detail else ""
    val = f'<span class="value">{html.escape(value)}</span>' if value else ""
    return (f'<div class="row"><div class="grow"><p class="t-body">{html.escape(title)}</p>'
            f'{sub}{bar}</div>{val}</div>')
