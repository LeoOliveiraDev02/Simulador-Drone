# Conceito do Mapa 1 (campo baiano) "como vai ficar no Unreal" — render no Blender (Cycles)
import bpy, math, random, sys, os
from mathutils import Vector
random.seed(7)
REC = "/tmp/rec/voo_e88/recursos"
SAIDA = sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "/tmp/conceito.png"
RES = int(sys.argv[sys.argv.index("--")+2]) if "--" in sys.argv and len(sys.argv) > sys.argv.index("--")+2 else 960
AMOSTRAS = int(sys.argv[sys.argv.index("--")+3]) if "--" in sys.argv and len(sys.argv) > sys.argv.index("--")+3 else 16

bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene
cena.render.engine = "CYCLES"
cena.cycles.device = "CPU"
cena.cycles.samples = AMOSTRAS
cena.cycles.use_denoising = True
cena.cycles.max_bounces = 4
cena.render.resolution_x = RES
cena.render.resolution_y = int(RES * 9 / 16)
cena.view_settings.view_transform = "AgX"
cena.view_settings.look = "AgX - Medium High Contrast"
cena.render.film_transparent = False

# céu (HDRI de fazenda) + sol de fim de tarde
mundo = bpy.data.worlds.new("Mundo"); cena.world = mundo; mundo.use_nodes = True
nt = mundo.node_tree; nt.nodes.clear()
env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(REC + "/ceu/farm_field_puresky.hdr")
mapc = nt.nodes.new("ShaderNodeMapping"); coord = nt.nodes.new("ShaderNodeTexCoord")
mapc.inputs["Rotation"].default_value[2] = math.radians(200)
bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 0.55
out = nt.nodes.new("ShaderNodeOutputWorld")
nt.links.new(coord.outputs["Generated"], mapc.inputs["Vector"]); nt.links.new(mapc.outputs["Vector"], env.inputs["Vector"])
nt.links.new(env.outputs["Color"], bg.inputs["Color"]); nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
sol = bpy.data.lights.new("Sol", "SUN"); sol.energy = 5.5; sol.angle = math.radians(1.2); sol.color = (1.0, 0.86, 0.68)
so = bpy.data.objects.new("Sol", sol); cena.collection.objects.link(so)
so.rotation_euler = (math.radians(68), 0, math.radians(35))

def mat_pbr(nome, pasta, escala=1.0, tom=None, rug=None):
    m = bpy.data.materials.new(nome); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    bsdf = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (escala, escala, escala)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    def tex(arq, cor=True):
        t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(f"{REC}/texturas/{pasta}/{arq}")
        t.projection = "BOX"; t.projection_blend = 0.3
        if not cor: t.image.colorspace_settings.name = "Non-Color"
        l.new(mp.outputs["Vector"], t.inputs["Vector"]); return t
    d = tex("diff.jpg")
    if tom:
        mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0; mix.inputs[7].default_value = (*tom, 1)
        l.new(d.outputs["Color"], mix.inputs[6]); l.new(mix.outputs[2], bsdf.inputs["Base Color"])
    else:
        l.new(d.outputs["Color"], bsdf.inputs["Base Color"])
    a = tex("arm.jpg", False); sep = n.new("ShaderNodeSeparateColor")
    l.new(a.outputs["Color"], sep.inputs["Color"]); l.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nm = tex("nor_gl.jpg", False); nmap = n.new("ShaderNodeNormalMap")
    l.new(nm.outputs["Color"], nmap.inputs["Color"]); l.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def ligar(o):
    cena.collection.objects.link(o); return o

# ---------------------------------------------------------------- terreno com colinas suaves
bpy.ops.mesh.primitive_grid_add(x_subdivisions=220, y_subdivisions=220, size=420)
terra = bpy.context.object; terra.name = "Terreno"
for v in terra.data.vertices:
    x, y = v.co.x, v.co.y
    h = 2.2 * math.sin(x * 0.018 + 1.3) * math.cos(y * 0.015) + 1.1 * math.sin(x * 0.05 + y * 0.03)
    d = math.hypot(x, y)
    h *= min(1.0, max(0.0, (d - 25) / 60))       # plano perto da base
    if math.hypot(x - 26, y - 46) < 20:            # açude (rebaixado)
        h -= 1.6 * (1 - math.hypot(x - 26, y - 46) / 20)
    if y > 170: h += (y - 170) * 0.25              # morro ao fundo
    v.co.z = h
