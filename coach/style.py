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

from coach import glass, motion

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
  --label-3: light-dark(#767676, #7C7C7C);   /* 4.5:1 or more on white and on black */ --strong: light-dark(#000000, #FFFFFF);
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

  /* motion: every change has a beginning, a middle and an end. Small
     answers (a press, a hover, a focus ring) take about a quarter second;
     a change of state about half; things that move the layout a little
     longer. One soft deceleration for things arriving, a symmetric curve
     for things that grow and shrink in place; nothing overshoots. */
  --ease: cubic-bezier(0.22, 0.61, 0.36, 1);
  --ease-layout: cubic-bezier(0.45, 0, 0.25, 1);
  --t-press: 120ms; --t-micro: 240ms; --t-state: 420ms; --t-space: 480ms; --t-layout: 560ms;
  --ease-nav: cubic-bezier(0.32, 0.72, 0, 1);   /* a surface travelling between places: sets off promptly, arrives slowly */
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
.stMainBlockContainer {{ max-width: 720px; padding: var(--space-8) var(--space-5) var(--space-7); }}
/* a page arrives as its content, each block rising a little as it comes
   in; the navigation at the top is not part of it and stays still */
.stMainBlockContainer > [data-testid="stVerticalBlock"] > :not(:has(> .st-key-topnav)) {{
  animation: arrive var(--t-space) var(--ease) backwards;   /* not "both": a kept transform would trap the floating button */
}}
@keyframes arrive {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: none; }}
}}
@media (min-width: 768px) {{ .stMainBlockContainer {{ padding-top: 96px; }} }}
/* the lesson page (Today) is wider, for the lesson cards, tables and quiz */
.stMainBlockContainer:has([class*="st-key-course_card"]) {{ max-width: 900px; }}
[data-testid="stVerticalBlock"] {{ gap: var(--space-5); }}

/* ---------- type ---------- */
.stApp h1, .stApp h2, .stApp h3 {{ color: var(--label); font-family: {SERIF}; font-weight: 300; font-variant-numeric: lining-nums; }}
.stApp h2 {{ font-size: 2.25rem; line-height: 1.12; letter-spacing: 0; padding: 0 0 var(--space-3); }}
.stApp h3 {{ font-size: 1.625rem; line-height: 1.22; letter-spacing: 0; padding: 0 0 var(--space-2); }}
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
  transform: scale(0.97); transition-duration: var(--t-press);
}}
.stButton button:disabled, .stFormSubmitButton button:disabled {{
  background: var(--glass-faint) !important; border-color: transparent !important; box-shadow: none !important;
  color: var(--label-3) !important; opacity: 0.55; cursor: default;
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
  animation: fade 280ms var(--ease) both;   /* opacity only: the popover is positioned by transform */
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
  transition: background-color var(--t-state) var(--ease), border-color var(--t-state) var(--ease), transform var(--t-state) var(--ease);
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
  /* exactly the header's glass: the same fill and the same filter (the
     refraction where the browser can, the light frost elsewhere), focused
     or not. Only a hairline outline, so she can see where the box is. */
  background: var(--glass) !important;
  -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-optics);
  box-shadow: inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.1), rgba(255, 255, 255, 0.1));
  transition: box-shadow 360ms var(--ease), background-color 360ms var(--ease);
}}
[data-testid="stChatInput"]:focus-within {{
  box-shadow: inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.28), rgba(255, 255, 255, 0.28));
}}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea {{ background: transparent !important; border: none !important; }}
[data-testid="stChatInput"] textarea {{ color: var(--label) !important; caret-color: var(--label); }}
[data-testid="stChatInput"] textarea::placeholder {{ color: var(--label-2); opacity: 1; }}
[data-testid="stChatInputSubmitButton"] {{
  border-radius: 50% !important; background: transparent !important; color: var(--label-3) !important;
  transition: background-color 320ms var(--ease), color 320ms var(--ease), transform var(--t-micro) var(--ease);
}}
[data-testid="stChatInputSubmitButton"]:not(:disabled) {{ background: var(--label) !important; color: var(--env) !important; }}
[data-testid="stChatInputSubmitButton"]:not(:disabled):active {{ transform: scale(0.92); transition-duration: var(--t-press); }}
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
[data-testid="stElementContainer"]:has(#lg-hook), [data-testid="stElementContainer"]:has(#cx-hook) {{ display: none; }}     /* the scroll memory, no box */
[data-testid="stElementContainer"]:has(.jump-anchor) {{ margin-bottom: calc(-1 * var(--space-5)); }}
html {{ scroll-behavior: smooth; }}
[data-testid="stAppScrollToBottomContainer"], [data-testid="stMain"] {{ scroll-behavior: smooth; }}

/* ---------- lesson cards: one per block, its name as the title ---------- */
/* one lesson reads as one article: each block is a section under a hairline,
   its text kept to a comfortable measure, not a box of its own */
[class*="st-key-lcard_"] {{
  padding: var(--space-5) 0 0; border-radius: 0; background: none; box-shadow: none;
  border-top: 0.5px solid var(--field-edge); gap: var(--space-3);
}}
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] {{ max-width: 42rem; }}
[class*="st-key-lcard_"] .lcard-title {{
  font-family: {SERIF}; font-size: 1.3125rem; font-weight: 400; line-height: 1.25;
  font-variant-numeric: lining-nums; color: var(--label);
}}
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] > :last-child,
[class*="st-key-lcard_"] [data-testid="stMarkdownContainer"] p:last-child {{ margin-bottom: 0 !important; }}
@media (max-width: 640px) {{ [class*="st-key-lcard_"] {{ padding: var(--space-4) 0 0; }} }}

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
.stApp [data-testid="stMarkdownContainer"]:has(> table) {{ overflow-x: auto; overscroll-behavior-x: contain; }}   /* a wide table scrolls, not the page */

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
  animation: lq-front 1150ms cubic-bezier(0.3, 0.6, 0.3, 1) both,
             lq-surge 1300ms cubic-bezier(0.4, 0, 0.3, 1) both;
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
  background: var(--lq-liquid); opacity: 0.92; transition: opacity var(--t-micro) var(--ease);
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
  color: var(--label-2); transition: color var(--t-state) var(--ease);
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
[class*="st-key-step_"][class*="_fresh"] button::after { animation: lq-fill 900ms cubic-bezier(0.3, 0.6, 0.3, 1) both; }
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
.lqv { --p: var(--to); display: flex; gap: 18px; align-items: stretch; margin: 0; }
.lqv-tube {
  position: relative; flex: none; width: 44px; height: 140px; box-sizing: border-box;
  border-radius: 15px;
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
  animation: lq-front 1150ms cubic-bezier(0.3, 0.6, 0.3, 1) both,
             lq-surge 1300ms cubic-bezier(0.4, 0, 0.3, 1) both;
}
/* the sidebar: the day, then today's subject beside its tube, then the
   book; one small label per step, one serif line under it, hairline apart */
.sb-label { font-size: 0.6875rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--label-3); }
/* the sidebar's date sits on the same line as the page's title (on Today,
   the same date): the two columns start together */
.sb-label:first-child { margin-top: 13px; }
.lqv-date {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; font-size: 1.375rem;
  line-height: 1.2; color: var(--label); font-variant-numeric: lining-nums; margin: 6px 0 26px;
}
.lqv-info { display: flex; flex-direction: column; min-width: 0; padding: 1px 0 2px; }
.lqv-subject {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 400; font-size: 1.0625rem; line-height: 1.25; color: var(--label);
}
.lqv-topic { font-size: 0.8125rem; line-height: 1.4; color: var(--label-2); margin-top: 4px; }
.lqv-pct {
  font-family: "Newsreader", serif; font-weight: 300; font-size: 2.25rem; line-height: 1;
  font-variant-numeric: lining-nums tabular-nums; color: var(--label); margin-top: auto; padding-top: 12px;
}
.lqv-pct .unit { font-size: 0.5em; margin-left: 2px; color: var(--label-2); }
.lqv-count { font-size: 0.75rem; color: var(--label-3); margin-top: 6px; font-variant-numeric: tabular-nums; }
.sb-rule { border: none; height: 0.5px; background: var(--field-edge); margin: 32px 0 22px; }
.sb-book { font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 400; font-size: 1.0625rem; line-height: 1.25; color: var(--label); margin-top: 8px; }
.sb-author { font-size: 0.8125rem; color: var(--label-2); margin-top: 3px; }
.sb-quiet { font-size: 0.8125rem; color: var(--label-3); margin-top: 8px; }
/* the book's days: the same liquid, as a thin line */
.sb-line {
  position: relative; height: 5px; margin: 14px 0 8px; border-radius: 999px; padding: 0.5px 0; box-sizing: border-box;
  background: linear-gradient(180deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 0 1px 1px -1px var(--lq-edge-hi), inset 0 -1px 1px -1px var(--lq-edge-lo), inset 0 0 0 0.5px var(--lq-edge-near);
}
.sb-line i { display: block; height: 100%; min-width: 4px; border-radius: 999px; background: var(--lq-liquid); opacity: 0.92;
  transition: width var(--t-layout, 560ms) var(--ease, ease); }
.sb-meta { font-size: 0.75rem; color: var(--label-3); font-variant-numeric: tabular-nums; }
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
  transition: background-color var(--t-state) var(--ease), color var(--t-state) var(--ease), box-shadow var(--t-state) var(--ease);
}
.st-key-prog_view [data-testid="stButtonGroup"] button p { font-size: 0.875rem; }
.st-key-prog_view [data-testid="stButtonGroup"] button[aria-checked="true"] {
  background: var(--env) !important; color: var(--label); box-shadow: var(--optic-strong) !important;
}
.st-key-prog_view [data-testid="stButtonGroup"] button[aria-checked="true"] p { font-weight: 600; }
@media (hover: hover) { .st-key-prog_view [data-testid="stButtonGroup"] button:hover:not([aria-checked="true"]) { color: var(--label); } }
/* a view eases in when switched to */
[class*="st-key-view_"] { gap: var(--space-4) !important; animation: rise-in var(--t-space) var(--ease) backwards; }
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
  transition: background-color 320ms var(--ease), box-shadow 320ms var(--ease), color 320ms var(--ease);
}
[class*="st-key-cal_20"] .stButton button > div, [class*="st-key-cal_20"] .stButton button [data-testid="stMarkdownContainer"] { overflow: visible !important; min-width: 0; }
[class*="st-key-cal_20"] .stButton button p { font-size: 0.9375rem; font-variant-numeric: tabular-nums; white-space: nowrap; overflow: visible; }
[class*="st-key-cal_20"] .stButton button::before, [class*="st-key-cal_20"] .stButton button::after {
  content: ""; position: absolute; bottom: 12px; left: calc(50% - 12px); height: 3px; border-radius: 1.5px;
}
[class*="st-key-cal_20"][class*="_done_"] .stButton button::before,
[class*="st-key-cal_20"][class*="_partial_"] .stButton button::before { width: 24px; background: var(--hair); }
[class*="st-key-cal_20"] .stButton button::after { width: 0; background: var(--label-2); transition: width var(--t-space) var(--ease); }
[class*="st-key-cal_20"][class*="_a1"] .stButton button::after { width: 4.8px; }
[class*="st-key-cal_20"][class*="_a2"] .stButton button::after { width: 9.6px; }
[class*="st-key-cal_20"][class*="_a3"] .stButton button::after { width: 14.4px; }
[class*="st-key-cal_20"][class*="_a4"] .stButton button::after { width: 19.2px; }
[class*="st-key-cal_20"][class*="_a5"] .stButton button::after { width: 24px; }
[class*="st-key-cal_20"][class*="_done_"] .stButton button { color: var(--label); }
[class*="st-key-cal_20"][class*="_done_"] .stButton button::after { background: var(--label); }
[class*="st-key-cal_20"][class*="_partial_"] .stButton button { color: var(--label-2); }
[class*="st-key-cal_20"][class*="_out"] .stButton button { opacity: 0.4; }
/* days to come: faint, but open to a tap (the day says what's planned) */
[class*="st-key-cal_20"][class*="_future_"] .stButton button { opacity: 0.45; }
[class*="st-key-cal_20"][class*="_future_"][class*="_sel"] .stButton button { opacity: 0.8; }
[class*="st-key-cal_20"][class*="_today"] .stButton button p { font-weight: 700; color: var(--strong); }
@media (hover: hover) { [class*="st-key-cal_20"]:not([class*="_sel"]) .stButton button:not(:disabled):not([data-picking]):hover { background: var(--glass); border: none; box-shadow: none; } }
/* the day picked: glass with a fine ink ring, so it reads at a glance. A
   tap shows it at once (data-picking, set by coach/glass.py) while the page
   redraws, and the old pick lets go */
