"""Rolling numbers: when a number on the page changes, its digits roll
vertically from the old value to the new one, like a physical counter.

Pure HTML + CSS (st.html strips scripts): each digit is a clipped window
over a vertical strip (blank, 0-9, 0-9, drawn by CSS so the page text is
just the number), and only the digits whose value
changed move, from the old position to the new one (CSS in style.py).
Separators (".", ",", "%", "/", spaces, words) never move. The width is the
new number's from the start, with tabular numerals, so nothing around it
shifts."""
import re
from html import escape

NUMBER = re.compile(r"\d[\d,.]*\d|\d")
BLANK = 0            # strip index of the empty slot above the digits


def _numbers(text: str) -> list:
    return NUMBER.findall(text or "")


def _value(token: str) -> float:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return 0.0


def _digits(new: str, old: str) -> str:
    """One number, digit by digit, right-aligned against the old one."""
    width = max(len(new), len(old))
    new_p, old_p = new.rjust(width), old.rjust(width)
    up = _value(new) >= _value(old)
    out = []
    for n, o in zip(new_p, old_p):
        if n == " ":
            continue                         # the new number is shorter: nothing to show here
        if not n.isdigit():
            out.append(f'<span class="rd-sep">{escape(n)}</span>')   # "." and "," stay put
            continue
        if o == n:
            out.append(f'<span class="rd-still">{n}</span>')   # unchanged digits stay still
            continue
        a = int(o) + 1 if o.isdigit() else BLANK
        b = int(n) + 1
        if a != BLANK and up and b < a:
            b += 10                          # 9 → 0 going up rolls on through, like a counter
        elif a != BLANK and not up and b > a:
            a += 10                          # going down rolls back the other way
        # the real digit is the text (it's what gets read and copied); the
        # strip is drawn by CSS (.rd-d::before), so it adds nothing to the page text
        out.append(f'<span class="rd-d" style="--a:{a};--b:{b}">{n}</span>')
    return "".join(out)


def html(new: str, old=None) -> str:
    """`new` as HTML, its numbers rolling from `old` when they differ. With
    no old value, or a different shape of text, it is shown as is."""
    new = str(new)
    if old is None or str(old) == new:
        return escape(new)
    new_nums, old_nums = _numbers(new), _numbers(str(old))
    if not new_nums or len(new_nums) != len(old_nums):
        return escape(new)
    out, pos = [], 0
    for m, old_token in zip(NUMBER.finditer(new), old_nums):
        out.append(escape(new[pos:m.start()]))
        token = m.group()
        out.append(escape(token) if token == old_token else
                   f'<span class="rd rolling">{_digits(token, old_token)}</span>')
        pos = m.end()
    out.append(escape(new[pos:]))
    return "".join(out)


def zeroed(text) -> str:
    """The same text with every number at 0, to count up from on arrival."""
    return NUMBER.sub("0", str(text))


def remember(store: dict, key: str, **texts) -> dict:
    """The texts last shown under `key` (empty the first time), and keep
    these new ones for next time."""
    old = store.get(key, {})
    store[key] = texts
    return old