bpy.ops.object.shade_smooth()
grama = mat_pbr("Pasto", "grass_ground", 0.22, tom=(0.78, 0.92, 0.55))
terra.data.materials.append(grama)

# estrada de terra vermelha (faixa)
bpy.ops.mesh.primitive_plane_add(size=1); est = bpy.context.object
est.scale = (5.0, 260, 1); est.location = (-24, 60, 0.03); est.rotation_euler[2] = math.radians(8)
est.data.materials.append(mat_pbr("Estrada", "red_laterite_soil_stones", 0.25))

# ---------------------------------------------------------------- base de pouso com H
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=4.2, depth=0.12, location=(0, 14, 0.06))
base = bpy.context.object; base.data.materials.append(mat_pbr("Concreto", "concrete_floor_worn_001", 0.5))
branco = bpy.data.materials.new("Tinta"); branco.use_nodes = True
branco.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.82, 1)
amar = bpy.data.materials.new("Amarelo"); amar.use_nodes = True
amar.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.62, 0.05, 1)
for (lx, ly, sx, sy) in [(-1.1, 0, 0.35, 2.4), (1.1, 0, 0.35, 2.4), (0, 0, 1.1, 0.35)]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(lx, 14 + ly, 0.125)); c = bpy.context.object
    c.scale = (sx, sy, 0.01); c.data.materials.append(branco)
bpy.ops.mesh.primitive_torus_add(major_radius=3.7, minor_radius=0.12, location=(0, 14, 0.12)); t = bpy.context.object
t.scale[2] = 0.08; t.data.materials.append(amar)

# ---------------------------------------------------------------- aros de treino (laranja brilhando)
aro = bpy.data.materials.new("Aro"); aro.use_nodes = True
pb = aro.node_tree.nodes["Principled BSDF"]; pb.inputs["Base Color"].default_value = (1.0, 0.35, 0.05, 1)
pb.inputs["Emission Color"].default_value = (1.0, 0.38, 0.06, 1); pb.inputs["Emission Strength"].default_value = 6.0
for (x, y, z, rz) in [(6, 34, 3.2, 10), (-10, 62, 4.0, -25), (14, 95, 3.4, 30)]:
    bpy.ops.mesh.primitive_torus_add(major_radius=2.0, minor_radius=0.09, location=(x, y, z), rotation=(math.radians(90), 0, math.radians(rz)))
    bpy.context.object.data.materials.append(aro)
    for s in (-1, 1):   # postes do aro
        bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=z - 2.0, location=(x + s * 0.0, y, (z - 2.0) / 2))

# ---------------------------------------------------------------- açude
bpy.ops.mesh.primitive_plane_add(size=1, location=(26, 46, -0.30)); agua = bpy.context.object
agua.scale = (34, 22, 1)
ma = bpy.data.materials.new("Agua"); ma.use_nodes = True
p = ma.node_tree.nodes["Principled BSDF"]; p.inputs["Base Color"].default_value = (0.12, 0.16, 0.12, 1)
p.inputs["Roughness"].default_value = 0.04; p.inputs["Transmission Weight"].default_value = 0.0
p.inputs["IOR"].default_value = 1.33
noise = ma.node_tree.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 30
bump = ma.node_tree.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.06
ma.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"]); ma.node_tree.links.new(bump.outputs["Normal"], p.inputs["Normal"])
agua.data.materials.append(ma)

# ---------------------------------------------------------------- galpão
bpy.ops.mesh.primitive_cube_add(size=1, location=(-46, 110, 3)); g = bpy.context.object
g.scale = (22, 12, 6); g.data.materials.append(mat_pbr("Parede", "clay_plaster", 0.25, tom=(0.95, 0.9, 0.82)))
for s in (-1, 1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-46, 110 + s * 3.1, 6.8)); r = bpy.context.object
    r.scale = (23.5, 6.8, 0.18); r.rotation_euler[0] = s * math.radians(-17)
    r.data.materials.append(mat_pbr("Telha", "clay_roof_tiles_02", 0.35))
