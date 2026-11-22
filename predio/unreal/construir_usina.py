"""Monta o MAPA 3 — USINA SIDERÚRGICA ABANDONADA no Unreal 5.8 (roda no editor com -ExecutePythonScript).

Entrada (no PC):
  D:/DronePredio/conteudo_usina/          FBX + layout_usina.json do blender/gerar_usina.py
  D:/DronePredio/recursos_usina/texturas/ texturas PBR (Poly Haven, CC0): <nome>/diff|nor_gl|arm.jpg
  D:/DronePredio/recursos_campo/...       texturas da fazenda (terra, madeira) e modelos de planta
  /Game/Campo/Modelos/                    arbustos, árvores e pedras já importados pela fazenda

1. materiais (aço enferrujado, chapa ondulada, tijolo, concreto, pintura velha, brasa...)
2. FBX do Blender (Nanite + colisão pela própria malha)
3. plantas tomando conta da usina (modelos da fazenda)
4. missões (coleta, entregas, fotos, engrenagens), aros, pontos do voo de teste, início
5. fim de tarde com névoa volumétrica (feixes de luz pelos buracos do telhado), brasa do alto-forno
6. salva /Game/Mapas/Usina e fecha o editor
"""
import json
import math
import os
import time
import traceback

import unreal

RAIZ = os.environ.get("PREDIO_RAIZ", "D:/DronePredio").replace("\\", "/")
CONTEUDO = RAIZ + "/conteudo_usina"
TEX_USINA = RAIZ + "/recursos_usina/texturas"
LOG = RAIZ + "/logs/construir_usina_progresso.txt"
PASTA = "/Game/Usina"
MAPA = "/Game/Mapas/Usina"

at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
T0 = time.time()