[class*="st-key-cal_20"][class*="_sel"] .stButton button, [class*="st-key-cal_20"] .stButton button[data-picking] {
  background: var(--glass-strong); color: var(--label);
  box-shadow: var(--optic), inset 0 0 0 1px light-dark(rgba(0, 0, 0, 0.3), rgba(255, 255, 255, 0.34));
}
[class*="st-key-cal_20"][class*="_sel"] .stButton button { animation: day-pick var(--t-state) var(--ease) backwards; }
[class*="st-key-calgrid_"]:has(button[data-picking]) [class*="_sel"] .stButton button:not([data-picking]) {
  background: transparent; box-shadow: none;
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
  animation: rise-in var(--t-space) var(--ease) backwards; scroll-margin: 88px 0 16px;
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
  animation: fade-in 420ms var(--ease) 80ms backwards;
}
/* the section grows with its text: the page is the one thing that scrolls */
/* its space opens in place, moving what is below down with it (the
   reader itself is sized by its row, so the row is what grows) */
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-reader_"]) {
  min-height: 0; overflow-y: clip; overflow-clip-margin: 6px;
  animation: grow-in var(--t-layout) var(--ease-layout) backwards;
}
[class*="st-key-reader_"] [role="tabpanel"] { animation: fade-in 320ms var(--ease) backwards; }
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
[class*="st-key-sessions_list_"] { gap: 0 !important; animation: fade-in 360ms var(--ease) backwards; }
[class*="st-key-sessions_list_"] > div { width: 100% !important; min-width: 0; }
[class*="st-key-oncal_"] button { min-height: 32px; padding: 0 !important; }
[class*="st-key-oncal_"] button p { font-size: 0.8125rem; color: var(--label-2); }

/* ---------- motion ---------- */
/* expanders open and close smoothly (where the browser can size to auto) */
:root { interpolate-size: allow-keywords; }
/* Streamlit's expander moves its own height (about half a second, in and
   out); animating it here as well played the close twice. Here, only the
   content fading in as the space opens. */
[data-testid="stExpander"] details::details-content { opacity: 0; }
[data-testid="stExpander"] details[open]::details-content { opacity: 1; transition: opacity 420ms var(--ease) 80ms; }
/* the bookshelf's rows are plain details: the space opens and the content
   fades in inside it; closing, the content fades first and the space follows */
