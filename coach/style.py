"""Look of the app: monochrome "liquid glass" on a softly lit environment,
light or dark with the system or the theme picked in Settings.

Colors and fonts live in .streamlit/config.toml (every palette color,
status colors included, is a gray). This adds what the theme can't
express: the lit environment, thin glass surfaces with a light-catching
edge, the type scale and motion. Glass is used only where there is
something to touch or something selected: buttons, the current page,
today in the calendar, her own messages and the chat bar. The one hue is
the pale air-blue liquid of the course progress bar (LIQUID below)."""
import streamlit as st

# Headings and numbers: Newsreader (light) with Noto Serif TC for Chinese;
# body text: Inter with Noto Sans TC.
SERIF = '"Newsreader", "Noto Serif TC", serif'
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600"
         "&family=Noto+Sans+TC:wght@300;400;500&family=Newsreader:opsz,wght@6..72,300;6..72,400"
         "&family=Noto+Serif+TC:wght@300;400;500&display=swap")

CSS = f"""
<style>
@import url("{FONTS}");
:root {{
  /* grayscale only; each token is light-dark(light, dark). Streamlit sets
     color-scheme on .stApp from the active theme (system or the one picked
     in Settings), and light-dark() follows it. */
  --env: light-dark(#F2F2F2, #080808);
  --light-1: light-dark(rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.06));
  --light-2: light-dark(rgba(0, 0, 0, 0.035), rgba(255, 255, 255, 0.035));
  --light-3: light-dark(rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.04));
  --label: light-dark(#141414, #EDEDED); --label-2: light-dark(#5C5C5C, #9B9B9B);
  --label-3: light-dark(#8C8C8C, #6A6A6A); --strong: light-dark(#000000, #FFFFFF);
  --hair: light-dark(rgba(0, 0, 0, 0.08), rgba(255, 255, 255, 0.08));
  --wash: light-dark(rgba(0, 0, 0, 0.05), rgba(255, 255, 255, 0.06));
  --field: light-dark(rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.03));
  --field-edge: light-dark(rgba(0, 0, 0, 0.12), rgba(255, 255, 255, 0.12));
  --field-focus: light-dark(rgba(0, 0, 0, 0.45), rgba(255, 255, 255, 0.5));
  --chrome: light-dark(rgba(255, 255, 255, 0.4), rgba(255, 255, 255, 0.02));
  --sidebar: light-dark(rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.015));
  --popover: light-dark(rgba(250, 250, 250, 0.82), rgba(20, 20, 20, 0.72));
  --popover-edge: light-dark(rgba(0, 0, 0, 0.1), rgba(255, 255, 255, 0.18));
  --outline: light-dark(rgba(0, 0, 0, 0.6), rgba(255, 255, 255, 0.7));
  --selection: light-dark(rgba(0, 0, 0, 0.14), rgba(255, 255, 255, 0.22));

  /* glass */
  --glass: light-dark(rgba(255, 255, 255, 0.45), rgba(255, 255, 255, 0.04));
  --glass-strong: light-dark(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.08));
  --glass-faint: light-dark(rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.02));
  --glass-edge: light-dark(rgba(0, 0, 0, 0.14), rgba(255, 255, 255, 0.42));
  --glass-edge-strong: light-dark(rgba(0, 0, 0, 0.28), rgba(255, 255, 255, 0.6));
  --glass-edge-soft: light-dark(rgba(0, 0, 0, 0.12), rgba(255, 255, 255, 0.22));
  --glass-edge-bubble: light-dark(rgba(0, 0, 0, 0.12), rgba(255, 255, 255, 0.3));
  --glass-edge-circle: light-dark(rgba(0, 0, 0, 0.35), rgba(255, 255, 255, 0.4));
  --hilite: light-dark(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.5));
  --hilite-soft: light-dark(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.28));
  --shadow: light-dark(rgba(0, 0, 0, 0.06), rgba(0, 0, 0, 0.12));
  --glass-blur: blur(8px) saturate(100%);
  --glass-depth: inset 0 1px var(--hilite), 0 12px 40px var(--shadow);
  --glass-depth-soft: inset 0 1px var(--hilite-soft), 0 8px 24px var(--shadow);

  /* geometry */
  --radius-small: 12px; --radius-medium: 16px; --radius-large: 24px; --radius-pill: 999px;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
  --control: 44px;

  /* motion */
  --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  --t-micro: 200ms; --t-space: 400ms;
}}

/* ---------- environment: dark interior, soft grayscale light ---------- */
.stApp {{ background: var(--env); }}
.stApp::before {{
  content: ""; position: fixed; inset: -12%; pointer-events: none; z-index: 0;
  background:
    radial-gradient(circle at 20% 20%, var(--light-1), transparent 30%),
    radial-gradient(circle at 80% 30%, var(--light-2), transparent 28%),
    radial-gradient(circle at 55% 105%, var(--light-3), transparent 38%);
  animation: ambient 90s ease-in-out infinite alternate;
}}
@keyframes ambient {{
  from {{ transform: translate3d(0, 0, 0); }}
  to   {{ transform: translate3d(-2.5%, 1.5%, 0); }}
}}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{ position: relative; z-index: 1; background: transparent; }}
::selection {{ background: var(--selection); color: var(--strong); }}

/* ---------- chrome ---------- */
[data-testid="stDecoration"], footer,
[data-testid="stHeaderActionElements"] {{ display: none !important; }}
[data-testid="stHeader"] {{
  background: var(--chrome);
  backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
  border-bottom: 1px solid var(--hair);
}}
[data-testid="stSidebar"] {{
  background: var(--sidebar);
  backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
  border-right: 1px solid var(--hair);
}}

/* ---------- page ---------- */
.stMainBlockContainer {{
  max-width: 720px; padding: var(--space-8) var(--space-5) 160px;
  animation: arrive var(--t-space) var(--ease) both;
}}
@keyframes arrive {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: none; }}
}}
@media (min-width: 768px) {{ .stMainBlockContainer {{ padding-top: 96px; }} }}
[data-testid="stVerticalBlock"] {{ gap: var(--space-5); }}

/* ---------- type ---------- */
.stApp h1, .stApp h2, .stApp h3 {{ color: var(--label); font-family: {SERIF}; font-weight: 300; font-variant-numeric: lining-nums; }}
.stApp h2 {{ font-size: 2.25rem; line-height: 1.12; letter-spacing: 0; padding: 0 0 var(--space-3); }}
.stApp h3 {{ font-size: 1.375rem; line-height: 1.25; letter-spacing: 0; padding: 0; }}
.stApp h4 {{
  font-size: 0.8125rem; font-weight: 600; letter-spacing: 0; color: var(--label-2);
  padding: var(--space-6) 0 0; margin: 0;
}}
.stApp p, .stApp li {{ line-height: 1.65; }}
[data-testid="stCaptionContainer"], .stApp small {{ color: var(--label-3); }}
.stApp a {{ color: var(--label); text-underline-offset: 0.2em; text-decoration-color: var(--label-3); }}
.stApp hr {{ border-color: var(--hair); margin: var(--space-6) 0; }}
.stApp [data-testid="stMarkdownContainer"] strong {{ font-weight: 600; }}
[data-testid="stWidgetLabel"] p {{ font-size: 0.8125rem; color: var(--label-2); }}

/* ---------- numbers: typography, no boxes ---------- */
[data-testid="stMetricLabel"] p {{ font-size: 0.75rem; color: var(--label-3); }}
[data-testid="stMetricValue"] {{
  font-family: {SERIF}; font-size: 1.875rem; font-weight: 300; letter-spacing: 0;
  font-variant-numeric: lining-nums tabular-nums;
}}

/* ---------- buttons: thin glass ---------- */
.stButton button, .stFormSubmitButton button, .stDownloadButton button {{
  min-height: var(--control); padding: 0 var(--space-5);
  border-radius: var(--radius-small); font-weight: 500; letter-spacing: 0.01em;
  background: var(--glass-faint); color: var(--label);
  border: 1px solid var(--glass-edge-soft);
  backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--glass-depth-soft);
  transition: background-color var(--t-micro) var(--ease), border-color var(--t-micro) var(--ease),
              transform var(--t-micro) var(--ease), box-shadow var(--t-micro) var(--ease);
}}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"] {{
  background: var(--glass-strong); color: var(--strong);
  border-color: var(--glass-edge-strong); box-shadow: var(--glass-depth);
}}
.stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {{
  background: var(--glass-strong); border-color: var(--glass-edge-strong); color: var(--strong);
}}
.stButton button:active, .stFormSubmitButton button:active, .stDownloadButton button:active {{
  transform: scale(0.97);
}}
.stButton button:focus-visible, .stFormSubmitButton button:focus-visible,
.stDownloadButton button:focus-visible {{
  outline: 1px solid var(--outline); outline-offset: 2px; box-shadow: var(--glass-depth);
}}

/* ---------- fields: quiet wells, not glass ---------- */
[data-testid="stSelectbox"] [role="group"], [data-testid="stDateInputField"],
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"] {{
  min-height: var(--control); box-sizing: border-box;
  background: var(--field) !important; border: 1px solid var(--field-edge) !important;
  border-radius: var(--radius-small) !important;
  transition: border-color var(--t-micro) var(--ease);
}}
[data-testid="stTextAreaRootElement"] {{ min-height: 0; }}
[data-testid="stSelectbox"] [role="group"]:focus-within, [data-testid="stDateInputField"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stTextAreaRootElement"]:focus-within {{
  border-color: var(--field-focus) !important;
}}
[data-testid="stSelectbox"] input, [data-testid="stTextInputRootElement"] input,
[data-testid="stTextAreaRootElement"] textarea {{ background: transparent !important; }}

/* floating menus and the date picker: glass above the page. They are
   rendered outside .stApp, where color-scheme isn't set, so their colors
   come from the theme's text color instead: the fill is that color
   inverted (dark behind light text, light behind dark text). */
[data-trigger] {{
  --strong: currentColor;
  --wash: rgb(from currentColor r g b / 0.07);
  --glass-strong: rgb(from currentColor r g b / 0.1);
  --glass-edge-strong: rgb(from currentColor r g b / 0.5);
  --hilite: rgba(255, 255, 255, 0.5);
  background: rgb(from currentColor calc(255 - r) calc(255 - g) calc(255 - b) / 0.82) !important;
  backdrop-filter: blur(10px) saturate(100%); -webkit-backdrop-filter: blur(10px) saturate(100%);
  border: 1px solid rgb(from currentColor r g b / 0.14) !important; border-radius: var(--radius-medium) !important;
  box-shadow: var(--glass-depth-soft) !important; overflow: hidden;
  animation: fade var(--t-space) var(--ease) both;   /* opacity only: the popover is positioned by transform */
}}
@keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
[role="grid"] {{   /* the date picker also renders outside .stApp */
  --strong: currentColor;
  --wash: rgb(from currentColor r g b / 0.07);
  --glass-strong: rgb(from currentColor r g b / 0.1);
  --glass-edge-strong: rgb(from currentColor r g b / 0.5);
  --hilite: rgba(255, 255, 255, 0.5);
}}
[role="grid"] [role="button"] {{
  border-radius: 50% !important; border: 1px solid transparent;
  transition: background-color 300ms var(--ease), border-color 300ms var(--ease), transform 300ms var(--ease);
}}
[role="grid"] [role="button"][data-selected="true"] {{
  background: var(--glass-strong) !important; color: var(--strong) !important;
  border-color: var(--glass-edge-strong) !important; box-shadow: inset 0 1px var(--hilite);
  animation: settle 300ms var(--ease) both;
}}
[role="grid"] [role="button"][data-hovered="true"]:not([data-selected="true"]) {{ background: var(--wash) !important; }}

/* ---------- checkbox: a glass circle, the tick draws itself ---------- */
[data-testid="stCheckbox"] label {{ align-items: center; gap: var(--space-3); min-height: var(--control); }}
[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p {{ margin: 0; line-height: 22px; }}
[data-testid="stCheckbox"] label > div:has(> svg) {{
  width: 22px; height: 22px; flex: 0 0 22px; margin: 0 !important; border-radius: 50%; box-sizing: border-box;
  display: grid; place-items: center;
  background: transparent !important; border: 1px solid var(--glass-edge-circle) !important;
  transition: background-color var(--t-micro) var(--ease), border-color var(--t-micro) var(--ease),
              box-shadow var(--t-micro) var(--ease);
}}
[data-testid="stCheckbox"][data-selected="true"] label > div:has(> svg) {{
  background: var(--glass-strong) !important; border-color: var(--glass-edge-strong) !important;
  box-shadow: inset 0 1px var(--hilite);
}}
[data-testid="stCheckbox"] label > div > svg {{ width: 11px; height: 9px; overflow: visible; opacity: 1 !important; }}
[data-testid="stCheckbox"] label > div > svg polyline {{
  fill: none; stroke: var(--strong) !important; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: 14; stroke-dashoffset: 14;
  transition: stroke-dashoffset 300ms var(--ease);
}}
[data-testid="stCheckbox"][data-selected="true"] label > div > svg polyline {{ stroke-dashoffset: 0; }}

/* ---------- navigation: glass pill on the current page ---------- */
[data-testid="stSidebarNav"] a {{
  min-height: 36px; border-radius: var(--radius-small); border: 1px solid transparent;
  background: transparent !important;
  transition: background-color var(--t-space) var(--ease), border-color var(--t-space) var(--ease),
              box-shadow var(--t-space) var(--ease);
}}
[data-testid="stSidebarNav"] a span {{ color: var(--label-2); }}
[data-testid="stSidebarNav"] a:hover span {{ color: var(--label); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: var(--glass) !important; border-color: var(--glass-edge);
  box-shadow: var(--glass-depth-soft);
}}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: var(--strong); font-weight: 500; }}
[data-testid="stSidebar"] h3 {{ font-size: 1.125rem; font-weight: 400; }}

/* ---------- disclosure: hairlines only ---------- */
[data-testid="stExpander"] details {{
  background: transparent; border: none; border-radius: 0; border-bottom: 1px solid var(--hair);
}}
[data-testid="stExpander"] summary {{ min-height: var(--control); transition: color var(--t-micro) var(--ease); }}
[data-testid="stExpander"] summary:hover {{ color: var(--strong); }}

/* ---------- notices: gray text on a hairline, no color ---------- */
[data-testid="stAlertContainer"] {{
  background: transparent !important; color: var(--label) !important;
  border: 1px solid var(--field-edge); border-radius: var(--radius-small);
}}
[data-testid="stAlertContainer"] [data-testid="stAlertDynamicIcon"] {{ display: none; }}
[data-testid="stToast"] {{
  background: var(--popover) !important; border: 1px solid var(--popover-edge);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-radius: var(--radius-medium);
}}

/* ---------- conversation ---------- */
[data-testid^="stChatMessageAvatar"] {{ display: none; }}
[data-testid="stChatMessage"] {{
  background: transparent; padding: 0; gap: 0;
  animation: arrive var(--t-space) var(--ease) both;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  width: fit-content; max-width: 85%; margin-left: auto;
  padding: var(--space-3) var(--space-4); border-radius: var(--radius-large);
  background: var(--glass); border: 1px solid var(--glass-edge-bubble);
  backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--glass-depth-soft);
}}
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] {{
  background: transparent !important;
}}
[data-testid="stChatInput"] {{
  min-height: 56px; box-sizing: border-box;
  border-radius: var(--radius-large) !important;
  background: var(--glass) !important; border: 1px solid var(--glass-edge) !important;
  backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--glass-depth);
}}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea {{ background: transparent !important; border: none !important; }}
[data-testid="stChatInputSubmitButton"] {{ border-radius: 50% !important; background: transparent !important; }}

/* ---------- progress: a hairline filling with light ---------- */
[data-testid="stProgress"] [role="progressbar"],
[data-testid="stProgress"] [role="progressbar"] div {{ height: 2px !important; border-radius: 1px; }}

/* ---------- lesson diagrams: natural size, centered, never wider than the page ---------- */
[data-testid="stGraphVizChart"] {{ display: flex; justify-content: center; margin: var(--space-2) 0; }}
[data-testid="stGraphVizChart"] svg {{ max-width: 100%; height: auto; }}

/* ---------- lesson tables: hairlines, no fills ---------- */
.stApp [data-testid="stMarkdownContainer"] table {{ border-collapse: collapse; width: 100%; font-size: 0.875rem; }}
.stApp [data-testid="stMarkdownContainer"] th, .stApp [data-testid="stMarkdownContainer"] td {{
  border: none !important; border-bottom: 1px solid var(--hair) !important;
  background: transparent !important; padding: var(--space-2) var(--space-3); text-align: left;
  word-break: keep-all;   /* short Chinese terms stay on one line on phones */
}}
.stApp [data-testid="stMarkdownContainer"]:has(> table) {{ overflow-x: auto; }}   /* a wide table scrolls, not the page */

.stApp [data-testid="stMarkdownContainer"] th {{ color: var(--label-2); font-weight: 500; }}

/* ---------- calendar (Progress page) ---------- */
.cal {{ display: grid; gap: var(--space-4); }}
.cal-head {{ display: flex; align-items: baseline; justify-content: space-between; }}
.cal-month {{ font-family: {SERIF}; font-size: 1.375rem; font-weight: 300; font-variant-numeric: lining-nums; color: var(--label); }}
.cal-range {{ font-size: 0.8125rem; color: var(--label-3); }}
.cal-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); row-gap: var(--space-2); }}
.cal-wd {{ text-align: center; font-size: 0.75rem; color: var(--label-3); padding-bottom: var(--space-2); }}
.cal-day {{
  position: relative; display: grid; place-items: center; justify-self: center;
  width: 40px; height: 48px; border-radius: var(--radius-small); border: 1px solid transparent;
  font-size: 0.9375rem; font-variant-numeric: tabular-nums; color: var(--label-2);
}}
.cal-day b {{ font-weight: 400; line-height: 1; transform: translateY(-3px); }}
.cal-day i {{
  position: absolute; bottom: 9px; left: 50%; width: 4px; height: 4px; margin-left: -2px;
  border-radius: 50%; box-sizing: border-box;
}}
.cal-day.done {{ color: var(--label); }}
.cal-day.done i {{ background: var(--label); }}
.cal-day.started i {{ border: 1px solid var(--label-2); }}
.cal-day.future {{ color: var(--label-3); opacity: 0.5; }}
.cal-day.today {{
  color: var(--strong); background: var(--glass); border-color: var(--glass-edge);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  box-shadow: var(--glass-depth-soft);
  animation: settle 300ms var(--ease) both;
}}
.cal-day.today b {{ font-weight: 600; }}
@keyframes settle {{ from {{ opacity: 0; transform: scale(0.98); }} to {{ opacity: 1; transform: none; }} }}
.cal-legend {{ display: flex; gap: var(--space-5); font-size: 0.75rem; color: var(--label-3); }}
.cal-legend span {{ display: inline-flex; align-items: center; gap: var(--space-2); }}
.cal-legend i {{ width: 6px; height: 6px; border-radius: 50%; box-sizing: border-box; }}
@media (max-width: 360px) {{ .cal-day {{ width: 36px; }} }}

/* ---------- small screens: recompose ---------- */
@media (max-width: 640px) {{
  .stMainBlockContainer {{ padding: 88px var(--space-4) 160px; }}
  .stApp h2 {{ font-size: 1.875rem; }}
  [data-testid="stVerticalBlock"] {{ gap: var(--space-4); }}
  /* the four numbers become a 2 × 2 grid instead of a tall column */
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{
    flex-flow: row wrap !important; row-gap: var(--space-5); column-gap: var(--space-4);
  }}
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {{
    flex: 0 0 calc(50% - var(--space-2)) !important; width: calc(50% - var(--space-2)) !important; min-width: 0 !important;
  }}
}}

/* ---------- reduced motion: a still version ---------- */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
}}
</style>
"""

