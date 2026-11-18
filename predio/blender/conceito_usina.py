"""Imagem de referência do MAPA 3 — Usina siderúrgica abandonada (cartão trancado do menu).
python3 conceito_usina.py SAIDA.png [largura] [amostras]"""
import math
import random
import sys

import bpy
from mathutils import Vector

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/usina.png"
LARG = int(sys.argv[2]) if len(sys.argv) > 2 else 1280
AMOSTRAS = int(sys.argv[3]) if len(sys.argv) > 3 else 48
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene


def mat(nome, cor, rug=0.7, metal=0.0, emi=None, forca=0.0):
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


def ruido_mat(nome, c1, c2, escala=6.0, rug=0.8, metal=0.0):
    """material com manchas (ferrugem / sujeira)"""
    m = bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = escala
    tex.inputs["Detail"].default_value = 8
    rmp = nt.nodes.new("ShaderNodeValToRGB")
    rmp.color_ramp.elements[0].color = (*c1, 1)
    rmp.color_ramp.elements[1].color = (*c2, 1)
    rmp.color_ramp.elements[0].position = 0.4
    rmp.color_ramp.elements[1].position = 0.65
    nt.links.new(tex.outputs["Fac"], rmp.inputs["Fac"])
    nt.links.new(rmp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rug
    b.inputs["Metallic"].default_value = metal
    return m


CONC = ruido_mat("concreto", (0.09, 0.085, 0.08), (0.2, 0.19, 0.17), 3.0, 0.75)
FERRO = ruido_mat("ferro", (0.16, 0.07, 0.03), (0.22, 0.2, 0.19), 9.0, 0.6, 0.6)
AMARELO = ruido_mat("amarelo", (0.55, 0.38, 0.03), (0.2, 0.08, 0.03), 7.0, 0.5, 0.3)
TELHA = ruido_mat("telha", (0.12, 0.12, 0.13), (0.18, 0.08, 0.04), 5.0, 0.55, 0.7)
BRASA = mat("brasa", (0.1, 0.03, 0.01), 0.4, 0, (1.0, 0.32, 0.04), 40.0)
VIDRO = mat("vidro_sujo", (0.25, 0.28, 0.26), 0.3, 0, (0.75, 0.85, 1.0), 0.7)


def caixa(nome, centro, tam, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=centro, rotation=rot)
    o = bpy.context.object
    o.name = nome
    o.scale = tam
    o.data.materials.append(m)
    return o


def cil(nome, centro, r, h, m, rot=(0, 0, 0), v=32):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=centro, rotation=rot, vertices=v)
    o = bpy.context.object
    o.name = nome
    o.data.materials.append(m)
    return o


L, Wd, H = 90.0, 34.0, 20.0
# chão com poças (planos lisos escuros)
caixa("chao", (0, 0, -0.1), (L, Wd, 0.2), CONC)
POCA = mat("poca", (0.02, 0.02, 0.02), 0.03)
for i in range(9):
    caixa("poca", (random.uniform(-30, 35), random.uniform(-12, 12), 0.005), (random.uniform(2, 6), random.uniform(1.5, 4), 0.01), POCA,
          (0, 0, random.uniform(0, 3)))
# paredes laterais com janelões
for s in (-1, 1):
    caixa("parede", (0, s * Wd / 2, 4), (L, 0.4, 8), CONC)
    for i in range(10):
        x = -40 + i * 9
        caixa("janela", (x, s * Wd / 2, 12.5), (6, 0.1, 6), VIDRO)
        caixa("vao", (x, s * Wd / 2, 9.2), (6.4, 0.5, 0.4), CONC)
    caixa("parede_alta", (0, s * Wd / 2, 17.5), (L, 0.4, 5), TELHA)
caixa("fundo", (L / 2, 0, H / 2), (0.4, Wd, H), CONC)
# pilares em I e vigas de rolamento
for i in range(12):
    x = -44 + i * 8
    for s in (-1, 1):
        y = s * (Wd / 2 - 1.2)
        caixa("pilar_alma", (x, y, H / 2), (0.15, 0.9, H), FERRO)
        caixa("pilar_aba1", (x - 0.35, y, H / 2), (0.08, 0.9, H), FERRO)
        caixa("pilar_aba2", (x + 0.35, y, H / 2), (0.08, 0.9, H), FERRO)
for s in (-1, 1):
    caixa("trilho_ponte", (0, s * (Wd / 2 - 1.2), 14.5), (L, 0.8, 1.2), FERRO)
# telhado em serra com buracos (luz entrando)
for i in range(15):
    x = -42 + i * 6
    if i in (4, 9, 11):
        continue                      # buracos no telhado
    caixa("telhado", (x, 0, H + 1.4), (6.2, Wd, 0.15), TELHA, (0, math.radians(-25), 0))
    caixa("treliça", (x, 0, H - 0.2), (0.25, Wd, 0.3), FERRO)
# ponte rolante amarela com gancho
gx = -6
caixa("ponte_viga1", (gx, 0, 15.6), (1.2, Wd - 2, 1.6), AMARELO)
caixa("ponte_viga2", (gx + 2.2, 0, 15.6), (1.2, Wd - 2, 1.6), AMARELO)
caixa("carro", (gx + 1.1, 4, 16.8), (3.6, 3.0, 1.4), AMARELO)
for k in range(2):
    cil("cabo", (gx + 0.6 + k, 4, 11.5), 0.04, 9, FERRO)