def log(*a):
    msg = "[%6.1fs] " % (time.time() - T0) + " ".join(str(x) for x in a)
    unreal.log(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def achar_recursos_campo():
    base = RAIZ + "/recursos_campo"
    for raiz, pastas, _ in os.walk(base):
        if "texturas" in pastas and "modelos" in pastas:
            return raiz.replace("\\", "/")
    return base + "/voo_e88/recursos"


TEX_CAMPO = achar_recursos_campo() + "/texturas"


# ----------------------------------------------------------------------------- importação
def importar(arquivo, destino, nome=None):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", arquivo)
    t.set_editor_property("destination_path", destino)
    if nome:
        t.set_editor_property("destination_name", nome)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    at.import_asset_tasks([t])
    return list(t.get_editor_property("imported_object_paths") or [])


def importar_textura(arquivo, destino, tipo):
    if not arquivo or not os.path.exists(arquivo):
        log("FALTA textura", arquivo)
        return None
    p = importar(arquivo, destino)
    if not p:
        log("FALHOU textura", arquivo)
        return None
    tex = unreal.load_asset(p[0])
    if tipo == "normal":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", True)
    elif tipo == "dados":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property("srgb", False)
    return tex


TEX = {}


def texturas(nome):
    if nome in TEX:
        return TEX[nome]
    pasta = None
    for base in (TEX_USINA, TEX_CAMPO):
        if os.path.isdir(base + "/" + nome):
            pasta = base + "/" + nome
            break
    if not pasta:
        log("FALTA pasta de textura", nome)
        TEX[nome] = None
        return None
    dest = PASTA + "/Texturas/" + nome
    r = (importar_textura(pasta + "/diff.jpg", dest, "cor"),
         importar_textura(pasta + "/nor_gl.jpg", dest, "normal"),
         importar_textura(pasta + "/arm.jpg", dest, "dados"))
    TEX[nome] = r if (r[0] and r[1] and r[2]) else None
    log("textura", nome, "ok" if TEX[nome] else "incompleta")
    return TEX[nome]


# ----------------------------------------------------------------------------- materiais
def novo_material(nome):
    caminho = PASTA + "/Materiais/" + nome
    if eal.does_asset_exist(caminho):
        eal.delete_asset(caminho)
    return at.create_asset(nome, PASTA + "/Materiais", unreal.Material, unreal.MaterialFactoryNew())


def expr(m, classe, x, y, **props):
    e = mel.create_material_expression(m, classe, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def ligar(a, sa, b, sb):
    mel.connect_material_expressions(a, sa, b, sb)


def rgb(m, fonte, saida, x, y):
    mk = expr(m, unreal.MaterialExpressionComponentMask, x, y, r=True, g=True, b=True, a=False)
    ligar(fonte, saida, mk, "")
    return mk


def const(m, v, x, y):
    return expr(m, unreal.MaterialExpressionConstant, x, y, r=float(v))


def lerp(m, a, b, alfa, x, y, sa="", sb="", salfa=""):
    l = expr(m, unreal.MaterialExpressionLinearInterpolate, x, y)
    ligar(a, sa, l, "A")
    ligar(b, sb, l, "B")
    ligar(alfa, salfa, l, "Alpha")
    return l


def mul(m, a, b, x, y, sa="", sb=""):
    e = expr(m, unreal.MaterialExpressionMultiply, x, y)
    ligar(a, sa, e, "A")
    ligar(b, sb, e, "B")
    return e


def amostra(m, tex, uv, x, y, tipo):
    st = {"cor": unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
          "normal": unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL,
          "dados": unreal.MaterialSamplerType.SAMPLERTYPE_MASKS}[tipo]
    s = expr(m, unreal.MaterialExpressionTextureSample, x, y, texture=tex, sampler_type=st)
    try:
        s.set_editor_property("sampler_source", unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
    except Exception:
        pass
    ligar(uv, "", s, "UVs")
    return s


def criar_mestre_pbr(tex):
    """PBR com textura, tinta, escala e sujeira (fuligem que escorre de cima: escurece embaixo de tudo)."""
    m = novo_material("M_UsinaPBR")
    tc = expr(m, unreal.MaterialExpressionTextureCoordinate, -1700, 0)
    esc = expr(m, unreal.MaterialExpressionScalarParameter, -1700, 120, parameter_name="Escala", default_value=1.0)
    uv = mul(m, tc, esc, -1500, 50)
    cor = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1250, -300, parameter_name="Cor", texture=tex[0])
    nrm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1250, 100, parameter_name="Normal", texture=tex[1],
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    orm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1250, 450, parameter_name="ORM", texture=tex[2],
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for s in (cor, nrm, orm):
        ligar(uv, "", s, "UVs")
    tinta = expr(m, unreal.MaterialExpressionVectorParameter, -1000, -450, parameter_name="Tinta",
                 default_value=unreal.LinearColor(1, 1, 1, 1))
    base = mul(m, rgb(m, cor, "", -1000, -300), rgb(m, tinta, "", -900, -450), -800, -350)
    # variação grande pelo mundo (manchas de sujeira) para não repetir igual em tudo
    pos = expr(m, unreal.MaterialExpressionWorldPosition, -1300, -650)
    msk = expr(m, unreal.MaterialExpressionComponentMask, -1150, -650, r=True, g=True, b=True, a=False)
    ligar(pos, "", msk, "")
    ruido = expr(m, unreal.MaterialExpressionNoise, -950, -650)
    for k, v in (("scale", 0.0012), ("levels", 4), ("output_min", 0.0), ("output_max", 1.0)):
        try:
            ruido.set_editor_property(k, v)
        except Exception:
            pass
    ligar(msk, "", ruido, "Position")
    sujo = lerp(m, const(m, 1.0, -800, -560), const(m, 0.62, -800, -500), ruido, -650, -600)
    final = mul(m, base, sujo, -500, -400)
    mel.connect_material_property(final, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rgb(m, nrm, "", -900, 100), "", unreal.MaterialProperty.MP_NORMAL)
    rm = expr(m, unreal.MaterialExpressionScalarParameter, -1000, 600, parameter_name="RugosidadeMult", default_value=1.0)
    rough = mul(m, orm, rm, -800, 520, sa="G")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mm = expr(m, unreal.MaterialExpressionScalarParameter, -1000, 700, parameter_name="MetalMult", default_value=1.0)
    met = mul(m, orm, mm, -800, 650, sa="B")
    mel.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(orm, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.recompile_material(m)
    return m


def criar_mestre_cor():
    m = novo_material("M_UsinaCor")
    cor = expr(m, unreal.MaterialExpressionVectorParameter, -800, -200, parameter_name="Cor",
               default_value=unreal.LinearColor(0.7, 0.7, 0.7, 1))
    c3 = rgb(m, cor, "", -600, -200)
    mel.connect_material_property(c3, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rug = expr(m, unreal.MaterialExpressionScalarParameter, -800, 0, parameter_name="Rugosidade", default_value=0.6)
    met = expr(m, unreal.MaterialExpressionScalarParameter, -800, 100, parameter_name="Metal", default_value=0.0)
    esp = expr(m, unreal.MaterialExpressionScalarParameter, -800, 200, parameter_name="Especular", default_value=0.5)
    emi = expr(m, unreal.MaterialExpressionScalarParameter, -800, 300, parameter_name="Brilho", default_value=0.0)
    e = mul(m, c3, emi, -500, 300)
    mel.connect_material_property(rug, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(esp, "", unreal.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    return m


def criar_brasa():
    """metal incandescente: laranja que pulsa devagar (calor ainda saindo da bica)."""
    m = novo_material("M_Brasa")
    tempo = expr(m, unreal.MaterialExpressionTime, -900, 200)
    t = mul(m, tempo, const(m, 1.3, -900, 300), -750, 250)
    sn = expr(m, unreal.MaterialExpressionSine, -620, 250)
    ligar(t, "", sn, "")
    pulso = lerp(m, const(m, 22.0, -620, 350), const(m, 38.0, -620, 420), sn, -480, 300)
    cor = expr(m, unreal.MaterialExpressionConstant3Vector, -620, 0, constant=unreal.LinearColor(1.0, 0.32, 0.04, 1))
    e = mul(m, cor, pulso, -330, 100)
    mel.connect_material_property(e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(expr(m, unreal.MaterialExpressionConstant3Vector, -330, -100,
                                       constant=unreal.LinearColor(0.2, 0.05, 0.01, 1)), "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(const(m, 0.9, -330, 300), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(m)
    return m


def criar_farol():
    m = novo_material("M_FarolUsina")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    tc = expr(m, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    v = expr(m, unreal.MaterialExpressionComponentMask, -750, 0, r=False, g=True, b=False, a=False)
    ligar(tc, "", v, "")
    inv = expr(m, unreal.MaterialExpressionOneMinus, -620, 0)
    ligar(v, "", inv, "")
    pw = expr(m, unreal.MaterialExpressionPower, -500, 0)
    ligar(inv, "", pw, "Base")
    ligar(const(m, 3.0, -620, 80), "", pw, "Exp")
    cor = expr(m, unreal.MaterialExpressionVectorParameter, -620, -200, parameter_name="Cor",
               default_value=unreal.LinearColor(1.0, 0.45, 0.05, 1))
    a = mul(m, rgb(m, cor, "", -480, -200), pw, -350, -100)
    b = mul(m, a, const(m, 2.5, -350, 0), -220, -100)
    mel.connect_material_property(b, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    return m


def criar_terreno():
    """brita/terra batida (base), asfalto velho (R), fuligem e minério escuro (G), terra (B)."""
    brita = texturas("gravel_road")
    asf = texturas("worn_asphalt") or brita
    terra = texturas("brown_mud_dry") or texturas("red_laterite_soil_stones") or brita
    if not brita:
        return None
    m = novo_material("M_TerrenoUsina")
    pos = expr(m, unreal.MaterialExpressionWorldPosition, -2200, 0)
    xy = expr(m, unreal.MaterialExpressionComponentMask, -2050, 0, r=True, g=True, b=False, a=False)
    ligar(pos, "", xy, "")
    uv = mul(m, xy, const(m, 1.0 / 450.0, -2050, 100), -1900, 0)          # 4,5 m por repetição
    uv_l = mul(m, xy, const(m, 1.0 / 1900.0, -2050, 200), -1900, 150)     # camada larga (quebra a repetição)
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1500, 700)
    camadas = []
    for k, (tx, u) in enumerate(((brita, uv), (asf, uv), (terra, uv))):
        y = k * 650 - 600
        c = amostra(m, tx[0], u, -1500, y, "cor")
        n = amostra(m, tx[1], u, -1500, y + 200, "normal")
        r = amostra(m, tx[2], u, -1500, y + 400, "dados")
        camadas.append((c, n, r))
    larga = amostra(m, brita[0], uv_l, -1500, 1400, "cor")
    cor = rgb(m, camadas[0][0], "", -1200, -600)
    nrm = rgb(m, camadas[0][1], "", -1200, -400)
    rug = camadas[0][2]
    rug_s = "G"
    for k, canal in ((2, "B"), (1, "R")):
        cor = lerp(m, cor, rgb(m, camadas[k][0], "", -1200, k * 650 - 600), vc, -900, k * 300 - 600, salfa=canal)
        nrm = lerp(m, nrm, rgb(m, camadas[k][1], "", -1200, k * 650 - 400), vc, -900, k * 300 - 450, salfa=canal)
        rug = lerp(m, rug, camadas[k][2], vc, -900, k * 300 - 300, sa=rug_s, sb="G", salfa=canal)
        rug_s = ""
    # fuligem (G) escurece; o pátio inteiro é sujo de pó de minério e carvão (bem mais escuro que a brita limpa)
    fuligem = lerp(m, const(m, 1.0, -700, 300), const(m, 0.16, -700, 360), vc, -550, 330, salfa="G")
    cor = mul(m, cor, fuligem, -400, 0)
    tom = expr(m, unreal.MaterialExpressionConstant3Vector, -550, 420, constant=unreal.LinearColor(0.5, 0.46, 0.41, 1))
    cor = mul(m, cor, tom, -350, 50)
    # variação larga
    var = lerp(m, const(m, 0.7, -700, 500), const(m, 1.2, -700, 560), larga, -550, 520, salfa="R")
    cor = mul(m, cor, var, -300, 100)
    mel.connect_material_property(cor, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nrm, "", unreal.MaterialProperty.MP_NORMAL)
    # chão seco: rugosidade alta sempre (a textura de terra deixava o pátio brilhando como se estivesse molhado)
    rug_final = lerp(m, const(m, 0.93, -500, 700), const(m, 0.82, -500, 760), vc, -350, 720, salfa="R")
    mel.connect_material_property(rug_final, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(const(m, 0.3, -350, 820), "", unreal.MaterialProperty.MP_SPECULAR)
    mel.recompile_material(m)
    log("material do terreno pronto")
    return m


# slot -> ("pbr", textura, tinta, escala, rug, metal) | ("cor", (r,g,b), rug, metal, brilho, especular)
SLOTS = {
    "ACO_FERRUGEM": ("pbr", "rusty_metal_02", (0.55, 0.47, 0.42), 1.0, 1.0, 1.0),
    "FERRUGEM_PESADA": ("pbr", "rust_coarse_01", (0.9, 0.85, 0.8), 0.5, 1.0, 1.0),
    "CHAPA_ONDULADA": ("pbr", "rusty_corrugated_iron", (0.85, 0.82, 0.8), 0.5, 1.0, 1.0),
    "TIJOLO": ("pbr", "factory_brick", (0.85, 0.8, 0.78), 1.0, 1.0, 0.0),
    "CONCRETO": ("pbr", "concrete_wall_008", (0.75, 0.73, 0.7), 1.0, 1.0, 0.0),
    "PISO": ("pbr", "damaged_concrete_floor", (1.0, 1.0, 1.0), 1.0, 1.0, 0.0),
    "CHAPA_PISO": ("pbr", "metal_plate", (0.75, 0.7, 0.65), 1.5, 1.0, 1.0),
    "PINTURA_AMARELA": ("pbr", "rusty_painted_metal", (1.6, 1.25, 0.35), 0.8, 1.0, 1.0),
    "CHAPA_PINTADA": ("pbr", "rusty_painted_metal", (0.85, 0.9, 1.0), 0.8, 1.0, 1.0),
    "PINTURA_VERDE": ("pbr", "green_metal_rust", (0.9, 0.95, 0.9), 0.5, 1.0, 1.0),
    "PAREDE_VELHA": ("pbr", "concrete_wall_008", (0.62, 0.6, 0.55), 1.0, 1.0, 0.0),
    "MADEIRA": ("pbr", "fine_grained_wood", (0.45, 0.36, 0.27), 1.0, 1.2, 0.0),
    "BRITA": ("pbr", "gravel_road", (0.6, 0.58, 0.55), 1.0, 1.0, 0.0),
    "BASE": ("pbr", "concrete_floor_worn_001", (0.5, 0.5, 0.48), 1.0, 1.0, 0.0),
    "GUARDA_CORPO": ("cor", (0.62, 0.42, 0.06), 0.65, 0.3, 0.0, 0.5),
    "TRILHO": ("cor", (0.38, 0.33, 0.30), 0.35, 1.0, 0.0, 0.5),
    "CABO": ("cor", (0.06, 0.055, 0.05), 0.55, 0.8, 0.0, 0.5),
    "BORRACHA": ("cor", (0.03, 0.03, 0.03), 0.9, 0.0, 0.0, 0.3),
    "MINERIO": ("cor", (0.17, 0.08, 0.05), 0.95, 0.0, 0.0, 0.3),
    "CARVAO": ("cor", (0.025, 0.025, 0.025), 0.8, 0.0, 0.0, 0.4),
    "ESCORIA": ("cor", (0.09, 0.085, 0.08), 0.7, 0.4, 0.0, 0.4),
    "FULIGEM": ("cor", (0.02, 0.02, 0.02), 0.95, 0.0, 0.0, 0.2),
    "ESCURO": ("cor", (0.005, 0.005, 0.005), 1.0, 0.0, 0.0, 0.0),
    "VIDRO_SUJO": ("cor", (0.05, 0.05, 0.045), 0.25, 0.0, 0.0, 0.7),
    "PINTURA_BRANCA": ("cor", (0.8, 0.8, 0.78), 0.6, 0.0, 0.0, 0.5),
    "CAIXA_PECAS": ("cor", (0.12, 0.2, 0.35), 0.5, 0.6, 0.0, 0.5),
    "PANO": ("cor", (0.95, 0.35, 0.06), 0.85, 0.0, 0.0, 0.4),
    "ARO_PRETO": ("cor", (0.02, 0.02, 0.02), 0.5, 0.0, 0.0, 0.5),
    "ARO": ("cor", (0.95, 0.30, 0.04), 0.45, 0.0, 0.6, 0.5),
    "OURO": ("cor", (1.0, 0.72, 0.18), 0.22, 1.0, 0.35, 0.5),
    "POCA": ("cor", (0.015, 0.016, 0.018), 0.03, 0.0, 0.0, 1.0),
}


def criar_materiais():
    if eal.does_directory_exist(PASTA + "/Materiais"):
        eal.delete_directory(PASTA + "/Materiais")
    mis = {}
    ter = criar_terreno()
    if ter:
        mis["TERRENO"] = ter
    base = texturas("rusty_metal_02")
    mestre_pbr = criar_mestre_pbr(base) if base else None
    mestre_cor = criar_mestre_cor()
    fac = unreal.MaterialInstanceConstantFactoryNew()
    for slot, d in SLOTS.items():
        mi = at.create_asset("MI_" + slot, PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
        tx = texturas(d[1]) if d[0] == "pbr" else None
        if d[0] == "pbr" and tx and mestre_pbr:
            mi.set_editor_property("parent", mestre_pbr)
            mel.set_material_instance_texture_parameter_value(mi, "Cor", tx[0])
            mel.set_material_instance_texture_parameter_value(mi, "Normal", tx[1])
            mel.set_material_instance_texture_parameter_value(mi, "ORM", tx[2])
            mel.set_material_instance_vector_parameter_value(mi, "Tinta", unreal.LinearColor(*d[2], 1))
            mel.set_material_instance_scalar_parameter_value(mi, "Escala", d[3])
            mel.set_material_instance_scalar_parameter_value(mi, "RugosidadeMult", d[4])
            mel.set_material_instance_scalar_parameter_value(mi, "MetalMult", d[5])
        else:
            mi.set_editor_property("parent", mestre_cor)
            if d[0] == "pbr":
                cor, rug, met, bri, esp = (0.35, 0.25, 0.2), 0.8, 0.0, 0.0, 0.5
            else:
                cor, rug, met, bri, esp = d[1], d[2], d[3], d[4], d[5]
            mel.set_material_instance_vector_parameter_value(mi, "Cor", unreal.LinearColor(*cor, 1))
            mel.set_material_instance_scalar_parameter_value(mi, "Rugosidade", rug)
            mel.set_material_instance_scalar_parameter_value(mi, "Metal", met)
            mel.set_material_instance_scalar_parameter_value(mi, "Brilho", bri)
            mel.set_material_instance_scalar_parameter_value(mi, "Especular", esp)
        mel.update_material_instance(mi)
        mis[slot] = mi
    if "TERRENO" not in mis:
        mis["TERRENO"] = mis["BRITA"]
    mis["BRASA"] = criar_brasa()
    mis["FAROL"] = criar_farol()
    log("materiais prontos:", len(mis))
    return mis


# ----------------------------------------------------------------------------- malhas
def material_do_slot(nome, mis):
    n = nome.upper()
    if n in mis:
        return mis[n]
    for chave in sorted(mis, key=len, reverse=True):
        if n.startswith(chave):
            return mis[chave]
    return None


def nanite(sm, ligar_nanite=True):
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", ligar_nanite)
    try:
        ns.set_editor_property("fallback_relative_error", 0.0)
    except Exception:
        pass
    sm.set_editor_property("nanite_settings", ns)


def colisao_complexa(sm):
    try:
        bs = sm.get_editor_property("body_setup")
        if bs:
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    except Exception as e:
        log("colisão falhou", sm.get_name(), e)


MODELOS_JOGO = ("CaixaEntrega", "Engrenagem", "Farol")
SEM_NANITE = ("Marcador", "Farol", "CaixaEntrega", "Engrenagem", "Aro", "Haste")


def importar_malhas(mis):
    malhas = {}
    if eal.does_directory_exist(PASTA + "/Malhas"):
        eal.delete_directory(PASTA + "/Malhas")
    for arq in sorted(os.listdir(CONTEUDO)):
        if not arq.lower().endswith(".fbx"):
            continue
        nome = arq[:-4]
        caminhos = importar(CONTEUDO + "/" + arq, PASTA + "/Malhas/" + nome)
        sms = [unreal.load_asset(p) for p in caminhos]
        sms = [a for a in sms if isinstance(a, unreal.StaticMesh)]
        if not sms:
            log("FALHOU malha", arq, caminhos)
            continue
        sm = sms[0]
        for i, smat in enumerate(sm.get_editor_property("static_materials")):
            alvo = material_do_slot(str(smat.get_editor_property("material_slot_name")), mis)
            if alvo:
                sm.set_material(i, alvo)
            else:
                log("  slot sem material:", nome, smat.get_editor_property("material_slot_name"))
        nanite(sm, nome not in SEM_NANITE)
        if nome not in ("Marcador", "Pocas") + MODELOS_JOGO:
            colisao_complexa(sm)
        eal.save_loaded_asset(sm)
        malhas[nome] = sm
        log("malha", nome)
    return malhas


def carregar_sm(pasta):
    if not eal.does_directory_exist(pasta):
        return []
    res = []
    for p in eal.list_assets(pasta, recursive=True, include_folder=False):
        a = eal.load_asset(p)
        if isinstance(a, unreal.StaticMesh):
            res.append(a)
    return res


# ----------------------------------------------------------------------------- mapa
def por(obj, nomes, valor):
    if isinstance(nomes, str):
        nomes = [nomes]
    for n in nomes:
        try:
            obj.set_editor_property(n, valor)
            return True
        except Exception:
            continue
    log("  propriedade não encontrada:", nomes)
    return False


def tag(ator, *nomes):
    ator.set_editor_property("tags", [unreal.Name(n) for n in nomes])


def montar_mapa(layout, malhas):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mundo = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    log("mapa em branco:", mundo)

    marc = malhas.get("Marcador")
    sx, sy, escala = 1.0, -1.0, 100.0
    if marc:
        bb = marc.get_bounding_box()
        cx, cy = (bb.min.x + bb.max.x) / 2, (bb.min.y + bb.max.y) / 2
        log("marcador centro", cx, cy, "(esperado 2000, -500)")
        if abs(cx) > 1:
            escala = abs(cx) / 20.0
            sx = 1.0 if cx > 0 else -1.0
            sy = 1.0 if cy > 0 else -1.0
    log("eixos: escala", escala, "sinal X", sx, "sinal Y", sy)

    def P(x, y, z):
        return unreal.Vector(x * escala * sx, y * escala * sy, z * escala)

    def yaw(graus):
        r = math.radians(graus)
        return math.degrees(math.atan2(sy * math.sin(r), sx * math.cos(r)))

    for nome, sm in malhas.items():
        if nome in ("Marcador", "Aro", "Haste") + MODELOS_JOGO:
            continue
        a = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        a.set_actor_label(nome)
        tag(a, "Terreno" if nome == "Terreno" else nome)
        if nome == "Pocas":
            a.set_actor_enable_collision(False)

    # plantas (modelos da fazenda)
    n = 0
    cache = {}
    for i, p in enumerate(layout.get("plantas", [])):
        if p["modelo"] not in cache:
            cache[p["modelo"]] = carregar_sm("/Game/Campo/Modelos/" + p["modelo"])
            if not cache[p["modelo"]] and p["modelo"] == "grass_medium_01":
                # a fazenda usa o próprio capim (touceira do Blender) no lugar do glTF
                cache[p["modelo"]] = carregar_sm("/Game/Campo/Malhas/Capim") or carregar_sm("/Game/Campo/Malhas/Palha")
            if not cache[p["modelo"]]:
                log("FALTA modelo de planta (rode a fazenda antes):", p["modelo"])
        for k, sm in enumerate(cache[p["modelo"]]):
            a = eas.spawn_actor_from_object(sm, P(p["x"], p["y"], p["z"]), unreal.Rotator(0, 0, yaw(p["yaw"])))
            a.set_actor_scale3d(unreal.Vector(p["sx"], p["sy"], p["sz"]))
            a.set_actor_label("%s_%03d_%d" % (p["modelo"], i, k))
            tag(a, "Planta")
            if p["modelo"] == "grass_medium_01":
                a.set_actor_enable_collision(False)
                c = a.get_component_by_class(unreal.StaticMeshComponent)
                por(c, "cast_shadow", False)
            n += 1
    log("plantas:", n)

    for nome_tag, sm in (("ModeloCaixa", malhas.get("CaixaEntrega")), ("ModeloFarol", malhas.get("Farol"))):
        if not sm:
            log("FALTA modelo do jogo", nome_tag)
            continue
        g = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, -100000), unreal.Rotator(0, 0, 0))
        g.set_actor_label(nome_tag)
        g.set_actor_enable_collision(False)
        g.set_actor_hidden_in_game(True)
        tag(g, nome_tag)

    def ponto(rotulo, pos, *tags):
        e = eas.spawn_actor_from_class(unreal.TargetPoint, P(*pos), unreal.Rotator(0, 0, 0))
        e.set_actor_label(rotulo)
        tag(e, *tags)
    ponto("Coleta", layout["coleta"], "Coleta")
    for i, en in enumerate(layout["entregas"]):
        ponto("Entrega_%d" % i, en["pos"], "Entrega_%d" % i, "Nome:" + en["nome"])
    for i, fo in enumerate(layout["fotos"]):
        ponto("Foto_%d" % i, fo["pos"], "Foto_%d" % i, "Nome:" + fo["nome"])
    eng = malhas.get("Engrenagem")
    for i, pos in enumerate(layout["ferraduras"]):
        if not eng:
            break
        a = eas.spawn_actor_from_object(eng, P(*pos), unreal.Rotator(0, 0, 0))
        a.set_actor_label("Engrenagem_%02d" % i)
        a.set_actor_enable_collision(False)
        a.set_actor_scale3d(unreal.Vector(2.0, 2.0, 2.0))
        tag(a, "Ferradura_%d" % i)
        a.get_component_by_class(unreal.StaticMeshComponent).set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    log("missões: entregas", len(layout["entregas"]), "fotos", len(layout["fotos"]), "engrenagens", len(layout["ferraduras"]))

    aro, haste = malhas.get("Aro"), malhas.get("Haste")
    for r in layout["aros"]:
        if not aro:
            break
        a = eas.spawn_actor_from_object(aro, P(r["x"], r["y"], r["z"]), unreal.Rotator(0, 0, yaw(r["yaw"])))
        a.set_actor_label("Aro_%02d" % (r["n"] + 1))
        tag(a, "Aro_%d" % r["n"], "Rota_%d" % r["n"])
        base_aro = r["z"] - 2.35
        if haste and r.get("haste") and base_aro - r["chao"] > 0.3:
            h = eas.spawn_actor_from_object(haste, P(r["x"], r["y"], r["chao"] - 0.2), unreal.Rotator(0, 0, 0))
            h.set_actor_scale3d(unreal.Vector(1, 1, base_aro - r["chao"] + 0.25))
            h.set_actor_label("Haste_%02d" % (r["n"] + 1))
    log("aros:", len(layout["aros"]))
    for i, v in enumerate(layout.get("vistas", [])):
        e = eas.spawn_actor_from_class(unreal.TargetPoint, P(v["x"], v["y"], v["z"]), unreal.Rotator(0, 0, yaw(v["yaw"])))
        e.set_actor_label("Vista_%02d" % i)
        tag(e, "Rota_%d" % (50 + i))

    L = layout["limites"]
    a, b = P(L["x0"], L["y0"], 0), P(L["x1"], L["y1"], 0)
    info = eas.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(0, 0, -5000), unreal.Rotator(0, 0, 0))
    info.set_actor_label("InfoUsina")
    tag(info, "AroRaio_%d" % int(layout.get("raio_aro", 2.05) * escala), "AlturaAndar_100000", "CotaTerreo_-100000",
        "Limites_%d_%d_%d_%d_%d" % (int(min(a.x, b.x)), int(min(a.y, b.y)), int(max(a.x, b.x)), int(max(a.y, b.y)), int(L["z1"] * escala)))

    ini = layout["inicio"]
    ps = eas.spawn_actor_from_class(unreal.PlayerStart, P(ini["x"], ini["y"], ini["z"] + 0.6), unreal.Rotator(0, 0, yaw(ini["yaw"])))
    ps.set_actor_label("InicioDrone")

    # ---- fim de tarde: sol baixo do oeste, alaranjado; névoa volumétrica para os feixes de luz
    sol = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 5000),
                                     unreal.Rotator(roll=0, pitch=-24, yaw=yaw(-25)))
    lc = sol.get_component_by_class(unreal.DirectionalLightComponent)
    por(lc, "intensity", 9.0)
    por(lc, "use_temperature", True)
    por(lc, "temperature", 4300.0)
    por(lc, "atmosphere_sun_light", True)
    por(lc, "light_source_angle", 0.8)
    por(lc, "shadow_amount", 0.9)
    por(lc, "volumetric_scattering_intensity", 1.5)
    por(lc, "mobility", unreal.ComponentMobility.MOVABLE)
    sol.set_actor_label("Sol")
    eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)).set_actor_label("Ceu")
    try:
        nv = eas.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        nv.set_actor_label("Nuvens")
    except Exception as e:
        log("sem nuvens volumétricas:", e)
    sky = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, 0, 0))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    por(sc, "real_time_capture", True)
    por(sc, "mobility", unreal.ComponentMobility.MOVABLE)
    por(sc, "intensity", 1.3)
    sky.set_actor_label("LuzDoCeu")
    for i, lz in enumerate(layout.get("luzes", [])):
        pl = eas.spawn_actor_from_class(unreal.PointLight, P(lz["x"], lz["y"], lz["z"]), unreal.Rotator(0, 0, 0))
        plc = pl.get_component_by_class(unreal.PointLightComponent)
        c = lz.get("cor", [255, 196, 130])
        por(plc, "intensity", float(lz.get("intensidade", 1500.0)))
        por(plc, "attenuation_radius", float(lz.get("raio", 800.0)))
        por(plc, "light_color", unreal.Color(r=c[0], g=c[1], b=c[2], a=255))
        por(plc, "source_radius", 20.0)
        por(plc, "cast_shadows", i < 2)
        por(plc, "mobility", unreal.ComponentMobility.MOVABLE)
        pl.set_actor_label("Luz_%d" % i)
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    por(fc, "fog_density", 0.006)
    por(fc, "start_distance", 2500.0)
    por(fc, "fog_height_falloff", 0.15)
    por(fc, "fog_inscattering_luminance", unreal.LinearColor(0.45, 0.4, 0.34, 1.0))
    por(fc, ["enable_volumetric_fog", "volumetric_fog"], True)
    por(fc, "volumetric_fog_scattering_distribution", 0.7)
    por(fc, "volumetric_fog_extinction_scale", 0.45)
    por(fc, "volumetric_fog_albedo", unreal.Color(r=190, g=178, b=165, a=255))
    por(fc, "volumetric_fog_distance", 9000.0)
    fog.set_actor_label("Neblina")

    ppv = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")

    def ov(nome, valor):
        try:
            s.set_editor_property("override_" + nome, True)
            s.set_editor_property(nome, valor)
        except Exception as e:
            log("  pp ignorado", nome, e)
    ov("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
    ov("auto_exposure_min_brightness", 0.0)
    ov("auto_exposure_max_brightness", 14.0)
    ov("auto_exposure_bias", 0.0)
    ov("local_exposure_shadow_contrast_scale", 0.75)
    ov("local_exposure_highlight_contrast_scale", 0.8)
    ov("lumen_scene_lighting_quality", 1.5)
    ov("lumen_final_gather_quality", 1.5)
    ov("lumen_max_trace_distance", 20000.0)
    ov("lumen_skylight_leaking", 0.18)
    ov("bloom_intensity", 0.45)
    ov("color_saturation", unreal.Vector4(1.02, 1.0, 0.96, 1.0))
    ov("color_contrast", unreal.Vector4(1.05, 1.05, 1.05, 1.0))
    ov("color_gain", unreal.Vector4(1.03, 1.0, 0.95, 1.0))
    ov("film_toe", 0.56)
    ov("vignette_intensity", 0.3)
    ppv.set_editor_property("settings", s)
    ppv.set_actor_label("PosProcesso")

    ok = unreal.EditorLoadingAndSavingUtils.save_map(mundo, MAPA)
    log("mapa salvo em", MAPA, ok, "atores:", len(eas.get_all_level_actors()))


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("construir_usina.py\n")
    try:
        with open(CONTEUDO + "/layout_usina.json", encoding="utf-8") as fp:
            layout = json.load(fp)
        mis = criar_materiais()
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        malhas = importar_malhas(mis)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        montar_mapa(layout, malhas)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("TUDO PRONTO")
    except Exception:
        log("FALHA GERAL:\n" + traceback.format_exc())
    finally:
        if os.environ.get("PREDIO_NAO_FECHAR") != "1":
            unreal.SystemLibrary.quit_editor()


main()
