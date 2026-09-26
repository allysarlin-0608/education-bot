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
    "philosophy": ("Humanities", "Bust of Socrates, Roman copy of a Greek original", "subjects/philosophy.jpg"),
    "cosmos": ("Natural science", "An astrolabe, the instrument that measured the sky", "subjects/cosmos.jpg"),
    "investing": ("Markets and money", "The Amsterdam Exchange, the first stock exchange", "subjects/investing.jpg"),
    "business": ("Enterprise", "Luca Pacioli, who first set out double-entry bookkeeping", "subjects/business.jpg"),
    "fashion": ("Dress and textiles", "Cloth on the loom", "subjects/fashion.jpg"),
    "jewelry": ("Craft and materials", "Gold worked by hand", "subjects/jewelry.jpg"),
    "free": ("Across the disciplines", "A library", "subjects/free.jpg"),
}
# who made each picture and where it is (shown under it once it's there)
CREDITS = {}


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
