"""The site in her language (ISS-108).

Every sentence the pages show is written in English in the code and passed
through tr(): tr("Take the quiz") is the English, or its translation in the
language she reads in. The translations are one JSON file per language in
coach/locales/ (English sentence → translation); a sentence missing from a
file shows in English, never as nothing. A sentence with parts that change
is a template: tr("{done} of {total} lessons passed", done=3, total=10); the
translation keeps the same {names}.

Her language: the one she chose (her preferences, coach/prefs.py, so it
follows her to any device), else the one her browser asks for, else
English. Only languages with a file are offered (LANGS lists the ones
planned). The lessons, quizzes and the coach's replies are written in it
too (ai_name: what the model is told).

tools/i18n.py lists every tr() sentence in the code and says which are
missing from each file; tests/test_i18n.py holds every file to it."""
import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent / "locales"
DEFAULT = "en"

# code → (its own name, its name in English, written right to left)
LANGS = {
    "en": ("English", "English", False),
    "zh-Hant": ("繁體中文", "Traditional Chinese", False),
    "zh-Hans": ("简体中文", "Simplified Chinese", False),
    "hi": ("हिन्दी", "Hindi", False),
    "es": ("Español", "Spanish", False),
    "ar": ("العربية", "Arabic", True),
    "fr": ("Français", "French", False),
    "bn": ("বাংলা", "Bengali", False),
    "pt": ("Português", "Portuguese", False),
    "ru": ("Русский", "Russian", False),
    "id": ("Bahasa Indonesia", "Indonesian", False),
    "ur": ("اردو", "Urdu", True),
    "de": ("Deutsch", "German", False),
    "ja": ("日本語", "Japanese", False),
    "mr": ("मराठी", "Marathi", False),
    "te": ("తెలుగు", "Telugu", False),
}


@lru_cache(maxsize=None)
def catalog(code: str) -> dict:
    """A language's translations ({} for English, or a language without a file)."""
    path = DIR / f"{code}.json"
    if code == DEFAULT or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def offered() -> list:
    """The languages she can choose: English and every language with a file."""
    return [c for c in LANGS if c == DEFAULT or (DIR / f"{c}.json").exists()]


def match(asked) -> str:
    """The offered language closest to a browser's or a stored one ("zh-TW",
    "zh_HK", "pt-BR", "es-419" …), else English."""
    if not isinstance(asked, str) or not asked.strip():
        return DEFAULT
    a = asked.strip().replace("_", "-").lower()
    have = {c.lower(): c for c in offered()}
    if a in have:
        return have[a]
    if a.startswith("zh"):
        traditional = any(x in a for x in ("hant", "-tw", "-hk", "-mo"))
        want = "zh-hant" if traditional else "zh-hans"
        return have.get(want, have.get("zh-hant" if not traditional else "zh-hans", DEFAULT))
    return have.get(a.split("-")[0], DEFAULT)


