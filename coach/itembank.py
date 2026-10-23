"""Checked questions shared by every learner (docs/LEARNING_DESIGN.md §10;
table shared_items, supabase/learning_v2.sql): the mathematics
curriculum's diagnostic questions, one per unit and language, written once
and kept, so each learner after the first costs no AI call for them.

Only questions that passed the checking call go in. A question two people
report is no longer given out (the table's function counts each person
once). Where the table isn't there yet (or the store has no bank: the
personal app), questions are simply written for her and kept with her
result: nothing fails, it only costs what it did before."""
import logging

import streamlit as st

from coach import errors, quiz

logger = logging.getLogger("coach.itembank")
MATH = "math-zero-to-research-zh-hant"     # the curriculum file's id


def _store():
    store = st.session_state.get("coach_store")
    return store if hasattr(store, "shared_items") else None


def get(curriculum: str, lang: str, units: list) -> dict:
    """{unit: (question, id)} for these units, as the bank has them now."""
    store = _store()
    if store is None or not units:
        return {}
    try:
        rows = store.shared_items(curriculum, lang, list(units))
    except errors.StorageError as e:
        logger.info("the shared questions couldn't be read (%s)", e)
        return {}
    out = {}
    for r in rows if isinstance(rows, list) else []:
        q = quiz._saved_question((r or {}).get("item"))
        if q and r.get("unit") in units and r["unit"] not in out:
            out[r["unit"]] = (q, r.get("id"))
    return out


def add(curriculum: str, lang: str, found: dict) -> None:
    """Checked questions, {unit: question}, into the bank for everyone."""
    store = _store()
    if store is None or not found:
        return
    try:
        store.add_shared_items(curriculum, lang, [{"unit": u, "item": q} for u, q in found.items()])
    except errors.StorageError as e:
        logger.info("the shared questions couldn't be saved (%s)", e)


def report(item_id) -> None:
    store = _store()
    if store is None or item_id is None:
        return
    try:
        store.report_shared_item(int(item_id))
    except (errors.StorageError, ValueError) as e:
        logger.info("the shared question couldn't be reported (%s)", e)
