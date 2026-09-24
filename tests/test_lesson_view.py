"""Lessons with tables and ```dot diagrams."""
from coach import lesson_view

LESSON = """【重點解析】：
**大小**：很大。

```dot
digraph G { 恆星 -> 紅巨星 [color=red]; 紅巨星 -> 白矮星; node [style=filled, fillcolor="#ff0000"]; }
```

| 類型 | 特徵 |
|---|---|
| A | 1 |

完成後記得打勾，連續完成比完美更重要。"""


def test_split_keeps_order_of_text_and_diagrams():
    parts = lesson_view.split(LESSON)
    assert [k for k, _ in parts] == ["md", "dot", "md"]
    assert parts[1][1].startswith("digraph G {")
    assert "| 類型 | 特徵 |" in parts[2][1]


def test_diagrams_are_drawn_in_grays_whatever_the_model_asked_for():
    dot = lesson_view.styled(lesson_view.split(LESSON)[1][1], dark=True)
    assert "red" not in dot and "#ff0000" not in dot and "filled" not in dot
    assert 'bgcolor="transparent"' in dot and 'fontcolor="#EDEDED"' in dot
    light = lesson_view.styled("digraph { a -> b }", dark=False)
    assert 'fontcolor="#1A1A1A"' in light and light.startswith("digraph {")


def test_broken_diagrams_are_skipped():
    assert lesson_view.styled("a -> b", dark=True) is None
    assert lesson_view.styled("digraph { a -> b", dark=True) is None
    assert lesson_view.styled("digraph { a -> { b }", dark=True) is None


def test_a_lesson_without_diagrams_is_one_markdown_part():
    assert lesson_view.split("只有文字\n\n| a | b |\n|---|---|") == [("md", "只有文字\n\n| a | b |\n|---|---|")]


def test_blocks_become_cards_without_brackets():
    text = ("Intro line.\n【Topic】 The orbit\n\n**【Key Idea】**: Tilt makes seasons.\n"
            "### 【Deep Dive】\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    parts = lesson_view.blocks(text)
    assert [t for t, _ in parts] == ["", "Topic", "Key Idea", "Deep Dive"]
    assert parts[2][1].strip() == "Tilt makes seasons."
    assert "【" not in "".join(body for _, body in parts)
    assert lesson_view.blocks("No blocks here.") == [("", "No blocks here.")]


def test_the_same_lesson_can_be_shown_twice_on_a_page(tmp_path):
    from streamlit.testing.v1 import AppTest
    script = tmp_path / "twice.py"
    script.write_text(
        "from coach import lesson_view\n"
        "text = '【Topic】 Gold\\n\\n【Key Idea】 24K is soft.'\n"
        "lesson_view.render(text, 'jewelry', key='2026-09-18_jewelry_3')\n"
        "lesson_view.render(text, 'jewelry', key='2026-09-25_jewelry_3')\n")
    at = AppTest.from_file(str(script)).run()
    assert not at.exception
