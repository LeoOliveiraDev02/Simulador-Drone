"""Vitrine (laboratório) — malhas pequenas para testar o vento na vegetação antes de levar para a fazenda.

Uso:  python3 gerar_vitrine.py SAIDA
Gera em SAIDA:
  TerrenoVitrine.fbx   chão de 300 x 300 m (plano no meio, morros em volta), cores de vértice como o da fazenda
  PastoVitrine.fbx     capim (cor do vértice R = altura dentro da touceira 0..1, G = altura do molde / 3 m)
  PalhaVitrine.fbx     palha seca (idem)
  FloresVitrine.fbx    flores amarelas (idem)
  MilhoVitrine.fbx     um canteiro de milho de 16 x 10 m (idem)
  vitrine.json         onde ficam as coisas (o Unreal monta o mapa com isso)

Reaproveita as funções do gerar_campo.py (moldes do capim, milho e flor)."""
import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/vitrine"
os.makedirs(SAIDA, exist_ok=True)

# carrega as funções da fazenda sem rodar a geração dela
fonte = open(os.path.join(AQUI, "gerar_campo.py"), encoding="utf-8").read()
fonte = fonte[: fonte.rindex("\nmain()")]
sys.argv = [sys.argv[0], SAIDA]
G = {"__name__": "gerar_campo_funcoes", "__file__": os.path.join(AQUI, "gerar_campo.py")}
exec(compile(fonte, "gerar_campo.py", "exec"), G)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

LADO = 300.0          # m
PLANO = 42.0          # raio plano no meio


