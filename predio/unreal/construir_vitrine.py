"""Vitrine / laboratório (roda no editor com -ExecutePythonScript): mapa pequeno para testar coisas novas
uma de cada vez antes de levar para a fazenda.

  /Game/Mapas/Vitrine  (300 x 300 m)
    - chão próprio (TerrenoVitrine, mesmo material da fazenda), capim, palha, flores e um canteiro de milho
      que BALANÇAM COM O VENTO (material com deslocamento de vértices; o jogo manda força, rajada, direção
      e a posição do drone — o vento das hélices deita o capim em volta)
    - árvores: ATUAL parada | ATUAL COM VENTO (galhos balançam, folhas tremem) | NOVA (Megaplants, quando houver)
    - canteiros de chão Megascans (Dry Soil, Arid Soil) e um laguinho com as ondas do vento
    - pontos Rota_N para o voo de teste tirar fotos

Entradas: D:/DronePredio/conteudo_vitrine/ (gerar_vitrine.py) e os materiais da fazenda (/Game/Campo/Materiais).
Os assets do Fab são achados sozinhos pelo nome; enquanto não estiverem no projeto aparece "FALTA ADICIONAR".
Atores com a tag "Vento" recebem do jogo os parâmetros VentoForca, VentoRajada, VentoDir, DronePos, DroneForca.
"""
import json
import os
import re
import time
import traceback

import unreal

RAIZ = os.environ.get("PREDIO_RAIZ", "D:/DronePredio").replace("\\", "/")
ENT = RAIZ + "/conteudo_vitrine"
LOG = RAIZ + "/logs/construir_vitrine_progresso.txt"
MAPA = "/Game/Mapas/Vitrine"
PASTA = "/Game/Vitrine"
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
at = unreal.AssetToolsHelpers.get_asset_tools()
T0 = time.time()


