"""Gera o PRÉDIO EM CONSTRUÇÃO andar por andar (Blender 5.2, bpy).

Uso:  python gerar_predio.py PASTA_SAIDA
Saída: um .fbx por grupo (Andar0..Andar4, Laje0..Laje4, Portal) + layout.json com
props (modelos do Poly Haven), luzes, portais, ligações verticais e início.

Unidades: metros, Z para cima. Prédio de 24 x 16 m, pé-direito (piso a piso) 3,00 m.
Cada grupo vira um Static Mesh Nanite no Unreal; o jogo mostra só o andar do drone.
"""
import json
import math
import os
import random
import sys

import bpy  # noqa (bpy antes do bmesh)
import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

SAIDA = os.path.abspath(sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].endswith(".py") else "saida_predio")
os.makedirs(SAIDA, exist_ok=True)
random.seed(42)

H = 3.0            # piso a piso
LAJE = 0.15        # espessura da laje
LX, LY = 24.0, 16.0
N_ANDARES = 5      # 0 térreo, 1, 2, 3, 4 = cobertura (laje de cima em obra)
PAREDE = 0.14      # parede de bloco cerâmico 14 cm
BLOCO_C, BLOCO_A, JUNTA = 0.29, 0.19, 0.01

# tamanho do "ladrilho" da textura (m) por material -> UV em escala real
TILE = {
    "CONCRETO_ESTRUTURA": 2.0, "CONCRETO_PISO": 2.5, "CONCRETO_TETO": 2.5, "CONCRETO_SUJO": 2.0,
    "CERAMICA": 0.6, "ARGAMASSA": 1.0, "REBOCO": 2.0, "COMPENSADO": 2.44, "MADEIRA": 1.5,
    "METAL_ESCORA": 1.0, "FERRUGEM": 0.8, "METAL_GALV": 1.0, "TELA": 1.0, "TERRA": 2.0,
    "BRITA": 1.5, "AREIA": 2.0, "PVC": 1.0, "ELETRODUTO": 0.5, "BORRACHA": 1.0,
    "LAMPADA": 1.0, "PORTAL": 1.0, "PINTURA_H": 1.0, "SACO": 1.0, "BALDE": 1.0,
}


# ----------------------------------------------------------------------------- acumuladores
class Grupo:
    """Junta toda a geometria de um grupo (vira um único mesh com vários materiais)."""

    def __init__(self, nome):
        self.nome = nome
        self.v = []
        self.f = []      # (indices, material, uv_offset, cor)

    def add(self, verts, faces, mat, cor=(1, 1, 1), uvoff=None):
        base = len(self.v)
        self.v.extend(verts)
        if uvoff is None:
            uvoff = (random.random() * 7.0, random.random() * 7.0)
        for fc in faces:
            self.f.append(([base + i for i in fc], mat, uvoff, cor))


GRUPOS = {}


def G(nome):
    if nome not in GRUPOS:
        GRUPOS[nome] = Grupo(nome)
    return GRUPOS[nome]


LAYOUT = {"props": [], "luzes": [], "portais": [], "conexoes": [], "inicio": None, "decalques": [],
          "altura_andar": H, "n_andares": N_ANDARES}


