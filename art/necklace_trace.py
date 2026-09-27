"""The reference necklace traced to a 2D blueprint (art/necklace_blueprint.json),
measured, and overlaid on the photograph to check it (necklace.py builds on it).

Run where the reference photograph (ref.jpg) and its mask rows (rows.json: for
each image row, the runs of the necklace's mask) are: the mask is the photo's
local texture (the stones' sparkle against the bust's felt), thresholded,
closed, its largest piece. Each side's centreline is a quintic fitted to the
mid-points of its runs (outliers dropped), its band width a cubic; the links
are laid end to end along the line, each 1.25 band-widths long, overlapping a
little as the reference's do."""
import json, math
import numpy as np, cv2
from PIL import Image, ImageDraw
rows = {int(k): v for k, v in json.load(open('rows.json')).items()}
W, H = 1200, 1604

def side(which):
    A = []
    for y in range(340, 890):
        r = rows.get(y)
        if not r: continue
        if len(r) >= 2: A.append((y, *(r[0] if which == 'L' else r[-1])))
        elif which == 'L' and y < 450: A.append((y, *r[0]))
    A = np.array(A, float); y = A[:, 0]; mid = (A[:, 1] + A[:, 2]) / 2; w = A[:, 2] - A[:, 1]
    keep = np.ones(len(y), bool)
    for _ in range(3):
        c = np.polyfit(y[keep], mid[keep], 5); r_ = mid - np.polyval(c, y)
        keep = np.abs(r_) < 2.5 * r_[keep].std() + 1
    cw = np.polyfit(y[keep], w[keep], 3)
    err = np.abs(mid[keep] - np.polyval(c, y[keep]))
    return dict(cx=c, cw=cw, y0=y[keep].min(), y1=y[keep].max(), err=(err.max(), err.mean()))

S = {'L': side('L'), 'R': side('R')}
for k, s in S.items(): print(k, 'fit err max/mean px %.1f / %.1f' % s['err'], 'y %d..%d' % (s['y0'], s['y1']))

def centerline(s, n=200):
    ys = np.linspace(s['y0'], s['y1'], n); xs = np.polyval(s['cx'], ys)
    return np.stack([xs, ys], 1)

def perp_width(s, pts):
    """horizontal run width -> width across the band (the band is slanted)"""
    d = np.gradient(pts, axis=0); ang = np.arctan2(d[:, 1], d[:, 0])
    return np.polyval(s['cw'], pts[:, 1]) * np.abs(np.sin(ang)), ang

# ---- the centre and the drop, from the mask rows
def span(y): r = rows.get(y); return (r[0][0], r[-1][1]) if r else None
stem = [(y, *span(y)) for y in range(890, 1004) if span(y)]
drop = [(y, *span(y)) for y in range(1004, 1292) if span(y)]
neck_y = min(stem, key=lambda t: t[2] - t[1] if t[0] > 975 else 1e9)[0]
drop_top, drop_bot = drop[0][0], drop[-1][0]
wid = max(drop, key=lambda t: t[2] - t[1]); drop_w = wid[2] - wid[1]
print('neck (bail) y', neck_y, ' drop top/bottom', drop_top, drop_bot, ' drop width %d at y %d' % (drop_w, wid[0]),
      ' length/width %.2f' % ((drop_bot - drop_top) / drop_w))

# ---- points of record, normalized to the image (x / width, y / height)
Lc, Rc = centerline(S['L']), centerline(S['R'])
pts = {'P1 left upper end': Lc[0], 'P2 left descending': Lc[60], 'P3 left lower': Lc[140], 'P4 left convergence': Lc[-1],
       'P6 right convergence': Rc[-1], 'P7 right lower': Rc[140], 'P8 right descending': Rc[60], 'P9 right upper end': Rc[0]}
cx_stem = np.mean([(a + b) / 2 for _, a, b in stem])
pts['P5 centre'] = np.array([cx_stem, 890.0])
pts['connector centre'] = np.array([cx_stem, (890 + neck_y) / 2])
pts['pendant top'] = np.array([(drop[0][1] + drop[0][2]) / 2, drop_top])
pts['pendant leftmost'] = np.array([wid[1], wid[0]]); pts['pendant rightmost'] = np.array([wid[2], wid[0]])
pts['pendant lowest'] = np.array([(drop[-1][1] + drop[-1][2]) / 2, drop_bot])
norm = {k: [round(float(v[0]) / W, 4), round(float(v[1]) / H, 4)] for k, v in pts.items()}
for k, v in norm.items(): print('%-22s x=%.4f y=%.4f' % (k, *v))