def log(*a):
    msg = "[%6.1fs] " % (time.time() - T0) + " ".join(str(x) for x in a)
    unreal.log(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


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


def chave(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def U(x, y, z=0.0):
    """metros do Blender (x leste, y para frente) -> centímetros do Unreal (o eixo Y do Unreal é o -y do Blender)."""
    return unreal.Vector(x * 100.0, -y * 100.0, z * 100.0)


def importar(arquivo, destino):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", arquivo)
    t.set_editor_property("destination_path", destino)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    at.import_asset_tasks([t])
    return list(t.get_editor_property("imported_object_paths") or [])


# ----------------------------------------------------------------------------- assets do Fab
NOSSAS = ("/Game/Campo", "/Game/Predio", "/Game/UI", "/Game/Drone", "/Game/Mapas", "/Game/Vitrine", "/Game/Developers", "/Game/Collections")


def todos_assets():
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    return [d for d in ar.get_assets_by_path("/Game", recursive=True) if not str(d.package_name).startswith(NOSSAS)]


def classe(d):
    try:
        return str(d.asset_class_path.asset_name)
    except Exception:
        return str(d.asset_class)


def achar(assets, palavras, classes):
    melhores = [d for d in assets if all(p in chave(str(d.asset_name) + " " + str(d.package_path)) for p in palavras) and classe(d) in classes]
    if not melhores:
        return None
    melhores.sort(key=lambda d: len(str(d.package_name)))
    return unreal.load_asset(str(melhores[0].package_name))


# ----------------------------------------------------------------------------- materiais com vento
def novo_material(nome):
    caminho = PASTA + "/Materiais/" + nome
    if eal.does_asset_exist(caminho):
        eal.delete_asset(caminho)
    return at.create_asset(nome, PASTA + "/Materiais", unreal.Material, unreal.MaterialFactoryNew())


def expr(m, classe_, x, y, **props):
    e = mel.create_material_expression(m, classe_, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def ligar(a, sa, b, sb):
    mel.connect_material_expressions(a, sa, b, sb)


def custom(m, x, y, codigo, entradas):
    c = expr(m, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", codigo)
    c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    c.set_editor_property("description", "Vento")
    lista = []
    for nome in entradas:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", nome)
        lista.append(ci)
    c.set_editor_property("inputs", lista)
    return c


def parametros_vento(m, x0, y0):
    """os parâmetros que o jogo atualiza todo quadro (iguais em todos os materiais com vento)."""
    p = {}
    for i, (nome, padrao) in enumerate((("VentoForca", 0.3), ("VentoRajada", 0.5), ("DroneForca", 0.0))):
        p[nome] = expr(m, unreal.MaterialExpressionScalarParameter, x0, y0 + i * 70, parameter_name=nome, default_value=padrao)
    p["VentoDir"] = expr(m, unreal.MaterialExpressionVectorParameter, x0, y0 + 230, parameter_name="VentoDir",
                         default_value=unreal.LinearColor(1, 0, 0, 0))
    p["DronePos"] = expr(m, unreal.MaterialExpressionVectorParameter, x0, y0 + 330, parameter_name="DronePos",
                         default_value=unreal.LinearColor(0, 0, -100000, 0))
    return p


def posicao_mundo(m, x, y):
    wp = expr(m, unreal.MaterialExpressionWorldPosition, x, y)
    try:
        wp.set_editor_property("world_position_shader_offset", unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    except Exception:
        pass
    return wp


CODIGO_CAPIM = r"""
float h = saturate(VC.r);
float alt = VC.g * 3.0;
float2 d = normalize(DIR.xy + float2(1e-4, 0.0));
float onda = 0.5 + 0.5 * sin(dot(P.xy, d) / 700.0 - T * 2.2);
float amt = F * (0.65 + 0.35 * R) * (0.55 + 0.45 * onda) * (10.0 + 22.0 * alt) * h * h;
float fl = sin(T * 7.0 + P.x * 0.031 + P.y * 0.047) * (0.6 + 2.5 * F) * h;
float3 o = float3(d * amt, -0.35 * amt * h);
o.xy += float2(-d.y, d.x) * fl;
float2 v = P.xy - DP.xy;
float dist = length(v);
float hd = max(0.0, DP.z - P.z);
float forca = DF * saturate(1.0 - dist / 320.0) * saturate(1.0 - hd / 450.0);
o.xy += (dist > 1.0 ? v / dist : float2(0.0, 0.0)) * 30.0 * forca * h * h;
o.z -= 8.0 * forca * h;
return o;
"""

CODIGO_ARVORE = r"""
float hr = saturate((P.z - O.z) / max(ALT, 100.0));
float fase = (O.x + O.y) * 0.013;
float2 d = normalize(DIR.xy + float2(1e-4, 0.0));
float balanco = F * (0.7 + 0.5 * R) * (0.8 + 0.2 * sin(T * 1.3 + fase)) * 60.0 * hr * hr;
float lado = sin(T * 0.9 + fase * 1.7) * F * 12.0 * hr * hr;
float3 o = float3(d * balanco + float2(-d.y, d.x) * lado, -0.15 * balanco * hr);
float tremor = FOLHA * (1.5 + 7.0 * F * (0.6 + 0.6 * R)) * hr;
o += tremor * float3(sin(T * 9.0 + dot(P, float3(0.071, 0.053, 0.037))), cos(T * 8.0 + dot(P, float3(0.049, 0.067, 0.029))), 0.5 * sin(T * 11.0 + P.z * 0.05));
return o;
"""


def mestre_capim():
    """folha de capim/milho/flor: cor lisa + balanço pelo vento (cor do vértice R = altura na planta)."""
    m = novo_material("M_FolhaVento")
    m.set_editor_property("two_sided", True)
    por(m, "max_world_position_offset_displacement", 80.0)
    cor = expr(m, unreal.MaterialExpressionVectorParameter, -900, -300, parameter_name="Cor", default_value=unreal.LinearColor(0.27, 0.36, 0.09, 1))
    mk = expr(m, unreal.MaterialExpressionComponentMask, -700, -300, r=True, g=True, b=True, a=False)
    ligar(cor, "", mk, "")
    mel.connect_material_property(mk, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rug = expr(m, unreal.MaterialExpressionScalarParameter, -900, -180, parameter_name="Rugosidade", default_value=0.75)
    mel.connect_material_property(rug, "", unreal.MaterialProperty.MP_ROUGHNESS)
    p = parametros_vento(m, -1300, 0)
    wp = posicao_mundo(m, -1300, 450)
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1300, 560)
    tempo = expr(m, unreal.MaterialExpressionTime, -1300, 680)
    c = custom(m, -700, 200, CODIGO_CAPIM, ["P", "VC", "T", "F", "R", "DIR", "DP", "DF"])
    for fonte, entrada in ((wp, "P"), (vc, "VC"), (tempo, "T"), (p["VentoForca"], "F"), (p["VentoRajada"], "R"),
                           (p["VentoDir"], "DIR"), (p["DronePos"], "DP"), (p["DroneForca"], "DF")):
        ligar(fonte, "", c, entrada)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    return m


def mestre_arvore():
    """árvore com vento: texturas do glTF (cor+alfa, normal, metal/rugosidade) + balanço da copa e tremor das folhas."""
    m = novo_material("M_ArvoreVento")
    m.set_editor_property("two_sided", True)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    por(m, "opacity_mask_clip_value", 0.4)
    por(m, "max_world_position_offset_displacement", 120.0)
    branco = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    normal_padrao = unreal.load_asset("/Engine/EngineMaterials/DefaultNormal")
    tc = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, -400, parameter_name="Cor", texture=branco)
    mel.connect_material_property(tc, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(tc, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    tn = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, -150, parameter_name="Normal", texture=normal_padrao,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_property(tn, "RGB", unreal.MaterialProperty.MP_NORMAL)
    tm = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, 100, parameter_name="MR", texture=branco,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    mel.connect_material_property(tm, "G", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(tm, "B", unreal.MaterialProperty.MP_METALLIC)
    p = parametros_vento(m, -1500, 300)
    wp = posicao_mundo(m, -1500, 750)
    op = expr(m, unreal.MaterialExpressionObjectPositionWS, -1500, 860)
    tempo = expr(m, unreal.MaterialExpressionTime, -1500, 960)
    folha = expr(m, unreal.MaterialExpressionScalarParameter, -1500, 1040, parameter_name="Folha", default_value=0.0)
    alt = expr(m, unreal.MaterialExpressionScalarParameter, -1500, 1120, parameter_name="AlturaArvore", default_value=1100.0)
    c = custom(m, -800, 500, CODIGO_ARVORE, ["P", "O", "T", "F", "R", "DIR", "FOLHA", "ALT"])
    for fonte, entrada in ((wp, "P"), (op, "O"), (tempo, "T"), (p["VentoForca"], "F"), (p["VentoRajada"], "R"),
                           (p["VentoDir"], "DIR"), (folha, "FOLHA"), (alt, "ALT")):
        ligar(fonte, "", c, entrada)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    return m


CORES_FOLHA = {"CAPIM": (0.27, 0.36, 0.09), "PALHA": (0.52, 0.43, 0.22), "FLOR_AMARELA": (0.95, 0.72, 0.06),
               "MILHO": (0.16, 0.32, 0.06), "ESPIGA": (0.55, 0.58, 0.22)}


def mi(nome, pai):
    caminho = PASTA + "/Materiais/" + nome
    if eal.does_asset_exist(caminho):
        eal.delete_asset(caminho)
    i = at.create_asset(nome, PASTA + "/Materiais", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    i.set_editor_property("parent", pai)
    return i


def textura_do_gltf(mat, tipo):
    """acha a textura de um material do glTF pelo nome do parâmetro (cor, normal ou metal/rugosidade)."""
    try:
        nomes = [str(n) for n in mel.get_texture_parameter_names(mat)]
    except Exception:
        nomes = []
    chaves = {"cor": ("basecolor", "base_color", "diffuse", "albedo"), "normal": ("normal",), "mr": ("metallicroughness", "roughness", "orm")}[tipo]
    for n in nomes:
        if any(k in n.lower().replace(" ", "") for k in chaves):
            try:
                t = mel.get_material_instance_texture_parameter_value(mat, n)
                if t:
                    return t
            except Exception:
                pass
    return None


def adicionar_vento_no_mestre(m):
    """põe o balanço/tremor da árvore (WPO) num material mestre já existente (cópia do mestre do glTF)."""
    por(m, "max_world_position_offset_displacement", 120.0)
    p = parametros_vento(m, -2600, 300)
    wp = posicao_mundo(m, -2600, 750)
    op = expr(m, unreal.MaterialExpressionObjectPositionWS, -2600, 860)
    tempo = expr(m, unreal.MaterialExpressionTime, -2600, 960)
    folha = expr(m, unreal.MaterialExpressionScalarParameter, -2600, 1040, parameter_name="Folha", default_value=0.0)
    alt = expr(m, unreal.MaterialExpressionScalarParameter, -2600, 1120, parameter_name="AlturaArvore", default_value=1100.0)
    c = custom(m, -2000, 500, CODIGO_ARVORE, ["P", "O", "T", "F", "R", "DIR", "FOLHA", "ALT"])
    for fonte, entrada in ((wp, "P"), (op, "O"), (tempo, "T"), (p["VentoForca"], "F"), (p["VentoRajada"], "R"),
                           (p["VentoDir"], "DIR"), (folha, "FOLHA"), (alt, "ALT")):
        ligar(fonte, "", c, entrada)
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)


COPIAS = {}


def copia_com_vento(mat):
    """cópia de um material/instância do glTF (e da cadeia de pais dele) com o vento no mestre.
    As instâncias copiadas mantêm todas as texturas e ajustes; só o mestre ganha o balanço."""
    caminho = mat.get_path_name()
    if caminho in COPIAS:
        return COPIAS[caminho]
    destino = PASTA + "/ArvoreVento/" + mat.get_name() + "_Vento"
    if eal.does_asset_exist(destino):
        eal.delete_asset(destino)
    nova = eal.duplicate_asset(caminho.split(".")[0], destino)
    if isinstance(mat, unreal.Material):
        adicionar_vento_no_mestre(nova)
        log("   mestre com vento:", caminho, "->", destino)
    else:
        pai = mat.get_editor_property("parent")
        if pai:
            nova.set_editor_property("parent", copia_com_vento(pai))
        mel.update_material_instance(nova)
        eal.save_loaded_asset(nova)
    COPIAS[caminho] = nova
    return nova


def arvore_com_vento(arvore, mestre_nao_usado=None):
    """cópia da árvore da fazenda com materiais que balançam (a da fazenda não muda)."""
    destino = PASTA + "/ArvoreVento/ArvoreVento"
    if eal.does_directory_exist(PASTA + "/ArvoreVento"):
        eal.delete_directory(PASTA + "/ArvoreVento")
    copia = eal.duplicate_asset(arvore.get_path_name().split(".")[0], destino)
    if not copia:
        log("FALHOU copiar a árvore")
        return None
    for i, sm in enumerate(copia.get_editor_property("static_materials")):
        original = sm.get_editor_property("material_interface")
        nome = str(sm.get_editor_property("material_slot_name"))
        if not original:
            continue
        novo = copia_com_vento(original)
        e_folha = "leaf" in nome.lower() or "leaves" in nome.lower()
        if isinstance(novo, unreal.MaterialInstanceConstant):
            mel.set_material_instance_scalar_parameter_value(novo, "Folha", 1.0 if e_folha else 0.0)
            mel.update_material_instance(novo)
            eal.save_loaded_asset(novo)
        copia.set_material(i, novo)
        log("   slot", i, nome, "->", "folha (treme)" if e_folha else "tronco/galho (balança)")
    eal.save_loaded_asset(copia)
    return copia


CODIGO_AAA = r"""
float3 lp = P - O;
float3 piv = float3(PV.x, -PV.y, PZ.x) * 100.0;
float nivel = PZ.y;
float flex = VC.r;
float fase = VC.g * 6.2832;
float folha = VC.b;
float faseF = VA * 6.2832;
float2 d = normalize(DIR.xy + float2(1e-4, 0.0));
float3 eixo = normalize(float3(-d.y, d.x, 0.0));
float vento = F * (0.6 + 0.6 * R);
float ht = saturate(lp.z / max(ALT, 100.0));
float3 o = float3(d, 0.0) * vento * (0.85 + 0.15 * sin(T * 0.7 + O.x * 0.01)) * 45.0 * ht * ht;
if (nivel > 0.5)
{
    float ang = (vento * (0.12 + 0.05 * nivel) + 0.07 * F * sin(T * (1.5 + 0.4 * nivel) + fase) + 0.02 * sin(T * 3.1 + fase * 2.0)) * flex;
    float3 r = lp - piv;
    float c = cos(ang);
    float s = sin(ang);
    float3 rr = r * c + cross(eixo, r) * s + eixo * dot(eixo, r) * (1.0 - c);
    o += rr - r;
}
o += folha * (0.8 + 4.5 * vento) * float3(sin(T * 10.0 + faseF), cos(T * 8.7 + faseF * 1.3), 0.6 * sin(T * 12.3 + faseF * 0.7));
return o;
"""


def mestre_aaa():
    """árvore do Blender: tronco dobra pela altura, cada galho gira em volta do pivô dele (UV1/UV2), folhas tremem."""
    m = novo_material("M_ArvoreAAA")
    m.set_editor_property("two_sided", True)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    por(m, "opacity_mask_clip_value", 0.45)
    por(m, "max_world_position_offset_displacement", 150.0)
    branco = unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture")
    normal_padrao = unreal.load_asset("/Engine/EngineMaterials/DefaultNormal")
    tc = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, -400, parameter_name="Cor", texture=branco)
    mel.connect_material_property(tc, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(tc, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    tn = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, -150, parameter_name="Normal", texture=normal_padrao,
              sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_property(tn, "RGB", unreal.MaterialProperty.MP_NORMAL)
    rug = expr(m, unreal.MaterialExpressionScalarParameter, -900, 80, parameter_name="Rugosidade", default_value=0.8)
    mel.connect_material_property(rug, "", unreal.MaterialProperty.MP_ROUGHNESS)
    p = parametros_vento(m, -1600, 300)
    wp = posicao_mundo(m, -1600, 750)
    op = expr(m, unreal.MaterialExpressionObjectPositionWS, -1600, 860)
    tempo = expr(m, unreal.MaterialExpressionTime, -1600, 960)
    vc = expr(m, unreal.MaterialExpressionVertexColor, -1600, 1040)
    pv = expr(m, unreal.MaterialExpressionTextureCoordinate, -1600, 1160, coordinate_index=1)
    pz = expr(m, unreal.MaterialExpressionTextureCoordinate, -1600, 1240, coordinate_index=2)
    alt = expr(m, unreal.MaterialExpressionScalarParameter, -1600, 1320, parameter_name="AlturaArvore", default_value=850.0)
    c = custom(m, -900, 500, CODIGO_AAA, ["P", "O", "T", "F", "R", "DIR", "VC", "VA", "PV", "PZ", "ALT"])
    for fonte, entrada in ((wp, "P"), (op, "O"), (tempo, "T"), (p["VentoForca"], "F"), (p["VentoRajada"], "R"),
                           (p["VentoDir"], "DIR"), (vc, "VC"), (pv, "PV"), (pz, "PZ"), (alt, "ALT")):
        ligar(fonte, "", c, entrada)
    ligar(vc, "A", c, "VA")    # a cor de vértice sai como RGB (float3): o alfa (fase da folha) entra separado
    mel.connect_material_property(c, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    return m


def arvore_blender(arvore_fazenda):
    """importa a árvore feita no Blender e põe os materiais AAA (casca da árvore da fazenda, folhas geradas)."""
    if not os.path.isfile(ENT + "/ArvoreBlender.fbx"):
        log("sem ArvoreBlender.fbx")
        return None
    if eal.does_directory_exist(PASTA + "/ArvoreBlender"):
        eal.delete_directory(PASTA + "/ArvoreBlender")
    caminhos = importar(ENT + "/ArvoreBlender.fbx", PASTA + "/ArvoreBlender")
    sms = [a for a in (unreal.load_asset(c) for c in caminhos) if isinstance(a, unreal.StaticMesh)]
    if not sms:
        log("FALHOU ArvoreBlender", caminhos)
        return None
    sm = sms[0]
    folhas = None
    p = importar(ENT + "/folhas_arvore.png", PASTA + "/ArvoreBlender")
    if p:
        folhas = unreal.load_asset(p[0])
    mestre = mestre_aaa()
    casca_cor = casca_nrm = None
    if arvore_fazenda:
        mats = arvore_fazenda.get_editor_property("static_materials")
        if mats:
            orig = mats[0].get_editor_property("material_interface")
            casca_cor = textura_do_gltf(orig, "cor")
            casca_nrm = textura_do_gltf(orig, "normal")
    for i, smat in enumerate(sm.get_editor_property("static_materials")):
        slot = str(smat.get_editor_property("material_slot_name")).upper()
        novo = mi("MI_ArvoreAAA_" + ("Folhas" if "FOLHA" in slot else "Casca"), mestre)
        if "FOLHA" in slot:
            if folhas:
                mel.set_material_instance_texture_parameter_value(novo, "Cor", folhas)
            mel.set_material_instance_scalar_parameter_value(novo, "Rugosidade", 0.6)
        else:
            if casca_cor:
                mel.set_material_instance_texture_parameter_value(novo, "Cor", casca_cor)
            if casca_nrm:
                mel.set_material_instance_texture_parameter_value(novo, "Normal", casca_nrm)
        mel.update_material_instance(novo)
        eal.save_loaded_asset(novo)
        sm.set_material(i, novo)
        log("   árvore Blender slot", slot, "->", novo.get_name())
    nanite(sm, folhagem=True)
    eal.save_loaded_asset(sm)
    return sm


# ----------------------------------------------------------------------------- peças do mapa
CUBO = "/Engine/BasicShapes/Cube.Cube"
PLANO = "/Engine/BasicShapes/Plane.Plane"


def caixa(x, y, z_topo, tam, material=None, nome="Caixa"):
    sm = unreal.load_asset(CUBO)
    a = eas.spawn_actor_from_object(sm, U(x, y, z_topo - tam[2] / 2), unreal.Rotator(0, 0, 0))
    a.set_actor_scale3d(unreal.Vector(tam[0], tam[1], tam[2]))
    if material:
        a.get_component_by_class(unreal.StaticMeshComponent).set_material(0, material)
    a.set_actor_label(nome)
    return a


def placa(texto, x, y, z, tamanho=45.0, cor=(255, 255, 255)):
    # virada para o drone (que olha para frente = -Y do Unreal): a frente do texto aponta para +Y
    t = eas.spawn_actor_from_class(unreal.TextRenderActor, U(x, y, z), unreal.Rotator(0, 0, 90))
    c = t.get_component_by_class(unreal.TextRenderComponent)
    c.set_editor_property("text", texto)
    por(c, "world_size", tamanho)
    por(c, "horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
    por(c, "text_render_color", unreal.Color(cor[0], cor[1], cor[2], 255))
    t.set_actor_label("Placa_" + chave(texto)[:20])
    return t


def luz_e_ceu():
    sol = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 5000), unreal.Rotator(roll=0, pitch=-46, yaw=-145))
    lc = sol.get_component_by_class(unreal.DirectionalLightComponent)
    for p_, v in (("intensity", 10.0), ("use_temperature", True), ("temperature", 5600.0), ("atmosphere_sun_light", True),
                  ("light_source_angle", 0.6), ("shadow_amount", 0.85), ("mobility", unreal.ComponentMobility.MOVABLE)):
        por(lc, p_, v)
    sol.set_actor_label("Sol")
    eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)).set_actor_label("Ceu")
    try:
        eas.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)).set_actor_label("Nuvens")
    except Exception as e:
        log("sem nuvens:", e)
    sky = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, 0, 0))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    for p_, v in (("real_time_capture", True), ("mobility", unreal.ComponentMobility.MOVABLE), ("intensity", 1.25)):
        por(sc, p_, v)
    sky.set_actor_label("LuzDoCeu")
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    for p_, v in (("fog_density", 0.007), ("start_distance", 3000.0), ("fog_height_falloff", 0.06)):
        por(fc, p_, v)
    fog.set_actor_label("Neblina")
    ppv = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    ppv.set_editor_property("unbound", True)
    s = ppv.get_editor_property("settings")
    for nome, valor in (("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM), ("auto_exposure_bias", 0.3),
                        ("lumen_skylight_leaking", 0.22), ("bloom_intensity", 0.3), ("film_toe", 0.58)):
        try:
            s.set_editor_property("override_" + nome, True)
            s.set_editor_property(nome, valor)
        except Exception as e:
            log("  pp ignorado", nome, e)
    ppv.set_editor_property("settings", s)
    ppv.set_actor_label("PosProcesso")


def material_do_terreno_da_fazenda():
    """o mesmo material que está no terreno da fazenda (pega direto da malha de lá)."""
    if eal.does_directory_exist("/Game/Campo/Malhas/Terreno"):
        for c in eal.list_assets("/Game/Campo/Malhas/Terreno", recursive=True, include_folder=False):
            a = eal.load_asset(c)
            if isinstance(a, unreal.StaticMesh):
                mats = a.get_editor_property("static_materials")
                if mats:
                    m = mats[0].get_editor_property("material_interface")
                    log("material do terreno:", m.get_path_name() if m else None)
                    return m
    for p in ("/Game/Campo/Materiais/M_Terreno", "/Game/Campo/Materiais/MI_TERRENO"):
        if eal.does_asset_exist(p):
            return unreal.load_asset(p)
    return None


def nanite(sm, folhagem=True):
    ns = sm.get_editor_property("nanite_settings")
    ns.set_editor_property("enabled", True)
    if folhagem:
        try:
            ns.set_editor_property("preserve_area", True)
        except Exception:
            pass
    sm.set_editor_property("nanite_settings", ns)


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    open(LOG, "w", encoding="utf-8").write("construir_vitrine.py\n")
    try:
        with open(ENT + "/vitrine.json", encoding="utf-8") as f:
            info = json.load(f)
        assets = todos_assets()
        log("assets do Fab no projeto:", len(assets))
        for d in assets[:300]:
            if classe(d) in ("MaterialInstanceConstant", "StaticMesh", "SkeletalMesh", "Blueprint"):
                log("   ", classe(d), d.package_name)

        # materiais
        m_capim = mestre_capim()
        m_arvore = None   # a árvore com vento usa uma cópia do mestre do glTF (ver copia_com_vento)
        mis = {"TERRENO": material_do_terreno_da_fazenda()}
        for slot, c in CORES_FOLHA.items():
            i = mi("MI_V_" + slot, m_capim)
            mel.set_material_instance_vector_parameter_value(i, "Cor", unreal.LinearColor(c[0], c[1], c[2], 1))
            mel.update_material_instance(i)
            eal.save_loaded_asset(i)
            mis[slot] = i
        log("materiais com vento prontos")

        # malhas da vitrine
        if eal.does_directory_exist(PASTA + "/Malhas"):
            eal.delete_directory(PASTA + "/Malhas")
        malhas = {}
        for arq in sorted(os.listdir(ENT)):
            if not arq.lower().endswith(".fbx"):
                continue
            nome = arq[:-4]
            if nome == "ArvoreBlender":
                continue    # tem material próprio (vento AAA), montada mais abaixo
            caminhos = importar(ENT + "/" + arq, PASTA + "/Malhas/" + nome)
            sms = [unreal.load_asset(c) for c in caminhos]
            sms = [a for a in sms if isinstance(a, unreal.StaticMesh)]
            if not sms:
                log("FALHOU", arq, caminhos)
                continue
            sm = sms[0]
            for i, smat in enumerate(sm.get_editor_property("static_materials")):
                slot = str(smat.get_editor_property("material_slot_name")).upper()
                alvo = mis.get(slot) or next((v for k, v in sorted(mis.items(), key=lambda kv: -len(kv[0])) if slot.startswith(k)), None)
                if alvo:
                    sm.set_material(i, alvo)
                else:
                    log("  slot sem material:", nome, slot)
            nanite(sm, folhagem=nome != "TerrenoVitrine")
            if nome == "TerrenoVitrine":
                try:
                    bs = sm.get_editor_property("body_setup")
                    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                except Exception as e:
                    log("colisão do terreno:", e)
            eal.save_loaded_asset(sm)
            malhas[nome] = sm
            log("malha", nome)

        mundo = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        luz_e_ceu()
        for nome, sm in malhas.items():
            a = eas.spawn_actor_from_object(sm, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
            a.set_actor_label(nome)
            if nome == "TerrenoVitrine":
                tag(a, "Terreno")
            else:
                tag(a, "Vento")
                a.set_actor_enable_collision(False)
                c = a.get_component_by_class(unreal.StaticMeshComponent)
                if nome != "MilhoVitrine":
                    por(c, "cast_shadow", False)
                por(c, "affect_distance_field_lighting", False)

        # canteiros Megascans
        neutro = unreal.load_asset("/Game/Campo/Materiais/MI_BASE")
        dry = achar(assets, ["drysoil"], ("MaterialInstanceConstant",))
        arid = achar(assets, ["aridsoil"], ("MaterialInstanceConstant",))
        log("Dry Soil:", dry.get_path_name() if dry else "FALTA ADICIONAR", "| Arid Soil:", arid.get_path_name() if arid else "FALTA ADICIONAR")
        nomes = ("DRY SOIL (MEGASCANS)", "ARID SOIL (MEGASCANS)")
        for (cx, cy, lx, ly), mat, nome in zip(info["canteiros"], (dry, arid), nomes):
            caixa(cx, cy, 0.03, (lx, ly, 0.2), mat or neutro, "Canteiro_" + chave(nome)[:10])
            placa(nome + ("" if mat else "\nFALTA ADICIONAR"), cx, cy - ly / 2 - 0.6, 0.9, 40.0, (255, 255, 255) if mat else (255, 190, 60))

        # laguinho (ondas com o vento — o jogo procura a tag "Agua")
        agua = unreal.load_asset("/Game/Campo/Materiais/M_Agua")
        lx, ly, ll, lf = info["lago"]
        a = eas.spawn_actor_from_object(unreal.load_asset(PLANO), U(lx, ly, 0.04), unreal.Rotator(0, 0, 0))
        a.set_actor_scale3d(unreal.Vector(ll, lf, 1))
        if agua:
            a.get_component_by_class(unreal.StaticMeshComponent).set_material(0, agua)
        a.set_actor_enable_collision(False)
        a.set_actor_label("Laguinho")
        tag(a, "Agua")
        placa("LAGO (ONDAS DO VENTO)", lx, ly - lf / 2 - 0.6, 0.9, 40.0)
        mx, my, ml, mf = info["milho"]
        placa("MILHO (VENTO)", mx, my - mf / 2 - 0.6, 0.9, 40.0)

        # árvores: atual parada | atual com vento | nova (Megaplants)
        arvore_atual = None
        if eal.does_directory_exist("/Game/Campo/Modelos/island_tree_01"):
            for c in eal.list_assets("/Game/Campo/Modelos/island_tree_01", recursive=True, include_folder=False):
                obj = eal.load_asset(c)
                if isinstance(obj, unreal.StaticMesh):
                    arvore_atual = obj
                    break
        ax, ay = info["arvores"]["atual"]
        vx, vy = info["arvores"]["vento"]
        nx, ny = info["arvores"]["nova"]
        if arvore_atual:
            a = eas.spawn_actor_from_object(arvore_atual, U(ax, ay, -0.05), unreal.Rotator(0, 0, 0))
            a.set_actor_scale3d(unreal.Vector(2.9, 2.9, 2.9))
            a.set_actor_label("ArvoreParada")
            placa("ÁRVORE ATUAL (PARADA)", ax, ay - 3.5, 1.2)
            av = arvore_com_vento(arvore_atual, m_arvore)
            if av:
                a = eas.spawn_actor_from_object(av, U(vx, vy, -0.05), unreal.Rotator(0, 0, 37))
                a.set_actor_scale3d(unreal.Vector(2.9, 2.9, 2.9))
                a.set_actor_label("ArvoreComVento")
                tag(a, "Vento")
                placa("ÁRVORE ATUAL COM VENTO", vx, vy - 3.5, 1.2, 45.0, (140, 220, 255))
        # árvore feita no Blender com vento AAA (galhos giram em volta do pivô, folhas tremem)
        ab = arvore_blender(arvore_atual)
        if ab:
            bx, by = info.get("arvore_blender", [17.0, 24.0])
            a = eas.spawn_actor_from_object(ab, U(bx, by, -0.1), unreal.Rotator(0, 0, 0))
            a.set_actor_label("ArvoreBlender")
            tag(a, "Vento")
            placa("ÁRVORE DO BLENDER (VENTO AAA)", bx, by - 4.0, 1.2, 45.0, (150, 255, 170))

        nova = (achar(assets, ["maple"], ("StaticMesh", "SkeletalMesh", "Blueprint"))
                or achar(assets, ["acer"], ("StaticMesh", "SkeletalMesh", "Blueprint"))
                or achar(assets, ["megaplant"], ("StaticMesh", "SkeletalMesh", "Blueprint")))
        log("árvore nova:", nova.get_path_name() if nova else "FALTA ADICIONAR")
        if nova:
            a = eas.spawn_actor_from_object(nova, U(nx, ny, -0.05), unreal.Rotator(0, 0, 0))
            a.set_actor_label("ArvoreNova")
            placa("ÁRVORE NOVA (MEGAPLANTS)", nx, ny - 3.5, 1.2)
        else:
            caixa(nx, ny, 0.3, (1.5, 1.5, 0.3), neutro, "LugarArvoreNova")
            placa("ÁRVORE NOVA (MEGAPLANTS)\nFALTA ADICIONAR", nx, ny - 3.5, 1.2, 45.0, (255, 190, 60))

        # drone começa de frente para tudo (olhando para +y do Blender = -Y do Unreal)
        ix, iy = info["inicio"]
        ps = eas.spawn_actor_from_class(unreal.PlayerStart, U(ix, iy, 0.6), unreal.Rotator(0, 0, -90))
        ps.set_actor_label("InicioDrone")

        # voo de teste: capim de perto, rente ao chão, canteiros, lago, milho, árvores
        vistas = [(0, 1.5, 1.2), (-6, 2.0, 0.5), (0, 4.5, 1.2), (-12, -1.5, 1.5), (-10, 16.5, 1.6),
                  (-9, 11.0, 3.0), (0, 13.0, 3.5), (0, 15.0, 6.0), (6, 9.0, 0.7), (15, 15.0, 3.5), (17, 19.0, 6.0)]
        for i, (x, y, z) in enumerate(vistas):
            e = eas.spawn_actor_from_class(unreal.TargetPoint, U(x, y, z), unreal.Rotator(0, 0, -90))
            e.set_actor_label("Vista_%02d" % i)
            tag(e, "Rota_%d" % i)

        ok = unreal.EditorLoadingAndSavingUtils.save_map(mundo, MAPA)
        log("mapa salvo em", MAPA, ok)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("TUDO PRONTO")
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
    finally:
        unreal.SystemLibrary.quit_editor()


main()
