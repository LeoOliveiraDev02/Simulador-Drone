# Exporta só o drone E88 do estúdio para o Godot (GLB com materiais PBR).
# Uso: blender -b e88_estudio.blend -P exportar_e88_godot.py -- SAIDA.glb
import bpy, sys
saida = sys.argv[sys.argv.index('--') + 1:][0]
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA') or o.name.startswith(('Tampo', 'Tapete')):
        bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.data.objects:
    if o.animation_data:
        o.animation_data_clear()
    if o.name.startswith('Eixo'):
        o.rotation_euler = (0, 0, 0)
bpy.ops.export_scene.gltf(filepath=saida, export_format='GLB', export_yup=True, export_apply=True,
                          export_materials='EXPORT', export_animations=False, export_lights=False,
                          export_cameras=False)
print('exportado', saida)
