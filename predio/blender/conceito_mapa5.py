"""Imagem-conceito do MAPA 5 — PLATAFORMA DE PETRÓLEO EM ALTO-MAR (fim de tarde, vento forte).
Plataforma fixa sobre quatro pernas, conveses com módulos e tubos, heliponto com H, guindastes,
torre de perfuração, queimador (flare) com fogo, navio de apoio, mar com ondas, drone E88 chegando.
python3 conceito_mapa5.py SAIDA.png [largura] [amostras]"""
import math
import random
import sys

import bpy
import bmesh
from mathutils import Vector, Matrix

args = [a for a in sys.argv[1:] if not a.endswith(".py")]
SAIDA = args[0] if args else "/tmp/mapa5.png"
LARG = int(args[1]) if len(args) > 1 else 1600
AMOSTRAS = int(args[2]) if len(args) > 2 else 64
random.seed(5)
bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene
MATS = {}


def mat(nome, cor, rug=0.7, metal=0.0, emi=None, forca=0.0):
    if nome in MATS:
        return MATS[nome]
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    if emi:
        b.inputs["Emission Color"].default_value = (*emi, 1)
        b.inputs["Emission Strength"].default_value = forca
    MATS[nome] = m
    return m


class M:
    def __init__(self, nome):
        self.nome = nome
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def fim(self):
        me = bpy.data.meshes.new(self.nome)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        o = bpy.data.objects.new(self.nome, me)
        cena.collection.objects.link(o)
        for p in me.polygons:
            p.use_smooth = False
        return o


def caixa(g, c, t, m, rz=0.0):
    r = bmesh.ops.create_cube(g.bm, size=1.0)
    M_ = Matrix.Translation(Vector(c)) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Diagonal(Vector((*t, 1)))
    bmesh.ops.transform(g.bm, matrix=M_, verts=r["verts"])
    k = g.mi(m)
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = k


def barra(g, a, b, e, m):
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    if L < 1e-4:
        return
    r = bmesh.ops.create_cone(g.bm, cap_ends=True, segments=8, radius1=e, radius2=e, depth=L)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(g.bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=r["verts"])
    k = g.mi(m)
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = k


def cil(g, base, r, h, m, lados=24, eixo=(0, 0, 1)):
    e = Vector(eixo).normalized()
    rr = bmesh.ops.create_cone(g.bm, cap_ends=True, segments=lados, radius1=r, radius2=r, depth=h)
    rot = Vector((0, 0, 1)).rotation_difference(e).to_matrix().to_4x4()
    bmesh.ops.transform(g.bm, matrix=Matrix.Translation(Vector(base) + e * h / 2) @ rot, verts=rr["verts"])
    k = g.mi(m)
    for f in {f for v in rr["verts"] for f in v.link_faces}:
        f.material_index = k


amarelo = mat("Amarelo", (0.85, 0.6, 0.05), 0.5)
branco = mat("Branco", (0.85, 0.85, 0.83), 0.55)
cinza = mat("Cinza", (0.35, 0.36, 0.37), 0.5, 0.6)
laranja = mat("Laranja", (0.9, 0.32, 0.05), 0.5)
verde = mat("Verde", (0.12, 0.35, 0.22), 0.6)
vermelho = mat("Vermelho", (0.6, 0.06, 0.04), 0.5)
escuro = mat("Escuro", (0.05, 0.05, 0.055), 0.6, 0.5)
ferrugem = mat("Ferrugem", (0.32, 0.14, 0.06), 0.8, 0.3)
janela = mat("Janela", (1.0, 0.85, 0.6), 0.3, emi=(1.0, 0.8, 0.5), forca=6.0)
fogo = mat("Fogo", (1, 0.4, 0.05), 0.5, emi=(1.0, 0.26, 0.03), forca=7.0)

