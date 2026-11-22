"""Mapa 3 — USINA SIDERÚRGICA ABANDONADA (Unreal).

Gera, no Blender (sem interface), os FBX e o layout_usina.json que o
unreal/construir_usina.py monta no editor. Coordenadas do Blender: x = leste,
y = norte, z = altura (m). No Unreal: (x*100, -y*100, z*100).

Partes do mapa (área de voo ~300 x 200 m, teto 75 m):
  Terreno       pátio de 700 m (asfalto, brita, terra, manchas de fuligem nas cores de vértice)
  Aciaria       galpão gigante (120 x 32 m, 24 m de altura): pilares em I, treliças do telhado,
                vigas de rolamento, passarela, escada, cabine de comando
  Chapas        chapas onduladas das paredes e do telhado, com muitos buracos (feixes de luz)
  Pontes        duas pontes rolantes (viga, carro, cabine, gancho e correntes)
  Conversor     conversor de aço tombado nos munhões, panelas de aço, lingoteira
  AltoForno     alto-forno (cuba, anéis de plataforma, escadas), casa de corrida com brasa
  Regeneradores três regeneradores (cowpers) de tijolo com cúpula e o tubo de ar quente
  Esteira       ponte da esteira inclinada (galeria em treliça) do pátio até o topo do forno
  Chamines      duas chaminés de tijolo de 56 m (escada com gaiola) e uma quebrada
  Silos         quatro silos com a galeria de cima
  Tubulacao     rack de tubos elevado que atravessa a usina
  Ferrovia      trilhos, dormentes, locomotiva e vagões de minério
  Escritorio    prédio de escritório em ruína
  Pilhas        pilhas de minério e de carvão
  Sucata        sucata, vigas empilhadas, tambores, contêiner
  Base          base de pouso do drone + plataforma de coleta das cargas
  Aro, Haste, Marcador, CaixaEntrega (caixa de peças), Engrenagem (dourada), Farol

Uso:  python3 gerar_usina.py SAIDA   (precisa do módulo bpy)
"""
import json
import math
import os
import random
import sys

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

SAIDA = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].endswith(".py") else "/tmp/usina_out"
os.makedirs(SAIDA, exist_ok=True)
random.seed(1977)
bpy.ops.wm.read_factory_settings(use_empty=True)

LAYOUT = {"nome": "usina", "aros": [], "entregas": [], "fotos": [], "ferraduras": [], "vistas": [],
          "luzes": [], "plantas": [], "giratorios": []}

# ----------------------------------------------------------------------------- utilidades
MATS = {}


def mat(nome):
    if nome not in MATS:
        MATS[nome] = bpy.data.materials.new(nome)
    return MATS[nome]


class Malha:
    """bmesh com lista de materiais por nome (mi = nome do slot)."""

    def __init__(self):
        self.bm = bmesh.new()
        self.slots = []

    def mi(self, nome):
        if nome not in self.slots:
            self.slots.append(nome)
        return self.slots.index(nome)

    def pintar(self, vs, nome):
        i = self.mi(nome)
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = i


OBJS = []


def finalizar(nome, m, escala_uv=None, recalc=True):
    bm = m.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0005)
    if recalc:
        # só para malhas fechadas: numa superfície aberta (terreno, pilhas) o recalc pode virar tudo para baixo
        faces = [f for f in bm.faces if m.slots[f.material_index] != "CHAPA_ONDULADA"]
        bmesh.ops.recalc_face_normals(bm, faces=faces)
    uv_caixa(bm, escala_uv or {})
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    for s in m.slots:
        me.materials.append(mat(s))
    ob = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(ob)
    OBJS.append(ob)
    print(nome, len(me.vertices), "vértices", len(me.polygons), "triângulos")
    return ob


def uv_caixa(bm, escalas):
    """UV por projeção de caixa; 1 UV = 'escala' metros (por slot)."""
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        e = escalas.get(f.material_index, 2.0)
        for lp in f.loops:
            co = lp.vert.co
            if ax == 0:
                lp[uv].uv = (co.y / e, co.z / e)
            elif ax == 1:
                lp[uv].uv = (co.x / e, co.z / e)
            else:
                lp[uv].uv = (co.x / e, co.y / e)


def caixa(m, centro, tam, mat_nome, giro_z=0.0, giro_x=0.0, giro_y=0.0):
    res = bmesh.ops.create_cube(m.bm, size=1.0)
    vs = res["verts"]
    M = (Matrix.Translation(Vector(centro)) @ Matrix.Rotation(math.radians(giro_z), 4, "Z")
         @ Matrix.Rotation(math.radians(giro_y), 4, "Y") @ Matrix.Rotation(math.radians(giro_x), 4, "X")
         @ Matrix.Diagonal(Vector((tam[0], tam[1], tam[2], 1.0))))
    bmesh.ops.transform(m.bm, matrix=M, verts=vs)
    m.pintar(vs, mat_nome)
    return vs


def cilindro(m, base, r1, r2, alt, mat_nome, lados=16, eixo=None, tampas=True):
    res = bmesh.ops.create_cone(m.bm, cap_ends=tampas, cap_tris=False, segments=lados, radius1=r1, radius2=r2, depth=alt)
    vs = res["verts"]
    if eixo is None:
        M = Matrix.Translation(Vector(base) + Vector((0, 0, alt / 2)))
    else:
        e = Vector(eixo).normalized()
        rot = Vector((0, 0, 1)).rotation_difference(e).to_matrix().to_4x4()
        M = Matrix.Translation(Vector(base) + e * (alt / 2)) @ rot
    bmesh.ops.transform(m.bm, matrix=M, verts=vs)
    m.pintar(vs, mat_nome)
    for f in {f for v in vs for f in v.link_faces}:
        f.smooth = True
    return vs


def tubo(m, p1, p2, r, mat_nome, lados=8):
    a, b = Vector(p1), Vector(p2)
    d = b - a
    if d.length < 1e-4:
        return []
    return cilindro(m, tuple(a), r, r, d.length, mat_nome, lados=lados, eixo=tuple(d.normalized()), tampas=False)


def barra(m, p1, p2, larg, alt, mat_nome, cima=(0, 0, 1)):
    """barra retangular de p1 a p2 (perfil larg x alt)."""
    a, b = Vector(p1), Vector(p2)
    d = b - a
    L = d.length
    if L < 1e-4:
        return []
    x = d.normalized()
    up = Vector(cima)
    if abs(x.dot(up)) > 0.95:
        up = Vector((1, 0, 0)) if abs(x.x) < 0.9 else Vector((0, 1, 0))
    y = up.cross(x).normalized()
    z = x.cross(y).normalized()
    R = Matrix((x, y, z)).transposed().to_4x4()
    res = bmesh.ops.create_cube(m.bm, size=1.0)
    vs = res["verts"]
    M = Matrix.Translation((a + b) / 2) @ R @ Matrix.Diagonal(Vector((L, larg, alt, 1.0)))
    bmesh.ops.transform(m.bm, matrix=M, verts=vs)
    m.pintar(vs, mat_nome)
    return vs


def viga_i(m, p1, p2, h, b, mat_nome, cima=(0, 0, 1), t=None):
    """perfil I (altura h, mesa b) de p1 a p2: alma + duas mesas."""
    a, c = Vector(p1), Vector(p2)
    d = c - a
    if d.length < 1e-4:
        return
    x = d.normalized()
    up = Vector(cima)
    if abs(x.dot(up)) > 0.95:
        up = Vector((1, 0, 0)) if abs(x.x) < 0.9 else Vector((0, 1, 0))
    y = up.cross(x).normalized()
    z = x.cross(y).normalized()
    t = t or max(0.012, h * 0.06)
    barra(m, a, c, t, h - 2 * t, mat_nome, cima=tuple(z))
    for s in (1, -1):
        off = z * (s * (h / 2 - t / 2))
        barra(m, a + off, c + off, b, t, mat_nome, cima=tuple(z))


def pilar_i(m, x, y, z0, z1, h, b, mat_nome, giro=0.0):
    """pilar em I vertical, alma ao longo de 'giro' (graus)."""
    g = math.radians(giro)
    viga_i(m, (x, y, z0), (x, y, z1), h, b, mat_nome, cima=(math.cos(g), math.sin(g), 0))


def trelica(m, p1, p2, altura, mat_nome, n=None, esp=0.08, cima=(0, 0, 1), larg=0.0):
    """treliça plana (Warren) de p1 a p2, banzo de baixo em p1-p2, banzo de cima 'altura' acima.
    larg > 0: treliça espacial (duas faces ligadas)."""
    a, b = Vector(p1), Vector(p2)
    d = b - a
    L = d.length
    x = d.normalized()
    up = Vector(cima)
    lado = up.cross(x).normalized()
    up = x.cross(lado).normalized()
    n = n or max(2, int(L / max(altura, 0.5)))
    faces = [Vector((0, 0, 0))] if larg <= 0 else [lado * (larg / 2), lado * (-larg / 2)]
    for o in faces:
        A, B = a + o, b + o
        barra(m, A, B, esp, esp, mat_nome)
        barra(m, A + up * altura, B + up * altura, esp, esp, mat_nome)
        for i in range(n + 1):
            p = A + x * (L * i / n)
            barra(m, p, p + up * altura, esp * 0.7, esp * 0.7, mat_nome)
            if i < n:
                q = A + x * (L * (i + 1) / n)
                if i % 2 == 0:
                    barra(m, p, q + up * altura, esp * 0.6, esp * 0.6, mat_nome)
                else:
                    barra(m, p + up * altura, q, esp * 0.6, esp * 0.6, mat_nome)
    if larg > 0:
        for i in range(n + 1):
            p = a + x * (L * i / n)
            barra(m, p + lado * (larg / 2), p - lado * (larg / 2), esp * 0.6, esp * 0.6, mat_nome)
            barra(m, p + lado * (larg / 2) + up * altura, p - lado * (larg / 2) + up * altura, esp * 0.6, esp * 0.6, mat_nome)


def guarda_corpo(m, pontos, mat_nome, alt=1.1, passo=1.5):
    for p, q in zip(pontos, pontos[1:]):
        P, Q = Vector(p), Vector(q)
        L = (Q - P).length
        n = max(1, int(L / passo))
        for i in range(n + 1):
            c = P + (Q - P) * (i / n)
            barra(m, c, c + Vector((0, 0, alt)), 0.045, 0.045, mat_nome)
        barra(m, P + Vector((0, 0, alt)), Q + Vector((0, 0, alt)), 0.05, 0.05, mat_nome)
        barra(m, P + Vector((0, 0, alt * 0.5)), Q + Vector((0, 0, alt * 0.5)), 0.035, 0.035, mat_nome)
        barra(m, P + Vector((0, 0, 0.08)), Q + Vector((0, 0, 0.08)), 0.15, 0.01, mat_nome)


def escada_marinheiro(m, base, alt, normal, mat_nome, gaiola=True):
    """escada vertical com gaiola. 'normal' = para onde a escada olha (fora da parede)."""
    b = Vector(base)
    nrm = Vector(normal).normalized()
    lado = Vector((0, 0, 1)).cross(nrm).normalized()
    for s in (-1, 1):
        barra(m, b + lado * 0.22 * s, b + lado * 0.22 * s + Vector((0, 0, alt)), 0.05, 0.05, mat_nome)
    k = 0.3
    while k < alt:
        barra(m, b + lado * -0.22 + Vector((0, 0, k)), b + lado * 0.22 + Vector((0, 0, k)), 0.03, 0.03, mat_nome)
        k += 0.3
    if gaiola and alt > 4:
        z = 2.5
        while z < alt:
            pts = []
            for i in range(9):
                a = math.pi * i / 8
                pts.append(b + lado * (math.cos(a) * 0.38) + nrm * (0.38 + math.sin(a) * 0.38) + Vector((0, 0, z)))
            for p, q in zip(pts, pts[1:]):
                barra(m, p, q, 0.03, 0.05, mat_nome)
            z += 1.2
        for i in range(5):
            a = math.pi * i / 4
            o = lado * (math.cos(a) * 0.38) + nrm * (0.38 + math.sin(a) * 0.38)
            barra(m, b + o + Vector((0, 0, 2.5)), b + o + Vector((0, 0, alt)), 0.03, 0.03, mat_nome)


