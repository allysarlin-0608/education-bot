"""Clear optical glass: the refraction filter the glass surfaces use.

The glass has almost no fill of its own. What shows it is how the content
behind it bends: an SVG displacement filter, used as the surface's
backdrop-filter, shifts that content by a few pixels in a narrow band along
the edges (more where two edges meet, at the corners) and leaves the
centre untouched, the way a thin sheet of clear glass with rounded edges
bends light only near its rim.

The displacement maps are drawn in pixels, not in proportions, so the band
is equally narrow on a small button and a wide card. Browsers that can't
use an SVG filter as a backdrop (Safari, Firefox) simply show clear glass.
"""
import base64
from urllib.parse import quote

EDGE = 26          # px: how far in from the rim the glass bends light
SCALE = 30         # px: the shift right at the rim is half this; it eases to nothing EDGE px in


def _map(axis: str) -> str:
    """A displacement map for one axis. Neutral grey (no shift) over the
    centre, so it stays perfectly clear; within EDGE px of the rim each
    point shows what lies further out, most at the rim and easing to
    nothing inward, the way the rounded edge of a thick clear lens pulls
    in and compresses what sits just beyond it. Red carries x, green
    carries y; the other stays neutral."""
    grey = "rgb(128,128,128)"
    back, fwd = ("rgb(0,128,128)", "rgb(255,128,128)") if axis == "x" else ("rgb(128,0,128)", "rgb(128,255,128)")
    size = 'width="{e}" height="100%"' if axis == "x" else 'width="100%" height="{e}"'
    end = 'x="-{e}"' if axis == "x" else 'y="-{e}"'
    at_end = 'x="100%"' if axis == "x" else 'y="100%"'
    start_line = 'x1="0" y1="0" x2="{e}" y2="0"' if axis == "x" else 'x1="0" y1="0" x2="0" y2="{e}"'
    end_line = 'x1="0" y1="0" x2="-{e}" y2="0"' if axis == "x" else 'x1="0" y1="0" x2="0" y2="-{e}"'
    # a curved falloff (strong at the rim, gentle inside): quarter, then nothing
    ease = lambda c: (f'<stop offset="0" stop-color="{c}"/><stop offset="0.45" stop-color="{_mix(c, 0.35)}"/>'
                      f'<stop offset="1" stop-color="{grey}"/>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">'
        '<defs>'
        f'<linearGradient id="a" gradientUnits="userSpaceOnUse" {start_line}>{ease(back)}</linearGradient>'
        f'<linearGradient id="b" gradientUnits="userSpaceOnUse" {end_line}>{ease(fwd)}</linearGradient>'
        '</defs>'
        f'<rect width="100%" height="100%" fill="{grey}"/>'
        f'<rect {size} fill="url(#a)"/>'
        f'<svg {at_end} overflow="visible"><rect {end} {size} fill="url(#b)"/></svg>'
        '</svg>'
    ).format(e=EDGE)
    return "data:image/svg+xml," + quote(svg)


def _mix(color: str, amount: float) -> str:
    """`amount` of the way from neutral grey to `color`."""
    r, g, b = (int(v) for v in color[4:-1].split(","))
    return "rgb({},{},{})".format(*(round(128 + (v - 128) * amount) for v in (r, g, b)))


def defs() -> str:
    """The filter, as an invisible SVG. It is added to the page once (a
    backdrop-filter can only point at a filter in the page itself)."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" style="position:absolute" aria-hidden="true">'
        # the maps cover the whole surface (no x/y/size: the filter region);
        # displacement is in pixels
        '<filter id="lg-refract" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">'
        f'<feImage href="{_map("x")}" preserveAspectRatio="none" result="mx"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="mx" scale="{SCALE}" xChannelSelector="R" yChannelSelector="G" result="dx"/>'
        f'<feImage href="{_map("y")}" preserveAspectRatio="none" result="my"/>'
        f'<feDisplacementMap in="dx" in2="my" scale="{SCALE}" xChannelSelector="R" yChannelSelector="G"/>'
        '</filter></svg>'
    )


def script() -> str:
    """Adds the filter to the page once, whatever page she opens first, and
    marks the page light or dark for the glass's filters. The markup travels
    base64-encoded: Streamlit drops a script whose text contains tags."""
    markup = base64.b64encode(defs().encode()).decode()
    return (
        '<div id="lg-hook" hidden></div>'
        "<script>(function () {"
        "const doc = window.parent.document;"
        "if (doc.getElementById('lg-defs')) return;"
        "const box = doc.createElement('div'); box.id = 'lg-defs';"
        "box.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';"
        f"box.innerHTML = atob('{markup}'); doc.body.appendChild(box);"
        # a filter can't follow light-dark(), so mark the page with the
        # theme Streamlit is showing (and keep it current when it changes)
        "const sync = () => { const app = doc.querySelector('.stApp');"
        "  if (app) doc.documentElement.dataset.scheme = getComputedStyle(app).colorScheme.includes('dark') ? 'dark' : 'light'; };"
        "sync(); setInterval(sync, 1500);"
        "window.parent.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', sync);"
        "})();</script>"
    )
