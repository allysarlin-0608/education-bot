"""What a lesson shows (coach/lesson_view.sections, ISS-102): no section
with nothing in it (the "Disclaimer" heading left empty once its line became
the footnote), a disclaimer only once and only as a footnote, and the Topic
section (the title again) shown only as the lesson's level."""
from coach import core, lesson_view

LESSON = f"""【Topic】: The purpose of investing versus saving (Beginner)
【Key Idea】: Saving keeps money safe; investing helps it grow over years.
【Deep Dive】:
**Time**: money for 5+ years can be invested.
【Example】:
【Disclaimer】:
{core.DISCLAIMER}
{core.CLOSING_LINE}"""


def test_no_empty_sections_and_one_disclaimer_as_a_footnote():
    parts, level, footer = lesson_view.sections(LESSON)
    assert [h for h, _ in parts] == ["Key Idea", "Deep Dive"], "Example and Disclaimer had nothing in them"
    assert level == "Beginner", "the Topic section: its level, not the title again"
    assert footer == [core.DISCLAIMER, core.CLOSING_LINE]


def test_a_disclaimer_section_in_the_models_words_is_a_footnote_once():
    text = ("【Key Idea】: X.\n【Disclaimer】: This is for learning only and is not financial advice.\n"
            f"{core.DISCLAIMER}\n{core.CLOSING_LINE}")
    parts, _, footer = lesson_view.sections(text)
    assert [h for h, _ in parts] == ["Key Idea"]
    assert footer == [core.DISCLAIMER, core.CLOSING_LINE], "never two disclaimers"
    parts, _, footer = lesson_view.sections("【Key Idea】: X.\n【Important notice】: Prices can fall.\n")
    assert [h for h, _ in parts] == ["Key Idea"] and footer == ["Prices can fall."]


def test_older_lessons_keep_working():
    parts, level, footer = lesson_view.sections("【今日主題】：哲學（入門）\n【核心概念】：控制二分法。")
    assert level == "Beginner" and [h for h, _ in parts] == ["核心概念"] and footer == []
    parts, level, _ = lesson_view.sections("Just some text without sections.")
    assert parts == [("", "Just some text without sections.")] and level == ""
