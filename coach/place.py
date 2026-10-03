"""Remembering where she scrolled to in each lesson, so "Jump to current
progress" takes her back to that spot instead of just the quiz heading.

The place is kept in the browser (localStorage), per lesson, as the lesson
card or anchor at the top of the screen plus how far past it she was, so it
still lands right if the page above it changes height. Only scrolling she
does herself is saved: the page opening at the top, a lesson switch or a
jump never overwrites it.
"""

from html import escape

# The page script: installed once per browser tab, it keeps working across
# reruns and reads the lesson it is saving for from the marker div below,
# so nothing is saved while another page is open.
_SCRIPT = """<script>
(function () {
  const w = window.parent, doc = w.document, TOP = 96;
  const marker = () => doc.getElementById("coach-place");
  const get = (k) => { try { return JSON.parse(w.localStorage.getItem("coach-place:" + k)); } catch (e) { return null; } };
  const put = (k, v) => { try { w.localStorage.setItem("coach-place:" + k, JSON.stringify(v)); } catch (e) {} };
  const scroller = () => {
    for (let e = doc.getElementById("coach-place"); e; e = e.parentElement) {
      const o = getComputedStyle(e).overflowY;
      if ((o === "auto" || o === "scroll") && e.scrollHeight > e.clientHeight) return e;
    }
    return doc.scrollingElement;
  };
  const landmarks = () => [...doc.querySelectorAll('.jump-anchor, [class*="st-key-lcard_"]')];
  const name = (e) => e.id ? "#" + e.id : "." + [...e.classList].find((c) => c.startsWith("st-key-lcard_"));

  const s = w.__coachPlace || (w.__coachPlace = { input: 0, quiet: 0, marker: null, timer: 0 });
  s.restore = (key) => {
    const p = key && get(key), box = scroller();
    if (!p || !box) return false;
    const e = p.sel && doc.querySelector(p.sel);
    if (e) box.scrollBy({ top: e.getBoundingClientRect().top - TOP + p.d, behavior: "smooth" });
    else box.scrollTo({ top: p.top, behavior: "smooth" });
    return true;
  };
  if (!s.installed) {
    s.installed = true;
    const user = () => { s.input = Date.now(); };
    ["wheel", "touchmove", "keydown"].forEach((t) => doc.addEventListener(t, user, { capture: true, passive: true }));
    doc.addEventListener("pointerdown", (e) => { if (e.target === scroller()) user(); }, true);   // the scrollbar
    doc.addEventListener("scroll", () => {
      clearTimeout(s.timer);
      s.timer = setTimeout(() => {
        const m = marker(), now = Date.now();
        if (!m || now - s.input > 2500 || now < s.quiet) return;
        const box = scroller(), past = landmarks().filter((e) => e.getBoundingClientRect().top <= TOP + 1).pop();
        put(m.dataset.key, past ? { sel: name(past), d: TOP - past.getBoundingClientRect().top }
                                : { top: box.scrollTop });
      }, 150);
    }, true);
  }
  const m = marker();
  if (m && m !== s.marker) { s.marker = m; s.quiet = Date.now() + 1000; }   // the page just (re)drew

  // After the button: wait until that lesson is drawn and the page stops
  // growing, then go to her place in it (or its anchor).
  if (m && m.dataset.jump) {
    const want = m.dataset.want;
    let last = "", calm = 0, tries = 0;
    const tick = () => {
      const top = m.dataset.jump === "top", a = top ? doc.body : doc.getElementById(m.dataset.jump);
      const h = [...doc.querySelectorAll("h3")].some((x) => x.innerText.startsWith(want));
      const now = a && h ? a.getBoundingClientRect().top + ":" + doc.body.scrollHeight : "";
      calm = now && now === last ? calm + 1 : 0; last = now;
      if (calm >= 3) {
        if (top) scroller().scrollTo({ top: 0, behavior: "smooth" });
        else if (m.dataset.restore === "0" || !s.restore(m.dataset.key)) a.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      else if (++tries < 60) setTimeout(tick, 100);
    };
    tick();
  }
})();
</script>"""


def html(key, jump="", want="", n=0, restore=True):
    """The marker for the lesson on screen, plus the script. `jump` is the
    anchor to fall back on and `want` the lesson heading to wait for, both
    set only right after the button was pressed; `n` counts presses, so a
    second press on the same lesson still redraws (and reruns) the script.
    With restore=False it goes straight to `jump` (her newest question)
    instead of the place she had scrolled to."""
    return (f'<div id="coach-place" hidden data-key="{escape(key)}" data-jump="{escape(jump)}" '
            f'data-want="{escape(want)}" data-n="{n}" data-restore="{int(restore)}"></div>' + _SCRIPT)


LATEST = "latest-question"


def latest_anchor():
    """Marks her newest question, which the page goes to after a reply."""
    return f'<div class="jump-anchor" id="{LATEST}"></div>'


def follow(n=0):
    """While a reply is being written: an anchor where her question starts,
    and a script that takes the page there, so she sees the answer arrive
    right under it. `n` makes each one new, so the script runs every time."""
    return f"""<div class="jump-anchor" id="reply-start-{n}"></div><script>
    (function go(tries) {{
      const a = window.parent.document.getElementById("reply-start-{n}");
      if (a) a.scrollIntoView({{behavior: "smooth", block: "start"}});
      else if (tries > 0) setTimeout(() => go(tries - 1), 50);
    }})(40);
    </script>"""


