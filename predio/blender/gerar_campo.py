"""Mapa 1 — CAMPO BAIANO no Unreal (porta do mapa do voo do E88 feito na Godot).

Gera, no Blender (sem interface), os FBX e o layout_campo.json que o
unreal/construir_campo.py monta no editor:

  Terreno.fbx      relevo de ~4,6 km (grade mais fina no centro), cores de vértice:
                   R = estrada de terra, G = beira do açude, B = terra batida (base/galpão)
  Agua.fbx         espelho d'água do açude
  Base.fbx         base de pouso (9 m x 0,5) com o H pintado
  Galpao.fbx       galpão de fazenda (paredes, pilares, telhado de duas águas, oitões)
  Biruta.fbx       mastro, base e o cone de pano
  Cercas.fbx       mourões e três fios (pasto, beira da estrada, curral)
  Postes.fbx       rede elétrica ao longo da estrada (postes, cruzetas, isoladores, fios com barriga)
  Aro.fbx          aro do circuito (furo no eixo X, raio 2,2 m) — colocado várias vezes no Unreal
  Haste.fbx        haste de 1 m (esticada no Unreal até o chão embaixo de cada aro)
  Marcador.fbx     caixinha em x=20, y=5 (diz ao Unreal como os eixos entraram)

O layout (mesmo desenho da Godot: estrada, açude, galpão, árvores de destaque,
eucaliptal, jacarandás, pedras) usa coordenadas do Blender: x = x da Godot,
y = -z da Godot, z = altura.

Uso:  python3 gerar_campo.py SAIDA   (precisa do módulo bpy)
"""
import json
import math
import os
import random
import sys

import bpy  # noqa: E402  (o bpy precisa vir antes do bmesh)
import bmesh
import numpy as np

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/campo"
os.makedirs(SAIDA, exist_ok=True)
rng = random.Random(2026)

# ----------------------------------------------------------------------------- desenho da Godot (x, z)
ESTRADA = [(120, 90), (66, 22), (49, -40), (46, -130), (58, -260), (86, -480), (132, -900), (200, -1500), (260, -2300)]
ACUDE_C = (-6.0, -122.0)
ACUDE_R = (34.0, 19.0)
GALPAO_C = (-47.0, -60.0)
GALPAO_GIRO = 12.0
# construções novas da fazenda (x, z da Godot): onde ficam e o raio do terreno aplainado
CASA_C = (-34.0, 26.0)
CAIXA_C = (28.0, 18.0)
CATAVENTO_C = (-75.0, -8.0)
SILOS_C = [(-28.0, -76.0), (-22.5, -81.5)]
CARRETA_C = (-62.0, -36.0)
PIER_C = (30.0, -118.0)
ROCA = (70.0, -150.0, 125.0, -72.0)     # milharal: x0, z0, x1, z1 (Godot)
ZONAS_PLANAS = [(CASA_C, 10.0, 19.0), (CAIXA_C, 4.0, 9.0), (CATAVENTO_C, 3.5, 8.0), ((-25.0, -79.0), 8.0, 14.0),
                (CARRETA_C, 4.0, 8.0)]
ESCALA_BASE = 0.5


