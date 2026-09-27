"""The reference necklace traced to a 2D blueprint (art/necklace_blueprint.json),
measured, and overlaid on the photograph to check it; necklace.py builds on it.

    python necklace_trace.py REF.png OUTDIR [threshold]

The necklace is found by its texture: the stones' sparkle against the bust's
felt (the image's local Laplacian, blurred, thresholded, closed, its largest
piece, holes filled). Row by row the mask gives each side's run; where the two
runs meet is the V; below it, the narrowest row is the bail; below that, the
drop. Each side's centreline is a quintic fitted to its runs' mid-points
(outliers dropped), its band width a cubic. Along each line, stations every
0.42 band-widths (the stones are laid at them). Written with it: the points of
record, normalized to the photograph (x / width, y / height), a blueprint
drawing, and the drawing overlaid on the photograph at 50%."""
import json
import math
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

ref_path, out = sys.argv[1], sys.argv[2]
T = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
img = cv2.imread(ref_path)
H, W = img.shape[:2]
g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
tex = cv2.GaussianBlur(np.abs(cv2.Laplacian(cv2.GaussianBlur(g, (3, 3), 0), cv2.CV_32F)), (0, 0), 4)
m = (tex > T).astype(np.uint8) * 255
m[:, : int(W * 0.14)] = 0                                   # the blurred shop behind the bust
m[:, int(W * 0.92):] = 0
m[: int(H * 0.14)] = 0
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
m = np.where(lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]), 255, 0).astype(np.uint8)
cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
mask = np.zeros_like(m)
cv2.drawContours(mask, cnts, -1, 255, -1)

rows = {}
for y in range(H):
    xs = np.nonzero(mask[y])[0]
    if len(xs):
        runs = np.split(xs, np.where(np.diff(xs) > 1)[0] + 1)
        rows[y] = [(int(r[0]), int(r[-1])) for r in runs if len(r) > 2]
ys = sorted(y for y in rows if rows[y])
top, bottom = ys[0], ys[-1]
# the V: the first row, going down, where the two sides are one run
two = [y for y in ys if len(rows[y]) >= 2]
v_y = max(y for y in two if y < top + 0.8 * (bottom - top))
# the bail: the narrowest row between the V and the drop's widest
span = lambda y: (rows[y][0][0], rows[y][-1][1])
width = lambda y: span(y)[1] - span(y)[0]
below = [y for y in ys if y > v_y + 10]
widest = max(below, key=width)
bail_y = min((y for y in below if y < widest), key=width)


def side(which):
    A = []
    for y in range(top, v_y):
        r = rows.get(y)
        if r and len(r) >= 2:
            A.append((y, *(r[0] if which == "L" else r[-1])))
    A = np.array(A, float)
    y, mid, w = A[:, 0], (A[:, 1] + A[:, 2]) / 2, A[:, 2] - A[:, 1]
    keep = np.ones(len(y), bool)
    for _ in range(3):
        c = np.polyfit(y[keep], mid[keep], 5)
        res = mid - np.polyval(c, y)
        keep = np.abs(res) < 2.5 * res[keep].std() + 1
    cw = np.polyfit(y[keep], w[keep], 3)
    err = np.abs(mid[keep] - np.polyval(c, y[keep]))
    return dict(cx=c, cw=cw, y0=float(y[keep].min()), y1=float(y[keep].max()), err=(float(err.max()), float(err.mean())))


S = {k: side(k) for k in "LR"}
for k, s in S.items():
    print(k, "fit error max/mean px %.1f / %.1f" % s["err"], "rows %d..%d" % (s["y0"], s["y1"]))


def line(s, n=600):
    yy = np.linspace(s["y0"], s["y1"], n)
    c = np.stack([np.polyval(s["cx"], yy), yy], 1)
    d = np.gradient(c, axis=0)
    ang = np.arctan2(d[:, 1], d[:, 0])
    across = np.polyval(s["cw"], yy) * np.abs(np.sin(ang))       # the run is horizontal; the band is slanted
    return c, ang, across


# stations along each line, every half band-width, from the V up to the neck
stations = []
for k in "LR":
    c, ang, wd = line(S[k])
    c, ang, wd = c[::-1], ang[::-1], wd[::-1]                 # from the V upward
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    at = 0.0
    while True:
        i = int(np.searchsorted(seg, at))
        if i >= len(c):
            break
        stations.append((k, float(c[i][0]), float(c[i][1]), float(ang[i]), float(max(wd[i], 4.0))))
        at += max(wd[i], 4.0) * 0.42