.bk-book::details-content {
  block-size: 0; opacity: 0; overflow-y: clip;
  transition: opacity 200ms var(--ease), block-size 440ms var(--ease-layout) 40ms, content-visibility 480ms allow-discrete;
}
.bk-book[open]::details-content {
  block-size: auto; opacity: 1;
  transition: block-size var(--t-layout) var(--ease-layout), opacity 420ms var(--ease) 80ms, content-visibility var(--t-layout) allow-discrete;
}
[class*="st-key-calgrid_"][class*="_next"] { animation: from-right 520ms var(--ease) backwards; }
[class*="st-key-calgrid_"][class*="_prev"] { animation: from-left 520ms var(--ease) backwards; }
[class*="st-key-calgrid_"][class*="_none"] { animation: fade-in 360ms var(--ease) backwards; }
[class*="st-key-calgrid_"] { transition: opacity 320ms var(--ease), transform 320ms var(--ease); }
[class*="st-key-calgrid_"][data-leaving="next"] { opacity: 0.3; transform: translateX(-10px); }
[class*="st-key-calgrid_"][data-leaving="prev"] { opacity: 0.3; transform: translateX(10px); }
@keyframes from-right { from { opacity: 0; transform: translateX(12px); } }
@keyframes from-left { from { opacity: 0; transform: translateX(-12px); } }
@keyframes rise-in { from { opacity: 0; transform: translateY(8px); } }
@keyframes grow-in { from { opacity: 0; block-size: 0; } }
@keyframes fade-in { from { opacity: 0; } }
@keyframes day-pick { from { background-color: transparent; box-shadow: none; } }
@media (prefers-reduced-motion: reduce) {
  [class*="st-key-calgrid_"], [class*="st-key-prog_day_"], [class*="st-key-reader_"], [class*="st-key-sessions_list_"],
  [class*="st-key-view_"],
  [class*="st-key-reader_"] [role="tabpanel"], [class*="st-key-cal_20"] .stButton button { animation: none !important; }
  [data-testid="stExpander"] details::details-content, [data-testid="stExpander"] details[open]::details-content { transition: none; }
  [class*="st-key-calgrid_"] { transition: none; }
  [data-testid="stLayoutWrapper"]:has(> [class*="st-key-reader_"]) { animation: none !important; }
  /* Streamlit animates an expander's height itself, reduced motion or not: hold it at its size */
  [data-testid="stExpander"] details[style*="height"] { height: auto !important; }
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


# The Reading page (coach/shelf.py): the book being read as the same thin
# liquid line as Today's lessons, and the bookshelf as a quiet grouped list.
BOOKS = """
<style>
.st-key-now_reading { container-type: inline-size; gap: var(--space-3) !important; }
.bk-label { font-size: 0.6875rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--label-3); }
.bk-now { display: grid; gap: 2px; margin: 2px 0 10px; }
.bk-now-title {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; font-size: 1.625rem; line-height: 1.2;
  font-variant-numeric: lining-nums; color: var(--label);
}
.bk-now-author { font-size: 0.875rem; color: var(--label-2); }

/* fourteen stretches of one glass tube; the liquid fills the days done */
.bk-line { display: grid; grid-template-columns: repeat(14, minmax(0, 1fr)); height: 40px; }
.bk-seg { position: relative; }
.bk-seg::before {
  content: ""; position: absolute; left: 0; right: 0; top: 4px; height: 9px;
  background: linear-gradient(180deg, var(--lq-glass-top), var(--lq-glass-bottom));
  box-shadow: inset 0 1px 1px -1px var(--lq-edge-hi), inset 0 -1px 1px -1px var(--lq-edge-lo),
              inset 0 2px 3px -2px var(--lq-edge-near), inset 0 -2px 3px -2px var(--lq-edge-near);
}
.bk-seg:first-child::before { border-radius: 999px 0 0 999px; }
.bk-seg:last-child::before { border-radius: 0 999px 999px 0; }
.bk-seg::after { content: ""; position: absolute; left: 0; top: 6.5px; height: 4px; width: 0; background: var(--lq-liquid); opacity: 0.92; }
.bk-seg:first-child::after { border-top-left-radius: 2px; border-bottom-left-radius: 2px; }
.bk-seg.done::after { width: 100%; }
.bk-seg.done.end::after { border-radius: 0 2.6px 2.2px 0 / 0 2px 2px 0; }
.bk-seg.done.end:first-child::after { border-radius: 2px 2.6px 2.2px 2px / 2px 2px 2px 2px; }
.bk-seg i {
  position: absolute; top: 21px; left: 0; right: 0; text-align: center; font-style: normal;
  font-size: 12px; line-height: 16px; font-variant-numeric: tabular-nums; color: var(--label-2); white-space: nowrap;
}
.bk-seg.current i { color: var(--label); font-weight: 600; }
.bk-seg.ahead i { opacity: 0.35; }
@container (min-width: 560px) { .bk-seg.done:not(.rest) i::after { content: "✓"; font-size: 10px; margin-left: 2px; } }
.bk-line.flowing .bk-seg.done::after { animation: lq-fill 140ms linear calc(var(--i) * 140ms) both; }
.bk-line.flowing .bk-seg.done.end::after { animation-duration: 380ms; animation-timing-function: cubic-bezier(0.3, 0.6, 0.25, 1); }
.bk-line + .lq-meta { margin-top: 6px; }

/* today's part of the book */
.bk-today { display: grid; gap: 2px; margin-top: 14px; }
.bk-k { font-size: 0.6875rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--label-3); }
.bk-v { font-size: 0.9375rem; line-height: 1.5; color: var(--label); }

/* the bookshelf: one light surface, a row per book, 0.5px lines between */
.bk-empty { margin: 0; font-size: 0.875rem; color: var(--label-3); }
.bk-shelf {
  --bk-sep: light-dark(rgba(0, 0, 0, 0.14), rgba(255, 255, 255, 0.14));
  border-radius: var(--radius-small); background: light-dark(rgba(0, 0, 0, 0.028), rgba(255, 255, 255, 0.05));
  overflow: hidden; corner-shape: superellipse(1.6);
}
.bk-book > summary {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  min-height: 56px; box-sizing: border-box; padding: 10px 16px; cursor: pointer; list-style: none;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
  transition: background-color var(--t-micro) var(--ease);
}
.bk-book > summary::-webkit-details-marker { display: none; }
.bk-book > summary::marker { content: ""; }
.bk-book + .bk-book > summary {       /* the line starts where the text does */
  background: linear-gradient(var(--bk-sep), var(--bk-sep)) 16px 0 / calc(100% - 16px) 0.5px no-repeat;
}
.bk-book > summary:active { background-color: var(--wash); }
@media (hover: hover) { .bk-book > summary:hover { background-color: light-dark(rgba(0, 0, 0, 0.02), rgba(255, 255, 255, 0.03)); } }
.bk-book > summary:focus-visible { outline: 1px solid var(--outline); outline-offset: -2px; }
.bk-name { display: grid; gap: 1px; min-width: 0; }
.bk-title { font-size: 0.9375rem; font-weight: 500; color: var(--label); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bk-author { font-size: 0.8125rem; color: var(--label-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bk-state { flex: none; font-size: 0.8125rem; color: var(--label-2); font-variant-numeric: tabular-nums; }

/* a book opened: its fourteen days, what she wrote, whether it passed */
.bk-open { padding: 0 16px 14px; }
.bk-days { list-style: none; margin: 0 !important; padding: 0 !important; }
/* a day: number, chapters and when it passed on one line; what she wrote
   under them, as wide as the row. In a narrow shelf the date drops under
   the chapters. */
.bk-shelf { container-type: inline-size; }
.bk-days li {
  display: grid; grid-template-columns: 3.4em minmax(0, 1fr) auto; grid-template-areas: "d r s" ". w w";
  column-gap: 12px; align-items: baseline;
  padding: 10px 0; font-size: 0.8125rem; line-height: 1.45; border-top: 0.5px solid var(--bk-sep); margin: 0;
}
.bk-d { grid-area: d; } .bk-r { grid-area: r; } .bk-s { grid-area: s; } .bk-days .bk-words { grid-area: w; }
@container (max-width: 380px) {
  .bk-days li { grid-template-columns: 3.4em minmax(0, 1fr); grid-template-areas: "d r" ". s" ". w"; }
  .bk-days .bk-s { margin-top: 1px; }
}
.bk-d { color: var(--label-3); font-variant-numeric: tabular-nums; }
.bk-r { color: var(--label); min-width: 0; }
.bk-s { color: var(--label-2); white-space: nowrap; font-variant-numeric: tabular-nums; }
.bk-days li.rest .bk-r, .bk-days li.rest .bk-s, .bk-days li.unread .bk-s { color: var(--label-3); }
.bk-words { margin: 4px 0 0 !important; color: var(--label-2); font-size: 0.8125rem; line-height: 1.55; }
.bk-wrap { border-top: 0.5px solid var(--bk-sep); padding-top: 10px; display: grid; gap: 4px; }
.bk-wrap p, .bk-wrap li { font-size: 0.875rem; line-height: 1.6; margin: 0 0 6px; color: var(--label); }
.bk-wrap ul { margin: 0 0 6px; padding-left: 1.2em; }

/* ---------- the Reading page: one page in two parts ---------- */
.stMainBlockContainer:has(.reading-page) { max-width: 1400px; }
.page-sub {
  margin: 0; font-size: 0.875rem; line-height: 1.5;
  color: light-dark(rgba(60, 60, 67, 0.78), rgba(235, 235, 245, 0.6));   /* secondary, 4.5:1 or more on either ground */
}
.st-key-read_main { margin-top: var(--space-5); }
.st-key-read_main [data-testid="stHorizontalBlock"] { gap: 72px !important; align-items: flex-start; }
/* wide: the chat box belongs to the book, so it keeps to the left part's width */
@media (min-width: 1024px) {
  .stMainBlockContainer:has(.reading-page) [data-testid="stLayoutWrapper"]:has(> .st-key-chat_dock) { width: calc((100% - 72px) * 6 / 11); }
}
.st-key-read_main [data-testid="stColumn"] { min-width: 0; }
.st-key-read_main h4 { padding-top: 0 !important; }
.st-key-read_main [data-testid="stColumn"]:last-child > [data-testid="stVerticalBlock"] { gap: 14px; }
@media (max-width: 1023.98px) {       /* one column: the book, then the shelf */
  .st-key-read_main [data-testid="stHorizontalBlock"] { flex-direction: column !important; gap: var(--space-7) !important; }
  .st-key-read_main [data-testid="stColumn"] { width: 100% !important; flex: 1 1 auto !important; }
}
@media (max-width: 640px) {
  .st-key-read_main { margin-top: var(--space-3); }
  .st-key-read_main [data-testid="stHorizontalBlock"] { gap: var(--space-6) !important; }
}

/* no book: a quiet outlined action the size of its words (36px to the eye, 44px to the finger) */
.st-key-start_book button {
  position: relative; width: auto; min-height: 36px; height: 36px; padding: 0 16px !important;
  border-radius: 999px; background: transparent !important; box-shadow: none !important;
  border: 0.5px solid light-dark(rgba(60, 60, 67, 0.36), rgba(235, 235, 245, 0.3)) !important;
  -webkit-backdrop-filter: none !important; backdrop-filter: none !important;
}
.st-key-start_book button::after { content: ""; position: absolute; inset: -5px -2px; }
.st-key-start_book button { transition: background-color var(--t-micro) var(--ease), border-color var(--t-micro) var(--ease), transform var(--t-micro) var(--ease) !important; }
@media (hover: hover) {
  .st-key-start_book button:hover { border-color: light-dark(rgba(60, 60, 67, 0.6), rgba(235, 235, 245, 0.5)) !important; }
}
.st-key-start_book button p { font-size: 0.875rem; color: var(--label); }
.st-key-start_book button:active { background: var(--wash) !important; transition-duration: var(--t-press) !important; }

/* an open book: its title row offers Close (the whole row closes it) */
.bk-side { flex: none; display: flex; align-items: baseline; gap: 14px; }
.bk-close { display: none; font-size: 13px; color: var(--label-2); }
.bk-book[open] > summary .bk-close { display: inline; }
/* the days not read wait behind one quiet line; opened, the whole fortnight shows in place */
.bk-open:not(:has(> .bk-more[open])) .bk-days li.later { display: none; block-size: 0; opacity: 0; padding-block: 0; }
.bk-days li.later {
  block-size: auto; overflow: clip;
  transition: block-size 480ms var(--ease-layout), padding-block 480ms var(--ease-layout),
              opacity 360ms var(--ease) 80ms, display 480ms allow-discrete;
}
@starting-style { .bk-open:has(> .bk-more[open]) .bk-days li.later { block-size: 0; opacity: 0; padding-block: 0; } }
.bk-more > summary {
  display: flex; align-items: center; min-height: 44px; cursor: pointer; list-style: none;
  font-size: 0.8125rem; color: var(--label-2); border-top: 0.5px solid var(--bk-sep);
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}
.bk-more > summary::-webkit-details-marker { display: none; }
.bk-more > summary::marker { content: ""; }
.bk-more > summary:active { color: var(--label); }
@media (hover: hover) { .bk-more > summary:hover { color: var(--label); } }
.bk-more-hide, .bk-more[open] .bk-more-show { display: none; }
.bk-more[open] .bk-more-hide { display: inline; }
@media (prefers-reduced-motion: reduce) { .bk-days li.later { transition: none; } }

/* Reading's chat box: a translucent material, clearly a surface to write
   on (what passes behind is blurred well away from the text), with a
   quiet ring when focused */
.stMainBlockContainer:has(.reading-page) [data-testid="stChatInput"] {
  background: light-dark(rgba(255, 255, 255, 0.64), rgba(30, 30, 32, 0.64)) !important;
  -webkit-backdrop-filter: blur(16px) saturate(1.8); backdrop-filter: blur(16px) saturate(1.8);
  box-shadow: inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.1), rgba(255, 255, 255, 0.12)),
              0 6px 20px -14px light-dark(rgba(0, 0, 0, 0.25), rgba(0, 0, 0, 0.9));
  transition: box-shadow 360ms var(--ease), background-color 360ms var(--ease);
}
.stMainBlockContainer:has(.reading-page) [data-testid="stChatInput"]:focus-within {
  background: light-dark(rgba(255, 255, 255, 0.74), rgba(34, 34, 36, 0.74)) !important;
  box-shadow: inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.3), rgba(255, 255, 255, 0.3)),
              0 0 0 3px light-dark(rgba(0, 0, 0, 0.045), rgba(255, 255, 255, 0.06)),
              0 6px 20px -14px light-dark(rgba(0, 0, 0, 0.25), rgba(0, 0, 0, 0.9));
}
.stMainBlockContainer:has(.reading-page) [data-testid="stChatInput"] textarea::placeholder { color: var(--label-2); }

/* Progress, Subjects: Reading is one line leading to its page */
.st-key-subj_list [data-testid="stPageLink"] a {
  padding: 0; min-height: 44px; background: transparent !important; border-radius: 0;
}
.st-key-subj_list [data-testid="stPageLink"] p {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; font-size: 1.1875rem; color: var(--label);
  text-decoration: underline; text-decoration-color: var(--label-3); text-underline-offset: 0.2em; text-decoration-thickness: 0.5px;
}
@media (prefers-reduced-motion: reduce) {
  .bk-line.flowing .bk-seg.done::after { animation: none; }
  .bk-book::details-content, .bk-book[open]::details-content { transition: none; }
  .st-key-start_book button, .stMainBlockContainer:has(.reading-page) [data-testid="stChatInput"] { transition: none !important; }
}
</style>
"""


# Connected controls (coach/motion.py) and the page navigation at the top
# (coach/topnav.py): one object with one active surface that travels.
NAV = """
<style>
/* the travelling surface: the same material as a chosen segment */
.cx-pill {
  position: absolute; left: 0; top: 0; z-index: 0; pointer-events: none; border-radius: 999px;
  background: light-dark(#FFFFFF, rgba(255, 255, 255, 0.13)); box-shadow: var(--optic-strong);
  will-change: transform, width;
}
[data-cx] { position: relative; isolation: isolate; }
.cx-pill { transition: opacity var(--t-micro) var(--ease); }
/* Today's lessons: the one short mark under the lesson open, travelling
   (it takes over from the mark each lesson drew for itself) */
.cx-pill.cx-mark { background: var(--label); box-shadow: none; border-radius: 0; }
[class*="st-key-lesson_steps"][data-cx] [class*="st-key-step_"][class*="_viewing"] button p::before { display: none; }
[data-cx] > :not(.cx-pill) { position: relative; z-index: 1; }

/* ---------- the header: one surface in three parts ----------
   left, the sidebar control; in the middle, the pages and Search; on the
   right, the app's own actions. No part has a surface of its own: they
   all sit on the header's glass, over one hairline at its lower edge. The
   page that is on is marked by a thin line on that edge, under its word,
   and the line travels (coach/motion.py). */
[data-testid="stHeader"] { height: 56px; min-height: 56px; box-shadow: inset 0 -0.5px 0 var(--field-edge); }
[data-testid="stLayoutWrapper"]:has(> .st-key-topnav) {
  position: fixed; top: 0; left: var(--cx-main, 50%); transform: translateX(-50%); z-index: 999990; width: auto !important;
  transition: left var(--t-layout) var(--ease-layout);    /* follows the page as the sidebar opens and closes */
}
.st-key-topnav { width: auto !important; height: 56px; flex-wrap: nowrap !important; gap: 0 !important; padding: 0; background: none; }
.st-key-topnav_items { width: auto !important; height: 56px !important; min-height: 56px; align-self: stretch !important; flex-wrap: nowrap !important; gap: 0 !important; align-items: stretch !important; }
.st-key-topnav > div, .st-key-topnav_items > div { width: auto !important; flex: 0 0 auto !important; min-width: 0; }
.st-key-topnav_items > div, .st-key-topnav_items [data-testid="stPageLink"] { height: 100%; margin: 0 !important; }
.st-key-topnav [data-testid="stPageLink-NavLink"] {
  position: relative; display: flex; align-items: center; justify-content: center;
  height: 56px; min-height: 56px; padding: 0 18px; margin: 0; border-radius: 0;
  background: transparent !important; text-decoration: none; -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}
.st-key-topnav [data-testid="stPageLink-NavLink"] p {
  margin: 0; font-size: 0.875rem; font-weight: 500; letter-spacing: 0.01em; white-space: nowrap;
  color: var(--label-2); transition: color var(--cx-dur, 360ms) var(--ease);
}
.st-key-topnav [data-testid="stPageLink-NavLink"][data-cx-on] p { color: var(--label); }
@media (hover: hover) { .st-key-topnav [data-testid="stPageLink-NavLink"]:not([data-cx-on]):hover p { color: var(--label); } }
.st-key-topnav [data-testid="stPageLink-NavLink"]:active p { color: var(--label); }
.st-key-topnav [data-testid="stPageLink-NavLink"]:focus-visible { outline: none; }
.st-key-topnav [data-testid="stPageLink-NavLink"]:focus-visible p { outline: 1px solid var(--outline); outline-offset: 4px; border-radius: 3px; }
/* the travelling mark: a thin line of the text's own colour on the header's edge */
.cx-pill.cx-line { background: var(--label); box-shadow: none; border-radius: 1px; }
/* Search: in the same row, after a short upright hairline */
.st-key-nav_search { position: relative; margin-left: 8px; display: flex; align-items: center; }
.st-key-nav_search::before {
  content: ""; position: absolute; left: -4px; top: 50%; height: 14px; margin-top: -7px; width: 0.5px; background: var(--field-edge);
}
.st-key-nav_search button {
  position: relative; width: 44px; min-width: 44px; height: 56px; min-height: 56px; padding: 0 !important;
  border-radius: 0; border: none !important; background: transparent !important; box-shadow: none !important;
  -webkit-backdrop-filter: none !important; backdrop-filter: none !important; color: var(--label-2);
  -webkit-tap-highlight-color: transparent; touch-action: manipulation; transition: color var(--t-micro) var(--ease);
}
.st-key-nav_search button p { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.st-key-nav_search button:active { color: var(--label); transform: none !important; }
@media (hover: hover) { .st-key-nav_search button:hover { color: var(--label); } }
/* the right: the app's own actions (Share, Star, Edit, GitHub, the menu) on
   the same surface, in the same quiet grey, answering like the pages do */
[data-testid="stToolbar"] { align-items: center; }
[data-testid="stToolbarActions"] button, [data-testid="stMainMenu"] button,
[data-testid="stToolbarActionButton"], [data-testid="stAppDeployButton"] button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--label-2) !important; transition: color var(--t-micro) var(--ease);
}
[data-testid="stToolbarActions"] button p, [data-testid="stToolbarActionButton"] p { font-size: 0.8125rem; font-weight: 500; color: inherit; }
@media (hover: hover) {
  [data-testid="stToolbarActions"] button:hover, [data-testid="stMainMenu"] button:hover, [data-testid="stToolbarActionButton"]:hover { color: var(--label) !important; }
}
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapseButton"] button { color: var(--label-2); transition: color var(--t-micro) var(--ease); }
@media (hover: hover) { [data-testid="stExpandSidebarButton"]:hover, [data-testid="stSidebarCollapseButton"] button:hover { color: var(--label); } }
/* narrower: the same three parts, closer together; the actions keep their
   icons and give up their words, then (on a phone) rest in the menu */
@media (max-width: 1024px) {
  .st-key-topnav [data-testid="stPageLink-NavLink"] { padding: 0 14px; }
  [data-testid="stToolbarActions"] button p, [data-testid="stToolbarActionButton"] p { display: none; }
}
@media (max-width: 640px) {
  .st-key-topnav [data-testid="stPageLink-NavLink"] { padding: 0 11px; }
  .st-key-nav_search { margin-left: 4px; }
  .st-key-nav_search button { width: 40px; min-width: 40px; }
  [data-testid="stToolbarActions"] { display: none; }
}
@media (max-width: 360px) {
  .st-key-topnav [data-testid="stPageLink-NavLink"] { padding: 0 6px; }
  .st-key-topnav [data-testid="stPageLink-NavLink"] p { font-size: 0.8125rem; }
  .st-key-nav_search { margin-left: 4px; }
  .st-key-nav_search button { width: 32px; min-width: 32px; }
}

/* moving between pages: the content quietens as the surface sets off, and
   the new page's blocks come in as it arrives (arrive, above) */
:root[data-cx-leaving] .stMainBlockContainer > [data-testid="stVerticalBlock"] > :not(:has(> .st-key-topnav)) {
  opacity: 0.35; transition: opacity 260ms var(--ease);
}

/* ---------- Progress: Day / Sessions / Subjects share the one surface ---------- */
.st-key-prog_view [data-cx] button[aria-checked="true"] { background: transparent !important; box-shadow: none !important; }
.st-key-prog_view [data-cx] button p { font-weight: 500 !important; transition: color var(--cx-dur, 360ms) var(--ease); }
.st-key-prog_view [data-cx] button { color: var(--label-2); }
.st-key-prog_view [data-cx] button[data-cx-on] { color: var(--label); }

/* ---------- tabs: Streamlit's own sliding mark, on the same clock ---------- */
[data-testid="stTab"] > [data-rac]:not([data-testid]) {
  transition: translate var(--t-state) var(--ease-nav), width var(--t-state) var(--ease-nav), background-color var(--t-micro) var(--ease) !important;
}

/* ---------- Search ---------- */
.st-key-search_results { gap: 0 !important; }
[class*="st-key-sres_"] { position: relative; gap: 0 !important; border-top: 0.5px solid var(--hair); border-radius: 10px; transition: background-color var(--t-micro) var(--ease); }
.sr { display: grid; gap: 2px; padding: 12px 8px; }
.sr-t { font-size: 0.9375rem; font-weight: 500; color: var(--label); }
.sr-m { font-size: 0.75rem; color: var(--label-3); }
.sr-s { font-size: 0.8125rem; line-height: 1.5; color: var(--label-2); }
/* the whole row is the button: it lies over the row, unseen, and the
   text beneath lets the tap through to it */
[class*="st-key-sres_"] [data-testid="stElementContainer"]:has(.sr) { pointer-events: none; }
[class*="st-key-sres_"] [data-testid="stElementContainer"]:has(.stButton),
[class*="st-key-sres_"] [data-testid="stElementContainer"]:has(.stButton) *:not(button) { position: static !important; }
[class*="st-key-sres_"] .stButton button {
  position: absolute !important; inset: 0; width: 100%; height: 100%; min-height: 0; z-index: 2; opacity: 0; cursor: pointer;
}
[class*="st-key-sres_"]:has(button:active) { background: var(--wash); }
@media (hover: hover) { [class*="st-key-sres_"]:hover { background: var(--wash); } }
[class*="st-key-sres_"]:has(button:focus-visible) { outline: 1px solid var(--outline); outline-offset: -1px; }
@media (pointer: coarse) { [role="dialog"] input { font-size: 16px !important; } }
/* a dialog's title: the same serif as every other heading */
[role="dialog"] [data-testid="stMarkdownContainer"]:not([data-testid="stVerticalBlock"] [data-testid="stMarkdownContainer"]) p {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; font-size: 1.625rem; line-height: 1.2; color: var(--label);
}

/* ---------- signing in: a quiet, centred page, not a boxed form ---------- */
.stMainBlockContainer:has([data-testid="stForm"]):not(:has(.st-key-topnav)) { max-width: 420px; padding-top: max(96px, 20vh); }
.stMainBlockContainer:has([data-testid="stForm"]):not(:has(.st-key-topnav)) h3 { font-size: 2.25rem; padding-bottom: 4px; }
.stMainBlockContainer:has([data-testid="stForm"]):not(:has(.st-key-topnav)) [data-testid="stForm"] { border: none; padding: 0; }
.stMainBlockContainer:has([data-testid="stForm"]):not(:has(.st-key-topnav)) [data-testid="stForm"] [data-testid="stElementContainer"]:has(button[kind="primaryFormSubmit"]),
.stMainBlockContainer:has([data-testid="stForm"]):not(:has(.st-key-topnav)) [data-testid="stForm"] [data-testid="stElementContainer"]:has(button[kind="primaryFormSubmit"]) *:has(button),
.stMainBlockContainer:has([data-testid="stForm"]):not(:has(.st-key-topnav)) button[kind="primaryFormSubmit"] { width: 100% !important; }
</style>
"""


SETUP = """
<style>
/* ---------- Settings in the bar: its name on a wide page; where the bar is
   narrow, a gear (like Search beside it), its name kept for screen readers ---------- */
.st-key-topnav [data-testid="stPageLink-NavLink"] > span:has([data-testid="stIconMaterial"]) { display: none; }
.st-key-topnav [data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {
  font-size: 18px; color: var(--label-2) !important; transition: color var(--cx-dur, 360ms) var(--ease);
  font-variation-settings: "FILL" 0, "wght" 300;     /* as light as the search glass beside it */
}
.st-key-topnav [data-testid="stPageLink-NavLink"][data-cx-on] [data-testid="stIconMaterial"] { color: var(--label) !important; }
@media (max-width: 640px) {
  .st-key-topnav [data-testid="stPageLink-NavLink"] > span:has([data-testid="stIconMaterial"]) { display: inline-flex; align-items: center; margin: 0; }
  .st-key-topnav [data-testid="stPageLink-NavLink"]:has([data-testid="stIconMaterial"]) > span:not(:has([data-testid="stIconMaterial"])) {
    position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap;
  }
}

/* ---------- setup and Settings: the same product, one decision at a time ---------- */
.stMainBlockContainer:has(#setup-page) { max-width: 1120px; }
.stMainBlockContainer:has(#settings-page) { max-width: 820px; }

/* where she is in the setup: one hairline filling step by step, and its name */
.ob-progress { display: grid; gap: 10px; }
.ob-track { position: relative; height: 1px; background: var(--field-edge); overflow: hidden; }
.ob-track i {
  position: absolute; inset: 0; background: var(--label); transform-origin: 0 50%;
  transform: scaleX(var(--to)); animation: ob-fill var(--t-layout) var(--ease-layout) both;
}
@keyframes ob-fill { from { transform: scaleX(var(--from)); } to { transform: scaleX(var(--to)); } }
.ob-where { display: flex; justify-content: space-between; font-size: 0.6875rem; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--label-3); font-variant-numeric: tabular-nums; }

/* a step comes in from the side she is heading to, and settles */
[class*="st-key-ob_step_"][class*="_fwd"] { animation: ob-from-right var(--t-space) var(--ease) both; }
[class*="st-key-ob_step_"][class*="_back"] { animation: ob-from-left var(--t-space) var(--ease) both; }
@keyframes ob-from-right { from { opacity: 0; transform: translateX(16px); } to { opacity: 1; transform: none; } }
@keyframes ob-from-left { from { opacity: 0; transform: translateX(-16px); } to { opacity: 1; transform: none; } }
[class*="st-key-ob_step_"] { gap: var(--space-5) !important; }
[class*="st-key-ob_step_"] h2 { padding-bottom: 0; }
[class*="st-key-ob_step_"] [data-testid="stElementContainer"]:has(h2) + [data-testid="stElementContainer"] { margin-top: calc(-1 * var(--space-2)); }
.ob-lede { margin: 0; max-width: 32rem; font-size: 1.0625rem; line-height: 1.5; color: var(--label-2); }
.ob-note { margin: 0; font-size: 0.8125rem; line-height: 1.5; color: var(--label-3); }

/* Back (quiet words) and Continue */
.st-key-ob_nav { margin-top: var(--space-2); gap: var(--space-3) !important; }
.st-key-ob_nav .stButton button[kind="primary"] { min-width: 148px; }
/* each button keeps its own width, however narrow the page */
.st-key-ob_nav > [data-testid="stElementContainer"], [class*="st-key-pqnav_"] > [data-testid="stElementContainer"],
[class*="st-key-pqdone_"] > [data-testid="stElementContainer"]:has(.stButton), [class*="st-key-setlvl_"] > [data-testid="stElementContainer"]:has(.stButton) {
  flex: 0 0 auto !important; width: auto !important; min-width: 0;
}
.st-key-ob_nav button, [class*="st-key-pqnav_"] button, [class*="st-key-pqdone_"] button, [class*="st-key-setlvl_"] button { white-space: nowrap; width: auto !important; }
.st-key-ob_nav button p, [class*="st-key-pqnav_"] button p, [class*="st-key-setlvl_"] button p { overflow: visible !important; text-overflow: clip !important; }
.st-key-ob_nav [data-testid="stElementContainer"]:has(+ [data-testid="stElementContainer"] .ob-note) { margin: 0; }
[data-testid="stElementContainer"]:has(.ob-note) + [data-testid="stLayoutWrapper"]:has(> .st-key-ob_nav) { margin-top: calc(-1 * var(--space-2)); }
.pq-gap { display: block; width: 1px; height: 1px; }
/* Back, Previous, Retake: words, not boxes */
.stMainBlockContainer:is(:has(#setup-page), :has(#settings-page)) .stButton button[kind="tertiary"] {
  color: var(--label-2); min-height: 44px; padding: 0 var(--space-2); background: transparent !important;
  border-color: transparent !important; box-shadow: none !important; backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
}
.st-key-ob_nav .stButton button[kind="tertiary"] { margin-left: calc(-1 * var(--space-2)); }
@media (hover: hover) { .stMainBlockContainer:is(:has(#setup-page), :has(#settings-page)) .stButton button[kind="tertiary"]:hover { color: var(--label); } }

/* ---------- a list of options: one row each; the whole row is the button ---------- */
[class*="st-key-optlist_"] { gap: 0 !important; border-bottom: 0.5px solid var(--field-edge); }
[class*="st-key-opt_"] {
  position: relative; gap: 0 !important; border-top: 0.5px solid var(--field-edge);
  transition: background-color var(--t-micro) var(--ease);
}
.opt { display: grid; grid-template-columns: minmax(0, 1fr) 20px; column-gap: var(--space-4); row-gap: 2px;
  align-items: center; min-height: 52px; padding: 13px 14px 13px 18px; box-sizing: border-box; }
.opt-t { grid-column: 1; font-size: 0.9375rem; line-height: 1.35; font-weight: 500; color: var(--label);
  transition: color var(--t-micro) var(--ease); }
.opt-s { grid-column: 1; font-size: 0.8125rem; line-height: 1.45; color: var(--label-2); }
.opt-mark { grid-column: 2; grid-row: 1 / span 2; position: relative; width: 20px; height: 20px; }
/* the check: drawn when chosen, gone when not */
.opt-mark::after {
  content: ""; position: absolute; left: 7px; top: 3px; width: 5px; height: 10px;
  border: solid var(--label); border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg) scale(0.6); opacity: 0;
  transition: opacity var(--t-micro) var(--ease), transform var(--t-state) var(--ease);
}
/* chosen: the check, the rule and a heavier name (a tap shows it at once: motion.py) */
[class*="st-key-opt_"][class*="__sel"]:not([data-on="0"]) .opt-t, [class*="st-key-opt_"][data-on="1"] .opt-t { font-weight: 600; }
[class*="st-key-opt_"][class*="__sel"]:not([data-on="0"]) .opt-mark::after,
[class*="st-key-opt_"][data-on="1"] .opt-mark::after { opacity: 1; transform: rotate(45deg) scale(1); }
/* a row that can't be chosen now (three already chosen) */
[class*="st-key-opt_"] [data-testid="stElementContainer"]:has(.opt) { pointer-events: none; }
[class*="st-key-opt_"] [data-testid="stElementContainer"]:has(.stButton),
[class*="st-key-opt_"] [data-testid="stElementContainer"]:has(.stButton) *:not(button) { position: static !important; }
[class*="st-key-opt_"] .stButton button {
  position: absolute !important; inset: 0; width: 100%; height: 100%; min-height: 0; z-index: 2; opacity: 0;
  cursor: pointer; transform: none !important;
}
[class*="st-key-opt_"] .stButton button:disabled { cursor: default; }
/* past the limit: quieter, but it can still be looked at */
[class*="st-key-opt_"][class*="__dis"] .opt { opacity: 0.5; transition: opacity var(--cx-dur, 360ms) var(--ease); }
[class*="st-key-optlist_"] [class*="__dis"][data-cx-on] .opt { opacity: 0.85; }
@media (hover: hover) { [class*="st-key-opt_"]:not([class*="__dis"]):hover { background: var(--wash); } }
[class*="st-key-opt_"]:not([class*="__dis"]):has(button:active) { background: var(--wash); transition-duration: var(--t-press); }
[class*="st-key-opt_"]:has(button:focus-visible) { outline: 1px solid var(--outline); outline-offset: -1px; }

/* ---------- Level: a subject at a time ---------- */
[class*="st-key-ob_subject_"] { gap: var(--space-3) !important; padding-top: var(--space-4); border-top: 0.5px solid var(--field-edge); }
.ob-subject { margin: 0; font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; font-size: 1.375rem; line-height: 1.25; color: var(--label); }
/* the two ways to start: the same switch as Progress's */
[class*="st-key-sw_"] [data-testid="stButtonGroup"], [class*="st-key-sw_"] [data-testid="stButtonGroup"] > div { width: 100%; }
[class*="st-key-sw_"] [data-testid="stButtonGroup"] > div { display: flex; gap: 2px; padding: 3px; border-radius: 999px; background: var(--wash); border: none; }
[class*="st-key-sw_"] [data-testid="stButtonGroup"] button {
  flex: 1 1 0; min-height: 36px; margin: 0 !important; border: none !important; border-radius: 999px !important;
  background: transparent !important; box-shadow: none !important; color: var(--label-2);
  transition: background-color var(--t-state) var(--ease), color var(--t-state) var(--ease), box-shadow var(--t-state) var(--ease);
}
[class*="st-key-sw_"] [data-testid="stButtonGroup"] button p { font-size: 0.875rem; white-space: nowrap; }
[class*="st-key-sw_"] [data-testid="stButtonGroup"] button[aria-checked="true"] { background: var(--env) !important; color: var(--label); box-shadow: var(--optic-strong) !important; }
[class*="st-key-sw_"] [data-cx] button[aria-checked="true"] { background: transparent !important; box-shadow: none !important; }
[class*="st-key-sw_"] [data-cx] button { color: var(--label-2); }
[class*="st-key-sw_"] [data-cx] button p { font-weight: 500 !important; transition: color var(--cx-dur, 360ms) var(--ease); }
[class*="st-key-sw_"] [data-cx] button[data-cx-on] { color: var(--label); }
@media (hover: hover) { [class*="st-key-sw_"] [data-testid="stButtonGroup"] button:hover:not([data-cx-on]) { color: var(--label); } }
@media (pointer: coarse) { [class*="st-key-sw_"] [data-testid="stButtonGroup"] button { min-height: 40px; } [class*="st-key-sw_"] [data-testid="stButtonGroup"] button::after { inset: -3px -1px; } }

/* the placement check: a question at a time, each coming in on its own */
[class*="st-key-pq_"] { gap: var(--space-3) !important; animation: ob-from-right var(--t-state) var(--ease) both; }
.pq-count { margin: var(--space-2) 0 0; font-size: 0.6875rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--label-3); font-variant-numeric: tabular-nums; }
.pq-q { margin: 6px 0 var(--space-1); font-size: 1rem; line-height: 1.45; font-weight: 500; color: var(--label); max-width: 34rem; }
[class*="st-key-pqnav_"] { margin-top: var(--space-1); }
[class*="st-key-pqdone_"] { gap: var(--space-3) !important; animation: ob-from-right var(--t-state) var(--ease) both; }
.pq-result { margin: 0; display: flex; align-items: baseline; gap: 10px; font-size: 0.9375rem; color: var(--label); }
.pq-result b { font-weight: 600; }
.pq-result span { font-size: 0.8125rem; color: var(--label-2); }

/* ---------- Reading: the toggle on a hairline ---------- */
.st-key-ob_toggle { border-top: 0.5px solid var(--field-edge); border-bottom: 0.5px solid var(--field-edge); padding: 6px 0 6px 2px; }

/* ---------- Summary: a quiet list of what she chose ---------- */
.ob-summary { margin: 0 !important; padding: 0 !important; border-top: 0.5px solid var(--field-edge); }
.ob-summary dd, .ob-summary dt { margin: 0 !important; padding-left: 0 !important; }
.ob-summary > div { margin: 0 !important; display: grid; grid-template-columns: 9.5rem minmax(0, 1fr); gap: var(--space-4); padding: 16px 0; border-bottom: 0.5px solid var(--field-edge); }
.ob-summary dt { font-size: 0.8125rem; line-height: 1.5; color: var(--label-2); padding-top: 1px; }
.ob-summary dd { margin: 0; display: grid; gap: 4px; font-size: 0.9375rem; line-height: 1.45; color: var(--label); }
.ob-summary small { font-size: 0.8125rem; color: var(--label-2); }
.ob-pair { display: flex; justify-content: space-between; gap: var(--space-3); }
.ob-pair small { font-size: 0.8125rem; }
@media (max-width: 520px) {
  .ob-summary > div { grid-template-columns: 1fr; gap: 4px; padding: 14px 0; }
  .ob-lede { font-size: 1rem; }
}

/* ---------- Settings: sections on hairlines; wide, the name beside its controls ---------- */
[class*="st-key-set_sec_"] { gap: var(--space-4) !important; padding-top: var(--space-5); border-top: 0.5px solid var(--field-edge); }
[class*="st-key-set_sec_"] h4 { padding-top: 0 !important; }
/* the section's hairline is the list's top edge: no second line under it */
[class*="st-key-set_sec_"] [class*="st-key-optlist_"] [class*="st-key-opt_"]:first-child,
[class*="st-key-set_sec_"] [class*="st-key-optlist_"] > :first-child [class*="st-key-opt_"] { border-top: none; }
[class*="st-key-set_sec_"] .st-key-ob_toggle { border-top: none; padding-top: 0; }
@media (min-width: 900px) { [class*="st-key-set_sec_"] .st-key-ob_toggle { margin-top: -6px; } }
@media (min-width: 900px) {
  [class*="st-key-set_sec_"] { display: grid !important; grid-template-columns: 10rem minmax(0, 1fr); column-gap: var(--space-6); align-items: start; }
  [class*="st-key-set_sec_"] > * { grid-column: 2; }
  [class*="st-key-set_sec_"] > :first-child { grid-column: 1; grid-row: 1; }
}
[class*="st-key-setlvl_"] { justify-content: space-between; gap: var(--space-3) !important; min-height: 44px; }
.set-level { margin: 0; display: flex; align-items: baseline; gap: 10px; font-size: 0.9375rem; color: var(--label); }
.set-level b { font-weight: 500; color: var(--label-2); font-size: 0.8125rem; }
.set-kept { color: var(--label-2); }
</style>
"""

LENS = """
<style>
/* ==========================================================================
   THE LENS: one piece of clear glass per control, travelling between choices
   --------------------------------------------------------------------------
   It lies over the words chosen. Its middle is perfectly clear (no frost:
   the words stay sharp); only a narrow rim bends what passes under it
   (glass.py: lg-lens), and a hairline of light marks its upper edge.
   Settled it is nearly invisible; while it travels (cx-live, motion.py) the
   rim bends a little more and its edge light gathers, then calms. Where the
   browser can't bend light, the same shape and edge light alone.
   ========================================================================== */
:root {
  --lens-fill: light-dark(rgba(0, 0, 0, 0.014), rgba(255, 255, 255, 0.03));
  --lens-fill-live: light-dark(rgba(0, 0, 0, 0.02), rgba(255, 255, 255, 0.045));
  --lens-rim:
    inset 0 0.5px 0 0 light-dark(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.2)),
    inset 0 -0.5px 0 0 light-dark(rgba(0, 0, 0, 0.07), rgba(255, 255, 255, 0.05)),
    inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.07), rgba(255, 255, 255, 0.09)),
    inset 0 0 18px -8px light-dark(rgba(0, 0, 0, 0.06), rgba(255, 255, 255, 0.07)),
    0 8px 22px -16px light-dark(rgba(0, 0, 0, 0.3), rgba(0, 0, 0, 0.9));
  --lens-rim-live:
    inset 0 1px 0 0 light-dark(rgba(255, 255, 255, 1), rgba(255, 255, 255, 0.34)),
    inset 0 -0.5px 0 0 light-dark(rgba(0, 0, 0, 0.1), rgba(255, 255, 255, 0.08)),
    inset 0 0 0 0.5px light-dark(rgba(0, 0, 0, 0.1), rgba(255, 255, 255, 0.14)),
    inset 0 0 22px -8px light-dark(rgba(0, 0, 0, 0.09), rgba(255, 255, 255, 0.11)),
    0 12px 26px -16px light-dark(rgba(0, 0, 0, 0.36), rgba(0, 0, 0, 0.95));
  --lens-optics: none; --lens-optics-live: none;
}
:root[data-refract] { --lens-optics: url(#lg-lens); --lens-optics-live: url(#lg-lens-live); }
:root[data-refract][data-scheme="dark"] { --lens-optics: url(#lg-lens-dim); --lens-optics-live: url(#lg-lens-live-dim); }
.cx-pill.cx-lens {
  z-index: 3; pointer-events: none; border-radius: 14px; corner-shape: superellipse(1.6);
  background: var(--lens-fill); box-shadow: var(--lens-rim);
  backdrop-filter: var(--lens-optics); -webkit-backdrop-filter: none;
}
.cx-pill.cx-lens.cx-live { background: var(--lens-fill-live); box-shadow: var(--lens-rim-live); backdrop-filter: var(--lens-optics-live); }
/* in a switch the track is a pill, and so is the lens riding in it */
.st-key-prog_view .cx-pill.cx-lens, [class*="st-key-sw_"] .cx-pill.cx-lens { border-radius: 999px; }
.st-key-prog_view [data-testid="stButtonGroup"] > div, [class*="st-key-sw_"] [data-testid="stButtonGroup"] > div {
  background: light-dark(rgba(0, 0, 0, 0.035), rgba(255, 255, 255, 0.045)) !important;
  box-shadow: inset 0 0 0 0.5px var(--hair);
}

/* ---------- a list of options, under the lens ---------- */
/* the words: quieter where not chosen, full where chosen or under the lens,
   changing on the lens's own clock */
[class*="st-key-optlist_"] .opt-t { color: var(--label-2); transition: color var(--cx-dur, 360ms) var(--ease); }
[class*="st-key-opt_"][class*="__sel"]:not([data-on="0"]) .opt-t, [class*="st-key-opt_"][data-on="1"] .opt-t,
[class*="st-key-optlist_"] [data-cx-on] .opt-t { color: var(--label); }
[class*="st-key-optlist_"] .opt-s { transition: color var(--cx-dur, 360ms) var(--ease); }
[class*="st-key-optlist_"] [data-cx-on] .opt-s { color: var(--label); opacity: 0.72; }
[class*="st-key-opt_"][class*="__sel"]:not([data-on="0"]) .opt-t, [class*="st-key-opt_"][data-on="1"] .opt-t { font-weight: 500; }
/* hover: the faintest wash, never where the lens is */
@media (hover: hover) { [class*="st-key-opt_"]:not([class*="__dis"]):hover { background: transparent; }
  [class*="st-key-optlist_"] [class*="st-key-opt_"]:not([class*="__dis"]):not([data-cx-on]):hover .opt-t { color: var(--label); } }
[class*="st-key-opt_"]:not([class*="__dis"]):has(button:active) { background: transparent; }
[class*="st-key-opt_"]:has(button:focus-visible) { outline: 1px solid var(--outline); outline-offset: -3px; border-radius: 12px; }
/* chosen, in a list of several: the check, and under it the day in the rotation */
.opt-mark { display: flex; flex-direction: column; align-items: center; justify-content: flex-start; width: auto; min-width: 32px; height: auto; min-height: 20px; }
.opt-mark::after { left: 50%; margin-left: -3px; top: 2px; }
.opt-day { margin-top: 20px; font-size: 0.6875rem; letter-spacing: 0.02em; color: var(--label-2); font-variant-numeric: tabular-nums; white-space: nowrap; }

/* the index (Subjects): a number, a name in the serif, a line under it */
.opt-index { grid-template-columns: 2.5rem minmax(0, 1fr) auto; padding: 18px 16px 18px 14px; row-gap: 4px; }
.opt-index .opt-n { grid-column: 1; grid-row: 1 / span 2; align-self: start; padding-top: 9px;
  font-size: 0.6875rem; letter-spacing: 0.1em; color: var(--label-3); font-variant-numeric: tabular-nums; }
.opt-index .opt-t { grid-column: 2; font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300 !important;
  font-size: 1.625rem; line-height: 1.12; letter-spacing: 0; }
.opt-index .opt-s { grid-column: 2; }
.opt-index .opt-mark { grid-column: 3; grid-row: 1 / span 2; }
@media (max-width: 520px) { .opt-index .opt-t { font-size: 1.375rem; } .opt-index { grid-template-columns: 2rem minmax(0, 1fr) auto; } }

/* the daily pace: its lessons as the day's line will draw them */
.opt-pace { grid-template-columns: minmax(0, 1fr) auto 32px; }
.opt-pace .opt-t { grid-column: 1; font-size: 1.0625rem; }
.opt-pace .opt-s { grid-column: 1; }
.opt-bars { grid-column: 2; grid-row: 1 / span 2; display: flex; gap: 3px; }
.opt-bars i { width: 12px; height: 3px; border-radius: 2px; background: var(--field-edge); transition: background-color var(--cx-dur, 360ms) var(--ease); }
.opt-bars i.on { background: var(--label-2); }
[class*="st-key-optlist_"] [data-cx-on] .opt-bars i.on, [class*="st-key-opt_"][class*="__sel"] .opt-bars i.on { background: var(--label); }
.opt-pace .opt-mark { grid-column: 3; grid-row: 1 / span 2; }

/* ==========================================================================
   SETUP: one editorial grid; the question on the left, the decision on the right
   ========================================================================== */
.st-key-ob_hero { gap: var(--space-5) !important; padding: clamp(24px, 9vh, 120px) 0 var(--space-7); }
.st-key-ob_hero h1 {
  font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; color: var(--label);
  font-size: clamp(3.25rem, 6.6vw, 6rem); line-height: 1; letter-spacing: -0.012em; max-width: 13.5ch; padding: 0;
}
.st-key-ob_hero .ob-lede { font-size: 1.125rem; max-width: 30rem; }
[class*="st-key-ob_grid"] {
  display: grid !important; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  column-gap: clamp(32px, 6vw, 96px); row-gap: var(--space-5); align-items: start;
}
[class*="st-key-ob_grid"] > * { min-width: 0; width: auto !important; }
[class*="st-key-ob_grid"] > :has(> .st-key-ob_lead) { position: sticky; top: 96px; }
.st-key-ob_lead { gap: var(--space-4) !important; }
.st-key-ob_lead [data-testid="stElementContainer"]:has(h2) + [data-testid="stElementContainer"] { margin-top: 0 !important; }
/* Streamlit pulls the text after a heading up under it; at these sizes that overlaps */
.st-key-ob_lead [data-testid="stMarkdownContainer"]:has(h2), .st-key-ob_hero [data-testid="stMarkdownContainer"]:has(h1) { margin-bottom: 0 !important; }
.st-key-ob_lead h2 { font-size: clamp(2.25rem, 3.4vw, 3.125rem); line-height: 1.06; letter-spacing: -0.005em; }
.st-key-ob_body { gap: var(--space-5) !important; padding-top: 6px; }
/* Subjects: the question and the index on the left, the stage on the right */
.st-key-ob_grid_subjects { grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); grid-template-areas: "lead stage" "body stage"; }
.st-key-ob_grid_subjects > :has(> .st-key-ob_lead) { grid-area: lead; position: static; }
.st-key-ob_grid_subjects > :has(> .st-key-ob_body) { grid-area: body; }
.st-key-ob_grid_subjects > :has(> .st-key-ob_stage) { grid-area: stage; position: sticky; top: 80px; align-self: start; }
@media (max-width: 899px) {
  [class*="st-key-ob_grid"] { display: flex !important; flex-direction: column; align-items: stretch !important; }
  [class*="st-key-ob_grid"] > * { width: 100% !important; }
  [class*="st-key-ob_grid"] > :has(> .st-key-ob_lead) { position: static; }
  /* on a narrow page the stage is a band that stays at the top while the index scrolls under it */
  [class*="st-key-ob_grid"].st-key-ob_grid_subjects > :has(> .st-key-ob_stage) { position: sticky; top: 56px; z-index: 4; width: calc(100% + 32px) !important; max-width: none !important; margin: 0 -16px; }
}

/* ---------- the stage: the subject in focus, large ---------- */
.sg-stage { position: relative; height: min(76vh, 700px); min-height: 460px; overflow: hidden; border-radius: 22px; corner-shape: superellipse(1.6); isolation: isolate; }
.sg-layer { position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: flex-end;
  opacity: 0; visibility: hidden; transition: opacity var(--t-layout) var(--ease), visibility 0s linear var(--t-layout); }
.sg-art {
  position: absolute; inset: 0; background: center 30% / cover no-repeat;
  filter: grayscale(1) contrast(1.06);
  /* the picture sinks into the page: fully there above, gone below the words */
  -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 34%, transparent 76%),
                      radial-gradient(ellipse 74% 66% at 50% 34%, #000 42%, transparent 100%);
  mask-image: linear-gradient(to bottom, #000 0%, #000 34%, transparent 76%),
              radial-gradient(ellipse 74% 66% at 50% 34%, #000 42%, transparent 100%);
  -webkit-mask-composite: source-in; mask-composite: intersect;
  transform: scale(1.035); transition: transform 1100ms var(--ease);
}
:root[data-scheme="dark"] .sg-art:not(.no-art) { filter: grayscale(1) contrast(1.06) brightness(0.84); }
/* on white, a studio backdrop would read as a grey slab: the picture lifts
   toward the page and its edges fall away sooner */
:root:not([data-scheme="dark"]) .sg-art:not(.no-art) {
  filter: grayscale(1) contrast(1.04) brightness(1.1);
  -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 30%, transparent 72%),
                      radial-gradient(ellipse 62% 58% at 50% 34%, #000 30%, transparent 100%);
  mask-image: linear-gradient(to bottom, #000 0%, #000 30%, transparent 72%),
              radial-gradient(ellipse 62% 58% at 50% 34%, #000 30%, transparent 100%);
}
/* no picture yet: the subject's number, large and faint, stands in its place */
.sg-art.no-art { -webkit-mask-image: none; mask-image: none; display: flex; align-items: flex-start; justify-content: flex-end; padding: 8px 24px 0 0; }
.sg-art.no-art::before { content: attr(data-n); font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300;
  font-size: clamp(9rem, 17vw, 15rem); line-height: 1; color: light-dark(rgba(0, 0, 0, 0.06), rgba(255, 255, 255, 0.07)); font-variant-numeric: lining-nums; }
.sg-copy { position: relative; display: grid; gap: 6px; padding: 0 clamp(20px, 3vw, 36px) clamp(20px, 3vw, 32px); }
.sg-copy p { margin: 0; }
.sg-kicker { font-size: 0.6875rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--label-2); font-variant-numeric: tabular-nums; }
/* the words over the picture keep a breath of the page's own colour around them */
.sg-kicker, .sg-title, .sg-desc { text-shadow: 0 0 18px var(--env), 0 0 2px var(--env); }
.sg-title { font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300; color: var(--label);
  font-size: clamp(2.75rem, 5vw, 4.5rem); line-height: 1; letter-spacing: -0.01em; margin-top: 4px !important; }
.sg-desc { font-size: 1.0625rem; line-height: 1.5; color: var(--label-2); max-width: 30rem; margin-top: 6px !important; }
.sg-meta { font-size: 0.75rem; color: var(--label-3); }
.sg-state { margin-top: 10px !important; font-size: 0.8125rem; color: var(--label-2); display: flex; align-items: center; gap: 8px; }
.sg-state[data-on="1"] { color: var(--label); }
.sg-state[data-on="1"]::before { content: ""; width: 5px; height: 10px; margin: -3px 3px 0 2px; border: solid var(--label); border-width: 0 1.5px 1.5px 0; transform: rotate(45deg); }
.sg-credit { font-size: 0.6875rem; color: var(--label-3); margin-top: 6px !important; }
/* the subject in focus: its layer comes up, its picture settles */
.sg-stage[data-focus="philosophy"] .sg-layer[data-t="philosophy"],
.sg-stage[data-focus="cosmos"] .sg-layer[data-t="cosmos"],
.sg-stage[data-focus="investing"] .sg-layer[data-t="investing"],
.sg-stage[data-focus="business"] .sg-layer[data-t="business"],
.sg-stage[data-focus="fashion"] .sg-layer[data-t="fashion"],
.sg-stage[data-focus="jewelry"] .sg-layer[data-t="jewelry"],
.sg-stage[data-focus="free"] .sg-layer[data-t="free"] {
  opacity: 1; visibility: visible; transition: opacity var(--t-layout) var(--ease), visibility 0s;
}
.sg-stage[data-focus="philosophy"] .sg-layer[data-t="philosophy"] .sg-art,
.sg-stage[data-focus="cosmos"] .sg-layer[data-t="cosmos"] .sg-art,
.sg-stage[data-focus="investing"] .sg-layer[data-t="investing"] .sg-art,
.sg-stage[data-focus="business"] .sg-layer[data-t="business"] .sg-art,
.sg-stage[data-focus="fashion"] .sg-layer[data-t="fashion"] .sg-art,
.sg-stage[data-focus="jewelry"] .sg-layer[data-t="jewelry"] .sg-art,
.sg-stage[data-focus="free"] .sg-layer[data-t="free"] .sg-art { transform: none; }
/* before the page has marked a focus, the first subject shows */
.sg-stage:not([data-focus]) .sg-layer:first-child { opacity: 1; visibility: visible; }
@media (max-width: 899px) {
  .sg-stage { height: 232px; min-height: 0; border-radius: 0; background: var(--env); }
  .sg-art { -webkit-mask-image: linear-gradient(to bottom, #000 20%, transparent 100%); mask-image: linear-gradient(to bottom, #000 20%, transparent 100%); }
  .sg-copy { padding: 0 16px 14px; gap: 2px; }
  .sg-title { font-size: 2.5rem; }
  .sg-desc, .sg-meta, .sg-credit { display: none; }
  .sg-state { margin-top: 4px !important; }
  .sg-art.no-art::before { font-size: 7.5rem; }
}

/* ---------- moving between steps: the step leaves toward where she came from ---------- */
[class*="st-key-ob_step_"][data-leaving] { transition: opacity 200ms var(--ease), transform 260ms var(--ease); pointer-events: none; }
[class*="st-key-ob_step_"][data-leaving="fwd"] { opacity: 0; transform: translateX(-20px); }
[class*="st-key-ob_step_"][data-leaving="back"] { opacity: 0; transform: translateX(20px); }

/* ---------- Settings: the same index and lens, a size smaller ---------- */
[class*="st-key-set_sec_"] .opt-index .opt-t { font-size: 1.25rem; }
[class*="st-key-set_sec_"] .opt-index { padding: 14px 14px 14px 12px; }

@media (prefers-reduced-motion: reduce) {
  .sg-layer, .sg-art, [class*="st-key-ob_step_"][data-leaving] { transition: none !important; }
  .sg-art { transform: none; }
}
</style>
"""

WORLDS = """
<style>
/* ==========================================================================
   A SUBJECT'S WORLD: one system, a room per subject
   The object that stands for the subject, its name set large, and below,
   quietly, where she is in it. Only the object, its composition and the
   title's setting change from one subject to the next (visuals.WORLD).
   ========================================================================== */
.stMainBlockContainer:has(#world-page) { max-width: 1180px; }
[class*="st-key-world_"] {
  display: grid !important; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
  column-gap: clamp(24px, 5vw, 80px); align-items: end; min-height: min(76vh, 740px);
}
[class*="st-key-world_"] > * { min-width: 0; width: auto !important; }
.st-key-w_copy { gap: var(--space-5) !important; padding-bottom: clamp(8px, 4vh, 40px); position: relative; z-index: 2; }
.w-copy p { margin: 0; }
.w-kicker { font-size: 0.6875rem; letter-spacing: 0.16em; text-transform: uppercase; color: var(--label-2); font-variant-numeric: tabular-nums; }
.stApp .w-title {
  margin: 14px 0 0; padding: 0; color: var(--label); font-family: "Newsreader", "Noto Serif TC", serif; font-weight: 300;
  font-size: clamp(3.5rem, 8vw, 7.25rem); line-height: 0.95; letter-spacing: -0.02em;
}
/* a subject about precision: its name in fine, spaced capitals */
.stApp .w-title-tracked .w-title {
  font-family: "Inter", "Noto Sans TC", sans-serif; font-weight: 300; text-transform: uppercase;
  font-size: clamp(1.75rem, 3.6vw, 3rem); letter-spacing: 0.3em; line-height: 1.25;
}
.w-about { margin-top: 22px !important; font-size: 1.1875rem; line-height: 1.5; color: var(--label-2); max-width: 27rem; }
.w-meta { margin-top: 12px !important; font-size: 0.75rem; color: var(--label-3); }
.st-key-w_actions { gap: var(--space-5) !important; flex-wrap: wrap; justify-content: flex-start !important; }
.st-key-w_actions > * { flex: 0 0 auto !important; width: auto !important; }
.st-key-w_actions .stButton button[kind="tertiary"] { color: var(--label-2); background: transparent !important; border-color: transparent !important; box-shadow: none !important; backdrop-filter: none !important; padding: 0 var(--space-2); }
.w-next { margin: 0; font-size: 0.875rem; color: var(--label-2); }

/* the object */
.st-key-w_object { position: relative; align-self: stretch; gap: 0 !important; }
.w-object {
  position: relative; height: min(76vh, 740px); background: center / cover no-repeat; transform-origin: center;
  filter: grayscale(1) contrast(1.06); border-radius: 22px; corner-shape: superellipse(1.6);
  -webkit-mask-image: linear-gradient(to left, #000 55%, transparent 100%), linear-gradient(to bottom, #000 58%, transparent 100%);
  mask-image: linear-gradient(to left, #000 55%, transparent 100%), linear-gradient(to bottom, #000 58%, transparent 100%);
  -webkit-mask-composite: source-in; mask-composite: intersect;
}
:root[data-scheme="dark"] .w-object:not(.is-drawn):not(.no-art) { filter: grayscale(1) contrast(1.06) brightness(0.84); }
:root:not([data-scheme="dark"]) .w-object:not(.is-drawn):not(.no-art) { filter: grayscale(1) contrast(1.04) brightness(1.08); }
/* the work's credit: small, at the object's upper corner, out of the words' way */
.w-credit { position: absolute; right: 14px; top: 12px; margin: 0; font-size: 0.6875rem; line-height: 1.4; color: var(--label-2);
  text-align: right; max-width: min(60%, 26rem); text-shadow: 0 0 10px var(--env), 0 0 2px var(--env); z-index: 1; }
.w-object.no-art { -webkit-mask-image: none; mask-image: none; display: flex; align-items: flex-start; justify-content: flex-end; }
.w-object.no-art::before { content: attr(data-n); font-family: "Newsreader", serif; font-weight: 300; font-size: clamp(10rem, 22vw, 20rem); line-height: 1;
  color: light-dark(rgba(0, 0, 0, 0.06), rgba(255, 255, 255, 0.07)); }
/* an instrument: held whole in the middle of its space, its edges falling away */
.st-key-world_instrument .w-object { background-size: contain;
  -webkit-mask-image: radial-gradient(ellipse 58% 60% at 50% 48%, #000 45%, transparent 100%); mask-image: radial-gradient(ellipse 58% 60% at 50% 48%, #000 45%, transparent 100%); }
/* a painting: a scene laid wide above, the name set where it fades */
.st-key-world_painting { grid-template-columns: minmax(0, 1fr); min-height: 0; }
.st-key-world_painting > :has(> .st-key-w_object) { grid-row: 1; }
.st-key-world_painting > :has(> .st-key-w_copy) { grid-row: 2; margin-top: clamp(-200px, -16vh, -80px); }
.st-key-world_painting .w-object { height: min(58vh, 560px);
  -webkit-mask-image: linear-gradient(to bottom, #000 40%, transparent 100%), radial-gradient(ellipse 80% 90% at 50% 40%, #000 55%, transparent 100%);
  mask-image: linear-gradient(to bottom, #000 40%, transparent 100%), radial-gradient(ellipse 80% 90% at 50% 40%, #000 55%, transparent 100%); }

/* a pendant: hung from the top of the page, the stone in the open space */
/* a drawn object: a picture in the theme's own ink, hung from the top */
.is-drawn { background: var(--ink-light) top center / contain no-repeat !important; }
:root[data-scheme="dark"] .is-drawn { background-image: var(--ink-dark) !important; }
.w-object.is-drawn { -webkit-mask-image: none; mask-image: none; filter: none; border-radius: 0; }
/* the chain starts at the header's lower edge (the page's top space is 96px, the header 56px) */
.st-key-world_pendant .w-object { height: calc(min(76vh, 740px) + 40px); margin-top: -40px; }

/* arriving: the object is carried in (motion.py); the words follow it, one after another */
@keyframes w-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.w-kicker { animation: w-rise var(--t-space) var(--ease) 180ms backwards; }
.stApp .w-title { animation: w-rise var(--t-layout) var(--ease) 260ms backwards; }
.w-about { animation: w-rise var(--t-space) var(--ease) 420ms backwards; }
.w-meta { animation: w-rise var(--t-space) var(--ease) 500ms backwards; }
.st-key-w_actions { animation: w-rise var(--t-space) var(--ease) 580ms backwards; }

/* ---------- below: where she is, what's next, lately ---------- */
[class*="st-key-w_sec_"] {
  display: grid !important; grid-template-columns: 10rem minmax(0, 1fr); column-gap: var(--space-6); align-items: start;
  padding-top: var(--space-5); border-top: 0.5px solid var(--field-edge); gap: var(--space-4) !important;
}
[class*="st-key-w_sec_"] > * { width: auto !important; min-width: 0; }
.st-key-w_sec_where { margin-top: var(--space-7); }
.w-sec-title { margin: 0; font-family: "Newsreader", serif; font-weight: 300; font-size: 1.375rem; line-height: 1.2; color: var(--label); }
.w-sec-body { display: grid; gap: 10px; }
.w-sec-body p { margin: 0; }
.w-big { font-family: "Newsreader", serif; font-weight: 300; font-size: 1.75rem; line-height: 1.15; color: var(--label); }
.w-small { font-size: 0.8125rem; color: var(--label-2); }
.w-line { position: relative; height: 2px; border-radius: 2px; background: var(--field-edge); overflow: hidden; max-width: 28rem; }
.w-line i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--label); border-radius: 2px; }
.w-list { list-style: none; margin: 0; padding: 0; display: grid; }
.w-list li { display: grid; grid-template-columns: 3rem minmax(0, 1fr) auto; gap: var(--space-3); padding: 10px 0; border-bottom: 0.5px solid var(--hair); font-size: 0.9375rem; color: var(--label); }
.w-list li:last-child { border-bottom: none; }
.w-list .n, .w-list .d { color: var(--label-3); font-size: 0.8125rem; font-variant-numeric: tabular-nums; padding-top: 2px; }
/* her other subjects: each its own room, entered by its object */
.st-key-w_others { gap: var(--space-5) !important; flex-wrap: wrap; justify-content: flex-start !important; }
.st-key-w_others > * { flex: 0 0 auto !important; width: auto !important; }
.st-key-w_others [class*="st-key-enter_"] { position: relative; width: 168px !important; flex: 0 0 168px !important; gap: 8px !important; }
.w-thumb { height: 112px; border-radius: 14px; corner-shape: superellipse(1.6); background: center / cover no-repeat;
  filter: grayscale(1) contrast(1.04); transition: transform var(--t-state) var(--ease); }
:root[data-scheme="dark"] .w-thumb:not(.is-drawn) { filter: grayscale(1) contrast(1.04) brightness(0.84); }
.w-thumb.is-drawn { background-color: var(--wash) !important; background-size: auto 130% !important; background-position: center 80% !important; filter: none; }
.w-thumb.no-art { background: var(--wash); }
.w-thumb-name { margin: 0; font-family: "Newsreader", serif; font-weight: 300; font-size: 1.125rem; color: var(--label); }
.st-key-w_others [class*="st-key-enter_"] [data-testid="stElementContainer"]:has(.w-thumb) { pointer-events: none; }
.st-key-w_others [class*="st-key-enter_"] [data-testid="stElementContainer"]:has(.stButton),
.st-key-w_others [class*="st-key-enter_"] [data-testid="stElementContainer"]:has(.stButton) *:not(button) { position: static !important; }
.st-key-w_others [class*="st-key-enter_"] .stButton button { position: absolute !important; inset: 0; width: 100%; height: 100%; opacity: 0; z-index: 2; }
@media (hover: hover) { .st-key-w_others [class*="st-key-enter_"]:hover .w-thumb { transform: scale(1.02); } }
.st-key-w_others [class*="st-key-enter_"]:has(button:focus-visible) { outline: 1px solid var(--outline); outline-offset: 4px; border-radius: 14px; }

/* the ways in, elsewhere: quiet words with an arrow */
[class*="st-key-enter_"] .stButton button[kind="tertiary"] { color: var(--label-2); background: transparent !important; border-color: transparent !important;
  box-shadow: none !important; backdrop-filter: none !important; padding: 0 2px; min-height: 36px; }
@media (hover: hover) { [class*="st-key-enter_"] .stButton button[kind="tertiary"]:hover { color: var(--label); } }
.st-key-set_worlds { gap: var(--space-4) !important; flex-wrap: wrap; }

/* ---------- the drawn necklace wherever it appears ---------- */
.sg-art.is-drawn { -webkit-mask-image: none; mask-image: none; filter: none; transform: none !important; background-size: auto 72% !important; }
.ob-objs { display: flex; gap: 8px; margin-bottom: 8px; }
.ob-obj { width: 40px; height: 52px; border-radius: 8px; background: center / cover no-repeat; filter: grayscale(1); flex: none; }
.ob-obj.is-drawn { background-color: var(--wash) !important; background-size: auto 140% !important; background-position: center 90% !important; filter: none; }
.ob-obj.no-art { background: var(--wash); }

@media (max-width: 899px) {
  [class*="st-key-world_"] { display: flex !important; flex-direction: column-reverse; min-height: 0; align-items: stretch !important; }
  .st-key-world_painting { flex-direction: column; }
  [class*="st-key-world_"] > * { width: 100% !important; }
  .st-key-world_painting > :has(> .st-key-w_copy) { margin-top: -12vh; }
  .w-object { height: 46vh; border-radius: 0; margin: 0 -16px; width: calc(100% + 32px); }
  .st-key-world_pendant .w-object { height: calc(46vh + 32px); margin-top: -32px; }
  .st-key-w_copy { margin-top: -10vh; }
  .st-key-world_painting .st-key-w_copy { margin-top: 0; }
  .w-credit { right: 16px; top: 10px; }
  [class*="st-key-w_sec_"] { display: flex !important; flex-direction: column; }
  .sg-art.is-drawn { background-size: auto 100% !important; background-position: 88% top !important; }
}
@media (prefers-reduced-motion: reduce) {
  .w-kicker, .stApp .w-title, .w-about, .w-meta, .st-key-w_actions { animation: none; }
}
</style>
"""

def stylesheet() -> str:
    rest = "".join(part.replace("<style>", "").replace("</style>", "") for part in (LIQUID, PROGRESS, BOOKS, NAV, SETUP, LENS, WORLDS, TOUCH))
    return CSS.replace("</style>", rest + "</style>")


def inject():
    st.html(stylesheet())
    st.html(glass.script(), unsafe_allow_javascript=True)      # the refraction filter the glass uses
    st.html(motion.script(), unsafe_allow_javascript=True)     # connected controls: one surface travelling between items
