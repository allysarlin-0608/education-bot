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
    for (let e = doc.getElementById("current-lesson"); e; e = e.parentElement) {
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
      const a = doc.getElementById(m.dataset.jump);
      const h = [...doc.querySelectorAll("h3")].some((x) => x.innerText.startsWith(want));
      const now = a && h ? a.getBoundingClientRect().top + ":" + doc.body.scrollHeight : "";
      calm = now && now === last ? calm + 1 : 0; last = now;
      if (calm >= 3) { if (!s.restore(m.dataset.key)) a.scrollIntoView({ behavior: "smooth", block: "start" }); }
      else if (++tries < 60) setTimeout(tick, 100);
    };
    tick();
  }
})();
</script>"""


def html(key, jump="", want="", n=0):
    """The marker for the lesson on screen, plus the script. `jump` is the
    anchor to fall back on and `want` the lesson heading to wait for, both
    set only right after the button was pressed; `n` counts presses, so a
    second press on the same lesson still redraws (and reruns) the script."""
    return (f'<div id="coach-place" hidden data-key="{escape(key)}" data-jump="{escape(jump)}" '
            f'data-want="{escape(want)}" data-n="{n}"></div>' + _SCRIPT)