def h_vitrine(x, y):
    """altura (m): plana no meio, morrinhos suaves que sobem para as bordas (fecha o horizonte)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    d = np.hypot(x, y)
    ondas = 1.6 * np.sin(x * 0.045 + 0.7) * np.cos(y * 0.038 - 0.4) + 0.9 * np.sin((x + y) * 0.09)
    sobe = G["smoothstep"](PLANO, LADO * 0.5, d)
    return (ondas + 9.0 * sobe ** 2) * sobe


def terreno():
    n = 150
    t = np.linspace(-LADO / 2, LADO / 2, n + 1)
    X, Y = np.meshgrid(t, t)
    H = h_vitrine(X, Y)
    # cores (o material do terreno da fazenda): R = estrada de terra, G = beira do açude, B = terra batida
    d = np.hypot(X, Y + 2.0)
    b = 1.0 - G["smoothstep"](3.0, 5.0, d)                                   # chão batido onde o drone sai
    caminho = (np.abs(X) < 1.6) & (Y > 2.0) & (Y < 30.0)                      # trilha até as árvores
    r = np.where(caminho, 1.0 - G["smoothstep"](0.9, 1.6, np.abs(X)), 0.0)
    g = np.zeros_like(X)
    nv = (n + 1) * (n + 1)
    verts = np.stack([X.ravel(), Y.ravel(), H.ravel()], axis=1).astype(np.float32)
    idx = np.arange(nv).reshape(n + 1, n + 1)
    a, bb, dd, e = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    quads = np.stack([a, bb, e, dd], axis=1)
    me = bpy.data.meshes.new("TerrenoVitrine")
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
    if me.polygons[nq // 2].normal.z < 0:
        me.flip_normals()
    ca = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
    ca.data.foreach_set("color", np.stack([r.ravel(), g.ravel(), b.ravel(), np.ones(nv)], axis=1).astype(np.float32).ravel())
    me.materials.append(G["mat"]("TERRENO"))
    me.polygons.foreach_set("use_smooth", np.ones(nq, dtype=bool))
    ob = bpy.data.objects.new("TerrenoVitrine", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def espalhar_com_altura(nome, mold, posicoes, materiais):
    """como o espalhar da fazenda, mas grava na cor do vértice a altura de cada ponto dentro da planta
    (R: 0 na raiz, 1 na ponta; G: altura do molde / 3 m) — é o que o material usa para balançar com o vento."""
    v0 = mold[0]
    zmax = max(1e-3, float(v0[:, 2].max()))
    ob = G["espalhar"](nome, mold, posicoes, materiais)
    me = ob.data
    nrep = len(posicoes)
    rr = np.clip(v0[:, 2] / zmax, 0.0, 1.0)
    cor = np.zeros((nrep * len(v0), 4), dtype=np.float32)
    cor[:, 0] = np.tile(rr, nrep)
    cor[:, 1] = min(1.0, zmax / 3.0)
    cor[:, 3] = 1.0
    ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", cor.ravel())
    G["normais_para_cima"](ob)
    return ob


def livre(x, y, canteiros, raio_extra=0.6):
    ok = np.hypot(x, y + 2.0) > 4.5                                   # onde o drone sai
    ok &= ~((np.abs(x) < 2.2) & (y > 2.0) & (y < 30.0))                # trilha
    for (cx, cy, lx, ly) in canteiros:
        ok &= ~((np.abs(x - cx) < lx / 2 + raio_extra) & (np.abs(y - cy) < ly / 2 + raio_extra))
    return ok


def main():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    G["modelos_soltos"]()                       # cria os moldes (MOLDES["capim"], ["milho"], ["flor"], ["palha"])
    for ob in list(bpy.data.objects):            # os objetos-modelo da fazenda não vão para a vitrine
        bpy.data.objects.remove(ob, do_unlink=True)
    M = G["MOLDES"]
    rr = np.random.RandomState(11)

    # onde ficam as coisas (metros; x = leste, y = norte/para frente do drone)
    canteiros = [(0.0, 7.0, 7.0, 7.0), (8.5, 7.0, 7.0, 7.0)]                 # Dry Soil, Arid Soil
    lago = (-12.0, 2.0, 9.0, 6.0)                                           # x, y, largura, fundo
    milho = (-10.0, 22.0, 10.0, 8.0)
    arvores = {"atual": (-9.0, 17.0), "vento": (0.0, 19.0), "nova": (9.0, 17.0)}
    bloqueios = canteiros + [lago, milho, (arvores["vento"][0], arvores["vento"][1], 3.0, 3.0),
                             (arvores["atual"][0], arvores["atual"][1], 3.0, 3.0), (arvores["nova"][0], arvores["nova"][1], 3.0, 3.0)]

    terreno()

    # capim em volta (mais denso perto, até 60 m)
    n = 70000
    ang = rr.uniform(0, 2 * np.pi, n)
    rad = np.sqrt(rr.uniform(0, 60.0 ** 2, n))
    x, y = np.cos(ang) * rad, np.sin(ang) * rad + 6.0
    ok = livre(x, y, bloqueios)
    x, y = x[ok][:16000], y[ok][:16000]
    pos = np.stack([x, y, h_vitrine(x, y) - 0.03, rr.uniform(0, 2 * np.pi, len(x)), rr.uniform(0.55, 0.95, len(x)), rr.uniform(0.55, 0.95, len(x))], axis=1)
    espalhar_com_altura("PastoVitrine", M["capim"], pos, ["CAPIM"])

    x2, y2 = np.cos(ang[::3]) * rad[::3] * 1.1, np.sin(ang[::3]) * rad[::3] * 1.1 + 6.0
    ok = livre(x2, y2, bloqueios) & (G["Ruido"](21, 3)(x2 * 0.06, y2 * 0.06) > 0.1)
    x2, y2 = x2[ok][:5000], y2[ok][:5000]
    pos = np.stack([x2, y2, h_vitrine(x2, y2) - 0.03, rr.uniform(0, 2 * np.pi, len(x2)), rr.uniform(0.6, 1.1, len(x2)), rr.uniform(0.5, 0.9, len(x2))], axis=1)
    espalhar_com_altura("PalhaVitrine", M["palha"], pos, ["PALHA"])

    x3, y3 = np.cos(ang[1::5]) * rad[1::5], np.sin(ang[1::5]) * rad[1::5] + 6.0
    ok = livre(x3, y3, bloqueios) & (G["Ruido"](31, 3)(x3 * 0.08, y3 * 0.08) > 0.3)
    x3, y3 = x3[ok][:2500], y3[ok][:2500]
    pos = np.stack([x3, y3, h_vitrine(x3, y3) - 0.02, rr.uniform(0, 2 * np.pi, len(x3)), rr.uniform(0.8, 1.25, len(x3)), rr.uniform(0.75, 1.3, len(x3))], axis=1)
    espalhar_com_altura("FloresVitrine", M["flor"], pos, ["CAPIM", "FLOR_AMARELA"])

    # canteiro de milho (fileiras a cada 95 cm, pés a cada 40 cm)
    mx, my, ml, mf = milho
    px, py = [], []
    xx = mx - ml / 2 + 0.4
    while xx < mx + ml / 2:
        yy = my - mf / 2 + 0.2
        while yy < my + mf / 2:
            px.append(xx + rr.uniform(-0.08, 0.08))
            py.append(yy + rr.uniform(-0.06, 0.06))
            yy += 0.40
        xx += 0.95
    px, py = np.array(px), np.array(py)
    pos = np.stack([px, py, h_vitrine(px, py) - 0.03, rr.uniform(0, 2 * np.pi, len(px)), rr.uniform(0.85, 1.15, len(px)), rr.uniform(0.8, 1.15, len(px))], axis=1)
    espalhar_com_altura("MilhoVitrine", M["milho"], pos, ["MILHO", "ESPIGA"])

    for ob in list(bpy.context.scene.objects):
        G["exportar"](ob)
    info = {"canteiros": canteiros, "lago": lago, "milho": milho, "arvores": arvores, "inicio": [0.0, -2.0]}
    with open(os.path.join(SAIDA, "vitrine.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print("vitrine pronta em", SAIDA)


main()
