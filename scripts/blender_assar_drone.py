# Blender 5.x: acabamento dos drones (mesmo processo da placa-mãe do Monta PC)
#  1. normais certas: junta vértices repetidos e suaviza por ângulo (some o "facetado" do CAD)
#  2. segundo mapa UV ("lm") com todas as malhas num atlas só
#  3. sombra de ambiente (AO) assada no Cycles; cada peça é assada sozinha
#     (assim, na vista explodida, a sombra continua certa em cada peça)
# Uso: blender -b -P blender_assar_drone.py -- entrada.glb saida.glb ao.png TAM AMOSTRAS DIST_CM
import bpy, sys, math, time

argv = sys.argv[sys.argv.index('--') + 1:]
SRC, DST, AO_PNG = argv[0], argv[1], argv[2]
SIZE = int(argv[3]); SAMPLES = int(argv[4]); DIST = float(argv[5]) / 100.0
t0 = time.time()
def log(*a): print(f'[{time.time() - t0:7.1f}s]', *a, flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
log('importado', len(meshes), 'malhas')

def peca_de(o):
    """Nome da peça = ancestral logo abaixo da raiz do drone."""
    cadeia = [o]
    while cadeia[-1].parent:
        cadeia.append(cadeia[-1].parent)
    return cadeia[-2].name if len(cadeia) >= 2 else o.name

# ---------- 1. normais ----------
for o in meshes:
    if not o.data.users == 1:
        o.data = o.data.copy()
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    escala = max(max(o.matrix_world.to_scale()), 1e-9)
    bpy.ops.mesh.remove_doubles(threshold=0.00001 / escala)
    bpy.ops.object.mode_set(mode='OBJECT')
    o.select_set(False)
for o in meshes:
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(32), keep_sharp_edges=True)
log('normais prontas')

# ---------- 2. atlas ----------
for o in meshes:
    if not o.material_slots or not o.material_slots[0].material:
        m = bpy.data.materials.new('cor|0.7,0.7,0.7|0.5|0|0')
        if o.material_slots: o.material_slots[0].material = m
        else: o.data.materials.append(m)
    while len(o.data.uv_layers) < 1:
        o.data.uv_layers.new(name='UVMap')
    uv = o.data.uv_layers.new(name='lm')
    o.data.uv_layers.active = uv
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0, scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=0.002, shape_method='CONCAVE')
bpy.ops.object.mode_set(mode='OBJECT')
log('atlas pronto')

# ---------- 3. AO ----------
scn = bpy.context.scene
scn.render.engine = 'CYCLES'
scn.cycles.device = 'CPU'
scn.cycles.samples = SAMPLES
scn.world = scn.world or bpy.data.worlds.new('w')
scn.world.light_settings.distance = DIST
img = bpy.data.images.new('ao', SIZE, SIZE, alpha=False, float_buffer=False)
img.colorspace_settings.name = 'Non-Color'
for o in meshes:
    for slot in o.material_slots:
        m = slot.material
        if not m: continue
        m.use_nodes = True
        nt = m.node_tree
        if 'AO_BAKE' in nt.nodes: continue
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = img; n.name = 'AO_BAKE'
        u = nt.nodes.new('ShaderNodeUVMap'); u.uv_map = 'lm'; u.name = 'AO_UV'
        nt.links.new(u.outputs['UV'], n.inputs['Vector'])
        nt.nodes.active = n

grupos = sorted({peca_de(o) for o in meshes})
log('assando', SIZE, 'px,', SAMPLES, 'amostras,', len(grupos), 'peças')
for gi, g in enumerate(grupos):
    minhas = [o for o in meshes if peca_de(o) == g]
    for o in meshes:
        o.hide_render = peca_de(o) != g
    bpy.ops.object.select_all(action='DESELECT')
    for o in minhas: o.select_set(True)
    bpy.context.view_layer.objects.active = minhas[0]
    bpy.ops.object.bake(type='AO', margin=8, margin_type='EXTEND', use_clear=(gi == 0), target='IMAGE_TEXTURES')
    log('  ', g, len(minhas), 'malhas')
for o in meshes: o.hide_render = False
img.filepath_raw = AO_PNG; img.file_format = 'PNG'; img.save()

for o in meshes:
    for slot in o.material_slots:
        if not slot.material: continue
        nt = slot.material.node_tree
        for n in [n for n in nt.nodes if n.name in ('AO_BAKE', 'AO_UV')]: nt.nodes.remove(n)
    o.data.uv_layers.active = o.data.uv_layers[0]
    o.data.uv_layers[0].active_render = True
bpy.ops.export_scene.gltf(filepath=DST, export_format='GLB', export_texcoords=True, export_normals=True,
                          export_materials='EXPORT', export_yup=True, export_apply=False)
log('exportado', DST)
