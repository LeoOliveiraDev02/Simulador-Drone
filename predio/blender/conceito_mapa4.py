"""Imagem-conceito do MAPA 4 — CENTRO HISTÓRICO (ladeira colonial no estilo do Pelourinho, Salvador).
Sobrados coloridos de 2 e 3 andares, sacadas de ferro, ladeira de paralelepípedo, igreja azul de duas torres
no alto do largo, fim de tarde dourado, drone E88 em primeiro plano.
python3 conceito_mapa4.py SAIDA.png [largura] [amostras]"""
import math
import random
import sys

import bpy
from mathutils import Vector

args = [a for a in sys.argv[1:] if not a.endswith(".py")]
SAIDA = args[0] if args else "/tmp/mapa4.png"
LARG = int(args[1]) if len(args) > 1 else 1600
AMOSTRAS = int(args[2]) if len(args) > 2 else 64
random.seed(4)
bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene


def mat(nome, cor, rug=0.8, metal=0.0, emi=None, forca=0.0):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*cor, 1)
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    if emi:
        b.inputs["Emission Color"].default_value = (*emi, 1)
        b.inputs["Emission Strength"].default_value = forca
    return m


def mat_ruido(nome, c1, c2, escala=5.0, rug=0.85, bump=0.3):
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = escala
    tex.inputs["Detail"].default_value = 10
    rmp = nt.nodes.new("ShaderNodeValToRGB")
    rmp.color_ramp.elements[0].color = (*c1, 1)
    rmp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(tex.outputs["Fac"], rmp.inputs["Fac"])
    nt.links.new(rmp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rug
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    nt.links.new(tex.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def pedras():
    """paralelepípedos (Voronoi) para a ladeira."""
    m = bpy.data.materials.new("Pedra")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    v = nt.nodes.new("ShaderNodeTexVoronoi")
    v.feature = "DISTANCE_TO_EDGE"
    v.inputs["Scale"].default_value = 3.2
    mp = nt.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = 0.0
    mp.inputs["From Max"].default_value = 0.08
    nt.links.new(v.outputs["Distance"], mp.inputs["Value"])
    rmp = nt.nodes.new("ShaderNodeValToRGB")
    rmp.color_ramp.elements[0].color = (0.06, 0.055, 0.05, 1)
    rmp.color_ramp.elements[1].color = (0.36, 0.32, 0.27, 1)
    nt.links.new(mp.outputs["Result"], rmp.inputs["Fac"])
    nt.links.new(rmp.outputs["Color"], b.inputs["Base Color"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.8
    nt.links.new(mp.outputs["Result"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.75
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], v.inputs["Vector"])
    return m


def caixa(centro, tam, m, rot_z=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centro, rotation=(0, 0, math.radians(rot_z)))
    o = bpy.context.object
    o.scale = tam
    o.data.materials.append(m)
    return o


def cil(centro, r, h, m, lados=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=lados, radius=r, depth=h, location=centro)
    o = bpy.context.object
    o.data.materials.append(m)
    return o


def cone(centro, r, h, m, lados=4, rot=45):
    bpy.ops.mesh.primitive_cone_add(vertices=lados, radius1=r, radius2=0, depth=h, location=centro, rotation=(0, 0, math.radians(rot)))
    o = bpy.context.object
    o.data.materials.append(m)
    return o


CORES = [(0.82, 0.32, 0.12), (0.95, 0.72, 0.18), (0.18, 0.42, 0.72), (0.86, 0.48, 0.58), (0.35, 0.62, 0.42), (0.95, 0.88, 0.70),
         (0.62, 0.18, 0.20), (0.40, 0.65, 0.80), (0.92, 0.55, 0.22), (0.70, 0.75, 0.30)]
branco = mat("Branco", (0.9, 0.88, 0.82), 0.7)
ferro = mat("Ferro", (0.03, 0.03, 0.035), 0.4, 0.8)
madeira_j = mat("Janela", (0.15, 0.32, 0.22), 0.6)
madeira_j2 = mat("Janela2", (0.45, 0.12, 0.08), 0.6)
vidro = mat("Vidro", (0.02, 0.025, 0.03), 0.05)
telha = mat_ruido("Telha", (0.42, 0.14, 0.07), (0.62, 0.26, 0.12), 8.0, 0.8)
chao = pedras()
calcada = mat_ruido("Calcada", (0.55, 0.53, 0.5), (0.7, 0.68, 0.64), 12.0)
luz_quente = mat("Lampiao", (1, 0.8, 0.5), 0.3, emi=(1.0, 0.65, 0.3), forca=25.0)


def sobrado(x0, y_base, z_base, largura, andares, frente_y, cor, lado=1):
    """sobrado colonial: fachada no plano y = frente_y, virada para -lado."""
    alt_andar = 3.6
    h = andares * alt_andar + 1.0
    prof = 9.0
    pc = mat_ruido("Parede%d" % random.randint(0, 99999), tuple(c * 0.92 for c in cor), cor, 3.0, 0.85, 0.08)
    caixa((x0 + largura / 2, frente_y + lado * prof / 2, z_base + h / 2), (largura, prof, h), pc)
    # cornija e embasamento brancos
    caixa((x0 + largura / 2, frente_y - lado * 0.15, z_base + h - 0.3), (largura + 0.1, 0.5, 0.6), branco)
    caixa((x0 + largura / 2, frente_y - lado * 0.08, z_base + 0.5), (largura + 0.05, 0.3, 1.0), branco)
    for xx in (x0 + 0.25, x0 + largura - 0.25):
        caixa((xx, frente_y - lado * 0.1, z_base + h / 2), (0.5, 0.35, h), branco)
    # telhado de duas águas
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x0 + largura / 2, frente_y + lado * prof / 2, z_base + h + 1.0))
    t = bpy.context.object
    t.scale = (largura + 0.4, prof + 1.2, 2.0)
    t.data.materials.append(telha)
    me = t.data
    for v in me.vertices:
        if v.co.z > 0:
            v.co.y *= 0.05
    # janelas com sacadas
    n = max(2, int(largura / 2.6))
    for a in range(andares):
        zj = z_base + a * alt_andar + 1.4
        for i in range(n):
            xj = x0 + (i + 0.5) * largura / n
            portada = madeira_j if (i + a) % 2 == 0 else madeira_j2
            caixa((xj, frente_y - lado * 0.06, zj + 1.1), (1.2, 0.12, 2.2), vidro)
            caixa((xj, frente_y - lado * 0.12, zj + 1.1), (1.4, 0.1, 2.4), branco)     # moldura
            caixa((xj - 0.45, frente_y - lado * 0.16, zj + 1.0), (0.42, 0.06, 2.0), portada)
            caixa((xj + 0.45, frente_y - lado * 0.16, zj + 1.0), (0.42, 0.06, 2.0), portada)
            if a > 0:
                caixa((xj, frente_y - lado * 0.55, zj - 0.05), (1.6, 0.9, 0.1), branco)   # sacada
                for k in range(9):
                    caixa((xj - 0.75 + k * 0.1875, frente_y - lado * 0.98, zj + 0.45), (0.025, 0.025, 0.9), ferro)
                caixa((xj, frente_y - lado * 0.98, zj + 0.92), (1.6, 0.04, 0.04), ferro)
    return h


# ---- ladeira (sobe para +x), largo triangular no alto
def z_ladeira(x):
    return max(0.0, min(9.0, (x + 10) * 0.16))


bpy.ops.mesh.primitive_plane_add(size=1)
chao_o = bpy.context.object
me = chao_o.data
# malha da rua em grade
bpy.ops.object.delete()
verts, faces = [], []
NX, NY = 120, 40
for j in range(NY + 1):
    for i in range(NX + 1):
        x = -40 + i * 110 / NX
        y = -14 + j * 28 / NY
        verts.append((x, y, z_ladeira(x)))
for j in range(NY):
    for i in range(NX):
        a = j * (NX + 1) + i
        faces.append((a, a + 1, a + NX + 2, a + NX + 1))
me = bpy.data.meshes.new("rua")
me.from_pydata(verts, [], faces)
ob = bpy.data.objects.new("rua", me)
cena.collection.objects.link(ob)
ob.data.materials.append(chao)
# calçadas
for yy in (-7.2, 7.2):
    for i in range(22):
        x = -40 + i * 5
        caixa((x + 2.5, yy, z_ladeira(x + 2.5) + 0.12), (5.05, 1.6, 0.24), calcada)

# sobrados dos dois lados (fachadas viradas para a rua)
for lado, fy in ((1, 8.0), (-1, -8.0)):
    x = -40.0
    k = 0
    while x < 48:
        w = random.uniform(5.5, 9.0)
        andares = random.choice((2, 3, 3, 2, 3))
        zb = z_ladeira(x + w / 2) - 0.5
        sobrado(x, 0, zb, w, andares, fy, CORES[(k * 3 + (0 if lado > 0 else 5)) % len(CORES)], lado)
        x += w + 0.05
        k += 1

# igreja azul de duas torres no alto do largo
ix = 66.0
zi = 9.0
azul = mat_ruido("Azul", (0.12, 0.30, 0.62), (0.18, 0.40, 0.75), 3.0, 0.8, 0.05)
caixa((ix + 6, 0, zi + 8), (12, 16, 16), azul)
for yy in (-4.2, 4.2):
    caixa((ix - 0.15, yy, zi + 8), (0.4, 0.8, 16.2), branco)
caixa((ix - 0.15, 0, zi + 15.9), (0.4, 16.2, 0.6), branco)
caixa((ix - 0.15, 0, zi + 0.4), (0.4, 16.2, 0.8), branco)
for yy in (-6.5, 6.5):
    caixa((ix + 1.5, yy, zi + 12), (4.0, 4.0, 24), azul)
    for oy in (-1.9, 1.9):
        caixa((ix - 0.45, yy + oy, zi + 12), (0.3, 0.45, 24.2), branco)
    caixa((ix + 1.5, yy, zi + 24.6), (4.4, 4.4, 1.2), branco)
    cone((ix + 1.5, yy, zi + 27.8), 2.6, 5.0, mat("Coruchéu", (0.85, 0.85, 0.82), 0.4), lados=8, rot=22.5)
    caixa((ix - 0.4, yy, zi + 19.5), (0.2, 1.6, 2.8), vidro)
# frontão curvo e portas
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=2.2, depth=0.6, location=(ix - 0.2, 0, zi + 17.5), rotation=(0, math.radians(90), 0))
bpy.context.object.data.materials.append(branco)
for yy in (-3, 0, 3):
    caixa((ix - 0.3, yy, zi + 2.0), (0.3, 1.8, 3.8), madeira_j2)
    caixa((ix - 0.3, yy, zi + 7.5), (0.3, 1.4, 2.6), vidro)
# escadaria até a igreja
for k in range(10):
    caixa((ix - 2 - k * 0.5, 0, zi - k * 0.18), (0.5, 12.0, 0.18 + k * 0.36), calcada)

# postes com lampião aceso, varais de bandeirinhas
for x in range(-36, 56, 9):
    for yy in (-6.5, 6.5):
        caixa((x, yy, z_ladeira(x) + 1.8), (0.12, 0.12, 3.6), ferro)
        cil((x, yy - math.copysign(0.4, yy), z_ladeira(x) + 3.7), 0.18, 0.5, luz_quente, lados=8)
for x in range(-18, 50, 7):
    pts = []
    for i in range(13):
        t = i / 12
        y = -7 + 14 * t
        z = z_ladeira(x) + 8.5 - 1.6 * math.sin(math.pi * t)
        pts.append((x, y, z))
    for i, p in enumerate(pts[:-1]):
        c = CORES[(i + x) % len(CORES)]
        bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.25, radius2=0, depth=0.45, location=(p[0], p[1], p[2] - 0.35),
                                        rotation=(math.pi, 0, 0))
        bpy.context.object.data.materials.append(mat("Band%d" % random.randint(0, 99999), c, 0.7))

