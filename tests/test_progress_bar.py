"""The liquid course progress bar's markup."""
from coach import progress_bar


def test_percent_and_labels():
    html = progress_bar.build("Philosophy: What philosophy is", 5, 7, "Unit lessons 1–7")
    assert 'aria-valuenow="71"' in html and ">71<span>%" in html
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