# The course progress bar (coach/progress_bar.py): the one place with a hue,
# a pale air-blue liquid in clear glass. Kept apart from CSS because the
# @property rules would need every brace doubled in the f-string. Their
# "<number>" is written \3C number> (the same string to CSS) because st.html
# sanitizes the markup and a literal "<number" reads as a tag, which drops
# the whole stylesheet.
LIQUID = """
<style>
@property --p { syntax: "\\3C number>"; inherits: true; initial-value: 0; }      /* the liquid's front */
@property --surge { syntax: "\\3C number>"; inherits: true; initial-value: 0; }  /* 0 still … 1 moving */
:root {
  --lq-liquid: light-dark(#C2D8E7, #D0E2EF);     /* one step deeper on a pale page */
  --lq-hi: #EAF4FA;
  --lq-deep: light-dark(#B4CEE0, #C2D8E7);
  --lq-glow: light-dark(#D0E2EF, #D9EBF7);
  --lq-glass-top: light-dark(rgba(0, 0, 0, 0.01), rgba(255, 255, 255, 0.03));
  --lq-glass-bottom: light-dark(rgba(0, 0, 0, 0.022), rgba(255, 255, 255, 0.012));
  --lq-edge-hi: light-dark(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.14));
  --lq-edge-lo: light-dark(rgba(0, 0, 0, 0.05), rgba(0, 0, 0, 0.35));
}
.lq {
  --height: 9px; --inset: 2.5px;               /* the liquid is 4px */
  --lh: calc((var(--height) - 2 * var(--inset)) / 2);
  --p: var(--to);
  display: grid; gap: 14px; margin: 4px 0 8px;
}
.lq-label { font-size: 0.6875rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--label-3); }
.lq-head { display: flex; align-items: baseline; justify-content: space-between; gap: 24px; }
.lq-title {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; font-variant-numeric: lining-nums;
  font-size: 1.625rem; line-height: 1.2; color: var(--label); min-width: 0;
}
.lq-pct {
  font-family: "Newsreader", serif; font-weight: 300; font-size: 2.125rem; line-height: 1;
  font-variant-numeric: lining-nums tabular-nums; color: var(--label); flex: none;
}
.lq-pct span { font-size: 0.55em; margin-left: 2px; color: var(--label-2); }
.lq-meta { display: flex; justify-content: space-between; gap: 16px; font-size: 0.8125rem; color: var(--label-2); font-variant-numeric: tabular-nums; }
.lq.compact { gap: 10px; }
.lq.compact .lq-title { font-size: 1.1875rem; }
.lq.compact .lq-pct { font-size: 1.5rem; }

/* the glass: no frame, a clear sliver with a trace of edge */
.lq-glass {
  position: relative; height: var(--height); padding: var(--inset) 0; box-sizing: border-box;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 0 0.5px 0 var(--lq-edge-hi), inset 0 -0.5px 0 var(--lq-edge-lo);
  backdrop-filter: blur(1.5px); -webkit-backdrop-filter: blur(1.5px);
}
/* the liquid: full colour to a soft round end, a touch lighter there so no
   colour gathers; while flowing the end draws out a little */
.lq-liquid {
  position: relative; height: 100%;
  width: max(calc(var(--lh) * 2), calc(var(--p) * 1%));
  /* exact radii: a 999px corner would make the browser shrink them all */
  border-radius: var(--lh) calc(var(--lh) * (1.3 + var(--surge) * 1.6)) calc(var(--lh) * (1.1 + var(--surge) * 0.8)) var(--lh) /
                 var(--lh) var(--lh) var(--lh) var(--lh);
  background: linear-gradient(90deg,
    color-mix(in srgb, var(--lq-liquid) 88%, var(--lq-deep)) 0%,
    var(--lq-liquid) 55%,
    color-mix(in srgb, var(--lq-liquid) 75%, var(--lq-hi)) calc(100% - 14px),
    color-mix(in srgb, var(--lq-liquid) 60%, var(--lq-hi)) 100%);
  opacity: 0.92;
  box-shadow: 0 0 6px color-mix(in srgb, var(--lq-glow) 7%, transparent);
}
.lq-liquid::after {              /* the one light response, barely there */
  content: ""; position: absolute; left: 0; right: 0; top: 0; height: 45%; border-radius: inherit;
  background: linear-gradient(90deg, transparent 10%,
    color-mix(in srgb, var(--lq-hi) calc(14% + var(--surge) * 10%), transparent) 55%, transparent 95%);
}
.lq.empty .lq-liquid { opacity: 0.45; }   /* a droplet at the start, so the bar is never missing */

/* motion: flows in, settles, then is still (no bounce, no loop) */
.lq.flowing .lq-liquid {
  animation: lq-front 950ms cubic-bezier(0.3, 0.6, 0.25, 1) both,
             lq-surge 1100ms cubic-bezier(0.4, 0, 0.3, 1) both;
}
@keyframes lq-front { from { --p: var(--from); } to { --p: var(--to); } }
@keyframes lq-surge { 0% { --surge: 0; } 30% { --surge: 1; } 100% { --surge: 0; } }

/* Today's course card: the day's lessons are the progress bar. Each
   lesson is one stretch of the same liquid line, its number below; a
   ticked lesson is filled. Opening a lesson only marks its number, so
   going back to review never empties the bar. */
[class*="st-key-course_card"] { gap: 10px; }
[class*="st-key-course_card"] .stElementContainer:has(> [data-testid="stButtonGroup"]),
[class*="st-key-course_card"] [data-testid="stButtonGroup"] { width: 100% !important; max-width: none; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] > div {
  display: flex; flex-wrap: nowrap; width: 100%; max-width: none; gap: 0;
  border: none !important; background: transparent !important; box-shadow: none !important;
}
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button {
  --lh: 2px;
  position: relative; flex: 1 1 0; min-width: 0; height: auto; min-height: 44px;
  padding: 20px 0 4px !important; margin: 0 !important;
  border: none !important; border-radius: 0 !important; background: transparent !important; box-shadow: none !important;
  color: var(--label-3); transition: color var(--t-micro) var(--ease);
}
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button p {
  font-size: 0.8125rem; font-variant-numeric: tabular-nums; white-space: nowrap; color: inherit;
}
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button [data-testid="stMarkdownContainer"] { min-width: max-content; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button span:has(> [data-testid="stIconMaterial"]) { display: none; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:hover { color: var(--label-2); }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button[aria-checked="true"] { color: var(--label); }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button[aria-checked="true"] p { font-weight: 600; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:focus-visible { outline: none; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:focus-visible p { outline: 1px solid var(--outline); outline-offset: 3px; border-radius: 4px; }
/* the glass line, continuous across the lessons */
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button::before {
  content: ""; position: absolute; left: 0; right: 0; top: 4px; height: 9px;
  background: linear-gradient(180deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 0 0.5px 0 var(--lq-edge-hi), inset 0 -0.5px 0 var(--lq-edge-lo);
}
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:first-child::before { border-radius: 999px 0 0 999px; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:last-child::before { border-radius: 0 999px 999px 0; }
/* the liquid in a ticked lesson; the last filled one ends in a round meniscus */
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button::after {
  content: ""; position: absolute; left: 0; top: 6.5px; height: 4px; width: 0;
  background: var(--lq-liquid); opacity: 0.92;
}
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:first-child::after { left: 0; border-top-left-radius: 2px; border-bottom-left-radius: 2px; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:has([data-testid="stIconMaterial"])::after { width: 100%; }
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:has([data-testid="stIconMaterial"]):not(:has(+ button [data-testid="stIconMaterial"]))::after {
  border-radius: 0 2.6px 2.2px 0 / 0 2px 2px 0;
  background: linear-gradient(90deg, var(--lq-liquid) calc(100% - 14px), color-mix(in srgb, var(--lq-liquid) 60%, var(--lq-hi)));
}
[class*="st-key-course_card"] [data-testid="stButtonGroup"] button:first-child:has([data-testid="stIconMaterial"]):not(:has(+ button [data-testid="stIconMaterial"]))::after {
  border-radius: 2px 2.6px 2.2px 2px / 2px 2px 2px 2px;
}
@keyframes lq-fill { from { width: 0; } to { width: 100%; } }

@media (max-width: 640px) {
  .lq { --height: 8px; --inset: 2.25px; }
  .lq-title { font-size: 1.375rem; }
  .lq-pct { font-size: 1.875rem; }
}
@media (prefers-reduced-motion: reduce) {
  .lq.flowing .lq-liquid { animation: none; }
}
</style>
"""

