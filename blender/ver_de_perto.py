# Abre o estúdio pronto para olhar o drone de perto, em tempo real, na placa de vídeo.
import bpy

def ligar_gpu():
    scn = bpy.context.scene
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for tipo in ('HIP', 'OPTIX', 'CUDA', 'ONEAPI'):
            try:
                prefs.compute_device_type = tipo
            except Exception:
                continue
            prefs.get_devices()
            if any(d.type == tipo for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == tipo
                scn.cycles.device = 'GPU'
                break
    except Exception as e:
        print('sem GPU:', e)
    scn.cycles.preview_samples = 64
    scn.cycles.use_preview_denoising = True

def preparar_tela():
    ligar_gpu()
    for janela in bpy.context.window_manager.windows:
        for area in janela.screen.areas:
            if area.type == 'VIEW_3D':
                for esp in area.spaces:
                    if esp.type == 'VIEW_3D':
                        esp.shading.type = 'RENDERED'
                        esp.overlay.show_overlays = False
                        esp.region_3d.view_perspective = 'PERSP'
                        esp.lens = 60
                        esp.clip_start = 0.002
                with bpy.context.temp_override(window=janela, area=area, region=[r for r in area.regions if r.type == 'WINDOW'][0]):
                    bpy.ops.object.select_all(action='DESELECT')
                    for o in bpy.data.objects:
                        if o.type == 'MESH' and o.name.startswith('Body'):
                            o.select_set(True)
                    bpy.ops.view3d.view_selected()
                    bpy.ops.object.select_all(action='DESELECT')
    return None

bpy.app.timers.register(preparar_tela, first_interval=1.0)
