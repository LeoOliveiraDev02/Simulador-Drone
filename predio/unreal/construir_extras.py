"""Peças extras do jogo único (roda no editor com -ExecutePythonScript):
  /Game/UI/T_Usina        imagem do mapa 3 (cartão trancado do menu)
  /Game/UI/T_Fazenda, T_Predio  fotos dos cartões dos mapas 1 e 2
  /Game/UI/S_Coleta, S_Foto, S_Blip, S_Vitoria  sons curtos
  /Game/Drone/E88_Corpo   drone E88 da abertura (sem as hélices)
  /Game/Drone/E88_Helice  uma hélice (o jogo põe 4 e faz girar)
Entrada: D:/DronePredio/conteudo_extras/"""
import os, time, traceback, unicodedata
import unreal

RAIZ = os.environ.get("PREDIO_RAIZ", "D:/DronePredio").replace("\\", "/")
ENT = RAIZ + "/conteudo_extras"
LOG = RAIZ + "/logs/construir_extras_progresso.txt"
at = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
T0 = time.time()


def log(*a):
    msg = "[%6.1fs] " % (time.time() - T0) + " ".join(str(x) for x in a)
    unreal.log(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def importar(arq, destino):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", arq)
    t.set_editor_property("destination_path", destino)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", False)
    at.import_asset_tasks([t])
    return list(t.get_editor_property("imported_object_paths") or [])


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def material_drone():
    if eal.does_asset_exist("/Game/Drone/M_DroneCor"):
        eal.delete_asset("/Game/Drone/M_DroneCor")
    m = at.create_asset("M_DroneCor", "/Game/Drone", unreal.Material, unreal.MaterialFactoryNew())

    def ex(c, x, y, **p):
        e = mel.create_material_expression(m, c, x, y)
        for k, v in p.items():
            e.set_editor_property(k, v)
        return e
    cor = ex(unreal.MaterialExpressionVectorParameter, -700, -100, parameter_name="Cor", default_value=unreal.LinearColor(0.03, 0.03, 0.03, 1))
    mk = ex(unreal.MaterialExpressionComponentMask, -500, -100, r=True, g=True, b=True, a=False)
    mel.connect_material_expressions(cor, "", mk, "")
    mel.connect_material_property(mk, "", unreal.MaterialProperty.MP_BASE_COLOR)
    for nome, prop, val, y in (("Rugosidade", unreal.MaterialProperty.MP_ROUGHNESS, 0.5, 50),
                               ("Metal", unreal.MaterialProperty.MP_METALLIC, 0.0, 150)):
        p = ex(unreal.MaterialExpressionScalarParameter, -700, y, parameter_name=nome, default_value=val)
        mel.connect_material_property(p, "", prop)
    bri = ex(unreal.MaterialExpressionScalarParameter, -700, 250, parameter_name="Brilho", default_value=0.0)
    mul = ex(unreal.MaterialExpressionMultiply, -400, 250)
    mel.connect_material_expressions(mk, "", mul, "A")
    mel.connect_material_expressions(bri, "", mul, "B")
    mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    return m


# palavra no nome do material do Blender -> (cor, rugosidade, metal, brilho)
CORES = [
    ("led de tr", ((1.0, 0.04, 0.02), 0.4, 0.0, 40.0)),
    ("led da frente", ((1.0, 1.0, 0.95), 0.4, 0.0, 25.0)),
    ("lente", ((0.01, 0.012, 0.02), 0.05, 0.0, 0.0)),
    ("motor", ((0.55, 0.55, 0.56), 0.3, 1.0, 0.0)),
    ("grafite", ((0.08, 0.08, 0.085), 0.4, 0.6, 0.0)),
    ("tampa", ((0.3, 0.3, 0.32), 0.45, 0.2, 0.0)),
    ("acetinado", ((0.025, 0.025, 0.027), 0.35, 0.0, 0.0)),
    ("helice", ((0.02, 0.02, 0.02), 0.5, 0.0, 0.0)),
    ("", ((0.03, 0.03, 0.032), 0.6, 0.0, 0.0)),
]


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    open(LOG, "w", encoding="utf-8").write("construir_extras.py\n")
    try:
        for arq, nome in (("usina.png", "T_Usina"), ("fazenda.png", "T_Fazenda"), ("predio.png", "T_Predio")):
            if not os.path.isfile(ENT + "/" + arq):
                log("falta", arq)
                continue
            p = importar(ENT + "/" + arq, "/Game/UI")
            if not p:
                log("FALHOU imagem", arq)
                continue
            tex = unreal.load_asset(p[0])
            if tex.get_name() != nome:
                if eal.does_asset_exist("/Game/UI/" + nome):
                    eal.delete_asset("/Game/UI/" + nome)
                eal.rename_asset(p[0].split(".")[0], "/Game/UI/" + nome)
                tex = unreal.load_asset("/Game/UI/" + nome)
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON)
            tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
            tex.set_editor_property("never_stream", True)
            eal.save_loaded_asset(tex)
            log("imagem:", tex.get_path_name())
        # sons curtos do jogo (coleta, foto, entrega/aro, vitória)
        for arq, nome in (("coleta.wav", "S_Coleta"), ("foto.wav", "S_Foto"), ("blip.wav", "S_Blip"), ("vitoria.wav", "S_Vitoria")):
            if not os.path.isfile(ENT + "/" + arq):
                log("falta", arq)
                continue
            p = importar(ENT + "/" + arq, "/Game/UI")
            if not p:
                log("FALHOU som", arq)
                continue
            if p[0].split(".")[0] != "/Game/UI/" + nome:
                if eal.does_asset_exist("/Game/UI/" + nome):
                    eal.delete_asset("/Game/UI/" + nome)
                eal.rename_asset(p[0].split(".")[0], "/Game/UI/" + nome)
            eal.save_asset("/Game/UI/" + nome)
            log("som:", nome)
        mestre = material_drone()
        fac = unreal.MaterialInstanceConstantFactoryNew()
        feitos = {}
        for nome in ("E88_Corpo", "E88_Helice"):
            caminhos = importar(ENT + "/" + nome + ".fbx", "/Game/Drone")
            sms = [unreal.load_asset(c) for c in caminhos]
            sms = [a for a in sms if isinstance(a, unreal.StaticMesh)]
            if not sms:
                log("FALHOU", nome, caminhos)
                continue
            sm = sms[0]
            if sm.get_path_name().split(".")[0] != "/Game/Drone/" + nome:
                eal.rename_asset(sm.get_path_name().split(".")[0], "/Game/Drone/" + nome)
                sm = unreal.load_asset("/Game/Drone/" + nome)
            for i, smat in enumerate(sm.get_editor_property("static_materials")):
                slot = sem_acento(str(smat.get_editor_property("material_slot_name")).replace("_", " "))
                for chave, (cor, rug, met, bri) in CORES:
                    if chave in slot:
                        k = chave or "padrao"
                        if k not in feitos:
                            mi = at.create_asset("MI_E88_" + k.replace(" ", "_"), "/Game/Drone", unreal.MaterialInstanceConstant, fac)
                            mi.set_editor_property("parent", mestre)
                            mel.set_material_instance_vector_parameter_value(mi, "Cor", unreal.LinearColor(*cor, 1))
                            mel.set_material_instance_scalar_parameter_value(mi, "Rugosidade", rug)
                            mel.set_material_instance_scalar_parameter_value(mi, "Metal", met)
                            mel.set_material_instance_scalar_parameter_value(mi, "Brilho", bri)
                            mel.update_material_instance(mi)
                            feitos[k] = mi
                        sm.set_material(i, feitos[k])
                        log("  slot", slot, "->", k)
                        break
            ns = sm.get_editor_property("nanite_settings")
            ns.set_editor_property("enabled", False)
            sm.set_editor_property("nanite_settings", ns)
            eal.save_loaded_asset(sm)
            log("malha", sm.get_path_name())
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log("TUDO PRONTO")
    except Exception:
        log("ERRO:\n" + traceback.format_exc())
    finally:
        unreal.SystemLibrary.quit_editor()


main()
