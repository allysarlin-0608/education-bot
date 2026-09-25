"""Look of the app: monochrome "liquid glass" on pure white or pure black,
light or dark with the system or the theme picked in Settings.

Colors and fonts live in .streamlit/config.toml (every palette color,
status colors included, is a gray). This adds what the theme can't
express: the lit environment, thin glass surfaces with a light-catching
edge, the type scale and motion. Glass is used only where there is
something to touch or something selected: buttons, the current page,
today in the calendar, her own messages and the chat bar. The one hue is
the pale air-blue liquid of the course progress bar (LIQUID below)."""
import streamlit as st

from coach import glass

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
  --env: light-dark(#FFFFFF, #000000);          /* pure white or pure black, nothing else */
  --label: light-dark(#141414, #EDEDED); --label-2: light-dark(#5C5C5C, #9B9B9B);
  --label-3: light-dark(#8C8C8C, #6A6A6A); --strong: light-dark(#000000, #FFFFFF);
  --hair: light-dark(rgba(0, 0, 0, 0.07), rgba(255, 255, 255, 0.07));
  --wash: light-dark(rgba(0, 0, 0, 0.05), rgba(255, 255, 255, 0.06));
  --field: light-dark(rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.03));
  --field-edge: light-dark(rgba(0, 0, 0, 0.12), rgba(255, 255, 255, 0.12));
  --field-focus: light-dark(rgba(0, 0, 0, 0.45), rgba(255, 255, 255, 0.5));
  --chrome: light-dark(rgba(255, 255, 255, 0.4), rgba(255, 255, 255, 0.02));
  --sidebar: light-dark(rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.015));
  --popover: light-dark(rgba(250, 250, 250, 0.82), rgba(20, 20, 20, 0.72));
  --popover-edge: light-dark(rgba(0, 0, 0, 0.06), rgba(255, 255, 255, 0.1));
  --outline: light-dark(rgba(0, 0, 0, 0.6), rgba(255, 255, 255, 0.7));
  --selection: light-dark(rgba(0, 0, 0, 0.14), rgba(255, 255, 255, 0.22));

  /* glass: thin, lightly frosted, physically curved. What's behind stays
     clearly visible and recognizable, just softened (a light frost, never
     milky or cloudy); the rim bends it a little more, diffuses it a little
     more and gathers a trace of light, which is what gives the glass its
     rounded, slightly thick edge. Only greys; no colour, no stroke, no glow. */
  --glass: light-dark(rgba(0, 0, 0, 0.012), rgba(255, 255, 255, 0.028));
  --glass-strong: light-dark(rgba(0, 0, 0, 0.026), rgba(255, 255, 255, 0.05));
  --glass-faint: light-dark(rgba(0, 0, 0, 0.006), rgba(255, 255, 255, 0.016));
  --glass-edge: transparent;
  --glass-edge-strong: transparent;
  --glass-edge-soft: transparent;
  --glass-edge-bubble: transparent;
  --glass-edge-circle: light-dark(rgba(0, 0, 0, 0.3), rgba(255, 255, 255, 0.36));
  --hilite: light-dark(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.14));
  --hilite-soft: light-dark(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.1));
  --shadow: light-dark(rgba(0, 0, 0, 0.035), rgba(0, 0, 0, 0.5));
  /* the frost: light, over the whole surface. Where the browser can (Chromium,
     marked by coach/glass.py) the lg-refract filter does it and adds the rim;
     elsewhere a plain light blur. The chat box also quiets what passes behind
     it a little, so what she types stays readable. Dark theme: see below. */
  --glass-blur: blur(1.3px);
  --glass-optics: blur(1.4px);
  --glass-optics-legible: blur(2px) contrast(0.45) brightness(1.4);
  /* thickness: a faint inner highlight along the top, the lower inner edge a
     shade deeper, and a soft band just inside the rim; all low contrast */
  --optic:
    inset 0 1px 1px -0.5px var(--hilite-soft),
    inset 0 -1px 1px -0.5px light-dark(rgba(0, 0, 0, 0.035), rgba(255, 255, 255, 0.04)),
    inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.035), rgba(255, 255, 255, 0.05)),
    inset 0 0 14px -7px light-dark(rgba(0, 0, 0, 0.07), rgba(255, 255, 255, 0.08)),
    0 1px 2px var(--shadow);
  --optic-strong:
    inset 0 1px 1px -0.5px var(--hilite),
    inset 0 -1px 1px -0.5px light-dark(rgba(0, 0, 0, 0.045), rgba(255, 255, 255, 0.05)),
    inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.045), rgba(255, 255, 255, 0.065)),
    inset 0 0 18px -8px light-dark(rgba(0, 0, 0, 0.08), rgba(255, 255, 255, 0.1)),
    0 1px 3px var(--shadow);
  --rim: var(--optic-strong);
  /* floating glass stands a hair off the page: the softest contact shadow */
  --lift: 0 8px 26px -14px light-dark(rgba(0, 0, 0, 0.2), rgba(0, 0, 0, 0.8));
  --glass-depth: var(--optic-strong);
  --glass-depth-soft: var(--optic);

  /* geometry */
  --radius-small: 16px; --radius-medium: 24px; --radius-large: 28px; --radius-pill: 999px;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
  --control: 44px;

  /* motion */
  --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  --t-micro: 200ms; --t-space: 400ms;
}}

/* ---------- environment: pure black or pure white, no ambient light ---------- */
.stApp {{ background: var(--env); }}
/* no position or z-index here: on a phone Streamlit lays the page out
   absolutely so the sidebar slides over it; overriding that squeezed the
   page into a strip beside the open sidebar */
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: transparent; }}
::selection {{ background: var(--selection); color: var(--strong); }}