def anel_plataforma(m, c, r_in, r_out, z, piso, grade, lados=36):
    """plataforma em anel (piso de chapa) com guarda-corpo na borda de fora."""
    bm = m.bm
    vi, vo, vi2, vo2 = [], [], [], []
    for i in range(lados):
        a = 2 * math.pi * i / lados
        ca, sa = math.cos(a), math.sin(a)
        vi.append(bm.verts.new((c[0] + ca * r_in, c[1] + sa * r_in, z)))
        vo.append(bm.verts.new((c[0] + ca * r_out, c[1] + sa * r_out, z)))
        vi2.append(bm.verts.new((c[0] + ca * r_in, c[1] + sa * r_in, z - 0.12)))
        vo2.append(bm.verts.new((c[0] + ca * r_out, c[1] + sa * r_out, z - 0.12)))
    k = m.mi(piso)
    for i in range(lados):
        j = (i + 1) % lados
        for quad in ((vi[i], vo[i], vo[j], vi[j]), (vi2[j], vo2[j], vo2[i], vi2[i]),
                     (vo[i], vo2[i], vo2[j], vo[j]), (vi[j], vi2[j], vi2[i], vi[i])):
            f = bm.faces.new(quad)
            f.material_index = k
    pts = [(c[0] + math.cos(2 * math.pi * i / lados) * (r_out - 0.05), c[1] + math.sin(2 * math.pi * i / lados) * (r_out - 0.05), z)
           for i in range(lados + 1)]
    guarda_corpo(m, pts, grade, passo=1.8)
    # mãos-francesas embaixo
    for i in range(0, lados, 3):
        a = 2 * math.pi * i / lados
        p = Vector((c[0] + math.cos(a) * r_in, c[1] + math.sin(a) * r_in, z - 1.4))
        q = Vector((c[0] + math.cos(a) * r_out, c[1] + math.sin(a) * r_out, z - 0.12))
        barra(m, p, q, 0.08, 0.08, grade)
        barra(m, Vector((p.x, p.y, z - 0.12)), q, 0.1, 0.12, grade)


def chapa_ondulada(m, origem, u, v, largura, altura, mat_nome, periodo=0.2, amp=0.035, normal=None):
    """chapa ondulada: ondas ao longo de u. origem = canto, u e v unitários."""
    O, U, V = Vector(origem), Vector(u).normalized(), Vector(v).normalized()
    N = Vector(normal).normalized() if normal else U.cross(V).normalized()
    bm = m.bm
    nu = max(2, int(largura / (periodo / 4)))
    linha_a, linha_b = [], []
    for i in range(nu + 1):
        s = largura * i / nu
        o = N * (amp * math.sin(2 * math.pi * s / periodo))
        linha_a.append(bm.verts.new(O + U * s + o))
        linha_b.append(bm.verts.new(O + U * s + V * altura + o))
    k = m.mi(mat_nome)
    # lado de trás: mesma onda, 4 mm atrás, faces ao contrário (a chapa aparece dos dois lados)
    tras_a = [bm.verts.new(v.co - N * 0.004) for v in linha_a]
    tras_b = [bm.verts.new(v.co - N * 0.004) for v in linha_b]
    for i in range(nu):
        f = bm.faces.new((linha_a[i], linha_a[i + 1], linha_b[i + 1], linha_b[i]))
        f.material_index = k
        f.smooth = True
        f = bm.faces.new((tras_b[i], tras_b[i + 1], tras_a[i + 1], tras_a[i]))
        f.material_index = k
        f.smooth = True


# ----------------------------------------------------------------------------- terreno
def altura_terreno(x, y):
    r = max(abs(x) / 175.0, abs(y) / 125.0)
    if r < 1.0:
        return 0.0
    t = min(1.0, (r - 1.0) / 1.4)
    ond = 4.0 * math.sin(x * 0.011 + 1.3) * math.cos(y * 0.013) + 2.5 * math.sin(x * 0.027 + y * 0.019)
    return (t * t) * (8.0 + ond)


def terreno():
    m = Malha()
    bm = m.bm
    k = m.mi("TERRENO")
    col = bm.loops.layers.color.new("Col")
    xs = []
    x = -350.0
    while x <= 350.01:
        xs.append(x)
        x += 4.0 if abs(x) < 190 else 10.0
    ys = []
    y = -350.0
    while y <= 350.01:
        ys.append(y)
        y += 4.0 if abs(y) < 140 else 10.0
    grade = [[bm.verts.new((x, y, altura_terreno(x, y))) for x in xs] for y in ys]

    def cor(x, y):
        # R = asfalto (vias e pátios), G = fuligem/minério escuro, B = terra
        r = 0.0
        if abs(y + 35) < 6 or abs(y - 30) < 5 or abs(x + 75) < 6 or abs(x - 70) < 5:
            r = 1.0
        if -64 < x < 64 and -18 < y < 18:
            r = 0.0
        if -112 < x < -78 and -74 < y < -44:
            r = 1.0
        g = 0.0
        for (cx, cy, rr) in ((40, -70, 22), (95, 10, 20), (0, 55, 12), (-20, 0, 25), (30, -36, 10)):
            dd = math.hypot(x - cx, y - cy) / rr
            g = max(g, max(0.0, 1.0 - dd) ** 1.5)
        b = 0.5 + 0.5 * math.sin(x * 0.05 + 0.7) * math.sin(y * 0.043 + 1.9) + 0.25 * math.sin(x * 0.13 + y * 0.11)
        b = max(0.0, min(1.0, (b - 0.42) * 1.8))
        if max(abs(x) / 175.0, abs(y) / 125.0) > 1.05:
            b = 1.0
        return (r, g * 0.85, b, 1.0)

    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            f = bm.faces.new((grade[j][i], grade[j][i + 1], grade[j + 1][i + 1], grade[j + 1][i]))
            f.material_index = k
            for lp in f.loops:
                lp[col] = cor(lp.vert.co.x, lp.vert.co.y)
    finalizar("Terreno", m, {0: 4.0}, recalc=False)


# ----------------------------------------------------------------------------- aciaria (galpão)
AX0, AX1, AY0, AY1 = -60.0, 60.0, -16.0, 16.0
BEIRAL, CUMEEIRA = 22.0, 26.0
TRILHO_Z = 16.5
PORTAS_FIM = (-6.0, 6.0, 15.0)      # porta grande nas cabeceiras (y0, y1, altura)


def aciaria():
    m = Malha()
    ACO, CHP, PISO = "ACO_FERRUGEM", "CHAPA_PISO", "PISO"
    # piso de concreto
    caixa(m, (0, 0, 0.1), (AX1 - AX0 + 2, AY1 - AY0 + 2, 0.2), PISO)
    # pilares a cada 10 m dos dois lados + consoles das vigas de rolamento
    for i in range(13):
        x = AX0 + i * 10.0
        for y, s in ((AY0, 1), (AY1, -1)):
            pilar_i(m, x, y, 0.2, BEIRAL, 0.9, 0.5, ACO, giro=90)
            caixa(m, (x, y, 0.45), (1.3, 1.3, 0.5), "CONCRETO")
            caixa(m, (x, y + s * 0.85, TRILHO_Z - 0.6), (0.5, 1.2, 0.6), ACO)       # console
            barra(m, (x, y, TRILHO_Z - 2.6), (x, y + s * 1.3, TRILHO_Z - 0.9), 0.25, 0.25, ACO)
    # vigas de rolamento (I) + trilho
    for y in (AY0 + 1.0, AY1 - 1.0):
        viga_i(m, (AX0, y, TRILHO_Z - 0.6), (AX1, y, TRILHO_Z - 0.6), 1.2, 0.5, ACO)
        barra(m, (AX0, y, TRILHO_Z + 0.08), (AX1, y, TRILHO_Z + 0.08), 0.12, 0.16, "TRILHO")
    # vigas longitudinais do beiral
    for y in (AY0, AY1):
        viga_i(m, (AX0, y, BEIRAL), (AX1, y, BEIRAL), 0.7, 0.3, ACO)
        viga_i(m, (AX0, y, 9.0), (AX1, y, 9.0), 0.4, 0.2, ACO)
        # contraventamento em X nos vãos das pontas
        for x0 in (AX0, AX1 - 10, -10.0):
            barra(m, (x0, y, 9.0), (x0 + 10, y, BEIRAL), 0.12, 0.12, ACO)
            barra(m, (x0 + 10, y, 9.0), (x0, y, BEIRAL), 0.12, 0.12, ACO)
    # treliças do telhado (duas águas) a cada 10 m + terças
    for i in range(13):
        x = AX0 + i * 10.0
        meio = (AY0 + AY1) / 2
        for ya, yb in ((AY0, meio), (AY1, meio)):
            pa, pb = Vector((x, ya, BEIRAL)), Vector((x, yb, CUMEEIRA))
            barra(m, pa, pb, 0.18, 0.25, ACO)                          # banzo de cima
            barra(m, (x, ya, BEIRAL - 2.2), (x, yb, BEIRAL - 2.2), 0.15, 0.2, ACO)  # banzo de baixo
            n = 8
            for k in range(n + 1):
                t = k / n
                pc = pa.lerp(pb, t)
                pd = Vector((x, ya + (yb - ya) * t, BEIRAL - 2.2))
                barra(m, pd, pc, 0.08, 0.08, ACO)
                if k < n:
                    t2 = (k + 1) / n
                    pc2 = pa.lerp(pb, t2)
                    barra(m, pd if k % 2 == 0 else pc, pc2 if k % 2 == 0 else Vector((x, ya + (yb - ya) * t2, BEIRAL - 2.2)), 0.07, 0.07, ACO)
    for k in range(9):
        t = k / 8
        for ya in (AY0, AY1):
            yy = ya + ((AY0 + AY1) / 2 - ya) * t
            zz = BEIRAL + (CUMEEIRA - BEIRAL) * t + 0.2
            barra(m, (AX0, yy, zz), (AX1, yy, zz), 0.12, 0.2, ACO)
    # lanternim (respiro em cima da cumeeira)
    for i in range(13):
        x = AX0 + i * 10.0
        for s in (-1, 1):
            barra(m, (x, s * 2.5, CUMEEIRA - 0.3), (x, s * 2.5, CUMEEIRA + 1.8), 0.12, 0.12, ACO)
    # passarela ao longo da parede sul (z = 8) com guarda-corpo e escada
    PZ = 8.0
    caixa(m, (0, AY0 + 1.2, PZ - 0.05), (AX1 - AX0 - 4, 1.6, 0.1), CHP)
    for i in range(12):
        x = AX0 + 5 + i * 10.0
        barra(m, (x, AY0, PZ - 1.4), (x, AY0 + 1.9, PZ - 0.1), 0.1, 0.1, ACO)
    guarda_corpo(m, [(AX0 + 2, AY0 + 2.0, PZ), (AX1 - 2, AY0 + 2.0, PZ)], "GUARDA_CORPO")
    # escada de 45° até a passarela (perto da porta oeste)
    ex0, ex1 = AX0 + 4.0, AX0 + 4.0 + PZ
    for k in range(int(PZ / 0.2)):
        z = k * 0.2 + 0.2
        x = ex0 + (ex1 - ex0) * (z / PZ)
        caixa(m, (x, AY0 + 3.2, z), (0.28, 1.0, 0.04), CHP)
    for s in (-0.55, 0.55):
        barra(m, (ex0, AY0 + 3.2 + s, 0.2), (ex1, AY0 + 3.2 + s, PZ), 0.06, 0.25, ACO)
    guarda_corpo(m, [(ex0, AY0 + 3.8, 0.2), (ex1, AY0 + 3.8, PZ)], "GUARDA_CORPO", passo=1.2)
    # cabine de comando sobre pernas, no meio do lado norte
    cx, cy, cz = 5.0, AY1 - 4.0, 6.0
    for dx in (-2, 2):
        for dy in (-1.5, 1.5):
            pilar_i(m, cx + dx, cy + dy, 0.2, cz, 0.3, 0.2, ACO)
    caixa(m, (cx, cy, cz + 0.1), (4.6, 3.4, 0.2), CHP)
    caixa(m, (cx, cy + 1.6, cz + 1.4), (4.4, 0.12, 2.6), "CHAPA_PINTADA")
    for dx in (-2.2, 2.2):
        caixa(m, (cx + dx, cy, cz + 0.6), (0.12, 3.2, 1.2), "CHAPA_PINTADA")
    caixa(m, (cx, cy - 1.6, cz + 0.6), (4.4, 0.12, 1.0), "CHAPA_PINTADA")
    for dx in (-2.2, 2.2):
        for dy in (-1.6, 1.6):
            caixa(m, (cx + dx, cy + dy, cz + 1.4), (0.12, 0.12, 2.6), "CHAPA_PINTADA")
    caixa(m, (cx, cy, cz + 2.8), (4.8, 3.6, 0.18), "CHAPA_PINTADA")
    caixa(m, (cx - 1.5, cy + 1.0, cz + 0.65), (1.2, 0.7, 0.9), "CHAPA_PINTADA")   # painel de comando
    caixa(m, (cx, cy - 1.62, cz + 1.75), (4.2, 0.03, 1.3), "VIDRO_SUJO")
    for k in range(int(cz / 0.25)):
        z = k * 0.25 + 0.25
        caixa(m, (cx + 3.0 + z * 0.75, cy - 0.5, z), (0.26, 0.9, 0.04), CHP)
    # fundações das paredes (mureta de concreto)
    for y in (AY0, AY1):
        caixa(m, (0, y, 1.2), (AX1 - AX0, 0.3, 2.4), "CONCRETO")
    for x in (AX0, AX1):
        for (ya, yb) in ((AY0, PORTAS_FIM[0]), (PORTAS_FIM[1], AY1)):
            caixa(m, (x, (ya + yb) / 2, 1.2), (0.3, yb - ya, 2.4), "CONCRETO")
    # oitões (frontões) das cabeceiras: estrutura
    for x in (AX0, AX1):
        for y in (-11.0, -6.0, 6.0, 11.0):
            z1 = BEIRAL + (CUMEEIRA - BEIRAL) * (1 - abs(y) / 16)
            pilar_i(m, x, y, 0.2, z1, 0.4, 0.25, ACO, giro=0)
        viga_i(m, (x, -6.5, PORTAS_FIM[2]), (x, 6.5, PORTAS_FIM[2]), 0.8, 0.35, ACO, cima=(0, 0, 1))
    finalizar("Aciaria", m, {m.mi("PISO"): 4.0, m.mi("CONCRETO"): 3.0})


