"""Monta o MAPA 1 — CAMPO BAIANO no Unreal 5.8 (roda no editor com -ExecutePythonScript).

Entrada (no PC):
  D:/DronePredio/conteudo_campo/   FBX + layout_campo.json gerados pelo blender/gerar_campo.py
  D:/DronePredio/recursos_campo/   o voo_e88_recursos.zip da Godot desempacotado
                                   (texturas/<nome>/diff|nor_gl|arm.jpg e modelos/<nome>/<nome>_1k.gltf)

1. texturas do campo e materiais (terreno misturado pelas cores de vértice, PBR dos objetos, cores lisas)
2. FBX do Blender (Nanite + colisão pela própria malha)
3. árvores, arbustos, pedras e objetos da fazenda (glTF do Poly Haven, Nanite)
4. aros do circuito (com tags Aro_N / Rota_N para o jogo), hastes, base, início do drone
5. sol, céu com atmosfera, nuvens volumétricas, névoa, pós-processo
6. salva /Game/Mapas/Campo e fecha o editor
"""
import json
import math
import os
import time
import traceback

import unreal

RAIZ = os.environ.get("PREDIO_RAIZ", "D:/DronePredio").replace("\\", "/")
CONTEUDO = RAIZ + "/conteudo_campo"
LOG = RAIZ + "/logs/construir_campo_progresso.txt"
PASTA = "/Game/Campo"
MAPA = "/Game/Mapas/Campo"

at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
T0 = time.time()


