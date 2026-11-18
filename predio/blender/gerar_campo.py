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
    vegetacao()
    LAYOUT["inicio"] = {"x": 0.0, "y": -2.0, "z": ALT_CENTRO - 0.28 + 0.4 + 0.15, "yaw": 90.0}
    for ob in list(bpy.context.scene.objects):
        exportar(ob)
    with open(os.path.join(SAIDA, "layout_campo.json"), "w", encoding="utf-8") as f:
        json.dump(LAYOUT, f, ensure_ascii=False, indent=1)
    print("layout_campo.json:", len(LAYOUT["aros"]), "aros,", len(LAYOUT["plantas"]), "plantas")


main()