def chapas():
    """paredes e telhado de chapa ondulada, com painéis faltando, tortos e pendurados."""
    m = Malha()
    rnd = random.Random(42)
    CH = "CHAPA_ONDULADA"
    PW = 1.0     # largura do painel
    buracos = []

    def parede(ponto_a, ponto_b, z0, z_topo_fn, normal, falta=0.22):
        A, B = Vector(ponto_a), Vector(ponto_b)
        L = (B - A).length
        U = (B - A).normalized()
        n = int(L / PW)
        for i in range(n):
            s0 = i * PW
            meio = A + U * (s0 + PW / 2)
            z1 = z_topo_fn(meio)
            if z1 - z0 < 0.5:
                continue
            # faixas de 3 m de altura; cada faixa pode faltar
            z = z0
            while z < z1 - 0.01:
                h = min(3.0, z1 - z)
                r = rnd.random()
                if r < falta:
                    buracos.append(tuple(meio))
                elif r < falta + 0.04:
                    # painel solto, torto
                    O = A + U * s0 + Vector((0, 0, z)) + Vector(normal) * 0.25
                    giro = Matrix.Rotation(math.radians(rnd.uniform(-25, 25)), 3, Vector(normal))
                    chapa_ondulada(m, O, giro @ U, giro @ Vector((0, 0, 1)), PW, h, CH, normal=normal)
                else:
                    O = A + U * s0 + Vector((0, 0, z)) + Vector(normal) * 0.05
                    chapa_ondulada(m, O, U, (0, 0, 1), PW + 0.02, h + 0.05, CH, normal=normal)
                z += 3.0

    def topo_lado(p):
        return BEIRAL

    def topo_oitao(p):
        return BEIRAL + (CUMEEIRA - BEIRAL) * (1 - abs(p.y) / 16)

    parede((AX0, AY0 - 0.3, 0), (AX1, AY0 - 0.3, 0), 2.4, topo_lado, (0, -1, 0), 0.24)
    parede((AX0, AY1 + 0.3, 0), (AX1, AY1 + 0.3, 0), 2.4, topo_lado, (0, 1, 0), 0.18)
    for x, nx in ((AX0 - 0.3, -1), (AX1 + 0.3, 1)):
        parede((x, AY0, 0), (x, PORTAS_FIM[0], 0), 2.4, topo_oitao, (nx, 0, 0), 0.2)
        parede((x, PORTAS_FIM[1], 0), (x, AY1, 0), 2.4, topo_oitao, (nx, 0, 0), 0.2)
        parede((x, PORTAS_FIM[0], 0), (x, PORTAS_FIM[1], 0), PORTAS_FIM[2] + 0.4, topo_oitao, (nx, 0, 0), 0.15)
    # telhado: painéis de 1 m ao longo de x, da beira à cumeeira, faltando bastante (feixes de luz)
    meio = (AY0 + AY1) / 2
    for ya, sgn in ((AY0 - 0.6, -1), (AY1 + 0.6, 1)):
        p0 = Vector((0, ya, BEIRAL - 0.15))
        p1 = Vector((0, meio, CUMEEIRA + 0.35))
        V = (p1 - p0)
        Lv = V.length
        V.normalize()
        nrm = Vector((0, sgn * (CUMEEIRA - BEIRAL) / Lv, 1)).normalized()
        x = AX0 - 0.6
        while x < AX1 + 0.6:
            s = 0.0
            while s < Lv - 0.01:
                h = min(4.0, Lv - s)
                buraco = rnd.random() < 0.20 or (abs(x + 30) < 6 and rnd.random() < 0.7) or (abs(x - 25) < 4 and rnd.random() < 0.6)
                if not buraco:
                    O = Vector((x, p0.y, p0.z)) + V * s + nrm * 0.25
                    chapa_ondulada(m, O, (1, 0, 0), V, PW + 0.02, h + 0.05, CH, normal=nrm)
                s += 4.0
            x += PW
    # lanternim: telhadinho em cima
    for s in (-1, 1):
        chapa_ondulada(m, (AX0, s * 0.2, CUMEEIRA + 1.8), (1, 0, 0), (0, s, -0.25), AX1 - AX0, 3.0, CH,
                       normal=(0, s * 0.25, 1))
    finalizar("Chapas", m, {0: 2.0}, recalc=False)


def pontes_rolantes():
    m = Malha()
    AM = "PINTURA_AMARELA"
    for px, carro_y, gancho_z in ((-25.0, 4.0, 6.5), (20.0, -6.0, 11.0)):
        # duas vigas-caixão de um trilho ao outro
        for dx in (-1.1, 1.1):
            caixa(m, (px + dx, 0, TRILHO_Z + 1.3), (0.7, AY1 - AY0 - 1.0, 1.8), AM)
            # nervuras laterais
            for k in range(-14, 15, 2):
                caixa(m, (px + dx + 0.36, k, TRILHO_Z + 1.3), (0.04, 0.1, 1.7), AM)
        # cabeceiras com rodas
        for y in (AY0 + 1.0, AY1 - 1.0):
            caixa(m, (px, y, TRILHO_Z + 0.75), (5.0, 1.2, 0.9), AM)
            for dx in (-1.9, 1.9):
                cilindro(m, (px + dx, y - 0.2, TRILHO_Z + 0.4), 0.35, 0.35, 0.4, "ACO_FERRUGEM", lados=16, eixo=(0, 1, 0))
        # passadiço e guarda-corpo
        caixa(m, (px + 1.9, 0, TRILHO_Z + 2.25), (0.9, AY1 - AY0 - 2.0, 0.06), "CHAPA_PISO")
        guarda_corpo(m, [(px + 2.35, AY0 + 1.5, TRILHO_Z + 2.25), (px + 2.35, AY1 - 1.5, TRILHO_Z + 2.25)], "GUARDA_CORPO", alt=1.0)
        # carro (trolley) com tambor
        cz = TRILHO_Z + 2.6
        caixa(m, (px, carro_y, cz), (3.4, 3.0, 0.7), AM)
        cilindro(m, (px - 1.3, carro_y, cz + 0.85), 0.6, 0.6, 2.6, "ACO_FERRUGEM", lados=20, eixo=(1, 0, 0))
        caixa(m, (px + 1.0, carro_y + 0.8, cz + 0.7), (1.0, 0.8, 0.8), "ACO_FERRUGEM")   # motor
        # cabine do operador pendurada
        cab = (px + 1.5, AY1 - 3.5, TRILHO_Z - 1.2)
        caixa(m, cab, (2.0, 2.0, 2.2), "CHAPA_PINTADA")
        caixa(m, (cab[0] - 1.01, cab[1], cab[2] + 0.2), (0.03, 1.6, 1.0), "VIDRO_SUJO")
        barra(m, (cab[0], cab[1], cab[2] + 1.1), (cab[0], cab[1], TRILHO_Z + 0.5), 0.2, 0.2, AM)
        # cabos e moitão + gancho
        for dy in (-0.4, 0.4):
            tubo(m, (px - 0.4, carro_y + dy, cz - 0.3), (px - 0.4, carro_y + dy, gancho_z + 1.6), 0.03, "CABO", lados=6)
        caixa(m, (px - 0.4, carro_y, gancho_z + 1.3), (0.6, 1.2, 0.8), AM)
        gx, gy, gz = px - 0.4, carro_y, gancho_z
        pts = []
        for i in range(15):
            a = math.radians(-40 + i * 260 / 14)
            pts.append((gx + math.sin(a) * 0.45, gy, gz + 0.3 - math.cos(a) * 0.45))
        for a0, a1 in zip(pts, pts[1:]):
            tubo(m, a0, a1, 0.1, "ACO_FERRUGEM", lados=8)
        tubo(m, (gx, gy, gz + 0.9), (gx, gy, gz + 0.3), 0.12, "ACO_FERRUGEM")
        # correntes penduradas no gancho (elos)
        if px > 0:
            for k in range(14):
                z = gz - 0.3 - k * 0.22
                g = 90 if k % 2 else 0
                caixa(m, (gx, gy, z), (0.05 if g else 0.16, 0.16 if g else 0.05, 0.24), "CABO")
    finalizar("Pontes", m, {})
    LAYOUT["pontes"] = [{"x": -25.0, "y": 4.0}, {"x": 20.0, "y": -6.0}]


