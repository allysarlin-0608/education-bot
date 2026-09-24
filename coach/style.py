"""Look of the app: quiet, editorial black / off-white / gray.

Colors and fonts live in .streamlit/config.toml; this adds what the theme
can't express (typography scale, hairlines, glass header, motion)."""
import streamlit as st

SERIF = '"Newsreader", "Noto Serif TC", serif'
SANS = '"Inter", "Noto Sans TC", sans-serif'

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600"
         "&family=Noto+Sans+TC:wght@300;400;500&family=Newsreader:opsz,wght@6..72,300;6..72,400"
         "&family=Noto+Serif+TC:wght@300;400;500&display=swap")

CSS = f"""
<style>
@import url("{FONTS}");
:root {{
  --ink: #1A1A1A; --paper: #FAFAF7; --mute: #8A8984;
  --hair: rgba(26, 26, 26, 0.09); --glass: rgba(250, 250, 247, 0.72);
  --ease: cubic-bezier(0.22, 0.61, 0.36, 1);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --ink: #E8E7E2; --paper: #0B0B0B; --mute: #7F7E79;
    --hair: rgba(232, 231, 226, 0.10); --glass: rgba(11, 11, 11, 0.66);
  }}
}}

/* chrome */
[data-testid="stDecoration"], footer, #MainMenu,
[data-testid="stHeaderActionElements"] {{ display: none !important; }}
[data-testid="stHeader"] {{
  background: var(--glass);
  backdrop-filter: saturate(120%) blur(16px);
  -webkit-backdrop-filter: saturate(120%) blur(16px);
  border-bottom: 1px solid var(--hair);
}}
::selection {{ background: var(--ink); color: var(--paper); }}

/* page */
.stMainBlockContainer {{
  max-width: 720px; padding-top: 8rem; padding-bottom: 10rem;
  animation: settle 1.6s var(--ease) both;
}}
@keyframes settle {{
  from {{ opacity: 0; transform: translateY(4px); }}
  to   {{ opacity: 1; transform: none; }}
}}
[data-testid="stVerticalBlock"] {{ gap: 1.5rem; }}

/* type */
.stApp h1, .stApp h2, .stApp h3 {{
  font-family: {SERIF}; font-weight: 300; letter-spacing: 0; color: var(--ink);
  font-variant-numeric: lining-nums;
}}
.stApp h2 {{ font-size: 2.1rem; line-height: 1.2; padding: 0 0 2rem; }}
.stApp h3 {{ font-size: 1.45rem; line-height: 1.3; padding: 0; }}
.stApp h4 {{
  font-family: {SANS}; font-size: 0.68rem; font-weight: 400;
  letter-spacing: 0.32em; text-transform: uppercase; color: var(--mute);
  border-top: 1px solid var(--hair); padding: 2rem 0 0; margin-top: 3rem;
}}
.stApp p, .stApp li {{ line-height: 1.8; }}
[data-testid="stCaptionContainer"], .stApp small {{ color: var(--mute); letter-spacing: 0.02em; }}
.stApp a {{ color: var(--ink); text-underline-offset: 0.25em; text-decoration-thickness: 1px; }}
.stApp hr {{ border-color: var(--hair); margin: 2.4rem 0; }}

/* numbers */
[data-testid="stMetric"] {{ border-top: 1px solid var(--hair); padding-top: 1.1rem; }}
[data-testid="stMetricLabel"] p {{
  font-size: 0.7rem; letter-spacing: 0.24em; text-transform: uppercase; color: var(--mute);
}}
[data-testid="stMetricValue"] {{
  font-family: {SERIF}; font-weight: 300; font-size: 2.1rem; font-variant-numeric: lining-nums;
}}

/* controls */
.stApp a, .stApp button, .stApp summary, [data-baseweb="input"],
[data-baseweb="select"] > div, [data-baseweb="textarea"] {{
  transition: color .6s var(--ease), background-color .6s var(--ease),
              border-color .6s var(--ease), opacity .6s var(--ease);
}}
.stButton button, .stFormSubmitButton button, .stDownloadButton button {{
  font-size: 0.74rem; font-weight: 400; letter-spacing: 0.22em; padding: 0.9rem 1.6rem; min-height: 3.1rem;
}}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"] {{
  background: var(--ink); color: var(--paper); border: 1px solid var(--ink);
}}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primaryFormSubmit"]:hover {{
  background: transparent; color: var(--ink);
}}
.stButton button[kind="secondary"], .stDownloadButton button {{
  background: transparent; border: 1px solid var(--hair);
}}
.stButton button[kind="secondary"]:hover, .stDownloadButton button:hover {{
  border-color: var(--ink); color: var(--ink);
}}
[data-testid="stWidgetLabel"] p {{ font-size: 0.8rem; letter-spacing: 0.06em; color: var(--mute); }}

/* disclosure */
[data-testid="stExpander"] details {{
  background: transparent; border: none; border-radius: 0;
  border-bottom: 1px solid var(--hair);
}}
[data-testid="stExpander"] summary:hover {{ opacity: 0.6; }}

/* notices: no color, a single rule */
[data-testid="stAlertContainer"] {{
  background: transparent !important; color: var(--ink) !important;
  border: 1px solid var(--hair); border-left: 2px solid var(--ink);
}}
[data-testid="stAlertContainer"] [data-testid="stAlertDynamicIcon"] {{ display: none; }}

/* conversation: text on paper, her words set off by a rule */
[data-testid^="stChatMessageAvatar"] {{ display: none; }}
[data-testid="stChatMessage"] {{
  background: transparent; border-radius: 0; padding: 1.4rem 0; gap: 0;
  border-bottom: 1px solid var(--hair);
  animation: settle 0.9s var(--ease) both;
}}
[data-testid="stChatMessage"] + [data-testid="stChatMessage"] {{ margin-top: 0; }}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  border-bottom: none; border-left: 1px solid var(--mute);
  padding: 0.2rem 0 0.2rem 1.4rem; margin: 0.6rem 0;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {{
  font-family: {SERIF}; font-size: 1.15rem; color: var(--mute);
}}
[data-testid="stBottom"] > div {{
  background: var(--glass);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
}}
[data-testid="stChatInput"] > div {{ border-radius: 0; }}

/* tables and progress */
.stApp table {{ border-collapse: collapse; width: 100%; }}
.stApp th, .stApp td {{ border: none !important; border-bottom: 1px solid var(--hair) !important; }}
.stApp th {{ font-weight: 500; font-size: 0.72rem; letter-spacing: 0.14em; color: var(--mute); }}
[data-testid="stProgress"] [role="progressbar"],
[data-testid="stProgress"] [role="progressbar"] div {{ height: 1px !important; }}
.stApp [data-testid="stMarkdownContainer"] td {{ font-size: 0.82rem; }}
.stApp [data-testid="stMarkdownContainer"] strong {{ font-weight: 500; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: var(--paper); border-right: 1px solid var(--hair); }}
[data-testid="stSidebar"] h3 {{
  font-family: {SANS}; font-size: 0.72rem; font-weight: 400;
  letter-spacing: 0.36em; padding-top: 0.5rem;
}}
[data-testid="stSidebarNav"] a {{ background: transparent !important; border-radius: 0; }}
[data-testid="stSidebarNav"] a span {{ letter-spacing: 0.08em; color: var(--mute); }}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: var(--ink); font-weight: 400; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ box-shadow: inset 1px 0 0 var(--ink); }}
</style>
"""


def inject():
    st.html(CSS)
