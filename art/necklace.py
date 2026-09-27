"""The jewellery subject's object: a high-jewellery diamond necklace, modelled
and rendered as a studio photograph of a real piece, floating on nothing.

The design is the reference photograph's (a V necklace on a display bust),
traced first and built second: art/necklace_trace.py turns the photograph into
a 2D blueprint (art/necklace_blueprint.json: each side's centreline and band
width with stations along it, the V, the stem to the bail, the drop's
outline), checked by overlaying it on the photograph; this script builds on
that blueprint in the plane the camera looks at square on, so the render lies
on the photograph's necklace. Along each side, princess-cut (square)
diamonds two abreast, each on its own collet with claws at its corners, their
edges square to the traced line, each turned a degree or two its own way; at
the V a princess set on its point, then a pear point up to the bail; the drop as traced, twice as
long as it is wide, widest at 64%.

Units are millimetres. Every stone is a faceted solid (a round brilliant's
table, star, bezel, upper and lower girdle and pavilion facets; the pear and
the marquise are the same brilliant drawn out to their outline), glass at
diamond's index 2.417, roughness 0.01, rendered once per colour channel at
the C, d and F lines (Abbe number 55). Each stone sits in its own collet with
claws over its edge (a V claw at a point); jump rings join the centre, the
marquise and the drop. Platinum, roughness about 0.12, barely varying.

No ground, no shadow. Two renders: for the dark theme, a dark studio lit by
three large soft sources (key, fill, rim at 1 : 0.2 : 0.15) with black flags,
the film and the glass transparent so the dark page shows through the stones
(transparent, and dark); for the light theme (--light), a white light box
with the same flags, the stones white on the white page.

Run with Blender's Python module (pip install bpy==4.2.0 numpy pillow, Python 3.11):

    python art/necklace.py jewelry.png 1600 96
    python art/necklace.py jewelry-light.png 1600 96 --light
    then: Image.open("jewelry.png").save("static/subjects/jewelry.webp", quality=88, method=6)

    python necklace.py OUT.png [height] [samples] [--mono] [--light] [--backdrop GREY]"""
import math
import random
import sys

import bpy
import bmesh  # after bpy: it is part of Blender's module
from mathutils import Matrix, Vector

out = sys.argv[1]
size = int(sys.argv[2]) if len(sys.argv) > 2 else 900
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 160
rng = random.Random(11)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- materials ----------
gem = bpy.data.materials.new("diamond")
gem.use_nodes = True
gn = gem.node_tree.nodes
gn.clear()
# diamond: fully transmissive (1.0), index 2.417 (set per colour channel below,
# Abbe number 55), facets polished to 0.01, colourless. Its dark facets come from
# what it reflects and refracts (the dark studio), never from lowered transmission.
# (Cycles' glass BSDF: a dielectric with full transmission and Fresnel
# reflection; the only transmissive material Cycles lets show the page through)
glass = gn.new("ShaderNodeBsdfGlass")
glass.distribution = "GGX"
glass.inputs["Color"].default_value = (1, 1, 1, 1)
glass.inputs["Roughness"].default_value = 0.005                  # facets optically crisp
glass.inputs["IOR"].default_value = 2.417
gem.node_tree.links.new(glass.outputs[0], gn.new("ShaderNodeOutputMaterial").inputs["Surface"])