def conversor():
    """conversor tombado, panelas de aço, lingoteiras, esteira de rolos."""
    m = Malha()
    F = "FERRUGEM_PESADA"
    cx, cy = -10.0, 6.0
    # base de concreto e munhões
    caixa(m, (cx, cy, 1.0), (10, 3, 2.0), "CONCRETO")
    for dy in (-4.0, 4.0):
        caixa(m, (cx, cy + dy, 3.0), (2.0, 1.2, 6.0), "CONCRETO")
        cilindro(m, (cx, cy + dy * 0.8, 5.0), 0.7, 0.7, 2.4, "ACO_FERRUGEM", lados=24, eixo=(0, -1 if dy > 0 else 1, 0))
    # vaso (tombado 35°)
    R = 3.4
    eixo = Vector((math.sin(math.radians(35)), 0, math.cos(math.radians(35))))
    base = Vector((cx, cy, 5.0)) - eixo * 3.0
    cilindro(m, tuple(base), R * 0.8, R, 1.6, F, lados=32, eixo=tuple(eixo))
    cilindro(m, tuple(base + eixo * 1.6), R, R, 3.2, F, lados=32, eixo=tuple(eixo))
    cilindro(m, tuple(base + eixo * 4.8), R, 1.5, 2.0, F, lados=32, eixo=tuple(eixo), tampas=False)
    cilindro(m, tuple(base + eixo * 6.8), 1.5, 1.5, 0.4, "ESCORIA", lados=24, eixo=tuple(eixo))
    cilindro(m, tuple(base + eixo * 3.2), R + 0.15, R + 0.15, 1.0, "ACO_FERRUGEM", lados=32, eixo=tuple(eixo))  # anel
    # panelas de aço (uma tombada)
    for (px, py, tomb) in ((-28.0, -8.0, 0), (-34.0, 8.5, 70), (34.0, 8.0, 0)):
        e = (math.sin(math.radians(tomb)), 0, math.cos(math.radians(tomb)))
        b = Vector((px, py, 0.2 + (1.8 if tomb else 0)))
        cilindro(m, tuple(b), 1.9, 2.3, 3.6, F, lados=28, eixo=e)
        cilindro(m, tuple(b + Vector(e) * 3.4), 2.4, 2.4, 0.3, "ACO_FERRUGEM", lados=28, eixo=e)
        cilindro(m, tuple(b + Vector(e) * 3.3), 2.15, 2.15, 0.12, "ESCORIA", lados=28, eixo=e)
        for s in (-1, 1):
            cilindro(m, (px, py + s * 2.4, b.z + 2.6), 0.35, 0.35, 0.5, "ACO_FERRUGEM", lados=12, eixo=(0, s, 0))
    # lingoteiras em fila
    for i in range(8):
        caixa(m, (14.0 + i * 1.6, 10.5, 0.9), (1.2, 1.2, 1.4), F)
        caixa(m, (14.0 + i * 1.6, 10.5, 1.62), (0.9, 0.9, 0.06), "ESCORIA")
    # mesa de rolos (laminação) ao longo do galpão
    for i in range(40):
        x = 8.0 + i * 1.2
        cilindro(m, (x, -12.0, 1.0), 0.22, 0.22, 2.2, "ACO_FERRUGEM", lados=12, eixo=(0, 1, 0))
    for y in (-13.2, -10.8):
        caixa(m, (32.0, y, 0.7), (49.0, 0.25, 1.0), F)
    for i in range(10):
        caixa(m, (8.5 + i * 5.0, -12.0, 0.35), (0.3, 2.8, 0.5), "CONCRETO")
    # placa de aço esquecida sobre os rolos
    caixa(m, (22.0, -12.0, 1.3), (6.0, 1.8, 0.2), "ESCORIA")
    finalizar("Conversor", m, {m.mi("CONCRETO"): 3.0})


# ----------------------------------------------------------------------------- alto-forno
AF = (95.0, 10.0)


def alto_forno():
    m = Malha()
    F, T = "FERRUGEM_PESADA", "TIJOLO"
    cx, cy = AF
    # base / cadinho de concreto e tijolo
    cilindro(m, (cx, cy, 0), 9.0, 9.0, 3.0, "CONCRETO", lados=32)
    cilindro(m, (cx, cy, 3.0), 7.0, 7.4, 6.0, T, lados=32)
    # rampa (bosh) e cuba
    perfil = [(9.0, 7.4), (11.0, 8.2), (14.0, 8.2), (30.0, 6.0), (34.0, 4.5), (37.0, 2.8)]
    for (z0, r0), (z1, r1) in zip(perfil, perfil[1:]):
        cilindro(m, (cx, cy, z0), r0, r1, z1 - z0, F, lados=40, tampas=False)
    cilindro(m, (cx, cy, 37.0), 2.8, 2.8, 0.3, F, lados=32)
    # cintas (anéis de aço)
    for z in range(12, 34, 3):
        r = 8.2 if z < 14 else 8.2 - (z - 14) * (2.2 / 16)
        cilindro(m, (cx, cy, z), r + 0.12, r + 0.12, 0.35, "ACO_FERRUGEM", lados=40)
    # algaravizes (ventaneiras) em volta da base + anel de ar quente
    anel_z = 10.5
    for i in range(16):
        a = 2 * math.pi * i / 16
        p = (cx + math.cos(a) * 7.2, cy + math.sin(a) * 7.2, anel_z - 1.0)
        q = (cx + math.cos(a) * 9.8, cy + math.sin(a) * 9.8, anel_z)
        tubo(m, p, q, 0.25, "ACO_FERRUGEM", lados=10)
        cilindro(m, p, 0.32, 0.32, 0.25, "BRASA", lados=10, eixo=(math.cos(a), math.sin(a), -0.35))
    pts = [(cx + math.cos(2 * math.pi * i / 40) * 10.0, cy + math.sin(2 * math.pi * i / 40) * 10.0, anel_z) for i in range(41)]
    for p, q in zip(pts, pts[1:]):
        tubo(m, p, q, 0.75, F, lados=14)
    # plataformas em anel (missões / fotos)
    anel_plataforma(m, AF, 8.3, 11.5, 12.0, "CHAPA_PISO", "GUARDA_CORPO")
    anel_plataforma(m, AF, 6.7, 9.5, 24.0, "CHAPA_PISO", "GUARDA_CORPO")
    anel_plataforma(m, AF, 4.6, 7.0, 34.0, "CHAPA_PISO", "GUARDA_CORPO")
    # pilares que seguram as plataformas e o topo (estrutura em volta)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        x, y = cx + math.cos(a) * 12.5, cy + math.sin(a) * 12.5
        pilar_i(m, x, y, 0, 44.0, 0.8, 0.5, "ACO_FERRUGEM")
        for z in (12.0, 24.0, 34.0):
            barra(m, (x, y, z - 0.2), (cx + math.cos(a) * 9.0, cy + math.sin(a) * 9.0, z - 0.2), 0.3, 0.4, "ACO_FERRUGEM")
        j = math.radians(45 + 90 * (i + 1))
        x2, y2 = cx + math.cos(j) * 12.5, cy + math.sin(j) * 12.5
        for z in (12.0, 24.0, 34.0, 44.0):
            viga_i(m, (x, y, z), (x2, y2, z), 0.6, 0.3, "ACO_FERRUGEM")
        barra(m, (x, y, 12.0), (x2, y2, 24.0), 0.15, 0.15, "ACO_FERRUGEM")
        barra(m, (x, y, 24.0), (x2, y2, 34.0), 0.15, 0.15, "ACO_FERRUGEM")
    # topo: tremonha e quatro tubos de gás descendo (downcomers) até o coletor de pó
    caixa(m, (cx, cy, 44.4), (18, 18, 0.4), "CHAPA_PISO")
    cilindro(m, (cx, cy, 37.3), 2.2, 3.4, 4.0, F, lados=24)
    for i in range(4):
        a = math.radians(i * 90)
        tubo(m, (cx + math.cos(a) * 2.0, cy + math.sin(a) * 2.0, 38.0), (cx + math.cos(a) * 2.6, cy + math.sin(a) * 2.6, 50.0), 0.8, F, lados=16)
    for i in range(4):
        a = math.radians(i * 90)
        tubo(m, (cx + math.cos(a) * 2.6, cy + math.sin(a) * 2.6, 50.0), (cx, cy, 52.0), 0.8, F, lados=16)
    cilindro(m, (cx, cy, 51.5), 1.2, 1.2, 2.5, F, lados=20)
    # downcomer grande até o coletor de pó (a leste)
    dc = (cx + 26.0, cy - 12.0)
    tubo(m, (cx, cy, 53.5), (dc[0], dc[1], 30.0), 1.3, F, lados=20)
    cilindro(m, (dc[0], dc[1], 8.0), 5.0, 5.0, 14.0, F, lados=28)
    cilindro(m, (dc[0], dc[1], 22.0), 5.0, 1.4, 6.0, F, lados=28)
    cilindro(m, (dc[0], dc[1], 3.0), 1.5, 5.0, 5.0, F, lados=28)
    for i in range(4):
        a = math.radians(45 + 90 * i)
        pilar_i(m, dc[0] + math.cos(a) * 4.6, dc[1] + math.sin(a) * 4.6, 0, 22.0, 0.6, 0.4, "ACO_FERRUGEM")
    # casa de corrida (galpão baixo encostado no forno) com a brasa da bica
    hx0, hx1, hy0, hy1 = cx - 24.0, cx - 8.0, cy - 9.0, cy + 9.0
    caixa(m, ((hx0 + hx1) / 2, (hy0 + hy1) / 2, 3.0), (hx1 - hx0, hy1 - hy0, 0.4), "CONCRETO")
    for x in (hx0, hx0 + 8, hx1):
        for y in (hy0, hy1):
            pilar_i(m, x, y, 0, 12.0, 0.5, 0.3, "ACO_FERRUGEM")
        barra(m, (x, hy0, 12.0), (x, hy1, 12.0), 0.3, 0.5, "ACO_FERRUGEM")
    for y in (hy0, hy1):
        barra(m, (hx0, y, 12.0), (hx1, y, 12.0), 0.3, 0.5, "ACO_FERRUGEM")
    # telhado da casa de corrida (metade faltando)
    for k in range(10):
        if k in (3, 4, 7):
            continue
        chapa_ondulada(m, (hx0, hy0 + k * 1.8, 12.4), (1, 0, 0), (0, 1, 0), hx1 - hx0, 1.85, "CHAPA_ONDULADA", normal=(0, 0, 1))
    # canal de gusa (bica) com brasa
    caixa(m, (cx - 10.0, cy, 3.4), (6.0, 1.2, 0.4), "TIJOLO")
    caixa(m, (cx - 10.0, cy, 3.62), (5.6, 0.6, 0.04), "BRASA")
    caixa(m, (cx - 7.3, cy, 4.2), (0.8, 1.4, 1.6), "TIJOLO")
    # escada em zigue-zague até a primeira plataforma
    for k in range(4):
        z0 = k * 3.0
        y0 = cy - 13.5
        x0 = cx - 4.0 + (k % 2) * 6.0
        x1 = cx + 2.0 - (k % 2) * 6.0
        for s in range(15):
            t = s / 15
            caixa(m, (x0 + (x1 - x0) * t, y0, z0 + 3.0 * t + 0.1), (0.3, 1.1, 0.04), "CHAPA_PISO")
        barra(m, (x0, y0 - 0.6, z0), (x1, y0 - 0.6, z0 + 3.0), 0.05, 0.2, "ACO_FERRUGEM")
        barra(m, (x0, y0 + 0.6, z0), (x1, y0 + 0.6, z0 + 3.0), 0.05, 0.2, "ACO_FERRUGEM")
        caixa(m, (x1, y0, z0 + 3.0), (1.4, 1.4, 0.08), "CHAPA_PISO")
        pilar_i(m, x1, y0, 0, z0 + 3.0, 0.2, 0.15, "ACO_FERRUGEM")
    escada_marinheiro(m, (cx, cy - 9.5, 12.0), 12.0, (0, -1, 0), "GUARDA_CORPO")
    escada_marinheiro(m, (cx, cy - 7.0, 24.0), 10.0, (0, -1, 0), "GUARDA_CORPO")
    finalizar("AltoForno", m, {m.mi("TIJOLO"): 2.0, m.mi("CONCRETO"): 3.0})
    LAYOUT["luzes"].append({"x": cx - 10.0, "y": cy, "z": 4.6, "intensidade": 9000.0, "raio": 1800.0, "cor": [255, 120, 40]})
    LAYOUT["luzes"].append({"x": cx - 7.5, "y": cy, "z": 9.6, "intensidade": 4000.0, "raio": 1400.0, "cor": [255, 110, 35]})


REG = [(120.0, 34.0), (132.0, 34.0), (144.0, 34.0)]


