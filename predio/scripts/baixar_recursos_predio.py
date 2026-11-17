"""Baixa os recursos gratuitos (CC0) do mapa do PRÉDIO EM CONSTRUÇÃO.

Fontes: Poly Haven (texturas 4K, modelos 2K, céus) e ambientCG (telas, decalques de
manchas/vazamento, papelão). Tudo CC0: pode usar e vender o jogo sem pagar nada.

Uso: python baixar_recursos_predio.py PASTA_DESTINO
Funciona no Linux e no Windows. Arquivos que já existem são pulados.
Normais em formato DirectX (nor_dx), que é o que o Unreal usa.
ARM = R: oclusão (AO), G: rugosidade, B: metal (mesmo padrão ORM do Unreal).
"""
import io
import json
import os
import sys
import urllib.request
import zipfile

UA = {"User-Agent": "simulador-drone-predio/0.1"}
PH_API = "https://api.polyhaven.com/files/"
ACG_API = "https://ambientcg.com/api/v2/full_json?include=downloadData&id="

# ---------------- texturas (Poly Haven, 4K) ----------------
TEXTURAS = {
    # concreto da estrutura (lajes, pilares, vigas)
    "concreto": [
        "concrete_floor_worn_001", "damaged_concrete_floor", "concrete_floor_damaged_01",
        "cracked_concrete", "garage_floor", "hangar_concrete_floor", "worn_concrete_floor",
        "scuffed_cement", "concrete_wall_006", "concrete_wall_008", "concrete_slab_wall",
        "concrete_layers_02", "hacked_concrete", "rebar_reinforced_concrete",
        "concrete_debris", "dirty_concrete", "chipped_concrete",
    ],
    # alvenaria (bloco cerâmico baiano, bloco de concreto, tijolo, reboco)
    "alvenaria": [
        "clay_block_wall", "concrete_block_wall", "concrete_block_wall_02",
        "large_red_bricks", "broken_brick_wall", "slumped_mortar_brick",
        "rough_plaster_broken", "grey_plaster_02", "damaged_plaster",
    ],
    # madeira (formas, escoras de madeira, tapumes, pallets)
    "madeira": ["plywood", "oriented_strand_board", "raw_wooden_floor_01", "embedded_plank_flooring"],
    # metal (vergalhão, escoras metálicas, chapas, andaime)
    "metal": [
        "rust_coarse_01", "rusty_metal_04", "rusty_metal_grid", "corrugated_iron_02",
        "metal_plate_02", "blue_metal_plate",
    ],
    # chão solto e sacaria
    "chao": ["gravel_floor", "dirt", "hessian_230"],
}
MAPAS_TEX = ["Diffuse", "nor_dx", "arm", "Displacement"]

# ---------------- modelos (Poly Haven, glTF 2K) ----------------
MODELOS = [
    "cement_bag", "ladder_sectioned_01", "wooden_ladder", "flood_lights",
    "portable_generator", "modular_electric_cables", "power_box_01", "modular_pipes",
    "modular_airduct_circular_01", "modular_airduct_rectangular_01", "caged_hanging_light",
    "mounted_fluorescent_lights", "pull_chain_light_socket", "lightbulb_01",
    "industrial_wall_lamp", "hanging_industrial_lamp", "security_light",
    "metal_jerrycan", "plastic_jerrycan", "Barrel_02", "barrel_03", "hand_truck",
    "portable_welding_cart", "concrete_road_barrier", "WetFloorSign_01",
    "cardboard_box_01", "plastic_crate_02", "trashbag", "sledgehammer_01", "crowbar_01",
    "metal_toolbox", "tool_cart", "old_tyre", "propane_tank", "korean_fire_extinguisher_01",
    "Drill_01", "wooden_crate_02", "modular_chainlink_fence", "pipe_wrench",
    "industrial_pastic_container", "plastic_bottle_gallon", "old_military_compressor",
]

