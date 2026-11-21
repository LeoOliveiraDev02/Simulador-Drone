"""Vitrine de testes (roda no editor com -ExecutePythonScript): um mapa pequeno para ver assets novos
um de cada vez antes de levar para a fazenda.

  /Game/Mapas/Vitrine
    - três canteiros de chão lado a lado: ATUAL (o chão da fazenda hoje) | DRY SOIL | ARID SOIL (Megascans)
    - duas árvores: ATUAL (a da fazenda hoje) | NOVA (Quixel Megaplants, quando estiver no projeto)
    - mesmo céu, sol e pós-processo da fazenda; o drone começa na frente dos canteiros
    - pontos Rota_N para o voo de teste tirar fotos de perto

Os assets do Fab são achados sozinhos pelo nome (onde quer que o Fab tenha colocado no projeto).
Enquanto não estiverem no projeto, o canteiro/árvore aparece com uma placa "FALTA ADICIONAR".
"""
import os
import re
import time
import traceback

import unreal

RAIZ = os.environ.get("PREDIO_RAIZ", "D:/DronePredio").replace("\\", "/")
LOG = RAIZ + "/logs/construir_vitrine_progresso.txt"
MAPA = "/Game/Mapas/Vitrine"
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
eal = unreal.EditorAssetLibrary
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


# ----------------------------------------------------------------------------- procurar assets do Fab
NOSSAS = ("/Game/Campo", "/Game/Predio", "/Game/UI", "/Game/Drone", "/Game/Mapas", "/Game/Developers", "/Game/Collections")


def todos_assets():
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    res = []
    for d in ar.get_assets_by_path("/Game", recursive=True):
        caminho = str(d.package_name)
        if caminho.startswith(NOSSAS):
            continue
        res.append(d)
    return res


def classe(d):
    try:
        return str(d.asset_class_path.asset_name)
    except Exception:
        return str(d.asset_class)


def achar(assets, palavras, classes):
    """primeiro asset cujo nome (sem _ e maiúsculas) contém todas as palavras e é de uma das classes."""
    melhores = []
    for d in assets:
        nome = chave(str(d.asset_name) + " " + str(d.package_path))
        if all(p in nome for p in palavras) and classe(d) in classes:
            melhores.append(d)
    if not melhores:
        return None
    melhores.sort(key=lambda d: len(str(d.package_name)))
    return unreal.load_asset(str(melhores[0].package_name))


# ----------------------------------------------------------------------------- peças do mapa
CUBO = "/Engine/BasicShapes/Cube.Cube"
PLANO = "/Engine/BasicShapes/Plane.Plane"


def caixa(pos, tam, material=None, nome="Caixa"):
    """caixa (tam em metros) com o topo em pos.z."""
    sm = unreal.load_asset(CUBO)
    a = eas.spawn_actor_from_object(sm, unreal.Vector(pos[0] * 100, pos[1] * 100, pos[2] * 100 - tam[2] * 50), unreal.Rotator(0, 0, 0))
    a.set_actor_scale3d(unreal.Vector(tam[0], tam[1], tam[2]))
    if material:
        a.get_component_by_class(unreal.StaticMeshComponent).set_material(0, material)
    a.set_actor_label(nome)
    return a


def placa(texto, pos, yaw=0.0, tamanho=60.0, cor=(255, 255, 255)):
    t = eas.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(pos[0] * 100, pos[1] * 100, pos[2] * 100), unreal.Rotator(0, 0, yaw))
    c = t.get_component_by_class(unreal.TextRenderComponent)
    c.set_editor_property("text", texto)
    por(c, "world_size", tamanho)
    por(c, "horizontal_alignment", unreal.HorizTextAligment.EHTA_CENTER)
    por(c, "text_render_color", unreal.Color(cor[0], cor[1], cor[2], 255))
    t.set_actor_label("Placa_" + chave(texto)[:20])
    return t