# ----------------------------------------------------------------------------- ruído (gradiente 2D, fractal)
class Ruido:
    def __init__(self, semente, oitavas):
        r = np.random.RandomState(semente)
        self.perm = np.concatenate([r.permutation(256)] * 2)
        ang = r.rand(256) * 2 * np.pi
        self.gx, self.gy = np.cos(ang), np.sin(ang)
        self.oitavas = oitavas

    def _base(self, x, y):
        xi = np.floor(x).astype(np.int64)
        yi = np.floor(y).astype(np.int64)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        p = self.perm

        def g(ix, iy, dx, dy):
            h = p[p[ix] + iy] & 255
            return self.gx[h] * dx + self.gy[h] * dy

        n00 = g(xi, yi, xf, yf)
        n10 = g(xi + 1, yi, xf - 1, yf)
        n01 = g(xi, yi + 1, xf, yf - 1)
        n11 = g(xi + 1, yi + 1, xf - 1, yf - 1)
        a = n00 + u * (n10 - n00)
        b = n01 + u * (n11 - n01)
        return (a + v * (b - a)) * 1.41

    def __call__(self, x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        tot, amp, f, norma = 0.0, 1.0, 1.0, 0.0
        for _ in range(self.oitavas):
            tot = tot + self._base(x * f, y * f) * amp
            norma += amp
            amp *= 0.5
            f *= 2.0
        return tot / norma


ruido_a, ruido_b, ruido_c = Ruido(11, 4), Ruido(23, 3), Ruido(37, 2)


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def altura_bruta(x, z):
    d = np.hypot(x, z)
    h = ruido_a(x * 0.0035, z * 0.0035) * 7.0
    h = h + ruido_b(x * 0.018, z * 0.018) * 1.1
    h = h + ruido_c(x * 0.09, z * 0.09) * 0.12
    morro = ruido_b(x * 0.0011 + 40.0, z * 0.0011) * 0.5 + 0.5
    return h + smoothstep(320.0, 1700.0, d) * (40.0 + morro * 150.0)


ALT_CENTRO = float(altura_bruta(np.array(0.0), np.array(0.0)))
ALT_GALPAO = float(altura_bruta(np.array(GALPAO_C[0]), np.array(GALPAO_C[1])))
NIVEL_AGUA = float(altura_bruta(np.array(ACUDE_C[0]), np.array(ACUDE_C[1]))) - 0.6


def dist_estrada(x, z):
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    melhor = np.full(np.broadcast(x, z).shape, 1e9)
    for (ax, az), (bx, bz) in zip(ESTRADA[:-1], ESTRADA[1:]):
        abx, abz = bx - ax, bz - az
        t = np.clip(((x - ax) * abx + (z - az) * abz) / (abx * abx + abz * abz), 0.0, 1.0)
        melhor = np.minimum(melhor, np.hypot(x - (ax + abx * t), z - (az + abz * t)))
    return melhor


def acude_e(x, z):
    return ((x - ACUDE_C[0]) / ACUDE_R[0]) ** 2 + ((z - ACUDE_C[1]) / ACUDE_R[1]) ** 2


def altura(x, z):
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    h = altura_bruta(x, z)
    d = np.hypot(x, z)
    h = ALT_CENTRO + (h - ALT_CENTRO) * smoothstep(14.0, 45.0, d)
    dg = np.hypot(x - GALPAO_C[0], z - GALPAO_C[1])
    h = np.where(dg < 24.0, ALT_GALPAO + (h - ALT_GALPAO) * smoothstep(11.0, 24.0, dg), h)
    for (cx, cz), r0, r1 in ZONAS_PLANAS:
        ref = float(altura_bruta(np.array(cx), np.array(cz)))
        dz = np.hypot(x - cx, z - cz)
        h = np.where(dz < r1, ref + (h - ref) * smoothstep(r0, r1, dz), h)
    h = h - 0.14 * (1.0 - smoothstep(2.5, 4.5, dist_estrada(x, z)))
    h = h - 2.6 * (1.0 - smoothstep(0.55, 1.35, acude_e(x, z)))
    return h


def alt1(x, z):
    return float(altura(np.array(x), np.array(z)))


def mascara(x, z):
    r = 1.0 - smoothstep(2.4, 4.3, dist_estrada(x, z))
    g = 1.0 - smoothstep(1.0, 1.55, acude_e(x, z))
    b = 1.0 - smoothstep(4.7, 6.6, np.hypot(x, z))
    b = np.maximum(b, 1.0 - smoothstep(9.0, 15.0, np.hypot(x - GALPAO_C[0], z - GALPAO_C[1])))
    for (cx, cz), r0, r1 in ZONAS_PLANAS:
        b = np.maximum(b, (1.0 - smoothstep(r0 * 0.6, r0 * 1.1, np.hypot(x - cx, z - cz))) * 0.85)
    # milharal: terra arada (canal B mais fraco, a grama some embaixo do milho)
    dentro = (x > ROCA[0] - 1) & (x < ROCA[2] + 1) & (z > ROCA[1] - 1) & (z < ROCA[3] + 1)
    b = np.where(dentro, np.maximum(b, 0.7), b)
    return r, g, b


def B(x, z, h):
    """Godot (x, z) + altura -> Blender."""
    return (float(x), float(-z), float(h))


# ----------------------------------------------------------------------------- utilidades do Blender
bpy.ops.wm.read_factory_settings(use_empty=True)
MATS = {}


def mat(nome):
    if nome not in MATS:
        MATS[nome] = bpy.data.materials.new(nome)
    return MATS[nome]


def novo_obj(nome, bm, materiais):
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    for m in materiais:
        me.materials.append(mat(m))
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def uv_caixa(bm, escala=1.0):
    """UV por projeção de caixa (1 UV = 1 m / escala), boa para texturas que repetem."""
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            co = lp.vert.co
            if ax == 0:
                lp[uv].uv = (co.y / escala, co.z / escala)
            elif ax == 1:
                lp[uv].uv = (co.x / escala, co.z / escala)
            else:
                lp[uv].uv = (co.x / escala, co.y / escala)


def caixa(bm, centro, tam, giro_z=0.0, giro_x=0.0, mi=0, giro_y=0.0):
    """caixa (tam em m) no bmesh, girada (graus) em X, Y e depois Z, em volta do centro."""
    from mathutils import Matrix, Vector
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res["verts"]
    M = (Matrix.Translation(Vector(centro)) @ Matrix.Rotation(math.radians(giro_z), 4, "Z")
         @ Matrix.Rotation(math.radians(giro_y), 4, "Y") @ Matrix.Rotation(math.radians(giro_x), 4, "X")
         @ Matrix.Diagonal(Vector((tam[0], tam[1], tam[2], 1.0))))
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def cilindro(bm, base, r1, r2, alt, lados=12, mi=0, eixo=None, tampas=True):
    """cilindro de base (x, y, z) subindo alt (ou ao longo de 'eixo', vetor unitário)."""
    from mathutils import Matrix, Vector
    res = bmesh.ops.create_cone(bm, cap_ends=tampas, cap_tris=False, segments=lados, radius1=r2, radius2=r1, depth=alt)
    vs = res["verts"]
    if eixo is None:
        M = Matrix.Translation(Vector(base) + Vector((0, 0, alt / 2)))
    else:
        e = Vector(eixo).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(e).to_matrix().to_4x4()
        M = Matrix.Translation(Vector(base) + e * (alt / 2)) @ rot
    bmesh.ops.transform(bm, matrix=M, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mi
    return vs


def segmento(bm, p1, p2, esp, mi=0, lados=4):
    from mathutils import Vector
    a, b = Vector(p1), Vector(p2)
    d = b - a
    if d.length < 1e-4:
        return
    cilindro(bm, tuple(a), esp, esp, d.length, lados=lados, mi=mi, eixo=tuple(d.normalized()), tampas=False)


LAYOUT = {
    "nome": "campo_baiano",
    "nivel_agua": NIVEL_AGUA,
    "altura_centro": ALT_CENTRO,
    "estrada": [B(x, z, alt1(x, z)) for x, z in ESTRADA],
    "acude": {"x": ACUDE_C[0], "y": -ACUDE_C[1], "rx": ACUDE_R[0], "ry": ACUDE_R[1]},
    "galpao": {"x": GALPAO_C[0], "y": -GALPAO_C[1], "raio": 14.0},
    "aros": [],
    "plantas": [],
}


# ----------------------------------------------------------------------------- terreno
def terreno():
    n, A, Bc = 760, 180.0, 2120.0
    t = np.linspace(-1.0, 1.0, n + 1)
    co = np.sign(t) * (A * np.abs(t) + Bc * np.abs(t) ** 4)
    X, Z = np.meshgrid(co, co)          # Godot x, z
    H = altura(X, Z)
    perto = (np.abs(X) < 700) & (np.abs(Z) < 1700)
    r, g, b = mascara(X, Z)
    r, g, b = np.where(perto, r, 0), np.where(perto, g, 0), np.where(perto, b, 0)
    nv = (n + 1) * (n + 1)
    verts = np.stack([X.ravel(), -Z.ravel(), H.ravel()], axis=1).astype(np.float32)
    idx = np.arange(nv).reshape(n + 1, n + 1)
    a = idx[:-1, :-1].ravel()
    bb = idx[:-1, 1:].ravel()
    d = idx[1:, :-1].ravel()
    e = idx[1:, 1:].ravel()
    # z da Godot = -y do Blender: a ordem (a, d, e, b) deixa a face virada para cima
    quads = np.stack([a, d, e, bb], axis=1)
    me = bpy.data.meshes.new("Terreno")
    me.vertices.add(nv)
    me.vertices.foreach_set("co", verts.ravel())
    nq = quads.shape[0]
    me.loops.add(nq * 4)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(nq)
    me.polygons.foreach_set("loop_start", (np.arange(nq) * 4).astype(np.int32))
    me.polygons.foreach_set("loop_total", np.full(nq, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    # confere a orientação: a normal do primeiro quadrado tem que apontar para cima
    if me.polygons[nq // 2].normal.z < 0:
        me.flip_normals()
    ca = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
    cores = np.stack([r.ravel(), g.ravel(), b.ravel(), np.ones(nv)], axis=1).astype(np.float32)
    ca.data.foreach_set("color", cores.ravel())
    me.materials.append(mat("TERRENO"))
    me.polygons.foreach_set("use_smooth", np.ones(nq, dtype=bool))
    ob = bpy.data.objects.new("Terreno", me)
    bpy.context.scene.collection.objects.link(ob)
    print("terreno:", nv, "vértices; centro", ALT_CENTRO, "água", NIVEL_AGUA)
    return ob


def agua():
    bm = bmesh.new()
    res = bmesh.ops.create_circle(bm, cap_ends=True, segments=72, radius=1.0)
    from mathutils import Matrix, Vector
    bmesh.ops.transform(bm, verts=res["verts"], matrix=Matrix.Translation(Vector(B(ACUDE_C[0], ACUDE_C[1], NIVEL_AGUA)))
                        @ Matrix.Diagonal(Vector((ACUDE_R[0] * 1.12, ACUDE_R[1] * 1.12, 1.0, 1.0))))
    uv_caixa(bm, 4.0)
    novo_obj("Agua", bm, ["AGUA"])


def base_pouso():
    bm = bmesh.new()
    r = 9.0 * ESCALA_BASE
    cilindro(bm, (0, 0, ALT_CENTRO - 0.28), r, r * 1.016, 0.4, lados=72, mi=0)
    uv_caixa(bm, 2.0)
    topo = ALT_CENTRO - 0.28 + 0.4 + 0.004
    # H branco (2 traços verticais + 1 horizontal), proporcional à base
    s = ESCALA_BASE
    for (cx, cy, w, h) in ((-2.2 * s, 0, 0.9 * s, 6.0 * s), (2.2 * s, 0, 0.9 * s, 6.0 * s), (0, 0, 3.5 * s, 0.9 * s)):
        caixa(bm, (cx, cy, topo), (w, h, 0.01), mi=1)
    # círculo pintado em volta
    for i in range(60):
        a0, a1 = 2 * math.pi * i / 60, 2 * math.pi * (i + 1) / 60
        rm = 7.6 * s
        segmento(bm, (rm * math.cos(a0), rm * math.sin(a0), topo), (rm * math.cos(a1), rm * math.sin(a1), topo), 0.18 * s, mi=1, lados=4)
    novo_obj("Base", bm, ["BASE", "PINTURA"])


def galpao():
    from mathutils import Matrix, Vector
    bm = bmesh.new()
    L, P, H = 17.0, 7.5, 3.0
    # tudo montado em volta da origem e depois girado/levado para o lugar
    caixa(bm, (0, 0, 0.05), (L + 0.6, P + 0.6, 0.3), mi=3)
    caixa(bm, (0, P / 2, H / 2), (L, 0.22, H), mi=0)          # fundo (z da Godot = -P/2 -> y = +P/2)
    caixa(bm, (-L / 2, 0, H / 2), (0.22, P, H), mi=0)
    caixa(bm, (L / 2, 0, H / 2), (0.22, P, H), mi=0)
    caixa(bm, (-L / 2 + 2.9, -P / 2, 0.55), (5.5, 0.2, 1.1), mi=0)
    for i in range(6):
        x = -L / 2 + 0.2 + i * (L - 0.4) / 5.0
        cilindro(bm, (x, -P / 2, 0), 0.1, 0.11, H, lados=10, mi=2)
    caixa(bm, (0, -P / 2, H), (L + 0.4, 0.2, 0.22), mi=2)
    caixa(bm, (0, P / 2, H), (L + 0.4, 0.2, 0.22), mi=2)
    beiral, subida = 0.9, 1.8
    meia = P / 2 + beiral
    comp = math.hypot(meia, subida)
    ang = math.degrees(math.atan2(subida, meia))
    for s in (-1.0, 1.0):
        caixa(bm, (0, s * meia / 2, H + subida / 2 - 0.15), (L + 1.6, comp, 0.14), giro_x=-s * ang, mi=1)
    caixa(bm, (0, 0, H + subida - 0.1), (L + 1.7, 0.3, 0.2), mi=1)
    for s in (-1.0, 1.0):                                       # oitões
        vs = [bm.verts.new((s * L / 2 + dx, y, H + zz)) for dx in (0.11, -0.11)
              for (y, zz) in ((-P / 2, 0.0), (P / 2, 0.0), (0.0, subida))]
        f1 = bm.faces.new(vs[0:3])
        f2 = bm.faces.new(vs[3:6][::-1])
        f1.material_index = f2.material_index = 0
    for i in range(4):
        x = rng.uniform(-L / 2 + 1, L / 2 - 1)
        cilindro(bm, (x, -rng.uniform(-2.5, 1.5), 0.2), 0.3, 0.3, 0.85, lados=14, mi=2)
    for i in range(3):
        caixa(bm, (L / 2 - 1.5 - i * 1.3, 2.6, 0.45), (1.1, 0.8, 0.5), mi=2)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    M = Matrix.Translation(Vector(B(GALPAO_C[0], GALPAO_C[1], ALT_GALPAO))) @ Matrix.Rotation(math.radians(GALPAO_GIRO), 4, "Z")
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    uv_caixa(bm, 2.5)
    novo_obj("Galpao", bm, ["PAREDE", "TELHA", "MADEIRA", "PISO"])


def biruta():
    bm = bmesh.new()
    x, z = -15.0, 3.0
    y = alt1(x, z)
    bx, by, _ = B(x, z, y)
    cilindro(bm, (bx, by, y - 0.2), 0.045, 0.06, 6.4, lados=12, mi=0)
    cilindro(bm, (bx, by, y - 0.05), 0.35, 0.35, 0.3, lados=24, mi=2)
    # cone de pano apontando para onde o vento vai (giro de -25° da Godot)
    giro = math.radians(-25.0)
    dx, dy = math.cos(giro), math.sin(giro)
    topo = (bx, by, y + 5.9)
    cilindro(bm, (topo[0] + dx * 0.05, topo[1] + dy * 0.05, topo[2] - 0.12), 0.16, 0.35, 2.4, lados=24, mi=1,
             eixo=(dx, dy, -0.12), tampas=False)
    uv_caixa(bm, 1.0)
    novo_obj("Biruta", bm, ["METAL", "PANO", "PISO"])


def linhas_cerca():
    linhas = [[(-110, -34), (-20, -31), (42, -33)]]
    for lado in (-1.0, 1.0):
        pts = []
        for i in range(1, len(ESTRADA) - 3):
            ax, az = ESTRADA[i]
            bx, bz = ESTRADA[i + 1]
            dl = math.hypot(bx - ax, bz - az)
            dx, dz = (bx - ax) / dl, (bz - az) / dl
            pts.append((ax - dz * lado * 7.5, az + dx * lado * 7.5))
        linhas.append(pts)
    gx, gz = GALPAO_C
    linhas.append([(gx + 9, gz + 6), (gx + 24, gz + 8), (gx + 26, gz - 6), (gx + 10, gz - 9)])
    return linhas


def cercas():
    bm = bmesh.new()
    n_m = 0
    for linha in linhas_cerca():
        ant = None
        for s in range(len(linha) - 1):
            ax, az = linha[s]
            bx, bz = linha[s + 1]
            passos = max(1, int(math.hypot(bx - ax, bz - az) / 3.2))
            extra = 1 if s == len(linha) - 2 else 0
            for k in range(passos + extra):
                t = k / passos
                px, pz = ax + (bx - ax) * t, az + (bz - az) * t
                if abs(px) > 470 or abs(pz) > 470:
                    ant = None
                    continue
                y = alt1(px, pz)
                topo = B(px, pz, y)
                cilindro(bm, (topo[0], topo[1], y - 0.1), 0.06, 0.075, 1.55, lados=7, mi=0)
                n_m += 1
                if ant is not None:
                    for alt in (0.45, 0.85, 1.2):
                        segmento(bm, (ant[0], ant[1], ant[2] + alt), (topo[0], topo[1], topo[2] + alt), 0.008, mi=1, lados=3)
                ant = topo
    uv_caixa(bm, 0.8)
    novo_obj("Cercas", bm, ["MADEIRA", "ARAME"])
    print("cercas:", n_m, "mourões")


def postes():
    bm = bmesh.new()
    ant = None
    acum, prox = 0.0, 0.0
    n = 0
    for i in range(len(ESTRADA) - 1):
        ax, az = ESTRADA[i]
        bx, bz = ESTRADA[i + 1]
        seg = math.hypot(bx - ax, bz - az)
        dx, dz = (bx - ax) / seg, (bz - az) / seg
        nx, nz = dz * 13.0, -dx * 13.0          # (-dir.y, dir.x) * -13 da Godot
        while prox <= acum + seg:
            px, pz = ax + dx * (prox - acum) + nx, az + dz * (prox - acum) + nz
            prox += 48.0
            if abs(px) > 520 or abs(pz) > 520:
                ant = None
                continue
            y = alt1(px, pz)
            b0 = B(px, pz, y)
            cilindro(bm, (b0[0], b0[1], y - 0.3), 0.11, 0.15, 9.8, lados=10, mi=0)
            # cruzeta perpendicular à estrada (no Blender a direção da estrada é (dx, -dz))
            ex, ey = dz, dx                       # perpendicular no plano do Blender
            caixa(bm, (b0[0], b0[1], y + 8.9), (2.4, 0.12, 0.12), giro_z=math.degrees(math.atan2(ey, ex)), mi=0)
            pts = []
            for off in (-1.0, 0.0, 1.0):
                p = (b0[0] + ex * off, b0[1] + ey * off, y + 8.96)
                cilindro(bm, p, 0.05, 0.07, 0.18, lados=8, mi=1)
                pts.append((p[0], p[1], p[2] + 0.18))
            if ant is not None:
                for k in range(3):
                    p1, p2 = ant[k], pts[k]
                    q_ant = p1
                    for s in range(1, 11):
                        t = s / 10
                        q = (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t,
                             p1[2] + (p2[2] - p1[2]) * t - 1.1 * 4.0 * t * (1 - t))
                        segmento(bm, q_ant, q, 0.012, mi=2, lados=4)
                        q_ant = q
            ant = pts
            n += 1
        acum += seg
    uv_caixa(bm, 1.0)
    novo_obj("Postes", bm, ["MADEIRA", "ISOLADOR", "FIO"])
    print("postes:", n)


def aro():
    """aro no eixo X (o furo aponta para +X), raio médio 2,2 m, tubo de 15 cm."""
    bm = bmesh.new()
    R, r, nu, nv = 2.2, 0.15, 64, 14
    vs = []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        lin = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            rr = R + r * math.cos(b)
            lin.append(bm.verts.new((r * math.sin(b), rr * math.cos(a), rr * math.sin(a))))
        vs.append(lin)
    for i in range(nu):
        for j in range(nv):
            f = bm.faces.new((vs[i][j], vs[(i + 1) % nu][j], vs[(i + 1) % nu][(j + 1) % nv], vs[i][(j + 1) % nv]))
            f.smooth = True
            # faixas pretas e laranjas alternadas (como portão de corrida FPV)
            f.material_index = 1 if (i // 4) % 4 == 0 else 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv_caixa(bm, 1.0)
    novo_obj("Aro", bm, ["ARO", "ARO_PRETO"])


def haste():
    bm = bmesh.new()
    cilindro(bm, (0, 0, 0), 0.06, 0.06, 1.0, lados=10, mi=0)
    uv_caixa(bm, 1.0)
    novo_obj("Haste", bm, ["METAL"])


def marcador():
    bm = bmesh.new()
    caixa(bm, (20.0, 5.0, 0.5), (1.0, 1.0, 1.0))
    novo_obj("Marcador", bm, ["METAL"])


# ----------------------------------------------------------------------------- circuito de aros
def circuito():
    # (x, z da Godot, altura do centro acima do chão/água) — usa os dois aros originais (-13,-52) e (24,-66)
    pts = [
        (0, -24, 3.0),       # 1  aquecimento, reto à frente da base
        (-13, -52, 2.35),    # 2  aro original da Godot
        (-38, -88, 4.0),     # 3  passando ao lado do galpão
        (-22, -124, 1.8),    # 4  rasante sobre o açude
        (24, -140, 4.0),     # 5  entre a árvore grande e a rede elétrica
        (47, -192, 3.2),     # 6  sobre a estrada de terra, por baixo dos fios
        (18, -238, 8.0),     # 7  subida
        (-62, -224, 6.0),    # 8  na frente do eucaliptal
        (-96, -152, 3.0),    # 9  descendo pelo pasto
        (24, -66, 2.35),     # 10 aro original da Godot
        (12, -14, 2.6),      # 11 chegada (de volta para a base, ao lado do aro 1)
    ]
    aros = []
    for i, (x, z, h) in enumerate(pts):
        chao = alt1(x, z)
        if acude_e(x, z) < 1.2:
            chao = max(chao, NIVEL_AGUA)
        px, pz = pts[i - 1][:2] if i > 0 else (0.0, 0.0)
        nx, nz = pts[i + 1][:2] if i + 1 < len(pts) else (0.0, 0.0)
        # normal do aro: direção de quem chega para quem vem depois (no plano do Blender: x, -z)
        dx, dy = nx - px, -(nz - pz)
        giro = math.degrees(math.atan2(dy, dx))
        aros.append({"n": i, "x": float(x), "y": float(-z), "z": float(chao + h), "chao": float(chao), "yaw": giro})
    LAYOUT["aros"] = aros
    LAYOUT["raio_aro"] = 2.05


# ----------------------------------------------------------------------------- vegetação e pedras (só posições)
PLANTAS_PERTO = []


def livre(x, z, folga):
    if math.hypot(x, z) < 18.0 + folga:
        return False
    if float(dist_estrada(np.array(x), np.array(z))) < 10.0 + folga:
        return False
    if float(acude_e(np.array(x), np.array(z))) < 1.4:
        return False
    if math.hypot(x - GALPAO_C[0], z - GALPAO_C[1]) < 14.0 + folga:
        return False
    for a in LAYOUT["aros"]:
        if math.hypot(x - a["x"], -z - a["y"]) < 9.0:
            return False
    for (cx, cz), r0, r1 in ZONAS_PLANAS:
        if math.hypot(x - cx, z - cz) < r1 + folga * 0.5:
            return False
    if ROCA[0] - 6 < x < ROCA[2] + 6 and ROCA[1] - 6 < z < ROCA[3] + 6:
        return False
    if math.hypot(x - PIER_C[0], z - PIER_C[1]) < 10:
        return False
    return True


def plantar(modelo, x, z, esc, giro=None, esc_v=None, afundar=0.05):
    y = alt1(x, z) - afundar
    bx, by, bz = B(x, z, y)
    sx = sy = sz = esc
    if esc_v:
        sx, sy, sz = esc_v[0], esc_v[2], esc_v[1]   # (x, altura, z) da Godot -> Blender (x, y, z)
    LAYOUT["plantas"].append({"modelo": modelo, "x": bx, "y": by, "z": bz,
                              "yaw": math.degrees(rng.random() * 2 * math.pi) if giro is None else giro,
                              "sx": sx, "sy": sy, "sz": sz})


def vegetacao():
    for (m, x, z, e) in (("island_tree_01", -33, -20, 2.9), ("island_tree_02", -72, -98, 2.7),
                         ("island_tree_03", 14, -158, 3.6), ("island_tree_01", 90, -58, 2.5),
                         ("island_tree_02", 142, -185, 2.9), ("tree_small_02", -20, -150, 2.3),
                         ("island_tree_03", 30, -105, 2.8)):
        plantar(m, x, z, e)
    x = -280.0
    while x < -30.0:                                  # eucaliptal (2 fileiras de árvores finas e altas)
        for fila in range(2):
            z = -238.0 - fila * 7.0 + rng.uniform(-2, 2)
            e = rng.uniform(2.4, 3.0)
            plantar("tree_small_02", x + rng.uniform(-1.5, 1.5) + fila * 3.0, z, e,
                    esc_v=(e * 0.75, e * rng.uniform(1.9, 2.3), e * 0.75))
        x += 6.5
    feitos = tent = 0
    while feitos < 90 and tent < 4000:                # árvores espalhadas até o horizonte
        tent += 1
        ang = rng.random() * 2 * math.pi
        r = rng.uniform(110.0, 1300.0)
        px, pz = math.cos(ang) * r, math.sin(ang) * r
        if pz > 60.0 and r < 600:
            continue
        if not livre(px, pz, 4.0):
            continue
        plantar(rng.choice(["island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02"]), px, pz, rng.uniform(2.2, 3.4))
        feitos += 1
    for p in ((-66, -38), (-24, -78), (32, -48), (-88, -132), (58, -112)):   # jacarandás floridos
        if livre(p[0], p[1], 2.0):
            plantar("jacaranda_tree", p[0], p[1], rng.uniform(0.95, 1.15))
    for i in range(110):                               # arbustos
        px, pz = rng.uniform(-130, 110), rng.uniform(-200, 15)
        if not livre(px, pz, -6.0):
            continue
        nome = "shrub_02" if rng.random() < 0.55 else "shrub_04"
        plantar(nome, px, pz, rng.uniform(0.9, 1.6) if nome == "shrub_02" else rng.uniform(1.5, 2.6))
    for i in range(26):
        plantar("shrub_02", rng.uniform(-110, 40), -33.0 + rng.uniform(-1.5, 1.5), rng.uniform(0.8, 1.3))
    for i in range(22):                                # pedras grandes
        ang = rng.random() * 2 * math.pi
        r = rng.uniform(11, 45)
        px, pz = math.cos(ang) * r, math.sin(ang) * r + 4.0
        if math.hypot(px, pz) < 7.0 or not livre(px, pz, -12.0):
            continue
        plantar("boulder_01", px, pz, rng.uniform(0.35, 0.9), afundar=0.2)
    for i in range(120):                               # pedrinhas
        px, pz = rng.uniform(-40, 40), rng.uniform(-40, 22)
        if math.hypot(px, pz) < 6.0:
            continue
        plantar("stone_01" if rng.random() < 0.5 else "rock_07", px, pz, rng.uniform(1.5, 4.0))
    # objetos da fazenda
    plantar("dead_tree_trunk_02", 16.0, -27.0, 1.0, giro=math.degrees(0.7), afundar=0.1)
    gx, gz = GALPAO_C
    for i in range(3):
        plantar("Barrel_01", gx + 9.6 + i * 0.75, gz + 6.5 + (i % 2) * 0.5, 1.0, afundar=0.0)
    for i in range(3):
        plantar("wooden_crate_01", gx + 9.5 + i * 0.95, gz - 6.0, 1.0, afundar=0.0)
    plantar("wooden_picnic_table", 9.0, 9.0, 1.0, giro=math.degrees(0.4), afundar=0.0)
    print("plantas/objetos:", len(LAYOUT["plantas"]))


# ----------------------------------------------------------------------------- fazenda nova (Unreal)
def em_mundo(bm, cx, cz, h, giro=0.0):
    """leva um bmesh montado em volta da origem (x = leste, y = norte) para o lugar (Godot cx, cz)."""
    from mathutils import Matrix, Vector
    M = Matrix.Translation(Vector(B(cx, cz, h))) @ Matrix.Rotation(math.radians(giro), 4, "Z")
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)


def parede_com_vaos(bm, eixo, fixo, a0, a1, z0, z1, esp, vaos, mi=0):
    """parede reta com vãos (porta/janelas) de verdade: dá para ver e voar por dentro.
    eixo "x": a parede corre em x (y = fixo); eixo "y": corre em y (x = fixo).
    vaos: lista de (centro, largura, z_baixo, z_cima)."""
    def bloco(u0, u1, w0, w1):
        if u1 - u0 < 0.01 or w1 - w0 < 0.01:
            return
        cu, cw = (u0 + u1) / 2, (w0 + w1) / 2
        if eixo == "x":
            caixa(bm, (cu, fixo, cw), (u1 - u0, esp, w1 - w0), mi=mi)
        else:
            caixa(bm, (fixo, cu, cw), (esp, u1 - u0, w1 - w0), mi=mi)
    u = a0
    for (c, larg, zb, zt) in sorted(vaos):
        bloco(u, c - larg / 2, z0, z1)
        bloco(c - larg / 2, c + larg / 2, z0, zb)
        bloco(c - larg / 2, c + larg / 2, zt, z1)
        u = c + larg / 2
    bloco(u, a1, z0, z1)


def moldura(bm, eixo, fixo, c, larg, zb, zt, esp, mi=2):
    """batente de madeira em volta do vão."""
    e = 0.07
    for (du, dz, tu, tz) in ((0, zb - e / 2, larg + 2 * e, e), (0, zt + e / 2, larg + 2 * e, e),
                             (-larg / 2 - e / 2, (zb + zt) / 2, e, zt - zb), (larg / 2 + e / 2, (zb + zt) / 2, e, zt - zb)):
        if eixo == "x":
            caixa(bm, (c + du, fixo, dz), (tu, esp + 0.04, tz), mi=mi)
        else:
            caixa(bm, (fixo, c + du, dz), (esp + 0.04, tu, tz), mi=mi)


def casa():
    """casa sede: alpendre virado para o norte (para a base), telhado de duas águas, chaminé.
    Porta aberta e janelas sem vidro: dá para entrar com o drone; lá dentro tem mesa, bancos, rede e um lampião."""
    bm = bmesh.new()
    L, P, H = 12.0, 9.0, 3.2
    VAR = 2.8
    ESP = 0.22
    z0, z1 = 0.4, 0.4 + H
    caixa(bm, (0, VAR / 2, 0.15), (L + 0.8, P + VAR + 0.6, 0.5), mi=3)                    # base/calçada
    PORTA = (0.4, 1.3, z0, 2.55)
    JAN = 1.3
    frente = [PORTA] + [(x, JAN, 1.35, 2.65) for x in (-4.2, -1.8, 2.6, 4.6)]
    fundo = [(-3.5, JAN, 1.35, 2.65), (1.0, 1.0, z0, 2.45), (3.5, JAN, 1.35, 2.65)]           # porta dos fundos também
    lados = [(-2.0, JAN, 1.35, 2.65), (2.0, JAN, 1.35, 2.65)]
    parede_com_vaos(bm, "x", P / 2, -L / 2, L / 2, z0, z1, ESP, frente, mi=0)
    parede_com_vaos(bm, "x", -P / 2, -L / 2, L / 2, z0, z1, ESP, fundo, mi=0)
    parede_com_vaos(bm, "y", -L / 2, -P / 2 + ESP / 2, P / 2 - ESP / 2, z0, z1, ESP, lados, mi=0)
    parede_com_vaos(bm, "y", L / 2, -P / 2 + ESP / 2, P / 2 - ESP / 2, z0, z1, ESP, lados, mi=0)
    for (c, w, zb, zt) in frente:
        moldura(bm, "x", P / 2, c, w, zb, zt, ESP)
    for (c, w, zb, zt) in fundo:
        moldura(bm, "x", -P / 2, c, w, zb, zt, ESP)
    for (c, w, zb, zt) in lados:
        moldura(bm, "y", -L / 2, c, w, zb, zt, ESP)
        moldura(bm, "y", L / 2, c, w, zb, zt, ESP)
    # parede interna (sala | quarto) com vão de passagem largo
    parede_com_vaos(bm, "y", 1.8, -P / 2 + ESP, P / 2 - ESP, z0, z1, 0.14, [(0.6, 1.6, z0, 2.7)], mi=0)
    # forro de madeira (o telhado fica por cima; sem ele a casa por dentro some no escuro do telhado)
    caixa(bm, (0, 0, z1 + 0.04), (L - 0.1, P - 0.1, 0.06), mi=2)
    # móveis da sala: mesa com 2 bancos, prateleira, filtro de barro no canto
    caixa(bm, (-2.6, 0.2, z0 + 0.76), (2.0, 0.9, 0.06), mi=2)
    for dx in (-0.9, 0.9):
        for dy in (-0.38, 0.38):
            caixa(bm, (-2.6 + dx, 0.2 + dy, z0 + 0.37), (0.07, 0.07, 0.74), mi=2)
    for dy in (-0.75, 1.15):
        caixa(bm, (-2.6, dy, z0 + 0.45), (1.8, 0.32, 0.05), mi=2)
        for dx in (-0.8, 0.8):
            caixa(bm, (-2.6 + dx, dy, z0 + 0.22), (0.06, 0.28, 0.44), mi=2)
    for k in range(3):
        caixa(bm, (-L / 2 + 0.35, -1.5, z0 + 1.1 + k * 0.45), (0.3, 1.6, 0.04), mi=2)
    cilindro(bm, (-L / 2 + 0.55, P / 2 - 0.7, z0 + 0.7), 0.2, 0.16, 0.45, lados=12, mi=3)
    caixa(bm, (-L / 2 + 0.55, P / 2 - 0.7, z0 + 0.35), (0.5, 0.5, 0.7), mi=2)
    # quarto: cama e rede armada na diagonal
    caixa(bm, (4.4, -2.6, z0 + 0.28), (1.9, 2.0, 0.3), mi=2)
    caixa(bm, (4.4, -2.6, z0 + 0.48), (1.8, 1.9, 0.12), mi=5)
    for k in range(9):
        t = k / 8.0
        x = 2.4 + t * 3.0
        y = 2.9 - t * 2.2
        zz = z0 + 1.55 - 0.55 * math.sin(math.pi * t)
        caixa(bm, (x, y, zz), (0.42, 0.95, 0.03), giro_z=-36.0, mi=5)
    # alpendre: piso, pilares e telhadinho
    for x in (-L / 2 + 0.3, -L / 6, L / 6, L / 2 - 0.3):
        cilindro(bm, (x, P / 2 + VAR - 0.3, 0.4), 0.11, 0.12, 2.75, lados=10, mi=2)
    caixa(bm, (0, P / 2 + VAR - 0.3, 3.15), (L + 0.4, 0.2, 0.18), mi=2)
    caixa(bm, (0, P / 2 + VAR / 2, 3.45), (L + 0.8, VAR + 0.6, 0.12), giro_x=8.0, mi=1)
    # telhado de duas águas (cumeeira leste-oeste)
    subida = 2.0
    meia = P / 2 + 0.6
    comp = math.hypot(meia, subida)
    ang = math.degrees(math.atan2(subida, meia))
    for sgn in (-1.0, 1.0):
        caixa(bm, (0, sgn * meia / 2, 0.4 + H + subida / 2 - 0.1), (L + 1.2, comp, 0.14), giro_x=-sgn * ang, mi=1)
    for sgn in (-1.0, 1.0):                                          # oitões
        vs = [bm.verts.new((sgn * L / 2 + dx, y, 0.4 + H + zz)) for dx in (0.11, -0.11)
              for (y, zz) in ((-P / 2, 0.0), (P / 2, 0.0), (0.0, subida))]
        f1 = bm.faces.new(vs[0:3])
        f2 = bm.faces.new(vs[3:6][::-1])
        f1.material_index = f2.material_index = 0
    caixa(bm, (3.0, -1.4, 0.4 + H + 1.6), (0.8, 0.8, 3.2), mi=0)   # chaminé
    caixa(bm, (3.0, -1.4, 0.4 + H + 3.25), (1.0, 1.0, 0.12), mi=3)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    h = alt1(*CASA_C)
    em_mundo(bm, CASA_C[0], CASA_C[1], h - 0.15)
    uv_caixa(bm, 2.0)
    novo_obj("Casa", bm, ["PAREDE", "TELHA", "MADEIRA", "PISO", "METAL", "PANO_CHITA"])
    # luz de dentro (lampião da sala e do quarto) — o Unreal cria as luzes nesses pontos
    zl = h - 0.15 + z1 - 0.35
    LAYOUT.setdefault("luzes", []).extend([
        {"x": CASA_C[0] - 2.4, "y": -CASA_C[1] + 0.2, "z": zl, "intensidade": 1800.0, "raio": 900.0},
        {"x": CASA_C[0] + 3.8, "y": -CASA_C[1] - 1.0, "z": zl, "intensidade": 1200.0, "raio": 700.0},
    ])
    topo_chamine = (CASA_C[0] + 3.0, CASA_C[1] + 1.4, h - 0.15 + 0.4 + H + 3.4)
    frente_p = (CASA_C[0], CASA_C[1] - (P / 2 + VAR + 3.5))
    return topo_chamine, frente_p


def caixa_dagua():
    """caixa d'água azul de fibra em cima de uma torre de 9 m (dá para pousar na tampa)."""
    bm = bmesh.new()
    alt = 9.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            segmento(bm, (sx * 1.6, sy * 1.6, 0), (sx * 1.1, sy * 1.1, alt), 0.09, mi=0, lados=8)
    for z in (2.5, 5.0, 7.5):
        k = 1.6 - 0.5 * z / alt
        pts = [(k, k), (-k, k), (-k, -k), (k, -k)]
        for i in range(4):
            a, b2 = pts[i], pts[(i + 1) % 4]
            segmento(bm, (a[0], a[1], z), (b2[0], b2[1], z), 0.05, mi=0, lados=6)
    caixa(bm, (0, 0, alt + 0.1), (3.0, 3.0, 0.2), mi=2)
    cilindro(bm, (0, 0, alt + 0.2), 1.75, 1.85, 2.4, lados=36, mi=1)
    cilindro(bm, (0, 0, alt + 2.6), 1.2, 1.78, 0.3, lados=36, mi=1)
    cilindro(bm, (0, 0, alt + 2.9), 1.2, 1.2, 0.05, lados=36, mi=1)          # tampa (pouso)
    for z in range(0, int(alt) + 1):                                          # escada
        segmento(bm, (1.45, -0.25, z * 1.0 + 0.3), (1.45, 0.25, z * 1.0 + 0.3), 0.025, mi=0, lados=5)
    segmento(bm, (1.45, -0.25, 0), (1.45, -0.25, alt), 0.03, mi=0, lados=5)
    segmento(bm, (1.45, 0.25, 0), (1.45, 0.25, alt), 0.03, mi=0, lados=5)
    h = alt1(*CAIXA_C)
    em_mundo(bm, CAIXA_C[0], CAIXA_C[1], h - 0.1)
    uv_caixa(bm, 1.0)
    novo_obj("CaixaDagua", bm, ["METAL", "TANQUE", "MADEIRA"])
    return h - 0.1 + alt + 2.95, h - 0.1 + alt + 1.4


def cata_vento():
    """torre de ferro de 10 m com cauda; o rotor é outra malha que o jogo faz girar."""
    bm = bmesh.new()
    alt = 10.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            segmento(bm, (sx * 1.3, sy * 1.3, 0), (sx * 0.3, sy * 0.3, alt), 0.05, mi=0, lados=6)
    for z in (2.0, 4.0, 6.0, 8.0):
        k = 1.3 - 1.0 * z / alt
        for (a, b2) in (((k, k), (-k, k)), ((-k, k), (-k, -k)), ((-k, -k), (k, -k)), ((k, -k), (k, k))):
            segmento(bm, (a[0], a[1], z), (b2[0], b2[1], z), 0.03, mi=0, lados=5)
    caixa(bm, (0, 0, alt), (1.4, 1.4, 0.08), mi=1)
    caixa(bm, (-0.2, 0, alt + 0.45), (1.1, 0.25, 0.25), mi=0)                  # cabeçote
    segmento(bm, (-0.6, 0, alt + 0.45), (-2.6, 0, alt + 0.55), 0.04, mi=0, lados=6)
    caixa(bm, (-2.9, 0, alt + 0.75), (1.2, 0.03, 0.9), mi=0)                    # cauda
    h = alt1(*CATAVENTO_C)
    em_mundo(bm, CATAVENTO_C[0], CATAVENTO_C[1], h - 0.1)
    uv_caixa(bm, 1.0)
    novo_obj("CataVento", bm, ["METAL", "MADEIRA"])
    # rotor: eixo em +X (para o Unreal girar em volta do X do ator)
    rb = bmesh.new()
    cilindro(rb, (0, 0, 0), 0.18, 0.18, 0.3, lados=16, mi=0, eixo=(1, 0, 0))
    for i in range(12):
        a = 2 * math.pi * i / 12
        d = (0.0, math.cos(a), math.sin(a))
        c = (0.12, d[1] * 1.15, d[2] * 1.15)
        caixa(rb, c, (0.02, 0.32, 1.5), giro_x=math.degrees(a) - 90.0, giro_z=0, mi=1)
    segmento(rb, (0.12, 0, 0), (0.12, 0, 0), 0.01)
    uv_caixa(rb, 1.0)
    novo_obj("CataVentoRotor", rb, ["METAL", "PALHETA"])
    centro = B(CATAVENTO_C[0] + 0.45, CATAVENTO_C[1], h - 0.1 + alt + 0.45)
    LAYOUT.setdefault("giratorios", []).append({"malha": "CataVentoRotor", "x": centro[0], "y": centro[1], "z": centro[2],
                                                "yaw": 0.0, "graus_s": 140.0})
    return centro


def silos():
    bm = bmesh.new()
    tops = []
    for i, (sx, sz) in enumerate(SILOS_C):
        h = alt1(sx, sz)
        bx, by, _ = B(sx, sz, h)
        cilindro(bm, (bx, by, h - 0.2), 2.4, 2.4, 9.2, lados=40, mi=0)
        cilindro(bm, (bx, by, h + 9.0), 0.3, 2.55, 1.8, lados=40, mi=0)
        cilindro(bm, (bx, by, h - 0.25), 2.7, 2.7, 0.45, lados=40, mi=1)
        for z in range(0, 9):
            segmento(bm, (bx + 2.5, by - 0.2, h + z + 0.4), (bx + 2.5, by + 0.2, h + z + 0.4), 0.02, mi=2, lados=5)
        segmento(bm, (bx + 2.5, by - 0.2, h), (bx + 2.5, by - 0.2, h + 9.2), 0.025, mi=2, lados=5)
        segmento(bm, (bx + 2.5, by + 0.2, h), (bx + 2.5, by + 0.2, h + 9.2), 0.025, mi=2, lados=5)
        tops.append((bx, by, h + 11.0))
    uv_caixa(bm, 1.0)
    novo_obj("Silos", bm, ["ZINCO", "PISO", "METAL"])
    return tops


def carreta():
    bm = bmesh.new()
    caixa(bm, (0, 0, 1.05), (4.2, 2.2, 0.12), mi=0)                               # carroceria (pouso)
    for sy in (-1, 1):
        caixa(bm, (0, sy * 1.12, 1.3), (4.2, 0.06, 0.45), mi=0)
    caixa(bm, (0, 0, 0.8), (3.6, 0.3, 0.3), mi=1)
    for sx in (-1.1, 1.1):
        for sy in (-1, 1):
            cilindro(bm, (sx, sy * 1.05, 0.45), 0.45, 0.45, 0.28, lados=20, mi=2, eixo=(0, 1, 0))
    segmento(bm, (2.1, 0, 0.8), (3.6, 0, 0.55), 0.06, mi=1, lados=8)
    h = alt1(*CARRETA_C)
    em_mundo(bm, CARRETA_C[0], CARRETA_C[1], h - 0.05, giro=25.0)
    uv_caixa(bm, 1.0)
    novo_obj("Carreta", bm, ["MADEIRA", "METAL", "PNEU"])
    return h - 0.05 + 1.12


def pier():
    bm = bmesh.new()
    topo = NIVEL_AGUA + 0.55
    for i in range(6):
        for sy in (-0.85, 0.85):
            x = -i * 1.8
            cilindro(bm, (x, sy, NIVEL_AGUA - 1.5), 0.09, 0.1, 2.1, lados=8, mi=0)
    for i in range(30):
        caixa(bm, (-i * 0.36 + 0.4, 0, 0), (0.3, 2.0, 0.06), mi=0)
    from mathutils import Matrix, Vector
    bx, by, _ = B(PIER_C[0], PIER_C[1], 0)
    for v in bm.verts:
        if v.co.z == 0 or abs(v.co.z) < 0.04:
            pass
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector((bx, by, 0))), verts=bm.verts)
    for v in bm.verts:
        if abs(v.co.z) <= 0.031:
            v.co.z += topo
    uv_caixa(bm, 1.0)
    novo_obj("Pier", bm, ["MADEIRA"])
    return (bx - 9.5, by, topo)


def plataforma(nome, cx, cz, h):
    """quadrado de madeira de 2,2 m com borda amarela (ponto de coleta/entrega)."""
    bm = bmesh.new()
    caixa(bm, (0, 0, 0.06), (2.2, 2.2, 0.12), mi=0)
    for (x, y, w, d) in ((0, 1.0, 2.2, 0.2), (0, -1.0, 2.2, 0.2), (1.0, 0, 0.2, 2.2), (-1.0, 0, 0.2, 2.2)):
        caixa(bm, (x, y, 0.125), (w, d, 0.01), mi=1)
    em_mundo(bm, cx, cz, h)
    uv_caixa(bm, 1.0)
    novo_obj(nome, bm, ["MADEIRA", "PINTURA_AMARELA"])
    SEM_MATO.append((cx, cz, 2.6))


def transformador():
    """um poste da rede ganha transformador (alvo de foto)"""
    # o mesmo cálculo de postes(): pega o poste mais perto de z = -90
    melhor = None
    acum, prox = 0.0, 0.0
    for i in range(len(ESTRADA) - 1):
        ax, az = ESTRADA[i]
        bx, bz = ESTRADA[i + 1]
        seg = math.hypot(bx - ax, bz - az)
        dx, dz = (bx - ax) / seg, (bz - az) / seg
        nx, nz = dz * 13.0, -dx * 13.0
        while prox <= acum + seg:
            px, pz = ax + dx * (prox - acum) + nx, az + dz * (prox - acum) + nz
            prox += 48.0
            if melhor is None or abs(pz + 90) < abs(melhor[1] + 90):
                melhor = (px, pz)
        acum += seg
    px, pz = melhor
    y = alt1(px, pz)
    b0 = B(px, pz, y)
    bm = bmesh.new()
    cilindro(bm, (b0[0] + 0.35, b0[1], y + 7.0), 0.32, 0.32, 1.1, lados=20, mi=0)
    caixa(bm, (b0[0] + 0.2, b0[1], y + 7.5), (0.25, 0.12, 0.6), mi=0)
    for k in range(3):
        cilindro(bm, (b0[0] + 0.2 + (k - 1) * 0.18, b0[1], y + 8.1), 0.04, 0.05, 0.18, lados=8, mi=1)
    uv_caixa(bm, 1.0)
    novo_obj("Transformador", bm, ["METAL", "ISOLADOR"])
    return (b0[0] + 0.35, b0[1], y + 7.6)


MOLDES = {}
SEM_MATO = []   # (x, z Godot, raio m): lugares onde não nasce capim/flor (plataformas etc.)


def molde(bm):
    """copia vértices, faces e material de um bmesh (para espalhar milhares de cópias com numpy)."""
    bm = bm.copy()
    bmesh.ops.triangulate(bm, faces=bm.faces[:])   # o FBX SDK não triangula malhas gigantes: já vai em triângulos
    bm.verts.ensure_lookup_table()
    v = np.array([vv.co[:] for vv in bm.verts], dtype=np.float64)
    f = [[vv.index for vv in ff.verts] for ff in bm.faces]
    m = [ff.material_index for ff in bm.faces]
    return v, f, m


def espalhar(nome, mold, posicoes, materiais):
    """uma malha só com cópias do molde: posicoes = lista de (x, y, z, giro_rad, escala_xy, escala_z) no Blender."""
    v0, f0, m0 = mold
    nv = len(v0)
    P = np.array(posicoes, dtype=np.float64)
    n = len(P)
    c, s_ = np.cos(P[:, 3]), np.sin(P[:, 3])
    x = v0[None, :, 0] * P[:, 4:5]
    y = v0[None, :, 1] * P[:, 4:5]
    z = v0[None, :, 2] * P[:, 5:6]
    X = x * c[:, None] - y * s_[:, None] + P[:, 0:1]
    Y = x * s_[:, None] + y * c[:, None] + P[:, 1:2]
    Z = z + P[:, 2:3]
    verts = np.stack([X, Y, Z], axis=2).reshape(-1, 3).astype(np.float32)
    tam = [len(ff) for ff in f0]
    idx0 = np.array([i for ff in f0 for i in ff], dtype=np.int64)
    loops = (idx0[None, :] + (np.arange(n) * nv)[:, None]).ravel().astype(np.int32)
    tot = np.tile(np.array(tam, dtype=np.int32), n)
    inicio = np.concatenate([[0], np.cumsum(tot)[:-1]]).astype(np.int32)
    me = bpy.data.meshes.new(nome)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(len(loops))
    me.loops.foreach_set("vertex_index", loops)
    me.polygons.add(len(tot))
    me.polygons.foreach_set("loop_start", inicio)
    me.polygons.foreach_set("loop_total", tot)
    me.polygons.foreach_set("material_index", np.tile(np.array(m0, dtype=np.int32), n))
    me.update(calc_edges=True)
    for mm in materiais:
        me.materials.append(mat(mm))
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    print(nome, n, "cópias,", len(tot), "faces")
    return ob


def normais_para_cima(ob):
    """capim e flores com a normal virada para cima: a luz bate neles como bate no chão
    (sem isso cada folha fica com um lado preto na sombra)."""
    me = ob.data
    try:
        me.normals_split_custom_set_from_vertices([(0.0, 0.0, 1.0)] * len(me.vertices))
    except Exception as e:
        print("normais personalizadas falharam:", e)


def pontos_livres(rr, N, r_min, r_max, perto=0.45, r_perto=45.0, folga_estrada=4.8):
    """pontos (x, z Godot) em volta da base, mais densos perto, fora de estrada, açude, roça, construções."""
    ang = rr.uniform(0, 2 * np.pi, N)
    r = np.sqrt(rr.uniform(r_min ** 2, r_max ** 2, N))
    r = np.where(rr.uniform(0, 1, N) < perto, np.sqrt(rr.uniform(r_min ** 2, r_perto ** 2, N)), r)
    gx, gz = np.cos(ang) * r, np.sin(ang) * r + 4.0
    ok = dist_estrada(gx, gz) > folga_estrada
    ok &= acude_e(gx, gz) > 1.25
    ok &= ~((gx > ROCA[0] - 3) & (gx < ROCA[2] + 3) & (gz > ROCA[1] - 3) & (gz < ROCA[3] + 3))
    ok &= np.hypot(gx - GALPAO_C[0], gz - GALPAO_C[1]) > 12.0
    for (cx, cz), r0, r1 in ZONAS_PLANAS:
        ok &= np.hypot(gx - cx, gz - cz) > r0 + 1.0
    for (cx, cz, rr0) in SEM_MATO:
        ok &= np.hypot(gx - cx, gz - cz) > rr0
    return gx[ok], gz[ok]


def manchas(gx, gz, semente, escala=0.045, limiar=0.15):
    """deixa só os pontos dentro de manchas (flores e palha aparecem em grupos, não espalhadas por igual)."""
    rn = Ruido(semente, 3)
    v = rn(gx * escala, gz * escala)
    return v > limiar


def plantacoes():
    """milharal, capim, palha seca, flores e mandacarus já espalhados (malhas prontas)."""
    rr = np.random.RandomState(77)
    pos = []
    x = ROCA[0] + 0.6
    while x < ROCA[2] - 0.3:
        z = ROCA[1] + 0.3
        while z < ROCA[3] - 0.3:
            px, pz = x + rr.uniform(-0.08, 0.08), z + rr.uniform(-0.06, 0.06)
            pos.append((px, pz))
            z += 0.40
        x += 0.95
    P = np.array(pos)
    H = altura(P[:, 0], P[:, 1])
    posicoes = np.stack([P[:, 0], -P[:, 1], H - 0.03, rr.uniform(0, 2 * np.pi, len(P)),
                         rr.uniform(0.85, 1.15, len(P)), rr.uniform(0.8, 1.15, len(P))], axis=1)
    espalhar("Milharal", MOLDES["milho"], posicoes, ["MILHO", "ESPIGA"])

    def montar(nome, molde_, gx, gz, esc_xy, esc_z, mats, afunda=0.03, cima=True):
        n = len(gx)
        if n == 0:
            return None
        gh = altura(gx, gz)
        posic = np.stack([gx, -gz, gh - afunda, rr.uniform(0, 2 * np.pi, n),
                          rr.uniform(*esc_xy, n), rr.uniform(*esc_z, n)], axis=1)
        ob = espalhar(nome, molde_, posic, mats)
        if cima:
            normais_para_cima(ob)
        return ob

    # capim verde: touceiras baixas (35–60 cm) — antes eram enormes e jogavam sombra preta por todo lado
    gx, gz = pontos_livres(rr, 90000, 6.0, 140.0)
    montar("Pasto", MOLDES["capim"], gx[:34000], gz[:34000], (0.55, 0.95), (0.55, 0.95), ["CAPIM"])
    # palha seca (tom de feno) em manchas
    gx, gz = pontos_livres(rr, 60000, 6.0, 160.0, perto=0.3)
    m = manchas(gx, gz, 21)
    montar("Palha", MOLDES["palha"], gx[m][:14000], gz[m][:14000], (0.6, 1.1), (0.5, 0.9), ["PALHA"])
    # flores do campo: amarelas, brancas e roxas, cada cor nas suas manchas
    for k, (nome, cor) in enumerate((("FloresAmarelas", "FLOR_AMARELA"), ("FloresBrancas", "FLOR_BRANCA"), ("FloresRoxas", "FLOR_ROXA"))):
        gx, gz = pontos_livres(rr, 40000, 6.0, 120.0, perto=0.5)
        m = manchas(gx, gz, 31 + k * 7, escala=0.06, limiar=0.32)
        montar(nome, MOLDES["flor"], gx[m][:3500], gz[m][:3500], (0.8, 1.25), (0.75, 1.3), ["CAPIM", cor])
    # mandacarus (cacto do sertão) pelos cantos do pasto — são sólidos (o drone bate)
    gx, gz = pontos_livres(rr, 4000, 25.0, 320.0, perto=0.0, folga_estrada=7.0)
    ok = np.ones(len(gx), dtype=bool)
    escolhidos = []
    for i in range(len(gx)):
        if len(escolhidos) >= 45:
            break
        if all(math.hypot(gx[i] - a, gz[i] - b) > 14.0 for a, b in escolhidos) and livre(gx[i], gz[i], 3.0):
            escolhidos.append((gx[i], gz[i]))
    if escolhidos:
        E = np.array(escolhidos)
        montar("Mandacarus", MOLDES["cacto"], E[:, 0], E[:, 1], (0.8, 1.3), (0.7, 1.4), ["CACTO"], afunda=0.1, cima=False)


def modelos_soltos():
    """malhas que o jogo usa em tempo de execução (ficam escondidas no mapa como modelo)."""
    # pé de milho (~2,1 m)
    bm = bmesh.new()
    cilindro(bm, (0, 0, 0), 0.018, 0.026, 2.1, lados=6, mi=0)
    for i in range(7):
        a = i * 2.4
        z0 = 0.35 + i * 0.24
        d = (math.cos(a), math.sin(a))
        pts = [(0.0, 0.0), (0.25, 0.18), (0.5, 0.22), (0.72, 0.1)]
        prev_l = prev_r = None
        for k, (r, dz) in enumerate(pts):
            w = 0.045 * (1 - k / len(pts)) + 0.01
            c = (d[0] * r, d[1] * r, z0 + dz)
            pl = bm.verts.new((c[0] - d[1] * w, c[1] + d[0] * w, c[2]))
            pr = bm.verts.new((c[0] + d[1] * w, c[1] - d[0] * w, c[2]))
            if prev_l:
                f = bm.faces.new((prev_l, prev_r, pr, pl))
                f.material_index = 0
            prev_l, prev_r = pl, pr
    cilindro(bm, (0.04, 0, 1.15), 0.035, 0.045, 0.28, lados=8, mi=1, eixo=(0.25, 0, 1))      # espiga
    for k in range(5):
        a = k * 1.25
        segmento(bm, (0, 0, 2.08), (math.cos(a) * 0.14, math.sin(a) * 0.14, 2.3), 0.006, mi=1, lados=3)
    uv_caixa(bm, 0.5)
    MOLDES["milho"] = molde(bm)
    novo_obj("PeMilho", bm, ["MILHO", "ESPIGA"])
    # touceira de capim (~0,5 m)
    bm = bmesh.new()
    rr = random.Random(5)
    for i in range(16):
        a = rr.random() * 2 * math.pi
        r0 = rr.uniform(0.0, 0.12)
        base = (math.cos(a) * r0, math.sin(a) * r0, 0.0)
        alt = rr.uniform(0.3, 0.6)
        inc = rr.uniform(0.1, 0.35)
        lado = (-math.sin(a), math.cos(a))
        topo = (base[0] + math.cos(a) * inc, base[1] + math.sin(a) * inc, alt)
        meio = (base[0] + math.cos(a) * inc * 0.4, base[1] + math.sin(a) * inc * 0.4, alt * 0.55)
        w0, w1 = 0.022, 0.012
        v = [bm.verts.new((base[0] - lado[0] * w0, base[1] - lado[1] * w0, 0)), bm.verts.new((base[0] + lado[0] * w0, base[1] + lado[1] * w0, 0)),
             bm.verts.new((meio[0] + lado[0] * w1, meio[1] + lado[1] * w1, meio[2])), bm.verts.new((meio[0] - lado[0] * w1, meio[1] - lado[1] * w1, meio[2])),
             bm.verts.new(topo)]
        bm.faces.new((v[0], v[1], v[2], v[3]))
        bm.faces.new((v[3], v[2], v[4]))
    uv_caixa(bm, 0.5)
    MOLDES["capim"] = molde(bm)
    novo_obj("Capim", bm, ["CAPIM"])
    # palha seca: folhas mais finas, abertas e tombadas
    bm = bmesh.new()
    rr = random.Random(9)
    for i in range(12):
        a = rr.random() * 2 * math.pi
        base = (math.cos(a) * rr.uniform(0, 0.08), math.sin(a) * rr.uniform(0, 0.08), 0.0)
        alt = rr.uniform(0.22, 0.45)
        inc = rr.uniform(0.2, 0.45)
        lado = (-math.sin(a), math.cos(a))
        topo = (base[0] + math.cos(a) * inc, base[1] + math.sin(a) * inc, alt)
        w = 0.016
        v = [bm.verts.new((base[0] - lado[0] * w, base[1] - lado[1] * w, 0)), bm.verts.new((base[0] + lado[0] * w, base[1] + lado[1] * w, 0)),
             bm.verts.new(topo)]
        bm.faces.new(v)
    MOLDES["palha"] = molde(bm)
    bm.free()
    # flor do campo: talo fino + 5 pétalas em estrela (material 0 = talo, 1 = pétala)
    bm = bmesh.new()
    alt = 0.32
    v = [bm.verts.new((-0.006, 0, 0)), bm.verts.new((0.006, 0, 0)), bm.verts.new((0.004, 0, alt)), bm.verts.new((-0.004, 0, alt))]
    f = bm.faces.new(v)
    f.material_index = 0
    for (dx, dz, w) in ((0.0, 0.12, 0.05), (0.0, 0.2, 0.04)):    # folhinhas
        v = [bm.verts.new((0, 0, dz)), bm.verts.new((0.09, w * 0.6, dz + 0.04)), bm.verts.new((0.12, 0, dz + 0.07)), bm.verts.new((0.09, -w * 0.6, dz + 0.04))]
        bm.faces.new(v).material_index = 0
    centro = bm.verts.new((0, 0, alt + 0.01))
    for k in range(5):
        a0 = k * 2 * math.pi / 5
        p1 = bm.verts.new((math.cos(a0 - 0.32) * 0.03, math.sin(a0 - 0.32) * 0.03, alt + 0.012))
        p2 = bm.verts.new((math.cos(a0) * 0.065, math.sin(a0) * 0.065, alt + 0.02))
        p3 = bm.verts.new((math.cos(a0 + 0.32) * 0.03, math.sin(a0 + 0.32) * 0.03, alt + 0.012))
        bm.faces.new((centro, p1, p2, p3)).material_index = 1
    MOLDES["flor"] = molde(bm)
    bm.free()
    # mandacaru: tronco com 2 a 3 braços que sobem
    bm = bmesh.new()
    cilindro(bm, (0, 0, -0.1), 0.17, 0.15, 3.0, lados=10, mi=0)
    for (ang, h0, comp, alt_b) in ((0.0, 1.1, 0.55, 1.3), (2.6, 1.5, 0.45, 1.0), (4.4, 0.9, 0.4, 0.8)):
        dx, dy = math.cos(ang), math.sin(ang)
        segmento(bm, (dx * 0.1, dy * 0.1, h0), (dx * comp, dy * comp, h0 + 0.15), 0.22, mi=0, lados=8)
        cilindro(bm, (dx * comp, dy * comp, h0 + 0.05), 0.12, 0.11, alt_b, lados=8, mi=0)
    for k in range(10):                                             # gomos (costelas) no tronco
        a = k * 2 * math.pi / 10
        segmento(bm, (math.cos(a) * 0.16, math.sin(a) * 0.16, 0.0), (math.cos(a) * 0.145, math.sin(a) * 0.145, 2.9), 0.03, mi=0, lados=3)
    MOLDES["cacto"] = molde(bm)
    bm.free()
    # caixa de entrega (40 x 30 x 30 cm) com fita
    bm = bmesh.new()
    caixa(bm, (0, 0, 0), (0.4, 0.3, 0.3), mi=0)
    caixa(bm, (0, 0, 0.152), (0.42, 0.06, 0.006), mi=1)
    caixa(bm, (0.202, 0, 0.0), (0.006, 0.06, 0.3), mi=1)
    caixa(bm, (-0.202, 0, 0.0), (0.006, 0.06, 0.3), mi=1)
    uv_caixa(bm, 0.5)
    novo_obj("CaixaEntrega", bm, ["PAPELAO", "FITA"])
    # ferradura dourada (em pé, 36 cm)
    bm = bmesh.new()
    pts = []
    for i in range(25):
        a = math.radians(-30 + i * 240 / 24)
        pts.append((0.0, math.cos(a) * 0.16, math.sin(a) * 0.16))
    for a0, a1 in zip(pts, pts[1:]):
        segmento(bm, a0, a1, 0.03, mi=0, lados=8)
    for p0 in (pts[0], pts[-1]):
        caixa(bm, (p0[0], p0[1], p0[2] - 0.03), (0.07, 0.08, 0.05), mi=0)
    uv_caixa(bm, 0.5)
    novo_obj("Ferradura", bm, ["OURO"])
    # farol: coluna de luz de 40 m (marca o alvo da missão de longe)
    bm = bmesh.new()
    n = 24
    baixo = [bm.verts.new((math.cos(2 * math.pi * i / n) * 1.0, math.sin(2 * math.pi * i / n) * 1.0, 0.0)) for i in range(n)]
    cima = [bm.verts.new((math.cos(2 * math.pi * i / n) * 1.0, math.sin(2 * math.pi * i / n) * 1.0, 40.0)) for i in range(n)]
    uv = bm.loops.layers.uv.verify()
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((baixo[i], baixo[j], cima[j], cima[i]))
        for lp in f.loops:
            lp[uv].uv = (i / n, 0.0 if lp.vert.co.z < 1 else 1.0)
    novo_obj("Farol", bm, ["FAROL"])


def fazenda():
    chamine, frente_casa = casa()
    topo_tanque, meio_tanque = caixa_dagua()
    rotor = cata_vento()
    tops_silos = silos()
    piso_carreta = carreta()
    ponta_pier = pier()
    trafo = transformador()
    modelos_soltos()
    # coleta das caixas: na frente do lado aberto do galpão
    g = math.radians(GALPAO_GIRO)
    lx, ly = 0.0, -(7.5 / 2 + 6.0)
    cx = GALPAO_C[0] + lx * math.cos(g) - ly * math.sin(g)
    cz = GALPAO_C[1] - (lx * math.sin(g) + ly * math.cos(g))
    h_coleta = alt1(cx, cz)
    plataforma("PlataformaColeta", cx, cz, h_coleta)
    h_casa = alt1(*frente_casa)
    plataforma("PlataformaCasa", frente_casa[0], frente_casa[1], h_casa)
    plantacoes()
    LAYOUT["coleta"] = list(B(cx, cz, h_coleta + 0.13))
    cxb, cyb, _ = B(*CAIXA_C, 0)
    carx, cary, _ = B(*CARRETA_C, 0)
    LAYOUT["entregas"] = [
        {"nome": "Casa sede", "pos": list(B(frente_casa[0], frente_casa[1], h_casa + 0.13))},
        {"nome": "Caixa d'água", "pos": [cxb, cyb, topo_tanque]},
        {"nome": "Carreta do curral", "pos": [carx, cary, piso_carreta]},
        {"nome": "Píer do açude", "pos": list(ponta_pier)},
    ]
    gtopo = B(GALPAO_C[0], GALPAO_C[1], ALT_GALPAO + 4.9)
    LAYOUT["fotos"] = [
        {"nome": "Transformador do poste", "pos": list(trafo)},
        {"nome": "Rotor do cata-vento", "pos": list(rotor)},
        {"nome": "Caixa d'água", "pos": [cxb, cyb, meio_tanque]},
        {"nome": "Telhado do galpão", "pos": list(gtopo)},
        {"nome": "Topo do silo", "pos": list(tops_silos[0])},
        {"nome": "Chaminé da casa", "pos": list(B(chamine[0], chamine[1], chamine[2]))},
    ]
    # ferraduras douradas escondidas pelo mapa
    fx = []
    def f(x, z, h_rel, base=None):
        b = base if base is not None else alt1(x, z)
        fx.append(list(B(x, z, b + h_rel)))
    f(GALPAO_C[0], GALPAO_C[1], 1.3, ALT_GALPAO)                              # dentro do galpão
    f(GALPAO_C[0], GALPAO_C[1], 5.4, ALT_GALPAO)                              # em cima do telhado
    fx.append([ponta_pier[0] - 1.5, ponta_pier[1], ponta_pier[2] + 1.0])       # na ponta do píer
    f(-19.0, -88.0, 1.0)                                                        # atrás dos silos
    fx.append([rotor[0] - 0.5, rotor[1], rotor[2] + 0.9])                       # em cima do cata-vento
    f((ROCA[0] + ROCA[2]) / 2, (ROCA[1] + ROCA[3]) / 2, 2.9)                   # no meio do milharal
    f(ACUDE_C[0], ACUDE_C[1], 1.6, NIVEL_AGUA)                                 # sobre o açude
    f(CAIXA_C[0], CAIXA_C[1], 3.0)                                             # embaixo da caixa d'água
    f(-150.0, -241.5, 4.0)                                                      # entre os eucaliptos
    fx.append([chamine[0], -chamine[1], chamine[2] + 0.7])                     # na chaminé da casa
    f(-15.0, 3.0, 7.3)                                                          # no alto da biruta
    f(trafo[0] - 2.0, -trafo[1] + 40.0, 5.2)                                    # embaixo dos fios
    LAYOUT["ferraduras"] = fx
    LAYOUT["roca"] = {"x0": ROCA[0], "y0": -ROCA[3], "x1": ROCA[2], "y1": -ROCA[1]}
    # pontos de vista para o voo de teste (fotos das construções novas)
    def vista(alvo_x, alvo_z, alvo_h, de_x, de_z, de_h):
        a = B(alvo_x, alvo_z, alvo_h)
        d = B(de_x, de_z, alt1(de_x, de_z) + de_h)
        yaw = math.degrees(math.atan2(a[1] - d[1], a[0] - d[0]))
        return {"x": d[0], "y": d[1], "z": d[2], "yaw": yaw}
    LAYOUT["vistas"] = [
        vista(CASA_C[0], CASA_C[1], alt1(*CASA_C) + 3, CASA_C[0] + 4, CASA_C[1] - 22, 4.0),
        vista(CAIXA_C[0], CAIXA_C[1], alt1(*CAIXA_C) + 8, CAIXA_C[0] - 14, CAIXA_C[1] - 12, 6.0),
        vista(CATAVENTO_C[0], CATAVENTO_C[1], alt1(*CATAVENTO_C) + 9, CATAVENTO_C[0] + 16, CATAVENTO_C[1] - 6, 7.0),
        vista(SILOS_C[0][0], SILOS_C[0][1], alt1(*SILOS_C[0]) + 6, SILOS_C[0][0] + 14, SILOS_C[0][1] + 14, 5.0),
        vista((ROCA[0] + ROCA[2]) / 2, (ROCA[1] + ROCA[3]) / 2, 0, ROCA[0] - 8, ROCA[3] + 6, 9.0),
        vista(PIER_C[0] - 5, PIER_C[1], NIVEL_AGUA, PIER_C[0] + 10, PIER_C[1] + 10, 4.0),
    ]


# ----------------------------------------------------------------------------- exportação
def exportar(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    caminho = os.path.join(SAIDA, ob.name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=caminho, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
                             axis_forward="-Y", axis_up="Z", mesh_smooth_type="FACE", colors_type="LINEAR",
                             use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False, path_mode="AUTO")
    print("  ->", caminho, round(os.path.getsize(caminho) / 1e6, 1), "MB")


def main():
    circuito()
    terreno()
    agua()
    base_pouso()
    galpao()
    biruta()
    cercas()
    postes()
    aro()
    haste()
    marcador()
    fazenda()
    vegetacao()
    LAYOUT["inicio"] = {"x": 0.0, "y": -2.0, "z": ALT_CENTRO - 0.28 + 0.4 + 0.15, "yaw": 90.0}
    for ob in list(bpy.context.scene.objects):
        exportar(ob)
    with open(os.path.join(SAIDA, "layout_campo.json"), "w", encoding="utf-8") as f:
        json.dump(LAYOUT, f, ensure_ascii=False, indent=1)
    print("layout_campo.json:", len(LAYOUT["aros"]), "aros,", len(LAYOUT["plantas"]), "plantas")


main()