# Keeping controls clear of the chat box. The box floats at the bottom of
# the screen; when a redraw puts a new control or message right where it
# floats (Retry after a failed quiz, the next button, an error), the page
# moves up just enough to show it. Only new elements count, so it never
# fights her own scrolling. A field or button that gets focus under the box
# (Tab, or a tap that opens the on-screen keyboard) is brought up the same way.
# (Not CSS scroll-padding: it made the selectboxes' option lists jump.)
_KEEP_CLEAR = """<div id="keep-clear-hook" hidden></div><script>
(function () {
  const w = window.parent, doc = w.document;
  if (w.__coachKeepClear) return;
  w.__coachKeepClear = true;
  const WANT = 'button, textarea, input, [data-testid="stAlert"], [data-testid="stAlertContainer"]';
  const scroller = (from) => {
    for (let e = from; e; e = e.parentElement) {
      const o = getComputedStyle(e).overflowY;
      if ((o === "auto" || o === "scroll") && e.scrollHeight > e.clientHeight) return e;
    }
    return doc.scrollingElement;
  };
  let fresh = [], timer = 0;
  const settle = () => {
    timer = 0;
    const dock = doc.querySelector(".st-key-chat_dock");
    const items = fresh.filter((e) => e.isConnected); fresh = [];
    if (!dock || !items.length) return;
    const d = dock.getBoundingClientRect();
    let need = 0, top = Infinity;
    for (const e of items) {
      // only the page's own content: never a dropdown, popover or dialog opened over it
      if (dock.contains(e) || !e.closest('[data-testid="stMain"]')
          || e.closest('[role="dialog"], [role="listbox"], [data-baseweb="popover"], [data-testid="stPopoverBody"]')) continue;
      const r = e.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || r.top > d.bottom || r.bottom < d.top - 2) continue;
      need = Math.max(need, r.bottom - d.top + 16);
      top = Math.min(top, r.top);
    }
    if (need > 0 && top - need > 64) scroller(dock).scrollBy({ top: need, behavior: "smooth" });
  };
  // a field or button focused under the box (Tab; a tap that opens the on-screen keyboard)
  doc.addEventListener("focusin", (ev) => {
    const t = ev.target;
    if (t && t.matches && t.matches(WANT)) { fresh.push(t); if (!timer) timer = w.setTimeout(settle, 250); }
  }, true);
  new w.MutationObserver((list) => {
    for (const m of list) for (const n of m.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.matches && n.matches(WANT)) fresh.push(n);
      if (n.querySelectorAll) fresh.push(...n.querySelectorAll(WANT));
    }
    if (fresh.length && !timer) timer = w.setTimeout(settle, 150);
    queueFit();
  }).observe(doc.body, { childList: true, subtree: true });
  // the chat box's band: its column (from its empty slot in the page), its
  // height and the keyboard's, which the page's scrolling area leaves free
  const root = doc.documentElement;
  let fitting = 0, sized = null;
  const fit = () => {
    fitting = 0;
    // the side panel's toggles only show an icon's name ("keyboard_double_arrow_right"): say what they do
    for (const [sel, name] of [['[data-testid="stExpandSidebarButton"]', "Open the side panel"],
                               ['[data-testid="stSidebarCollapseButton"] button', "Close the side panel"],
                               [".st-key-account_menu button", "Your account"]]) {
      const b = doc.querySelector(sel);
      if (b && b.getAttribute("aria-label") !== name) b.setAttribute("aria-label", name);
    }
    // cards due: a dot on Review in the bar (the number is for screen readers)
    const due = doc.getElementById("review-due");
    const link = [...doc.querySelectorAll('.st-key-topnav [data-testid="stPageLink-NavLink"]')]
      .find((a) => ["/review", "/review/"].includes(new URL(a.getAttribute("href") || "/", w.location.href).pathname));
    if (link) {
      const n = due ? +due.dataset.n : 0;
      if (n > 0 && link.dataset.due !== String(n)) { link.dataset.due = String(n); link.setAttribute("aria-label", `Review, ${n} due`); }
      if (!n && link.dataset.due) { delete link.dataset.due; link.removeAttribute("aria-label"); }
    }
    const dock = doc.querySelector(".st-key-chat_dock");
    if (!dock) { ["--dock-h", "--kb"].forEach((v) => root.style.removeProperty(v)); return; }
    const slot = dock.parentElement.getBoundingClientRect();
    const vv = w.visualViewport;
    const kb = vv ? Math.max(0, Math.round(w.innerHeight - vv.height - vv.offsetTop)) : 0;
    dock.style.setProperty("--dock-left", `${Math.round(slot.left)}px`);
    dock.style.setProperty("--dock-width", `${Math.round(slot.width)}px`);
    root.style.setProperty("--dock-h", `${Math.ceil(dock.getBoundingClientRect().height)}px`);
    root.style.setProperty("--kb", `${kb}px`);
    if (sized !== dock) {               // a new box (another page): follow its size as she types
      sized = dock;
      new w.ResizeObserver(queueFit).observe(dock);
      new w.ResizeObserver(queueFit).observe(dock.parentElement.parentElement);
    }
  };
  function queueFit() { if (!fitting) fitting = w.requestAnimationFrame(fit); }
  w.addEventListener("resize", queueFit);
  if (w.visualViewport) { w.visualViewport.addEventListener("resize", queueFit); w.visualViewport.addEventListener("scroll", queueFit); }
  queueFit();
})();
</script>"""


def keep_clear() -> str:
    return _KEEP_CLEAR