bpy.ops.mesh.primitive_cube_add(size=1, location=(-46, 103.95, 2.2)); port = bpy.context.object
port.scale = (6, 0.1, 4.2)
mp_ = bpy.data.materials.new("Portao"); mp_.use_nodes = True
mp_.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.13, 0.22, 1)
mp_.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.6
port.data.materials.append(mp_)

# ---------------------------------------------------------------- biruta
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=6, location=(9, 8, 3))
bpy.ops.mesh.primitive_cone_add(radius1=0.45, radius2=0.18, depth=2.2, location=(9.9, 8.3, 5.8), rotation=(0, math.radians(80), math.radians(20)))
bpy.context.object.data.materials.append(aro)

# ---------------------------------------------------------------- postes e fios
madeira = bpy.data.materials.new("Poste"); madeira.use_nodes = True
madeira.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.25, 0.2, 0.15, 1)
topos = []
for i in range(7):
    x, y = -32 + i * 1.5, -10 + i * 38
    bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=9, location=(x, y, 4.5)); bpy.context.object.data.materials.append(madeira)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 8.4)); cr = bpy.context.object; cr.scale = (2.0, 0.12, 0.12); cr.data.materials.append(madeira)
    topos.append((x, y))
fio_m = bpy.data.materials.new("Fio"); fio_m.use_nodes = True
fio_m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
for k in (-0.9, 0.0, 0.9):
    for a, b in zip(topos, topos[1:]):
        cu = bpy.data.curves.new("fio", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.012
        sp = cu.splines.new("POLY"); sp.points.add(8)
        for j in range(9):
            t = j / 8
            x = a[0] + (b[0] - a[0]) * t + k; y = a[1] + (b[1] - a[1]) * t
            z = 8.5 - 0.9 * math.sin(math.pi * t)
            sp.points[j].co = (x, y, z, 1)
        ob = bpy.data.objects.new("fio", cu); cu.materials.append(fio_m); ligar(ob)

# ---------------------------------------------------------------- cerca ao longo da estrada
for i in range(40):
    y = -20 + i * 5.5
    x = -18 + y * math.tan(math.radians(8)) * 0.0 - 0.0
    bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=1.4, location=(-19.5 + y * 0.14, y, 0.7)); bpy.context.object.data.materials.append(madeira)
for zf in (0.55, 1.05):
    cu = bpy.data.curves.new("arame", "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 0.006
    sp = cu.splines.new("POLY"); sp.points.add(1)
    sp.points[0].co = (-19.5 - 20 * 0.14, -20, zf, 1); sp.points[1].co = (-19.5 + 194.5 * 0.14, 194.5, zf, 1)
    ob = bpy.data.objects.new("arame", cu); cu.materials.append(fio_m); ligar(ob)

# ---------------------------------------------------------------- árvores (eucaliptal + copas no pasto)
def importar(pasta, nome):
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f"{REC}/modelos/{pasta}/{nome}")
    novos = [o for o in bpy.data.objects if o not in antes]
    col = bpy.data.collections.new(pasta)
    for o in novos:
        for c in o.users_collection: c.objects.unlink(o)
        col.objects.link(o)
    return col
arv1 = importar("island_tree_01", "island_tree_01_1k.gltf")
arv2 = importar("island_tree_02", "island_tree_02_1k.gltf")
arbusto = importar("shrub_02", "shrub_02_1k.gltf")
pedra = importar("boulder_01", "boulder_01_1k.gltf")
def instancia(col, x, y, esc, rz=None):
    o = bpy.data.objects.new(col.name + "_i", None); o.instance_type = "COLLECTION"; o.instance_collection = col
    o.location = (x, y, 0); o.scale = (esc, esc, esc); o.rotation_euler[2] = rz if rz is not None else random.uniform(0, 6.28)
    ligar(o); return o
for i in range(16):                                   # fileira do fundo
    instancia(random.choice([arv1, arv2]), -75 + i * 10 + random.uniform(-2, 2), 118 + random.uniform(-5, 5), random.uniform(2.6, 3.4))
for (x, y, e) in [(44, 30, 2.2), (-34, 36, 2.0), (52, 70, 2.6), (-6, 96, 2.4), (12, 60, 1.8)]:
    instancia(random.choice([arv1, arv2]), x, y, e)
for i in range(18):
    instancia(arbusto, random.uniform(-40, 50), random.uniform(20, 140), random.uniform(0.8, 1.6))
