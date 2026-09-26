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

    python necklace.py OUT.png [height] [samples] [--mono]"""
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
glass = gn.new("ShaderNodeBsdfGlass")
glass.inputs["Roughness"].default_value = 0.0
glass.inputs["Color"].default_value = (1, 1, 1, 1)
gem.node_tree.links.new(glass.outputs[0], gn.new("ShaderNodeOutputMaterial").inputs["Surface"])

metal = bpy.data.materials.new("platinum")
metal.use_nodes = True
mn, ml = metal.node_tree.nodes, metal.node_tree.links
pb = mn["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.7, 0.68, 0.65, 1)
pb.inputs["Metallic"].default_value = 1.0
tc = mn.new("ShaderNodeTexCoord")
noise = mn.new("ShaderNodeTexNoise")          # roughness that varies, as polishing leaves it
noise.inputs["Scale"].default_value = 0.6
noise.inputs["Detail"].default_value = 6.0
ml.new(tc.outputs["Object"], noise.inputs["Vector"])
rough = mn.new("ShaderNodeMapRange")
rough.inputs["To Min"].default_value, rough.inputs["To Max"].default_value = 0.12, 0.26
ml.new(noise.outputs["Fac"], rough.inputs["Value"])
ml.new(rough.outputs[0], pb.inputs["Roughness"])
wave = mn.new("ShaderNodeTexWave")            # fine scratches, barely there
wave.inputs["Scale"].default_value = 5.0
wave.inputs["Distortion"].default_value = 14.0
ml.new(tc.outputs["Object"], wave.inputs["Vector"])
bump = mn.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.03
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


# ---------- the sides: two twisted bands meeting in a V ----------
NECK = 48.0             # the neck's radius (mm): the sides curve back around it


def side_point(u, sx):
    """The band's centre line: from the V (u=0) up to the neck (u=1 is 36 mm out)."""
    x = 36 * u * sx
    y = 62 * (0.36 * u + 0.64 * u ** 2.15)
    z = NECK * (math.cos(math.asin(min(abs(x) / (NECK + 6), 0.99))) - 1)       # around the neck
    return Vector((x, y, z))


def face_normal(p):
    """Radial from the neck's axis, tipped up a little (the chest slopes back)."""
    n = Vector((p.x, 0, p.z + NECK)).normalized()
    return (n + Vector((0, 0.18, 0))).normalized()


for sx in (-1, 1):
    # the centre line, sampled finely, and measured
    us = [i / 2000 * 1.18 for i in range(2001)]
    line = [side_point(u, sx) for u in us]
    lens = [0.0]
    for a, b in zip(line, line[1:]):
        lens.append(lens[-1] + (a - b).length)

    def at(s):
        i = min(range(len(lens)), key=lambda k: abs(lens[k] - s))
        t = (line[min(i + 1, len(line) - 1)] - line[max(i - 1, 0)]).normalized()
        return line[i], t

    # the rail under the stones, the length of the side
    wire([line[i] + face_normal(line[i]) * -2.0 for i in range(0, len(line), 40)], 0.55)
    s, k = 5.2, 0
    while s < lens[-1]:
        grow = max(0.0, 1 - s / 110)                        # larger toward the front
        d = 2.9 + 1.5 * grow                                # a round's diameter (mm)
        p, t = at(s)
        n = face_normal(p)
        b = n.cross(t).normalized()
        side = 1 if k % 2 == 0 else -1
        place("round", 1.0, d / 2 * rng.uniform(0.985, 1.015), p + b * (side * 0.44 * d) + n * 0.1, n,
              t)
        # a marquise across the gap to the next round, along the other diagonal
        pitch = 0.94 * d
        pm, tm = at(s + pitch / 2)
        nm = face_normal(pm)
        bm_ = nm.cross(tm).normalized()
        axis = (tm * 0.95 + bm_ * (side * 1.0)).normalized()
        place("marquise", 2.9, 0.95 * (d / 4.4 + 0.25), pm + nm * 0.35, nm, axis)
        s += pitch
        k += 1

