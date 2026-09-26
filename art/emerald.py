"""An emerald-cut diamond, modelled and rendered in Cycles.

The stone: a step cut. Octagon rings (a rectangle with its corners cut at
45°) stacked from the table down through the crown's three steps to the
girdle, then the pavilion's steps down to a short keel. Diamond's index,
2.417; dispersion by rendering once per channel at that channel's index.
Lit like a jeweller's photograph: a white light box, with dark cards and the
camera's own dark face showing in the facets.

Run with Blender's Python module (pip install bpy==4.2.0 pillow, Python 3.11):

    python art/emerald.py static/subjects/jewelry.png 1600 256 --necklace
    (then as WEBP: Image.open(png).save("static/subjects/jewelry.webp", quality=86, method=6))

    python emerald.py OUT.png [size] [samples] [--necklace] [--mono]"""
import math
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

out = sys.argv[1]
size = int(sys.argv[2]) if len(sys.argv) > 2 else 900
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 256
necklace = "--necklace" in sys.argv

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- the stone ----------
W, L = 1.0, 1.42            # width, length (a classic 1.4 ratio)
C = 0.17                    # the corner cut, as a share of the width
R2 = 2 - math.sqrt(2)


def ring(inset, z):
    """The girdle's octagon moved inward by `inset` (every edge parallel), at height z."""
    a, b, c = W / 2 - inset, L / 2 - inset, C * W - inset * R2
    a, b, c = max(a, 1e-4), max(b, 1e-4), max(c, 0.0)
    pts = [(-a + c, b), (a - c, b), (a, b - c), (a, -b + c), (a - c, -b), (-a + c, -b), (-a, -b + c), (-a, b - c)]
    return [Vector((x, y, z)) for x, y in pts]


g = 0.012                                   # half the girdle's thickness
crown = [(0.0, g), (0.075, 0.062), (0.145, 0.105), (0.19, 0.128)]      # (inset, height): girdle → table
pav = [(0.0, -g), (0.09, -0.127), (0.19, -0.231), (0.31, -0.343), (0.495, -0.504)]  # girdle → keel (width → ~0)
rings = [ring(i, z) for i, z in reversed(crown)] + [ring(i, z) for i, z in pav]

bm = bmesh.new()
vs = [[bm.verts.new(p) for p in r] for r in rings]
bm.faces.new(vs[0])                                     # the table
for r0, r1 in zip(vs, vs[1:]):
    for k in range(8):
        a, b, c, d = r0[k], r0[(k + 1) % 8], r1[(k + 1) % 8], r1[k]
        bm.faces.new((a, b, c, d))
bm.faces.new(list(reversed(vs[-1])))                    # the keel (a sliver)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mesh = bpy.data.meshes.new("stone")
bm.to_mesh(mesh)
stone = bpy.data.objects.new("stone", mesh)
scene.collection.objects.link(stone)

gem = bpy.data.materials.new("diamond")
gem.use_nodes = True
nt = gem.node_tree
nt.nodes.clear()
glass = nt.nodes.new("ShaderNodeBsdfGlass")
glass.inputs["Roughness"].default_value = 0.0
glass.inputs["Color"].default_value = (1, 1, 1, 1)
mo = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(glass.outputs[0], mo.inputs["Surface"])
stone.data.materials.append(gem)

# ---------- the setting and the necklace ----------
metal = bpy.data.materials.new("platinum")
metal.use_nodes = True
pb = metal.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.62, 0.62, 0.64, 1)
pb.inputs["Metallic"].default_value = 1.0
pb.inputs["Roughness"].default_value = 0.18


def add(obj):
    scene.collection.objects.link(obj)
    obj.data.materials.append(metal)
    return obj


