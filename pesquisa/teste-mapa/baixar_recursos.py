"""Baixa os recursos gratuitos (CC0) do Poly Haven usados na cena de teste.

Uso: python baixar_recursos.py [pasta_do_projeto_godot]
Funciona no Linux e no Windows. Arquivos que já existem são pulados.
"""
import json
import os
import sys
import urllib.request

API = "https://api.polyhaven.com/files/"
UA = {"User-Agent": "simulador-drone/0.1"}

# texturas: nome -> resolução
TEXTURAS = {
    "aerial_grass_rock": "2k",        # pasto visto de longe
    "grass_ground": "2k",             # pasto de perto
    "red_laterite_soil_stones": "2k", # estrada de terra vermelha
    "brown_mud_dry": "2k",            # terra seca / beira do açude
    "concrete_floor_worn_001": "2k",  # base de pouso
    "clay_roof_tiles_02": "2k",       # telhado do galpão
    "clay_plaster": "2k",             # parede do galpão
    "fine_grained_wood": "1k",        # postes e mourões
}
MAPAS = {"diff": "Diffuse", "nor_gl": "nor_gl", "arm": "arm"}

# modelos: nome -> resolução das texturas
MODELOS = {
    "island_tree_01": "1k",
    "island_tree_02": "1k",
    "island_tree_03": "1k",
    "tree_small_02": "1k",
    "shrub_01": "1k",
    "shrub_02": "1k",
    "shrub_04": "1k",
    "boulder_01": "1k",
    "rock_07": "1k",
    "stone_01": "1k",
    "grass_medium_01": "1k",
}

HDRI = ("farm_field_puresky", "4k")


def baixar(url, destino):
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(destino + ".tmp", "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
    os.replace(destino + ".tmp", destino)
    print("  ok", os.path.relpath(destino))


def info(nome):
    req = urllib.request.Request(API + nome, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    raiz = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "godot")
    rec = os.path.join(raiz, "recursos")

    print("Texturas:")
    for nome, res in TEXTURAS.items():
        d = info(nome)
        for curto, chave in MAPAS.items():
            arq = d[chave][res]["jpg"]
            baixar(arq["url"], os.path.join(rec, "texturas", nome, f"{curto}.jpg"))

    print("Modelos:")
    for nome, res in MODELOS.items():
        g = info(nome)["gltf"][res]["gltf"]
        pasta = os.path.join(rec, "modelos", nome)
        baixar(g["url"], os.path.join(pasta, os.path.basename(g["url"])))
        for rel, arq in g.get("include", {}).items():
            baixar(arq["url"], os.path.join(pasta, rel))

    print("Céu:")
    nome, res = HDRI
    h = info(nome)["hdri"][res]["hdr"]
    baixar(h["url"], os.path.join(rec, "ceu", f"{nome}.hdr"))
    print("Pronto.")


if __name__ == "__main__":
    main()