stem = [(y, *span(y)) for y in range(v_y, bail_y + 1) if y in rows and rows[y]]
drop = [(y, *span(y)) for y in range(bail_y + 1, bottom + 1) if y in rows and rows[y]]
dw = max(drop, key=lambda t: t[2] - t[1])
cx = float(np.mean([(a + b) / 2 for _, a, b in stem]))
print("V at row", v_y, " bail at row", bail_y, " drop rows %d..%d, width %d at row %d, length/width %.2f, widest at %.0f%%"
      % (drop[0][0], drop[-1][0], dw[2] - dw[1], dw[0], (drop[-1][0] - drop[0][0]) / (dw[2] - dw[1]),
         100 * (dw[0] - drop[0][0]) / (drop[-1][0] - drop[0][0])))

Lc, Rc = line(S["L"])[0], line(S["R"])[0]
pts = {"P1 left upper end": Lc[0], "P2 left descending": Lc[200], "P3 left lower": Lc[450], "P4 left convergence": Lc[-1],
       "P5 centre": np.array([cx, v_y]), "P6 right convergence": Rc[-1], "P7 right lower": Rc[450],
       "P8 right descending": Rc[200], "P9 right upper end": Rc[0], "connector centre": np.array([cx, (v_y + bail_y) / 2]),
       "pendant top": np.array([(drop[0][1] + drop[0][2]) / 2, drop[0][0]]), "pendant leftmost": np.array([dw[1], dw[0]]),
       "pendant rightmost": np.array([dw[2], dw[0]]), "pendant lowest": np.array([(drop[-1][1] + drop[-1][2]) / 2, drop[-1][0]])}
norm = {k: [round(float(v[0]) / W, 4), round(float(v[1]) / H, 4)] for k, v in pts.items()}
for k, v in norm.items():
    print("%-22s x=%.4f y=%.4f" % (k, *v))


def draw(canvas, col, width=2, detail=True):
    d = ImageDraw.Draw(canvas)
    for k in "LR":
        c, ang, wd = line(S[k])
        nx, ny = -np.sin(ang), np.cos(ang)
        for sg in (1, -1):
            d.line([(x + sg * a * w / 2, y + sg * b * w / 2) for (x, y), a, b, w in zip(c, nx, ny, wd)], fill=col, width=width)
    if detail:
        for k, x, y, a, w in stations:
            r = w * 0.27
            d.ellipse((x - r, y - r, x + r, y + r), outline=col, width=1)
    d.line([(a, y) for y, a, b in stem] + [(b, y) for y, a, b in stem][::-1], fill=col, width=width)
    d.line([(a, y) for y, a, b in drop] + [(b, y) for y, a, b in drop][::-1] + [(drop[0][1], drop[0][0])], fill=col, width=width)


bp = Image.new("RGB", (W, H), "white")
draw(bp, (20, 20, 20))
for v in pts.values():
    ImageDraw.Draw(bp).ellipse((v[0] - 5, v[1] - 5, v[0] + 5, v[1] + 5), outline=(200, 0, 0), width=2)
bp.save(f"{out}/blueprint.png")
ref = Image.open(ref_path).convert("RGB")
Image.blend(ref, bp, 0.5).save(f"{out}/overlay.png")
chk = ref.copy()
draw(chk, (230, 20, 20), 3, detail=False)
chk.save(f"{out}/check.png")
json.dump({"px": [W, H], "points_px": {k: [float(v[0]), float(v[1])] for k, v in pts.items()}, "normalized": norm,
           "sides": {k: {"cx": s["cx"].tolist(), "cw": s["cw"].tolist(), "y0": s["y0"], "y1": s["y1"]} for k, s in S.items()},
           "stations": stations, "stem": stem, "drop": drop, "v_y": v_y, "bail_y": bail_y,
           "frame": [int(min(Lc[:, 0].min(), dw[1]) - 25), int(max(Rc[:, 0].max(), dw[2]) + 25), top - 25, bottom + 25]},
          open(f"{out}/blueprint.json", "w"))
print("stations", sum(1 for s in stations if s[0] == "L"), sum(1 for s in stations if s[0] == "R"))
