from coach import glass, style


def test_filter_is_there_and_subtle():
    svg = glass.defs()
    assert 'id="lg-refract"' in svg
    assert svg.count("<feDisplacementMap") == 12           # one pass per axis, in each of the six filters
    def filt(fid):
        start = svg.index(f'id="{fid}"')
        return svg[start:svg.index("</filter>", start)]
    for fid in ("lg-refract-dim", "lg-lens-dim", "lg-lens-live-dim"):
        assert '<feMergeNode in="rimlight"/>' not in filt(fid)   # the dark theme's glass gathers no light
    # the lens lies over words: no frost over its middle, only the rim bends
    assert "stdDeviation" not in filt("lg-lens").split('result="bent"')[0]
    assert glass.LENS_SCALE < glass.LENS_LIVE_SCALE <= 20
    assert f'scale="{glass.SCALE}"' in svg and glass.SCALE <= 20  # a subtle bend, at the rim only


def test_centre_stays_clear():
    from urllib.parse import unquote
    for axis in ("x", "y"):
        m = unquote(glass._map(axis))
        assert '<rect width="100%" height="100%" fill="rgb(128,128,128)"/>' in m   # no shift in the middle
        assert f'"{glass.EDGE}"' in m                                             # only a band this wide bends


def test_script_adds_the_filter_once():
    js = glass.script()
    assert "getElementById('lg-defs')" in js and "atob(" in js
    script = js[js.index("<script>"):]
    assert "<svg" not in script and "<filter" not in script  # Streamlit drops a script with tags in it


def test_frost_stays_light():
    import re
    css = style.stylesheet()
    assert "url(#lg-refract)" in css
    # every rule for a chat box (the Reading page gives its own a material to write on)
    rules = re.findall(r"[^{}]*\{[^{}]*\}", css)
    chat = "".join(r for r in rules if "stChatInput" in r.split("{")[0])
    glass_only = "".join(r for r in rules if "stChatInput" not in r.split("{")[0])
    blurs = [float(v) for v in re.findall(r"blur\(([\d.]+)px\)", glass_only)]
    assert blurs and max(blurs) <= 2.5                     # the glass: lightly frosted, never heavy
    # the chat box carries text, so it may get a surface and a controlled blur, not a heavy one
    assert all(float(v) <= 24 for v in re.findall(r"blur\(([\d.]+)px\)", chat))
    assert glass.FROST <= 2 and glass.HAZE <= 4