def log(*a):
    msg = "[%6.1fs] " % (time.time() - T0) + " ".join(str(x) for x in a)
    unreal.log(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def achar_recursos():
    base = RAIZ + "/recursos_campo"
    for raiz, pastas, _ in os.walk(base):
        if "texturas" in pastas and "modelos" in pastas:
            return raiz.replace("\\", "/")
    return base + "/voo_e88/recursos"


RECURSOS = achar_recursos()


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
        tex.set_editor_property("flip_green_channel", True)   # Poly Haven nor_gl (OpenGL) -> DirectX do Unreal
    elif tipo == "dados":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        tex.set_editor_property("srgb", False)
    return tex


TEX = {}


def texturas(nome):
    """(cor, normal, arm) de recursos/texturas/<nome>/ — None se não tiver a pasta."""
    if nome in TEX:
        return TEX[nome]
    pasta = RECURSOS + "/texturas/" + nome
    if not os.path.isdir(pasta):
        log("FALTA pasta de textura", pasta)
        TEX[nome] = None
        return None
    dest = PASTA + "/Texturas/" + nome
    r = (importar_textura(pasta + "/diff.jpg", dest, "cor"),
         importar_textura(pasta + "/nor_gl.jpg", dest, "normal"),
         importar_textura(pasta + "/arm.jpg", dest, "dados"))
    TEX[nome] = r if r[0] else None
    log("textura", nome, "ok" if TEX[nome] else "sem cor")
    return TEX[nome]


# ----------------------------------------------------------------------------- materiais
def novo_material(nome):
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


def criar_terreno_material():
    """grama (perto + vista aérea misturadas) / estrada de terra vermelha (R) / beira do açude (G) / terra batida (B)."""
    grama = texturas("grass_ground")
    aerea = texturas("aerial_grass_rock")
    terra = texturas("red_laterite_soil_stones")
    lama = texturas("brown_mud_dry") or terra
    if not (grama and terra):
        log("terreno sem texturas — material liso")
        return None
    m = novo_material("M_Terreno")
    wp = expr(m, unreal.MaterialExpressionWorldPosition, -2600, 0)
    xy = expr(m, unreal.MaterialExpressionComponentMask, -2450, 0, r=True, g=True, b=False, a=False)
    ligar(wp, "", xy, "")

    def uv(cm, y):
        mul = expr(m, unreal.MaterialExpressionMultiply, -2250, y)
        ligar(xy, "", mul, "A")
        ligar(const(m, 1.0 / cm, -2400, y + 60), "", mul, "B")
        return mul

    uv_g, uv_a, uv_t, uv_l = uv(320.0, -600), uv(3600.0, -200), uv(380.0, 200), uv(420.0, 600)
    g_c, g_n, g_a = (amostra(m, grama[0], uv_g, -1900, -900, "cor"), amostra(m, grama[1], uv_g, -1900, -650, "normal"),
                     amostra(m, grama[2], uv_g, -1900, -400, "dados") if grama[2] else None)
    a_c = amostra(m, aerea[0], uv_a, -1900, -150, "cor") if aerea else None
    t_c, t_n = amostra(m, terra[0], uv_t, -1900, 150, "cor"), amostra(m, terra[1], uv_t, -1900, 400, "normal")
    l_c, l_n = amostra(m, lama[0], uv_l, -1900, 650, "cor"), amostra(m, lama[1], uv_l, -1900, 900, "normal")
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1600, 1150)

    # grama: a textura de perto com a vista aérea por cima (quebra a repetição de longe)
    cor_g = rgb(m, g_c, "", -1600, -900)
    if a_c:
        cor_a = rgb(m, a_c, "", -1600, -150)
        tom = expr(m, unreal.MaterialExpressionMultiply, -1450, -150)
        ligar(cor_a, "", tom, "A")
        ligar(const(m, 1.15, -1600, -60), "", tom, "B")
        cor_g = lerp(m, cor_g, tom, const(m, 0.38, -1450, -400), -1300, -600)
    c1 = lerp(m, cor_g, rgb(m, t_c, "", -1600, 150), vc, -1100, -300, salfa="R")
    c2 = lerp(m, c1, rgb(m, l_c, "", -1600, 650), vc, -900, -200, salfa="G")
    batida = expr(m, unreal.MaterialExpressionMultiply, -1100, 700)
    ligar(rgb(m, l_c, "", -1300, 700), "", batida, "A")
    ligar(const(m, 1.1, -1300, 790), "", batida, "B")
    c3 = lerp(m, c2, batida, vc, -700, -100, salfa="B")
    mel.connect_material_property(c3, "", unreal.MaterialProperty.MP_BASE_COLOR)

    n1 = lerp(m, rgb(m, g_n, "", -1600, -650), rgb(m, t_n, "", -1600, 400), vc, -1100, 300, salfa="R")
    n2 = lerp(m, n1, rgb(m, l_n, "", -1600, 900), vc, -900, 400, salfa="G")
    n3 = lerp(m, n2, rgb(m, l_n, "", -1300, 950), vc, -700, 450, salfa="B")
    mel.connect_material_property(n3, "", unreal.MaterialProperty.MP_NORMAL)

    rug_g = g_a if g_a else const(m, 0.9, -1600, -400)
    r1 = lerp(m, rug_g, const(m, 0.95, -1300, 1000), vc, -900, 800, sa="G" if g_a else "", salfa="R")
    mel.connect_material_property(r1, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(const(m, 0.35, -700, 900), "", unreal.MaterialProperty.MP_SPECULAR)
    if g_a:
        mel.connect_material_property(g_a, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.recompile_material(m)
    log("material do terreno pronto")
    return m


def criar_mestre_pbr(tex_cor, tex_nrm, tex_orm):
    m = novo_material("M_CampoPBR")
    tc = expr(m, unreal.MaterialExpressionTextureCoordinate, -1700, 0)
    esc = expr(m, unreal.MaterialExpressionScalarParameter, -1700, 120, parameter_name="Escala", default_value=1.0)
    uv = expr(m, unreal.MaterialExpressionMultiply, -1500, 50)
    ligar(tc, "", uv, "A")
    ligar(esc, "", uv, "B")
    cor = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1250, -300, parameter_name="Cor", texture=tex_cor)
    nrm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1250, 100, parameter_name="Normal", texture=tex_nrm,
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    orm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -1250, 450, parameter_name="ORM", texture=tex_orm,
               sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    for s in (cor, nrm, orm):
        ligar(uv, "", s, "UVs")
    tinta = expr(m, unreal.MaterialExpressionVectorParameter, -1000, -450, parameter_name="Tinta",
                 default_value=unreal.LinearColor(1, 1, 1, 1))
    mul = expr(m, unreal.MaterialExpressionMultiply, -800, -350)
    ligar(rgb(m, cor, "", -1000, -300), "", mul, "A")
    ligar(rgb(m, tinta, "", -900, -450), "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rgb(m, nrm, "", -900, 100), "", unreal.MaterialProperty.MP_NORMAL)
    rm = expr(m, unreal.MaterialExpressionScalarParameter, -1000, 600, parameter_name="RugosidadeMult", default_value=1.0)
    rough = expr(m, unreal.MaterialExpressionMultiply, -800, 520)
    ligar(orm, "G", rough, "A")
    ligar(rm, "", rough, "B")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(orm, "B", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(orm, "R", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.recompile_material(m)
    return m


def criar_mestre_cor():
    m = novo_material("M_CampoCor")
    cor = expr(m, unreal.MaterialExpressionVectorParameter, -800, -200, parameter_name="Cor",
               default_value=unreal.LinearColor(0.7, 0.7, 0.7, 1))
    c3 = rgb(m, cor, "", -600, -200)
    mel.connect_material_property(c3, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rug = expr(m, unreal.MaterialExpressionScalarParameter, -800, 0, parameter_name="Rugosidade", default_value=0.6)
    met = expr(m, unreal.MaterialExpressionScalarParameter, -800, 100, parameter_name="Metal", default_value=0.0)
    esp = expr(m, unreal.MaterialExpressionScalarParameter, -800, 200, parameter_name="Especular", default_value=0.5)
    emi = expr(m, unreal.MaterialExpressionScalarParameter, -800, 300, parameter_name="Brilho", default_value=0.0)
    mul = expr(m, unreal.MaterialExpressionMultiply, -500, 300)
    ligar(c3, "", mul, "A")
    ligar(emi, "", mul, "B")
    mel.connect_material_property(rug, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(esp, "", unreal.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    return m


# slot do Blender -> ("pbr", textura, tinta, escala, rug) | ("cor", (r,g,b), rug, metal, brilho, especular)
SLOTS = {
    "BASE": ("pbr", "concrete_floor_worn_001", (0.92, 0.9, 0.88), 1.0, 1.0),
    "PISO": ("pbr", "concrete_floor_worn_001", (0.85, 0.8, 0.75), 1.0, 1.0),
    "PAREDE": ("pbr", "clay_plaster", (1.0, 0.97, 0.9), 1.0, 1.0),
    "TELHA": ("pbr", "clay_roof_tiles_02", (1.0, 1.0, 1.0), 1.0, 1.0),
    "MADEIRA": ("pbr", "fine_grained_wood", (0.62, 0.5, 0.38), 1.0, 1.0),
    "PINTURA": ("cor", (0.85, 0.85, 0.82), 0.6, 0.0, 0.0, 0.5),
    "METAL": ("cor", (0.72, 0.72, 0.70), 0.45, 0.8, 0.0, 0.5),
    "ARAME": ("cor", (0.45, 0.45, 0.43), 0.5, 0.7, 0.0, 0.5),
    "FIO": ("cor", (0.04, 0.04, 0.04), 0.5, 0.3, 0.0, 0.5),
    "ISOLADOR": ("cor", (0.80, 0.80, 0.76), 0.25, 0.0, 0.0, 0.6),
    "PANO": ("cor", (0.95, 0.35, 0.06), 0.85, 0.0, 0.0, 0.4),
    "ARO_PRETO": ("cor", (0.02, 0.02, 0.02), 0.5, 0.0, 0.0, 0.5),
    "ARO": ("cor", (0.95, 0.30, 0.04), 0.45, 0.0, 0.6, 0.5),
    "AGUA": ("cor", (0.015, 0.045, 0.05), 0.04, 0.0, 0.0, 1.0),
}
# reserva quando falta a textura: cor lisa parecida
RESERVA = {"BASE": (0.55, 0.54, 0.52), "PISO": (0.5, 0.48, 0.45), "PAREDE": (0.85, 0.8, 0.7),
           "TELHA": (0.6, 0.28, 0.18), "MADEIRA": (0.42, 0.32, 0.22)}


def criar_materiais():
    if eal.does_directory_exist(PASTA + "/Materiais"):
        eal.delete_directory(PASTA + "/Materiais")
    mis = {}
    terreno = criar_terreno_material()
    if terreno:
        mis["TERRENO"] = terreno
    base = None
    for slot, d in SLOTS.items():
        if d[0] == "pbr" and texturas(d[1]):
            base = texturas(d[1])
            break
    mestre_pbr = criar_mestre_pbr(*base) if base and base[1] and base[2] else None
    mestre_cor = criar_mestre_cor()
    fac = unreal.MaterialInstanceConstantFactoryNew()
    for slot, d in SLOTS.items():
        mi = at.create_asset("MI_" + slot, PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
        tx = texturas(d[1]) if d[0] == "pbr" else None
        if d[0] == "pbr" and tx and tx[1] and tx[2] and mestre_pbr:
            mi.set_editor_property("parent", mestre_pbr)
            mel.set_material_instance_texture_parameter_value(mi, "Cor", tx[0])
            mel.set_material_instance_texture_parameter_value(mi, "Normal", tx[1])
            mel.set_material_instance_texture_parameter_value(mi, "ORM", tx[2])
            mel.set_material_instance_vector_parameter_value(mi, "Tinta", unreal.LinearColor(*d[2], 1))
            mel.set_material_instance_scalar_parameter_value(mi, "Escala", d[3])
            mel.set_material_instance_scalar_parameter_value(mi, "RugosidadeMult", d[4])
        else:
            mi.set_editor_property("parent", mestre_cor)
            if d[0] == "pbr":
                cor, rug, met, bri, esp = RESERVA.get(slot, (0.6, 0.6, 0.6)), 0.8, 0.0, 0.0, 0.5
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
        mi = at.create_asset("MI_TERRENO", PASTA + "/Materiais", unreal.MaterialInstanceConstant, fac)
        mi.set_editor_property("parent", mestre_cor)
        mel.set_material_instance_vector_parameter_value(mi, "Cor", unreal.LinearColor(0.16, 0.2, 0.08, 1))
        mel.set_material_instance_scalar_parameter_value(mi, "Rugosidade", 0.95)
        mel.update_material_instance(mi)
        mis["TERRENO"] = mi
    log("materiais prontos:", sorted(mis))
    return mis


# ----------------------------------------------------------------------------- malhas do Blender
def material_do_slot(nome, mis):
    n = nome.upper()
    if n in mis:
        return mis[n]
    for chave in sorted(mis, key=len, reverse=True):
        if n.startswith(chave):
            return mis[chave]
    return None


def nanite(sm, ligar_nanite=True, erro_reserva=None):
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", ligar_nanite)
    if erro_reserva is not None:
        try:
            ns.set_editor_property("fallback_relative_error", erro_reserva)
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


def carregar_sm(pasta):
    if not eal.does_directory_exist(pasta):
        return []
    res = []
    for p in eal.list_assets(pasta, recursive=True, include_folder=False):
        a = eal.load_asset(p)
        if isinstance(a, unreal.StaticMesh):
            res.append(a)
    return res


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
        nanite(sm, nome not in ("Marcador", "Agua"), 0.0)
        if nome not in ("Marcador", "Agua"):
            colisao_complexa(sm)
        eal.save_loaded_asset(sm)
        malhas[nome] = sm
        log("malha", nome)
    return malhas


def importar_modelos(layout, refazer):
    nomes = sorted({p["modelo"] for p in layout["plantas"]} | {"grass_medium_01"})
    modelos = {}
    for n in nomes:
        destino = PASTA + "/Modelos/" + n
        sms = [] if refazer else carregar_sm(destino)
        if not sms:
            pasta = RECURSOS + "/modelos/" + n
            gltf = [f for f in os.listdir(pasta) if f.endswith(".gltf") or f.endswith(".glb")] if os.path.isdir(pasta) else []
            if not gltf:
                log("FALTA modelo", n)
                continue
            if eal.does_directory_exist(destino):
                eal.delete_directory(destino)
            caminhos = importar(pasta + "/" + gltf[0], destino)
            sms = [unreal.load_asset(p) for p in caminhos]
            sms = [a for a in sms if isinstance(a, unreal.StaticMesh)]
            if not sms:
                log("FALHOU modelo", n, caminhos)
                continue
            for sm in sms:
                nanite(sm, True)
                if n != "grass_medium_01":
                    colisao_complexa(sm)
                eal.save_loaded_asset(sm)
            log("modelo", n, len(sms), "malha(s)")
        modelos[n] = sms
    return modelos


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


def montar_mapa(layout, malhas, modelos):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    mundo = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    log("mapa em branco:", mundo)

    marc = malhas.get("Marcador")
    sx, sy, escala = 1.0, -1.0, 100.0
    if marc:
        bb = marc.get_bounding_box()
        cx, cy = (bb.min.x + bb.max.x) / 2, (bb.min.y + bb.max.y) / 2
        log("marcador centro", cx, cy, "(esperado 20 m, 5 m)")
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

    # malhas fixas (já estão no lugar dentro do FBX)
    for nome, sm in malhas.items():
        if nome in ("Marcador", "Aro", "Haste"):
            continue
        a = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        a.set_actor_label(nome)
        tag(a, nome)
        if nome == "Agua":
            a.set_actor_enable_collision(False)

    # árvores, arbustos, pedras e objetos
    n = 0
    for i, p in enumerate(layout["plantas"]):
        sms = modelos.get(p["modelo"])
        if not sms:
            continue
        for k, sm in enumerate(sms):
            a = eas.spawn_actor_from_object(sm, P(p["x"], p["y"], p["z"]), unreal.Rotator(0, 0, yaw(p["yaw"])))
            a.set_actor_scale3d(unreal.Vector(p["sx"], p["sy"], p["sz"]))
            a.set_actor_label("%s_%03d_%d" % (p["modelo"], i, k))
            tag(a, "Planta")
            if math.hypot(p["x"], p["y"]) > 650.0:
                a.set_actor_enable_collision(False)    # fora da área de voo
            n += 1
    log("plantas e objetos colocados:", n)

    # grama: modelo escondido que o jogo espalha em volta da base (HISM em tempo de execução)
    if modelos.get("grass_medium_01"):
        g = eas.spawn_actor_from_object(modelos["grass_medium_01"][0], unreal.Vector(0, 0, -100000), unreal.Rotator(0, 0, 0))
        g.set_actor_label("ModeloGrama")
        g.set_actor_enable_collision(False)
        g.set_actor_hidden_in_game(True)
        tag(g, "ModeloGrama")

    # aros do circuito
    aro, haste = malhas.get("Aro"), malhas.get("Haste")
    for r in layout["aros"]:
        if not aro:
            break
        a = eas.spawn_actor_from_object(aro, P(r["x"], r["y"], r["z"]), unreal.Rotator(0, 0, yaw(r["yaw"])))
        a.set_actor_label("Aro_%02d" % (r["n"] + 1))
        tag(a, "Aro_%d" % r["n"], "Rota_%d" % r["n"])
        base_aro = r["z"] - 2.35
        if haste and base_aro - r["chao"] > 0.3:
            h = eas.spawn_actor_from_object(haste, P(r["x"], r["y"], r["chao"] - 0.2), unreal.Rotator(0, 0, 0))
            h.set_actor_scale3d(unreal.Vector(1, 1, base_aro - r["chao"] + 0.25))
            h.set_actor_label("Haste_%02d" % (r["n"] + 1))
    log("aros:", len(layout["aros"]))

    # informações para o jogo: raio do aro, açude e estrada (a grama evita esses lugares)
    ac = layout["acude"]
    c = P(ac["x"], ac["y"], 0)
    info = eas.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(0, 0, -5000), unreal.Rotator(0, 0, 0))
    info.set_actor_label("InfoCampo")
    tag(info, "AroRaio_%d" % int(layout.get("raio_aro", 2.05) * escala),
        "Acude_%d_%d_%d_%d" % (int(c.x), int(c.y), int(ac["rx"] * escala * 1.25), int(ac["ry"] * escala * 1.25)),
        "AlturaAndar_100000", "CotaTerreo_-100000")
    for i, (x, y, z) in enumerate(layout["estrada"]):
        e = eas.spawn_actor_from_class(unreal.TargetPoint, P(x, y, z), unreal.Rotator(0, 0, 0))
        e.set_actor_label("Estrada_%02d" % i)
        tag(e, "Estrada_%d" % i)

    ini = layout["inicio"]
    ps = eas.spawn_actor_from_class(unreal.PlayerStart, P(ini["x"], ini["y"], ini["z"] + 0.6), unreal.Rotator(0, 0, yaw(ini["yaw"])))
    ps.set_actor_label("InicioDrone")

    # ---- dia de céu aberto no sertão (sol alto vindo do nordeste, como o céu "farm_field" da Godot)
    sol = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 5000),
                                     unreal.Rotator(roll=0, pitch=-46, yaw=yaw(215)))
    lc = sol.get_component_by_class(unreal.DirectionalLightComponent)
    por(lc, "intensity", 10.0)
    por(lc, "use_temperature", True)
    por(lc, "temperature", 5600.0)
    por(lc, "atmosphere_sun_light", True)
    por(lc, "light_source_angle", 0.6)
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
    por(sc, "intensity", 1.0)
    sky.set_actor_label("LuzDoCeu")
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    por(fc, "fog_density", 0.004)
    por(fc, "fog_height_falloff", 0.06)
    por(fc, "fog_inscattering_luminance", unreal.LinearColor(0.55, 0.65, 0.8, 1.0))
    por(fc, ["enable_volumetric_fog", "volumetric_fog"], False)
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
    ov("auto_exposure_bias", 0.3)
    ov("lumen_scene_lighting_quality", 1.5)
    ov("lumen_final_gather_quality", 1.5)
    ov("lumen_max_trace_distance", 20000.0)
    ov("bloom_intensity", 0.3)
    ov("color_saturation", unreal.Vector4(1.08, 1.06, 1.0, 1.0))
    ov("color_contrast", unreal.Vector4(1.04, 1.04, 1.04, 1.0))
    ov("film_toe", 0.58)
    ppv.set_editor_property("settings", s)
    ppv.set_actor_label("PosProcesso")

    ok = unreal.EditorLoadingAndSavingUtils.save_map(mundo, MAPA)
    log("mapa salvo em", MAPA, ok, "atores:", len(eas.get_all_level_actors()))


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("construir_campo.py\n")
    try:
        log("recursos da Godot em", RECURSOS)
        with open(CONTEUDO + "/layout_campo.json", encoding="utf-8") as fp:
            layout = json.load(fp)
        op = {"modelos": False}
        arq_op = RAIZ + "/unreal/opcoes_campo.json"
        if os.path.exists(arq_op):
            with open(arq_op, encoding="utf-8") as fp:
                op.update(json.load(fp))
        log("opções:", op)
        mis = criar_materiais()
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        malhas = importar_malhas(mis)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        modelos = importar_modelos(layout, op.get("modelos", False))
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        montar_mapa(layout, malhas, modelos)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("TUDO PRONTO")
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
    finally:
        if os.environ.get("PREDIO_NAO_FECHAR") != "1":
            unreal.SystemLibrary.quit_editor()


main()