metal = bpy.data.materials.new("platinum")
metal.use_nodes = True
mn, ml = metal.node_tree.nodes, metal.node_tree.links
pb = mn["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.74, 0.73, 0.71, 1)      # platinum: neutral, near white
pb.inputs["Metallic"].default_value = 1.0
tc = mn.new("ShaderNodeTexCoord")
noise = mn.new("ShaderNodeTexNoise")          # roughness that varies, as polishing leaves it
noise.inputs["Scale"].default_value = 0.6
noise.inputs["Detail"].default_value = 6.0
ml.new(tc.outputs["Object"], noise.inputs["Vector"])
rough = mn.new("ShaderNodeMapRange")
rough.inputs["To Min"].default_value, rough.inputs["To Max"].default_value = 0.1, 0.15      # about 0.12, barely varying
ml.new(noise.outputs["Fac"], rough.inputs["Value"])
ml.new(rough.outputs[0], pb.inputs["Roughness"])
wave = mn.new("ShaderNodeTexWave")            # micro-roughness in the surface, barely there (new, not worn)
wave.inputs["Scale"].default_value = 5.0
wave.inputs["Distortion"].default_value = 14.0
ml.new(tc.outputs["Object"], wave.inputs["Vector"])
bump = mn.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.012
ml.new(wave.outputs["Fac"], bump.inputs["Height"])
ml.new(bump.outputs["Normal"], pb.inputs["Normal"])


# ---------- the cuts ----------
def brilliant_points():
    """A round brilliant of radius 1 (diameter 2), table up: 57% table, 15% crown,
    43% pavilion, a thin girdle; its facets are the convex hull of these points.
    Cut plainly: sixteen girdle points and no lower-girdle facets, so each facet
    is large enough to carry one clean reflection (a table, eight stars, eight
    bezels and sixteen upper-girdle facets above; sixteen long pavilion facets
    below), not a mosaic."""
    pts = []
    rt = 0.57 / math.cos(math.radians(22.5))
    for k in range(8):                                       # the table
        a = math.radians(45 * k)
        pts.append((rt * math.cos(a), rt * math.sin(a), 0.32))
    for k in range(8):                                       # the star facets' points
        a = math.radians(45 * k + 22.5)
        pts.append((0.79 * math.cos(a), 0.79 * math.sin(a), 0.178))
    for k in range(16):                                      # the girdle, both edges
        a = math.radians(22.5 * k)
        pts += [(math.cos(a), math.sin(a), 0.02), (math.cos(a), math.sin(a), -0.02)]
    pts.append((0, 0, -0.88))                                # the culet
    return pts


def vesica(ux, uy, lh):
    """Distance to the outline of a marquise (half-width 1, half-length lh) along (ux, uy)."""
    d = (lh * lh - 1) / 2
    rho = d + 1
    x = -abs(ux)
    return d * x + math.sqrt(d * d * x * x + rho * rho - d * d)


def outline(shape, lh):
    if shape == "round":
        return lambda ux, uy: 1.0
    if shape == "square":           # a princess cut: square, its corners barely softened (a superellipse, p = 12)
        return lambda ux, uy: (abs(ux) ** 12 + abs(uy) ** 12) ** (-1 / 12)
    if shape == "marquise":
        return lambda ux, uy: vesica(ux, uy, lh)
    if shape == "pear2":            # the reference's drop: point up, its lower part a half-ellipse (widest at 55%)
        low = PEAR_LOW
        return lambda ux, uy: 1.0 / math.sqrt(ux * ux + (uy / low) ** 2) if uy <= 0 else vesica(ux, uy, lh)
    return lambda ux, uy: 1.0 if uy <= 0 else vesica(ux, uy, lh)          # pear: point up


PEAR_LOW = 1.62


def princess_points():
    """A princess cut, half-width 1: a square table (70%), a crown of two steps,
    a thin girdle with its corners barely chamfered, and a pavilion of one row
    of chevrons (a square ring crossed by one turned 45 degrees) down to a
    culet; 73% deep. Few facets, each large: a square stone reads as square,
    a table and a few bright and dark planes."""
    pts = []

    def sq(h, z, c=0.0):
        for sx in (-1, 1):
            for sy in (-1, 1):
                pts.extend([(sx * (h - c), sy * h, z), (sx * h, sy * (h - c), z)] if c else [(sx * h, sy * h, z)])

    def mid(h, z):
        pts.extend([(h, 0, z), (-h, 0, z), (0, h, z), (0, -h, z)])

    sq(0.70, 0.17)                                  # the table
    sq(0.86, 0.10, 0.03)                            # the crown's step
    sq(1.0, 0.012, 0.05)                            # the girdle, both edges
    sq(1.0, -0.012, 0.05)
    mid(0.98, 0.10)                                 # the crown's kite facets, from the sides' middles
    sq(0.55, -0.36, 0.03)                           # the pavilion: one square ring...
    mid(0.62, -0.34)                                # ...crossed by one turned 45 degrees: a single row of chevrons
    pts.append((0, 0, -0.73))                       # the culet
    return pts


def stone_mesh(shape="round", lh=1.0):
    """A cut as a mesh: its points, then their hull (a round brilliant drawn out
    to its outline for the round, pear and marquise; the princess its own)."""
    f = outline(shape, lh)
    bm = bmesh.new()
    if shape == "square":
        for p in princess_points():
            bm.verts.new(p)
        bmesh.ops.convex_hull(bm, input=bm.verts)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.6), verts=bm.verts, edges=bm.edges)
        me = bpy.data.meshes.new("princess")
        bm.to_mesh(me)
        me.materials.append(gem)
        return me
    for x, y, z in brilliant_points():
        r = math.hypot(x, y)
        s = f(x / r, y / r) if r > 1e-9 else 1.0
        bm.verts.new((x * s, y * s, z))
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.6), verts=bm.verts, edges=bm.edges)
    me = bpy.data.meshes.new(f"{shape}")
    bm.to_mesh(me)
    me.materials.append(gem)
    return me


