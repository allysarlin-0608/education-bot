from coach import glass, style


def test_filter_is_there_and_subtle():
    svg = glass.defs()
    assert 'id="lg-refract"' in svg
    assert svg.count("<feDisplacementMap") == 2            # one pass per axis
    assert f'scale="{glass.SCALE}"' in svg and glass.SCALE <= 4   # at most ±2px at the rim


def test_script_adds_the_filter_once():
    js = glass.script()
    assert "getElementById('lg-defs')" in js and "atob(" in js
    script = js[js.index("<script>"):]
    assert "<svg" not in script and "<filter" not in script  # Streamlit drops a script with tags in it


def test_no_frosting_left_in_the_stylesheet():
    css = style.stylesheet()
    assert "blur(" not in css
    assert "url(#lg-refract)" in css