# ---------- the centre: a round at the V, a marquise, and the drop ----------
front = Vector((0, 0.05, 1)).normalized()
place("round", 1.0, 2.5, Vector((0, 1.2, 0.3)), front, Vector((0, 1, 0)))
place("marquise", 2.2, 2.5, Vector((0, -7.8, 0.2)), front, Vector((0, 1, 0)))
jump_ring(Vector((0, -2.1, -0.2)), 0.9, 0.28, Vector((1, 0, 0)))
jump_ring(Vector((0, -14.0, -0.3)), 1.2, 0.34, Vector((1, 0, 0)))
# the drop: 16 mm across, 30 mm long, its point up under the marquise
PEAR_W, PEAR_LH = 8.0, 22.0 / 8.0
place("pear", PEAR_LH, PEAR_W, Vector((0, -15.4 - PEAR_LH * PEAR_W, 0.0)), Vector((0, -0.02, 1)).normalized(),
      Vector((0, 1, 0)))

# ---------- the studio: a white light box, no ground ----------
world = bpy.data.worlds.new("box")
scene.world = world
world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
bgn = wn["Background"]
bgn.inputs["Strength"].default_value = 0.9
# white in front of the piece, a grey room behind it (what the stones see through themselves)
wtc = wn.new("ShaderNodeTexCoord")
wsep = wn.new("ShaderNodeSeparateXYZ")
wl.new(wtc.outputs["Generated"], wsep.inputs[0])
wramp = wn.new("ShaderNodeValToRGB")
BACK = 0.12
wramp.color_ramp.elements[0].position, wramp.color_ramp.elements[0].color = 0.4, (BACK, BACK, BACK, 1)
wramp.color_ramp.elements[1].position, wramp.color_ramp.elements[1].color = 0.62, (1, 1, 1, 1)
wmap = wn.new("ShaderNodeMapRange")
wmap.inputs["From Min"].default_value, wmap.inputs["From Max"].default_value = -1.0, 1.0
wl.new(wsep.outputs["Z"], wmap.inputs["Value"])
wl.new(wmap.outputs[0], wramp.inputs[0])
wl.new(wramp.outputs[0], bgn.inputs["Color"])


def panel(el0, el1, az, half, value, dist=2000.0):
    """A card in the box, seen from the piece between elevations el0..el1
    (degrees, from the stones' tables), centred on azimuth az, `half` degrees wide."""
    mat = bpy.data.materials.new(f"card{value}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    e = nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (value, value, value, 1)
    mat.node_tree.links.new(e.outputs[0], nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    b2 = bmesh.new()
    n, rows = 12, []
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
    me = bpy.data.meshes.new("panel")
    b2.to_mesh(me)
    o = bpy.data.objects.new("panel", me)
    scene.collection.objects.link(o)
    o.data.materials.append(mat)
    o.visible_camera = False
    o.visible_shadow = False
    o.visible_diffuse = False


for c in ([72, 90, 0, 180, 0], [62, 70, 0, 180, 0],
          [30, 58, 0, 10, 0], [30, 58, 180, 10, 0], [10, 20, 0, 30, 0], [10, 20, 180, 30, 0],
          [25, 35, 90, 25, 0.15], [25, 35, 270, 25, 0.15],
          [40, 50, 45, 12, 0.05], [40, 50, 135, 12, 0.05], [40, 50, 225, 12, 0.05], [40, 50, 315, 12, 0.05],
          [18, 24, 45, 25, 0.3], [18, 24, 135, 25, 0.3], [18, 24, 225, 25, 0.3], [18, 24, 315, 25, 0.3]):
    panel(*c)

key = bpy.data.lights.new("softbox", "AREA")                 # soft, from above-front: highlights on the metal
key.shape = "RECTANGLE"
key.size, key.size_y = 900.0, 500.0
key.energy = 9.0e6
ko = bpy.data.objects.new("softbox", key)
scene.collection.objects.link(ko)
ko.location = (200, -600, 1400)
ko.rotation_euler = (Vector((0, 0, 0)) - ko.location).to_track_quat("-Z", "Y").to_euler()

# ---------- the camera: a long lens, face on ----------
cam = bpy.data.cameras.new("cam")
cam.lens = 100
cam.sensor_fit = "VERTICAL"
cam.sensor_height = 24
cam.clip_end = 5000
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
aim = Vector((0, 8.0, 0))
co.location = aim + Vector((0, 0, 540))
co.rotation_euler = (0, 0, 0)
scene.camera = co

r = scene.render
r.engine = "CYCLES"
r.film_transparent = True
r.resolution_y = size
r.resolution_x = int(size * 0.8)
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"
cy = scene.cycles
cy.device = "CPU"
cy.samples = samples
cy.max_bounces = 32
cy.transmission_bounces = 32
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
    for ch, ior in (("r", 2.410), ("g", 2.418), ("b", 2.432)):
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
