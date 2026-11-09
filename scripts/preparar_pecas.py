"""Deixa as peças avulsas do CAD no padrão do simulador.

Padrão: Y para cima, centrada em X/Z, apoiada em y = 0, malhas juntadas por cor
(nó "peca__m0", "peca__m1"...), triângulos limitados.

Uso: python preparar_pecas.py pasta_glb_entrada pasta_saida
"""
import os
import sys
from collections import defaultdict

import fast_simplification
import numpy as np
import trimesh

R = trimesh.transformations.rotation_matrix


def cor(m):
    c = getattr(getattr(m.visual, "material", None), "baseColorFactor", None)
    return tuple(int(x) for x in c) if c is not None else (180, 180, 180, 255)


def malhas(caminho):
    s = trimesh.load(caminho)
    out = []
    for no in s.graph.nodes_geometry:
        T, g = s.graph[no]
        m = s.geometry[g].copy()
        m.apply_transform(T)
        out.append(m)
    return out


def girar(ms, M):
    for m in ms:
        m.apply_transform(M)


def tudo(ms):
    return trimesh.util.concatenate(ms)


def topo_mais_largo(ms):
    """Gira 180° se a parte mais larga (raio maior) estiver embaixo."""
    v = tudo(ms).vertices
    c = v.mean(axis=0)
    r = np.linalg.norm((v - c)[:, [0, 2]], axis=1)
    largos = v[r > np.percentile(r, 85)]
    if largos[:, 1].mean() < c[1]:
        girar(ms, R(np.pi, [1, 0, 0]))


def eixo_para_cima(ms):
    """Motor: o eixo (pontos perto do centro, bem finos) tem que ficar em cima."""
    v = tudo(ms).vertices
    c = v.mean(axis=0)
    r = np.linalg.norm((v - c)[:, [0, 2]], axis=1)
    eixo = v[r < np.percentile(r, 3)]
    if eixo[:, 1].max() < v[:, 1].max() - 1e-4 and eixo[:, 1].min() <= v[:, 1].min() + 1e-4:
        girar(ms, R(np.pi, [1, 0, 0]))


def so_um_motor(ms):
    """O CAD do 0702 traz dois motores lado a lado: fica com o que tem o adaptador de hélice."""
    b = tudo(ms).bounds
    meio = (b[0][0] + b[1][0]) / 2
    esq = [m for m in ms if m.bounds.mean(axis=0)[0] < meio]
    dir_ = [m for m in ms if m.bounds.mean(axis=0)[0] >= meio]
    azul = lambda lst: sum(1 for m in lst if cor(m)[2] > 150 and cor(m)[0] < 120)
    return dir_ if azul(dir_) >= azul(esq) else esq


AJUSTES = {
    # nome: (função que recebe a lista de malhas e devolve a lista ajustada, limite de triângulos)
    "pixhawk": (lambda ms: (girar(ms, R(-np.pi / 2, [1, 0, 0])), ms)[1], 40000),
    "gps": (lambda ms: (girar(ms, R(-np.pi / 2, [1, 0, 0])), topo_mais_largo(ms), ms)[2], 30000),
    "bat3s": (lambda ms: (girar(ms, R(np.pi / 2, [0, 1, 0])), ms)[1], 20000),
    "esc30": (lambda ms: (girar(ms, R(np.pi / 2, [0, 1, 0])), ms)[1], 25000),
    "meteor65": (lambda ms: ms, 90000),
    "motor0702": (lambda ms: (lambda u: (girar(u, R(np.pi, [1, 0, 0])), u)[1])(so_um_motor(ms)), 10000000),
}


def main():
    ent, sai = sys.argv[1], sys.argv[2]
    os.makedirs(sai, exist_ok=True)
    for nome, (ajuste, limite) in AJUSTES.items():
        ms = ajuste(malhas(os.path.join(ent, nome + ".glb")))
        b = tudo(ms).bounds
        desl = [-(b[0][0] + b[1][0]) / 2, -b[0][1], -(b[0][2] + b[1][2]) / 2]
        total = sum(len(m.faces) for m in ms)
        fator = min(1.0, limite / max(total, 1))
        por_cor = defaultdict(list)
        for m in ms:
            por_cor[cor(m)].append(m)
        cena = trimesh.Scene()
        for i, (c, lst) in enumerate(por_cor.items()):
            j = trimesh.util.concatenate(lst)
            j.apply_translation(desl)
            if fator < 0.95 and len(j.faces) > 2000:
                v, f = fast_simplification.simplify(j.vertices, j.faces, 1.0 - fator)
                j = trimesh.Trimesh(v, f, process=False)
            j.merge_vertices()
            j.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(baseColorFactor=list(c), metallicFactor=0.0, roughnessFactor=0.5))
            cena.add_geometry(j, node_name=f"{nome}__m{i}", geom_name=f"{nome}__m{i}")
        cena.export(os.path.join(sai, nome + ".glb"))
        bb = cena.bounds
        print(nome, "tamanho", (bb[1] - bb[0]).round(4), "tris", sum(len(g.faces) for g in cena.geometry.values()))


if __name__ == "__main__":
    main()