g = M("Plataforma")
# pernas (jaqueta) saindo do mar com contraventamento
pernas = [(-18, -14), (18, -14), (-18, 14), (18, 14)]
for (x, y) in pernas:
    cil(g, (x * 1.25, y * 1.25, -30), 2.2, 30, amarelo, lados=20, eixo=(-x * 0.008, -y * 0.008, 1))
    cil(g, (x, y, -0.5), 2.0, 22.5, amarelo, lados=20)
for z in (-8, 2, 12):
    for (a, b) in ((0, 1), (2, 3), (0, 2), (1, 3)):
        pa, pb = pernas[a], pernas[b]
        barra(g, (pa[0], pa[1], z), (pb[0], pb[1], z), 0.5, amarelo)
        barra(g, (pa[0], pa[1], z), (pb[0], pb[1], z + 10), 0.35, amarelo)
# conveses
for z, (sx, sy) in ((22, (52, 40)), (30, (50, 38)), (38, (46, 34))):
    caixa(g, (0, 0, z), (sx, sy, 1.2), cinza)
    for k in range(int(sx / 2)):
        barra(g, (-sx / 2 + k * 2, -sy / 2, z + 0.6), (-sx / 2 + k * 2, -sy / 2, z + 1.7), 0.04, amarelo)
    barra(g, (-sx / 2, -sy / 2, z + 1.7), (sx / 2, -sy / 2, z + 1.7), 0.05, amarelo)
# módulos de processo (caixas coloridas, tanques e tubos)
for i in range(14):
    x, y = random.uniform(-20, 20), random.uniform(-14, 14)
    z = random.choice((22.6, 30.6))
    caixa(g, (x, y, z + 2.5), (random.uniform(3, 8), random.uniform(3, 7), 5), random.choice((branco, verde, cinza, ferrugem)))
for i in range(10):
    x, y = random.uniform(-20, 20), random.uniform(-14, 14)
    cil(g, (x, y, 30.6), random.uniform(1.0, 2.2), random.uniform(4, 7), random.choice((branco, cinza, amarelo)))
# feixes de tubos paralelos (organizados, como numa plataforma de verdade)
for (y0, z, n) in ((-17.0, 24.5, 6), (16.5, 25.0, 5), (-15.5, 32.5, 5), (15.0, 33.0, 6)):
    for k in range(n):
        r = 0.18 + 0.06 * (k % 3)
        barra(g, (-24, y0 + k * 0.7, z + (k % 2) * 0.5), (24, y0 + k * 0.7, z + (k % 2) * 0.5), r, (cinza, amarelo, verde, branco)[k % 4])
for (x0, z) in ((-23.0, 26.5), (22.0, 34.5)):
    for k in range(4):
        barra(g, (x0 + k * 0.7, -17, z), (x0 + k * 0.7, 17, z), 0.22, (amarelo, cinza)[k % 2])
# acomodações (prédio branco com janelas acesas) + heliponto em cima
hx, hy = -20.0, -12.0
caixa(g, (hx, hy, 46.0), (14, 12, 14), branco)
for zz in (41.5, 44.5, 47.5, 50.5):
    for k in range(5):
        caixa(g, (hx + 7.02, hy - 4.5 + k * 2.2, zz), (0.05, 1.2, 0.9), janela)
cil(g, (hx - 2, hy - 2, 53.0), 11.0, 0.6, escuro, lados=8)
for (dx, dy, sx, sy) in ((-2.4, 0, 0.9, 6.0), (2.4, 0, 0.9, 6.0), (0, 0, 4.0, 0.9)):
    caixa(g, (hx - 2 + dx, hy - 2 + dy, 53.32), (sx, sy, 0.05), branco)
for i in range(32):
    a = 2 * math.pi * i / 32
    caixa(g, (hx - 2 + math.cos(a) * 9.6, hy - 2 + math.sin(a) * 9.6, 53.32), (1.2, 0.25, 0.05), amarelo, rz=math.degrees(a) + 90)
for i in range(8):
    a = 2 * math.pi * i / 8
    barra(g, (hx - 2 + math.cos(a) * 10.5, hy - 2 + math.sin(a) * 10.5, 52.7), (hx + math.cos(a) * 3, hy + math.sin(a) * 3, 46.0), 0.25, cinza)