# ---- the blueprint drawing (level 1 silhouette + level 2 structure)
def draw(canvas, col, width=2, structure=True):
    d = ImageDraw.Draw(canvas)
    links = []
    for key in 'LR':
        s = S[key]; c = centerline(s, 400); pw, ang = perp_width(s, c)
        nx, ny = -np.sin(ang), np.cos(ang)
        e1 = [(x + a * w / 2, y + b * w / 2) for (x, y), a, b, w in zip(c, nx, ny, pw)]
        e2 = [(x - a * w / 2, y - b * w / 2) for (x, y), a, b, w in zip(c, nx, ny, pw)]
        d.line(e1, fill=col, width=width); d.line(e2, fill=col, width=width)
        if structure:
            # cluster links: each about 1.25 x the band's width, end to end along the centerline
            seg = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
            at = 0.0
            while True:
                i = np.searchsorted(seg, at); 
                if i >= len(c): break
                L = 1.25 * pw[i]
                j = np.searchsorted(seg, at + L / 2)
                if j >= len(c): break
                x, y = c[j]; a = ang[j]
                links.append((key, float(x), float(y), float(a), float(L), float(pw[j])))
                # the link: an oval, its centre stone
                poly = [(x + math.cos(a) * L / 2 * math.cos(t) - math.sin(a) * pw[j] / 2 * 0.92 * math.sin(t),
                         y + math.sin(a) * L / 2 * math.cos(t) + math.cos(a) * pw[j] / 2 * 0.92 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40)]
                d.line(poly + [poly[0]], fill=col, width=1)
                r = pw[j] * 0.22; d.ellipse((x - r, y - r, x + r, y + r), outline=col, width=1)
                at += L * 0.86
    # the centre: the convergence block and the marquise-shaped setting, the bail
    stem_pts_l = [(a, y) for y, a, b in stem]; stem_pts_r = [(b, y) for y, a, b in stem][::-1]
    d.line(stem_pts_l, fill=col, width=width); d.line(stem_pts_r, fill=col, width=width)
    if structure:
        my0, my1 = 925, neck_y - 4; mcx = cx_stem; mw = max(b - a for y, a, b in stem if my0 < y < my1)
        mq = [(mcx + mw / 2 * math.sin(math.pi * t) * (1 if k == 0 else -1), my0 + (my1 - my0) * t) for k in (0, 1) for t in (np.linspace(0, 1, 30) if k == 0 else np.linspace(1, 0, 30))]
        d.line(mq + [mq[0]], fill=col, width=1)
        d.ellipse((mcx - 6, neck_y - 6, mcx + 6, neck_y + 6), outline=col, width=1)
    # the drop
    dl = [(a, y) for y, a, b in drop]; dr = [(b, y) for y, a, b in drop][::-1]
    d.line(dl + dr + [dl[0]], fill=col, width=width)
    if structure:
        tx, ty = (wid[1] + wid[2]) / 2, wid[0]; d.ellipse((tx - drop_w * 0.28, ty - drop_w * 0.45, tx + drop_w * 0.28, ty + drop_w * 0.2), outline=col, width=1)
    return links

bp = Image.new('RGB', (W, H), 'white'); links = draw(bp, (20, 20, 20))
for k, v in pts.items(): ImageDraw.Draw(bp).ellipse((v[0] - 5, v[1] - 5, v[0] + 5, v[1] + 5), outline=(200, 0, 0), width=2)
bp.save('blueprint.png')
ref = Image.open('ref.jpg').convert('RGB')
Image.blend(ref, bp, 0.5).save('overlay.png')
# a crisp check: the traced silhouette in red over the reference
chk = ref.copy(); draw(chk, (230, 20, 20), 3, structure=False); chk.save('check.png')
json.dump({'points_px': {k: [float(v[0]), float(v[1])] for k, v in pts.items()}, 'normalized': norm,
           'sides': {k: {'cx': s['cx'].tolist(), 'cw': s['cw'].tolist(), 'y0': s['y0'], 'y1': s['y1']} for k, s in S.items()},
           'stem': stem, 'drop': drop, 'neck_y': neck_y, 'links': links, 'px': [W, H]}, open('blueprint.json', 'w'))
print('links per side', sum(1 for l in links if l[0] == 'L'), sum(1 for l in links if l[0] == 'R'))
