"""Connected controls: one active surface that travels between the items
of a control instead of each item lighting up on its own.

Used by the page navigation at the top (Today, Reading, Progress,
Settings), the switch on Progress (Day, Sessions, Subjects) and the
setup's starting-level switch. For each control the
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
    { root: '.st-key-topnav_items', item: '[data-testid="stPageLink-NavLink"]', pages: true, target: 'p, [data-testid="stIconMaterial"]', cls: 'cx-line',
      shape: (b, r) => ({ x: b.x - 2, y: r.h - 1.5, w: b.w + 4, h: 1.5 }),
      on: (items) => items.find((a) => a.getAttribute('href') && pathOf(a) === here()) || (here() === '/' ? items.find((a) => !a.getAttribute('href')) : null) },
    // switches (Progress's Day | Sessions | Subjects, a subject's starting
    // point): the lens slides along the track, over the words chosen
    { root: '.st-key-prog_view [data-testid="stButtonGroup"] > div', item: 'button', cls: 'cx-lens',
      on: (items) => items.find((b) => b.getAttribute('aria-checked') === 'true') },
    { root: '[class*="st-key-sw_"] [data-testid="stButtonGroup"] > div', item: 'button', cls: 'cx-lens',
      on: (items) => items.find((b) => b.getAttribute('aria-checked') === 'true') },
    // lists of options (setup, Settings, the placement check): the lens lies
    // over the row in focus: the one chosen, or in a list of several choices,
    // the one she last touched (what is chosen shows in each row, choices.py)
    { root: '[class*="st-key-optlist_"]', item: '[class*="st-key-opt_"]', cls: 'cx-lens',
      shape: (b) => ({ x: b.x - 8, y: b.y + 3, w: b.w + 16, h: b.h - 6 }),
      on: (items) => items.find((r) => (r.className.split(' ').find((k) => k.startsWith('st-key-opt_')) || '').endsWith('_f'))
        || items.find((r) => r.querySelector('.opt[data-multi="0"]') && r.className.includes('__sel')) },
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
    // the target that shows (Settings is a word on a wide page, an icon on a narrow one)
    const t = c && c.target ? [...el.querySelectorAll(c.target)].find((x) => x.getBoundingClientRect().width > 1) || el : el;
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
    // the edge light and fill change on their own gentler clock (moving, then settling)
    p.style.transition = (ms ? 'transform ' + ms + 'ms var(--ease-nav), width ' + ms + 'ms var(--ease-nav), height ' + ms + 'ms var(--ease-nav), ' : '')
      + 'box-shadow 360ms var(--ease), background-color 360ms var(--ease), opacity 240ms var(--ease)';
    p.style.width = b.w + 'px'; p.style.height = b.h + 'px';
    p.style.transform = 'translate(' + b.x + 'px, ' + b.y + 'px)';
    root.style.setProperty('--cx-dur', (ms || 1) + 'ms');
    // moving, the glass shows its material a little more; settled, it calms
    if (ms) { p.classList.add('cx-live'); clearTimeout(p._live); p._live = setTimeout(() => p.classList.remove('cx-live'), ms + 120); }
  }
  // move the surface to `to`: the time grows a little with the distance
  function go(root, items, to, animate, c) {
    const s = state.get(root) || {};
    if (c) s.c = c;
    state.set(root, s);
    const b = box(root, to, s.c);
    let ms = 0;
    if (animate && s.b) ms = reduced() ? 0 : Math.round(Math.min(620, Math.max(340, 300 + Math.hypot(b.x - s.b.x, b.y - s.b.y) * 0.8)));
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
        // nothing on (a page not in the bar, a subject's world): the surface bows out and no item claims to be here
        if (!on) { const p = root.querySelector(':scope > .cx-pill'); if (p) p.style.opacity = '0'; items.forEach((i) => i.hasAttribute('data-cx-on') && i.removeAttribute('data-cx-on')); const s0 = state.get(root); if (s0) { s0.on = null; state.set(root, s0); } return; }
        const s = state.get(root) || {};
        // the page redrew the control as a new element (a key changed): if
        // that happened just now, the surface carries on from where it was
        if (!s.b && c.last && performance.now() - c.last.at > 0 && 2000 > performance.now() - c.last.at) {
          s.c = c; s.b = c.last.b; state.set(root, s); draw(root, s.b, 0); root.getBoundingClientRect();
        }
        if (s.pending && performance.now() - s.pendingAt > 3000) s.pending = null;
        // (the tapped item redrawn as a new element: the page has caught up)
        if (s.pending && s.pending !== on && s.pending.isConnected) return;
        s.pending = null; state.set(root, s);
        const b = box(root, on, c);
        const p = root.querySelector(':scope > .cx-pill');
        const moved = s.b && Math.abs(b.x - s.b.x) + Math.abs(b.y - s.b.y) > 0.5;
        if (s.on !== on || !s.b || moved || Math.abs(b.w - s.b.w) + Math.abs(b.h - s.b.h) > 0.5 || !p || p.style.opacity === '0') go(root, items, on, !!s.b && (s.on !== on || moved), c);
      });
    }
    stage();
    world();
    // a new page has come in (Streamlit has redrawn: its stale marks have
    // come and gone): let the content settle back
    if (doc.documentElement.hasAttribute('data-cx-leaving')) {
      const stale = !!doc.querySelector('[data-testid="stMain"] [data-stale="true"]');
      if (stale) sawStale = true;
      if ((sawStale && !stale && here() !== leftFrom) || performance.now() - leftAt > 1500) doc.documentElement.removeAttribute('data-cx-leaving');
    }
  }
  // the subjects' stage (the setup, Settings): it shows the subject in focus
  // (the row the lens lies over) and whether it is chosen. The page draws it
  // with its subject already in focus; a touch moves the focus at once (the
  // row the lens is going to), so name, words, object and state change
  // together, as one; nothing here falls back to another subject. A way
  // into a world drawn beside the stage for one subject stands aside while
  // the stage shows another (the page redraws it for the new one)
  function stage() {
    doc.querySelectorAll('.sg-stage').forEach((st) => {
      const g = st.dataset.group || 'subj';
      const rows = [...doc.querySelectorAll('[class*="st-key-opt_' + g + '_"]')];
      const re = new RegExp('st-key-opt_' + g + '_([a-z]+)__');
      const topic = (r) => (r.className.match(re) || [])[1];
      const chosen = (r) => (r.dataset.on ? r.dataset.on === '1' : /__sel/.test(r.className));
      const f = rows.find((r) => r.hasAttribute('data-cx-on'))
        || rows.find((r) => (r.className.match(new RegExp('st-key-opt_' + g + '_\\S+')) || [''])[0].endsWith('_f'));
      const t = f ? topic(f) : st.dataset.focus;
      if (t && st.dataset.focus !== t) st.dataset.focus = t;
      st.querySelectorAll('.sg-layer').forEach((l) => { const h = l.dataset.t === st.dataset.focus ? 'false' : 'true'; if (l.getAttribute('aria-hidden') !== h) l.setAttribute('aria-hidden', h); });
      const holder = st.closest('[class*="st-key-"][class*="_stage"]');
      if (holder) holder.querySelectorAll('[class*="st-key-enter_"]').forEach((e) => {
        const mine = (e.className.match(/st-key-enter_([a-z]+)/) || [])[1];
        if (mine === st.dataset.focus) e.removeAttribute('data-other'); else e.setAttribute('data-other', '');
      });
      const layer = st.querySelector('.sg-layer[data-t="' + st.dataset.focus + '"]');
      const state = layer && layer.querySelector('.sg-state');
      if (!state || !f) return;
      let text = /__dis/.test(f.className) ? 'Not chosen · three are chosen already, so take one out to add this' : 'Not chosen';
      if (chosen(f)) {
        const o = f.querySelector('.opt');
        const day = o && o.dataset.day ? +o.dataset.day : rows.filter((r) => chosen(r) && r !== f).length + 1;
        text = 'Chosen · day ' + day + ' of the rotation';
      }
      if (state.textContent !== text) state.textContent = text;
      state.dataset.on = chosen(f) ? '1' : '0';
    });
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

  // a subject's world: touching a way into it (anything inside an
  // enter_(subject) block, or Start learning at the end of the setup), the
  // subject's object is noted where it is on screen; the world then carries
  // that same object from there into its own place (world() below)
  const shown = (e) => {
    const r = e.getBoundingClientRect();
    if (r.width * r.height === 0 || r.bottom > w.innerHeight + 40 && r.top > w.innerHeight) return false;
    const layer = e.closest('.sg-layer');
    return !layer || +w.getComputedStyle(layer).opacity > 0.5;
  };
  doc.addEventListener('click', (ev) => {
    const b = ev.target.closest && ev.target.closest('[class*="st-key-enter_"] button, .st-key-ob_nav .st-key-ob_next button, .st-key-ob_nav button[kind="primary"]');
    if (!b) return;
    const box = b.closest('[class*="st-key-enter_"]');
    const mark = doc.querySelector('[data-enter]');
    const t = box ? (box.className.match(/st-key-enter_([a-z]+)/) || [])[1] : mark && mark.dataset.enter;
    if (!t) return;
    const o = [...doc.querySelectorAll('[data-object="' + t + '"]')].find(shown);
    const r = o && o.getBoundingClientRect();
    try {
      w.sessionStorage.setItem('cx-object', JSON.stringify(r ? { t: t, x: r.left, y: r.top, w: r.width, h: r.height, at: Date.now() } : { t: t, at: Date.now() }));
    } catch (e) {}
  }, true);
  function world() {
    const hero = doc.querySelector('.w-object[data-object]:not([data-arrived])');
    if (!hero) return;
    if (!hero.getBoundingClientRect().width) return;
    hero.dataset.arrived = '1';
    // a new world opens at its beginning, wherever the last one was left
    const scroller = doc.querySelector('[data-testid="stMain"]');
    if (scroller && scroller.scrollTop) scroller.scrollTo({ top: 0, behavior: 'instant' });
    const r = hero.getBoundingClientRect();
    const page = hero.closest('[class*="st-key-world_"]');
    let from = null;
    try { from = JSON.parse(w.sessionStorage.getItem('cx-object') || 'null'); w.sessionStorage.removeItem('cx-object'); } catch (e) {}
    if (page) page.dataset.entering = '1';
    setTimeout(() => page && page.removeAttribute('data-entering'), 1400);
    if (reduced()) return;
    if (from && from.t === hero.dataset.object && 6000 > Date.now() - from.at && from.w) {
      // the same object, from where it was to where it lives here
      const k = Math.sqrt((from.w / r.width) * (from.h / r.height));
      const dx = from.x + from.w / 2 - (r.left + r.width / 2), dy = from.y + from.h / 2 - (r.top + r.height / 2);
      hero.animate([{ transform: 'translate(' + dx + 'px,' + dy + 'px) scale(' + k + ')', opacity: 0.9 },
                    { transform: 'none', opacity: 1 }],
                   { duration: 820, easing: 'cubic-bezier(0.32, 0.72, 0, 1)', fill: 'backwards' });
    } else {
      hero.animate([{ opacity: 0, transform: 'scale(1.035)' }, { opacity: 1, transform: 'none' }],
                   { duration: 900, easing: 'cubic-bezier(0.22, 0.61, 0.36, 1)', fill: 'backwards' });
    }
  }

  // the setup: pressing Continue or Back, the step leaves toward where she
  // came from while the next one is drawn (style.py)
  doc.addEventListener('click', (ev) => {
    const b = ev.target.closest && ev.target.closest('.st-key-ob_nav button');
    if (!b || b.disabled) return;
    const step = b.closest('[class*="st-key-ob_step_"]');
    if (step && !reduced()) {
      step.dataset.leaving = b.closest('.st-key-ob_back') ? 'back' : 'fwd';
      // the same step drawn again (nothing to move on to): it comes back
      setTimeout(() => { if (step.isConnected) step.removeAttribute('data-leaving'); }, 1400);
    }
  }, true);

  // a list of options (setup, Settings): a tap shows the row chosen (or not)
  // at once; the page redraws it the same way a moment later, and the marks
  // set here are cleared once it has
  let pickAt = 0, pickSaw = false;
  doc.addEventListener('click', (ev) => {
    const b = ev.target.closest && ev.target.closest('[class*="st-key-opt_"] button');
    if (!b || b.disabled) return;
    const row = b.closest('[class*="st-key-opt_"]'), list = row.closest('[class*="st-key-optlist_"]');
    const o = row.querySelector('.opt'), on = row.dataset.on ? row.dataset.on === '1' : row.className.includes('__sel');
    if (o && o.dataset.multi === '1') { if (!/__dis/.test(row.className)) row.dataset.on = on ? '0' : '1'; }
    else if (list) { list.querySelectorAll('[class*="st-key-opt_"]').forEach((r) => { r.dataset.on = '0'; }); row.dataset.on = '1'; }
    pickAt = performance.now(); pickSaw = false;
    stage();
  }, true);
  new w.MutationObserver(() => {
    if (!pickAt) return;
    const stale = !!doc.querySelector('[data-testid="stMain"] [data-stale="true"]');
    if (stale) pickSaw = true;
    if ((pickSaw && !stale) || performance.now() - pickAt > 2500) {
      doc.querySelectorAll('[class*="st-key-opt_"][data-on]').forEach((r) => r.removeAttribute('data-on'));
      pickAt = 0;
    }
  }).observe(doc.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-stale'] });

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