MESHES = {}


def cut(shape, lh=1.0):
    key = (shape, round(lh, 3))
    if key not in MESHES:
        MESHES[key] = stone_mesh(shape, lh)
    return MESHES[key]


def frame(pos, normal, up):
    """A matrix placing a stone's table facing `normal`, its length along `up`."""
    z = normal.normalized()
    y = (up - z * up.dot(z)).normalized()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = pos
    return m


def place(shape, lh, half_w, pos, normal, up):
    """A stone of half-width half_w (mm), with its collet and claws."""
    o = bpy.data.objects.new(shape, cut(shape, lh))
    scene.collection.objects.link(o)
    m = frame(pos, normal, up) @ Matrix.Diagonal((half_w, half_w, half_w, 1))
    o.matrix_world = m
    f = outline(shape, lh)
    # the collet: a ring under the girdle, following the outline
    ring = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        r = f(math.cos(a), math.sin(a)) * 0.82
        ring.append(m @ Vector((r * math.cos(a), r * math.sin(a), -0.32)))
    wire(ring, half_w * 0.075, closed=True)
    # the claws: round beads over the girdle, a V claw at each point
    if shape == "round":
        angles = [45 + 90 * k for k in range(4)]
    elif shape == "marquise":
        angles = [90, 270, 25, 155, 205, 335]
    else:
        angles = [90, 200, 250, 290, 340]
    for deg in angles:
        a = math.radians(deg)
        r = f(math.cos(a), math.sin(a))
        tip = m @ Vector((r * math.cos(a) * 0.97, r * math.sin(a) * 0.97, 0.07))
        low = m @ Vector((r * math.cos(a) * 0.86, r * math.sin(a) * 0.86, -0.32))
        wire([low, (low + tip) / 2 + (m.to_3x3() @ Vector((math.cos(a), math.sin(a), 0))).normalized() * half_w * 0.08, tip],
             half_w * 0.07)
        bead(tip, half_w * (0.12 if shape == "round" else 0.09) * (1.25 if deg in (90, 270) and shape != "round" else 1))
    return o


def wire(points, radius, closed=False):
    cu = bpy.data.curves.new("wire", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.use_fill_caps = not closed
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for p, q in zip(sp.points, points):
        p.co = (q[0], q[1], q[2], 1)
    sp.use_cyclic_u = closed
    sp.use_endpoint_u = not closed
    sp.order_u = 3
    sp.resolution_u = 6
    o = bpy.data.objects.new("wire", cu)
    scene.collection.objects.link(o)
    o.data.materials.append(metal)
    return o


BEAD = None


def bead(p, r):
    global BEAD
    if BEAD is None:
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=1)
        BEAD = bpy.data.meshes.new("bead")
        bm.to_mesh(BEAD)
        for poly in BEAD.polygons:
            poly.use_smooth = True
        BEAD.materials.append(metal)
    o = bpy.data.objects.new("bead", BEAD)
    scene.collection.objects.link(o)
    o.matrix_world = Matrix.Translation(p) @ Matrix.Diagonal((r, r, r, 1))


def jump_ring(p, r, tube, axis):
    bm = bmesh.new()
    segs, rings = 32, 10
    verts = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        row = []
        for j in range(rings):
            b = 2 * math.pi * j / rings
            row.append(bm.verts.new(((r + tube * math.cos(b)) * math.cos(a), (r + tube * math.cos(b)) * math.sin(a), tube * math.sin(b))))
        verts.append(row)
    for i in range(segs):
        for j in range(rings):
            bm.faces.new((verts[i][j], verts[(i + 1) % segs][j], verts[(i + 1) % segs][(j + 1) % rings], verts[i][(j + 1) % rings]))
    me = bpy.data.meshes.new("ring")
    bm.to_mesh(me)
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(metal)
    o = bpy.data.objects.new("ring", me)
    scene.collection.objects.link(o)
    z = axis.normalized()
    x = z.orthogonal().normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = p
    o.matrix_world = m