# ---------------- céus (Poly Haven, EXR) ----------------
CEUS = {
    "abandoned_construction": "4k",              # referência de obra (luz e reflexo)
    "kloofendal_overcast_puresky": "4k",          # céu nublado: luz suave pela tela
    "kloofendal_48d_partly_cloudy_puresky": "4k", # sol entre nuvens
    "rooftop_night": "2k",                        # para um modo noite
}

# ---------------- ambientCG (4K-JPG) ----------------
AMBIENTCG = {
    "telas": ["Net001A", "Net002A", "Net003A", "Net004A", "Net002B", "Fence003", "Fence006"],
    "decalques": ["Leaking001", "Leaking003", "Leaking006", "Leaking009", "Leaking012A",
                  "Leaking015A", "Leaking018A", "AsphaltDamage001", "TireTracks001"],
    "papelao": ["Cardboard001", "Cardboard004"],
}


def baixar(url, destino):
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return False
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        dados = r.read()
    tmp = destino + ".parcial"
    with open(tmp, "wb") as f:
        f.write(dados)
    os.replace(tmp, destino)
    return True


def json_de(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def texturas(base):
    for grupo, nomes in TEXTURAS.items():
        for nome in nomes:
            info = json_de(PH_API + nome)
            for mapa in MAPAS_TEX:
                if mapa not in info:
                    continue
                arq = info[mapa]["4k"]
                fmt = "png" if mapa == "Displacement" and "png" in arq else "jpg"
                url = arq[fmt]["url"]
                destino = os.path.join(base, "texturas", grupo, nome, os.path.basename(url))
                if baixar(url, destino):
                    print("textura", grupo, nome, mapa)


def baixar_gltf(info_gltf, pasta):
    """glTF do Poly Haven: arquivo principal + 'include' (bin e texturas)."""
    principal = info_gltf["gltf"]
    baixar(principal["url"], os.path.join(pasta, os.path.basename(principal["url"])))
    for rel, inc in principal.get("include", {}).items():
        baixar(inc["url"], os.path.join(pasta, rel))


def modelos(base):
    for nome in MODELOS:
        try:
            info = json_de(PH_API + nome)
        except Exception as e:  # nome que saiu do site
            print("PULADO (não achei)", nome, e)
            continue
        res = "2k" if "2k" in info["gltf"] else sorted(info["gltf"])[-1]
        pasta = os.path.join(base, "modelos", nome)
        if os.path.isdir(pasta) and os.listdir(pasta):
            continue
        baixar_gltf(info["gltf"][res], pasta)
        print("modelo", nome, res)


def ceus(base):
    for nome, res in CEUS.items():
        try:
            info = json_de(PH_API + nome)
        except Exception as e:
            print("PULADO (não achei)", nome, e)
            continue
        url = info["hdri"][res]["exr"]["url"]
        if baixar(url, os.path.join(base, "ceus", os.path.basename(url))):
            print("céu", nome, res)


def ambientcg(base):
    for grupo, ids in AMBIENTCG.items():
        for aid in ids:
            pasta = os.path.join(base, "texturas", grupo, aid)
            if os.path.isdir(pasta) and os.listdir(pasta):
                continue
            d = json_de(ACG_API + aid)
            achou = None
            for a in d.get("foundAssets", []):
                for c in a["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"]["downloads"]:
                    if c["attribute"] == "4K-JPG":
                        achou = c["downloadLink"]
            if not achou:
                print("PULADO (sem 4K)", aid)
                continue
            req = urllib.request.Request(achou, headers=UA)
            with urllib.request.urlopen(req, timeout=300) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            os.makedirs(pasta, exist_ok=True)
            for n in z.namelist():
                seguro = os.path.basename(n)  # nunca escrever fora da pasta
                if seguro and not n.endswith("/"):
                    with open(os.path.join(pasta, seguro), "wb") as f:
                        f.write(z.read(n))
            print("ambientCG", grupo, aid)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    destino = os.path.abspath(sys.argv[1])
    texturas(destino)
    modelos(destino)
    ceus(destino)
    ambientcg(destino)
    print("PRONTO:", destino)