# torre de perfuração (treliça alta)
tx, ty = 12.0, 6.0
for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
    barra(g, (tx + sx * 5, ty + sy * 5, 38.6), (tx + sx * 1.2, ty + sy * 1.2, 82), 0.3, branco)
for k in range(12):
    z = 38.6 + k * 3.6
    s = 5 - (k * 3.6) / 43.4 * 3.8
    pts = [(tx - s, ty - s), (tx + s, ty - s), (tx + s, ty + s), (tx - s, ty + s)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        barra(g, (a[0], a[1], z), (b[0], b[1], z), 0.12, branco)
        barra(g, (a[0], a[1], z), (b[0], b[1], z + 3.6), 0.08, branco)
caixa(g, (tx, ty, 83), (3, 3, 2), laranja)
# lança do queimador (flare boom) inclinada para fora com fogo na ponta
fa = Vector((24, 14, 38))
fb = Vector((52, 34, 70))
d = fb - fa
for (ox, oy) in ((0.8, 0), (-0.8, 0), (0, 0.8)):
    barra(g, fa + Vector((ox, oy, 0)), fb + Vector((ox * 0.3, oy * 0.3, 0)), 0.22, branco)
n = 14
for k in range(n):
    p = fa + d * (k / n)
    q = fa + d * ((k + 1) / n)
    barra(g, p + Vector((0.8, 0, 0)), q + Vector((-0.8, 0, 0)), 0.1, branco)
    barra(g, p + Vector((0, 0.8, 0)), q + Vector((0.8 * 0.3, 0, 0)), 0.1, branco)
g.fim()

# fogo do flare (várias "línguas" emissivas)
for k in range(9):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(fb.x + random.uniform(-0.8, 0.8) + k * 0.45, fb.y + random.uniform(-0.6, 0.6) + k * 0.25, fb.z + 1.5 + k * 1.1))
    o = bpy.context.object
    o.scale = (1.6 - k * 0.1, 1.2 - k * 0.08, 2.4 - k * 0.15)
    o.data.materials.append(fogo)
lz = bpy.data.lights.new("luz_fogo", "POINT")
lz.energy = 600000
lz.color = (1, 0.5, 0.15)
lo = bpy.data.objects.new("luz_fogo", lz)
lo.location = (fb.x, fb.y, fb.z + 4)
cena.collection.objects.link(lo)

# guindastes
for (cx, cy, giro) in ((18, -16, -40), (-24, 15, 150)):
    gg = M("Guindaste")
    cil(gg, (cx, cy, 38.6), 1.4, 5, amarelo, lados=16)
    caixa(gg, (cx, cy, 44.5), (4, 3, 2.5), amarelo)
    r = math.radians(giro)
    ponta = Vector((cx + math.cos(r) * 30, cy + math.sin(r) * 30, 62))
    for o in (-0.8, 0.8):
        barra(gg, (cx + math.cos(r + 1.57) * o, cy + math.sin(r + 1.57) * o, 45), ponta, 0.25, amarelo)
    barra(gg, ponta, (ponta.x, ponta.y, 40), 0.04, escuro)
    gg.fim()

# navio de apoio
nv = M("Navio")
caixa(nv, (-70, -40, 1.5), (60, 14, 5), vermelho)
caixa(nv, (-70, -40, 4.5), (58, 13, 1.2), cinza)
caixa(nv, (-50, -40, 9), (12, 11, 8), branco)
for k in range(5):
    caixa(nv, (-43.98, -44 + k * 2, 11), (0.05, 1.2, 0.9), janela)
for k in range(4):
    caixa(nv, (-78 + k * 7, -40, 6.5), (5, 10, 3), random.choice((laranja, verde, branco)))
nv.fim()

