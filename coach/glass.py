"""Page behaviours the stylesheet relies on (coach/style.py).

GNOSIS is solid and flat: there is no glass, filter or refraction. What is
left here is the little script every page runs once: it marks the page
light or dark, gives touch screens their pressed look, and lets the
Progress calendar answer a tap before the page has redrawn.
"""


def script() -> str:
    """Page behaviours added once, whatever page she opens first: the page
    marked light or dark (for the few rules light-dark() can't express),
    the pressed look on touch screens, and the calendar's instant feedback."""
    return (
        '<div id="lg-hook" hidden></div>'
        "<script>(function () {"
        "const doc = window.parent.document;"
        "if (doc.documentElement.dataset.gnosisPage) return; doc.documentElement.dataset.gnosisPage = '1';"
        # mark the page with the theme Streamlit is showing (and keep it current when it changes)
        "const sync = () => { const app = doc.querySelector('.stApp');"
        "  if (app) doc.documentElement.dataset.scheme = getComputedStyle(app).colorScheme.includes('dark') ? 'dark' : 'light'; };"
        "sync(); setInterval(sync, 1500);"
        "window.parent.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', sync);"
        # Safari on iPhone and iPad shows :active (the pressed look) only
        # once the page listens for touches; passive, so scrolling is untouched
        "doc.addEventListener('touchstart', () => {}, { passive: true });"
        # a day tapped on the Progress calendar shows as picked at once,
        # before the page has redrawn (the redraw replaces the button)
        "doc.addEventListener('click', (ev) => { if (!ev.target.closest || !ev.target.closest('button')) return;"
        "  doc.querySelectorAll('[data-picking]').forEach((x) => x.removeAttribute('data-picking'));"
        "  const b = ev.target.closest('[class*=\"st-key-cal_20\"] button');"
        "  if (b && !b.disabled) b.setAttribute('data-picking', '');"
        # a month change starts the moment she taps: the month showing steps
        # aside (away from where she is going) while the next one is drawn,
        # then the next one comes in from that side (style.py)
        "  const grid = doc.querySelector('[class*=\"st-key-calgrid_\"]'); if (!grid) return;"
        "  const gm = (grid.className.match(/st-key-calgrid_(\\d+)_(\\d+)/) || []).slice(1).map(Number);"
        "  let way = ev.target.closest('.st-key-cal_next') ? 'next' : ev.target.closest('.st-key-cal_prev') ? 'prev' : '';"
        "  const day = b && b.closest('[class*=\"st-key-cal_20\"]').className.match(/st-key-cal_(\\d+)-(\\d+)-/);"
        "  if (!way && day && gm.length === 2) { const d = +day[1] * 12 + +day[2], g = gm[0] * 12 + gm[1]; way = d > g ? 'next' : g > d ? 'prev' : ''; }"
        "  if (way) grid.dataset.leaving = way; }, true);"
        "})();</script>"
    )
