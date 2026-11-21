"""Árvore feita no Blender com dados de vento no estilo dos jogos AAA (tipo Pivot Painter).

Uso:  python3 gerar_arvore.py SAIDA
Gera: SAIDA/ArvoreBlender.fbx, SAIDA/folhas_arvore.png

Cada vértice leva:
  UV0  textura (casca ou cacho de folhas)
  UV1  (x, y) do PIVÔ do galho de 1º nível a que ele pertence (m, espaço da árvore)
  UV2  (z do pivô, nível) — nível 0 = tronco, 1 = galho, 2 = raminho/folha
  cor  R = flexibilidade (0 no pivô do galho, 1 na ponta mais longe), G = fase do galho (0..1),
       B = 1 nas folhas, A = fase da folha (0..1)
No Unreal o material usa isso para: o tronco dobrar pela altura, cada galho GIRAR em volta do pivô dele
(com ritmo próprio, levando raminhos e folhas juntos) e as folhas tremerem.
Materiais: CASCA (tronco/galhos) e FOLHAS_ARVORE (cartões com recorte)."""
import math
import os
import random
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw, ImageFilter

SAIDA = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].endswith(".py") else "/tmp/vitrine"
os.makedirs(SAIDA, exist_ok=True)
rnd = random.Random(2026)


# ----------------------------------------------------------------------------- textura do cacho de folhas
def textura_folhas(caminho):
    N = 1024
    img = Image.new("RGBA", (N, N), (60, 80, 30, 0))
    d = ImageDraw.Draw(img)
    # raminho no meio
    d.line([(N * 0.5, N * 0.98), (N * 0.52, N * 0.55), (N * 0.47, N * 0.12)], fill=(72, 55, 35, 255), width=10)
    folhas = []
    for i in range(16):
        t = 0.12 + i * 0.052
        lado = -1 if i % 2 else 1
        cx = N * (0.5 + lado * (0.10 + 0.09 * math.sin(i)))
        cy = N * (1.0 - t)
        ang = math.radians(90 - lado * (35 + 15 * math.sin(i * 1.7)))
        folhas.append((cx, cy, ang, rnd.uniform(0.85, 1.15)))
    folhas.append((N * 0.47, N * 0.08, math.radians(95), 1.1))
    for (cx, cy, ang, esc) in folhas:
        L, W = 150 * esc, 58 * esc
        pts = []
        for k in range(40):
            u = k / 39.0
            w = W * math.sin(math.pi * u) ** 0.9 * (1.0 - 0.25 * u)
            pts.append((u * L, w))
        pts += [(u * L, -w) for (u, w) in [(p[0] / L, p[1]) for p in pts[::-1]]]
        ca, sa = math.cos(ang), math.sin(ang)
        poly = [(cx + x * ca - y * sa, cy - (x * sa + y * ca)) for (x, y) in pts]
        g = rnd.randint(95, 140)
        cor = (int(g * 0.45), g, int(g * 0.28), 255)
        d.polygon(poly, fill=cor)
        # nervura
        d.line([(cx, cy), (cx + L * 0.95 * ca, cy - L * 0.95 * sa)], fill=(int(g * 0.6), int(g * 1.15), int(g * 0.4), 255), width=3)
    # leve variação de luz/cor dentro da folha
    arr = np.array(img).astype(np.float32)
    ruido = np.random.RandomState(4).rand(N, N) * 0.18 + 0.91
    arr[..., :3] *= ruido[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.SMOOTH)
    img.save(caminho)


# ----------------------------------------------------------------------------- malha
bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
uv0 = bm.loops.layers.uv.new("UVMap")
uv1 = bm.loops.layers.uv.new("Pivo")
uv2 = bm.loops.layers.uv.new("PivoZ")
corl = bm.loops.layers.float_color.new("Col")


def marcar(faces, pivo, nivel, fase_galho, flex_de, folha=0.0, fase_folha=0.0):
    """grava os dados do vento nos cantos das faces. flex_de(v) -> 0..1."""
    for f in faces:
        for lp in f.loops:
            lp[uv1].uv = (pivo.x, pivo.y)
            lp[uv2].uv = (pivo.z, float(nivel))
            lp[corl] = (flex_de(lp.vert.co), fase_galho, folha, fase_folha)


def tubo(pontos, raios, lados=8, v_por_m=0.9):
    """tubo com UV (casca) seguindo a lista de pontos; devolve as faces."""
    faces = []
    aneis = []
    v_acum = 0.0
    for i, (p, r) in enumerate(zip(pontos, raios)):
        if i < len(pontos) - 1:
            t = (pontos[i + 1] - p).normalized()
        else:
            t = (p - pontos[i - 1]).normalized()
        a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        n1 = t.cross(a).normalized()
        n2 = t.cross(n1).normalized()
        anel = []
        for k in range(lados + 1):
            ang = 2 * math.pi * k / lados
            anel.append(bm.verts.new(p + (n1 * math.cos(ang) + n2 * math.sin(ang)) * r))
        if i > 0:
            v_acum += (p - pontos[i - 1]).length * v_por_m
        aneis.append((anel, v_acum))
    for i in range(len(aneis) - 1):
        (A, va), (B, vb) = aneis[i], aneis[i + 1]
        for k in range(lados):
            f = bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
            f.material_index = 0
            for lp, (u, v) in zip(f.loops, ((k / lados, va), ((k + 1) / lados, va), ((k + 1) / lados, vb), (k / lados, vb))):
                lp[uv0].uv = (u * 2.0, v)
            faces.append(f)
    return faces


