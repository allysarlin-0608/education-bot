"""The jewellery subject's object: a high-jewellery diamond necklace, modelled
and rendered as a studio photograph of a real piece, floating on nothing.

The design is the reference photograph's (a V necklace on a display bust),
traced first and built second: art/necklace_trace.py turns the photograph into
a 2D blueprint (art/necklace_blueprint.json: each side's centreline and band
width with stations along it, the V, the stem to the bail, the drop's
outline), checked by overlaying it on the photograph; this script builds on
that blueprint in the plane the camera looks at square on, so the render lies
on the photograph's necklace. Along each side, two staggered rows of
individually set round brilliants twisting down the band, a small stone in
each notch at the edges, a pear or a marquise across the band every fifth; at
the V a round, then a pear point up to the bail; the drop as traced, twice as
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

    python necklace.py OUT.png [height] [samples] [--mono] [--light]"""
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
    43% pavilion, a thin girdle; its facets are the convex hull of these points."""
    pts = []
    rt = 0.57 / math.cos(math.radians(22.5))
    for k in range(8):                                       # the table
        a = math.radians(45 * k)
        pts.append((rt * math.cos(a), rt * math.sin(a), 0.32))
    for k in range(8):                                       # the star facets' points
        a = math.radians(45 * k + 22.5)
        pts.append((0.79 * math.cos(a), 0.79 * math.sin(a), 0.178))
    for k in range(32):                                      # the girdle, both edges
        a = math.radians(11.25 * k)
        pts += [(math.cos(a), math.sin(a), 0.02), (math.cos(a), math.sin(a), -0.02)]
    for k in range(8):                                       # the lower girdle facets' points
        a = math.radians(45 * k + 22.5)
        r = 0.23
        pts.append((r * math.cos(a), r * math.sin(a), -0.02 - (1 - r) * 0.86 + 0.012))
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
    if shape == "marquise":
        return lambda ux, uy: vesica(ux, uy, lh)
    if shape == "pear2":            # the reference's drop: point up, its lower part a half-ellipse (widest at 55%)
        low = PEAR_LOW
        return lambda ux, uy: 1.0 / math.sqrt(ux * ux + (uy / low) ** 2) if uy <= 0 else vesica(ux, uy, lh)
    return lambda ux, uy: 1.0 if uy <= 0 else vesica(ux, uy, lh)          # pear: point up


PEAR_LOW = 1.62


def stone_mesh(shape="round", lh=1.0):
    """A cut as a mesh: the brilliant drawn out to its outline, then its hull."""
    f = outline(shape, lh)
    bm = bmesh.new()
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


# ---------- the sides: two staggered rows of individually set stones, twisting ----------
# At each station (every 0.42 band-widths along the traced line) one stone,
# alternately on the band's outer and inner half: two rows of round brilliants,
# each a little over half the band wide, interlocking, a small stone in each
# notch between them on the edges; every fifth, a pear or a marquise
# laid across the band, as the reference's twist has them. The band's own
# width, as traced, makes them larger toward the centre.
for i, (side_, x, y, ang, w) in enumerate(BP["stations"]):
    ax = Vector((math.cos(ang), -math.sin(ang), 0))          # along the band (image y is down)
    ac = Vector((-ax.y, ax.x, 0))                             # across it
    k = i if side_ == "L" else i - sum(1 for s_ in BP["stations"] if s_[0] == "L")
    row = 1 if k % 2 == 0 else -1
    c = to_mm(x, y) + ac * row * w * MM * 0.22
    d = w * MM * rng.uniform(0.52, 0.58)                      # a stone's diameter
    # a small stone in the notch on the other row's side, between this stone and the last
    place_melee(to_mm(x, y) - ac * row * w * MM * 0.36 - ax * w * MM * 0.2 + FACE * 0.02, w * MM * 0.11)
    if k % 5 == 3:
        lean = math.radians(rng.uniform(35, 55)) * row
        axis = (ax * math.cos(lean) + ac * math.sin(lean)).normalized()
        shape = "pear" if k % 10 == 3 else "marquise"
        place(shape, 1.9, d * 0.34, c + FACE * 0.05, FACE, axis)
    else:
        place_melee(c, d / 2)
# the gallery under each side: a wire along the traced line, the collets sitting on it
for key in "LR":
    ss = [s_ for s_ in BP["stations"] if s_[0] == key]
    wire([to_mm(x, y, -0.9) for _, x, y, _, _ in ss[::2]], max(0.25, ss[0][4] * MM * 0.08))

# ---------- the centre, as traced: the V, a pear point up, the bail ----------
STEM = BP["stem"]
cx = sum((a_ + b_) / 2 for _, a_, b_ in STEM) / len(STEM)
v_y, bail_y = BP["v_y"], BP["bail_y"]
# where the rows meet, a round closes the V
w_v = STEM[0][2] - STEM[0][1]
place_melee(to_mm(cx, v_y + w_v * 0.3, 0.05), w_v * MM * 0.3)
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


# long soft boxes round the piece, with dark gaps between them: what the pavilion's
# facets see through the stone (light passing through it, the transparent, light
# regions) and what they don't (the dark room, the deep ones)
if not LIGHT:
    # 1.5: on the drop about 54% light-carrying midtones, 35% deep, 10% bright, 1% clipped
    SB = 1.5
    for az in (20, 110, 200, 290):
        softbox(28, 52, az, 22, SB)
    for az in (65, 245):
        softbox(58, 72, az, 30, SB * 0.6)


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
    img = mono + 0.35 * (disp - mono)    # a third of the fire kept: a trace of cool colour at the edges, never rainbow bands
    img[..., 3] = g_[..., 3]
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA").save(out)
print("wrote", out)
