"""What each subject looks like: the image that stands for it, a short
line placing it, and facts from its own syllabus.

The images are works in the public domain (museum collections), kept in
static/subjects/ and served by Streamlit (server.enableStaticServing). A
subject whose image isn't there yet is shown by its typography alone,
never as a broken picture."""
from functools import lru_cache
from pathlib import Path

from coach import curriculum

STATIC = Path(__file__).resolve().parent.parent / "static"

# topic -> (kicker: the field it belongs to, what its picture shows, image file)
ART = {
    "philosophy": ("Humanities", "A marble bust of Socrates", "subjects/philosophy.jpg"),
    "cosmos": ("Natural science", "A planispheric astrolabe, the instrument that measured the sky", "subjects/cosmos.jpg"),
    "investing": ("Markets and money", "The courtyard of the Old Exchange in Amsterdam, full of traders", "subjects/investing.jpg"),
    "business": ("Enterprise", "Luca Pacioli, who first set out double-entry bookkeeping, at his desk", "subjects/business.jpg"),
    "fashion": ("Dress and textiles", "Vermeer's Lacemaker, bent over her lace pillow", "subjects/fashion.jpg"),
    "jewelry": ("Craft and materials", "A goldsmith weighing a ring in his shop", "subjects/jewelry.jpg"),
    "free": ("Across the disciplines", "The frontispiece of the Encyclopédie: all the arts and sciences gathered", "subjects/free.jpg"),
}
# where each picture sits in its frame (its subject kept in view)
FOCUS = {"philosophy": "50% 28%", "cosmos": "50% 42%", "investing": "50% 50%", "business": "46% 30%",
         "fashion": "50% 36%", "jewelry": "58% 34%", "free": "50% 22%"}
# the work, who made it, where it is, and its licence (all public domain or CC0,
# from Wikimedia Commons; converted to greys for the page)
CREDITS = {
    "philosophy": "Socrates, Roman marble after a Greek original · Musée du Louvre · Public domain",
    "cosmos": "Planispheric astrolabe by Muhammad Zaman al-Munajjim al-Asturlabi · The Metropolitan Museum of Art · CC0",
    "investing": "Job Berckheyde, The Courtyard of the Old Exchange in Amsterdam, c. 1670 · Museum Boijmans Van Beuningen · Public domain",
    "business": "Portrait of Luca Pacioli, attributed to Jacopo de' Barbari, 1495 · Museo di Capodimonte · Public domain",
    "fashion": "Johannes Vermeer, The Lacemaker, c. 1669–70 · Musée du Louvre · Public domain",
    "jewelry": "Petrus Christus, A Goldsmith in His Shop, 1449 · The Metropolitan Museum of Art · CC0",
    "free": "Frontispiece of the Encyclopédie, drawn by Charles-Nicolas Cochin, engraved by Benoît-Louis Prévost · Public domain",
}


def image_url(topic: str):
    """The picture's address, or None while the file isn't there."""
    rel = ART[topic][2]
    return f"app/static/{rel}" if (STATIC / rel).exists() else None


@lru_cache(maxsize=None)
def facts(topic: str) -> dict:
    """From the syllabus itself: how many lessons and topics, and where it begins."""
    units = [line.lstrip("#").strip()
             for line in (curriculum.DIR / f"{topic}.txt").read_text(encoding="utf-8").splitlines()
             if line.startswith("#")]
    return {"lessons": curriculum.written(topic), "units": len(units), "first": units[0] if units else ""}
