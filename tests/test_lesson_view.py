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
