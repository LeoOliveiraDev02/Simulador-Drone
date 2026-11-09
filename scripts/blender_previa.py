# Renderiza uma prévia rápida (Workbench) de um .glb visto de lado e de cima.
# Uso: blender -b -P blender_previa.py -- entrada.glb saida.png
import bpy, sys, math
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
objs = [o for o in bpy.data.objects if o.type == 'MESH']
mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
centro = (mn + mx) / 2
tam = max(mx - mn)
scn = bpy.context.scene
scn.render.engine = 'BLENDER_WORKBENCH'
scn.display.shading.light = 'STUDIO'
scn.display.shading.color_type = 'MATERIAL'
scn.render.resolution_x = 640
scn.render.resolution_y = 480
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scn.collection.objects.link(cam)
scn.camera = cam
cam.data.type = 'ORTHO'
cam.data.ortho_scale = tam * 1.3
# Blender é Z para cima (o importador já converte o Y do glTF)
cam.location = centro + Vector((tam * 2, -tam * 2, tam * 1.2))
cam.rotation_euler = (centro - cam.location).to_track_quat('-Z', 'Y').to_euler()
scn.render.filepath = a[1]
bpy.ops.render.render(write_still=True)