# drone E88 em primeiro plano (forma simples: corpo, braços, hélices)
corpo = mat("Corpo", (0.03, 0.03, 0.035), 0.35)
cinza = mat("Cinza", (0.25, 0.26, 0.28), 0.4)
dx, dy, dz = -29.2, -2.55, 6.35
caixa((dx, dy, dz), (0.32, 0.14, 0.07), corpo)
for sx in (-1, 1):
    for sy in (-1, 1):
        a = (dx + sx * 0.2, dy + sy * 0.2, dz + 0.02)
        caixa(((dx + a[0]) / 2, (dy + a[1]) / 2, dz + 0.02), (0.26, 0.03, 0.02), corpo, rot_z=45 * sx * sy)
        cil(a, 0.03, 0.05, cinza, lados=12)
        cil((a[0], a[1], a[2] + 0.035), 0.13, 0.005, mat("Helice", (0.2, 0.2, 0.22), 0.5), lados=24)
cil((dx + 0.17, dy, dz - 0.01), 0.025, 0.04, vidro, lados=12)

# ---- luz: sol baixo de fim de tarde vindo do fim da ladeira, céu
sol = bpy.data.lights.new("sol", "SUN")
sol.energy = 3.2
sol.color = (1.0, 0.6, 0.32)
sol.angle = math.radians(1.5)
so = bpy.data.objects.new("sol", sol)
cena.collection.objects.link(so)
so.rotation_euler = (math.radians(74), 0, math.radians(-25))
w = bpy.data.worlds.new("ceu")
cena.world = w
w.use_nodes = True
nt = w.node_tree
sky = nt.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "MULTIPLE_SCATTERING"
except Exception:
    try:
        sky.sky_type = "NISHITA"
    except Exception:
        pass
try:
    sky.sun_elevation = math.radians(14)
    sky.sun_rotation = math.radians(170)
except Exception:
    pass
nt.links.new(sky.outputs["Color"], nt.nodes["Background"].inputs["Color"])
nt.nodes["Background"].inputs["Strength"].default_value = 0.22

cam = bpy.data.cameras.new("cam")
cam.lens = 22
co = bpy.data.objects.new("cam", cam)
cena.collection.objects.link(co)
cena.camera = co
co.location = (-31.5, -3.2, 5.9)
d = Vector((40, 1.5, 16)) - co.location
co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
cena.render.engine = "CYCLES"
cena.cycles.samples = AMOSTRAS
cena.cycles.use_denoising = True
cena.render.resolution_x = LARG
cena.render.resolution_y = int(LARG * 9 / 16)
cena.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in cena.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
try:
    cena.view_settings.look = "AgX - Punchy"
except Exception:
    cena.view_settings.look = "None"
cena.render.filepath = SAIDA
bpy.ops.render.render(write_still=True)
print("salvo", SAIDA)