def curva(base, direcao, comp, n, curvatura, gravidade):
    pts = [base.copy()]
    d = direcao.normalized()
    passo = comp / n
    for i in range(n):
        d = (d + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 0.6))) * curvatura
             - Vector((0, 0, gravidade * (i / n)))).normalized()
        pts.append(pts[-1] + d * passo)
    return pts


def cartao_folhas(centro, normal_dir, tam, girar):
    """cartão em X (dois planos cruzados) com o cacho de folhas."""
    faces = []
    up = normal_dir.normalized()
    a = Vector((0, 0, 1)) if abs(up.z) < 0.9 else Vector((1, 0, 0))
    lado = up.cross(a).normalized()
    R = Matrix.Rotation(girar, 3, up)
    lado = R @ lado
    for k in range(2):
        l2 = (Matrix.Rotation(math.pi / 2 * k, 3, up) @ lado)
        p0 = centro - l2 * tam * 0.5
        p1 = centro + l2 * tam * 0.5
        p2 = p1 + up * tam
        p3 = p0 + up * tam
        vs = [bm.verts.new(p) for p in (p0, p1, p2, p3)]
        f = bm.faces.new(vs)
        f.material_index = 1
        for lp, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uv0].uv = uv
        faces.append(f)
    return faces


ALTURA = 8.5
# tronco (levemente torto) e raízes aparentes
pts_tronco = curva(Vector((0, 0, -0.3)), Vector((0.05, 0.02, 1)), ALTURA * 0.62, 10, 0.08, 0.0)
raios_tronco = [0.34 * (1 - 0.55 * i / 10) for i in range(11)]
raios_tronco[0] = 0.45
f = tubo(pts_tronco, raios_tronco, lados=12)
marcar(f, Vector((0, 0, 0)), 0, 0.0, lambda v: 0.0)

n_galhos = 9
for g in range(n_galhos):
    t = 0.38 + 0.6 * g / (n_galhos - 1)
    i = int(t * 10)
    base = pts_tronco[min(i, 10)]
    ang = g * 2.39996 + rnd.uniform(-0.3, 0.3)
    sobe = rnd.uniform(0.35, 0.9) + 0.5 * t
    direcao = Vector((math.cos(ang), math.sin(ang), sobe))
    comp = rnd.uniform(2.4, 3.6) * (1.15 - 0.45 * t)
    pts = curva(base, direcao, comp, 6, 0.15, 0.25)
    r0 = raios_tronco[min(i, 10)] * 0.55
    raios = [r0 * (1 - 0.8 * k / 6) for k in range(7)]
    pivo = base.copy()
    fase = rnd.random()
    alcance = comp * 1.45                     # até a ponta dos raminhos/folhas

    def flex(v, pivo=pivo, alcance=alcance):
        return min(1.0, (v - pivo).length / alcance)

    marcar(tubo(pts, raios, lados=7), pivo, 1, fase, flex)
    # raminhos e cachos de folhas ao longo do galho
    for k in range(2, 7):
        b2 = pts[k]
        for j in range(2):
            a2 = ang + rnd.uniform(-1.4, 1.4)
            d2 = Vector((math.cos(a2), math.sin(a2), rnd.uniform(0.2, 0.9)))
            c2 = rnd.uniform(0.6, 1.1)
            p2 = curva(b2, d2, c2, 3, 0.25, 0.2)
            rr = raios[k] * 0.45
            marcar(tubo(p2, [rr, rr * 0.7, rr * 0.45, rr * 0.2], lados=5), pivo, 2, fase, flex)
            for q in (1, 2, 3):
                ff = cartao_folhas(p2[q], (p2[q] - p2[q - 1]) + Vector((0, 0, 0.35)), rnd.uniform(0.75, 1.05), rnd.uniform(0, 6.28))
                marcar(ff, pivo, 2, fase, flex, folha=1.0, fase_folha=rnd.random())
    # cacho na ponta
    ff = cartao_folhas(pts[-1], pts[-1] - pts[-2], 1.1, rnd.uniform(0, 6.28))
    marcar(ff, pivo, 2, fase, flex, folha=1.0, fase_folha=rnd.random())

# copa de cima (topo do tronco)
topo = pts_tronco[-1]
for k in range(10):
    a = k * 0.63
    c = topo + Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, rnd.uniform(-0.2, 0.6)))
    ff = cartao_folhas(c, Vector((math.cos(a), math.sin(a), 1.4)), 1.1, rnd.uniform(0, 6.28))
    marcar(ff, topo, 2, rnd.random(), lambda v, topo=topo: min(1.0, (v - topo).length / 2.0), folha=1.0, fase_folha=rnd.random())

bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f.material_index == 0])
me = bpy.data.meshes.new("ArvoreBlender")
bm.to_mesh(me)
bm.free()
for nome in ("CASCA", "FOLHAS_ARVORE"):
    me.materials.append(bpy.data.materials.new(nome))
ob = bpy.data.objects.new("ArvoreBlender", me)
bpy.context.scene.collection.objects.link(ob)
print("árvore:", len(me.vertices), "vértices,", len(me.polygons), "faces")

textura_folhas(os.path.join(SAIDA, "folhas_arvore.png"))
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
caminho = os.path.join(SAIDA, "ArvoreBlender.fbx")
bpy.ops.export_scene.fbx(filepath=caminho, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
                         axis_forward="-Y", axis_up="Z", mesh_smooth_type="FACE", colors_type="LINEAR",
                         add_leaf_bones=False, bake_anim=False)
print("->", caminho)
