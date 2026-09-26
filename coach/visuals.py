"""What each subject looks like: the object that stands for it, the field
it belongs to, how its world is composed, and facts from its own syllabus.

One system, a world per subject. Every subject has the same parts (an
object, a kicker, a composition, a title style); only their values differ,
so a new subject needs one entry in WORLD and its object, nothing else.

Objects are either pictures (works in the public domain or CC0, kept in
static/subjects/ and served by Streamlit's static serving) or drawn here
(the jewellery's necklace). A picture that isn't there yet is never shown
broken: the subject's number stands in for it."""
from functools import lru_cache
from html import escape
from pathlib import Path

from coach import curriculum

STATIC = Path(__file__).resolve().parent.parent / "static"

# topic -> its world:
#   kicker   the field it belongs to
#   shows    what its object is (alt text)
#   object   "subjects/<file>" for a picture, or "svg:<name>" for a drawn one
#   focus    where a picture sits in its frame (its subject kept in view)
#   layout   how the world is composed: "figure" (a tall figure beside the
#            title), "instrument" (an object held in the middle of the
#            space), "painting" (a scene laid wide), "pendant" (hung from
#            the top of the page)
#   title    "serif" (the house serif, large) or "tracked" (spaced capitals,
#            for a subject about precision)
#   credit   the work, who made it, where it is, its licence
WORLD = {
    "philosophy": dict(kicker="Humanities", shows="A marble bust of Socrates", object="subjects/philosophy.jpg",
                       focus="50% 28%", layout="figure", title="serif",
                       credit="Socrates, Roman marble after a Greek original · Musée du Louvre · Public domain"),
    "cosmos": dict(kicker="Natural science", shows="A planispheric astrolabe, the instrument that measured the sky",
                   object="subjects/cosmos.jpg", focus="50% 42%", layout="instrument", title="serif",
                   credit="Planispheric astrolabe by Muhammad Zaman al-Munajjim al-Asturlabi · "
                          "The Metropolitan Museum of Art · CC0"),
    "investing": dict(kicker="Markets and money", shows="The courtyard of the Old Exchange in Amsterdam, full of traders",
                      object="subjects/investing.jpg", focus="50% 50%", layout="painting", title="serif",
                      credit="Job Berckheyde, The Courtyard of the Old Exchange in Amsterdam, c. 1670 · "
                             "Museum Boijmans Van Beuningen · Public domain"),
    "business": dict(kicker="Enterprise", shows="Luca Pacioli, who first set out double-entry bookkeeping, at his desk",
                     object="subjects/business.jpg", focus="46% 30%", layout="painting", title="serif",
                     credit="Portrait of Luca Pacioli, attributed to Jacopo de' Barbari, 1495 · "
                            "Museo di Capodimonte · Public domain"),
    "fashion": dict(kicker="Dress and textiles", shows="Vermeer's Lacemaker, bent over her lace pillow",
                    object="subjects/fashion.jpg", focus="50% 36%", layout="figure", title="serif",
                    credit="Johannes Vermeer, The Lacemaker, c. 1669–70 · Musée du Louvre · Public domain"),
    "jewelry": dict(kicker="Craft and materials", shows="A single emerald-cut diamond on a fine chain",
                    object="svg:emerald", focus="", layout="pendant", title="tracked", credit=""),
    "free": dict(kicker="Across the disciplines",
                 shows="The frontispiece of the Encyclopédie: all the arts and sciences gathered",
                 object="subjects/free.jpg", focus="50% 22%", layout="figure", title="serif",
                 credit="Frontispiece of the Encyclopédie, drawn by Charles-Nicolas Cochin, engraved by "
                        "Benoît-Louis Prévost · Public domain"),
}


def _octagon(cx, cy, w, h, cut):
    """An emerald cut's outline: a rectangle with its corners cut."""
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    pts = [(x0 + cut, y0), (x1 - cut, y0), (x1, y0 + cut), (x1, y1 - cut),
           (x1 - cut, y1), (x0 + cut, y1), (x0, y1 - cut), (x0, y0 + cut)]
    return pts