# ---------- the piece, built on the traced blueprint ----------
# art/necklace_blueprint.json is the reference photograph traced (art/necklace_trace.py):
# each side's centreline and band width with stations along it every half
# band-width, the stem from the V to the bail, the drop's outline. Here those
# image pixels become millimetres (the drop 26 mm across) in the plane the camera
# looks at square on, so the model's silhouette is the tracing's: the stones are
# laid around the line, never the other way round.
import json
import os
BP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "necklace_blueprint.json")))
DROP = BP["drop"]
MM = 26.0 / max(b_ - a_ for _, a_, b_ in DROP)                 # mm per traced pixel
X0, Y0 = BP["points_px"]["P5 centre"]
FACE = Vector((0, 0, 1))


def to_mm(px, py, z=0.0):
    return Vector(((px - X0) * MM, -(py - Y0) * MM, z))


def place_melee(p, r):
    """A small brilliant set a few degrees off true (as a setter leaves it), on
    its own collet with claws."""
    tilt = Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 1)).normalized()
    place("round", 1.0, r, p, tilt, Vector((math.cos(rng.uniform(0, 6.3)), math.sin(rng.uniform(0, 6.3)), 0)))


# ---------- the sides: square diamonds, two abreast, along the traced line ----------
# At each station (every 0.42 band-widths along the traced line) a pair of
# princess-cut diamonds side by side across the band, each 0.38 of its width
# (a fine gap to the next every way), their edges square to the line; every other pair shifted a touch
# along and across, and every stone turned a degree or two its own way, as a
# setter leaves them (the band reads as square stones, never as a ruled grid).
# The band's own width, as traced, makes them larger toward the centre.
def place_square(p, side_len, along):
    turn = math.radians(rng.uniform(-3, 3))
    tilt = Vector((rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), 1)).normalized()
    up = (along * math.cos(turn) + FACE.cross(along) * math.sin(turn)).normalized()
    place("square", 1.0, side_len / 2, p, tilt, up)


for i, (side_, x, y, ang, w) in enumerate(BP["stations"]):
    ax = Vector((math.cos(ang), -math.sin(ang), 0))          # along the band (image y is down)
    ac = Vector((-ax.y, ax.x, 0))                             # across it
    k = i if side_ == "L" else i - sum(1 for s_ in BP["stations"] if s_[0] == "L")
    shift = (0.04 if k % 2 else -0.04) * w * MM
    for row in (1, -1):
        c = to_mm(x, y) + ac * (row * 0.205 * w * MM + shift * 0.5) + ax * shift
        place_square(c, w * MM * rng.uniform(0.37, 0.39), ax)     # 0.42 w apart along, 0.41 w across: fine gaps between
# the gallery under each side: a wire along the traced line, the collets sitting on it
for key in "LR":
    ss = [s_ for s_ in BP["stations"] if s_[0] == key]
    for row in (1, -1):
        pts = []
        for _, x, y, ang, w in ss[::2]:
            ax = Vector((math.cos(ang), -math.sin(ang), 0))
            pts.append(to_mm(x, y, -0.9) + Vector((-ax.y, ax.x, 0)) * row * 0.205 * w * MM)
        wire(pts, max(0.18, ss[0][4] * MM * 0.05))

# ---------- the centre, as traced: the V, a pear point up, the bail ----------
STEM = BP["stem"]
cx = sum((a_ + b_) / 2 for _, a_, b_ in STEM) / len(STEM)
v_y, bail_y = BP["v_y"], BP["bail_y"]
# where the rows meet, a square diamond closes the V, set on its point
w_v = STEM[0][2] - STEM[0][1]
place("square", 1.0, w_v * MM * 0.24, to_mm(cx, v_y + w_v * 0.32, 0.05), FACE,
      Vector((math.cos(math.pi / 4), math.sin(math.pi / 4), 0)))
# the connecting pear, point up, filling the traced stem below it
sw = max(b_ - a_ for y_, a_, b_ in STEM if y_ > v_y + (bail_y - v_y) * 0.3)
p_top, p_bot = v_y + (bail_y - v_y) * 0.32, bail_y - 4
PW = sw * MM / 2 * 0.92
p_len = (p_bot - p_top) * MM
p_lh = 0.62 * p_len / PW
PEAR_LOW = 0.38 * p_len / PW
place("pear2", p_lh, PW, to_mm(cx, p_top + 0.62 * (p_bot - p_top), 0.1), FACE, Vector((0, 1, 0)))
jump_ring(to_mm(cx, bail_y, -0.3), 0.9, 0.3, Vector((1, 0, 0)))

