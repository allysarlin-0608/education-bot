"""Cut an object out of its photograph, so it stands free in the page.

GrabCut, seeded by what is surely the object (bright marble with --lum, the
default; coloured metal on a grey backdrop with --sat) and surely backdrop
(the frame's edges), then a soft edge. --fade dissolves the object's base (a
plinth) into the page. Writes a greyscale WEBP with transparency (with
--preview, also two PNGs beside it: the object on black and on white).

    python art/cutout.py art/src/philosophy.jpg static/subjects/philosophy.webp --fade
    python art/cutout.py art/src/cosmos.jpg static/subjects/cosmos.webp --sat"""
import sys
import cv2
import numpy as np
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
seed = "sat" if "--sat" in sys.argv else "lum"      # what marks the object for sure: brightness or colour
fade = "--fade" in sys.argv                          # dissolve its base (a plinth) into the page
img = cv2.imread(src)
H, W = img.shape[:2]
k = 1000 / max(H, W)
small = cv2.resize(img, (int(W * k), int(H * k)), interpolation=cv2.INTER_AREA)
h, w = small.shape[:2]
lum = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
# the bust sits roughly in the middle; frame edges are backdrop
x0, y0, x1, y1 = int(w * 0.06), int(h * 0.02), int(w * 0.94), int(h * 0.97)
mask[y0:y1, x0:x1] = cv2.GC_PR_FGD
if seed == "lum":
    mask[lum < 38] = cv2.GC_PR_BGD
mask[:, : int(w * 0.04)] = cv2.GC_BGD; mask[:, -int(w * 0.04):] = cv2.GC_BGD; mask[: int(h * 0.01)] = cv2.GC_BGD
sat = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[..., 1]
core = (lum > 150).astype(np.uint8) if seed == "lum" else (sat > 70).astype(np.uint8)
if seed == "sat":
    mask[sat < 22] = cv2.GC_PR_BGD
core = cv2.erode(core, np.ones((5, 5), np.uint8))
mask[core > 0] = cv2.GC_FGD
bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
cv2.grabCut(small, mask, None, bgd, fgd, 8, cv2.GC_INIT_WITH_MASK)
fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
# keep the largest piece, fill its holes
n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
big = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
fg = np.where(lab == big, 255, 0).astype(np.uint8)
if seed == "sat":
    # a shadow on the backdrop is as grey as the backdrop: keep only what lies near colour
    near = cv2.dilate((sat > 45).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
    fg = cv2.bitwise_and(fg, near)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    fg = np.where(lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]), 255, 0).astype(np.uint8)
# fill the holes, but not a real opening (a ring's eye): only small ones
inv = cv2.bitwise_not(fg)
n, lab, stats, _ = cv2.connectedComponentsWithStats(inv)
for i in range(1, n):
    x, y, ww, hh_, area = stats[i]
    touches = x == 0 or y == 0 or x + ww == w or y + hh_ == h
    if not touches and area < 0.0003 * w * h:
        fg[lab == i] = 255
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
# back to full size, a soft edge a few pixels wide, pulled in slightly so no backdrop fringe shows
alpha = cv2.resize(fg, (W, H), interpolation=cv2.INTER_LINEAR)
alpha = cv2.erode(alpha, np.ones((5, 5), np.uint8))
alpha = cv2.GaussianBlur(alpha, (0, 0), 2.2)
grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
out = np.dstack([grey, grey, grey, alpha])
im = Image.fromarray(out, "RGBA")
bbox = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
im = im.crop(bbox)
# the plinth dissolves: the bust stands in the page's own space, not on a block
if fade:
    a = np.asarray(im.getchannel("A")).astype(np.float32)
    hh = a.shape[0]
    ramp = np.clip((0.97 - np.arange(hh) / hh) / (0.97 - 0.80), 0, 1) ** 1.6
    im.putalpha(Image.fromarray((a * ramp[:, None]).astype(np.uint8)))
im.thumbnail((1100, 1400), Image.LANCZOS)
im.save(dst, "WEBP", quality=82, method=6)
print(dst, im.size)
for name, bg in ((("k", 0), ("w", 250)) if "--preview" in sys.argv else ()):
    base = Image.new("RGBA", im.size, (bg, bg, bg, 255)); base.alpha_composite(im)
    base.convert("RGB").resize((im.width // 2, im.height // 2)).save(f"{dst}.on_{name}.png")