# Motion for the lesson bar on Today (views/daily.py picks the container
# key): on arriving the ticked lessons fill one after another, ~1 s in all;
# when one lesson is ticked only that stretch fills.
_SEG = '[data-testid="stButtonGroup"] button'
_DONE = ':has([data-testid="stIconMaterial"])'
LESSON_MOTION = "".join(
    f'.st-key-course_card_flow {_SEG}:nth-child({k}){_DONE}::after '
    f'{{ animation: lq-fill 200ms linear {(k - 1) * 200}ms both; }}\n'
    for k in range(1, 8)
) + (
    f'.st-key-course_card_flow {_SEG}{_DONE}:not(:has(+ button [data-testid="stIconMaterial"]))::after '
    '{ animation-duration: 420ms; animation-timing-function: cubic-bezier(0.3, 0.6, 0.25, 1); }\n'
) + "".join(
    f'.st-key-course_card_tick{k} {_SEG}:nth-child({k})::after '
    '{ animation: lq-fill 700ms cubic-bezier(0.3, 0.6, 0.25, 1) both; }\n'
    for k in range(1, 8)
)


def stylesheet() -> str:
    return CSS.replace("</style>", LIQUID.replace("<style>", "").replace("</style>", LESSON_MOTION + "</style>"))


def inject():
    st.html(stylesheet())