def luz_e_ceu():
    """o mesmo dia de céu aberto da fazenda (sol, atmosfera, nuvens, luz do céu, névoa leve, pós-processo)."""
    sol = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 5000), unreal.Rotator(roll=0, pitch=-46, yaw=-145))
    lc = sol.get_component_by_class(unreal.DirectionalLightComponent)
    por(lc, "intensity", 10.0)
    por(lc, "use_temperature", True)
    por(lc, "temperature", 5600.0)
    por(lc, "atmosphere_sun_light", True)
    por(lc, "light_source_angle", 0.6)
    por(lc, "shadow_amount", 0.85)
    por(lc, "mobility", unreal.ComponentMobility.MOVABLE)
    sol.set_actor_label("Sol")
    eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)).set_actor_label("Ceu")
    try:
        eas.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0)).set_actor_label("Nuvens")
    except Exception as e:
        log("sem nuvens:", e)
    sky = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, 0, 0))
    sc = sky.get_component_by_class(unreal.SkyLightComponent)
    por(sc, "real_time_capture", True)
    por(sc, "mobility", unreal.ComponentMobility.MOVABLE)
    por(sc, "intensity", 1.25)
    sky.set_actor_label("LuzDoCeu")
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    por(fc, "fog_density", 0.007)
    por(fc, "start_distance", 3000.0)
    por(fc, "fog_height_falloff", 0.06)
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


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    open(LOG, "w", encoding="utf-8").write("construir_vitrine.py\n")
    try:
        assets = todos_assets()
        log("assets fora das nossas pastas (do Fab):", len(assets))
        for d in assets[:400]:
            if classe(d) in ("MaterialInstanceConstant", "StaticMesh", "SkeletalMesh", "Blueprint", "Material"):
                log("   ", classe(d), d.package_name)

        mundo = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        log("mapa em branco:", mundo)
        luz_e_ceu()

        chao_atual = unreal.load_asset("/Game/Campo/Materiais/MI_TERRENO") or unreal.load_asset("/Game/Campo/Materiais/MI_PISO")
        neutro = unreal.load_asset("/Game/Campo/Materiais/MI_BASE")
        dry = achar(assets, ["drysoil"], ("MaterialInstanceConstant",))
        arid = achar(assets, ["aridsoil"], ("MaterialInstanceConstant",))
        log("chão Dry Soil:", dry.get_path_name() if dry else "FALTA ADICIONAR")
        log("chão Arid Soil:", arid.get_path_name() if arid else "FALTA ADICIONAR")

        # chão grande em volta (o da fazenda) e os três canteiros de 14 x 14 m, 2 cm acima
        caixa((0, 0, 0), (220, 220, 1), chao_atual, "ChaoVolta")
        canteiros = (("ATUAL (FAZENDA HOJE)", chao_atual, -16), ("DRY SOIL (MEGASCANS)", dry, 0), ("ARID SOIL (MEGASCANS)", arid, 16))
        for nome, mat, x in canteiros:
            caixa((x, 10, 0.02), (14, 14, 0.2), mat or neutro, "Canteiro_" + chave(nome)[:12])
            placa(nome if mat else nome + "\nFALTA ADICIONAR", (x, 2.6, 0.9), yaw=90.0, tamanho=55.0,
                  cor=(255, 255, 255) if mat else (255, 190, 60))

        # árvores: a atual e a nova (Megaplants), lado a lado, a 30 m dos canteiros
        arvore_atual = None
        for p in ("/Game/Campo/Modelos/island_tree_01", "/Game/Campo/Modelos/island_tree_02"):
            if eal.does_directory_exist(p):
                for c in eal.list_assets(p, recursive=True, include_folder=False):
                    a = eal.load_asset(c)
                    if isinstance(a, unreal.StaticMesh):
                        arvore_atual = a
                        break
            if arvore_atual:
                break
        nova = (achar(assets, ["maple"], ("StaticMesh", "SkeletalMesh", "Blueprint"))
                or achar(assets, ["acer"], ("StaticMesh", "SkeletalMesh", "Blueprint"))
                or achar(assets, ["megaplant"], ("StaticMesh", "SkeletalMesh", "Blueprint")))
        log("árvore atual:", arvore_atual.get_path_name() if arvore_atual else "não achada")
        log("árvore nova:", nova.get_path_name() if nova else "FALTA ADICIONAR")
        if arvore_atual:
            a = eas.spawn_actor_from_object(arvore_atual, unreal.Vector(-1400, 4000, 0), unreal.Rotator(0, 0, 0))
            a.set_actor_scale3d(unreal.Vector(2.9, 2.9, 2.9))
            a.set_actor_label("ArvoreAtual")
        placa("ÁRVORE ATUAL", (-14, 31, 1.2), yaw=90.0, tamanho=70.0)
        if nova:
            a = eas.spawn_actor_from_object(nova, unreal.Vector(1400, 4000, 0), unreal.Rotator(0, 0, 0))
            a.set_actor_label("ArvoreNova")
            placa("ÁRVORE NOVA (MEGAPLANTS)", (14, 31, 1.2), yaw=90.0, tamanho=70.0)
        else:
            caixa((14, 40, 0.3), (2, 2, 0.3), neutro, "LugarArvoreNova")
            placa("ÁRVORE NOVA (MEGAPLANTS)\nFALTA ADICIONAR", (14, 31, 1.2), yaw=90.0, tamanho=70.0, cor=(255, 190, 60))

        # drone começa de frente para os canteiros
        ps = eas.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0, -600, 120), unreal.Rotator(0, 0, 90))
        ps.set_actor_label("InicioDrone")

        # pontos do voo de teste (fotos): perto de cada canteiro e de cada árvore
        vistas = [(-16, 1.0, 1.2, 90), (0, 1.0, 1.2, 90), (16, 1.0, 1.2, 90),    # chão de perto
                  (-16, 6.0, 0.6, 90), (0, 6.0, 0.6, 90), (16, 6.0, 0.6, 90),    # rente ao chão
                  (-14, 22, 3.0, 90), (14, 22, 3.0, 90),                         # árvores de frente
                  (0, 18, 9.0, 90)]                                              # as duas de cima
        for i, (x, y, z, yaw) in enumerate(vistas):
            e = eas.spawn_actor_from_class(unreal.TargetPoint, unreal.Vector(x * 100, y * 100, z * 100), unreal.Rotator(0, 0, yaw))
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
