"""Connected controls: one active surface that travels between the items
of a control instead of each item lighting up on its own.

Used by the page navigation at the top (Today, Reading, Progress) and by
the switch on Progress (Day, Sessions, Subjects). For each control the
script finds which item is on from the page itself (the page's address
for the navigation, aria-checked for the switch), so there is one source
of truth, and draws one surface under it:

- tapping an item starts the surface moving at once, before the page has
  redrawn; its width follows the item; a longer way takes a little longer;
- the item's text changes with it, on the same clock;
- moving between pages, the page's content quietens as the surface leaves
  and the new page comes in as it arrives (style.py);
- on a touch screen, a clearly sideways swipe across the page moves the
  surface with the finger toward the next or previous page, and lets go
  into it (or back) when the finger lifts. Vertical scrolling, sideways
  scrolling areas, fields and the screen edges are left alone.

Kept apart from glass.py: this is interaction, that is material. The
script has no "<" in it (Streamlit drops a script that looks like it
holds a tag)."""

SCRIPT = r"""
(function () {
  const w = window.parent, doc = w.document;
  if (w.__cxControls) return; w.__cxControls = true;
  const reduced = () => w.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const strip = (p) => p.replace(/\/+$/, '') || '/';
  const here = () => strip(w.location.pathname);
  const pathOf = (a) => strip(new URL(a.getAttribute('href'), w.location.href).pathname);
  const CONTROLS = [
    // the pages: a thin line on the header's lower edge, under the words of
    // the page that is on (it travels, and takes each word's width)
    { root: '.st-key-topnav_items', item: '[data-testid="stPageLink-NavLink"]', pages: true, target: 'p', cls: 'cx-line',
      shape: (b, r) => ({ x: b.x - 2, y: r.h - 1.5, w: b.w + 4, h: 1.5 }),
      on: (items) => items.find((a) => a.getAttribute('href') && pathOf(a) === here()) || items.find((a) => !a.getAttribute('href')) },
    { root: '.st-key-prog_view [data-testid="stButtonGroup"] > div', item: 'button',
      on: (items) => items.find((b) => b.getAttribute('aria-checked') === 'true') },
    // Today's lessons: the short mark under the lesson open travels to the
    // next one opened (it moves once the page has opened it: a locked lesson
    // only says so, so it must not set off on the tap)
    { root: '[class*="st-key-lesson_steps"]', item: '[class*="st-key-step_"] button', wait: true, cls: 'cx-mark',
      shape: (b) => ({ x: b.x + b.w / 2 - 6, y: b.y + 40, w: 12, h: 1 }),
      on: (items) => items.find((x) => x.closest('[class*="st-key-step_"]').className.includes('_viewing')) },
  ];
  const state = new WeakMap();

  function box(root, el, c) {
    const r = root.getBoundingClientRect();
    const t = c && c.target ? el.querySelector(c.target) || el : el;
    const e = t.getBoundingClientRect();
    const b = { x: e.left - r.left, y: e.top - r.top, w: e.width, h: e.height };
    return c && c.shape ? c.shape(b, { w: r.width, h: r.height }) : b;
  }
  function pill(root, c) {
    let p = root.querySelector(':scope > .cx-pill');
    if (!p) { p = doc.createElement('span'); p.className = 'cx-pill' + (c && c.cls ? ' ' + c.cls : ''); p.setAttribute('aria-hidden', 'true'); root.appendChild(p); }
    return p;
  }
  function mark(items, on) { items.forEach((i) => { if (i === on) i.setAttribute('data-cx-on', ''); else i.removeAttribute('data-cx-on'); }); }
  function draw(root, b, ms) {
    const p = pill(root, (state.get(root) || {}).c);
    p.style.opacity = '';
    p.style.transition = ms ? 'transform ' + ms + 'ms var(--ease-nav), width ' + ms + 'ms var(--ease-nav), height ' + ms + 'ms var(--ease-nav)' : 'none';
    p.style.width = b.w + 'px'; p.style.height = b.h + 'px';
    p.style.transform = 'translate(' + b.x + 'px, ' + b.y + 'px)';
    root.style.setProperty('--cx-dur', (ms || 1) + 'ms');
  }
  // move the surface to `to`: the time grows a little with the distance
  function go(root, items, to, animate, c) {
    const s = state.get(root) || {};
    if (c) s.c = c;
    state.set(root, s);
    const b = box(root, to, s.c);
    let ms = 0;
    if (animate && s.b) ms = reduced() ? 0 : Math.round(Math.min(560, Math.max(300, 280 + Math.abs(b.x - s.b.x) * 0.9)));
    if (ms === 0 && animate && reduced()) pill(root).animate([{ opacity: 0.4 }, { opacity: 1 }], { duration: 160 });
    draw(root, b, ms);
    mark(items, to);
    root.setAttribute('data-cx', '');
    state.set(root, Object.assign(s, { b: b, on: to }));
    if (s.c) s.c.last = { b: b, at: performance.now() };
  }

  // keep every control's surface on its item (the truth), unless a tap has
  // just sent it somewhere the page hasn't caught up with yet
  function sync() {
    for (const c of CONTROLS) {
      doc.querySelectorAll(c.root).forEach((root) => {
        const items = [...root.querySelectorAll(c.item)];
        const on = items.length && c.on(items);
        if (!on) { const p = root.querySelector(':scope > .cx-pill'); if (p) p.style.opacity = '0'; return; }   // nothing on: the surface bows out
        const s = state.get(root) || {};
        // the page redrew the control as a new element (a key changed): if
        // that happened just now, the surface carries on from where it was
        if (!s.b && c.last && performance.now() - c.last.at > 0 && 2000 > performance.now() - c.last.at) {
          s.c = c; s.b = c.last.b; state.set(root, s); draw(root, s.b, 0); root.getBoundingClientRect();
        }
        if (s.pending && performance.now() - s.pendingAt > 3000) s.pending = null;
        if (s.pending && s.pending !== on) return;
        s.pending = null; state.set(root, s);
        const b = box(root, on, c);
        const p = root.querySelector(':scope > .cx-pill');
        if (s.on !== on || !s.b || Math.abs(b.x - s.b.x) + Math.abs(b.w - s.b.w) > 0.5 || !p || p.style.opacity === '0') go(root, items, on, !!s.b && (s.on !== on || Math.abs(b.x - s.b.x) > 0.5), c);
      });
    }
    // a new page has come in (Streamlit has redrawn: its stale marks have
    // come and gone): let the content settle back
    if (doc.documentElement.hasAttribute('data-cx-leaving')) {
      const stale = !!doc.querySelector('[data-testid="stMain"] [data-stale="true"]');
      if (stale) sawStale = true;
      if ((sawStale && !stale && here() !== leftFrom) || performance.now() - leftAt > 1500) doc.documentElement.removeAttribute('data-cx-leaving');
    }
  }
  let queued = false, leftFrom = null, leftAt = 0, sawStale = false;
  const soon = () => { if (!queued) { queued = true; w.requestAnimationFrame(() => { queued = false; sync(); }); } };
  new w.MutationObserver(soon).observe(doc.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['aria-checked', 'href', 'data-stale'] });
  w.addEventListener('resize', () => { for (const c of CONTROLS) doc.querySelectorAll(c.root).forEach((r) => { const s = state.get(r); if (s && s.on) { s.b = null; state.set(r, s); } }); soon(); });
  w.setInterval(soon, 500);

  // a tap: the surface sets off at once; for a page, the content begins to quieten
  function send(root, items, to) {
    const s = state.get(root) || {};
    if (s.on === to) return;
    go(root, items, to, true);
    s.pending = to; s.pendingAt = performance.now(); state.set(root, s);
  }
  doc.addEventListener('click', (ev) => {
    for (const c of CONTROLS) {
      if (c.wait) continue;
      const to = ev.target.closest && ev.target.closest(c.root + ' ' + c.item);
      if (!to) continue;
      const root = to.closest(c.root);
      const items = [...root.querySelectorAll(c.item)];
      const was = (state.get(root) || {}).on;
      send(root, items, to);
      if (c.pages && was && was !== to) {
        leftFrom = here(); leftAt = performance.now(); sawStale = false;
        doc.documentElement.setAttribute('data-cx-leaving', '');
      }
    }
  }, true);

  // a clearly sideways swipe across the page, on a touch screen, moves between pages
  let sw = null;
  const sideways = (el) => {
    for (let e = el; e && e !== doc.body; e = e.parentElement) {
      const cs = w.getComputedStyle(e);
      if (/(auto|scroll)/.test(cs.overflowX) && e.scrollWidth > e.clientWidth + 2) return true;
    }
    return false;
  };
  doc.addEventListener('touchstart', (ev) => {
    sw = null;
    if (ev.touches.length !== 1) return;
    const t = ev.touches[0], tg = ev.target;
    if (!tg.closest || !tg.closest('[data-testid="stMain"]')) return;
    if (tg.closest('input, textarea, select, [role="tablist"], [role="slider"], [role="dialog"], [data-baseweb], .st-key-topnav, [data-testid="stChatInput"]')) return;
    if (24 > t.clientX || t.clientX > w.innerWidth - 24 || sideways(tg)) return;
    const root = doc.querySelector(CONTROLS[0].root);
    if (!root || !(state.get(root) || {}).on) return;
    sw = { x: t.clientX, y: t.clientY, root: root, mode: null, p: 0, to: null };
  }, { passive: true });
  doc.addEventListener('touchmove', (ev) => {
    if (!sw) return;
    const t = ev.touches[0], dx = t.clientX - sw.x, dy = t.clientY - sw.y;
    if (!sw.mode) {
      if (Math.abs(dy) > 10 && Math.abs(dy) >= Math.abs(dx)) { sw = null; return; }
      if (Math.abs(dx) > 16 && Math.abs(dx) > 2 * Math.abs(dy)) sw.mode = 'h'; else return;
    }
    const items = [...sw.root.querySelectorAll(CONTROLS[0].item)];
    const s = state.get(sw.root), at = items.indexOf(s.on);
    const to = items[at + (dx > 0 ? -1 : 1)];   // a swipe to the left goes on to the next page
    sw.to = to || null;
    if (!to) { sw.p = 0; draw(sw.root, s.b, 0); return; }
    const a = s.b, b = box(sw.root, to, CONTROLS[0]);
    const p = sw.p = Math.min(1, Math.abs(dx) / (w.innerWidth * 0.45));
    draw(sw.root, { x: a.x + (b.x - a.x) * p, y: a.y, w: a.w + (b.w - a.w) * p, h: a.h }, 0);
    mark(items, p > 0.5 ? to : s.on);
  }, { passive: true });
  doc.addEventListener('touchend', () => {
    if (!sw || !sw.mode) { sw = null; return; }
    const g = sw; sw = null;
    const s = state.get(g.root);
    if (g.to && g.p > 0.5) g.to.click();   // lets go into the next page (the click carries the surface on from where the finger left it)
    else { draw(g.root, s.b, reduced() ? 0 : 320); mark([...g.root.querySelectorAll(CONTROLS[0].item)], s.on); }   // or settles back
  }, { passive: true });
  // the navigation sits over the middle of the page's content (not of the
  // window): with the sidebar open, that is to the right of the middle
  const main = doc.querySelector('[data-testid="stMain"]');
  const centre = () => { if (main) { const m = main.getBoundingClientRect(); doc.documentElement.style.setProperty('--cx-main', (m.left + m.width / 2) + 'px'); } };
  if (main && w.ResizeObserver) new w.ResizeObserver(centre).observe(main);
  centre();
  soon();
})();
"""


def script() -> str:
    assert "<" not in SCRIPT      # Streamlit drops a script that seems to hold a tag
    return f'<div id="cx-hook" hidden></div><script>{SCRIPT}</script>'
