"""Organiza o .glb vindo do CAD em peças nomeadas para o simulador.

Cada peça vira um nó "chave__N" (chave = item de dados/pecas.json, N = número),
com as malhas juntadas por material. Parafusos e peças sem regra vão para a
peça mais próxima. O modelo é girado para ficar em pé (Y para cima),
centralizado e apoiado em y = 0.

Uso: python preparar_drone.py <drone_id> entrada.glb saida.glb
"""
import re
import sys
from collections import defaultdict

import numpy as np
import trimesh

# (regex no nome do nó ou de algum pai, chave da peça, separar por instância?)
REGRAS = {
    "quad450": [
        (r"^base bottom", "pdb", False),
        (r"^base top", "frame", False),
        (r"^arm ", "braco", True),
        (r"^motor ", "motor", True),
        (r"^propellor v", "helice", True),
        (r"^propellor head", "helice", "perto"),
    ],
    "fpv5": [
        (r"^Propeller (CW|CCW)", "helice", True),
        (r"^RS2205", "motor", True),
        (r"^REGEL_ASM|^MAMBA_KABLE", "esc_4em1", False),
        (r"^FCCKO_ASM|^GUMICKA", "fc_stack", False),
        (r"^DJI o4 Lite VTX", "vtx", False),
        (r"^DJI O4 PRO CAM", "camera_fpv", False),
        (r"^DJI O4 +Pro Antenna", "antena_vtx", False),
        (r"^Tattu", "bateria", False),
        (r"^XT60", "esc_4em1", False),
        (r"^20498|RECE ASS", "receptor", False),
        (r"^Arm(_Mirror)?:", "braco", True),
        (r"^(Upper_Plate|Lower Plate|Upper_Lower_Plate|Kreus|Camera_CF|DJI_O4_Camera_Holder|5mm M3|Thread_insert)", "frame_carbono", False),
    ],
    "hexa_agro": [
        (r"^Prop_20_6_Twist", "helice", True),
        (r"^kunci prop fix", "helice", "perto"),
        (r"^Tiger U7 Motor", "motor", True),
        (r"^clamp motor", "motor", "perto"),
        (r"^arm:", "braco", True),
        (r"^clamp for tube", "braco", "perto"),
        (r"^(landing tube|clamp landing gear|clamp kaki)", "trem_pouso", False),
        (r"^(tandon|sampingan tandon)", "tanque", False),
        (r"^nozzle:", "bomba", False),
        (r"^pucuk nozzle", "bico", True),
        (r"^(clamp nozzle|tutup nozzle)", "bico", "perto"),
        (r"^(alas gps|standgps|gps antenna)", "gps_rtk", False),
        (r"^batre", "bateria", False),
        (r"^(board|spacer|alas|tutup alas|tutup drone|plang|spongati|baut)", "frame_agro", False),
    ],
}

# Giro para ficar com Y para cima (graus no eixo X)
GIRO_X = {"quad450": 0.0, "fpv5": 0.0, "whoop65": -90.0, "hexa_agro": -90.0}
LIMITE_TRIS = {"fpv5": 60000, "hexa_agro": 60000, "quad450": 80000, "whoop65": 80000}


def cor_material(m):
    mat = getattr(m.visual, "material", None)
    c = getattr(mat, "baseColorFactor", None)
    if c is None:
        return (200, 200, 200, 255)
    return tuple(int(x) for x in c)


def caminho(cena, no):
    """Nomes do nó e de todos os pais (do mais fundo ao mais alto)."""
    nomes = []
    atual = no
    pais = cena.graph.transforms.parents
    while atual in pais:
        nomes.append(atual)
        atual = pais[atual]
    return nomes


def nome_limpo(n):
    return re.sub(r"_[0-9a-f]{6}$", "", n)