/* the glass filters for the dark theme (coach/glass.py marks the page) */
:root[data-scheme="dark"] {{ --glass-optics-legible: blur(2px) brightness(0.5); }}
:root[data-refract] {{
  --glass-optics: url(#lg-refract);
  --glass-optics-legible: url(#lg-refract) blur(0.6px) contrast(0.45) brightness(1.4);
}}
:root[data-refract][data-scheme="dark"] {{
  /* on black, no gathered light at the rim (lg-refract-dim): it read as a grey slab */
  --glass-optics: url(#lg-refract-dim);
  --glass-optics-legible: url(#lg-refract-dim) blur(0.6px) brightness(0.5);
}}

/* corners: generous and continuous, the curve easing into the straight edge
   (a superellipse where the browser can draw one) */
.stButton button, .stFormSubmitButton button, [data-testid="stChatInput"], [class*="st-key-lcard_"],
[data-testid="stChatMessage"], .st-key-day_done, [data-testid="stToast"], [data-trigger],
[class*="st-key-prog_day_"], [class*="st-key-reader_"], [class*="st-key-cal_20"] button {{ corner-shape: superellipse(1.6); }}

/* ---------- chrome ---------- */
[data-testid="stDecoration"], footer,
[data-testid="stHeaderActionElements"] {{ display: none !important; }}
[data-testid="stHeader"] {{
  background: var(--glass);
  -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-optics);
}}
[data-testid="stSidebar"] {{
  background: var(--env);                /* a plain surface, so the page links stay readable over the page on a phone */
  border-right: 1px solid var(--hair);
}}

/* ---------- page ---------- */
.stMainBlockContainer {{
  max-width: 720px; padding: var(--space-8) var(--space-5) var(--space-7);
  animation: arrive var(--t-space) var(--ease) backwards;   /* not "both": a kept transform would trap the floating button */
}}
@keyframes arrive {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: none; }}
}}
@media (min-width: 768px) {{ .stMainBlockContainer {{ padding-top: 96px; }} }}
/* the lesson page (Today) is wider, for the lesson cards, tables and quiz */
.stMainBlockContainer:has([class*="st-key-course_card"]) {{ max-width: 900px; }}
[data-testid="stVerticalBlock"] {{ gap: var(--space-5); }}

/* ---------- type ---------- */
.stApp h1, .stApp h2, .stApp h3 {{ color: var(--label); font-family: {SERIF}; font-weight: 300; font-variant-numeric: lining-nums; }}
.stApp h2 {{ font-size: 2.25rem; line-height: 1.12; letter-spacing: 0; padding: 0 0 var(--space-3); }}
.stApp h3 {{ font-size: 1.625rem; line-height: 1.22; letter-spacing: 0; padding: 0; }}
/* section headings (Quiz, Last four weeks, Progress by subject, ...): the
   serif at a size that reads as a heading, in full ink */
