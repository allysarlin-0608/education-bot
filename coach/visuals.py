"""What each subject looks like: the object that stands for it, the field
it belongs to, how its world is composed, and facts from its own syllabus.

One system, a world per subject. Every subject has the same parts (an
object, a kicker, a composition, a title style); only their values differ,
so a new subject needs one entry in WORLD and its object, nothing else.

Objects are pictures kept in static/subjects/ and served by Streamlit's
static serving: works in the public domain or CC0, or objects modelled and
rendered for this app (the jewellery's necklace, art/necklace.py). A "cut"
object stands free, its background taken away (art/cutout.py, or rendered
on nothing), so it sits in the page itself rather than in a frame. A
picture that isn't there yet is never shown broken: the subject's number
stands in for it."""
from functools import lru_cache
from html import escape
from pathlib import Path

from coach import core, curriculum, settings

STATIC = Path(__file__).resolve().parent.parent / "static"

# topic -> its world:
#   kicker   the field it belongs to
#   shows    what its object is (alt text)
#   object   "subjects/<file>"
#   cut      the object stands free (no background of its own), not framed
#   focus    where a picture sits in its frame (its subject kept in view)
#   layout   how the world is composed: "figure" (a tall figure beside the
#            title), "instrument" (an object held in the middle of the
#            space), "painting" (a scene laid wide), "pendant" (hung from
#            the top of the page)
#   title    "serif" (the house serif, large) or "tracked" (spaced capitals,
#            for a subject about precision)
#   credit   the work, who made it, where it is, its licence
WORLD = {
    "philosophy": dict(kicker="Humanities", shows="A marble bust of Socrates", object="subjects/philosophy.webp",
                       cut=True, focus="50% 28%", layout="figure", title="serif",
                       credit="Socrates, Roman marble after a Greek original · Musée du Louvre · Public domain"),
    "cosmos": dict(kicker="Natural science", shows="A planispheric astrolabe, the instrument that measured the sky",
                   object="subjects/cosmos.webp", cut=True, focus="50% 42%", layout="instrument", title="serif",
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
    "jewelry": dict(kicker="Craft and materials",
                    shows="A diamond necklace: two twisted bands of round and marquise diamonds meeting in a V, "
                          "a pear-shaped diamond hanging from it",
                    object="subjects/jewelry.webp", cut=True, focus="50% 0%", layout="pendant", title="tracked",
                    credit="Diamond and platinum necklace with a pear-shaped drop · modelled and rendered for this app"),
    "free": dict(kicker="Across the disciplines",
                 shows="The frontispiece of the Encyclopédie: all the arts and sciences gathered",
                 object="subjects/free.jpg", focus="50% 22%", layout="figure", title="serif",
                 credit="Frontispiece of the Encyclopédie, drawn by Charles-Nicolas Cochin, engraved by "
                        "Benoît-Louis Prévost · Public domain"),
}


def image_url(topic: str):
    """A picture's address, or None (a picture not there yet)."""
    obj = WORLD[topic]["object"]
    return f"app/static/{obj}" if (STATIC / obj).exists() else None


def has_object(topic: str) -> bool:
    return image_url(topic) is not None


def object_html(topic: str, cls: str, number: int = 0) -> str:
    """The subject's object, marked with data-object so the page can carry
    it from one screen to the next (motion.py)."""
    w = WORLD[topic]
    url = image_url(topic)
    if url:
        return (f'<div class="{cls}{" is-cut" if w.get("cut") else ""}" data-object="{topic}" data-layout="{w["layout"]}" role="img" '
                f'aria-label="{escape(w["shows"])}" '
                f'style="background-image:url(\'{url}\');background-position:{w["focus"]}"></div>')
    return f'<div class="{cls} no-art" data-object="{topic}" aria-hidden="true" data-n="{number:02d}"></div>'


def credit(topic: str) -> str:
    return WORLD[topic]["credit"] if image_url(topic) else ""


def known(topic) -> bool:
    return topic in WORLD


def subject(topic: str) -> dict:
    """Everything a page shows of one subject, from one place: every screen
    that shows a subject (the stage in the setup and in Settings, its world,
    the ways into it) draws its name, words and object from here, keyed by
    the one subject it is showing, so no part of a screen can belong to
    another subject."""
    w = WORLD[topic]
    return {"key": topic, "number": list(settings.SUBJECTS).index(topic) + 1 if topic in settings.SUBJECTS else 0,
            "title": core.TOPICS[topic], "description": settings.DESCRIPTIONS.get(topic, ""),
            "kicker": w["kicker"], "shows": w["shows"], "layout": w["layout"], "title_style": w["title"],
            "credit": credit(topic), "facts": facts(topic)}


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