for (x, y, e) in [(-6, 26, 0.9), (30, 54, 1.4), (5, 52, 0.7)]:
    instancia(pedra, x, y, e)

# ---------------------------------------------------------------- capim (lâminas) perto da câmera
bpy.ops.mesh.primitive_plane_add(size=1); lam = bpy.context.object; lam.name = "Lamina"
for v in lam.data.vertices:
    t = v.co.y + 0.5
    v.co.x, v.co.y, v.co.z = t * 0.5, v.co.x * 0.035 * (1.0 - 0.8 * t), (t ** 2) * 0.12
mc = bpy.data.materials.new("Capim"); mc.use_nodes = True
pc = mc.node_tree.nodes["Principled BSDF"]; pc.inputs["Base Color"].default_value = (0.26, 0.32, 0.08, 1)
pc.inputs["Roughness"].default_value = 0.7; pc.inputs["Subsurface Weight"].default_value = 0.15
lam.data.materials.append(mc)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=60, y_subdivisions=60, size=1); area = bpy.context.object
area.scale = (40, 45, 1); area.location = (0, 22, 0.02)
import bmesh
bm = bmesh.new(); bm.from_mesh(area.data)
fora = [f for f in bm.faces if math.hypot(f.calc_center_median().x * 40, f.calc_center_median().y * 45 + 22 - 14) < 4.6]
bmesh.ops.delete(bm, geom=fora, context="FACES"); bm.to_mesh(area.data); bm.free()
ps = area.modifiers.new("capim", "PARTICLE_SYSTEM").particle_system.settings
ps.type = "HAIR"; ps.count = 320000; ps.render_type = "PATH"; ps.hair_length = 0.16
ps.use_advanced_hair = True; ps.brownian_factor = 0.0; ps.factor_random = 0.25
ps.length_random = 0.6
try:
    ps.radius_scale = 0.0022; ps.root_radius = 1.0; ps.tip_radius = 0.0
except Exception as e:
    print("raio do capim:", e)
area.data.materials.append(mc)
ps.material_slot = "Capim"
mt = bpy.data.materials.new("Invisivel"); mt.use_nodes = True
nn = mt.node_tree.nodes; nn.clear(); o_ = nn.new("ShaderNodeOutputMaterial"); tr = nn.new("ShaderNodeBsdfTransparent")
mt.node_tree.links.new(tr.outputs[0], o_.inputs["Surface"]); area.data.materials.append(mt); area.active_material_index = 1
area.show_instancer_for_render = False
lam.hide_render = True

# ---------------------------------------------------------------- o E88 pairando
try:
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath="/home/claude/simulador-drone/voo_e88/drone/e88.glb")
    novos = [o for o in bpy.data.objects if o not in antes]
    raiz = bpy.data.objects.new("E88", None); ligar(raiz)
    for o in novos:
        if o.parent is None: o.parent = raiz
    raiz.location = (0.35, 4.1, 1.85); raiz.rotation_euler = (math.radians(-9), math.radians(5), math.radians(180))
    raiz.scale = (1.0, 1.0, 1.0)
    for o in novos:
        if o.type != "MESH": continue
        for sl in o.material_slots:
            m = sl.material
            if not m or not m.use_nodes: continue
            b = m.node_tree.nodes.get("Principled BSDF")
            if not b: continue
            if b.inputs["Emission Strength"].default_value > 0.01: continue
            if b.inputs["Metallic"].default_value > 0.5:
                b.inputs["Base Color"].default_value = (0.18, 0.18, 0.19, 1); continue
            for l in list(b.inputs["Base Color"].links): m.node_tree.links.remove(l)
            b.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
            b.inputs["Roughness"].default_value = 0.58
except Exception as e:
    print("sem E88:", e)

# ---------------------------------------------------------------- câmera atrás do drone
cam = bpy.data.cameras.new("Cam"); cam.lens = 20; cam.dof.use_dof = True
cam.dof.focus_distance = 0.95; cam.dof.aperture_fstop = 4.0
co = bpy.data.objects.new("Cam", cam); ligar(co); cena.camera = co
co.location = (0.0, 3.15, 2.05)
alvo = Vector((1.2, 40, 0.2)); d = alvo - co.location
co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

bpy.context.view_layer.update()
cena.render.filepath = SAIDA
bpy.ops.render.render(write_still=True)
print("OK", SAIDA)