.stApp h4 {{
  font-family: {SERIF}; font-size: 1.3125rem; font-weight: 400; line-height: 1.25;
  font-variant-numeric: lining-nums; letter-spacing: 0; color: var(--label);
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
/* hover only where there is a real pointer: on a touch screen a tap leaves :hover stuck on */
@media (hover: hover) {{
  .stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {{
    background: var(--glass-strong); border-color: var(--glass-edge-strong); color: var(--strong);
  }}
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
  --hilite: rgba(255, 255, 255, 0.3);
  background: rgb(from currentColor calc(255 - r) calc(255 - g) calc(255 - b) / 0.97) !important;
  border: 1px solid rgb(from currentColor r g b / 0.08) !important; border-radius: var(--radius-medium) !important;
  box-shadow: var(--glass-depth-soft) !important; overflow: hidden;
  animation: fade var(--t-space) var(--ease) both;   /* opacity only: the popover is positioned by transform */
}}
@keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
[role="grid"] {{   /* the date picker also renders outside .stApp */
  --strong: currentColor;
  --wash: rgb(from currentColor r g b / 0.07);
  --glass-strong: rgb(from currentColor r g b / 0.1);
  --glass-edge-strong: rgb(from currentColor r g b / 0.16);
  --hilite: rgba(255, 255, 255, 0.3);
}}
[role="grid"] [role="button"] {{
  border-radius: 50% !important; border: 1px solid transparent;
  transition: background-color 300ms var(--ease), border-color 300ms var(--ease), transform 300ms var(--ease);
}}
[role="grid"] [role="button"][data-selected="true"] {{
  background: var(--glass-strong) !important; color: var(--strong) !important;
  border-color: var(--glass-edge-strong) !important; box-shadow: inset 0 1px 1px -1px var(--hilite);
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
  box-shadow: var(--optic-strong);
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
@media (hover: hover) {{ [data-testid="stSidebarNav"] a:hover span {{ color: var(--label); }} }}
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
@media (hover: hover) {{ [data-testid="stExpander"] summary:hover {{ color: var(--strong); }} }}

/* ---------- notices: gray text on a hairline, no color ---------- */
[data-testid="stAlertContainer"] {{
  background: transparent !important; color: var(--label) !important;
  border: 1px solid var(--field-edge); border-radius: var(--radius-small);
}}
[data-testid="stAlertContainer"] [data-testid="stAlertDynamicIcon"] {{ display: none; }}
[data-testid="stToast"] {{
  background: color-mix(in srgb, var(--env) 97%, transparent) !important; border: none;
  border-radius: var(--radius-medium); box-shadow: var(--optic), var(--lift);
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
/* the chat box: a physical control resting just above the page. Readable
   first: enough of a surface behind the text for clear contrast (still a
   little see-through, with a controlled blur), a fine edge that catches the
   light, and a soft shadow to lift it off the page. It answers her: a
   touch firmer when focused, the send button fills once there is text,
   and presses in a little when tapped. */
[data-testid="stChatInput"] {{
  min-height: 56px; box-sizing: border-box;
  border-radius: var(--radius-large) !important; border: none !important;
  background: light-dark(rgba(255, 255, 255, 0.8), rgba(24, 24, 26, 0.8)) !important;
  -webkit-backdrop-filter: blur(18px) saturate(1.15); backdrop-filter: blur(18px) saturate(1.15);
  box-shadow:
    inset 0 0.5px 0 light-dark(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.1)),
    inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.085), rgba(255, 255, 255, 0.085)),
    0 1px 2px light-dark(rgba(0, 0, 0, 0.05), rgba(0, 0, 0, 0.5)),
    0 10px 30px -14px light-dark(rgba(0, 0, 0, 0.22), rgba(0, 0, 0, 0.9));
  transition: box-shadow 220ms var(--ease), background-color 220ms var(--ease);
}}
[data-testid="stChatInput"]:focus-within {{
  background: light-dark(rgba(255, 255, 255, 0.9), rgba(28, 28, 30, 0.88)) !important;
  box-shadow:
    inset 0 0.5px 0 light-dark(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.12)),
    inset 0 0 0 1px light-dark(rgba(0, 0, 0, 0.16), rgba(255, 255, 255, 0.18)),
    0 1px 2px light-dark(rgba(0, 0, 0, 0.06), rgba(0, 0, 0, 0.5)),
    0 14px 36px -14px light-dark(rgba(0, 0, 0, 0.26), rgba(0, 0, 0, 0.95));
}}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea {{ background: transparent !important; border: none !important; }}
[data-testid="stChatInput"] textarea {{ color: var(--label) !important; caret-color: var(--label); }}
[data-testid="stChatInput"] textarea::placeholder {{ color: var(--label-2); opacity: 1; }}
[data-testid="stChatInputSubmitButton"] {{
  border-radius: 50% !important; background: transparent !important; color: var(--label-3) !important;
  transition: background-color 180ms var(--ease), color 180ms var(--ease), transform 120ms var(--ease);
}}
[data-testid="stChatInputSubmitButton"]:not(:disabled) {{ background: var(--label) !important; color: var(--env) !important; }}
[data-testid="stChatInputSubmitButton"]:not(:disabled):active {{ transform: scale(0.92); }}
/* the chat box stays at the bottom of the screen while she scrolls; at the end of the page it sits in its place */
[data-testid="stLayoutWrapper"]:has(> .st-key-chat_dock), .st-key-chat_dock {{
  position: sticky; bottom: max(var(--space-4), env(safe-area-inset-bottom)); z-index: 40;   /* clear of the iPhone's home bar */
}}
/* on a page shorter than the screen it still sits at the bottom, not right under the text */
.stMainBlockContainer:has(.st-key-chat_dock) {{ min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; box-sizing: border-box; }}
.stMainBlockContainer:has(.st-key-chat_dock) > [data-testid="stVerticalBlock"] {{ flex: 1; }}
[data-testid="stLayoutWrapper"]:has(> .st-key-chat_dock) {{ margin-top: auto; }}

/* ---------- progress: a hairline filling with light ---------- */
[data-testid="stProgress"] [role="progressbar"],
[data-testid="stProgress"] [role="progressbar"] div {{ height: 2px !important; border-radius: 1px; }}

/* ---------- where a move lands (below the header) ---------- */
.jump-anchor {{ height: 0; scroll-margin-top: 96px; }}      /* land below the header */
[data-testid="stElementContainer"]:has(#coach-place) {{ display: none; }}
[data-testid="stElementContainer"]:has(#lg-hook) {{ display: none; }}     /* the scroll memory, no box */
[data-testid="stElementContainer"]:has(.jump-anchor) {{ margin-bottom: calc(-1 * var(--space-5)); }}
html {{ scroll-behavior: smooth; }}
[data-testid="stAppScrollToBottomContainer"], [data-testid="stMain"] {{ scroll-behavior: smooth; }}

/* ---------- lesson cards: one per block, its name as the title ---------- */
[class*="st-key-lcard_"] {{
  padding: var(--space-4) var(--space-5) var(--space-5); border-radius: var(--radius-medium);
  background: var(--glass); box-shadow: var(--optic); gap: var(--space-2);
}}
[class*="st-key-lcard_"] .lcard-title {{
  font-family: {SERIF}; font-size: 1.3125rem; font-weight: 400; line-height: 1.25;
  font-variant-numeric: lining-nums; color: var(--label);
}}
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] > :last-child,
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] p:last-child {{ margin-bottom: 0 !important; }}
@media (max-width: 640px) {{ [class*="st-key-lcard_"] {{ padding: var(--space-3) var(--space-4); }} }}

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

/* ---------- small screens: recompose ---------- */
@media (max-width: 640px) {{
  .stMainBlockContainer {{ padding: 88px var(--space-4) var(--space-7); }}
  .stApp h2 {{ font-size: 1.875rem; }}
  .stApp h3 {{ font-size: 1.4375rem; }}
  .stApp h4, [class*="st-key-lcard_"] .lcard-title {{ font-size: 1.1875rem; }}
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
  --lq-glass-top: light-dark(rgba(0, 0, 0, 0.006), rgba(255, 255, 255, 0.022));
  --lq-glass-bottom: light-dark(rgba(0, 0, 0, 0.014), rgba(255, 255, 255, 0.01));
  --lq-edge-hi: light-dark(rgba(0, 0, 0, 0.05), rgba(255, 255, 255, 0.2));
  --lq-edge-lo: light-dark(rgba(0, 0, 0, 0.08), rgba(255, 255, 255, 0.06));
  --lq-edge-near: light-dark(rgba(0, 0, 0, 0.04), rgba(255, 255, 255, 0.05));   /* the rim bends a little light */
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
.lq-pct .unit { font-size: 0.55em; margin-left: 2px; color: var(--label-2); }
.lq-meta { display: flex; justify-content: space-between; gap: 16px; font-size: 0.8125rem; color: var(--label-2); font-variant-numeric: tabular-nums; }
/* a subject's topic, under the subject: the unit she is in now */
.lq-topic { display: flex; align-items: baseline; gap: 8px; min-width: 0; margin-top: -8px; }
.lq-topic-label { flex: none; font-size: 0.6875rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--label-3); }
.lq-topic-name { font-size: 0.875rem; color: var(--label-2); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lq.compact { gap: 10px; }
.lq.compact .lq-topic { margin-top: -6px; }
.lq:not(.compact) .lq-topic-name { white-space: normal; }
.lq.compact .lq-title { font-size: 1.1875rem; }
.lq.compact .lq-pct { font-size: 1.5rem; }

/* the glass: no frame, a clear sliver with a trace of edge */
.lq-glass {
  position: relative; height: var(--height); padding: var(--inset) 0; box-sizing: border-box;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 0 1px 1px -1px var(--lq-edge-hi), inset 0 -1px 1px -1px var(--lq-edge-lo),
              inset 0 2px 3px -2px var(--lq-edge-near), inset 0 -2px 3px -2px var(--lq-edge-near);
}
/* the liquid: full colour to a soft round end, a touch lighter there so no
   colour gathers; while flowing the end draws out a little */
.lq-liquid {
  position: relative; height: 100%;
  width: max(calc(var(--lh) * 2), calc(var(--p) * 1%));
  /* exact radii: a 999px corner would make the browser shrink them all */
  border-radius: var(--lh) calc(var(--lh) * (1.3 + var(--surge) * 1.6)) calc(var(--lh) * (1.1 + var(--surge) * 0.8)) var(--lh) /
                 var(--lh) var(--lh) var(--lh) var(--lh);
  /* one continuous liquid: the faintest drift from depth to light, no
     bands and nothing gathered or brightened at the end */
  background: linear-gradient(90deg, color-mix(in srgb, var(--lq-liquid) 94%, var(--lq-deep)), var(--lq-liquid));
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

/* Today's course card: the day's lessons are the liquid line, as it
   always was: one glass tube across the lessons, the liquid filling each
   completed stretch and ending in a round meniscus. Under each stretch its
   number: completed with a small check, current bold, locked faded, and a
   short mark under the one open. */
[class*="st-key-course_card"] { gap: 12px; }
[class*="st-key-lesson_steps"] { gap: 0 !important; flex-wrap: nowrap !important; }
[class*="st-key-lesson_steps"] > div { flex: 1 1 0 !important; min-width: 0; width: auto !important; }
[class*="st-key-lesson_steps"] [data-testid="stButton"], [class*="st-key-lesson_steps"] button { width: 100%; }
[class*="st-key-lesson_steps"] button {
  position: relative; display: block; height: 44px; min-height: 44px;   /* a clear, invisible tap area */
  padding: 0 !important; margin: 0 !important; cursor: pointer;
  border: none !important; border-radius: 0 !important; background: transparent !important;
  box-shadow: none !important; backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
  transform: none !important; transition: none;
}
/* the glass, continuous across the lessons */
[class*="st-key-lesson_steps"] button::before {
  content: ""; position: absolute; left: 0; right: 0; top: 4px; height: 9px;
  background: linear-gradient(180deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 0 1px 1px -1px var(--lq-edge-hi), inset 0 -1px 1px -1px var(--lq-edge-lo),
              inset 0 2px 3px -2px var(--lq-edge-near), inset 0 -2px 3px -2px var(--lq-edge-near);
}
[class*="st-key-lesson_steps"] > :first-child button::before { border-radius: 999px 0 0 999px; }
[class*="st-key-lesson_steps"] > :last-child button::before { border-radius: 0 999px 999px 0; }
/* the liquid in a completed lesson; the last completed one ends in a round meniscus */
[class*="st-key-step_"] button::after {
  content: ""; position: absolute; left: 0; top: 6.5px; height: 4px; width: 0;
  background: var(--lq-liquid); opacity: 0.92; transition: opacity 0.3s ease-out;
}
[class*="st-key-lesson_steps"] > :first-child button::after { border-top-left-radius: 2px; border-bottom-left-radius: 2px; }
[class*="st-key-step_"][class*="_completed"] button::after { width: 100%; }
[class*="st-key-step_"][class*="_completed"]:not(:has(+ [class*="_completed"])) button::after {
  border-radius: 0 2.6px 2.2px 0 / 0 2px 2px 0;
}
[class*="st-key-lesson_steps"] > [class*="_completed"]:first-child:not(:has(+ [class*="_completed"])) button::after {
  border-radius: 2px 2.6px 2.2px 2px / 2px 2px 2px 2px;
}
@media (hover: hover) {
  [class*="st-key-step_"][class*="_completed"] button:hover::after { opacity: 1; }
}
/* the number, 8px under the glass */
[class*="st-key-lesson_steps"] button > div {
  position: absolute; top: 21px; left: 0; right: 0; display: flex; justify-content: center; overflow: visible;
}
[class*="st-key-lesson_steps"] button [data-testid="stMarkdownContainer"] { line-height: 16px; }
[class*="st-key-lesson_steps"] button p {
  display: block; margin: 0; font-size: 12px; line-height: 16px; font-variant-numeric: tabular-nums;
  color: var(--label-2); transition: color 0.3s ease-out;
}
[class*="st-key-lesson_steps"] button:focus-visible { outline: 1px solid var(--outline); outline-offset: 2px; }
[class*="st-key-step_"][class*="_completed"] button p::after { content: "✓"; font-size: 10px; margin-left: 2px; }
[class*="st-key-step_"][class*="_current"] button p { color: var(--label); font-weight: 600; }
[class*="st-key-step_"][class*="_locked"] button { cursor: default; }
[class*="st-key-step_"][class*="_locked"] button p { opacity: 0.35; }
[class*="st-key-lesson_steps"] button [data-testid="stMarkdownContainer"] { overflow: visible !important; }
[class*="st-key-lesson_steps"] button p { position: relative; }
[class*="st-key-step_"][class*="_viewing"] button p::before {      /* 3px under the number */
  content: ""; position: absolute; top: 19px; left: 50%; width: 12px; height: 1px; margin-left: -6px; background: var(--label);
}
/* motion: arriving on the page, the completed lessons fill one after another
   (about a second in all); a lesson just passed fills on its own */
@keyframes lq-fill { from { width: 0; } to { width: 100%; } }
.st-key-lesson_steps_flow > :nth-child(1)[class*="_completed"] button::after { animation: lq-fill 200ms linear 0ms both; }
.st-key-lesson_steps_flow > :nth-child(2)[class*="_completed"] button::after { animation: lq-fill 200ms linear 200ms both; }
.st-key-lesson_steps_flow > :nth-child(3)[class*="_completed"] button::after { animation: lq-fill 200ms linear 400ms both; }
.st-key-lesson_steps_flow > :nth-child(4)[class*="_completed"] button::after { animation: lq-fill 200ms linear 600ms both; }
.st-key-lesson_steps_flow > :nth-child(5)[class*="_completed"] button::after { animation: lq-fill 200ms linear 800ms both; }
.st-key-lesson_steps_flow > :nth-child(6)[class*="_completed"] button::after { animation: lq-fill 200ms linear 1000ms both; }
.st-key-lesson_steps_flow > :nth-child(7)[class*="_completed"] button::after { animation: lq-fill 200ms linear 1200ms both; }
.st-key-lesson_steps_flow > [class*="_completed"]:not(:has(+ [class*="_completed"])) button::after {
  animation-duration: 420ms; animation-timing-function: cubic-bezier(0.3, 0.6, 0.25, 1);
}
[class*="st-key-step_"][class*="_fresh"] button::after { animation: lq-fill 700ms cubic-bezier(0.3, 0.6, 0.25, 1) both; }
@media (prefers-reduced-motion: reduce) {
  [class*="st-key-step_"] button::after { animation: none !important; }
}

/* all of today's lessons done: the summary card */
.st-key-day_done {
  gap: var(--space-2) !important; padding: var(--space-5); border-radius: var(--radius-large);
  background: var(--glass); box-shadow: var(--optic-strong);
}
.st-key-day_done h3 { padding: 0 0 var(--space-1); line-height: 1.25; }
.st-key-day_done [data-testid="stCaptionContainer"] { margin-bottom: var(--space-2); }
.st-key-day_done [data-testid="stMarkdownContainer"] p { margin: 0; }

/* reviewing an earlier lesson: a quiet bar above its title */
.st-key-review_bar {
  align-items: center !important; justify-content: space-between; gap: var(--space-3) !important; padding: var(--space-2) var(--space-2) var(--space-2) var(--space-4);
  border-radius: var(--radius-medium); background: var(--wash);
}
.st-key-review_bar [data-testid="stMarkdownContainer"] p { font-size: 0.875rem; color: var(--label-2); margin: 0; }
.st-key-review_bar [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
/* Back to the current lesson: a plain outlined pill, 36px to the eye, 44px to the finger */
.st-key-review_bar [data-testid="stButton"] button {
  position: relative; isolation: isolate; height: 44px; min-height: 44px; padding: 0 14px !important;
  white-space: nowrap; border: none !important; background: transparent !important; box-shadow: none !important;
  backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
}
.st-key-review_bar [data-testid="stButton"] button::before {
  content: ""; position: absolute; inset: 4px 0; z-index: -1; box-sizing: border-box; border-radius: 999px;
  background: light-dark(#FFFFFF, #1C1C1E);
  border: 0.5px solid light-dark(rgba(60, 60, 67, 0.18), rgba(235, 235, 245, 0.18));
}
.st-key-review_bar [data-testid="stButton"] button p { font-size: 13px; color: var(--label); }
[class*="st-key-back_to_current_up"] button p::before { content: "↑"; font-size: 12px; margin-right: 6px; }
[class*="st-key-back_to_current_down"] button p::before { content: "↓"; font-size: 12px; margin-right: 6px; }
.st-key-review_bar > div:first-child { flex: 1 1 auto; min-width: 0; }
.st-key-review_bar > div:last-child { flex: 0 0 auto; width: auto !important; }

/* ---------- today in the sidebar: an upright glass tube ---------- */
.lqv { --p: var(--to); display: flex; gap: 16px; align-items: stretch; margin: 4px 0 8px; }
.lqv-tube {
  position: relative; flex: none; width: 52px; height: 148px; box-sizing: border-box;
  border-radius: 16px;
  background: linear-gradient(90deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 1px 0 1px -1px var(--lq-edge-hi), inset -1px 0 1px -1px var(--lq-edge-lo),
              inset 0 1px 1px -1px var(--lq-edge-hi), inset 0 0 6px -2px var(--lq-edge-near);
}
/* the liquid rises from the bottom; its surface is a soft meniscus that
   tilts a little while it moves and levels out as it settles */
.lqv-liquid {
  position: absolute; left: 5px; right: 5px; bottom: 5px;
  height: max(10px, calc((100% - 10px) * var(--p) / 100));
  border-radius: calc(7px + var(--surge) * 5px) calc(7px - var(--surge) * 3px) 11px 11px /
                 6px 6px 11px 11px;
  background: linear-gradient(0deg, color-mix(in srgb, var(--lq-liquid) 94%, var(--lq-deep)), var(--lq-liquid));
  opacity: 0.92;
  box-shadow: 0 0 6px color-mix(in srgb, var(--lq-glow) 7%, transparent);
}
.lqv-liquid::after {              /* the one light response, barely there */
  content: ""; position: absolute; top: 4px; bottom: 4px; left: 3px; width: 35%; border-radius: inherit;
  background: linear-gradient(0deg, transparent 5%,
    color-mix(in srgb, var(--lq-hi) calc(16% + var(--surge) * 10%), transparent) 60%, transparent 95%);
}
.lqv.empty .lqv-liquid { opacity: 0.45; }   /* a drop at the bottom, so the tube is never empty-looking */
.lqv.flowing .lqv-liquid {
  animation: lq-front 950ms cubic-bezier(0.3, 0.6, 0.25, 1) both,
             lq-surge 1100ms cubic-bezier(0.4, 0, 0.3, 1) both;
}
.lqv-info { display: flex; flex-direction: column; justify-content: space-between; min-width: 0; padding: 2px 0; }
.lqv-date {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 400; font-size: 1.1875rem;
  line-height: 1.2; color: var(--label); font-variant-numeric: lining-nums;
}
.lqv-subject { font-size: 0.8125rem; color: var(--label-2); margin-top: 4px; }
.lqv-pct {
  font-family: "Newsreader", serif; font-weight: 300; font-size: 2.5rem; line-height: 1;
  font-variant-numeric: lining-nums tabular-nums; color: var(--label); margin-top: auto;
}
.lqv-pct .unit { font-size: 0.5em; margin-left: 2px; color: var(--label-2); }
.lqv-count { font-size: 0.75rem; color: var(--label-3); margin-top: 6px; }
@media (prefers-reduced-motion: reduce) { .lqv.flowing .lqv-liquid { animation: none; } }

/* ---------- rolling numbers (coach/rolling.py) ---------- */
/* each changed digit is a window onto a vertical strip (blank, 0-9, 0-9)
   drawn by ::before, sliding from the old digit to the new one; the digit
   itself (transparent) is the text and gives the window its width and
   baseline, so nothing around it moves and copying gives the number */
.rd, .rd-d, .rd-still, .rd-sep { font-variant-numeric: lining-nums tabular-nums; }
.rd-d {
  position: relative; display: inline-block; line-height: 1.1; clip-path: inset(0 -0.2em);
  -webkit-text-fill-color: transparent;       /* the digit is there for width, baseline and copying */
}
.rd-d::before {
  content: "\\00a0\\A 0\\A 1\\A 2\\A 3\\A 4\\A 5\\A 6\\A 7\\A 8\\A 9\\A 0\\A 1\\A 2\\A 3\\A 4\\A 5\\A 6\\A 7\\A 8\\A 9";
  position: absolute; left: 0; right: 0; top: 0; text-align: center; white-space: pre; line-height: 1.1;
  -webkit-text-fill-color: currentColor; pointer-events: none;
  transform: translateY(calc(var(--b) * -1.1em));
}
.rd.rolling .rd-d {
  -webkit-mask-image: linear-gradient(180deg, transparent, #000 9%, #000 91%, transparent);
          mask-image: linear-gradient(180deg, transparent, #000 9%, #000 91%, transparent);
}
/* all reels start together; each has its own duration (--t, by distance),
   so they come to rest one after another; smooth ease-out, no overshoot */
.rd.rolling .rd-d::before { animation: rd-roll var(--t, 1100ms) cubic-bezier(0.3, 0.6, 0.3, 1) both; }
@keyframes rd-roll {
  from { transform: translateY(calc(var(--a) * -1.1em)); }
  to   { transform: translateY(calc(var(--b) * -1.1em)); }
}
@media (prefers-reduced-motion: reduce) { .rd.rolling .rd-d::before { animation: none; } }

/* ---------- the figures at the top of Progress: one row, as many as fit ---------- */
.figures { display: grid; grid-template-columns: repeat(auto-fit, minmax(108px, 1fr)); gap: 24px 16px; }
.figure-label { font-size: 0.75rem; color: var(--label-3); margin-bottom: 4px; }
.figure-value {
  font-family: "Newsreader", "Noto Serif TC", serif; font-size: 1.875rem; font-weight: 300; line-height: 1.2;
  color: var(--label); font-variant-numeric: lining-nums tabular-nums;
}

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

PROGRESS = """
<style>
/* ---------- Progress: two sides ----------
   The month on the left; on the right one view at a time (the day picked,
   every session, the subjects), switched at its top, so neither side is
   ever crowded. Wide: side by side, each scrolling on its own, the switch
   staying at the top of its side. Narrower than about 860px of page width
   (container queries: the sidebar is taken in), the view comes under the
   month and the page scrolls as usual. */
.stMainBlockContainer:has(#progress-page) { max-width: 1320px; }
[data-testid="stElementContainer"]:has(#progress-page) { display: none; }
.st-key-prog_main { container-type: inline-size; margin-top: var(--space-2); }
.st-key-prog_main [data-testid="stHorizontalBlock"]:not([class*="st-key-"]) { gap: clamp(32px, 5cqw, 72px) !important; align-items: flex-start; }
.st-key-prog_main [data-testid="stHorizontalBlock"]:not([class*="st-key-"]) > [data-testid="stColumn"] { min-width: 0; }
@container (min-width: 860px) {
  .st-key-prog_main [data-testid="stHorizontalBlock"]:not([class*="st-key-"]) > [data-testid="stColumn"] {
    position: sticky; top: 72px; max-height: calc(100vh - 92px); max-height: calc(100dvh - 92px); overflow-y: auto; overscroll-behavior: contain;
    padding: 6px 8px 40px 6px; margin: -6px -8px 0 -6px;
    scrollbar-width: thin; scrollbar-color: var(--hair) transparent;
    mask-image: linear-gradient(to bottom, #000 calc(100% - 32px), transparent);
  }
}
@container (max-width: 859.98px) {
  .st-key-prog_main [data-testid="stHorizontalBlock"]:not([class*="st-key-"]) { flex-direction: column; gap: var(--space-6) !important; }
  .st-key-prog_main [data-testid="stHorizontalBlock"]:not([class*="st-key-"]) > [data-testid="stColumn"] { width: 100% !important; flex: 1 1 auto !important; }
}

/* the switch: three equal segments on a quiet track, the chosen one glass;
   it stays at the top of its side while the view scrolls under it */
.st-key-prog_view {
  position: sticky; top: -6px; z-index: 5; padding: 6px 0 var(--space-3);
  background: linear-gradient(var(--env) 80%, transparent);
}
.st-key-prog_view [data-testid="stButtonGroup"], .st-key-prog_view [data-testid="stButtonGroup"] > div { width: 100%; }
.st-key-prog_view [data-testid="stButtonGroup"] > div {
  display: flex; gap: 2px; padding: 3px; border-radius: 999px; background: var(--wash); border: none;
}
.st-key-prog_view [data-testid="stButtonGroup"] button {
  flex: 1 1 0; min-height: 36px; margin: 0 !important; border: none !important; border-radius: 999px !important;
  background: transparent !important; box-shadow: none !important; color: var(--label-2);
  transition: background-color 220ms var(--ease), color 220ms var(--ease), box-shadow 220ms var(--ease);
}
.st-key-prog_view [data-testid="stButtonGroup"] button p { font-size: 0.875rem; }
.st-key-prog_view [data-testid="stButtonGroup"] button[aria-checked="true"] {
  background: var(--env) !important; color: var(--label); box-shadow: var(--optic-strong) !important;
}
.st-key-prog_view [data-testid="stButtonGroup"] button[aria-checked="true"] p { font-weight: 600; }
@media (hover: hover) { .st-key-prog_view [data-testid="stButtonGroup"] button:hover:not([aria-checked="true"]) { color: var(--label); } }
/* a view eases in when switched to */
[class*="st-key-view_"] { gap: var(--space-4) !important; animation: rise-in 240ms var(--ease) backwards; }
/* the subjects: as many columns as fit, never cramped */
.st-key-subj_list {
  display: grid !important; grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr));
  gap: var(--space-5) var(--space-6) !important;
}
.st-key-subj_list > div { width: 100% !important; min-width: 0; }

/* ---------- the month ---------- */
.st-key-cal_head { flex-direction: row !important; justify-content: space-between; flex-wrap: nowrap !important; }
.st-key-cal_head > div:first-child { flex: 1 1 auto !important; min-width: 0; }
.st-key-cal_head h4 { padding: 0 !important; margin: 0; }
.st-key-cal_nav { flex: 0 0 auto !important; width: auto !important; gap: 4px !important; flex-direction: row !important; }
.st-key-cal_nav > div { flex: 0 0 auto !important; width: auto !important; }
.st-key-cal_nav button { min-height: 36px; height: 36px; padding: 0 14px !important; }
.st-key-cal_nav button p { font-size: 0.9375rem; }
@container (max-width: 520px) { .st-key-cal_nav button { padding: 0 10px !important; } }
.cal-summary { font-size: 0.8125rem; color: var(--label-3); }

.cal-week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; margin-bottom: -8px; }
.cal-week span { display: grid; justify-items: center; gap: 1px; min-width: 0; }
.cal-week b { font-size: 0.75rem; font-weight: 500; color: var(--label-2); }
.cal-week i { font-style: normal; font-size: 0.6875rem; color: var(--label-3); max-width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* the days: each a button; the line under the number grows with the
   lessons passed that day, dark once the day is completed */
[class*="st-key-calgrid_"] { gap: 4px !important; }
[class*="st-key-calw_"] { gap: 4px !important; flex-direction: row !important; flex-wrap: nowrap !important; }
[class*="st-key-calw_"] > div { flex: 1 1 0 !important; min-width: 0; width: auto !important; }
[class*="st-key-calw_"] [data-testid="stButton"], [class*="st-key-calw_"] button { width: 100%; }
[class*="st-key-cal_20"] .stButton button {
  position: relative; height: 56px; min-height: 44px; padding: 0 0 12px !important;
  border: none; border-radius: 14px; background: transparent; box-shadow: none;
  backdrop-filter: none; -webkit-backdrop-filter: none; color: var(--label-3);
  transition: background-color 200ms var(--ease), box-shadow 200ms var(--ease), color 200ms var(--ease);
}
[class*="st-key-cal_20"] .stButton button > div, [class*="st-key-cal_20"] .stButton button [data-testid="stMarkdownContainer"] { overflow: visible !important; min-width: 0; }
[class*="st-key-cal_20"] .stButton button p { font-size: 0.9375rem; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: visible; }
[class*="st-key-cal_20"] .stButton button::before, [class*="st-key-cal_20"] .stButton button::after {
  content: ""; position: absolute; bottom: 12px; left: calc(50% - 12px); height: 3px; border-radius: 1.5px;
}
[class*="st-key-cal_20"][class*="_done_"] .stButton button::before,
[class*="st-key-cal_20"][class*="_partial_"] .stButton button::before { width: 24px; background: var(--hair); }
[class*="st-key-cal_20"] .stButton button::after { width: 0; background: var(--label-2); transition: width 300ms var(--ease); }
[class*="st-key-cal_20"][class*="_a1"] .stButton button::after { width: 4.8px; }
[class*="st-key-cal_20"][class*="_a2"] .stButton button::after { width: 9.6px; }
[class*="st-key-cal_20"][class*="_a3"] .stButton button::after { width: 14.4px; }
[class*="st-key-cal_20"][class*="_a4"] .stButton button::after { width: 19.2px; }
[class*="st-key-cal_20"][class*="_a5"] .stButton button::after { width: 24px; }
[class*="st-key-cal_20"][class*="_done_"] .stButton button { color: var(--label); }
[class*="st-key-cal_20"][class*="_done_"] .stButton button::after { background: var(--label); }
[class*="st-key-cal_20"][class*="_partial_"] .stButton button { color: var(--label-2); }
[class*="st-key-cal_20"][class*="_out"] .stButton button { opacity: 0.4; }
[class*="st-key-cal_20"][class*="_future_"] .stButton button { opacity: 0.35; cursor: default; background: transparent; }
[class*="st-key-cal_20"][class*="_today"] .stButton button p { font-weight: 700; color: var(--strong); }
@media (hover: hover) { [class*="st-key-cal_20"] .stButton button:not(:disabled):hover { background: var(--glass); border: none; box-shadow: none; } }
[class*="st-key-cal_20"][class*="_sel"] .stButton button {
  background: var(--glass-strong); box-shadow: var(--optic); animation: day-pick 220ms var(--ease) backwards;
}
[class*="st-key-cal_20"] .stButton button:focus-visible { outline: 1px solid var(--outline); outline-offset: 1px; }
@container (max-width: 520px) { [class*="st-key-cal_20"] .stButton button { height: 48px; } }

.cal-key { display: flex; flex-wrap: wrap; gap: 6px 20px; font-size: 0.75rem; color: var(--label-3); }
.cal-key span { display: inline-flex; align-items: center; gap: 8px; }
.cal-key i { display: inline-block; width: 16px; height: 3px; border-radius: 1.5px; }
.cal-key .k-done { background: var(--label); }
.cal-key .k-part { background: linear-gradient(90deg, var(--label-2) 50%, var(--hair) 50%); }

/* ---------- the day picked ---------- */
[class*="st-key-prog_day_"] {
  gap: var(--space-2) !important; padding: var(--space-5);
  border-radius: var(--radius-medium); background: var(--glass); box-shadow: var(--optic);
  animation: rise-in 260ms var(--ease) backwards; scroll-margin: 88px 0 16px;
}
[class*="st-key-prog_day_"] h4 { padding: 0 0 2px !important; }
[class*="st-key-prog_day_"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
.day-status { font-size: 0.8125rem; color: var(--label-2); }

/* a day's lessons: one line each */
.lesson-rows { list-style: none; margin: 2px 0 0 !important; padding: 0 !important; display: grid; gap: 0; }
.lesson-rows li {
  display: grid; grid-template-columns: 8px 2.5em minmax(0, 1fr) auto; align-items: center; column-gap: 8px;
  padding: 5px 0; font-size: 0.875rem; line-height: 1.35; color: var(--label); border-bottom: 1px solid var(--hair);
}
.lesson-rows li:last-child { border-bottom: none; }
.lesson-rows li::before { content: ""; width: 6px; height: 6px; border-radius: 50%; box-sizing: border-box; background: var(--label); }
.lesson-rows li.open { color: var(--label-2); }
.lesson-rows li.open::before { background: transparent; border: 1px solid var(--label-3); }
.lesson-rows .n { color: var(--label-3); font-variant-numeric: tabular-nums; }
.lesson-rows .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lesson-rows .q { font-size: 0.8125rem; color: var(--label-2); font-variant-numeric: tabular-nums; }

/* one lesson to read, a section at a time */
[class*="st-key-reader_"] {
  gap: var(--space-2) !important; padding: var(--space-4) var(--space-4) var(--space-3);
  border-radius: 18px; background: var(--glass); box-shadow: var(--optic);
  animation: rise-in 240ms var(--ease) backwards;
}
/* the section grows with its text: the page is the one thing that scrolls */
[class*="st-key-reader_"] [role="tabpanel"] { animation: fade-in 200ms var(--ease) backwards; }
[class*="st-key-reader_"] [role="tablist"] { gap: 2px; }
[class*="st-key-reader_"] [role="tab"] p { font-size: 0.8125rem; white-space: nowrap; }

/* ---------- every session ---------- */
.st-key-sessions_head { flex-direction: row !important; flex-wrap: wrap !important; justify-content: space-between;
  align-items: center !important; gap: var(--space-3) !important; margin-top: var(--space-6); }
.st-key-view_sessions .st-key-sessions_head { margin-top: 0; }
.view-count { font-size: 0.8125rem; color: var(--label-2); font-variant-numeric: tabular-nums; }
.st-key-sessions_head h4 { padding: 0 !important; margin: 0; }
.st-key-sessions_head [data-testid="stSelectbox"] { width: min(240px, 100%); }
.st-key-sessions_head > div:last-child { flex: 0 1 240px !important; width: auto !important; }
[class*="st-key-sessions_list_"] { gap: 0 !important; animation: fade-in 240ms var(--ease) backwards; }
[class*="st-key-sessions_list_"] > div { width: 100% !important; min-width: 0; }
[class*="st-key-oncal_"] button { min-height: 32px; padding: 0 !important; }
[class*="st-key-oncal_"] button p { font-size: 0.8125rem; color: var(--label-2); }

/* ---------- motion ---------- */
/* expanders open and close smoothly (where the browser can size to auto) */
:root { interpolate-size: allow-keywords; }
[data-testid="stExpander"] details::details-content {
  block-size: 0; overflow-y: clip;
  transition: block-size 280ms var(--ease), content-visibility 280ms allow-discrete;
}
[data-testid="stExpander"] details[open]::details-content { block-size: auto; }
[class*="st-key-calgrid_"][class*="_next"] { animation: from-right 320ms var(--ease) backwards; }
[class*="st-key-calgrid_"][class*="_prev"] { animation: from-left 320ms var(--ease) backwards; }
[class*="st-key-calgrid_"][class*="_none"] { animation: fade-in 220ms var(--ease) backwards; }
@keyframes from-right { from { opacity: 0; transform: translateX(16px); } }
@keyframes from-left { from { opacity: 0; transform: translateX(-16px); } }
@keyframes rise-in { from { opacity: 0; transform: translateY(6px); } }
@keyframes fade-in { from { opacity: 0; } }
@keyframes day-pick { from { background-color: transparent; box-shadow: none; } }
@media (prefers-reduced-motion: reduce) {
  [class*="st-key-calgrid_"], [class*="st-key-prog_day_"], [class*="st-key-reader_"], [class*="st-key-sessions_list_"],
  [class*="st-key-view_"],
  [class*="st-key-reader_"] [role="tabpanel"], [class*="st-key-cal_20"] .stButton button { animation: none !important; }
  [data-testid="stExpander"] details::details-content { transition: none; }
}
</style>
"""


# Touch screens (iPhone, iPad, touch tablets). What looks compact stays
# compact; only the area a finger can hit grows, invisibly, to about 44px.
# Kept apart from the rest so a mouse sees exactly what it did before.
TOUCH = """
<style>
/* no grey flash on tap (each control shows its own pressed state instead),
   and no double-tap-to-zoom wait on anything tappable */
.stApp, [data-trigger] { -webkit-tap-highlight-color: transparent; }
button, a, summary, label, input, textarea, [role="tab"], [role="option"], [data-baseweb="select"] { touch-action: manipulation; }
/* scrolling a focused field into view (or moving to a lesson) stops clear
   of the header above and the chat box below */
[data-testid="stMain"] { scroll-padding: 72px 0 112px; }

/* pressed: a quiet answer under the finger (and the mouse) */
[data-testid="stSidebarNav"] a:active { background: var(--wash) !important; }
[data-testid="stExpander"] summary:active { color: var(--strong); }
.st-key-prog_view [data-testid="stButtonGroup"] button:not([aria-checked="true"]):active { background: var(--wash) !important; }
[class*="st-key-cal_20"] .stButton button:not(:disabled):active { background: var(--wash); }
[data-testid="stButtonGroup"] button:active, [role="tab"]:active { opacity: 0.6; }
[class*="st-key-oncal_"] button:active p, .st-key-cal_nav button:active p { color: var(--strong); }

/* Streamlit shows the sidebar's close button only while the sidebar is
   hovered, which never happens on a touch screen (an iPad could open the
   sidebar and not close it again) */
@media (hover: none) { [data-testid="stSidebarCollapseButton"] { visibility: visible !important; } }
@media (pointer: coarse) {
  /* 16px text in every field: below that Safari zooms the page in on focus */
  .stApp input, .stApp textarea, [data-testid="stChatInput"] textarea, [data-trigger] input { font-size: 16px !important; }

  /* the finger's reach, larger than what shows: an invisible margin around
     the small controls (the calendar days and the lesson line are already
     44px and draw their own marks with ::before and ::after, so they are
     left alone) */
  .st-key-prog_view [data-testid="stButtonGroup"] button,
  [data-testid="stButtonGroup"] button,
  .st-key-cal_nav button, [class*="st-key-oncal_"] button,
  [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button,
  [data-testid="stMainMenu"] button { position: relative; }
  .st-key-prog_view [data-testid="stButtonGroup"] button::after,
  [data-testid="stButtonGroup"] button::after,
  .st-key-cal_nav button::after, [class*="st-key-oncal_"] button::after {
    content: ""; position: absolute; inset: -8px -3px;
  }
  [data-testid="stButtonGroup"] button { overflow: visible; }   /* it clipped the reach */
  [class*="st-key-read_"] [data-testid="stButtonGroup"] > div { row-gap: 12px; }   /* each row keeps its own reach */
  /* the switch: a little taller to the eye, and its reach fills the track */
  .st-key-prog_view [data-testid="stButtonGroup"] > div { overflow: visible; }
  .st-key-prog_view [data-testid="stButtonGroup"] button { min-height: 40px; }
  .st-key-prog_view [data-testid="stButtonGroup"] button::after { inset: -3px -1px; }
  .st-key-cal_nav button { min-width: 44px; }
  [data-testid="stExpandSidebarButton"]::after, [data-testid="stSidebarCollapseButton"] button::after,
  [data-testid="stMainMenu"] button::after { content: ""; position: absolute; inset: -9px; }
  [data-testid="stSidebarNav"] a { min-height: 44px; }
  [role="tab"] { min-height: 44px; min-width: 44px; justify-content: center; }
  [role="option"] { min-height: 44px; }

  /* one scroll, the page's: on a touch screen the two sides of Progress and
     a lesson being read don't scroll on their own inside it (a swipe would
     move the inner box one moment and the page the next) */
  .st-key-prog_main [data-testid="stHorizontalBlock"]:not([class*="st-key-"]) > [data-testid="stColumn"] {
    position: static !important; max-height: none !important; overflow: visible !important;
    padding: 0 !important; margin: 0 !important; mask-image: none !important;
  }
  /* the sections' names: swiped sideways; the arrow buttons (made for a
     mouse) sat over the last name in view and took its taps */
  [data-testid="stTabs"] [role="tablist"] { overflow-x: auto; overscroll-behavior-x: contain; scrollbar-width: none; }
  [data-testid="stTabs"] button[aria-label^="Scroll tabs"] { display: none; }
}
/* the switch stays in sight while the view scrolls: under the header when
   the page itself scrolls (the sides stacked, or on a touch screen), where
   the header would otherwise sit over it and take its taps */
@container (max-width: 859.98px) { .st-key-prog_view { top: 52px; } }
@media (pointer: coarse) { .st-key-prog_view { top: 52px; } }
</style>
"""


def stylesheet() -> str:
    return CSS.replace("</style>", LIQUID.replace("<style>", "").replace("</style>", (PROGRESS + TOUCH).replace("<style>", "").replace("</style>", "", 1)))


def inject():
    st.html(stylesheet())
    st.html(glass.script(), unsafe_allow_javascript=True)      # the refraction filter the glass uses