# mar: modificador Ocean (ondas de verdade) + plano grande no fundo até o horizonte
bpy.ops.mesh.primitive_plane_add(size=6000, location=(0, 0, -0.6))
fundo = bpy.context.object
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
mar = bpy.context.object
oc = mar.modifiers.new("Ocean", "OCEAN")
oc.geometry_mode = "GENERATE"
oc.resolution = 10
oc.spatial_size = 220
oc.repeat_x = 12
oc.repeat_y = 12
oc.wave_scale = 2.2
oc.wind_velocity = 18.0
oc.choppiness = 1.3
mar.location = (-1320, -1320, 0)
mm = bpy.data.materials.new("Mar")
mm.use_nodes = True
nt = mm.node_tree
b = nt.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.01, 0.04, 0.06, 1)
b.inputs["Roughness"].default_value = 0.08
try:
    b.inputs["Transmission Weight"].default_value = 0.0
except Exception:
    pass
wv = nt.nodes.new("ShaderNodeTexWave")
wv.inputs["Scale"].default_value = 0.6
wv.inputs["Distortion"].default_value = 6.0
wv.inputs["Detail"].default_value = 6.0
nz = nt.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 0.4
nz.inputs["Detail"].default_value = 12.0
mix = nt.nodes.new("ShaderNodeMath")
mix.operation = "ADD"
nt.links.new(wv.outputs["Fac"], mix.inputs[0])
nt.links.new(nz.outputs["Fac"], mix.inputs[1])
bp = nt.nodes.new("ShaderNodeBump")
bp.inputs["Strength"].default_value = 0.35
bp.inputs["Distance"].default_value = 0.4
nt.links.new(mix.outputs["Value"], bp.inputs["Height"])
nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
mar.data.materials.append(mm)
fundo.data.materials.append(mm)

# drone E88 em primeiro plano
dr = M("Drone")
dx, dy, dz = -93.4, 69.4, 48.25
caixa(dr, (dx, dy, dz), (0.32, 0.14, 0.07), escuro)
for sx in (-1, 1):
    for sy in (-1, 1):
        a = (dx + sx * 0.2, dy + sy * 0.2, dz + 0.02)
        barra(dr, (dx, dy, dz + 0.02), a, 0.015, escuro)
        cil(dr, a, 0.03, 0.05, cinza, lados=12)
        cil(dr, (a[0], a[1], a[2] + 0.035), 0.13, 0.005, cinza, lados=24)
dr.fim()

# céu de fim de tarde
sol = bpy.data.lights.new("sol", "SUN")
sol.energy = 2.4
sol.color = (1.0, 0.68, 0.42)
sol.angle = math.radians(1.0)
so = bpy.data.objects.new("sol", sol)
cena.collection.objects.link(so)
so.rotation_euler = (math.radians(80), 0, math.radians(120))
w = bpy.data.worlds.new("ceu")
cena.world = w
w.use_nodes = True
nt = w.node_tree
sky = nt.nodes.new("ShaderNodeTexSky")
for tipo in ("MULTIPLE_SCATTERING", "NISHITA"):
    try:
        sky.sky_type = tipo
        break
    except Exception:
        pass
try:
    sky.sun_elevation = math.radians(7)
    sky.sun_rotation = math.radians(300)
except Exception:
    pass
nt.links.new(sky.outputs["Color"], nt.nodes["Background"].inputs["Color"])
nt.nodes["Background"].inputs["Strength"].default_value = 0.22

cam = bpy.data.cameras.new("cam")
cam.lens = 26
co = bpy.data.objects.new("cam", cam)
cena.collection.objects.link(co)
cena.camera = co
co.location = (-95.0, 70.0, 48.0)
dd = Vector((0, 0, 36)) - co.location
co.rotation_euler = dd.to_track_quat("-Z", "Y").to_euler()
cena.render.engine = "CYCLES"
cena.cycles.samples = AMOSTRAS
cena.cycles.use_denoising = True
cena.render.resolution_x = LARG
cena.render.resolution_y = int(LARG * 9 / 16)
cena.view_settings.exposure = -0.4
try:
    cena.view_settings.look = "AgX - Punchy"
except Exception:
    pass
cena.render.filepath = SAIDA
bpy.ops.render.render(write_still=True)
print("salvo", SAIDA)
