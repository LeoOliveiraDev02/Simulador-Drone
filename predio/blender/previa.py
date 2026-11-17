"""Prévia rápida (Workbench) de um ou mais grupos: python previa.py saida.png Grupo1,Grupo2 camx,camy,camz alvox,alvoy,alvoz"""
import sys, math
import bpy  # noqa
import gerar_predio as gp
from mathutils import Vector

saida, grupos, cam, alvo = sys.argv[1], sys.argv[2].split(","), [float(v) for v in sys.argv[3].split(",")], [float(v) for v in sys.argv[4].split(",")]
bpy.ops.wm.read_factory_settings(use_empty=True)
gp.malha_portal()
for k in range(gp.N_ANDARES):
    gp.andar(k)
for n in grupos:
    ob = gp.construir_objeto(gp.GRUPOS[n])
    ob.data.color_attributes.active_color_index = 0
sc = bpy.context.scene
camd = bpy.data.cameras.new("c"); camd.lens = 14
co = bpy.data.objects.new("c", camd); sc.collection.objects.link(co); sc.camera = co
co.location = Vector(cam)
d = Vector(alvo) - Vector(cam)
co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'VERTEX'
sc.display.shading.show_cavity = True
sc.display.shading.show_shadows = True
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.filepath = saida
bpy.ops.render.render(write_still=True)