caixa("moitao", (gx + 1.1, 4, 7.0), (1.2, 0.8, 1.4), AMARELO)
bpy.ops.mesh.primitive_torus_add(location=(gx + 1.1, 4, 5.8), major_radius=0.45, minor_radius=0.12, rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(FERRO)
# alto-forno no fundo, brilhando
cil("forno", (34, -5, 9), 5.5, 18, FERRO)
cil("forno_topo", (34, -5, 19.5), 3.5, 3, FERRO)
for k in range(6):
    a = k * math.pi / 3
    caixa("fenda", (34 + 5.55 * math.cos(a), -5 + 5.55 * math.sin(a), 3.0), (0.3, 1.2, 1.8), BRASA, (0, 0, a))
caixa("bica", (27, -5, 1.6), (4, 1.0, 0.5), BRASA, (0, math.radians(-8), 0))
caixa("poca_ferro", (23.5, -5, 0.05), (4, 3, 0.08), BRASA)
cil("chamine", (40, 10, 18), 1.4, 36, FERRO)
for k in range(4):
    cil("tubo", (0, Wd / 2 - 3 - k * 0.9, 9 + k * 0.6), 0.35, L, FERRO, (0, math.pi / 2, 0), 16)
# esteira inclinada
caixa("esteira", (10, 8, 5), (26, 1.8, 0.4), FERRO, (0, math.radians(-14), 0))
for k in range(6):
    caixa("pe", (0 + k * 4, 8, 1.5 + k), (0.3, 1.6, 3 + k * 2), FERRO)
# pilhas de sucata e bobinas
for k in range(7):
    cil("bobina", (-20 + random.uniform(-6, 6), -9 + random.uniform(-3, 3), 0.8), 0.9, 1.4, FERRO, (math.pi / 2, 0, random.uniform(0, 3)))
for k in range(5):
    caixa("chapa", (-32 + k * 1.1, 10, 0.2 + k * 0.12), (3, 2, 0.1), FERRO, (0, 0, random.uniform(-0.3, 0.3)))
# plataforma de entrega (onde o drone vai pousar a carga)
caixa("plataforma", (5, -11, 6), (4, 4, 0.2), AMARELO)
for (dx, dy) in ((-1.8, -1.8), (1.8, -1.8), (-1.8, 1.8), (1.8, 1.8)):
    caixa("perna", (5 + dx, -11 + dy, 3), (0.15, 0.15, 6), FERRO)
LUZ_PLAT = mat("led", (0.1, 0.4, 0.1), 0.5, 0, (0.2, 1.0, 0.35), 25)
caixa("marca", (5, -11, 6.12), (2.4, 2.4, 0.02), LUZ_PLAT)
caixa("marca_furo", (5, -11, 6.13), (2.0, 2.0, 0.02), AMARELO)

# atmosfera com poeira (só dentro do galpão)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, H / 2))
vol = bpy.context.object
vol.scale = (L, Wd, H)
mv = bpy.data.materials.new("poeira")
mv.use_nodes = True
nt = mv.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
vs = nt.nodes.new("ShaderNodeVolumeScatter")
vs.inputs["Density"].default_value = 0.02
vs.inputs["Anisotropy"].default_value = 0.6
nt.links.new(vs.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
vol.data.materials.append(mv)

# luzes
bpy.ops.object.light_add(type="SUN", rotation=(math.radians(35), math.radians(-20), math.radians(30)))
sol = bpy.context.object
sol.data.energy = 8.0
sol.data.color = (1.0, 0.88, 0.7)
sol.data.angle = math.radians(1.0)
for (p, e, c) in (((26, -5, 3), 9000, (1, 0.35, 0.05)), ((22, -5, 1), 4000, (1, 0.4, 0.08)), ((5, -11, 7.5), 300, (0.3, 1, 0.4))):
    bpy.ops.object.light_add(type="POINT", location=p)
    l = bpy.context.object
    l.data.energy = e
    l.data.color = c
    l.data.shadow_soft_size = 1.5
mundo = bpy.data.worlds.new("ceu")
cena.world = mundo
mundo.use_nodes = True
mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.42, 0.55, 1)
mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

# câmera na altura de um drone, olhando o galpão até o alto-forno
bpy.ops.object.camera_add(location=(-38, 6, 4.2))
cam = bpy.context.object
alvo = Vector((30, -4, 6.5))
cam.rotation_euler = (alvo - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.rotation_euler.y += math.radians(-4)   # leve inclinação, como drone fazendo curva
cam.data.lens = 24
cena.camera = cam

cena.render.engine = "CYCLES"
cena.cycles.device = "CPU"
cena.cycles.samples = AMOSTRAS
cena.cycles.use_denoising = True
cena.cycles.volume_step_rate = 4.0
cena.cycles.max_bounces = 4
cena.render.resolution_x = LARG
cena.render.resolution_y = int(LARG * 9 / 16)
cena.view_settings.view_transform = "AgX"
cena.view_settings.look = "AgX - Medium High Contrast"
cena.render.filepath = SAIDA
bpy.ops.render.render(write_still=True)
print("ok", SAIDA)