def current() -> str:
    """The language this session shows: hers (st.session_state.lang, set from
    her preferences or her choice), else her browser's, else English."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is None:
            return DEFAULT
        chosen = st.session_state.get("lang")
        if chosen in LANGS and chosen in offered():
            return chosen
        return match(st.context.locale)
    except Exception:          # (outside a page: the tests, a background thread)
        return DEFAULT


def tr(text: str, /, **parts) -> str:
    """The sentence in her language (English when it has no translation yet),
    with its {parts} filled in."""
    return tr_in(current(), text, **parts)


def trn(one: str, many: str, n: int, /, **parts) -> str:
    """A sentence about a number: `one` when it is 1, else `many`; {n} is
    the number (each language's file has both, worded its own way)."""
    return tr(one if n == 1 else many, n=n, **parts)


def N_(text: str) -> str:
    """A sentence kept in a constant, marked for translation (tools/i18n.py
    finds it); the page shows it through tr(CONSTANT)."""
    return text


def tr_in(lang: str, text: str, /, **parts) -> str:
    """The sentence in a given language (an email, a background job)."""
    out = catalog(lang).get(text) or text
    if parts:
        try:
            return out.format(**parts)
        except (KeyError, IndexError, ValueError):
            return text.format(**parts)        # a broken translation: the English
    return out


def rtl(lang: str = None) -> bool:
    return LANGS.get(lang or current(), LANGS[DEFAULT])[2]


def name(lang: str) -> str:
    return LANGS.get(lang, LANGS[DEFAULT])[0]


def ai_name(lang: str = None) -> str:
    """What the model is told to write in, in English ("Traditional Chinese")."""
    return LANGS.get(lang or current(), LANGS[DEFAULT])[1]


def texts() -> list:
    """The fixed words kept as data rather than in a tr() call, shown through
    tr(value) where they are drawn: subject names and descriptions, levels,
    days and months (tools/i18n.py lists them with the tr() sentences)."""
    from coach import core, directions, mastery, paths, settings, visuals
    out = list(core.TOPICS.values()) + list(settings.DESCRIPTIONS.values()) + list(core.LEVELS)
    out += list(mastery.LEVEL_NAMES.values()) + list(directions.IDENTITIES) + list(directions.GENERAL_PURPOSES)
    out += list(paths.SUGGESTIONS) + [x for ideas in paths.SUGGESTIONS.values() for x in ideas]
    out += [s[0] for s in paths.STARTS.values()]
    for group, topics in directions.DIRECTIONS.items():
        out += [group] + list(topics) + [x for subs in topics.values() for x in subs]
    out += [x for ps in directions.PURPOSES.values() for x in ps] + [directions.ALL_OF_IT]
    out += [x for pace in settings.PACES.values() for x in pace]
    from coach import plans, reports
    out += list(reports.REASONS.values())
    out += ["Topic", "Key Idea", "Deep Dive", "Example", "Today's Task", "Vocabulary", "Question to Explore", "Note",
            "Check it yourself", "Disclaimer"]
    out += [core.CLOSING_LINE, core.DISCLAIMER]
    out += list(plans.NAMES.values()) + list(plans.BLURBS.values()) + list(plans.EVERY_PLAN)
    out += [w["kicker"] for w in visuals.WORLD.values()] + [w["shows"] for w in visuals.WORLD.values()]
    out += list(WEEKDAYS) + list(MONTHS) + [d[:3] for d in WEEKDAYS] + [m[:3] for m in MONTHS]
    return out


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")


def weekday(d) -> str:
    return tr(WEEKDAYS[d.weekday()])


def month(d, short: bool = False) -> str:
    m = MONTHS[d.month - 1]
    return tr(m[:3] if short else m)


def day_long(d, year: bool = False) -> str:
    """"Wednesday, October 14" (with the year: "Wednesday, October 14, 2026"), in her language."""
    if year:
        return tr("{weekday}, {month} {day}, {year}", weekday=weekday(d), month=month(d), day=d.day, year=d.year)
    return tr("{weekday}, {month} {day}", weekday=weekday(d), month=month(d), day=d.day)


def day_short(d, year: bool = False) -> str:
    """"Oct 14" (or "Oct 14, 2026"), in her language."""
    if year:
        return tr("{month} {day}, {year}", month=month(d, short=True), day=d.day, year=d.year)
    return tr("{month} {day}", month=month(d, short=True), day=d.day)


def date_long(d, year: bool = True) -> str:
    """"October 14, 2026" (or "October 14"), in her language."""
    if year:
        return tr("{month} {day}, {year}", month=month(d), day=d.day, year=d.year)
    return tr("{month} {day}", month=month(d), day=d.day)


def month_year(d) -> str:
    return tr("{month} {year}", month=month(d), year=d.year)


def relative_day(d, today) -> str:
    """"Today", "Tomorrow", else "Wed Oct 14", in her language."""
    k = (d - today).days
    if k == 0:
        return tr("Today")
    if k == 1:
        return tr("Tomorrow")
    return tr("{weekday} {month} {day}", weekday=tr(WEEKDAYS[d.weekday()][:3]), month=month(d, short=True), day=d.day)
