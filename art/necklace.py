"""The jewellery subject's object: a high-jewellery diamond necklace, modelled
and rendered as a studio photograph of a real piece, floating on nothing.

The design follows a reference photograph (a V necklace on a display bust):
- two sides that come down from the neck and meet in a V, each a twisted
  band of round brilliants set in two staggered rows, a marquise laid across
  every gap between them, the stones growing larger toward the front;
- at the V a round brilliant, a marquise hanging from it, and from that the
  pear-shaped drop, point up: 30 x 16 mm, the piece's focus.

Units are millimetres. Every stone is a faceted solid (a round brilliant's
table, star, bezel, upper and lower girdle and pavilion facets; the pear and
the marquise are the same brilliant drawn out to their outline), diamond's
index 2.417, and dispersion from one render per colour channel at that
channel's index, only part of it kept (fire at the edges, never rainbow
bands). Each stone sits in its own setting: a collet ring under the girdle
and claws over its edge (a V claw at a point), all on a rail that runs the
length of each side; jump rings join the V, the marquise and the drop.
Platinum with roughness that varies across the surface and fine scratches.

No ground, no shadow: the necklace hangs in a white light box with dark
flags (the facets mirror them, which gives a diamond its contrast), a
large softbox above, and the film is transparent, so the page is its
background.

Run with Blender's Python module (pip install bpy==4.2.0 numpy pillow, Python 3.11):

    python art/necklace.py jewelry.png 1600 160
    then: Image.open("jewelry.png").save("static/subjects/jewelry.webp", quality=86, method=6)

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
glass.inputs["Roughness"].default_value = 0.01
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
    return lambda ux, uy: 1.0 if uy <= 0 else vesica(ux, uy, lh)          # pear: point up


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


# ---------- the sides: articulated modules along one smooth V ----------
# Each side is a cubic Bézier from the V up to the neck; a slight tipping of
# the stones' faces follows the neck they would lie around.
NECK = 60.0


def bezier(t, sx):
    p0, p1, p2, p3 = Vector((0, 0, 0)), Vector((sx * 7, 5.5, 0)), Vector((sx * 27, 30, 0)), Vector((sx * 39, 76, 0))
    q = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
    q.z = NECK * (math.cos(math.asin(min(abs(q.x) / (NECK + 8), 0.99))) - 1)       # curving back round the neck
    return q


def face_normal(p):
    n = Vector((p.x, 0, p.z + NECK)).normalized()
    return (n + Vector((0, 0.15, 0))).normalized()


# one module (mm, in the band's own frame: x along it, y across it, the outside +y):
# a principal round on the outside, a smaller round on the inside half a step on
# (the two rows interlock, stone to stone), a small round in the inner notch, and
# a marquise standing out of the outer notch, the band's leafy outer edge; checked
# so no two stones touch
MODULE = [("round", 1.0, 1.40, (0.0, 0.9), 0),
          ("round", 1.0, 1.15, (2.15, -1.0), 0),
          ("round", 1.0, 0.60, (0.0, -1.45), 0),
          ("marquise", 2.8, 0.45, (2.15, 1.95), 80)]
PITCH = 4.3
SCALE = 1.45   # the band about a third of the drop's width, as in the reference

for sx in (-1, 1):
    ts = [i / 3000 for i in range(3001)]
    line = [bezier(t, sx) for t in ts]
    lens = [0.0]
    for a_, b_ in zip(line, line[1:]):
        lens.append(lens[-1] + (a_ - b_).length)

    def at(dist):
        i = min(range(len(lens)), key=lambda k: abs(lens[k] - dist))
        return line[i], (line[min(i + 1, len(line) - 1)] - line[max(i - 1, 0)]).normalized()

    # the hinge rail under the modules, visible between them
    wire([line[i] + face_normal(line[i]) * -1.6 for i in range(0, len(line), 60)], 0.45)
    dist, k, prev = 7.0, 0, None
    while dist < lens[-1] - 2:
        g = SCALE * (1.0 - 0.3 * min(1.0, dist / 95))         # modules grow toward the front
        p, t = at(dist)
        n = face_normal(p)
        b = n.cross(t).normalized() * sx                      # across the band, the outside +
        turn = math.radians(7 if k % 2 else -5)               # each module sits a little differently
        t2 = (t * math.cos(turn) + b * math.sin(turn)).normalized()
        b2 = n.cross(t2).normalized() * sx
        for shape, lh, hw, (u, v), ang in MODULE:
            pos = p + (t2 * u + b2 * v) * g + n * 0.12
            if shape == "round":
                place("round", 1.0, hw * g * rng.uniform(0.97, 1.03), pos, n, t2)
            else:
                a = math.radians(ang)
                axis = (t2 * math.cos(a) + b2 * math.sin(a)).normalized()
                place("marquise", lh, hw * g, pos + n * 0.1, n, axis)
        # the module's hinge to the last one, under the stones
        here = p + n * -1.1
        if prev is not None:
            wire([prev, (prev + here) / 2 + n * -0.3, here], 0.4 * g)
        prev = here
        dist += PITCH * g
        k += 1

# ---------- the centre: the two sides gather to a round, then the marquise, then the drop ----------
front = Vector((0, 0.1, 1)).normalized()
place("round", 1.0, 2.0, Vector((0, 1.0, 0.5)), front, Vector((0, 1, 0)))
for sx in (-1, 1):                                            # small pears leading each side in
    place("pear", 1.9, 0.9, Vector((sx * 3.4, 2.6, 0.3)), front, Vector((sx * 0.8, 0.6, 0)).normalized())
MQ_W, MQ_LH = 2.3, 2.3                                        # 4.6 x 10.6 mm
place("marquise", MQ_LH, MQ_W, Vector((0, -1.6 - MQ_W * MQ_LH, 0.2)), front, Vector((0, 1, 0)))
jump_ring(Vector((0, -1.3, -0.3)), 0.8, 0.26, Vector((1, 0, 0)))
ring_y = -1.6 - 2 * MQ_W * MQ_LH - 0.9
jump_ring(Vector((0, ring_y, -0.3)), 1.1, 0.32, Vector((1, 0, 0)))
# the drop: 20 mm across, 36 mm long, point up
PEAR_W, PEAR_LH = 10.0, 2.6
place("pear", PEAR_LH, PEAR_W, Vector((0, ring_y - 1.0 - PEAR_LH * PEAR_W, 0.0)), Vector((0, -0.02, 1)).normalized(),
      Vector((0, 1, 0)))

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
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1) if LIGHT else (0, 0, 0, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7 if LIGHT else 1.0


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


KEY = 1.5e7 if LIGHT else 4.0e7
area("key", (520, 320), KEY, (-220, 1100, 650))                # above, a little left: its bands cross the facets, not a table's mirror line
area("fill", (1400, 700), KEY * 0.2, (0, -1100, 900))           # broad and weak, low in front (off the tables' mirror line)
area("rim", (260, 700), KEY * 0.15, (1100, 250, -60))            # far right, grazing: the silhouette's edge, never seen through a stone


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
flag((0, 30, 700), (260, 260))
flag((-600, 0, 380), (160, 900))
flag((600, 0, 380), (160, 900))

# ---------- the camera: an 85 mm lens square to the piece, everything in focus ----------
cam = bpy.data.cameras.new("cam")
cam.lens = 85
cam.sensor_fit = "VERTICAL"
cam.sensor_height = 24
cam.clip_end = 10000
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
aim = Vector((0, 11.0, 0))
co.location = aim + Vector((0, 0, 500))
co.rotation_euler = (0, 0, 0)
scene.camera = co

r = scene.render
r.engine = "CYCLES"
r.film_transparent = True
scene.cycles.film_transparent_glass = not LIGHT     # where a stone shows only the dark room, the page shows through
scene.cycles.film_transparent_roughness = 0.1
r.resolution_y = size
r.resolution_x = int(size * 0.72)
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
    img = mono + 0.35 * (disp - mono)
    img[..., 3] = g_[..., 3]
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA").save(out)
print("wrote", out)