# ---------- the drop, as traced: its width, its length, widest where it is ----------
top, bot = DROP[0][0], DROP[-1][0]
wid = max(DROP, key=lambda t: t[2] - t[1])
DW = (wid[2] - wid[1]) * MM / 2                                # half its width, mm
total = (bot - top) * MM
f = (wid[0] - top) / (bot - top)                               # where it is widest (0 top, 1 bottom)
lh = f * total / DW
PEAR_LOW = (1 - f) * total / DW
place("pear2", lh, DW, to_mm(cx, wid[0]), FACE, Vector((0, 1, 0)))

# ---------- the studio: dark, lit by three large soft sources ----------
# The film is transparent and so is the glass where it shows only the dark
# room behind: the page itself shows through a stone. What a stone does show
# is what its facets catch: the key's broad reflection bands, a little fill,
# a faint rim, and black flags (for the dark facets a real stone shows in any
# light). No ground, nothing that could cast a shadow on anything.
world = bpy.data.worlds.new("dark")
scene.world = world
world.use_nodes = True
LIGHT = "--light" in sys.argv       # the same piece in a white light box, for the page's light theme
# the dark studio isn't pure black: a faint neutral room (#050505 or so) gives the
# transparent facets something to carry, so they read as clear, not as holes
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1) if LIGHT else (0.0016, 0.0016, 0.0016, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = (0.6 if LIGHT else 1.0)   # the white box a little down, so the facets keep their structure


def area(name, size, power, loc, aim=(0, 0, 0)):
    li = bpy.data.lights.new(name, "AREA")
    li.shape = "RECTANGLE"
    li.size, li.size_y = size
    li.energy = power
    li.use_shadow = True
    o = bpy.data.objects.new(name, li)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return li


# three long soft boxes, key : secondary : rim = 1 : 0.3 : 0.2, far brighter than the room,
# so the facets carry long bright bands against deep dark ones (the contrast is the light's,
# not the stone's colour). Chosen from three setups compared on the drop (moderate,
# stronger, stronger rim): the stronger one, with the soft boxes below
KEY = 2.5e7 if LIGHT else 9.0e7
area("key", (700, 180), KEY, (-220, 1100, 650))                 # a long strip above, a little left: bands across the facets
area("secondary", (180, 700), KEY * 0.3, (900, -500, 700))      # a long strip front right, crossing the key's bands
area("rim", (220, 900), KEY * 0.2, (1100, 250, -60))   # far right, grazing: the edges


def softbox(el0, el1, az, half, power, dist=2000.0):
    """A large soft light round the piece (the stones see it; the camera never does),
    seen from the piece between elevations el0..el1 degrees, centred on azimuth az."""
    m = bpy.data.materials.new("softbox")
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    e = nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = power
    m.node_tree.links.new(e.outputs[0], nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    b2 = bmesh.new()
    n, rows = 10, []
    for i in range(n + 1):
        el = math.radians(el0 + (el1 - el0) * i / n)
        row = []
        for j in range(n + 1):
            t = math.radians(az - half + 2 * half * j / n)
            row.append(b2.verts.new((dist * math.cos(el) * math.cos(t), dist * math.cos(el) * math.sin(t), dist * math.sin(el))))
        rows.append(row)
    for i in range(n):
        for j in range(n):
            b2.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    me = bpy.data.meshes.new("softbox")
    b2.to_mesh(me)
    o = bpy.data.objects.new("softbox", me)
    scene.collection.objects.link(o)
    o.data.materials.append(m)
    o.visible_camera = False
    o.visible_shadow = False


# the reflection sources: a few large, bright shapes in a dark room, for the
# facets to mirror (not to light the piece): a tall softbox 20 degrees off the
# camera's axis, a long narrow strip at 50, a broad soft source low to the side
# for the edges, and the room dark between them. Each large facet then carries
# one of three things: a clean bright band, the dark room, or the light passing
# through the stone.
if not LIGHT:
    RS = 2.0
    SZ = 1.4        # each source 1.4 times its first size: on the drop about 34% light-carrying, 31% deep, 35% bright, 0.6% clipped

    def big(el0, el1, az, half, power):
        mid, h = (el0 + el1) / 2, (el1 - el0) / 2 * SZ
        softbox(max(1, mid - h), min(85, mid + h), az, half * SZ, power)

    big(55, 78, 150, 16, 6.0 * RS)                # the tall key reflection, upper left of the camera
    big(34, 46, 20, 34, 5.0 * RS)                 # the long narrow strip, right
    big(6, 26, 250, 40, 3.0 * RS)                 # the broad edge source, low left
    big(18, 36, 300, 18, 2.0 * RS)                # a secondary, lower right
    big(20, 40, 90, 22, 2.0 * RS)                 # and one behind, seen through the stone


def flag(loc, size):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = (size[0], size[1], 1)
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("Z", "Y").to_euler()
    m = bpy.data.materials.new("flag")
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    e = nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0, 0, 0, 1)
    m.node_tree.links.new(e.outputs[0], nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    o.data.materials.append(m)
    o.visible_camera = False
    o.visible_shadow = False
    o.visible_diffuse = False


# black flags: the camera and its operator, and two long ones off the sides
flag((0, 30, 700), (260, 260) if not LIGHT else (420, 420))
flag((-600, 0, 380), (160, 900))
flag((600, 0, 380), (160, 900))

# ---------- the camera: square on to the piece, no perspective, framing it as traced ----------
# (orthographic, so the render lies on the blueprint exactly; a long lens would too, near enough)
cam = bpy.data.cameras.new("cam")
cam.type = "ORTHO"
cam.clip_end = 10000
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
bx0, bx1, by0, by1 = BP["frame"]                               # the traced piece's box in the photograph, with a margin
lo, hi = to_mm(bx0, by1), to_mm(bx1, by0)
co.location = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 500))
cam.ortho_scale = max(hi.x - lo.x, hi.y - lo.y)
scene.camera = co
ASPECT = (bx1 - bx0) / (by1 - by0)