def main():
    drone, entrada, saida = sys.argv[1], sys.argv[2], sys.argv[3]
    cena = trimesh.load(entrada)
    rot = trimesh.transformations.rotation_matrix(np.radians(GIRO_X.get(drone, 0.0)), [1, 0, 0])

    pecas = []  # (chave, instancia, malha, modo)
    for no in cena.graph.nodes_geometry:
        T, g = cena.graph[no]
        m = cena.geometry[g].copy()
        m.apply_transform(rot @ T)
        nomes = [nome_limpo(n) for n in caminho(cena, no)]
        chave, inst, modo = None, "0", None
        for regex, k, por_inst in REGRAS.get(drone, []):
            achou = next((n for n in nomes if re.search(regex, n)), None)
            if achou:
                chave, modo = k, por_inst
                inst = achou if por_inst is True else "0"
                break
        pecas.append([chave, inst, m, modo])

    # whoop: o CAD é um bloco só; separa pela cor
    if drone == "whoop65":
        for p in pecas:
            c = cor_material(p[2])[:3]
            if c[1] > 80 and c[0] < 40:
                p[0] = "placa_aio"
            elif c[0] > 100 and c[1] < 20:
                p[0] = "frame_dutos"
            elif abs(c[0] - c[2]) < 30 and 120 < c[0] < 160:
                p[0], p[3] = "helice", "quadrante"
            elif c[0] < 30:
                p[0] = "frame_dutos"
            else:
                p[0] = "frame_dutos"

    # numera instâncias (motor 1..N ordenado por ângulo em volta do centro)
    centro = np.mean([p[2].bounds.mean(axis=0) for p in pecas], axis=0)
    grupos = defaultdict(list)
    for p in pecas:
        if p[0] is not None and p[3] is True:
            grupos[(p[0], p[1])].append(p)
    por_chave = defaultdict(list)
    for (k, inst), ps in grupos.items():
        c = np.mean([q[2].bounds.mean(axis=0) for q in ps], axis=0)
        por_chave[k].append((inst, c))
    numero = {}
    for k, lst in por_chave.items():
        lst.sort(key=lambda it: np.arctan2(it[1][0] - centro[0], -(it[1][2] - centro[2])) % (2 * np.pi))
        for i, (inst, _) in enumerate(lst):
            numero[(k, inst)] = i + 1
    centros = {(k, numero[(k, inst)]): c for k, lst in por_chave.items() for inst, c in lst}

    finais = defaultdict(list)
    for p in pecas:
        k, inst, m, modo = p
        if k is None:
            continue
        if modo is True:
            finais[(k, numero[(k, inst)])].append(m)
        elif modo in ("perto", "quadrante"):
            c = m.bounds.mean(axis=0)
            cand = [(np.linalg.norm((cc - c)[[0, 2]]), n) for (kk, n), cc in centros.items() if kk == k]
            if not cand and modo == "quadrante":
                ang = np.arctan2(c[0] - centro[0], -(c[2] - centro[2])) % (2 * np.pi)
                finais[(k, int(ang / (np.pi / 2)) + 1)].append(m)
                continue
            if not cand:
                finais[(k, 1)].append(m)
                continue
            finais[(k, min(cand)[1])].append(m)
        else:
            finais[(k, 0)].append(m)

    # sem regra (parafusos, porcas): vai para a peça mais próxima (menos hélices)
    alvos = {key: np.mean([q.bounds.mean(axis=0) for q in ms], axis=0) for key, ms in finais.items() if key[0] != "helice"}
    for p in pecas:
        if p[0] is None:
            c = p[2].bounds.mean(axis=0)
            key = min(alvos, key=lambda kk: np.linalg.norm(alvos[kk] - c))
            finais[key].append(p[2])

    # junta por material, simplifica, centraliza
    todas = [m for ms in finais.values() for m in ms]
    b = trimesh.util.concatenate(todas).bounds
    desloc = np.array([-(b[0][0] + b[1][0]) / 2, -b[0][1], -(b[0][2] + b[1][2]) / 2])
    total_tris = sum(len(m.faces) for m in todas)
    limite = LIMITE_TRIS.get(drone, 80000)
    saida_cena = trimesh.Scene()
    for (k, n), ms in sorted(finais.items()):
        por_cor = defaultdict(list)
        for m in ms:
            por_cor[cor_material(m)].append(m)
        for i, (cor, lst) in enumerate(por_cor.items()):
            jun = trimesh.util.concatenate(lst)
            jun.apply_translation(desloc)
            alvo = len(jun.faces) * min(1.0, limite * 4 / max(total_tris, 1))
            if len(jun.faces) > 3000 and alvo < len(jun.faces) * 0.9:
                v, f = __import__("fast_simplification").simplify(jun.vertices, jun.faces, 1.0 - alvo / len(jun.faces))
                jun = trimesh.Trimesh(v, f, process=False)
            jun.merge_vertices()
            mat = trimesh.visual.material.PBRMaterial(baseColorFactor=list(cor), metallicFactor=0.0, roughnessFactor=0.5)
            jun.visual = trimesh.visual.TextureVisuals(material=mat)
            nome_no = f"{k}__{n}"
            saida_cena.add_geometry(jun, node_name=f"{nome_no}__m{i}", geom_name=f"{nome_no}__m{i}")
    saida_cena.export(saida)
    tam = trimesh.util.concatenate(todas).bounds
    print(drone, "peças:", len(finais), "tris:", sum(len(g.faces) for g in saida_cena.geometry.values()), "tamanho:", (tam[1] - tam[0]).round(3))
    for (k, n) in sorted(finais):
        print("  ", k, n, len(finais[(k, n)]))


if __name__ == "__main__":
    main()