def regeneradores():
    m = Malha()
    for (x, y) in REG:
        cilindro(m, (x, y, 0), 5.0, 5.0, 1.0, "CONCRETO", lados=32)
        cilindro(m, (x, y, 1.0), 4.5, 4.5, 26.0, "FERRUGEM_PESADA", lados=36, tampas=False)
        for z in range(3, 27, 4):
            cilindro(m, (x, y, z), 4.62, 4.62, 0.3, "ACO_FERRUGEM", lados=36)
        # cúpula
        n = 6
        for k in range(n):
            a0, a1 = math.pi / 2 * k / n, math.pi / 2 * (k + 1) / n
            r0, r1 = 4.5 * math.cos(a0), 4.5 * math.cos(a1)
            z0, z1 = 27 + 4.5 * math.sin(a0), 27 + 4.5 * math.sin(a1)
            cilindro(m, (x, y, z0), r0, max(0.05, r1), z1 - z0, "FERRUGEM_PESADA", lados=36, tampas=(k == n - 1))
        anel_plataforma(m, (x, y), 4.6, 6.4, 14.0, "CHAPA_PISO", "GUARDA_CORPO", lados=28)
        escada_marinheiro(m, (x, y - 4.6, 0.0), 14.0, (0, -1, 0), "GUARDA_CORPO")
        # ligação ao tubo principal
        tubo(m, (x, y - 4.5, 6.0), (x, y - 9.0, 6.0), 0.9, "FERRUGEM_PESADA", lados=16)
        # pequena chaminé ao lado de cada um
        tubo(m, (x + 4.0, y + 4.0, 0), (x + 4.0, y + 4.0, 34.0), 0.6, "ACO_FERRUGEM", lados=14)
    # tubo de ar quente até o anel do forno
    tubo(m, (REG[0][0] - 6, REG[0][1] - 9.0, 6.0), (REG[-1][0] + 4, REG[-1][1] - 9.0, 6.0), 1.2, "FERRUGEM_PESADA", lados=20)
    tubo(m, (REG[0][0] - 6, REG[0][1] - 9.0, 6.0), (AF[0] + 10.0, AF[1] + 2.0, 10.5), 1.2, "FERRUGEM_PESADA", lados=20)
    for x in range(int(REG[0][0] - 4), int(REG[-1][0] + 4), 6):
        barra(m, (x, REG[0][1] - 9.0, 0), (x, REG[0][1] - 9.0, 5.0), 0.4, 0.4, "ACO_FERRUGEM")
        barra(m, (x - 1.2, REG[0][1] - 9.0, 4.9), (x + 1.2, REG[0][1] - 9.0, 4.9), 0.3, 0.3, "ACO_FERRUGEM")
    finalizar("Regeneradores", m, {m.mi("CONCRETO"): 3.0})


def esteira():
    """galeria em treliça (ponte da esteira) subindo do pátio de minério até o topo do forno."""
    m = Malha()
    A = Vector((55.0, -62.0, 4.0))
    B = Vector((AF[0] - 3.0, AF[1] - 6.0, 40.0))
    d = B - A
    L = d.length
    x = d.normalized()
    lado = Vector((0, 0, 1)).cross(x).normalized()
    up = x.cross(lado).normalized()
    W, H = 3.6, 3.2
    trelica(m, A, B, H, "ACO_FERRUGEM", n=int(L / 3.2), esp=0.18, cima=tuple(up), larg=W)
    # piso, correia e rolos
    n = int(L / 1.5)
    for i in range(n):
        p = A + x * (L * (i + 0.5) / n)
        caixa_vs = barra(m, p - x * 0.76 + lado * 0, p + x * 0.76, W - 0.2, 0.06, "CHAPA_PISO", cima=tuple(up))
        q = p + up * 0.6 + lado * 0.6
        barra(m, q - lado * 0.6, q + lado * 0.6, 0.12, 0.12, "ACO_FERRUGEM", cima=tuple(up))
    barra(m, A + up * 0.72 + lado * 0.6, B + up * 0.72 + lado * 0.6, 1.0, 0.03, "BORRACHA", cima=tuple(up))
    # cobertura de chapa (metade faltando)
    k = 0
    s = 0.0
    while s < L - 2.5:
        if random.random() > 0.35:
            O = A + x * s + up * (H + 0.05) - lado * (W / 2 + 0.1)
            chapa_ondulada(m, O, tuple(lado), tuple(x), W + 0.2, 2.5, "CHAPA_ONDULADA", normal=tuple(up))
        s += 2.5
        k += 1
    # cavaletes (torres) que seguram a galeria
    for t in (0.18, 0.42, 0.66, 0.86):
        p = A + d * t
        for sl in (-1, 1):
            b = p + lado * (sl * (W / 2 + 0.8))
            pilar_i(m, b.x, b.y, 0, p.z, 0.5, 0.35, "ACO_FERRUGEM")
        for z in range(4, int(p.z), 5):
            barra(m, (p.x + lado.x * -2.6, p.y + lado.y * -2.6, z), (p.x + lado.x * 2.6, p.y + lado.y * 2.6, z), 0.18, 0.18, "ACO_FERRUGEM")
            barra(m, (p.x + lado.x * -2.6, p.y + lado.y * -2.6, z), (p.x + lado.x * 2.6, p.y + lado.y * 2.6, min(p.z, z + 5)), 0.12, 0.12, "ACO_FERRUGEM")
    # casa de transferência embaixo (moega) e no topo
    caixa(m, (A.x - 2.0, A.y, 4.0), (7.0, 7.0, 8.0), "CHAPA_PINTADA")
    caixa(m, (A.x - 2.0, A.y, 8.2), (7.6, 7.6, 0.4), "ACO_FERRUGEM")
    finalizar("Esteira", m, {})
    LAYOUT["esteira"] = {"a": list(A), "b": list(B)}
    return A, B


# ----------------------------------------------------------------------------- chaminés, silos
CHAMINES = [(-22.0, 56.0, 56.0), (2.0, 56.0, 56.0), (26.0, 56.0, 23.0)]


def chamines():
    m = Malha()
    for (x, y, h) in CHAMINES:
        cilindro(m, (x, y, 0), 4.6, 4.6, 2.0, "CONCRETO", lados=32)
        quebrada = h < 40
        cilindro(m, (x, y, 2.0), 4.0, 4.0 - 1.8 * (h / 56.0), h - 2.0, "TIJOLO", lados=32, tampas=False)
        rt = 4.0 - 1.8 * (h / 56.0)
        if quebrada:
            # topo quebrado: borda serrilhada (alturas que sobem e descem devagar, com dentes soltos), sem cara de castelo
            n = 40
            for i in range(n):
                a = 2 * math.pi * i / n
                hh = max(0.05, 1.6 + 1.4 * math.sin(a * 2 + 0.7) + 0.9 * math.sin(a * 5 + 2.0) + random.uniform(-0.5, 0.5))
                larg = 2 * math.pi * rt / n + 0.05
                caixa(m, (x + math.cos(a) * rt, y + math.sin(a) * rt, h + hh / 2 - 0.05), (larg, 0.42, hh), "TIJOLO",
                      giro_z=math.degrees(a) + 90, giro_x=random.uniform(-4, 4))
            for i in range(14):
                caixa(m, (x + random.uniform(-9, 9), y + random.uniform(-9, 9), 0.4), (random.uniform(0.6, 1.8), random.uniform(0.5, 1.4), 0.7), "TIJOLO",
                      giro_z=random.uniform(0, 180))
        else:
            cilindro(m, (x, y, h), rt + 0.35, rt + 0.35, 1.2, "CONCRETO", lados=32, tampas=False)
            cilindro(m, (x, y, h + 0.9), rt - 0.4, rt - 0.4, 0.2, "FULIGEM", lados=32)
            anel_plataforma(m, (x, y), rt + 0.4, rt + 1.7, h - 2.0, "CHAPA_PISO", "GUARDA_CORPO", lados=28)
            anel_plataforma(m, (x, y), 4.0 - 1.8 * (28 / 56.0) + 0.1, 4.0 - 1.8 * (28 / 56.0) + 1.4, 28.0, "CHAPA_PISO", "GUARDA_CORPO", lados=28)
            escada_marinheiro(m, (x, y - (4.0 - 1.8 * 0.02) - 0.05, 0.0), 28.0, (0, -1, 0), "GUARDA_CORPO")
            r28 = 4.0 - 1.8 * (28 / 56.0)
            escada_marinheiro(m, (x, y - r28 - 0.1, 28.0), h - 30.0, (0, -1, 0), "GUARDA_CORPO")
        # cintas de aço
        for z in range(6, int(h) - 2, 6):
            rr = 4.0 - 1.8 * (z / 56.0)
            cilindro(m, (x, y, z), rr + 0.06, rr + 0.06, 0.25, "ACO_FERRUGEM", lados=32, tampas=False)
        # duto de fumaça chegando
        tubo(m, (x, y - 20.0, 3.0), (x, y - 4.0, 3.0), 1.4, "FERRUGEM_PESADA", lados=18)
        caixa(m, (x, y - 4.1, 2.6), (2.0, 0.4, 3.6), "ESCURO")   # boca escura (passagem)
    finalizar("Chamines", m, {m.mi("TIJOLO"): 2.0})


SILOS = [(-118.0, 30.0), (-104.0, 30.0), (-118.0, 46.0), (-104.0, 46.0)]


def silos():
    m = Malha()
    V = "PINTURA_VERDE"
    for (x, y) in SILOS:
        cilindro(m, (x, y, 0), 6.0, 6.0, 0.6, "CONCRETO", lados=32)
        for i in range(8):
            a = 2 * math.pi * i / 8 + 0.3
            pilar_i(m, x + math.cos(a) * 5.0, y + math.sin(a) * 5.0, 0.6, 8.0, 0.4, 0.3, "ACO_FERRUGEM")
        cilindro(m, (x, y, 5.0), 0.8, 5.5, 3.5, V, lados=32, tampas=False)
        cilindro(m, (x, y, 8.5), 5.5, 5.5, 16.0, V, lados=36, tampas=False)
        for z in range(9, 25, 2):
            cilindro(m, (x, y, z), 5.56, 5.56, 0.12, "ACO_FERRUGEM", lados=36, tampas=False)
        cilindro(m, (x, y, 24.5), 5.5, 1.2, 2.0, V, lados=36)
        guarda_corpo(m, [(x + math.cos(2 * math.pi * i / 24) * 5.0, y + math.sin(2 * math.pi * i / 24) * 5.0, 24.6) for i in range(25)], "GUARDA_CORPO", passo=2.0)
    # galeria de cima ligando os quatro silos (com vão para passar por baixo)
    gz = 27.5
    for (y,) in ((30.0,), (46.0,)):
        trelica(m, (-128.0, y, gz), (-94.0, y, gz), 2.6, "ACO_FERRUGEM", n=10, esp=0.14, larg=2.6)
        caixa(m, (-111.0, y, gz + 0.05), (34.0, 2.5, 0.1), "CHAPA_PISO")
    trelica(m, (-111.0, 30.0, gz), (-111.0, 46.0, gz), 2.6, "ACO_FERRUGEM", n=6, esp=0.14, larg=2.6)
    caixa(m, (-111.0, 38.0, gz + 0.05), (2.5, 16.0, 0.1), "CHAPA_PISO")
    escada_marinheiro(m, (-124.0, 30.0, 0.0), 27.5, (-1, 0, 0), "GUARDA_CORPO")
    finalizar("Silos", m, {})


def tubulacao():
    """rack de tubos elevado que cruza a usina (y = 30) e desce até o galpão."""
    m = Malha()
    y0 = 30.0
    xs = list(range(-90, 92, 8))
    for x in xs:
        for dy in (-1.8, 1.8):
            pilar_i(m, x, y0 + dy, 0, 9.0, 0.35, 0.25, "ACO_FERRUGEM", giro=90)
        barra(m, (x, y0 - 2.2, 6.0), (x, y0 + 2.2, 6.0), 0.3, 0.3, "ACO_FERRUGEM")
        barra(m, (x, y0 - 2.2, 9.0), (x, y0 + 2.2, 9.0), 0.3, 0.3, "ACO_FERRUGEM")
        barra(m, (x, y0 - 1.8, 0.5), (x, y0 + 1.8, 5.8), 0.12, 0.12, "ACO_FERRUGEM")
    for (dy, z, r, mn) in ((-1.3, 6.6, 0.45, "PINTURA_VERDE"), (-0.2, 6.5, 0.35, "ACO_FERRUGEM"), (0.8, 6.7, 0.55, "FERRUGEM_PESADA"),
                           (1.6, 6.45, 0.25, "PINTURA_AMARELA"), (-1.0, 9.7, 0.6, "FERRUGEM_PESADA"), (0.9, 9.5, 0.4, "ACO_FERRUGEM")):
        tubo(m, (xs[0] - 2, y0 + dy, z), (xs[-1] + 2, y0 + dy, z), r, mn, lados=14)
        for x in range(xs[0], xs[-1], 12):
            cilindro(m, (x + 3.0, y0 + dy, z), r + 0.08, r + 0.08, 0.18, "ACO_FERRUGEM", lados=14, eixo=(1, 0, 0))   # flanges
    # válvulas grandes (alvo de foto)
    for x in (-38.0, 54.0):
        cilindro(m, (x, y0 + 0.8, 6.7), 0.8, 0.8, 1.2, "PINTURA_VERDE", lados=16, eixo=(1, 0, 0))
        tubo(m, (x + 0.6, y0 + 0.8, 6.7), (x + 0.6, y0 + 0.8, 8.4), 0.08, "ACO_FERRUGEM")
        pts = [(x + 0.6 + math.cos(2 * math.pi * i / 16) * 0.55, y0 + 0.8 + math.sin(2 * math.pi * i / 16) * 0.55, 8.4) for i in range(17)]
        for a, b in zip(pts, pts[1:]):
            tubo(m, a, b, 0.04, "PINTURA_AMARELA", lados=6)
    # tubo que desce até o galpão e entra na parede norte
    tubo(m, (-30.0, y0 - 1.0, 9.7), (-30.0, 18.0, 9.7), 0.6, "FERRUGEM_PESADA", lados=14)
    tubo(m, (-30.0, 18.0, 9.7), (-30.0, 15.0, 12.0), 0.6, "FERRUGEM_PESADA", lados=14)
    finalizar("Tubulacao", m, {})