# ----------------------------------------------------------------------------- primitivas
def caixa_chanfrada(sx, sy, sz, c):
    """Caixa centrada na origem com chanfro c em todas as arestas (24 vértices)."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    c = max(0.0, min(c, hx * 0.45, hy * 0.45, hz * 0.45))
    if c <= 1e-5:
        v = [(x, y, z) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        return v, f
    idx = {}
    v = []
    for sxg in (-1, 1):
        for syg in (-1, 1):
            for szg in (-1, 1):
                for ax in range(3):
                    p = [sxg * (hx - c), syg * (hy - c), szg * (hz - c)]
                    p[ax] = (sxg, syg, szg)[ax] * (hx, hy, hz)[ax]
                    idx[(ax, sxg, syg, szg)] = len(v)
                    v.append(tuple(p))
    f = []
    s = (-1, 1)
    # faces principais
    for ax in range(3):
        for sg in s:
            o = [a for a in range(3) if a != ax]
            loop = []
            for (u, w) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                sig = [0, 0, 0]
                sig[ax] = sg
                sig[o[0]] = u
                sig[o[1]] = w
                loop.append(idx[(ax, sig[0], sig[1], sig[2])])
            f.append(tuple(loop))
    # chanfros das arestas
    for a in range(3):
        for b in range(a + 1, 3):
            c3 = 3 - a - b
            for sa in s:
                for sb in s:
                    sig1 = [0, 0, 0]
                    sig1[a] = sa
                    sig1[b] = sb
                    sig1[c3] = -1
                    sig2 = list(sig1)
                    sig2[c3] = 1
                    f.append((idx[(a, *sig1)], idx[(a, *sig2)], idx[(b, *sig2)], idx[(b, *sig1)]))
    # cantos
    for sxg in s:
        for syg in s:
            for szg in s:
                f.append((idx[(0, sxg, syg, szg)], idx[(1, sxg, syg, szg)], idx[(2, sxg, syg, szg)]))
    return v, f


def cilindro(r, h, n=10, r2=None):
    r2 = r if r2 is None else r2
    v = []
    for i in range(n):
        a = 2 * math.pi * i / n
        v.append((r * math.cos(a), r * math.sin(a), -h / 2))
    for i in range(n):
        a = 2 * math.pi * i / n
        v.append((r2 * math.cos(a), r2 * math.sin(a), h / 2))
    f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n + j, n + i))
    return v, f


def torno(perfil, n=24):
    """Sólido de revolução em Z a partir de [(raio, z), ...] (de baixo para cima)."""
    v, f = [], []
    m = len(perfil)
    for i in range(n):
        a = 2 * math.pi * i / n
        for (r, z) in perfil:
            v.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(n):
        j = (i + 1) % n
        for k in range(m - 1):
            f.append((i * m + k, j * m + k, j * m + k + 1, i * m + k + 1))
    return v, f


def transformar(verts, loc=(0, 0, 0), rot=(0, 0, 0), esc=(1, 1, 1)):
    M = Matrix.Translation(Vector(loc)) @ Euler(rot, "XYZ").to_matrix().to_4x4() @ Matrix.Diagonal((*esc, 1))
    return [tuple(M @ Vector(p)) for p in verts]


def caixa(grupo, mn, mx, mat, c=0.0, cor=(1, 1, 1), rot=(0, 0, 0), uvoff=None):
    sx, sy, sz = (mx[0] - mn[0]), (mx[1] - mn[1]), (mx[2] - mn[2])
    if sx <= 1e-4 or sy <= 1e-4 or sz <= 1e-4:
        return
    v, f = caixa_chanfrada(sx, sy, sz, c)
    cen = ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    G(grupo).add(transformar(v, cen, rot), f, mat, cor, uvoff)


def caixa_c(grupo, cen, tam, mat, c=0.0, rot=(0, 0, 0), cor=(1, 1, 1), uvoff=None):
    v, f = caixa_chanfrada(tam[0], tam[1], tam[2], c)
    G(grupo).add(transformar(v, cen, rot), f, mat, cor, uvoff)


def tubo(grupo, a, b, r, mat, n=10, cor=(1, 1, 1)):
    a, b = Vector(a), Vector(b)
    d = b - a
    comp = d.length
    if comp < 1e-5:
        return
    v, f = cilindro(r, comp, n)
    rot = d.to_track_quat("Z", "Y").to_euler()
    G(grupo).add(transformar(v, (a + b) / 2, rot), f, mat, cor)


def retangulos_menos_furos(x0, y0, x1, y1, furos):
    """Divide o retângulo em pedaços que evitam os furos (lista de (x0,y0,x1,y1))."""
    xs = sorted({x0, x1, *[max(x0, min(x1, h[0])) for h in furos], *[max(x0, min(x1, h[2])) for h in furos]})
    ys = sorted({y0, y1, *[max(y0, min(y1, h[1])) for h in furos], *[max(y0, min(y1, h[3])) for h in furos]})
    cel = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(h[0] < cx < h[2] and h[1] < cy < h[3] for h in furos):
                continue
            cel.append([xs[i], ys[j], xs[i + 1], ys[j + 1]])
    # junta faixas na direção X para ter menos peças
    junt = True
    while junt:
        junt = False
        for a in cel:
            for b in cel:
                if a is b:
                    continue
                if abs(a[1] - b[1]) < 1e-6 and abs(a[3] - b[3]) < 1e-6 and abs(a[2] - b[0]) < 1e-6:
                    a[2] = b[2]
                    cel.remove(b)
                    junt = True
                    break
            if junt:
                break
    return cel


# ----------------------------------------------------------------------------- planta
PILARES_X = [0.15, 6.0, 12.0, 18.0, 23.85]
PILARES_Y = [0.15, 8.0, 15.85]
PILAR = 0.30

POCO = (13.2, 9.2, 15.0, 11.1)            # elevador (interno)
POCO_PAREDE = 0.15
ESCADA = (9.0, 9.2, 12.4, 14.0)           # caixa da escada
FURO_ESCADA = (9.0, 9.8, 12.4, 14.0)      # vão na laje (deixa o patamar de chegada)
SHAFT = (4.0, 13.4, 5.3, 14.7)            # furo hidráulico 1,3 x 1,3
BURACO_COB = (18.6, 10.2, 21.2, 12.6)     # laje da cobertura sem concretar


def furos_da_laje(k):
    pe = POCO_PAREDE
    f = [(POCO[0] - pe, POCO[1] - pe, POCO[2] + pe, POCO[3] + pe), FURO_ESCADA, SHAFT]
    if k == 4:
        f.append(BURACO_COB)
    if k == 0:
        f = [(POCO[0] - pe, POCO[1] - pe, POCO[2] + pe, POCO[3] + pe)]
    return f


# paredes: (x0,y0,x1,y1, aberturas[(centro, largura, base, topo)])
PORTA = (0.80, 0.0, 2.10)
JANELA = (1.20, 1.00, 2.20)


def ab(c, tipo):
    return (c, tipo[0], tipo[1], tipo[2])


PAREDES_INTERNAS = [
    # corredor (eixo X), sul y=7.0 e norte y=8.6
    (0.3, 7.0, 23.7, 7.0, [ab(3.0, PORTA), ab(9.0, PORTA), ab(15.0, PORTA), ab(21.0, PORTA)]),
    (0.3, 8.6, 9.0, 8.6, [ab(4.5, PORTA)]),
    (15.15, 8.6, 23.7, 8.6, [ab(17.0, PORTA)]),
    # divisórias sul (eixo Y)
    (6.0, 0.3, 6.0, 7.0, [ab(3.5, PORTA)]),
    (12.0, 0.3, 12.0, 7.0, []),
    (18.0, 0.3, 18.0, 7.0, [ab(5.0, PORTA)]),
    # norte: apto NO / núcleo / apto NE
    (9.0, 8.6, 9.0, 15.7, []),
    (12.4, 9.2, 12.4, 15.7, []),
    (19.5, 8.6, 19.5, 15.7, [ab(12.0, PORTA)]),
    (12.4, 14.0, 9.0, 14.0, []),
]
PAREDES_FACHADA = [
    (0.3, 0.15, 23.7, 0.15, [ab(3.0, JANELA), ab(9.0, JANELA), ab(15.0, JANELA), ab(21.0, JANELA)]),
    (0.3, 15.85, 23.7, 15.85, [ab(3.0, JANELA), ab(6.8, JANELA), ab(17.5, JANELA), ab(21.5, JANELA)]),
    (0.15, 0.3, 0.15, 15.7, [ab(4.0, JANELA), ab(12.0, JANELA)]),
    (23.85, 0.3, 23.85, 15.7, [ab(4.0, JANELA), ab(12.0, JANELA)]),
]


def parede_de_blocos(grupo, x0, y0, x1, y1, z0, altura, aberturas, completo=1.0, reboco_lado=0):
    """Alvenaria de blocos cerâmicos 14x19x29 bloco a bloco (cor variando por bloco),
    argamassa no miolo e vergas de concreto sobre as aberturas. 'completo' < 1 deixa a
    parede pela metade, com o topo em degraus como numa obra de verdade."""
    dx, dy = x1 - x0, y1 - y0
    comp = math.hypot(dx, dy)
    if comp < 0.05:
        return
    ux, uy = dx / comp, dy / comp
    nx, ny = -uy, ux
    ang = math.atan2(dy, dx)
    fiadas = int(altura / (BLOCO_A + JUNTA))
    mod = BLOCO_C + JUNTA

    def livre(s, zb, zt):
        for (c, w, b, t) in aberturas:
            if c - w / 2 - 0.005 < s < c + w / 2 + 0.005 and zt > b + 0.001 and zb < t - 0.001:
                return False
        return True

    # altura construída variando ao longo da parede (degraus)
    def fiadas_em(s):
        if completo >= 1.0:
            return fiadas
        base = completo * fiadas
        degrau = max(0, int((s / comp - 0.55) * 14)) if s / comp > 0.55 else 0
        return max(2, int(base) - degrau)

    for fi in range(fiadas):
        zb = z0 + fi * (BLOCO_A + JUNTA) + JUNTA
        zt = zb + BLOCO_A
        desloc = (mod / 2) if fi % 2 else 0.0
        s = -desloc
        while s < comp - 0.001:
            s0, s1 = max(0.0, s), min(comp, s + BLOCO_C)
            s += mod
            if s1 - s0 < 0.04:
                continue
            meio = (s0 + s1) / 2
            if fi >= fiadas_em(meio):
                continue
            # recorta pedaços que caem em abertura
            if not livre(meio, zb, zt):
                continue
            if not (livre(s0 + 0.01, zb, zt) and livre(s1 - 0.01, zb, zt)):
                # bloco cortado na borda da abertura
                for (c, w, b, t) in aberturas:
                    if zt > b and zb < t:
                        if s0 < c - w / 2 < s1:
                            s1 = c - w / 2
                        if s0 < c + w / 2 < s1:
                            s0 = c + w / 2
                if s1 - s0 < 0.04:
                    continue
                meio = (s0 + s1) / 2
            if random.random() < 0.004:  # bloco faltando
                continue
            tom = random.uniform(0.82, 1.12)
            cor = (tom * random.uniform(0.96, 1.04), tom, tom * random.uniform(0.93, 1.03))
            cx = x0 + ux * meio + nx * random.uniform(-0.004, 0.004)
            cy = y0 + uy * meio + ny * random.uniform(-0.004, 0.004)
            caixa_c(grupo, (cx, cy, (zb + zt) / 2), (s1 - s0, PAREDE, BLOCO_A), "CERAMICA", c=0.006,
                    rot=(0, 0, ang + random.uniform(-0.004, 0.004)), cor=cor)
    # miolo de argamassa (aparece nas juntas)
    pedacos = [(0.0, comp)]
    for (c, w, b, t) in aberturas:
        novo = []
        for (a0, a1) in pedacos:
            l0, l1 = c - w / 2, c + w / 2
            if l1 <= a0 or l0 >= a1:
                novo.append((a0, a1))
            else:
                if l0 > a0:
                    novo.append((a0, l0))
                if l1 < a1:
                    novo.append((l1, a1))
        pedacos = novo
    hmax = (BLOCO_A + JUNTA) * (fiadas if completo >= 1 else max(2, int(completo * fiadas)))
    for (a0, a1) in pedacos:
        m = (a0 + a1) / 2
        caixa_c(grupo, (x0 + ux * m, y0 + uy * m, z0 + hmax / 2), (a1 - a0 - 0.02, PAREDE - 0.03, hmax - 0.01),
                "ARGAMASSA", rot=(0, 0, ang))
    # trechos de argamassa sob/sobre aberturas (peitoril e acima da verga)
    for (c, w, b, t) in aberturas:
        mx_, my_ = x0 + ux * c, y0 + uy * c
        if b > 0.05:
            caixa_c(grupo, (mx_, my_, z0 + b / 2), (w - 0.02, PAREDE - 0.03, b - 0.02), "ARGAMASSA", rot=(0, 0, ang))
        if completo >= 1.0 and t < altura - 0.05:
            # verga de concreto
            caixa_c(grupo, (mx_, my_, z0 + t + 0.06), (w + 0.4, PAREDE + 0.005, 0.12), "CONCRETO_SUJO",
                    c=0.008, rot=(0, 0, ang))
            caixa_c(grupo, (mx_, my_, z0 + (t + 0.12 + altura) / 2), (w - 0.02, PAREDE - 0.03, altura - t - 0.12),
                    "ARGAMASSA", rot=(0, 0, ang))
    if reboco_lado:
        # chapisco/reboco em parte da parede (lado indicado), com borda irregular
        lim = comp * random.uniform(0.35, 0.8)
        for i in range(int(lim / 0.5)):
            s0 = i * 0.5
            hh = altura - 0.1 - random.uniform(0, 0.3)
            if not all(livre(s0 + q * 0.1, 0.1, hh) for q in range(5)):
                continue
            off = (PAREDE / 2 + 0.008) * reboco_lado
            caixa_c(grupo, (x0 + ux * (s0 + 0.25) + nx * off, y0 + uy * (s0 + 0.25) + ny * off, z0 + 0.05 + hh / 2),
                    (0.5, 0.016, hh), "REBOCO", c=0.004, rot=(0, 0, ang))


def verga_e_contraverga(grupo, *_):
    pass


# ----------------------------------------------------------------------------- estrutura
def laje(k):
    """Laje k: piso do andar k e teto do andar k-1 (grupo Laje{k})."""
    g = f"Laje{k}"
    zt = k * H
    esp = 0.20 if k == 0 else LAJE
    fur = furos_da_laje(k)
    for (a, b, c, d) in retangulos_menos_furos(0.0, 0.0, LX, LY, fur):
        caixa(g, (a, b, zt - esp), (c, d, zt - 0.012), "CONCRETO_TETO" if k > 0 else "CONCRETO_SUJO", c=0.004)
        caixa(g, (a, b, zt - 0.012), (c, d, zt), "CONCRETO_PISO", c=0.002)
    if k == 0:
        # piso de terra/brita em volta (área externa até a tela)
        caixa(g, (-3.0, -3.0, -0.25), (LX + 3.0, LY + 3.0, -0.2), "TERRA")
        return
    # vigas por baixo (eixos dos pilares)
    def trechos(a0, a1, cortes):
        res = [(a0, a1)]
        for (c0, c1) in cortes:
            novo = []
            for (b0, b1) in res:
                if c1 <= b0 or c0 >= b1:
                    novo.append((b0, b1))
                else:
                    if c0 > b0:
                        novo.append((b0, c0))
                    if c1 < b1:
                        novo.append((c1, b1))
            res = novo
        return [r for r in res if r[1] - r[0] > 0.05]

    for y in PILARES_Y:
        cortes = [(f[0] - 0.05, f[2] + 0.05) for f in fur if f[1] - 0.1 < y < f[3] + 0.1]
        for (a, b) in trechos(0.0, LX, cortes):
            caixa(g, (a, y - 0.1, zt - LAJE - 0.40), (b, y + 0.1, zt - LAJE), "CONCRETO_ESTRUTURA", c=0.012)
    for x in PILARES_X:
        cortes = [(f[1] - 0.05, f[3] + 0.05) for f in fur if f[0] - 0.1 < x < f[2] + 0.1]
        for (a, b) in trechos(0.0, LY, cortes):
            caixa(g, (x - 0.1, a, zt - LAJE - 0.40), (x + 0.1, b, zt - LAJE), "CONCRETO_ESTRUTURA", c=0.012)
    # borda da laje com marcas e pontas de ferro aparecendo na última laje
    if k == 4:
        for i in range(int(LX / 0.2)):
            x = 0.1 + i * 0.2
            for y, s in ((0.0, -1), (LY, 1)):
                tubo(g, (x, y, zt - 0.05), (x, y + s * random.uniform(0.15, 0.6), zt - 0.05 + random.uniform(-0.02, 0.05)),
                     0.005, "FERRUGEM", n=6)
    # parede do poço dentro da espessura da laje
    poco_paredes(g, zt - LAJE, LAJE, sem_porta=True)


def pilares(k):
    g = f"Andar{k}"
    z0 = k * H
    topo = z0 + H - LAJE - (0.40 if k < 4 else 0.0)
    for x in PILARES_X:
        for y in PILARES_Y:
            if k < 4:
                caixa_c(g, (x, y, (z0 + topo) / 2 + 0.2), (PILAR, PILAR, topo - z0 + 0.4), "CONCRETO_ESTRUTURA",
                        c=0.015)
            else:
                # cobertura: arranques de pilar com fôrma e armadura saindo
                hpil = random.choice([0.0, 0.0, 1.2, 2.6])
                if hpil > 0:
                    caixa_c(g, (x, y, z0 + hpil / 2), (PILAR, PILAR, hpil), "CONCRETO_ESTRUTURA", c=0.015)
                if hpil < 2.6 and random.random() < 0.6:
                    # fôrma de madeira montada
                    for (ox, oy, sx, sy) in ((0.17, 0, 0.025, 0.36), (-0.17, 0, 0.025, 0.36),
                                             (0, 0.17, 0.36, 0.025), (0, -0.17, 0.36, 0.025)):
                        caixa_c(g, (x + ox, y + oy, z0 + hpil + 1.1), (sx, sy, 2.2), "COMPENSADO", c=0.003)
                # 4 barras + estribos
                for (ox, oy) in ((-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)):
                    tubo(g, (x + ox, y + oy, z0), (x + ox, y + oy, z0 + hpil + 1.6 + random.uniform(-0.1, 0.2)),
                         0.0065, "FERRUGEM", n=6)
                for e in range(int((hpil + 1.4) / 0.15)):
                    ze = z0 + 0.1 + e * 0.15
                    for (a, b) in (((-0.1, -0.1), (0.1, -0.1)), ((0.1, -0.1), (0.1, 0.1)),
                                   ((0.1, 0.1), (-0.1, 0.1)), ((-0.1, 0.1), (-0.1, -0.1))):
                        tubo(g, (x + a[0], y + a[1], ze), (x + b[0], y + b[1], ze), 0.003, "FERRUGEM", n=5)


def poco_paredes(g, zb, altura, sem_porta=False, porta_lado_sul=True):
    pe = POCO_PAREDE
    x0, y0, x1, y1 = POCO
    zt = zb + altura
    # norte, leste, oeste inteiras
    caixa(g, (x0 - pe, y1, zb), (x1 + pe, y1 + pe, zt), "CONCRETO_ESTRUTURA", c=0.01)
    caixa(g, (x0 - pe, y0 - pe, zb), (x0, y1, zt), "CONCRETO_ESTRUTURA", c=0.01)
    caixa(g, (x1, y0 - pe, zb), (x1 + pe, y1, zt), "CONCRETO_ESTRUTURA", c=0.01)
    # sul com porta 0,9 x 2,1
    if sem_porta:
        caixa(g, (x0, y0 - pe, zb), (x1, y0, zt), "CONCRETO_ESTRUTURA", c=0.01)
        return
    pc = (x0 + x1) / 2
    caixa(g, (x0, y0 - pe, zb), (pc - 0.45, y0, zt), "CONCRETO_ESTRUTURA", c=0.01)
    caixa(g, (pc + 0.45, y0 - pe, zb), (x1, y0, zt), "CONCRETO_ESTRUTURA", c=0.01)
    caixa(g, (pc - 0.45, y0 - pe, zb + 2.1), (pc + 0.45, y0, zt), "CONCRETO_ESTRUTURA", c=0.01)
    # marcas de fôrma (tábuas) por dentro: frisos horizontais
    for i in range(int(altura / 0.3)):
        z = zb + 0.3 * (i + 1)
        caixa(g, (x0 + 0.002, y1 - 0.004, z - 0.006), (x1 - 0.002, y1, z), "CONCRETO_SUJO")
    # guarda-corpo provisório de madeira na porta do poço (deixa vão para o drone)
    tubo(g, (pc - 0.6, y0 - pe - 0.05, zb + 1.15), (pc + 0.6, y0 - pe - 0.05, zb + 1.15), 0.02, "MADEIRA", n=6)


def escada(k):
    """Escada em U entre o andar k e k+1 (grupo Andar{k})."""
    if k >= 4:
        return
    g = f"Andar{k}"
    z0 = k * H
    x0, y0, x1, y1 = ESCADA
    meio = (x0 + x1) / 2
    pe, esp = 0.15, 0.28
    n = 10
    # lance 1 (oeste) sobe em +Y
    ya = y0 + 0.6
    for i in range(n):
        zt = z0 + pe * (i + 1)
        caixa(g, (x0 + 0.05, ya + esp * i, zt - pe - 0.12), (meio - 0.05, ya + esp * (i + 1), zt), "CONCRETO_ESTRUTURA",
              c=0.008)
    # patamar
    caixa(g, (x0 + 0.05, ya + esp * n, z0 + 1.5 - 0.15), (x1 - 0.05, y1 - 0.02, z0 + 1.5), "CONCRETO_ESTRUTURA", c=0.01)
    # lance 2 (leste) sobe em -Y
    for i in range(n):
        zt = z0 + 1.5 + pe * (i + 1)
        yb = ya + esp * n - esp * (i + 1)
        caixa(g, (meio + 0.05, yb, zt - pe - 0.12), (x1 - 0.05, yb + esp, zt), "CONCRETO_ESTRUTURA", c=0.008)
    # escoras de madeira sob os lances (obra)
    for i in range(3):
        y = ya + 0.7 + i * 0.9
        tubo(g, (x0 + 0.4, y, z0), (x0 + 0.4, y, z0 + pe * (i * 3 + 3) - 0.12), 0.04, "MADEIRA", n=6)
    # guarda-corpo provisório (madeira) no lance 2
    for i in range(0, n, 3):
        yb = ya + esp * n - esp * (i + 1)
        zt = z0 + 1.5 + pe * (i + 1)
        tubo(g, (meio, yb + 0.14, zt), (meio, yb + 0.14, zt + 1.0), 0.025, "MADEIRA", n=6)
    tubo(g, (meio, ya + esp * n - 0.1, z0 + 2.5), (meio, ya, z0 + 4.0), 0.02, "MADEIRA", n=6)
    LAYOUT["conexoes"].append({"andar": k, "x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "raio": 4.2})


def andaime_e_tela(k):
    """Andaime fachadeiro + tela de proteção em volta do andar k (grupo Andar{k})."""
    g = f"Andar{k}"
    z0 = k * H - (0.25 if k == 0 else 0.0)
    z1 = k * H + H + (1.6 if k == 4 else 0.0)
    off_in, off_out, off_tela = 0.35, 1.35, 1.6
    lados = [
        ((0.0, 0.0), (LX, 0.0), (0, -1)),
        ((LX, 0.0), (LX, LY), (1, 0)),
        ((LX, LY), (0.0, LY), (0, 1)),
        ((0.0, LY), (0.0, 0.0), (-1, 0)),
    ]
    for (a, b, nrm) in lados:
        ax_, ay_ = a
        bx_, by_ = b
        comp = math.hypot(bx_ - ax_, by_ - ay_)
        ux, uy = (bx_ - ax_) / comp, (by_ - ay_) / comp
        nx, ny = nrm
        npost = int(comp / 2.0) + 1
        for i in range(npost):
            s = min(comp, i * 2.0)
            for off in (off_in, off_out):
                px, py = ax_ + ux * s + nx * off, ay_ + uy * s + ny * off
                tubo(g, (px, py, z0), (px, py, z1), 0.024, "METAL_GALV", n=10)
                # braçadeiras
                for zz in (k * H + 0.1, k * H + 1.1, k * H + 2.1):
                    if z0 < zz < z1:
                        caixa_c(g, (px, py, zz), (0.07, 0.07, 0.06), "METAL_GALV", c=0.008)
        # longarinas e guarda-corpos
        for zz in (k * H + 0.1, k * H + 1.1, k * H + 2.1):
            if not (z0 < zz < z1):
                continue
            for off in (off_in, off_out):
                p0 = (ax_ + nx * off, ay_ + ny * off, zz)
                p1 = (bx_ + nx * off, by_ + ny * off, zz)
                tubo(g, p0, p1, 0.024, "METAL_GALV", n=10)
        # tábuas da plataforma (piso do andaime) na altura da laje
        zp = k * H + 0.12
        for t in range(4):
            off = off_in + 0.12 + t * 0.25
            p0 = Vector((ax_ + nx * off, ay_ + ny * off, zp))
            p1 = Vector((bx_ + nx * off, by_ + ny * off, zp))
            m = (p0 + p1) / 2
            ang = math.atan2(uy, ux)
            caixa_c(g, (m.x, m.y, m.z + 0.02), (comp - 0.1, 0.23, 0.035), "MADEIRA", c=0.004,
                    rot=(0, random.uniform(-0.004, 0.004), ang))
        # diagonais
        for i in range(0, npost - 1, 2):
            s0, s1 = i * 2.0, min(comp, i * 2.0 + 2.0)
            off = off_out
            tubo(g, (ax_ + ux * s0 + nx * off, ay_ + uy * s0 + ny * off, z0 + 0.15),
                 (ax_ + ux * s1 + nx * off, ay_ + uy * s1 + ny * off, min(z1, z0 + 2.0)), 0.022, "METAL_GALV", n=8)
        # tela de proteção (malha com transparência), levemente ondulada
        ext = off_tela
        ax2, ay2 = ax_ - ux * ext, ay_ - uy * ext
        comp_t = comp + 2 * ext
        segs = int(comp_t / 0.5)
        hz = z1 - z0
        nz = int(hz / 0.5) + 1
        verts, faces = [], []
        for i in range(segs + 1):
            s = comp_t * i / segs
            for j in range(nz + 1):
                z = z0 + hz * j / nz
                ond = 0.06 * math.sin(s * 1.3 + z * 0.7) + 0.03 * math.sin(s * 3.1 + j)
                if j in (0, nz) or i % 4 == 0 or i in (0, segs):
                    ond *= 0.3
                verts.append((ax2 + ux * s + nx * (off_tela + ond), ay2 + uy * s + ny * (off_tela + ond), z))
        for i in range(segs):
            for j in range(nz):
                a0 = i * (nz + 1) + j
                b0 = (i + 1) * (nz + 1) + j
                faces.append((a0, b0, b0 + 1, a0 + 1))
        G(g).add(verts, faces, "TELA", uvoff=(0.0, 0.0))


def escoras_e_formas(k):
    """Andar 3: floresta de escoras metálicas segurando as fôrmas da laje de cima."""
    g = f"Andar{k}"
    z0 = k * H
    zf = z0 + H - LAJE           # fundo da laje de cima
    # vigas de madeira (barrotes) e chapas de compensado sob a laje
    for y in [0.6 + i * 1.2 for i in range(13)]:
        x_ini = 0.2
        cortes = sorted((f[0] - 0.1, f[2] + 0.1) for f in furos_da_laje(4) if f[1] - 0.1 < y < f[3] + 0.1)
        for (c0, c1) in cortes + [(LX - 0.2, LX)]:
            if c0 - x_ini > 0.3:
                caixa(g, (x_ini, y - 0.04, zf - 0.07 - 0.12), (c0, y + 0.04, zf - 0.07), "MADEIRA", c=0.006)
            x_ini = max(x_ini, c1)
    for i in range(int(LX / 1.22)):
        for j in range(int(LY / 2.44)):
            x, y = 0.05 + i * 1.22, 0.05 + j * 2.44
            if any(f[0] - 0.3 < x + 0.6 < f[2] + 0.3 and f[1] - 0.3 < y + 1.2 < f[3] + 0.3
                   for f in furos_da_laje(4)):
                continue
            caixa(g, (x, y, zf - 0.07), (x + 1.21, y + 2.43, zf - 0.052), "COMPENSADO", c=0.002)
    # escoras: base, tubo externo, tubo interno, pino e forcado
    pts = []
    for i in range(16):
        for j in range(11):
            x = 0.9 + i * 1.45 + random.uniform(-0.15, 0.15)
            y = 0.8 + j * 1.38 + random.uniform(-0.15, 0.15)
            if 7.0 < y < 8.6 and i % 3 != 0:
                continue  # corredor um pouco mais aberto
            if any(f[0] - 0.4 < x < f[2] + 0.4 and f[1] - 0.4 < y < f[3] + 0.4 for f in furos_da_laje(3) + furos_da_laje(4)):
                continue
            if any(abs(x - px) < 0.45 and abs(y - py) < 0.45 for px in PILARES_X for py in PILARES_Y):
                continue
            if any(math.hypot(x - px, y - py) < 1.0 for (px, py) in ((6.25, 12.65), (8.0, 7.8), (14.5, 4.0))):
                continue
            pts.append((x, y))
    cores = [(0.08, 0.22, 0.55), (0.7, 0.12, 0.08), (0.85, 0.55, 0.05)]
    for (x, y) in pts:
        cor = random.choice(cores)
        inc = (random.uniform(-0.012, 0.012), random.uniform(-0.012, 0.012))
        topo = zf - 0.07 - 0.12
        caixa_c(g, (x, y, z0 + 0.006), (0.15, 0.15, 0.012), "METAL_ESCORA", c=0.003, cor=cor)
        tubo(g, (x, y, z0), (x + inc[0], y + inc[1], z0 + 1.6), 0.03, "METAL_ESCORA", n=12, cor=cor)
        tubo(g, (x + inc[0], y + inc[1], z0 + 1.5), (x + inc[0] * 1.8, y + inc[1] * 1.8, topo - 0.02), 0.024,
             "METAL_GALV", n=12)
        tubo(g, (x + inc[0] - 0.06, y + inc[1], z0 + 1.62), (x + inc[0] + 0.06, y + inc[1], z0 + 1.62), 0.006,
             "METAL_GALV", n=6)
        caixa_c(g, (x + inc[0] * 1.8, y + inc[1] * 1.8, topo - 0.01), (0.14, 0.09, 0.02), "METAL_ESCORA",
                c=0.002, cor=cor)
    # algumas escoras caídas no chão
    for _ in range(6):
        x, y = random.uniform(1, 23), random.uniform(1, 15)
        a = random.uniform(0, math.pi)
        tubo(g, (x, y, z0 + 0.03), (x + 2.2 * math.cos(a), y + 2.2 * math.sin(a), z0 + 0.03), 0.03, "METAL_ESCORA",
             n=12, cor=random.choice(cores))


def armadura_cobertura():
    """Cobertura: malhas de aço sobre a laje e caranguejos (espaçadores)."""
    g = "Andar4"
    z = 4 * H + 0.04
    for (x0, y0, x1, y1) in ((1.0, 1.0, 7.0, 6.0), (14.0, 2.0, 22.0, 7.0), (2.0, 10.0, 8.0, 14.5)):
        for i in range(int((x1 - x0) / 0.15)):
            x = x0 + i * 0.15
            tubo(g, (x, y0, z), (x, y1, z), 0.0042, "FERRUGEM", n=5)
        for j in range(int((y1 - y0) / 0.15)):
            y = y0 + j * 0.15
            tubo(g, (x0, y, z + 0.009), (x1, y, z + 0.009), 0.0042, "FERRUGEM", n=5)
    # ferros de espera em volta do buraco não concretado
    x0, y0, x1, y1 = BURACO_COB
    for i in range(int((x1 - x0) / 0.15) + 1):
        x = x0 + i * 0.15
        for y, s in ((y0, 1), (y1, -1)):
            tubo(g, (x, y - s * 0.05, z - 0.08), (x, y + s * random.uniform(0.25, 0.45), z - 0.1), 0.005, "FERRUGEM",
                 n=6)
    LAYOUT["conexoes"].append({"andar": 3, "x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "raio": 4.5})


# ----------------------------------------------------------------------------- objetos modelados
def betoneira(g, x, y, z, ang):
    perfil = [(0.02, 0.0), (0.35, 0.05), (0.45, 0.35), (0.42, 0.55), (0.28, 0.80), (0.18, 0.86)]
    v, f = torno(perfil, 28)
    v = transformar(v, (0, 0, 0), (math.radians(-35), 0, 0))
    v = transformar(v, (x, y, z + 0.55), (0, 0, ang))
    G(g).add(v, f, "METAL_ESCORA", cor=(0.75, 0.42, 0.05))
    # chassi
    for dx in (-0.35, 0.35):
        tubo(g, (x + dx * math.cos(ang), y + dx * math.sin(ang), z + 0.15),
             (x + dx * math.cos(ang), y + dx * math.sin(ang), z + 0.75), 0.03, "METAL_ESCORA", cor=(0.75, 0.42, 0.05))
    tubo(g, (x - 0.5, y, z + 0.18), (x + 0.5, y, z + 0.18), 0.025, "METAL_GALV")
    for dx in (-0.5, 0.5):
        v, f = cilindro(0.18, 0.08, 18)
        G(g).add(transformar(v, (x + dx, y, z + 0.18), (0, math.pi / 2, 0)), f, "BORRACHA")
    caixa_c(g, (x, y - 0.35, z + 0.45), (0.3, 0.2, 0.25), "METAL_ESCORA", c=0.02, cor=(0.2, 0.2, 0.2))


def carrinho_de_mao(g, x, y, z, ang):
    perfil = [(0.0, 0.0), (0.25, 0.02), (0.36, 0.18), (0.38, 0.2)]
    v, f = torno(perfil, 16)
    v = transformar(v, (0, 0, 0), (0, 0, 0), (1.3, 0.9, 1.0))
    G(g).add(transformar(v, (x, y, z + 0.38), (0, 0, ang)), f, "METAL_ESCORA", cor=(0.1, 0.35, 0.12))
    ca, sa = math.cos(ang), math.sin(ang)
    for s in (-0.22, 0.22):
        tubo(g, (x - ca * 0.4 - sa * s, y - sa * 0.4 + ca * s, z + 0.4),
             (x + ca * 0.9 - sa * s * 1.6, y + sa * 0.9 + ca * s * 1.6, z + 0.55), 0.016, "METAL_GALV")
    v, f = cilindro(0.17, 0.08, 18)
    G(g).add(transformar(v, (x - ca * 0.55, y - sa * 0.55, z + 0.17), (math.pi / 2, 0, ang)), f, "BORRACHA")


def balde(g, x, y, z, cor=(0.15, 0.15, 0.15)):
    v, f = torno([(0.0, 0.0), (0.13, 0.0), (0.16, 0.3), (0.165, 0.31), (0.155, 0.31), (0.12, 0.03)], 20)
    G(g).add(transformar(v, (x, y, z)), f, "BALDE", cor=cor)


def pallet_de_blocos(g, x, y, z, ang, camadas=6):
    ca, sa = math.cos(ang), math.sin(ang)

    def p(lx, ly):
        return (x + ca * lx - sa * ly, y + sa * lx + ca * ly)

    for i, ly in enumerate((-0.45, 0.0, 0.45)):
        cx, cy = p(0, ly)
        caixa_c(g, (cx, cy, z + 0.05), (1.2, 0.1, 0.1), "MADEIRA", c=0.006, rot=(0, 0, ang))
    for i in range(7):
        cx, cy = p(-0.55 + i * 0.183, 0)
        caixa_c(g, (cx, cy, z + 0.115), (0.12, 1.0, 0.025), "MADEIRA", c=0.004, rot=(0, 0, ang))
    for c in range(camadas):
        for i in range(4):
            for j in range(3):
                if c == camadas - 1 and random.random() < 0.35:
                    continue
                lx, ly = -0.45 + i * 0.3, -0.33 + j * 0.33
                cx, cy = p(lx, ly)
                tom = random.uniform(0.85, 1.1)
                caixa_c(g, (cx, cy, z + 0.13 + 0.1 + c * 0.195), (0.29, 0.14 if c % 2 else 0.29, 0.19), "CERAMICA",
                        c=0.006, rot=(0, 0, ang + (math.pi / 2 if c % 2 else 0)), cor=(tom, tom, tom))


def monte(g, x, y, z, raio, altura, mat):
    n = 28
    v = [(x, y, z + altura)]
    aneis = 6
    for a in range(1, aneis + 1):
        r = raio * a / aneis
        for i in range(n):
            t = 2 * math.pi * i / n
            rr = r * (1 + 0.12 * math.sin(3 * t + a) + 0.06 * random.random())
            hz = altura * (1 - (a / aneis) ** 1.6) + random.uniform(-0.01, 0.01)
            v.append((x + rr * math.cos(t), y + rr * math.sin(t), z + max(0.0, hz)))
    f = []
    for i in range(n):
        f.append((0, 1 + i, 1 + (i + 1) % n))
    for a in range(aneis - 1):
        for i in range(n):
            j = (i + 1) % n
            b0, b1 = 1 + a * n, 1 + (a + 1) * n
            f.append((b0 + i, b1 + i, b1 + j, b0 + j))
    G(g).add(v, f, mat)


def feixe_vergalhao(g, x, y, z, ang, comp=6.0):
    ca, sa = math.cos(ang), math.sin(ang)
    for i in range(30):
        ox, oz = random.uniform(-0.12, 0.12), random.uniform(0, 0.12)
        tubo(g, (x - ca * comp / 2 - sa * ox, y - sa * comp / 2 + ca * ox, z + 0.06 + oz),
             (x + ca * comp / 2 - sa * ox, y + sa * comp / 2 + ca * ox, z + 0.06 + oz), 0.006, "FERRUGEM", n=6)
    for s in (-1.5, 1.5):
        caixa_c(g, (x + ca * s, y + sa * s, z + 0.03), (0.1, 0.5, 0.06), "MADEIRA", c=0.005, rot=(0, 0, ang))


def eletroduto(g, pts, r=0.012):
    for a, b in zip(pts, pts[1:]):
        tubo(g, a, b, r, "ELETRODUTO", n=8)


def gambiarra(g, a, b, n_lamp, k):
    """Fio pendurado com lâmpadas (luz de obra)."""
    a, b = Vector(a), Vector(b)
    segs = 16
    pts = []
    for i in range(segs + 1):
        t = i / segs
        p = a.lerp(b, t)
        p.z -= 0.35 * math.sin(math.pi * t)
        pts.append(p)
    for p0, p1 in zip(pts, pts[1:]):
        tubo(g, p0, p1, 0.004, "BORRACHA", n=5)
    for i in range(n_lamp):
        t = (i + 0.5) / n_lamp
        p = a.lerp(b, t)
        p.z -= 0.35 * math.sin(math.pi * t)
        tubo(g, p, p - Vector((0, 0, 0.18)), 0.003, "BORRACHA", n=5)
        v, f = torno([(0.0, -0.05), (0.03, -0.045), (0.032, -0.02), (0.015, 0.0), (0.015, 0.03)], 12)
        G(g).add(transformar(v, (p.x, p.y, p.z - 0.22)), f, "LAMPADA")
        LAYOUT["luzes"].append({"grupo": f"Andar{k}", "tipo": "ponto", "x": p.x, "y": p.y, "z": p.z - 0.27,
                                "lumens": 900, "kelvin": 2700, "raio": 9.0})


# ----------------------------------------------------------------------------- props (Poly Haven)
def prop(nome, k, x, y, z, ang=0.0, esc=1.0):
    LAYOUT["props"].append({"modelo": nome, "grupo": f"Andar{k}", "x": x, "y": y, "z": z, "yaw": math.degrees(ang),
                            "escala": esc})


def portal(n, x, y, z, ang, inclinacao=0.0, esc=0.5):
    LAYOUT["portais"].append({"n": n, "x": x, "y": y, "z": z, "yaw": math.degrees(ang),
                              "pitch": math.degrees(inclinacao), "escala": esc})


# ----------------------------------------------------------------------------- andares
def andar(k):
    g = f"Andar{k}"
    z0 = k * H
    alt_par = H - LAJE - 0.40 if k < 4 else 0.0
    laje(k)
    pilares(k)
    andaime_e_tela(k)
    # poço do elevador (no térreo ele desce 1,2 m: fosso)
    if k == 0:
        poco_paredes(g, -1.2, H - LAJE + 1.2)
        caixa(g, (POCO[0], POCO[1], -1.35), (POCO[2], POCO[3], -1.2), "CONCRETO_SUJO")
    elif k < 4:
        poco_paredes(g, z0, H - LAJE)
    else:
        poco_paredes(g, z0, 2.4)   # casa de máquinas subindo
    LAYOUT["conexoes"].append({"andar": k, "x": (POCO[0] + POCO[2]) / 2, "y": (POCO[1] + POCO[3]) / 2, "raio": 3.8})
    escada(k)
    if k < 4:
        LAYOUT["conexoes"].append({"andar": k, "x": (SHAFT[0] + SHAFT[2]) / 2, "y": (SHAFT[1] + SHAFT[3]) / 2,
                                   "raio": 3.6})
        # tubos de PVC no shaft (o drone passa ao lado)
        for i in range(3):
            x = SHAFT[0] + 0.12 + i * 0.16
            tubo(g, (x, SHAFT[3] - 0.12, z0 - LAJE), (x, SHAFT[3] - 0.12, z0 + H - LAJE), 0.05, "PVC", n=14)
        # guarda-corpo em volta do shaft
        for (a, b) in (((SHAFT[0] - 0.1, SHAFT[1] - 0.1), (SHAFT[2] + 0.1, SHAFT[1] - 0.1)),
                       ((SHAFT[0] - 0.1, SHAFT[1] - 0.1), (SHAFT[0] - 0.1, SHAFT[3]))):
            for zz in (0.5, 1.0):
                tubo(g, (a[0], a[1], z0 + zz), (b[0], b[1], z0 + zz), 0.02, "MADEIRA", n=6)
            for p in (a, b):
                tubo(g, (p[0], p[1], z0), (p[0], p[1], z0 + 1.05), 0.03, "MADEIRA", n=6)

    # alvenaria
    if k <= 2:
        completo = 1.0 if k < 2 else 0.55
        for (x0, y0, x1, y1, abre) in PAREDES_INTERNAS:
            reb = 1 if (k == 0 and abs(y0 - y1) < 1e-6) else 0
            parede_de_blocos(g, x0, y0, x1, y1, z0, alt_par, abre, completo if k == 2 else 1.0, reb)
        for (x0, y0, x1, y1, abre) in PAREDES_FACHADA:
            parede_de_blocos(g, x0, y0, x1, y1, z0, alt_par, abre, completo)

    random.seed(100 + k)
    entulho(k, 320 if k < 3 else 140)
    manchas(k)
    if k < 4:
        extensao(k, [(22.8, 7.6), (20.0, 7.9), (16.5, 7.5), (13.0, 7.7), (12.6, 6.0), (11.0, 4.5), (9.6, 3.3)])
    if k == 0:
        andar_terreo(g, z0)
    elif k == 1:
        andar_1(g, z0)
    elif k == 2:
        andar_2(g, z0)
    elif k == 3:
        escoras_e_formas(k)
        andar_3(g, z0)
    else:
        armadura_cobertura()
        andar_4(g, z0)


def entulho(k, quantidade=260):
    """Caliça e restos de obra espalhados (perto das paredes e pilares, como de verdade)."""
    g = f"Andar{k}"
    z0 = k * H
    pontos_base = []
    for (x0, y0, x1, y1, _) in (PAREDES_INTERNAS + PAREDES_FACHADA if k <= 2 else []):
        for t in range(int(math.hypot(x1 - x0, y1 - y0) / 0.7)):
            f = random.random()
            pontos_base.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
    for x in PILARES_X:
        for y in PILARES_Y:
            pontos_base.append((x, y))
    if not pontos_base:
        return
    for _ in range(quantidade):
        bx, by = random.choice(pontos_base)
        x = min(LX - 0.3, max(0.3, bx + random.gauss(0, 0.35)))
        y = min(LY - 0.3, max(0.3, by + random.gauss(0, 0.35)))
        if any(f[0] - 0.1 < x < f[2] + 0.1 and f[1] - 0.1 < y < f[3] + 0.1 for f in furos_da_laje(k)):
            continue
        tipo = random.random()
        rot = (random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4), random.uniform(0, math.pi))
        if tipo < 0.45:      # caco de bloco
            t = (random.uniform(0.04, 0.14), random.uniform(0.03, 0.1), random.uniform(0.02, 0.07))
            tom = random.uniform(0.8, 1.1)
            caixa_c(g, (x, y, z0 + t[2] * 0.35), t, "CERAMICA", c=0.004, rot=rot, cor=(tom, tom, tom))
        elif tipo < 0.8:     # pedaço de concreto/argamassa
            t = (random.uniform(0.02, 0.09), random.uniform(0.02, 0.08), random.uniform(0.015, 0.05))
            caixa_c(g, (x, y, z0 + t[2] * 0.35), t, random.choice(["ARGAMASSA", "CONCRETO_SUJO"]), c=0.005, rot=rot)
        elif tipo < 0.93:    # sobra de madeira
            t = (random.uniform(0.2, 0.7), random.uniform(0.04, 0.1), 0.025)
            caixa_c(g, (x, y, z0 + 0.0125), t, "MADEIRA", c=0.003, rot=(0, 0, rot[2]))
        else:                # ponta de vergalhão
            a = rot[2]
            c_ = random.uniform(0.3, 1.0)
            tubo(g, (x, y, z0 + 0.006), (x + c_ * math.cos(a), y + c_ * math.sin(a), z0 + 0.006), 0.005, "FERRUGEM", n=6)


def extensao(k, pts):
    """Cabo de extensão laranja largado no chão."""
    g = f"Andar{k}"
    z = k * H + 0.006
    pv = None
    for (x, y) in pts:
        p = (x, y, z)
        if pv:
            tubo(g, pv, p, 0.0055, "ELETRODUTO", n=6, cor=(1.0, 0.45, 0.1))
        pv = p


DECAL_PAREDE = ["Leaking001", "Leaking003", "Leaking006", "Leaking009", "Leaking012A", "Leaking015A", "Leaking018A"]
DECAL_CHAO = ["Leaking006", "Leaking009", "AsphaltDamage001", "Leaking001"]


def decalque(k, tex, x, y, z, dx, dy, dz, larg, alt, giro=0.0):
    """dx,dy,dz = direção da projeção (para dentro da superfície)."""
    LAYOUT["decalques"].append({"grupo": f"Andar{k}", "tex": tex, "x": x, "y": y, "z": z, "dx": dx, "dy": dy, "dz": dz,
                                "largura": larg, "altura": alt, "giro": giro})


def manchas(k):
    z0 = k * H
    # escorrido abaixo das janelas (lado de dentro da fachada) e nos pilares
    if k <= 2:
        for (x0, y0, x1, y1, abre) in PAREDES_FACHADA:
            comp = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / comp, (y1 - y0) / comp
            # normal para dentro do prédio
            cx, cy = LX / 2 - x0, LY / 2 - y0
            nx, ny = -uy, ux
            if nx * cx + ny * cy < 0:
                nx, ny = -nx, -ny
            for (c, w, b, t) in abre:
                if random.random() < 0.8:
                    px = x0 + ux * c + nx * (PAREDE / 2 + 0.02)
                    py = y0 + uy * c + ny * (PAREDE / 2 + 0.02)
                    decalque(k, random.choice(DECAL_PAREDE), px, py, z0 + b * 0.55, -nx, -ny, 0.0,
                             w * random.uniform(0.8, 1.3), b * random.uniform(0.9, 1.2))
    for x in PILARES_X:
        for y in PILARES_Y:
            if random.random() < 0.5 and k < 4:
                lado = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                decalque(k, random.choice(DECAL_PAREDE), x + lado[0] * 0.17, y + lado[1] * 0.17,
                         z0 + random.uniform(0.6, 1.6), -lado[0], -lado[1], 0.0, 0.32, random.uniform(0.8, 1.8))
    # manchas no chão (água, nata de cimento, óleo)
    for _ in range(14 if k < 4 else 8):
        x, y = random.uniform(1, LX - 1), random.uniform(1, LY - 1)
        if any(f[0] - 0.3 < x < f[2] + 0.3 and f[1] - 0.3 < y < f[3] + 0.3 for f in furos_da_laje(k)):
            continue
        tam = random.uniform(0.8, 2.6)
        decalque(k, random.choice(DECAL_CHAO), x, y, z0 + 0.02, 0.0, 0.0, -1.0, tam, tam * random.uniform(0.6, 1.4),
                 random.uniform(0, 360))


def luz_obra(k, x, y, z, ang, lum=6000):
    prop("flood_lights", k, x, y, z, ang)
    LAYOUT["luzes"].append({"grupo": f"Andar{k}", "tipo": "spot", "x": x + 0.15 * math.cos(ang),
                            "y": y + 0.15 * math.sin(ang), "z": z + 1.55, "yaw": math.degrees(ang), "pitch": -25,
                            "lumens": lum, "kelvin": 5200, "raio": 16.0, "cone": 55})


def andar_terreo(g, z0):
    # marca do H de pouso pintada (decalque simples em geometria)
    hx, hy = 2.6, 3.2
    for (a, b) in (((hx - 0.5, hy - 0.6), (hx - 0.35, hy + 0.6)), ((hx + 0.35, hy - 0.6), (hx + 0.5, hy + 0.6)),
                   ((hx - 0.35, hy - 0.07), (hx + 0.35, hy + 0.07))):
        caixa(g, (a[0], a[1], z0 + 0.001), (b[0], b[1], z0 + 0.004), "PINTURA_H")
    LAYOUT["inicio"] = {"x": hx, "y": hy, "z": z0 + 0.25, "yaw": 90.0}
    betoneira(g, 9.5, 3.0, z0, 0.6)
    carrinho_de_mao(g, 10.8, 4.6, z0, 2.2)
    monte(g, 14.2, 2.4, z0, 1.3, 0.75, "AREIA")
    monte(g, 16.6, 2.0, z0, 1.0, 0.55, "BRITA")
    pallet_de_blocos(g, 20.0, 2.2, z0, 0.1)
    pallet_de_blocos(g, 21.6, 4.6, z0, 1.5, 5)
    feixe_vergalhao(g, 4.0, 10.8, z0, 0.0)
    for i, (x, y) in enumerate(((8.4, 1.4), (8.0, 2.0), (12.6, 4.8))):
        balde(g, x, y, z0, random.choice([(0.12, 0.12, 0.12), (0.7, 0.45, 0.05)]))
    for i in range(10):
        prop("cement_bag", 0, 18.8 + (i % 5) * 0.48, 5.6 + (i // 5) * 0.75, z0 + 0.0 + 0.0, random.uniform(-0.1, 0.1))
    for i in range(6):
        prop("cement_bag", 0, 19.0 + (i % 3) * 0.48, 5.9, z0 + 0.14, 1.57 + random.uniform(-0.1, 0.1))
    prop("portable_generator", 0, 22.6, 13.8, z0, 3.3)
    prop("power_box_01", 0, 23.6, 10.0, z0 + 1.3, math.pi)
    prop("tool_cart", 0, 1.8, 12.8, z0, 0.4)
    prop("metal_toolbox", 0, 2.5, 10.4, z0, 1.0)
    prop("ladder_sectioned_01", 0, 7.4, 13.6, z0, 0.3)
    prop("Barrel_02", 0, 22.9, 15.0, z0, 0.0)
    prop("barrel_03", 0, 22.2, 15.2, z0, 0.6)
    prop("propane_tank", 0, 1.0, 15.0, z0, 0.0)
    prop("hand_truck", 0, 7.2, 10.1, z0, 2.0)
    prop("WetFloorSign_01", 0, 11.0, 7.6, z0, 0.3)
    prop("concrete_road_barrier", 0, 4.0, 6.0, z0, 0.0)
    prop("korean_fire_extinguisher_01", 0, 12.3, 8.9, z0, 1.57)
    prop("trashbag", 0, 16.3, 14.9, z0, 0.0)
    prop("trashbag", 0, 16.9, 15.1, z0, 1.0)
    prop("cardboard_box_01", 0, 20.7, 14.6, z0, 0.3)
    prop("old_tyre", 0, 15.8, 12.8, z0, 0.0)
    luz_obra(0, 1.0, 1.0, z0, math.radians(35))
    luz_obra(0, 22.8, 7.8, z0, math.radians(180))
    luz_obra(0, 7.6, 15.0, z0, math.radians(-60), 4500)
    gambiarra(g, (0.8, 7.8, z0 + 2.3), (23.2, 7.8, z0 + 2.3), 5, 0)
    eletroduto(g, [(0.4, 6.92, z0 + 0.3), (0.4, 6.92, z0 + 2.3), (8.0, 6.92, z0 + 2.3)])
    # portais
    portal(1, 3.0, 6.6, z0 + 1.05, math.radians(90), esc=0.42)          # porta do corredor (sul->corredor)
    portal(2, 9.6, 7.8, z0 + 1.2, 0.0, esc=0.6)                       # corredor
    portal(3, (POCO[0] + POCO[2]) / 2, POCO[1] - 0.6, z0 + 1.05, math.radians(90), esc=0.45)  # entra no poço


def andar_1(g, z0):
    pc = (POCO[0] + POCO[2]) / 2
    portal(4, pc, POCO[1] - 0.45, z0 + 1.05, math.radians(-90), esc=0.45)  # sai do poço no 1º andar
    portal(5, 15.0, 7.4, z0 + 1.05, math.radians(-90), esc=0.42)          # entra no apto sudeste
    portal(6, 15.0, 0.5, z0 + 1.6, math.radians(-90), esc=0.55)          # sai pela janela para o andaime
    portal(7, 7.0, -0.85, z0 + 1.2, math.radians(180), esc=0.45)           # corredor do andaime (entre a parede e a tela)
    portal(8, 3.0, -0.2, z0 + 1.6, math.radians(90), esc=0.55)            # volta pela janela
    portal(9, 3.0, 6.6, z0 + 1.05, math.radians(90), esc=0.42)                          # corredor até a escada
    portal(95, 10.2, 7.8, z0 + 1.2, 0.0, esc=0.6)
    portal(10, 9.85, 10.3, z0 + 1.15, math.radians(90), esc=0.5)          # sobe a escada
    for (a, b) in (((0.5, 6.9, z0 + 2.35), (23.5, 6.9, z0 + 2.35)), ((0.5, 8.7, z0 + 2.35), (8.9, 8.7, z0 + 2.35))):
        eletroduto(g, [a, b])
    for x in (2.0, 7.5, 13.0, 20.0):
        eletroduto(g, [(x, 6.93, z0 + 0.3), (x, 6.93, z0 + 2.35)])
        caixa_c(g, (x, 6.92, z0 + 1.1), (0.10, 0.03, 0.10), "ELETRODUTO", c=0.005)
    gambiarra(g, (0.8, 7.8, z0 + 2.3), (23.2, 7.8, z0 + 2.3), 6, 1)
    gambiarra(g, (13.0, 0.6, z0 + 2.3), (17.6, 6.4, z0 + 2.3), 2, 1)
    pallet_de_blocos(g, 2.8, 2.6, z0, 0.2, 4)
    balde(g, 4.2, 1.2, z0)
    prop("cement_bag", 1, 20.4, 3.0, z0, 0.2)
    prop("cement_bag", 1, 20.9, 3.0, z0, 0.0)
    prop("industrial_pastic_container", 1, 9.2, 2.2, z0, 0.5)
    prop("Drill_01", 1, 9.6, 2.7, z0 + 0.0, 0.8)
    prop("wooden_ladder", 1, 7.0, 3.6, z0, 2.0)
    prop("plastic_bottle_gallon", 1, 8.4, 5.6, z0, 0.0)
    prop("pipe_wrench", 1, 5.2, 13.2, z0, 0.6)
    prop("metal_jerrycan", 1, 22.4, 14.6, z0, 1.0)
    luz_obra(1, 0.9, 0.9, z0, math.radians(30), 5000)
    luz_obra(1, 22.6, 14.8, z0, math.radians(-150), 5000)


def andar_2(g, z0):
    portal(11, 11.55, 9.9, z0 + 0.8, math.radians(-90), esc=0.5)         # chega pela escada
    portal(12, 7.4, 7.8, z0 + 1.0, math.radians(180), esc=0.6)           # corredor com paredes pela metade
    portal(13, (SHAFT[0] + SHAFT[2]) / 2, (SHAFT[1] + SHAFT[3]) / 2 - 0.15, z0 + 2.6, 0.0, math.radians(90), esc=0.48)  # sobe no shaft
    pallet_de_blocos(g, 15.5, 3.5, z0, 0.0, 6)
    pallet_de_blocos(g, 20.5, 12.0, z0, 0.4, 3)
    # cavaletes e masseira
    for (x, y) in ((8.5, 4.0), (21.0, 4.5)):
        caixa_c(g, (x, y, z0 + 0.12), (1.0, 0.6, 0.24), "BALDE", c=0.03, cor=(0.08, 0.08, 0.08))
        for dx in (-0.4, 0.4):
            tubo(g, (x + dx, y - 0.3, z0), (x + dx, y - 0.3, z0 + 0.8), 0.03, "MADEIRA")
            tubo(g, (x + dx, y + 0.3, z0), (x + dx, y + 0.3, z0 + 0.8), 0.03, "MADEIRA")
        caixa_c(g, (x, y, z0 + 0.82), (1.2, 0.7, 0.03), "COMPENSADO", c=0.004)
    for i in range(5):
        balde(g, random.uniform(2, 22), random.uniform(1, 6), z0, random.choice([(0.12, 0.12, 0.12), (0.7, 0.45, 0.05)]))
    carrinho_de_mao(g, 13.5, 5.5, z0, -0.4)
    gambiarra(g, (0.8, 7.8, z0 + 2.3), (23.2, 7.8, z0 + 2.3), 5, 2)
    prop("cement_bag", 2, 9.5, 5.6, z0, 0.0)
    prop("plastic_crate_02", 2, 3.0, 12.0, z0, 0.3)
    prop("sledgehammer_01", 2, 3.6, 11.4, z0 + 0.02, 1.2)
    prop("crowbar_01", 2, 14.0, 12.5, z0 + 0.02, 0.4)
    luz_obra(2, 23.0, 0.9, z0, math.radians(140), 5500)
    luz_obra(2, 1.0, 15.0, z0, math.radians(-40), 5000)


def andar_3(g, z0):
    sx, sy = (SHAFT[0] + SHAFT[2]) / 2, (SHAFT[1] + SHAFT[3]) / 2
    portal(14, sx + 1.6, sy - 1.4, z0 + 1.3, math.radians(-50), esc=0.6)   # sai do shaft
    portal(15, 8.0, 7.8, z0 + 1.2, 0.0, esc=0.6)                            # floresta de escoras
    portal(16, 14.5, 4.0, z0 + 1.2, math.radians(10), esc=0.6)
    portal(17, (BURACO_COB[0] + BURACO_COB[2]) / 2, (BURACO_COB[1] + BURACO_COB[3]) / 2, z0 + 2.5, 0.0,
           math.radians(90), esc=0.7)                                        # sobe pelo buraco da laje
    gambiarra(g, (0.8, 7.6, z0 + 2.15), (23.2, 7.6, z0 + 2.15), 7, 3)
    gambiarra(g, (2.0, 2.0, z0 + 2.1), (22.0, 3.0, z0 + 2.1), 4, 3)
    luz_obra(3, 1.0, 1.0, z0, math.radians(40), 4000)
    prop("ladder_sectioned_01", 3, 16.0, 13.0, z0, 0.0)
    prop("metal_toolbox", 3, 6.0, 12.0, z0, 0.5)


def andar_4(g, z0):
    portal(18, 12.0, 4.0, z0 + 1.6, math.radians(180), esc=0.8)    # entre os arranques de pilar
    portal(19, 3.0, 8.0, z0 + 1.6, math.radians(90), esc=0.8)      # chegada
    feixe_vergalhao(g, 10.0, 13.0, z0, 0.3)
    feixe_vergalhao(g, 20.5, 3.5, z0, 1.2)
    for i in range(4):
        x, y = 15.0 + i * 0.6, 14.0
        for j in range(5):
            caixa_c(g, (x, y, z0 + 0.012 + j * 0.019), (1.22, 2.44, 0.018), "COMPENSADO", c=0.002,
                    rot=(0, 0, 1.57 + random.uniform(-0.05, 0.05)))
    prop("portable_welding_cart", 4, 6.0, 12.5, z0, 1.0)
    prop("cement_bag", 4, 2.0, 3.0, z0, 0.0)
    luz_obra(4, 23.0, 15.0, z0, math.radians(-135), 3000)


# ----------------------------------------------------------------------------- portal (malha)
def malha_portal():
    """Aro do portal: 1,7 m de diâmetro interno, tubo com faixas (vira mesh separado)."""
    g = "Portal"
    R, r = 0.92, 0.045
    n, m = 64, 12
    v, f = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        for j in range(m):
            b = 2 * math.pi * j / m
            rr = R + r * math.cos(b)
            v.append((0.0, rr * math.cos(a), rr * math.sin(a) + 0.0 + r * 0 + 0.0))
            v[-1] = (r * math.sin(b), rr * math.cos(a), rr * math.sin(a))
    for i in range(n):
        for j in range(m):
            a0, a1 = i * m + j, ((i + 1) % n) * m + j
            f.append((a0, a1, ((i + 1) % n) * m + (j + 1) % m, i * m + (j + 1) % m))
    G(g).add(v, f, "PORTAL")


# ----------------------------------------------------------------------------- saída
def construir_objeto(grupo):
    me = bpy.data.meshes.new(grupo.nome)
    faces = [fc[0] for fc in grupo.f]
    me.from_pydata(grupo.v, [], faces)
    me.update()
    mats = sorted({fc[1] for fc in grupo.f})
    for nome in mats:
        m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
        me.materials.append(m)
    mi = {n: i for i, n in enumerate(mats)}
    ob = bpy.data.objects.new(grupo.nome, me)
    bpy.context.scene.collection.objects.link(ob)

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.new("UVMap")
    col = bm.loops.layers.color.new("Col")
    bm.faces.ensure_lookup_table()
    for face, info in zip(bm.faces, grupo.f):
        _, mat, off, cor = info
        face.material_index = mi[mat]
        t = TILE.get(mat, 1.0)
        nrm = face.normal
        ax = max(range(3), key=lambda i: abs(nrm[i]))
        for loop in face.loops:
            co = loop.vert.co
            if ax == 0:
                u, w = co.y, co.z
            elif ax == 1:
                u, w = co.x, co.z
            else:
                u, w = co.x, co.y
            if mat == "TELA":
                u, w = (co.x + co.y), co.z
            loop[uv].uv = (u / t + off[0], w / t + off[1])
            loop[col] = (cor[0], cor[1], cor[2], 1.0)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    return ob


def exportar():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    malha_portal()
    for k in range(N_ANDARES):
        andar(k)
    # objeto marcador para conferir eixos/escala no Unreal (caixa em x=20, y=5)
    caixa("Marcador", (19.5, 4.5, 0.0), (20.5, 5.5, 1.0), "CONCRETO_SUJO")
    resumo = {}
    for nome, gr in GRUPOS.items():
        bpy.ops.object.select_all(action="DESELECT")
        ob = construir_objeto(gr)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        caminho = os.path.join(SAIDA, f"{nome}.fbx")
        bpy.ops.export_scene.fbx(filepath=caminho, use_selection=True, apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_ALL", mesh_smooth_type="FACE",
                                 use_mesh_modifiers=False, add_leaf_bones=False, bake_anim=False,
                                 axis_forward="-Z", axis_up="Y", colors_type="LINEAR")
        resumo[nome] = {"vertices": len(gr.v), "faces": len(gr.f)}
        bpy.data.objects.remove(ob)
    LAYOUT["grupos"] = resumo
    for i, p in enumerate(LAYOUT["portais"]):
        p["n"] = i + 1
    with open(os.path.join(SAIDA, "layout.json"), "w", encoding="utf-8") as fp:
        json.dump(LAYOUT, fp, ensure_ascii=False, indent=1)
    print(json.dumps(resumo, indent=1))


if __name__ == "__main__":
    exportar()