def _pts(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


@lru_cache(maxsize=None)
def emerald_svg() -> str:
    """One emerald-cut diamond on a fine chain, drawn in the page's own ink:
    clear as glass, its step-cut facets in hairlines, a single glint. The
    chain falls from the top of its frame, so the stone hangs in the space."""
    cx, cy, w, h = 200, 640, 128, 178
    rings = [_octagon(cx, cy, w - 2 * k, h - 2 * k, 26 - k * 0.55) for k in (0, 11, 22, 33)]
    table = rings[-1]
    facets = "".join(
        f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>'
        for a, b in zip(rings[0], table))
    steps = "".join(f'<polygon points="{_pts(r)}" opacity="{0.55 - i * 0.1:.2f}"/>' for i, r in enumerate(rings[1:], 1))
    top = cy - h / 2
    return (
        '<svg class="obj-svg" viewBox="0 0 400 900" preserveAspectRatio="xMidYMin meet" role="img" '
        'aria-label="A single emerald-cut diamond on a fine chain" xmlns="http://www.w3.org/2000/svg">'
        '<defs><linearGradient id="em-body" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="currentColor" stop-opacity="0.10"/>'
        '<stop offset="0.5" stop-color="currentColor" stop-opacity="0.03"/>'
        '<stop offset="1" stop-color="currentColor" stop-opacity="0.08"/></linearGradient>'
        '<linearGradient id="em-table" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="currentColor" stop-opacity="0.14"/>'
        '<stop offset="0.55" stop-color="currentColor" stop-opacity="0"/>'
        '<stop offset="1" stop-color="currentColor" stop-opacity="0.06"/></linearGradient></defs>'
        # the chain: two fine strands meeting at the bail
        f'<g fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-dasharray="2.2 1.6" opacity="0.7">'
        f'<path d="M92,0 C110,250 170,430 {cx - 4},{top - 22}"/>'
        f'<path d="M308,0 C290,250 230,430 {cx + 4},{top - 22}"/></g>'
        # the bail
        f'<rect x="{cx - 5}" y="{top - 26}" width="10" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.2" opacity="0.75"/>'
        f'<line x1="{cx}" y1="{top - 8}" x2="{cx}" y2="{top}" stroke="currentColor" stroke-width="1.2" opacity="0.75"/>'
        # the stone: a clear body, its steps, the table, the corner facets
        f'<polygon points="{_pts(rings[0])}" fill="url(#em-body)" stroke="currentColor" stroke-width="1.3" opacity="0.95"/>'
        f'<g fill="none" stroke="currentColor" stroke-width="0.8">{steps}</g>'
        f'<polygon points="{_pts(table)}" fill="url(#em-table)" stroke="currentColor" stroke-width="0.9" opacity="0.7"/>'
        f'<g stroke="currentColor" stroke-width="0.6" opacity="0.4">{facets}</g>'
        # one glint, at the upper left of the table
        f'<g transform="translate({table[0][0] + 6:.1f},{table[0][1] + 10:.1f})" fill="currentColor" opacity="0.85">'
        '<path d="M0,-7 L1.1,-1.1 L7,0 L1.1,1.1 L0,7 L-1.1,1.1 L-7,0 L-1.1,-1.1 Z"/></g>'
        "</svg>"
    )


SVGS = {"emerald": emerald_svg}
# a page can't hold an <svg> of its own (Streamlit's HTML is sanitised), so a
# drawn object is served as a picture, once in each theme's ink
INKS = {"light": "#141414", "dark": "#EDEDED"}


def drawn_file(name: str, theme: str) -> str:
    return f"subjects/{name}-{theme}.svg"


def drawn_svg(name: str, theme: str) -> str:
    """A drawn object as a standalone picture in one theme's ink."""
    return SVGS[name]().replace("currentColor", INKS[theme]).replace(' class="obj-svg"', "")


def write_drawn() -> None:
    """Write every drawn object's pictures (python -m coach.visuals)."""
    for name in SVGS:
        for theme in INKS:
            (STATIC / drawn_file(name, theme)).write_text(drawn_svg(name, theme), encoding="utf-8")


def image_url(topic: str):
    """A picture's address, or None (a drawn object, or a picture not there yet)."""
    obj = WORLD[topic]["object"]
    if obj.startswith("svg:"):
        return None
    return f"app/static/{obj}" if (STATIC / obj).exists() else None


def has_object(topic: str) -> bool:
    return WORLD[topic]["object"].startswith("svg:") or image_url(topic) is not None


def object_html(topic: str, cls: str, number: int = 0) -> str:
    """The subject's object, marked with data-object so the page can carry
    it from one screen to the next (motion.py)."""
    w = WORLD[topic]
    obj = w["object"]
    if obj.startswith("svg:"):
        name = obj[4:]
        return (f'<div class="{cls} is-drawn" data-object="{topic}" data-layout="{w["layout"]}" role="img" '
                f'aria-label="{escape(w["shows"])}" style="--ink-light:url(\'app/static/{drawn_file(name, "light")}\');'
                f'--ink-dark:url(\'app/static/{drawn_file(name, "dark")}\')"></div>')
    url = image_url(topic)
    if url:
        return (f'<div class="{cls}" data-object="{topic}" data-layout="{w["layout"]}" role="img" '
                f'aria-label="{escape(w["shows"])}" '
                f'style="background-image:url(\'{url}\');background-position:{w["focus"]}"></div>')
    return f'<div class="{cls} no-art" data-object="{topic}" aria-hidden="true" data-n="{number:02d}"></div>'


def credit(topic: str) -> str:
    return WORLD[topic]["credit"] if image_url(topic) else ""


@lru_cache(maxsize=None)
def facts(topic: str) -> dict:
    """From the syllabus itself: how many lessons and topics, and where it begins."""
    units = [line.lstrip("#").strip()
             for line in (curriculum.DIR / f"{topic}.txt").read_text(encoding="utf-8").splitlines()
             if line.startswith("#")]
    return {"lessons": curriculum.written(topic), "units": len(units), "first": units[0] if units else ""}


@lru_cache(maxsize=None)
def units(topic: str) -> tuple:
    """The syllabus's topics (units) in order, with the lesson numbers each spans."""
    out, n, current = [], 0, None
    for line in (curriculum.DIR / f"{topic}.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = [line.lstrip("#").strip(), n + 1, n]
            out.append(current)
        else:
            n += 1
            if current:
                current[2] = n
    return tuple((name, first, last) for name, first, last in out)


if __name__ == "__main__":
    write_drawn()