def ferrovia():
    m = Malha()
    y0 = -35.0
    for dy in (-0.72, 0.72):
        barra(m, (-170.0, y0 + dy, 0.28), (170.0, y0 + dy, 0.28), 0.07, 0.15, "TRILHO")
    x = -170.0
    while x < 170.0:
        caixa(m, (x, y0, 0.14), (0.24, 2.6, 0.16), "MADEIRA", giro_z=random.uniform(-3, 3))
        x += 0.65
    caixa(m, (0, y0, 0.03), (340.0, 3.6, 0.1), "BRITA")
    # desvio até o galpão
    for dy in (-0.72, 0.72):
        barra(m, (-40.0, -20.0 + dy, 0.3), (-40.0, y0 + 1.5 + dy, 0.3), 0.07, 0.15, "TRILHO", cima=(0, 0, 1))
    # vagões de minério (gôndolas abertas)
    for i, vx in enumerate((14.0, 27.0, 40.0, 53.0)):
        caixa(m, (vx, y0, 1.25), (11.0, 2.8, 0.25), "FERRUGEM_PESADA")
        for (dx, dy, sx, sy) in ((0, -1.4, 11.0, 0.1), (0, 1.4, 11.0, 0.1), (-5.5, 0, 0.1, 2.8), (5.5, 0, 0.1, 2.8)):
            caixa(m, (vx + dx, y0 + dy, 2.35), (sx, sy, 2.0), "FERRUGEM_PESADA")
        for k in range(-5, 6, 2):
            caixa(m, (vx + k, y0 - 1.46, 2.35), (0.12, 0.06, 2.0), "ACO_FERRUGEM")
            caixa(m, (vx + k, y0 + 1.46, 2.35), (0.12, 0.06, 2.0), "ACO_FERRUGEM")
        if i != 1:   # o segundo vagão está vazio (destino de entrega)
            cilindro(m, (vx, y0, 1.4), 4.5, 0.6, 2.6, "MINERIO", lados=10)
        for dx in (-3.8, 3.8):
            caixa(m, (vx + dx, y0, 0.75), (2.0, 2.2, 0.6), "ACO_FERRUGEM")
            for ddx in (-0.6, 0.6):
                for s in (-0.72, 0.72):
                    cilindro(m, (vx + dx + ddx, y0 + s - 0.06, 0.45), 0.42, 0.42, 0.12, "ACO_FERRUGEM", lados=16, eixo=(0, 1, 0))
    # locomotiva
    lx = -12.0
    caixa(m, (lx, y0, 1.3), (15.0, 2.9, 0.4), "PINTURA_AMARELA")
    caixa(m, (lx - 1.0, y0, 2.9), (10.0, 2.2, 2.8), "PINTURA_AMARELA")
    caixa(m, (lx + 5.4, y0, 3.3), (3.2, 2.9, 3.6), "PINTURA_AMARELA")
    caixa(m, (lx + 7.0, y0, 3.9), (0.04, 2.4, 1.0), "VIDRO_SUJO")
    caixa(m, (lx + 5.4, y0, 5.2), (3.4, 3.0, 0.2), "ACO_FERRUGEM")
    cilindro(m, (lx - 3.0, y0, 4.3), 0.3, 0.3, 0.8, "FULIGEM", lados=10)
    for dx in (-5.0, 5.0):
        caixa(m, (lx + dx, y0, 0.75), (3.0, 2.3, 0.6), "ACO_FERRUGEM")
    finalizar("Ferrovia", m, {m.mi("MADEIRA"): 2.0})


def escritorio():
    """prédio de escritório de dois andares em ruína perto da base."""
    m = Malha()
    x0, x1, y0, y1 = -142.0, -122.0, -88.0, -74.0
    C = "CONCRETO"
    for z in (0.0, 3.6, 7.2):
        espessura = 0.25
        if z == 7.2:
            # laje de cima com buraco grande
            caixa(m, ((x0 + x1) / 2 - 5, (y0 + y1) / 2, z), (x1 - x0 - 10, y1 - y0, espessura), C)
            caixa(m, (x1 - 2.5, (y0 + y1) / 2, z), (5, y1 - y0, espessura), C)
        else:
            caixa(m, ((x0 + x1) / 2, (y0 + y1) / 2, z), (x1 - x0, y1 - y0, espessura), C)
    for z0 in (0.0, 3.6):
        for (a, b, eixo, fixo) in ((x0, x1, "x", y0), (x0, x1, "x", y1), (y0, y1, "y", x0), (y0, y1, "y", x1)):
            n = int((b - a) / 2.5)
            for i in range(n):
                s0 = a + i * (b - a) / n
                s1 = a + (i + 1) * (b - a) / n
                c = (s0 + s1) / 2
                w = s1 - s0
                # parapeito, pilarete e verga (janela aberta no meio)
                if eixo == "x":
                    caixa(m, (c, fixo, z0 + 0.6), (w, 0.25, 1.0), "PAREDE_VELHA")
                    caixa(m, (c, fixo, z0 + 3.2), (w, 0.25, 0.6), "PAREDE_VELHA")
                    caixa(m, (s0 + 0.15, fixo, z0 + 2.0), (0.3, 0.25, 2.4), "PAREDE_VELHA")
                else:
                    caixa(m, (fixo, c, z0 + 0.6), (0.25, w, 1.0), "PAREDE_VELHA")
                    caixa(m, (fixo, c, z0 + 3.2), (0.25, w, 0.6), "PAREDE_VELHA")
                    caixa(m, (fixo, s0 + 0.15, z0 + 2.0), (0.25, 0.3, 2.4), "PAREDE_VELHA")
    # porta (vão sem parapeito) — tira um parapeito: deixa um bloco de entrada
    caixa(m, ((x0 + x1) / 2, y1 + 1.5, 0.15), (4.0, 3.0, 0.3), C)
    # escombros
    for i in range(18):
        caixa(m, (random.uniform(x0, x1), random.uniform(y0, y1), 0.35), (random.uniform(0.3, 1.2), random.uniform(0.3, 1.0), random.uniform(0.2, 0.6)), C,
              giro_z=random.uniform(0, 180), giro_x=random.uniform(-15, 15))
    # caixa d'água em cima
    for dx in (-1, 1):
        for dy in (-1, 1):
            barra(m, (x1 - 3 + dx, y0 + 3 + dy, 7.3), (x1 - 3 + dx * 0.8, y0 + 3 + dy * 0.8, 10.0), 0.12, 0.12, "ACO_FERRUGEM")
    cilindro(m, (x1 - 3, y0 + 3, 10.0), 1.5, 1.5, 2.2, "PINTURA_VERDE", lados=20)
    finalizar("Escritorio", m, {m.mi(C): 3.0, m.mi("PAREDE_VELHA"): 3.0})


def pilhas():
    m = Malha()
    rnd = random.Random(5)
    for (cx, cy, r, h, mn) in ((32.0, -72.0, 13.0, 8.0, "MINERIO"), (52.0, -82.0, 10.0, 6.5, "MINERIO"), (12.0, -84.0, 9.0, 5.0, "CARVAO"),
                               (-6.0, -74.0, 7.0, 4.0, "CARVAO")):
        bm = m.bm
        k = m.mi(mn)
        n, an = 14, 28
        aneis = []
        for j in range(n + 1):
            t = j / n
            anel = []
            for i in range(an):
                a = 2 * math.pi * i / an
                rr = r * (1 - t) * (1 + 0.12 * math.sin(3 * a + cx) + rnd.uniform(-0.04, 0.04))
                z = h * (1 - (1 - t) ** 1.6) + rnd.uniform(-0.1, 0.1) * (1 - t)
                anel.append(bm.verts.new((cx + math.cos(a) * rr, cy + math.sin(a) * rr, max(0.0, z - (0.3 if j == 0 else 0)))))
            aneis.append(anel)
        for j in range(n):
            for i in range(an):
                f = bm.faces.new((aneis[j][i], aneis[j][(i + 1) % an], aneis[j + 1][(i + 1) % an], aneis[j + 1][i]))
                f.material_index = k
                f.smooth = True
    finalizar("Pilhas", m, {0: 3.0, 1: 3.0}, recalc=False)