if necklace:
    top = L / 2
    # four claws, one on each corner facet
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx = sx * (W / 2 - C * W / 2 + 0.004)
            cy = sy * (L / 2 - C * W / 2 + 0.004)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.046, location=(cx, cy, 0.035), segments=32, ring_count=16)
            claw = bpy.context.object
            claw.scale = (1, 1, 1.25)
            claw.data.materials.append(metal)
    # the bail: a small loop standing above the top edge
    # the bail: a loop facing the viewer, held on a short stem at the top edge
    bpy.ops.mesh.primitive_torus_add(major_radius=0.06, minor_radius=0.016, location=(0, top + 0.115, 0.0),
                                     major_segments=48, minor_segments=16)
    bail = bpy.context.object
    bail.scale = (0.8, 1.0, 1.0)
    bail.data.materials.append(metal)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=0.07, location=(0, top + 0.03, 0.0), rotation=(math.pi / 2, 0, 0))
    bpy.context.object.data.materials.append(metal)
    # the chain: two strands rising from the bail, each a run of fine cable links
    link = bpy.data.meshes.new("link")
    lb = bmesh.new()
    bmesh.ops.create_circle(lb, cap_ends=False, segments=20, radius=1)
    lb.to_mesh(link)
    for sx in (-1, 1):
        pts = []
        p0 = Vector((0, top + 0.16, 0))
        p3 = Vector((sx * 1.05, top + 3.2, 0))
        p1 = Vector((sx * 0.05, top + 0.9, 0))
        p2 = Vector((sx * 0.55, top + 2.2, 0))
        n = 400
        for i in range(n + 1):
            t = i / n
            pts.append((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3)
        # links every `step` along the curve, alternately flat and on edge
        step, acc, last, k = 0.028, 0.0, pts[0], 0
        for p in pts[1:]:
            acc += (p - last).length
            last = p
            if acc < step:
                continue
            acc = 0.0
            i = pts.index(p)
            d = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
            bpy.ops.mesh.primitive_torus_add(major_radius=0.019, minor_radius=0.0045, location=p,
                                             major_segments=16, minor_segments=8)
            o = bpy.context.object
            o.scale = (1.0, 1.35, 1.0)
            ang = math.atan2(d.y, d.x) - math.pi / 2
            # the link's long axis (y) along the chain, every other one turned on its edge
            rot = Matrix.Rotation(ang, 4, "Z") @ (Matrix.Rotation(math.pi / 2, 4, "Y") if k % 2 else Matrix())
            o.matrix_world = Matrix.Translation(p) @ rot @ Matrix.Diagonal((1.0, 1.35, 1.0, 1.0))
            o.data.materials.append(metal)
            k += 1

# ---------- the light box ----------
world = bpy.data.worlds.new("box")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

dark = bpy.data.materials.new("card")
dark.use_nodes = True
dn = dark.node_tree.nodes
dn.clear()
em = dn.new("ShaderNodeEmission")
em.inputs["Strength"].default_value = 1.0
dark.node_tree.links.new(em.outputs[0], dn.new("ShaderNodeOutputMaterial").inputs["Surface"])


def flag(el0, el1, az, half, value, dist=10.0):
    """A card in the box, seen from the stone between elevations el0..el1
    (degrees), centred on azimuth az, `half` degrees wide each way."""
    mat = dark if value == 0 else None
    if value:
        mat = bpy.data.materials.new(f"grey{value}")
        mat.use_nodes = True
        mn = mat.node_tree.nodes
        mn.clear()
        e = mn.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (value, value, value, 1)
        mat.node_tree.links.new(e.outputs[0], mn.new("ShaderNodeOutputMaterial").inputs["Surface"])
    else:
        em.inputs["Color"].default_value = (0, 0, 0, 1)
    bm2 = bmesh.new()
    n = 12
    rows = []
    for i in range(n + 1):
        e = math.radians(el0 + (el1 - el0) * i / n)
        row = []
        for j in range(n + 1):
            t = math.radians(az - half + 2 * half * j / n)
            row.append(bm2.verts.new((dist * math.cos(e) * math.cos(t), dist * math.cos(e) * math.sin(t), dist * math.sin(e))))
        rows.append(row)
    for i in range(n):
        for j in range(n):
            bm2.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    me = bpy.data.meshes.new("flag")
    bm2.to_mesh(me)
    o = bpy.data.objects.new("flag", me)
    scene.collection.objects.link(o)
    o.data.materials.append(mat)
    o.visible_camera = False
    return o


# the box's dark and grey panels: [elevation from, to, azimuth, half its width, grey].
# The camera and whoever holds it straight above; a ring higher up; tall dark
# flags off the long sides (the step cut's long facets mirror them into the
# "hall of mirrors"); greys off the ends and at the four corners, for the outline.
PANELS = [[82, 90, 0, 180, 0], [62, 70, 0, 180, 0],
          [30, 58, 0, 10, 0], [30, 58, 180, 10, 0], [10, 20, 0, 30, 0], [10, 20, 180, 30, 0],
          [25, 35, 90, 25, 0.15], [25, 35, 270, 25, 0.15],
          [18, 24, 45, 25, 0.3], [18, 24, 135, 25, 0.3], [18, 24, 225, 25, 0.3], [18, 24, 315, 25, 0.3]]
for c in PANELS:
    flag(*c)

cam = bpy.data.cameras.new("cam")
cam.lens = 150
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
co.location = (0, 0, 22 if not necklace else 30)
if necklace:
    co.location = (0, 1.25, 30)
scene.camera = co
cam.sensor_width = 36
cam.type = "ORTHO"
cam.ortho_scale = 1.75 if not necklace else 4.3

r = scene.render
r.engine = "CYCLES"
r.film_transparent = True
r.resolution_x = size if not necklace else int(size * 0.62)
r.resolution_y = int(size * 1.0) if not necklace else size
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
view = scene.view_settings
view.view_transform = "Standard"
view.look = "None"
cy = scene.cycles
cy.device = "CPU"
cy.samples = samples
cy.max_bounces = 48
cy.transmission_bounces = 48
cy.glossy_bounces = 24
cy.transparent_max_bounces = 16
cy.caustics_reflective = True
cy.caustics_refractive = True
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
scene.render.threads_mode = "FIXED"
scene.render.threads = 4

# dispersion: one pass per channel at that channel's index
if "--mono" in sys.argv:
    glass.inputs["IOR"].default_value = 2.417
    r.filepath = out
    bpy.ops.render.render(write_still=True)
else:
    from PIL import Image
    parts = []
    for ch, ior in (("r", 2.407), ("g", 2.419), ("b", 2.440)):
        glass.inputs["IOR"].default_value = ior
        r.filepath = f"{out}.{ch}.png"
        bpy.ops.render.render(write_still=True)
        parts.append(Image.open(r.filepath).convert("RGBA"))
    # each channel from its own index, then only a third of the difference kept:
    # fire in the edges and corners, not coloured bands across the steps
    import numpy as np
    r_, g_, b_ = (np.asarray(p, dtype=np.float32) for p in parts)
    mono = (r_ + g_ + b_) / 3
    disp = mono.copy()
    disp[..., 0], disp[..., 1], disp[..., 2] = r_[..., 0], g_[..., 1], b_[..., 2]
    img = mono + 0.35 * (disp - mono)
    img[..., 3] = g_[..., 3]
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA").save(out)
print("wrote", out)
