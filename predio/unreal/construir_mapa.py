"""Monta o mapa do prédio dentro do Unreal 5.8 (roda no editor com -ExecutePythonScript).

1. importa as texturas 4K (Poly Haven / ambientCG) e cria os materiais PBR
2. importa os andares (FBX do Blender) como Nanite, colisão complexa
3. importa os objetos do Poly Haven (glTF) e põe no lugar
4. luzes de obra, sol de fim de tarde, céu, névoa volumétrica, pós-processo
5. pontos de rota (invisíveis, só para o voo de teste), ligações verticais, início do drone
6. salva /Game/Mapas/Predio e fecha o editor

Tudo é refeito do zero a cada execução (apaga /Game/Predio e o mapa).
"""
import json
import math
import os
import time
import traceback

import unreal

RAIZ = os.environ.get("PREDIO_RAIZ", "D:/DronePredio").replace("\\", "/")
CONTEUDO = RAIZ + "/conteudo"          # FBX + layout.json do Blender
RECURSOS = RAIZ + "/recursos"          # texturas / modelos baixados
LOG = RAIZ + "/logs/construir_mapa_progresso.txt"
PASTA = "/Game/Predio"
MAPA = "/Game/Mapas/Predio"

at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
T0 = time.time()


def log(*a):
    msg = "[%6.1fs] " % (time.time() - T0) + " ".join(str(x) for x in a)
    unreal.log(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ----------------------------------------------------------------------------- importação
def importar(arquivo, destino, nome=None, opcoes=None):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", arquivo)
    t.set_editor_property("destination_path", destino)
    if nome:
        t.set_editor_property("destination_name", nome)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    if opcoes is not None:
        t.set_editor_property("options", opcoes)
    at.import_asset_tasks([t])
    return list(t.get_editor_property("imported_object_paths") or [])


def importar_textura(arquivo, destino, tipo):
    p = importar(arquivo, destino)
    if not p:
        log("FALHOU textura", arquivo)
        return None
    tex = unreal.load_asset(p[0])
    if tipo == "normal":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", False)
    elif tipo == "dados":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property("srgb", False)
    elif tipo == "cinza":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
        tex.set_editor_property("srgb", False)
    return tex


# ----------------------------------------------------------------------------- materiais mestres
def novo_material(nome, mascarado=False, emissivo=False):
    caminho = PASTA + "/Materiais"
    m = at.create_asset(nome, caminho, unreal.Material, unreal.MaterialFactoryNew())
    if mascarado:
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        m.set_editor_property("two_sided", True)
    if emissivo:
        m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    return m


def expr(m, classe, x, y, **props):
    e = mel.create_material_expression(m, classe, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def ligar(a, sa, b, sb):
    mel.connect_material_expressions(a, sa, b, sb)


def rgb(m, fonte, saida, x, y):
    """máscara RGB (tira o alfa) para não misturar float3 com float4."""
    mk = expr(m, unreal.MaterialExpressionComponentMask, x, y, r=True, g=True, b=True, a=False)
    ligar(fonte, saida, mk, "")
    return mk


def dessaturar(m, cor_rgb, fracao, x, y):
    lum = expr(m, unreal.MaterialExpressionConstant3Vector, x - 200, y + 120,
               constant=unreal.LinearColor(0.3, 0.59, 0.11, 1))
    dot = expr(m, unreal.MaterialExpressionDotProduct, x - 100, y + 60)
    ligar(cor_rgb, "", dot, "A")
    ligar(lum, "", dot, "B")
    lp = expr(m, unreal.MaterialExpressionLinearInterpolate, x, y)
    ligar(cor_rgb, "", lp, "A")
    ligar(dot, "", lp, "B")
    ligar(fracao, "", lp, "Alpha")
    return lp


def criar_mestre_opaco(tex_cor, tex_nrm, tex_orm):
    m = novo_material("M_Obra")
    cor = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1400, -300, parameter_name="Cor", texture=tex_cor)
    nrm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1400, 100, parameter_name="Normal", texture=tex_nrm,
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    orm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1400, 450, parameter_name="ORM", texture=tex_orm,
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    # cor: dessatura -> tinge -> vertex color
    p_dess = expr(m, unreal.MaterialExpressionScalarParameter, -1300, -150, parameter_name="Dessaturar", default_value=0.0)
    cor3 = rgb(m, cor, "", -1250, -300)
    dess = dessaturar(m, cor3, p_dess, -1050, -300)
    tint = expr(m, unreal.MaterialExpressionVectorParameter, -1100, -450, parameter_name="Tinta",
                default_value=unreal.LinearColor(1, 1, 1, 1))
    tint3 = rgb(m, tint, "", -950, -450)
    mult1 = expr(m, unreal.MaterialExpressionMultiply, -900, -350)
    ligar(dess, "", mult1, "A")
    ligar(tint3, "", mult1, "B")
    vc0 = expr(m, unreal.MaterialExpressionVertexColor, -1250, -600)
    vc = rgb(m, vc0, "", -1100, -600)
    p_vc = expr(m, unreal.MaterialExpressionScalarParameter, -1100, -700, parameter_name="PesoVertexColor", default_value=0.0)
    um = expr(m, unreal.MaterialExpressionConstant3Vector, -1100, -800, constant=unreal.LinearColor(1, 1, 1, 1))
    lerp_vc = expr(m, unreal.MaterialExpressionLinearInterpolate, -850, -650)
    ligar(um, "", lerp_vc, "A")
    ligar(vc, "", lerp_vc, "B")
    ligar(p_vc, "", lerp_vc, "Alpha")
    mult2 = expr(m, unreal.MaterialExpressionMultiply, -650, -400)
    ligar(mult1, "", mult2, "A")
    ligar(lerp_vc, "", mult2, "B")
    mel.connect_material_property(mult2, "", unreal.MaterialProperty.MP_BASE_COLOR)
    # normal com intensidade
    p_ni = expr(m, unreal.MaterialExpressionScalarParameter, -1100, 250, parameter_name="ForcaNormal", default_value=1.0)
    flat = expr(m, unreal.MaterialExpressionConstant3Vector, -1100, 320, constant=unreal.LinearColor(0, 0, 1, 1))
    lerp_n = expr(m, unreal.MaterialExpressionLinearInterpolate, -800, 150)
    nrm3 = rgb(m, nrm, "", -1000, 150)
    ligar(flat, "", lerp_n, "A")
    ligar(nrm3, "", lerp_n, "B")
    ligar(p_ni, "", lerp_n, "Alpha")
    mel.connect_material_property(lerp_n, "", unreal.MaterialProperty.MP_NORMAL)
    # ORM
    p_rm = expr(m, unreal.MaterialExpressionScalarParameter, -1100, 600, parameter_name="RugosidadeMult", default_value=1.0)
    rough = expr(m, unreal.MaterialExpressionMultiply, -800, 520)
    ligar(orm, "G", rough, "A")
    ligar(p_rm, "", rough, "B")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    p_me = expr(m, unreal.MaterialExpressionScalarParameter, -1100, 700, parameter_name="MetalMult", default_value=1.0)
    metal = expr(m, unreal.MaterialExpressionMultiply, -800, 680)
    ligar(orm, "B", metal, "A")
    ligar(p_me, "", metal, "B")
    mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(orm, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    p_sp = expr(m, unreal.MaterialExpressionScalarParameter, -800, 800, parameter_name="Especular", default_value=0.5)
    mel.connect_material_property(p_sp, "", unreal.MaterialProperty.MP_SPECULAR)
    mel.recompile_material(m)
    return m


def criar_mestre_tela(tex_cor, tex_nrm, tex_op, tex_ru):
    m = novo_material("M_Tela", mascarado=True)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    cor = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1200, -200, parameter_name="Cor", texture=tex_cor)
    nrm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1200, 150, parameter_name="Normal", texture=tex_nrm,
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    op = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1200, 450, parameter_name="Opacidade", texture=tex_op,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    ru = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1200, 750, parameter_name="Rugosidade", texture=tex_ru,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    tint = expr(m, unreal.MaterialExpressionVectorParameter, -900, -350, parameter_name="Tinta",
                default_value=unreal.LinearColor(0.05, 0.30, 0.09, 1))
    tint3 = rgb(m, tint, "", -750, -350)
    um = expr(m, unreal.MaterialExpressionConstant, -1000, -100, r=1.0)
    cor3 = rgb(m, cor, "", -1000, -200)
    dess = dessaturar(m, cor3, um, -850, -200)
    mul = expr(m, unreal.MaterialExpressionMultiply, -600, -250)
    ligar(dess, "", mul, "A")
    ligar(tint3, "", mul, "B")
    mul2 = expr(m, unreal.MaterialExpressionMultiply, -450, -250)
    dois = expr(m, unreal.MaterialExpressionConstant, -600, -120, r=1.6)
    ligar(mul, "", mul2, "A")
    ligar(dois, "", mul2, "B")
    mel.connect_material_property(mul2, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rgb(m, nrm, "", -800, 150), "", unreal.MaterialProperty.MP_NORMAL)
    inv = expr(m, unreal.MaterialExpressionOneMinus, -800, 450)
    ligar(op, "R", inv, "")
    mel.connect_material_property(inv, "", unreal.MaterialProperty.MP_OPACITY_MASK)
    mel.connect_material_property(ru, "R", unreal.MaterialProperty.MP_ROUGHNESS)
    sub = expr(m, unreal.MaterialExpressionMultiply, -450, 0)
    ligar(mul, "", sub, "A")
    meio = expr(m, unreal.MaterialExpressionConstant, -600, 60, r=0.8)
    ligar(meio, "", sub, "B")
    mel.connect_material_property(sub, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    m.set_editor_property("opacity_mask_clip_value", 0.4)
    mel.recompile_material(m)
    return m


def criar_decalques(layout):
    """Material de decalque + uma instância por textura do ambientCG usada no layout."""
    usados = sorted({d["tex"] for d in layout.get("decalques", [])})
    if not usados:
        return {}
    m = novo_material("M_Decalque")
    m.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mis = {}
    texs = {}
    for t in usados:
        pasta = os.path.join(RECURSOS, "texturas", "decalques", t)
        if not os.path.isdir(pasta):
            log("FALTA decalque", t)
            continue
        fs = os.listdir(pasta)
        def ach(suf):
            r = [os.path.join(pasta, f).replace("\\", "/") for f in fs if f.endswith(suf)]
            return r[0] if r else None
        dest = PASTA + "/Texturas/Decalques/" + t
        cor = importar_textura(ach("_Color.jpg"), dest, "cor")
        op = importar_textura(ach("_Opacity.jpg"), dest, "cinza") if ach("_Opacity.jpg") else None
        nr = importar_textura(ach("_NormalDX.jpg"), dest, "normal") if ach("_NormalDX.jpg") else None
        texs[t] = (cor, op, nr)
    if not texs:
        return {}
    c0, o0, n0 = next(iter(texs.values()))
    cor = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, -200, parameter_name="Cor", texture=c0)
    op = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, 150, parameter_name="Opacidade", texture=o0 or c0,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    nr = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, 450, parameter_name="Normal", texture=n0,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    forca = expr(m, unreal.MaterialExpressionScalarParameter, -900, 300, parameter_name="Forca", default_value=0.85)
    mul = expr(m, unreal.MaterialExpressionMultiply, -500, 150)
    ligar(op, "R", mul, "A")
    ligar(forca, "", mul, "B")
    mel.connect_material_property(rgb(m, cor, "", -600, -200), "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_OPACITY)
    mel.connect_material_property(rgb(m, nr, "", -600, 450), "", unreal.MaterialProperty.MP_NORMAL)
    ru = expr(m, unreal.MaterialExpressionConstant, -500, 600, r=0.55)
    mel.connect_material_property(ru, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(m)
    fac = unreal.MaterialInstanceConstantFactoryNew()
    for t, (c, o, n) in texs.items():
        mi = at.create_asset("MI_Decal_" + t, PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
        mi.set_editor_property("parent", m)
        mel.set_material_instance_texture_parameter_value(mi, "Cor", c)
        if o:
            mel.set_material_instance_texture_parameter_value(mi, "Opacidade", o)
        if n:
            mel.set_material_instance_texture_parameter_value(mi, "Normal", n)
        mel.update_material_instance(mi)
        mis[t] = mi
    log("decalques:", len(mis))
    return mis


def criar_mestre_emissivo():
    m = novo_material("M_Luz", emissivo=True)
    cor = expr(m, unreal.MaterialExpressionVectorParameter, -600, 0, parameter_name="Cor",
               default_value=unreal.LinearColor(1.0, 0.35, 0.02, 1))
    forca = expr(m, unreal.MaterialExpressionScalarParameter, -600, 200, parameter_name="Forca", default_value=20.0)
    mul = expr(m, unreal.MaterialExpressionMultiply, -300, 50)
    ligar(rgb(m, cor, "", -450, 0), "", mul, "A")
    ligar(forca, "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    return m


# material de cada "slot" vindo do Blender: (textura, tinta, dessaturar, peso_vc, rug_mult, metal_mult, forca_normal)
MATERIAIS = {
    "CONCRETO_ESTRUTURA": ("concreto/concrete_wall_006", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "CONCRETO_PISO": ("concreto/concrete_floor_worn_001", (0.95, 0.94, 0.92), 0.0, 0.0, 0.9, 0.0, 1.0),
    "CONCRETO_TETO": ("concreto/concrete_wall_008", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "CONCRETO_SUJO": ("concreto/dirty_concrete", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "CERAMICA": ("concreto/scuffed_cement", (0.78, 0.36, 0.20), 1.0, 1.0, 1.05, 0.0, 1.4),
    "ARGAMASSA": ("alvenaria/grey_plaster_02", (0.72, 0.70, 0.66), 0.4, 0.0, 1.0, 0.0, 1.0),
    "REBOCO": ("alvenaria/grey_plaster_02", (0.95, 0.93, 0.9), 0.0, 0.0, 1.0, 0.0, 1.0),
    "COMPENSADO": ("madeira/plywood", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "MADEIRA": ("madeira/raw_wooden_floor_01", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "METAL_ESCORA": ("metal/metal_plate_02", (1.7, 1.7, 1.7), 1.0, 1.0, 0.8, 0.3, 1.0),
    "FERRUGEM": ("metal/rust_coarse_01", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 1.0, 1.0),
    "METAL_GALV": ("metal/metal_plate_02", (0.85, 0.86, 0.88), 1.0, 0.0, 0.7, 1.0, 0.6),
    "TERRA": ("chao/dirt", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "BRITA": ("chao/gravel_floor", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
    "AREIA": ("chao/dirt", (1.35, 1.12, 0.82), 0.3, 0.0, 1.0, 0.0, 0.6),
    "PVC": ("alvenaria/grey_plaster_02", (0.92, 0.92, 0.9), 1.0, 0.0, 0.45, 0.0, 0.15),
    "ELETRODUTO": ("alvenaria/grey_plaster_02", (0.95, 0.66, 0.04), 1.0, 0.0, 0.5, 0.0, 0.15),
    "BORRACHA": ("alvenaria/grey_plaster_02", (0.05, 0.05, 0.05), 1.0, 0.0, 0.9, 0.0, 0.3),
    "BALDE": ("alvenaria/grey_plaster_02", (1.0, 1.0, 1.0), 1.0, 1.0, 0.6, 0.0, 0.2),
    "PINTURA_H": ("alvenaria/grey_plaster_02", (0.95, 0.75, 0.05), 1.0, 0.0, 0.8, 0.0, 0.3),
    "SACO": ("chao/hessian_230", (1.0, 1.0, 1.0), 0.0, 0.0, 1.0, 0.0, 1.0),
}


def arquivos_polyhaven(pasta):
    """devolve (cor, normal_dx, arm) de uma pasta do Poly Haven."""
    fs = os.listdir(pasta)
    def ach(sufixo):
        for f in fs:
            if sufixo in f:
                return os.path.join(pasta, f).replace("\\", "/")
        return None
    return ach("_diff_"), ach("_nor_dx_"), ach("_arm_")


def criar_materiais():
    texs = {}
    caminho_tex = PASTA + "/Texturas"
    usadas = sorted({v[0] for v in MATERIAIS.values()})
    for rel in usadas:
        pasta = os.path.join(RECURSOS, "texturas", rel)
        if not os.path.isdir(pasta):
            log("FALTA pasta de textura", pasta)
            continue
        c, n, a = arquivos_polyhaven(pasta)
        nome = rel.split("/")[-1]
        dest = caminho_tex + "/" + nome
        texs[rel] = (importar_textura(c, dest, "cor"), importar_textura(n, dest, "normal"),
                     importar_textura(a, dest, "dados"))
        log("textura", rel)
    base = texs[usadas[0]]
    mestre = criar_mestre_opaco(*base)
    # tela
    pt = os.path.join(RECURSOS, "texturas", "telas", "Net004A")
    fs = os.listdir(pt)
    def ach(s):
        return [os.path.join(pt, f).replace("\\", "/") for f in fs if f.endswith(s)][0]
    t_cor = importar_textura(ach("_Color.jpg"), caminho_tex + "/Net004A", "cor")
    t_nrm = importar_textura(ach("_NormalDX.jpg"), caminho_tex + "/Net004A", "normal")
    t_op = importar_textura(ach("_Opacity.jpg"), caminho_tex + "/Net004A", "cinza")
    t_ru = importar_textura(ach("_Roughness.jpg"), caminho_tex + "/Net004A", "cinza")
    mestre_tela = criar_mestre_tela(t_cor, t_nrm, t_op, t_ru)
    mestre_luz = criar_mestre_emissivo()

    mis = {}
    fac = unreal.MaterialInstanceConstantFactoryNew()
    for slot, (rel, tinta, dess, pvc, rug, met, fn) in MATERIAIS.items():
        if rel not in texs:
            continue
        mi = at.create_asset("MI_" + slot, PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
        mi.set_editor_property("parent", mestre)
        c, n, a = texs[rel]
        mel.set_material_instance_texture_parameter_value(mi, "Cor", c)
        mel.set_material_instance_texture_parameter_value(mi, "Normal", n)
        mel.set_material_instance_texture_parameter_value(mi, "ORM", a)
        mel.set_material_instance_vector_parameter_value(mi, "Tinta", unreal.LinearColor(tinta[0], tinta[1], tinta[2], 1))
        mel.set_material_instance_scalar_parameter_value(mi, "Dessaturar", dess)
        mel.set_material_instance_scalar_parameter_value(mi, "PesoVertexColor", pvc)
        mel.set_material_instance_scalar_parameter_value(mi, "RugosidadeMult", rug)
        mel.set_material_instance_scalar_parameter_value(mi, "MetalMult", met)
        mel.set_material_instance_scalar_parameter_value(mi, "ForcaNormal", fn)
        mel.update_material_instance(mi)
        mis[slot] = mi
    mi = at.create_asset("MI_TELA", PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
    mi.set_editor_property("parent", mestre_tela)
    mis["TELA"] = mi
    for slot, cor, forca in (("LAMPADA", (1.0, 0.72, 0.42), 30.0), ("PORTAL", (1.0, 0.35, 0.02), 9.0)):
        mi = at.create_asset("MI_" + slot, PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
        mi.set_editor_property("parent", mestre_luz)
        mel.set_material_instance_vector_parameter_value(mi, "Cor", unreal.LinearColor(cor[0], cor[1], cor[2], 1))
        mel.set_material_instance_scalar_parameter_value(mi, "Forca", forca)
        mel.update_material_instance(mi)
        mis[slot] = mi
    log("materiais prontos:", len(mis))
    return mis


# ----------------------------------------------------------------------------- malhas do Blender
def preparar_malha(sm, mis, nanite=True, colisao=True):
    mats = sm.get_editor_property("static_materials")
    for i, smat in enumerate(mats):
        nome = str(smat.get_editor_property("material_slot_name"))
        alvo = None
        for chave in mis:
            if nome.upper().startswith(chave):
                alvo = mis[chave]
                break
        if alvo:
            sm.set_material(i, alvo)
        else:
            log("  slot sem material:", nome)
    if nanite:
        ns = sm.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", True)
        try:
            ns.set_editor_property("fallback_relative_error", 0.0)
        except Exception:
            pass
        sm.set_editor_property("nanite_settings", ns)
    if colisao:
        bs = sm.get_editor_property("body_setup")
        if bs:
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    eal.save_loaded_asset(sm)


def importar_malhas(mis):
    malhas = {}
    for arq in sorted(os.listdir(CONTEUDO)):
        if not arq.lower().endswith(".fbx"):
            continue
        nome = arq[:-4]
        if nome == "Portal":
            continue  # aros antigos: não existem mais
        caminhos = importar(CONTEUDO + "/" + arq, PASTA + "/Malhas/" + nome)
        sm = None
        for p in caminhos:
            a = unreal.load_asset(p)
            if isinstance(a, unreal.StaticMesh):
                sm = a
        if not sm:
            log("FALHOU malha", arq, caminhos)
            continue
        preparar_malha(sm, mis, nanite=(nome != "Marcador"), colisao=(nome not in ("Portal", "Marcador")))
        malhas[nome] = sm
        log("malha", nome, "triângulos?", "ok")
    return malhas


def importar_props(layout):
    nomes = sorted({p["modelo"] for p in layout["props"]})
    props = {}
    for n in nomes:
        pasta = os.path.join(RECURSOS, "modelos", n)
        if not os.path.isdir(pasta):
            log("FALTA modelo", n)
            continue
        gltf = [f for f in os.listdir(pasta) if f.endswith(".gltf")]
        if not gltf:
            continue
        caminhos = importar((pasta + "/" + gltf[0]).replace("\\", "/"), PASTA + "/Props/" + n)
        sm = None
        for p in caminhos:
            a = unreal.load_asset(p)
            if isinstance(a, unreal.StaticMesh):
                sm = a
        if not sm:
            log("FALHOU prop", n, caminhos)
            continue
        ns = sm.get_editor_property("nanite_settings")
        ns.set_editor_property("enabled", True)
        sm.set_editor_property("nanite_settings", ns)
        eal.save_loaded_asset(sm)
        colisao_prop(sm)
        props[n] = sm
        log("prop", n)
    return props


# ----------------------------------------------------------------------------- mapa
def por(obj, nomes, valor):
    """set_editor_property tentando nomes alternativos (mudam entre versões)."""
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


def montar_mapa(layout, malhas, props, mis):
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mundo = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    log("mapa em branco (sem World Partition):", mundo)

    # ---- eixos: o marcador (x=20, y=5 m no Blender) diz como o FBX entrou no Unreal
    marc = malhas.get("Marcador")
    sx, sy = 1.0, -1.0
    escala = 100.0
    if marc:
        bb = marc.get_bounding_box()
        cx = (bb.min.x + bb.max.x) / 2
        cy = (bb.min.y + bb.max.y) / 2
        cz = (bb.min.z + bb.max.z) / 2
        log("marcador centro", cx, cy, cz, "(esperado 20 m, 5 m, 0,5 m)")
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

    H = layout["altura_andar"]

    for nome, sm in malhas.items():
        if nome in ("Portal", "Marcador"):
            continue
        a = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        a.set_actor_label(nome)
        tag(a, nome)
    # props
    for i, p in enumerate(layout["props"]):
        sm = props.get(p["modelo"])
        if not sm:
            continue
        a = eas.spawn_actor_from_object(sm, P(p["x"], p["y"], p["z"]), unreal.Rotator(0, 0, yaw(p["yaw"])))
        e = p.get("escala", 1.0)
        a.set_actor_scale3d(unreal.Vector(e, e, e))
        a.set_actor_label("%s_%03d" % (p["modelo"], i))
        tag(a, p["grupo"])
    log("props colocados", len(layout["props"]))

    # luzes de obra
    for i, l in enumerate(layout["luzes"]):
        loc = P(l["x"], l["y"], l["z"])
        if l["tipo"] == "spot":
            a = eas.spawn_actor_from_class(unreal.SpotLight, loc, unreal.Rotator(roll=0, pitch=l.get("pitch", -20),
                                                                                  yaw=yaw(l.get("yaw", 0))))
            c = a.get_component_by_class(unreal.SpotLightComponent)
            por(c, "outer_cone_angle", l.get("cone", 50) / 2 + 8)
            por(c, "inner_cone_angle", l.get("cone", 50) / 2 - 10)
            por(c, "source_radius", 12.0)
        else:
            a = eas.spawn_actor_from_class(unreal.PointLight, loc, unreal.Rotator(0, 0, 0))
            c = a.get_component_by_class(unreal.PointLightComponent)
            por(c, "source_radius", 2.5)
            por(c, "cast_shadows", False)
        por(c, "intensity_units", unreal.LightUnits.LUMENS)
        por(c, "intensity", float(l["lumens"]))
        por(c, "use_temperature", True)
        por(c, "temperature", float(l["kelvin"]))
        por(c, "attenuation_radius", l.get("raio", 10) * escala)
        por(c, "mobility", unreal.ComponentMobility.MOVABLE)
        por(c, "volumetric_scattering_intensity", 1.5 if l["tipo"] == "spot" else 0.0)
        a.set_actor_label("Luz_%s_%02d" % (l["grupo"], i))
        tag(a, l["grupo"])
    log("luzes", len(layout["luzes"]))

    # pontos de rota: invisíveis, sem colisão e sem luz (só o voo de teste automático usa)
    for p in layout.get("rota", []):
        a = eas.spawn_actor_from_class(unreal.TargetPoint, P(p["x"], p["y"], p["z"]),
                                       unreal.Rotator(roll=0, pitch=p.get("pitch", 0.0), yaw=yaw(p["yaw"])))
        a.set_actor_label("Rota_%02d" % p["n"])
        tag(a, "Rota_%d" % p["n"])
    log("pontos de rota", len(layout.get("rota", [])))

    # decalques (escorridos, manchas)
    dmis = {}
    for a in assets_na_pasta(PASTA + "/Materiais", unreal.MaterialInstanceConstant):
        if a.get_name().startswith("MI_Decal_"):
            dmis[a.get_name()[9:]] = a
    n_dec = 0
    for i, d in enumerate(layout.get("decalques", [])):
        mi = dmis.get(d["tex"])
        if not mi:
            continue
        direcao = unreal.Vector(d["dx"] * sx, d["dy"] * sy, d["dz"])
        rot = unreal.MathLibrary.make_rot_from_x(direcao)
        rot = unreal.Rotator(roll=d.get("giro", 0.0), pitch=rot.pitch, yaw=rot.yaw)
        a = eas.spawn_actor_from_class(unreal.DecalActor, P(d["x"], d["y"], d["z"]), rot)
        a.set_decal_material(mi)
        dc = a.get_component_by_class(unreal.DecalComponent)
        por(dc, "decal_size", unreal.Vector(12.0, d["largura"] * escala / 2, d["altura"] * escala / 2))
        a.set_actor_label("Decal_%s_%03d" % (d["grupo"], i))
        tag(a, d["grupo"])
        n_dec += 1
    log("decalques colocados", n_dec)

    # ligações verticais e marcadores do jogo
    for i, c in enumerate(layout["conexoes"]):
        a = eas.spawn_actor_from_class(unreal.TargetPoint, P(c["x"], c["y"], c["andar"] * H + 1.5), unreal.Rotator(0, 0, 0))
        a.set_actor_label("Conexao_%d_%02d" % (c["andar"], i))
        tag(a, "Conexao_%d" % c["andar"])
    info = eas.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(0, 0, -500), unreal.Rotator(0, 0, 0))
    info.set_actor_label("InfoPredio")
    tag(info, "AlturaAndar_%d" % int(H * escala), "CotaTerreo_0")

    ini = layout["inicio"]
    ps = eas.spawn_actor_from_class(unreal.PlayerStart, P(ini["x"], ini["y"], ini["z"] + 0.6),
                                    unreal.Rotator(0, 0, yaw(ini["yaw"])))
    ps.set_actor_label("InicioDrone")

    # ---- luz natural: sol de fim de tarde entrando pela tela
    sol = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 3000),
                                     unreal.Rotator(roll=0, pitch=-16, yaw=yaw(28)))
    c = sol.get_component_by_class(unreal.DirectionalLightComponent)
    por(c, "intensity", 9.0)
    por(c, "use_temperature", True)
    por(c, "temperature", 4300.0)
    por(c, "atmosphere_sun_light", True)
    por(c, "volumetric_scattering_intensity", 4.0)
    por(c, "light_source_angle", 0.8)
    por(c, "mobility", unreal.ComponentMobility.MOVABLE)
    sol.set_actor_label("Sol")
    eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)).set_actor_label("Ceu")
    sky = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500), unreal.Rotator(0, 0, 0))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    por(sc, "real_time_capture", True)
    por(sc, "mobility", unreal.ComponentMobility.MOVABLE)
    por(sc, "intensity", 1.0)
    sky.set_actor_label("LuzDoCeu")
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    por(fc, "fog_density", 0.012)
    por(fc, "fog_height_falloff", 0.05)
    por(fc, ["enable_volumetric_fog", "volumetric_fog", "b_enable_volumetric_fog"], True)
    por(fc, "volumetric_fog_scattering_distribution", 0.75)
    por(fc, "volumetric_fog_albedo", unreal.Color(235, 222, 205, 255))
    por(fc, "volumetric_fog_extinction_scale", 1.6)
    por(fc, "volumetric_fog_distance", 3500.0)
    fog.set_actor_label("PoeiraNoAr")

    ppv = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    def ov(nome, valor):
        try:
            s.set_editor_property("override_" + nome, True)
            s.set_editor_property(nome, valor)
        except Exception as e:  # nome mudou nesta versão
            log("  pp ignorado", nome, e)
    ov("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
    ov("auto_exposure_min_brightness", -2.0)
    ov("auto_exposure_max_brightness", 12.0)
    ov("auto_exposure_bias", 0.0)
    ov("lumen_scene_lighting_quality", 2.0)
    ov("lumen_scene_detail", 2.0)
    ov("lumen_final_gather_quality", 2.0)
    ov("lumen_max_trace_distance", 4000.0)
    ov("lumen_reflection_quality", 2.0)
    ov("lumen_surface_cache_resolution", 1.0)
    ov("ambient_occlusion_intensity", 0.5)
    ov("bloom_intensity", 0.35)
    ov("color_saturation", unreal.Vector4(1.05, 1.03, 1.0, 1.0))
    ov("color_contrast", unreal.Vector4(1.06, 1.06, 1.06, 1.0))
    ov("white_temp", 6300.0)
    ov("film_toe", 0.6)
    ppv.set_editor_property("settings", s)
    ppv.set_actor_label("PosProcesso")

    ok = unreal.EditorLoadingAndSavingUtils.save_map(mundo, MAPA)
    log("mapa salvo em", MAPA, ok)
    n = len(eas.get_all_level_actors())
    log("atores no mapa:", n)


def assets_na_pasta(pasta, classe):
    res = []
    if not eal.does_directory_exist(pasta):
        return res
    for p in eal.list_assets(pasta, recursive=True, include_folder=False):
        a = eal.load_asset(p)
        if isinstance(a, classe):
            res.append(a)
    return res


def carregar_materiais():
    mis = {}
    for a in assets_na_pasta(PASTA + "/Materiais", unreal.MaterialInstanceConstant):
        mis[a.get_name()[3:]] = a
    log("materiais carregados:", len(mis))
    return mis


def colisao_prop(sm):
    """Props colidem pela própria malha (o drone não atravessa saco de cimento, barreira etc.)."""
    try:
        bs = sm.get_editor_property("body_setup")
        if bs:
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            eal.save_loaded_asset(sm)
    except Exception as e:
        log("colisao prop falhou", sm.get_name(), e)


def carregar_props(layout):
    props = {}
    for n in sorted({p["modelo"] for p in layout["props"]}):
        sms = assets_na_pasta(PASTA + "/Props/" + n, unreal.StaticMesh)
        if sms:
            props[n] = sms[0]
            colisao_prop(sms[0])
    log("props carregados:", len(props))
    return props


def carregar_malhas():
    malhas = {}
    for arq in sorted(os.listdir(CONTEUDO)):
        if arq.lower().endswith(".fbx"):
            n = arq[:-4]
            sms = assets_na_pasta(PASTA + "/Malhas/" + n, unreal.StaticMesh)
            if sms:
                malhas[n] = sms[0]
    log("malhas carregadas:", len(malhas))
    return malhas


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("construir_mapa.py\n")
    try:
        # FBX/glTF pelo Interchange (padrão do 5.8)
        with open(CONTEUDO + "/layout.json", encoding="utf-8") as fp:
            layout = json.load(fp)
        op = {"materiais": True, "malhas": True, "props": True}
        arq_op = RAIZ + "/unreal/opcoes.json"
        if os.path.exists(arq_op):
            with open(arq_op, encoding="utf-8") as fp:
                op.update(json.load(fp))
        log("opções:", op)
        if op["materiais"]:
            if eal.does_directory_exist(PASTA + "/Materiais"):
                eal.delete_directory(PASTA + "/Materiais")
            mis = criar_materiais()
            criar_decalques(layout)
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        else:
            mis = carregar_materiais()
            if op.get("decalques"):
                criar_decalques(layout)
                unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        if op["malhas"]:
            if eal.does_directory_exist(PASTA + "/Malhas"):
                eal.delete_directory(PASTA + "/Malhas")
            malhas = importar_malhas(mis)
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        else:
            malhas = carregar_malhas()
        if op["props"]:
            props = importar_props(layout)
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        else:
            props = carregar_props(layout)
        montar_mapa(layout, malhas, props, mis)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("TUDO PRONTO")
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
    finally:
        if os.environ.get("PREDIO_NAO_FECHAR") != "1":
            unreal.SystemLibrary.quit_editor()


main()