def sucata():
    m = Malha()
    rnd = random.Random(9)
    # vigas empilhadas no pátio
    for k in range(6):
        for j in range(4 - k // 2):
            viga_i(m, (-70.0, -48.0 + j * 0.9 + (k % 2) * 0.4, 0.3 + k * 0.42), (-58.0, -48.0 + j * 0.9 + (k % 2) * 0.4, 0.3 + k * 0.42), 0.4, 0.2, "ACO_FERRUGEM",
                   cima=(0, 1, 0) if k % 2 else (0, 0, 1))
    # tambores
    for i in range(26):
        x, y = rnd.uniform(-60, 58), rnd.choice((rnd.uniform(-15, -9), rnd.uniform(9, 15)))
        if rnd.random() < 0.3:
            cilindro(m, (x, y, 0.62), 0.3, 0.3, 0.9, rnd.choice(("FERRUGEM_PESADA", "PINTURA_AMARELA", "PINTURA_VERDE")), lados=14, eixo=(1, rnd.uniform(-1, 1), 0))
        else:
            cilindro(m, (x, y, 0.2), 0.3, 0.3, 0.9, rnd.choice(("FERRUGEM_PESADA", "PINTURA_AMARELA", "PINTURA_VERDE")), lados=14)
    # pilhas de sucata (pedaços aleatórios) dentro do galpão
    for (cx, cy, n) in ((-45.0, 9.0, 60), (40.0, -4.0, 45), (-50.0, -70.0, 50)):
        for i in range(n):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(0, 4.0) ** 0.8
            h = max(0.2, 3.0 - r * 0.8) * rnd.random()
            caixa(m, (cx + math.cos(a) * r, cy + math.sin(a) * r, h + 0.3), (rnd.uniform(0.3, 2.4), rnd.uniform(0.05, 0.5), rnd.uniform(0.05, 0.6)),
                  rnd.choice(("FERRUGEM_PESADA", "ACO_FERRUGEM", "ESCORIA")), giro_z=rnd.uniform(0, 180), giro_x=rnd.uniform(-40, 40), giro_y=rnd.uniform(-30, 30))
    # contêineres
    for (cx, cy, g, mn) in ((-84.0, -20.0, 5.0, "PINTURA_AMARELA"), (-84.0, -20.0, 5.0, "FERRUGEM_PESADA"), (78.0, -48.0, 80.0, "PINTURA_VERDE")):
        z = 1.3 if mn != "FERRUGEM_PESADA" else 3.9
        caixa(m, (cx, cy, z), (12.0, 2.4, 2.6), mn, giro_z=g if z < 2 else g + 8)
        for k in range(-5, 6):
            caixa(m, (cx + k * math.cos(math.radians(g)), cy + k * math.sin(math.radians(g)), z), (0.1, 2.48, 2.5), "ACO_FERRUGEM", giro_z=g)
    # postes de luz com lâmpada
    for (x, y) in ((-95.0, -40.0), (-60.0, -40.0), (-20.0, -40.0), (20.0, -42.0), (60.0, -40.0), (-75.0, 20.0)):
        tubo(m, (x, y, 0), (x, y, 10.0), 0.12, "ACO_FERRUGEM", lados=8)
        tubo(m, (x, y, 10.0), (x + 1.5, y, 10.4), 0.08, "ACO_FERRUGEM", lados=8)
        caixa(m, (x + 1.6, y, 10.3), (0.6, 0.3, 0.2), "ACO_FERRUGEM")
    finalizar("Sucata", m, {})


def pocas():
    """poças d'água paradas no piso do galpão e no pátio (refletem o céu pelos buracos do telhado)."""
    m = Malha()
    rnd = random.Random(77)
    k = m.mi("POCA")
    bm = m.bm
    lugares = [(-30.0, -3.0, 0.21, 5.0), (-28.0, 6.0, 0.21, 3.0), (26.0, 3.0, 0.21, 4.5), (-48.0, -6.0, 0.21, 3.5), (4.0, -4.0, 0.21, 2.5),
               (44.0, 6.0, 0.21, 3.0), (-70.0, -30.0, 0.02, 4.0), (10.0, -48.0, 0.02, 5.0), (60.0, 24.0, 0.02, 3.0), (-95.0, -20.0, 0.02, 3.5)]
    for (cx, cy, z, r) in lugares:
        n = 28
        centro = bm.verts.new((cx, cy, z + 0.012))
        borda = []
        for i in range(n):
            a = 2 * math.pi * i / n
            rr = r * (0.75 + 0.25 * math.sin(3 * a + cx) + rnd.uniform(-0.08, 0.08))
            borda.append(bm.verts.new((cx + math.cos(a) * rr * 1.3, cy + math.sin(a) * rr, z + 0.012)))
        for i in range(n):
            f = bm.faces.new((centro, borda[i], borda[(i + 1) % n]))
            f.material_index = k
    finalizar("Pocas", m, {}, recalc=False)


def entulho():
    """chapas do telhado caídas no chão, vigas tortas e correntes penduradas da treliça."""
    m = Malha()
    rnd = random.Random(13)
    for i in range(22):
        x, y = rnd.uniform(AX0 + 3, AX1 - 3), rnd.uniform(AY0 + 3, AY1 - 3)
        if abs(x + 10) < 7 and abs(y - 6) < 6:
            continue
        g = math.radians(rnd.uniform(0, 180))
        U = Vector((math.cos(g), math.sin(g), 0))
        V = Vector((-math.sin(g), math.cos(g), rnd.uniform(-0.05, 0.25))).normalized()
        chapa_ondulada(m, (x, y, 0.23 + rnd.uniform(0, 0.05)), tuple(U), tuple(V), 1.0, rnd.uniform(2.0, 3.0), "CHAPA_ONDULADA", normal=(0, 0, 1))
    # vigas caídas, uma apoiada na outra
    viga_i(m, (-52.0, -10.0, 0.4), (-40.0, -12.0, 0.4), 0.5, 0.25, "ACO_FERRUGEM")
    viga_i(m, (-50.0, -13.0, 0.3), (-44.0, -6.0, 2.6), 0.4, 0.2, "ACO_FERRUGEM")
    viga_i(m, (36.0, 12.0, 0.35), (48.0, 9.0, 0.35), 0.5, 0.25, "ACO_FERRUGEM")
    # correntes penduradas das treliças
    for (x, y, comp) in ((-40.0, -8.0, 9.0), (-12.0, 10.0, 7.0), (14.0, -9.0, 10.0), (32.0, 8.0, 6.0), (50.0, -2.0, 8.0)):
        z0 = BEIRAL - 2.2
        for k in range(int(comp / 0.22)):
            z = z0 - k * 0.22
            g = 90 if k % 2 else 0
            caixa(m, (x, y, z), (0.05 if g else 0.14, 0.14 if g else 0.05, 0.22), "CABO")
    # paletes e caixotes
    for i in range(14):
        x, y = rnd.uniform(-58, 58), rnd.choice((rnd.uniform(-14.5, -11), rnd.uniform(11, 14.5)))
        for k in range(3):
            caixa(m, (x, y - 0.4 + k * 0.4, 0.26), (1.2, 0.1, 0.03), "MADEIRA")
        for k in range(3):
            caixa(m, (x - 0.5 + k * 0.5, y, 0.31), (0.1, 1.0, 0.08), "MADEIRA")
        if rnd.random() < 0.6:
            caixa(m, (x, y, 0.85), (1.0, 0.9, 1.0), rnd.choice(("MADEIRA", "CAIXA_PECAS")), giro_z=rnd.uniform(-10, 10))
    finalizar("Entulho", m, {m.mi("MADEIRA"): 1.0}, recalc=False)


# ----------------------------------------------------------------------------- base do drone e plataformas
INICIO = (-96.0, -60.0)
COLETA = (-86.0, -50.0)


def base():
    m = Malha()
    x, y = INICIO
    caixa(m, (x, y, 0.25), (9.0, 9.0, 0.5), "BASE")
    for (dx, dy, sx, sy) in ((-1.6, 0, 0.6, 4.4), (1.6, 0, 0.6, 4.4), (0, 0, 2.6, 0.6)):
        caixa(m, (x + dx, y + dy, 0.505), (sx, sy, 0.01), "PINTURA_BRANCA")
    for i in range(16):
        a = 2 * math.pi * i / 16
        caixa(m, (x + math.cos(a) * 3.7, y + math.sin(a) * 3.7, 0.505), (0.9, 0.18, 0.01), "PINTURA_AMARELA", giro_z=math.degrees(a) + 90)
    # plataforma de coleta (cargas) com grade e listras
    cx, cy = COLETA
    caixa(m, (cx, cy, 0.6), (4.0, 4.0, 1.2), "CONCRETO")
    caixa(m, (cx, cy, 1.21), (3.6, 3.6, 0.02), "PINTURA_AMARELA")
    caixa(m, (cx, cy, 1.225), (2.6, 2.6, 0.02), "BASE")
    # caixas de carga empilhadas ao lado (cenário)
    for i in range(6):
        caixa(m, (cx + 4.0 + (i % 3) * 1.3, cy - 1.0 + (i // 3) * 1.3, 0.6), (1.2, 1.2, 1.2), "CAIXA_PECAS", giro_z=random.uniform(-6, 6))
    caixa(m, (cx + 5.3, cy - 0.35, 1.8), (1.2, 1.2, 1.2), "CAIXA_PECAS", giro_z=12)
    # biruta do pátio
    tubo(m, (x - 6.0, y + 5.0, 0), (x - 6.0, y + 5.0, 6.0), 0.06, "ACO_FERRUGEM", lados=8)
    cilindro(m, (x - 6.0, y + 5.0, 6.0), 0.35, 0.12, 1.6, "PANO", lados=12, eixo=(1, 0.2, -0.15), tampas=False)
    finalizar("Base", m, {})


def plataformas_missao():
    """pequenas plataformas de pouso (destinos) com listras: dão um lugar certo para soltar a carga."""
    m = Malha()
    for d in LAYOUT["entregas"]:
        if d.get("plataforma"):
            x, y, z = d["pos"]
            caixa(m, (x, y, z - 0.08), (2.4, 2.4, 0.16), "CHAPA_PISO")
            caixa(m, (x, y, z + 0.005), (2.0, 2.0, 0.01), "PINTURA_AMARELA")
            caixa(m, (x, y, z + 0.01), (1.4, 1.4, 0.01), "BASE")
            if d.get("suporte"):
                barra(m, (x, y, z - 0.16), d["suporte"], 0.15, 0.15, "ACO_FERRUGEM")
    finalizar("Plataformas", m, {})


def aro():
    m = Malha()
    bm = m.bm
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
    k0, k1 = m.mi("ARO"), m.mi("ARO_PRETO")
    for i in range(nu):
        for j in range(nv):
            f = bm.faces.new((vs[i][j], vs[(i + 1) % nu][j], vs[(i + 1) % nu][(j + 1) % nv], vs[i][(j + 1) % nv]))
            f.smooth = True
            f.material_index = k1 if (i // 4) % 4 == 0 else k0
    finalizar("Aro", m, {})


def modelos_jogo():
    m = Malha()
    cilindro(m, (0, 0, 0), 0.06, 0.06, 1.0, "ACO_FERRUGEM", lados=10)
    finalizar("Haste", m, {})
    m = Malha()
    caixa(m, (20.0, 5.0, 0.5), (1.0, 1.0, 1.0), "ACO_FERRUGEM")
    finalizar("Marcador", m, {})
    # caixa de peças de aço (carga): 45 x 35 x 30 cm com cantoneiras e alça
    m = Malha()
    caixa(m, (0, 0, 0), (0.45, 0.35, 0.3), "CAIXA_PECAS")
    for dx in (-0.22, 0.22):
        for dy in (-0.17, 0.17):
            caixa(m, (dx, dy, 0), (0.03, 0.03, 0.31), "PINTURA_AMARELA")
    caixa(m, (0, 0, 0.152), (0.47, 0.05, 0.01), "PINTURA_AMARELA")
    tubo(m, (-0.1, 0, 0.16), (-0.1, 0, 0.24), 0.012, "ACO_FERRUGEM", lados=6)
    tubo(m, (0.1, 0, 0.16), (0.1, 0, 0.24), 0.012, "ACO_FERRUGEM", lados=6)
    tubo(m, (-0.1, 0, 0.24), (0.1, 0, 0.24), 0.012, "ACO_FERRUGEM", lados=6)
    finalizar("CaixaEntrega", m, {})
    # engrenagem dourada (em pé, 40 cm)
    m = Malha()
    bm = m.bm
    k = m.mi("OURO")
    dentes = 12
    pts = []
    for i in range(dentes * 4):
        a = 2 * math.pi * i / (dentes * 4)
        r = 0.2 if (i % 4) in (1, 2) else 0.16
        pts.append((math.cos(a) * r, math.sin(a) * r))
    fr = [bm.verts.new((-0.04, p[0], p[1])) for p in pts]
    tr = [bm.verts.new((0.04, p[0], p[1])) for p in pts]
    furo_f = [bm.verts.new((-0.04, math.cos(2 * math.pi * i / 16) * 0.06, math.sin(2 * math.pi * i / 16) * 0.06)) for i in range(16)]
    furo_t = [bm.verts.new((0.04, math.cos(2 * math.pi * i / 16) * 0.06, math.sin(2 * math.pi * i / 16) * 0.06)) for i in range(16)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((fr[i], fr[j], tr[j], tr[i])).material_index = k
    for i in range(16):
        j = (i + 1) % 16
        bm.faces.new((furo_f[j], furo_f[i], furo_t[i], furo_t[j])).material_index = k
    # faces da frente e de trás (anel ligando borda dentada ao furo)
    for lado_borda, lado_furo in ((fr, furo_f), (tr, furo_t)):
        for i in range(n):
            j = (i + 1) % n
            a = int(i * 16 / n) % 16
            b = int(j * 16 / n) % 16
            if a == b:
                f = bm.faces.new((lado_borda[i], lado_borda[j], lado_furo[a]))
            else:
                f = bm.faces.new((lado_borda[i], lado_borda[j], lado_furo[b], lado_furo[a]))
            f.material_index = k
    finalizar("Engrenagem", m, {})
    # farol (coluna de luz)
    m = Malha()
    bm = m.bm
    k = m.mi("FAROL")
    n = 24
    baixo = [bm.verts.new((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0)) for i in range(n)]
    cima = [bm.verts.new((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 40.0)) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((baixo[i], baixo[j], cima[j], cima[i])).material_index = k
    bm.normal_update()
    me = bpy.data.meshes.new("Farol")
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        for lp in f.loops:
            ang = math.atan2(lp.vert.co.y, lp.vert.co.x)
            lp[uv].uv = (ang / (2 * math.pi), 0.0 if lp.vert.co.z < 1 else 1.0)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat("FAROL"))
    ob = bpy.data.objects.new("Farol", me)
    bpy.context.scene.collection.objects.link(ob)
    OBJS.append(ob)


# ----------------------------------------------------------------------------- missões
def missoes(esteira_a, esteira_b):
    E = LAYOUT["entregas"]
    meio_esteira = [esteira_a[i] + (esteira_b[i] - esteira_a[i]) * 0.5 for i in range(3)]
    # (nome, posição do ponto em cima da superfície)
    E.append({"nome": "Vagão de minério vazio", "pos": [27.0, -35.0, 1.4]})
    E.append({"nome": "Carro da ponte rolante", "pos": [-25.0, 4.0, TRILHO_Z + 2.95], "plataforma": True})
    E.append({"nome": "Plataforma do alto-forno (24 m)", "pos": [AF[0], AF[1] - 8.1, 24.0], "plataforma": True})
    d = Vector(esteira_b) - Vector(esteira_a)
    lado = Vector((0, 0, 1)).cross(d.normalized()).normalized()
    p = Vector(meio_esteira) - lado * 0.9
    E.append({"nome": "Dentro da galeria da esteira", "pos": [p.x, p.y, p.z + 0.1]})
    E.append({"nome": "Galeria em cima dos silos", "pos": [-111.0, 38.0, 27.6], "plataforma": True})
    E.append({"nome": "Topo da chaminé", "pos": [2.0, 56.0 - (4.0 - 1.8 + 0.35) - 1.0, 54.0], "plataforma": True})
    LAYOUT["coleta"] = [COLETA[0], COLETA[1], 1.25]
    F = LAYOUT["fotos"]
    F.append({"nome": "Rachadura na chaminé", "pos": [-22.0, 56.0 - 3.3, 30.0]})
    F.append({"nome": "Gancho da ponte rolante", "pos": [19.6, -6.0, 11.0]})
    F.append({"nome": "Boca do conversor", "pos": [-10.0 + math.sin(math.radians(35)) * 3.8, 6.0, 5.0 + math.cos(math.radians(35)) * 3.8]})
    F.append({"nome": "Válvula da tubulação", "pos": [54.0, 30.8, 6.7]})
    F.append({"nome": "Bica de gusa do alto-forno", "pos": [AF[0] - 10.0, AF[1], 3.7]})
    F.append({"nome": "Cúpula do regenerador", "pos": [REG[1][0], REG[1][1], 31.5]})
    F.append({"nome": "Cabine da locomotiva", "pos": [-5.0, -35.0, 3.9]})
    # 12 engrenagens douradas escondidas
    LAYOUT["ferraduras"] = [
        [-45.0, 9.0, 3.6],             # em cima da pilha de sucata no galpão
        [5.0, AY1 - 4.0, 6.8],         # dentro da cabine de comando
        [AX0 + 30.0, AY0 + 1.2, 8.6],  # na passarela
        [-25.6, AY1 - 3.5, TRILHO_Z - 1.2],  # ao lado da cabine da ponte rolante
        [4.6, 50.0, 1.0],              # embaixo do duto da chaminé
        [26.0, 56.0, 1.2],             # dentro da chaminé quebrada
        [AF[0] - 16.0, AF[1], 4.0],    # casa de corrida
        [AF[0] + 6.0, AF[1] + 6.0, 45.3],  # topo do alto-forno
        [-111.0, 30.0, 4.0],           # embaixo do silo
        [-132.0, -81.0, 4.4],          # no escritório (1º andar)
        [40.0, -35.0, 4.5],            # em cima do minério do vagão
        [REG[2][0] + 6.0, REG[2][1] + 6.0, 1.2],  # atrás do último regenerador
    ]
    # circuito de aros: entra pela porta oeste do galpão, passa por baixo das pontes, sai pela leste,
    # sobe ao lado da esteira, contorna o alto-forno, passa entre as chaminés e volta pelo trem
    pts = [
        (-84.0, -40.0, 3.0),
        (-72.0, 0.0, 6.0),
        (AX0 - 3.0, 0.0, 8.0),     # porta oeste
        (-38.0, -2.0, 10.0),
        (-25.0, -8.0, 13.0),       # ao lado do gancho da ponte 1
        (-10.0, 6.0, 13.5),        # sobre o conversor
        (8.0, -2.0, 7.0),
        (20.0, 2.0, 13.5),         # embaixo da ponte 2
        (AX1 + 3.0, 0.0, 9.0),     # porta leste
        (75.0, -22.0, 16.0),       # ao lado da esteira
        (AF[0] - 6.0, AF[1] - 14.5, 28.0),
        (AF[0] + 15.0, AF[1] + 8.0, 20.0),
        (REG[0][0] + 6.0, REG[0][1] - 9.0, 12.0),   # entre os regeneradores e o tubo de ar
        (60.0, 30.0, 14.0),        # por cima do rack de tubos
        (14.0, 50.0, 30.0),        # entre as chaminés
        (-10.0, 56.0, 12.0),
        (-62.0, 30.0, 3.5),        # por baixo do rack de tubos
        (-111.0, 38.0, 13.0),      # entre os quatro silos
        (-104.0, -10.0, 5.0),
        (-90.0, -36.0, 3.0),       # chegada (sobre os trilhos)
    ]
    aros = []
    for i, (x, y, z) in enumerate(pts):
        px, py = pts[i - 1][:2] if i > 0 else INICIO
        nx, ny = pts[i + 1][:2] if i + 1 < len(pts) else INICIO
        giro = math.degrees(math.atan2(ny - py, nx - px))
        aros.append({"n": i, "x": x, "y": y, "z": z, "chao": 0.0, "yaw": giro, "haste": z < 9 and not (AX0 - 5 < x < AX1 + 5 and abs(y) < 16)})
    LAYOUT["aros"] = aros
    LAYOUT["raio_aro"] = 2.05
    # pontos de vista do voo de teste
    LAYOUT["vistas"] = [
        {"x": -92.0, "y": -70.0, "z": 6.0, "yaw": 40.0},
        {"x": -75.0, "y": 0.0, "z": 10.0, "yaw": 0.0},
        {"x": -50.0, "y": -10.0, "z": 12.0, "yaw": 10.0},
        {"x": -20.0, "y": 10.0, "z": 5.0, "yaw": -10.0},
        {"x": 40.0, "y": 8.0, "z": 19.0, "yaw": 190.0},
        {"x": 70.0, "y": -40.0, "z": 20.0, "yaw": 60.0},
        {"x": 75.0, "y": -10.0, "z": 30.0, "yaw": 30.0},
        {"x": 120.0, "y": 0.0, "z": 25.0, "yaw": 120.0},
        {"x": 30.0, "y": 25.0, "z": 45.0, "yaw": 150.0},
        {"x": -60.0, "y": 60.0, "z": 20.0, "yaw": -40.0},
        {"x": -140.0, "y": 0.0, "z": 30.0, "yaw": 20.0},
        {"x": -100.0, "y": -95.0, "z": 25.0, "yaw": 70.0},
    ]
    LAYOUT["limites"] = {"x0": -158.0, "x1": 160.0, "y0": -105.0, "y1": 92.0, "z1": 75.0}
    LAYOUT["luzes"] += [
        {"x": -20.0, "y": 0.0, "z": 14.0, "intensidade": 1200.0, "raio": 2600.0, "cor": [255, 200, 150]},
        {"x": 25.0, "y": 0.0, "z": 14.0, "intensidade": 1200.0, "raio": 2600.0, "cor": [255, 200, 150]},
        {"x": -45.0, "y": 0.0, "z": 6.0, "intensidade": 900.0, "raio": 2000.0, "cor": [255, 190, 140]},
        {"x": 45.0, "y": 0.0, "z": 6.0, "intensidade": 900.0, "raio": 2000.0, "cor": [255, 190, 140]},
        {"x": 5.0, "y": AY1 - 4.0, "z": 8.0, "intensidade": 600.0, "raio": 700.0, "cor": [255, 220, 170]},
    ]
    LAYOUT["inicio"] = {"x": INICIO[0], "y": INICIO[1], "z": 0.5 + 0.15, "yaw": 50.0}


def vegetacao():
    """arbustos e árvores pequenas tomando conta (modelos da fazenda, já importados no projeto)."""
    rnd = random.Random(31)
    pl = LAYOUT["plantas"]

    def livre(x, y):
        if AX0 - 4 < x < AX1 + 4 and AY0 - 4 < y < AY1 + 4:
            return False
        if abs(y + 35) < 4 or math.hypot(x - AF[0], y - AF[1]) < 16 or math.hypot(x - INICIO[0], y - INICIO[1]) < 9:
            return False
        if math.hypot(x - COLETA[0], y - COLETA[1]) < 6:
            return False
        for (cx, cy, _) in CHAMINES:
            if math.hypot(x - cx, y - cy) < 7:
                return False
        for (cx, cy) in SILOS + REG:
            if math.hypot(x - cx, y - cy) < 8:
                return False
        if -146 < x < -118 and -92 < y < -70:
            return False
        if abs(y - 30) < 3.5 and -92 < x < 92:
            return False
        return True
    n = 0
    while n < 110:
        x, y = rnd.uniform(-165, 165), rnd.uniform(-115, 100)
        if not livre(x, y):
            continue
        modelo = rnd.choice(("shrub_02", "shrub_04", "shrub_02", "shrub_04", "tree_small_02", "boulder_01", "rock_07"))
        e = rnd.uniform(0.7, 1.4) if "tree" not in modelo else rnd.uniform(0.5, 0.8)
        pl.append({"modelo": modelo, "x": x, "y": y, "z": altura_terreno(x, y) - 0.05, "yaw": rnd.uniform(0, 360), "sx": e, "sy": e, "sz": e})
        n += 1
    # capim nascendo nas frestas: junto das paredes do galpão, nos trilhos e no pátio
    for i in range(170):
        if i < 70:
            lado = rnd.choice((AY0 - 1.2, AY1 + 1.2))
            x, y = rnd.uniform(AX0, AX1), lado + rnd.uniform(-0.8, 0.8)
        elif i < 110:
            x, y = rnd.uniform(-150, 150), -35.0 + rnd.choice((-2.2, 2.2)) + rnd.uniform(-0.4, 0.4)
        else:
            x, y = rnd.uniform(-160, 160), rnd.uniform(-110, 95)
            if not livre(x, y):
                continue
        e = rnd.uniform(0.8, 1.6)
        pl.append({"modelo": "grass_medium_01", "x": x, "y": y, "z": altura_terreno(x, y) - 0.03, "yaw": rnd.uniform(0, 360), "sx": e, "sy": e, "sz": e})
    # árvores grandes do lado de fora da área
    for i in range(110):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(1.08, 1.75)
        x, y = math.cos(a) * 185 * r, math.sin(a) * 135 * r
        pl.append({"modelo": rnd.choice(("island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02")), "x": x, "y": y, "z": altura_terreno(x, y) - 0.1,
                   "yaw": rnd.uniform(0, 360), "sx": 1.0, "sy": 1.0, "sz": rnd.uniform(0.9, 1.2)})
        for k in range(2):
            x2, y2 = x + rnd.uniform(-9, 9), y + rnd.uniform(-9, 9)
            e = rnd.uniform(0.9, 1.6)
            pl.append({"modelo": rnd.choice(("shrub_02", "shrub_04")), "x": x2, "y": y2, "z": altura_terreno(x2, y2) - 0.05,
                       "yaw": rnd.uniform(0, 360), "sx": e, "sy": e, "sz": e})


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
    terreno()
    aciaria()
    chapas()
    pontes_rolantes()
    conversor()
    alto_forno()
    regeneradores()
    a, b = esteira()
    chamines()
    silos()
    tubulacao()
    ferrovia()
    escritorio()
    pilhas()
    sucata()
    pocas()
    entulho()
    base()
    missoes(a, b)
    plataformas_missao()
    aro()
    modelos_jogo()
    vegetacao()
    if "--sem-fbx" not in sys.argv:
        for ob in OBJS:
            exportar(ob)
    with open(os.path.join(SAIDA, "layout_usina.json"), "w", encoding="utf-8") as f:
        json.dump(LAYOUT, f, ensure_ascii=False, indent=1)
    print("layout_usina.json:", len(LAYOUT["aros"]), "aros,", len(LAYOUT["entregas"]), "entregas,", len(LAYOUT["fotos"]), "fotos,",
          len(LAYOUT["ferraduras"]), "engrenagens,", len(LAYOUT["plantas"]), "plantas")


main()
