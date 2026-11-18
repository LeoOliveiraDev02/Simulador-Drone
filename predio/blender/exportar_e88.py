"""Exporta o E88 (modelo da Godot) para o Unreal: E88_Corpo.fbx (tudo menos as hélices, frente = +X)
e E88_Helice.fbx (uma hélice no centro, gira em Z) + e88.json com a posição dos 4 eixos (cm, eixos do Unreal).
python3 exportar_e88.py e88.glb SAIDA"""
import json, math, os, sys
import bpy
from mathutils import Vector, Matrix
ENT, SAIDA = sys.argv[1], sys.argv[2]
os.makedirs(SAIDA, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=ENT)
objs = list(bpy.context.scene.objects)
eixos = {o.name.replace("Eixo Hélice ", ""): o.matrix_world.translation.copy() for o in objs if o.type == "EMPTY"}
corpo = [o for o in objs if o.type == "MESH" and not o.name.startswith("Hélice")]
helices = [o for o in objs if o.type == "MESH" and o.name.startswith("Hélice")]
pts = [o.matrix_world @ Vector(c) for o in corpo for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centro = (mn + mx) / 2
frente = (eixos["frente direita"] + eixos["frente esquerda"]) / 2 - (eixos["trás direita"] + eixos["trás esquerda"]) / 2
ang = math.atan2(frente.y, frente.x)
R = Matrix.Rotation(-ang, 4, "Z") @ Matrix.Translation(-centro)
# confere o lado: depois de girar, a "direita" tem que ficar em y negativo (no Unreal, y positivo)
d = R @ eixos["frente direita"]
espelhar = d.y > 0
print("frente", frente, "ang", math.degrees(ang), "direita depois", d, "espelhar", espelhar)
M = (Matrix.Scale(-1, 4, Vector((0, 1, 0))) if espelhar else Matrix.Identity(4)) @ R
for o in corpo:
    o.data.transform(o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    o.data.transform(M)
    if espelhar:
        o.data.flip_normals()
bpy.ops.object.select_all(action="DESELECT")
for o in corpo:
    o.select_set(True)
bpy.context.view_layer.objects.active = corpo[0]
bpy.ops.object.join()
c = bpy.context.object
c.name = "E88_Corpo"
# uma hélice no centro
h = helices[0]
e = h.parent.matrix_world.translation.copy() if h.parent else h.matrix_world.translation.copy()
mw = h.matrix_world.copy()
h.parent = None
h.matrix_world = mw
h.data.transform(Matrix.Translation(-e) @ mw)
h.matrix_world = Matrix.Identity(4)
h.name = "E88_Helice"
for o in helices[1:]:
    bpy.data.objects.remove(o)
for o in list(bpy.context.scene.objects):
    if o.type == "EMPTY":
        bpy.data.objects.remove(o)
info = {"eixos": {}}
for k, v in eixos.items():
    p = M @ v
    info["eixos"][k] = [p.x * 100, -p.y * 100, p.z * 100]   # Blender -> Unreal (cm)
for o in (c, h):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.fbx(filepath=os.path.join(SAIDA, o.name + ".fbx"), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_ALL", axis_forward="-Y", axis_up="Z", mesh_smooth_type="FACE",
                             add_leaf_bones=False, bake_anim=False)
    print(o.name, [m.name for m in o.data.materials], [round(x, 3) for x in o.dimensions])
json.dump(info, open(os.path.join(SAIDA, "e88.json"), "w"), indent=1, ensure_ascii=False)
print(info)