r = scene.render
r.engine = "CYCLES"
r.film_transparent = True
# the transmission test: the piece against a flat backdrop of a given grey, seen through the stones
# (python necklace.py OUT.png 800 32 --mono --backdrop 0.5); a stone that shows the backdrop through it is transparent
if "--backdrop" in sys.argv:
    grey = float(sys.argv[sys.argv.index("--backdrop") + 1])
    bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, -60))
    bd = bpy.context.object
    bm_ = bpy.data.materials.new("backdrop")
    bm_.use_nodes = True
    bn = bm_.node_tree.nodes
    bn.clear()
    em_ = bn.new("ShaderNodeEmission")
    em_.inputs["Color"].default_value = (grey, grey, grey, 1)
    bm_.node_tree.links.new(em_.outputs[0], bn.new("ShaderNodeOutputMaterial").inputs["Surface"])
    bd.data.materials.append(bm_)
    bd.visible_shadow = False
    bd.visible_glossy = False
    r.film_transparent = False
scene.cycles.film_transparent_glass = not LIGHT     # where a stone shows only the dark room, the page shows through
scene.cycles.film_transparent_roughness = 0.1
r.resolution_y = size
r.resolution_x = int(size * ASPECT)
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX"          # highlights roll off instead of clipping; no bloom, no glare
cy = scene.cycles
cy.device = "CPU"
cy.samples = samples
cy.max_bounces = 40
cy.transmission_bounces = 40
cy.glossy_bounces = 16
cy.transparent_max_bounces = 16
cy.caustics_reflective = False
cy.caustics_refractive = False
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
r.threads_mode = "FIXED"
r.threads = 4

if "--mono" in sys.argv:
    glass.inputs["IOR"].default_value = 2.417
    r.filepath = out
    bpy.ops.render.render(write_still=True)
else:
    import numpy as np
    from PIL import Image
    parts = []
    # diamond's index at the C, d and F lines (Abbe number 55)
    for ch, ior in (("r", 2.4076), ("g", 2.4175), ("b", 2.4334)):
        glass.inputs["IOR"].default_value = ior
        r.filepath = f"{out}.{ch}.png"
        bpy.ops.render.render(write_still=True)
        parts.append(np.asarray(Image.open(r.filepath).convert("RGBA"), dtype=np.float32))
    # each channel from its own index, only part of the difference kept:
    # fire at the edges, not rainbow bands
    r_, g_, b_ = parts
    mono = (r_ + g_ + b_) / 3
    disp = mono.copy()
    disp[..., 0], disp[..., 1], disp[..., 2] = r_[..., 0], g_[..., 1], b_[..., 2]
    img = mono + 0.25 * (disp - mono)    # a third of the fire kept: a trace of cool colour at the edges, never rainbow bands
    img[..., 3] = g_[..., 3]
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA").save(out)
print("wrote", out)
