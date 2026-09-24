"""The liquid course progress bar's markup."""
from coach import progress_bar


def test_percent_and_labels():
    html = progress_bar.build("Philosophy: What philosophy is", 5, 7, "Unit lessons 1–7")
    assert 'aria-valuenow="71"' in html and ">71<span class=\"unit\">%" in html
    assert "5 / 7 lessons" in html and "Unit lessons 1–7" in html
    assert "flowing" not in html and "empty" not in html


def test_flows_only_when_the_value_changed():
    assert "flowing" in progress_bar.build("t", 3, 5, previous=40)
    assert "--from:40" in progress_bar.build("t", 3, 5, previous=40)
    assert "flowing" not in progress_bar.build("t", 3, 5, previous=60)


def test_empty_and_escaped():
    html = progress_bar.build("<b>Unit</b> & more", 0, 5)
    assert "empty" in html and "&lt;b&gt;Unit&lt;/b&gt; &amp; more" in html
    assert progress_bar.percent(0, 0) == 0


def test_stylesheet_has_no_stray_angle_brackets():
    # st.html sanitizes its markup: a literal "<number>" inside the CSS reads
    # as a tag and the whole stylesheet is dropped.
    from coach import style
    css = style.stylesheet()
    body = css.split("<style>", 1)[1].rsplit("</style>", 1)[0]
    assert "<" not in body and "lq-liquid" in body


def test_header_only_and_counts():
    html = progress_bar.build("Astronomy: Earth's orbit", 2, 5, bar=False)
    assert ">40<span class=\"unit\">%" in html and "lq-glass" not in html
    assert progress_bar.count(3, 10, "reading day") == "3 / 10 reading days"


def test_lesson_bar_motion(monkeypatch):
    state = {}
    monkeypatch.setattr(progress_bar.st, "session_state", state)
    state["lq_entering"] = True
    assert progress_bar.lesson_motion("d", [True, False, False]) == "flow"   # arriving on the page
    state["lq_entering"] = False
    assert progress_bar.lesson_motion("d", [True, False, False]) == "still"  # e.g. reviewing lesson 1
    assert progress_bar.lesson_motion("d", [True, True, False]) == "tick2"   # lesson 2 just ticked
    assert progress_bar.lesson_motion("d", [True, False, False]) == "still"  # unticked: no fill to play


def test_custom_left_label():
    html = progress_bar.build("No book in progress", 0, 1, "2 books finished", left="Start one on the Reading page")
    assert "<span>Start one on the Reading page</span>" in html and "<span>0 / 1" not in html


def test_vertical_tube_for_today():
    html = progress_bar.build_vertical("Friday, September 25", "Jewelry & Craft", 2, 5, previous=0)
    assert 'class="lqv flowing"' in html and "--to:40;--from:0" in html
    assert "Friday, September 25" in html and "Jewelry &amp; Craft" in html
    assert ">40<span class=\"unit\">%" in html and "2 of 5 lessons today" in html
    empty = progress_bar.build_vertical("Friday", "Jewelry", 0, 5)
    assert "lqv empty" in empty and "flowing" not in empty
    assert "No lessons left to do" in progress_bar.build_vertical("Friday", "Jewelry", 0, 0)
