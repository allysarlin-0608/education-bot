"""The mathematics object: Euclid I.47 (the squares on a right triangle's
sides), drawn in the manner of Oliver Byrne's coloured Euclid (1847): flat
red, yellow and blue squares with a fine rule, nothing else. Rendered for
this app, one for each theme (the rule dark on light, light on dark), on
nothing, so it stands free on the page.

    python art/pythagoras.py      -> static/subjects/math.webp, math-light.webp"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "static" / "subjects"
W, H, SS = 1000, 1400, 4            # final size, supersampling
RED, YELLOW, BLUE = (204, 51, 43), (242, 183, 5), (31, 78, 158)

# the triangle: hypotenuse BC along the bottom, the right angle at A (3-4-5)
B, C, A = (0.0, 0.0), (5.0, 0.0), (1.8, 2.4)


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


SQUARES = [
    (BLUE, [B, C, (5.0, -5.0), (0.0, -5.0)]),                      # on the hypotenuse
    (RED, [B, A, add(A, (-2.4, 1.8)), add(B, (-2.4, 1.8))]),        # on the short side
    (YELLOW, [A, C, add(C, (2.4, 3.2)), add(A, (2.4, 3.2))]),       # on the long side
]


def render(rule):
    xs = [x for _, pts in SQUARES for x, _ in pts]
    ys = [y for _, pts in SQUARES for _, y in pts]
    span = max(max(xs) - min(xs), (max(ys) - min(ys)) * W / H)
    scale = W * 0.78 / span * SS
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def at(p):
        return (W * SS / 2 + (p[0] - cx) * scale, H * SS / 2 - (p[1] - cy) * scale)

    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for colour, pts in SQUARES:
        d.polygon([at(p) for p in pts], fill=colour + (255,))
    for _, pts in SQUARES:
        d.line([at(p) for p in pts + [pts[0]]], fill=rule + (255,), width=3 * SS, joint="curve")
    d.line([at(p) for p in (B, A, C)], fill=rule + (255,), width=3 * SS, joint="curve")
    return im.resize((W, H), Image.LANCZOS)


if __name__ == "__main__":
    render((236, 236, 236)).save(OUT / "math.webp", "WEBP", quality=92, method=6)
    render((24, 24, 24)).save(OUT / "math-light.webp", "WEBP", quality=92, method=6)
