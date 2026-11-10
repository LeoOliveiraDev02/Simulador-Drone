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

def modo_tempo_real():
    # EEVEE: motor em tempo real da placa de vídeo (60 fps), com reflexos por raytracing.
    # As fotos finais continuam no Cycles (RENDERIZAR_NA_GPU.bat).
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_EEVEE'
    ee = scn.eevee
    for nome, valor in (('use_raytracing', True), ('ray_tracing_method', 'SCREEN'), ('use_shadows', True),
                        ('taa_samples', 64), ('use_taa_reprojection', True), ('use_gtao', True),
                        ('shadow_ray_count', 3), ('shadow_step_count', 12), ('use_shadow_jitter_viewport', False)):
        if hasattr(ee, nome):
            setattr(ee, nome, valor)
    try:
        rt = ee.ray_tracing_options
        rt.resolution_scale = '1'
        rt.use_denoise = True
        rt.denoise_spatial = True
        rt.denoise_temporal = True
        rt.denoise_bilateral = True
    except Exception:
        pass

def preparar_tela():
    ligar_gpu()
    modo_tempo_real()
    scn = bpy.context.scene
    scn.sync_mode = 'AUDIO_SYNC'   # toca as hélices na velocidade certa (60 quadros por segundo)
    tocou = False
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
                    if not tocou and not bpy.context.screen.is_animation_playing:
                        bpy.ops.screen.animation_play()
                        tocou = True
    return None

bpy.app.timers.register(preparar_tela, first_interval=1.0)
