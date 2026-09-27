"""Accessibility on every page, light and dark: every control has a name,
text contrast (4.5:1, large text 3:1), the keyboard reaches the controls
with a visible focus ring, and reduced motion turns movement off.
(No outside checker: the rules are measured here directly.)"""
import itertools
import time

import pytest

import flows
from conftest import covers

_n = itertools.count()

NAMELESS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const nameOf = e => {
    const by = e.getAttribute('aria-labelledby');
    const lab = by ? by.split(/\\s+/).map(id => document.getElementById(id)?.innerText || '').join(' ') : '';
    const forLab = e.id ? (document.querySelector(`label[for="${CSS.escape(e.id)}"]`)?.innerText || '') : '';
    const wrap = e.closest('label')?.innerText || '';
    return (e.getAttribute('aria-label') || lab || forLab || wrap || e.innerText || e.value && e.type === 'submit' && e.value
            || e.getAttribute('title') || e.getAttribute('placeholder') || '').trim();
  };
  return [...document.querySelectorAll('button, a[href], input:not([type=hidden]), textarea, select, [role=button], [role=switch], [role=tab], [role=radio], [role=checkbox]')]
    .filter(vis).filter(e => !nameOf(e))
    .map(e => e.outerHTML.slice(0, 160));
}"""

CONTRAST = """() => {
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const over = (top, bottom) => ({r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a),
                                  b: top.b * top.a + bottom.b * (1 - top.a), a: 1});
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bgOf = el => { const layers = [];
    for (let e = el; e; e = e.parentElement) { const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== 'none' && !s.backgroundImage.startsWith('linear-gradient')) return null;  // an image: can't tell
      const c = parse(s.backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; } }
    let base = parse(getComputedStyle(document.body).backgroundColor) || {r: 255, g: 255, b: 255, a: 1};
    if (base.a < 1) base = over(base, {r: 255, g: 255, b: 255, a: 1});
    return layers.reverse().reduce((acc, l) => over(l, acc), base); };
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; const el = t.parentElement;
    if (!el || seen.has(el) || !t.textContent.trim()) continue; seen.add(el);
    const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    if (r.width < 1 || r.height < 1 || s.visibility === 'hidden' || +s.opacity === 0) continue;
    if (el.closest('[aria-hidden=true], [hidden], .material-symbols-rounded, [data-testid=stIconMaterial]')) continue;
    if (el.closest('button:disabled, [aria-disabled=true], input:disabled')) continue;   // disabled controls are exempt
    let fg = parse(s.color); const bg = bgOf(el); if (!fg || !bg) continue;
    let op = 1; for (let e = el; e; e = e.parentElement) op *= +getComputedStyle(e).opacity;
    fg = over({...fg, a: fg.a * op}, bg);
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(s.fontSize); const bold = +s.fontWeight >= 700;
    const need = (size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5;
    if (ratio < need) bad.push(`${ratio.toFixed(2)} < ${need}: "${t.textContent.trim().slice(0, 40)}" (${s.color} on rgb(${bg.r|0},${bg.g|0},${bg.b|0}), ${size}px)`);
  }
  return bad;
}"""


def person(app, pages, scheme="light", width=1440, reading=True, **kw):
    p = pages(width=width, scheme=scheme, **kw)
    email = f"a11y{next(_n)}-{int(time.time() * 1000)}@example.com"
    flows.sign_in(p, app, email=email)
    flows.onboard(p, reading=reading)
    flows.open_app(p, app)
    return p


PAGES = [("/", "Start this lesson"), ("/records", "Backup and restore"), ("/settings", "Daily pace"),
         ("/reading", "Start a new book"), ("/subject?subject=philosophy", "Where you are")]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_names_and_contrast_on_every_page(public_app, pages, scheme):
    covers("W-topnav-p")
    app = public_app
    p = person(app, pages, scheme=scheme)
    problems = {}
    for path, marker in PAGES:
        flows.open_app(p, app, path)
        assert flows.wait_text(p.page, marker, 15), path
        p.page.wait_for_timeout(600)                     # entrance motion settles
        nameless = p.page.evaluate(NAMELESS)
        low = p.page.evaluate(CONTRAST)
        if nameless or low:
            problems[path] = {"no name": nameless[:8], "contrast": low[:12]}
    assert not problems, problems


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_sign_in_page_names_and_contrast(public_app, pages, scheme):
    covers("W-auth-si_form")
    app = public_app
    p = pages(width=1440, scheme=scheme)
    flows.open_app(p, app)
    assert flows.wait_text(p.page, "Continue with Google")
    assert p.page.evaluate(NAMELESS) == []
    assert p.page.evaluate(CONTRAST) == []


def test_keyboard_reaches_everything_with_a_visible_focus(public_app, pages):
    covers("W-topnav-p", "W-daily-start_this_lesson")
    app = public_app
    p = person(app, pages)
    page = p.page
    page.locator("body").click(position={"x": 5, "y": 300})
    reached, invisible = [], []
    for _ in range(60):
        page.keyboard.press("Tab")
        info = page.evaluate("""() => { const e = document.activeElement; if (!e || e === document.body) return null;
            const s = getComputedStyle(e);
            const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow && s.boxShadow !== 'none');
            const within = e.closest('[data-baseweb]') ? true : false;
            return {name: (e.getAttribute('aria-label') || e.innerText || e.getAttribute('placeholder') || e.tagName).trim().slice(0, 40),
                    ring, within, tag: e.tagName}; }""")
        if not info:
            continue
        reached.append(info["name"])
        if not info["ring"] and not info["within"]:
            invisible.append(info["name"])
    for must in ("Today", "Progress", "Settings", "Start this lesson"):
        assert any(must in r for r in reached), f"Tab never reaches {must!r}: {reached}"
    assert not invisible, f"focused without a visible ring: {sorted(set(invisible))}"


def test_reduced_motion_turns_movement_off(public_app, pages):
    covers("W-topnav-p")
    app = public_app
    p = person(app, pages, reduced_motion=True)
    flows.go(p, app, "Progress")
    flows.go(p, app, "Today")
    moving = p.page.evaluate("""() => [...document.querySelectorAll('*')].filter(e => {
        const s = getComputedStyle(e);
        const long = v => v.split(',').some(x => parseFloat(x) * (x.includes('ms') ? 1 : 1000) > 10);
        return (s.animationName !== 'none' && long(s.animationDuration) && s.animationIterationCount !== '0')
               || (s.transitionProperty.includes('transform') && long(s.transitionDuration));
    }).map(e => (e.className && e.className.toString().slice(0, 60)) || e.tagName).slice(0, 15)""")
    assert not moving, f"still animated with reduced motion: {moving}"
