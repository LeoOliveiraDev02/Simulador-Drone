# Versões leves das árvores, arbustos e pedras do mapa só para o celular.
# Os modelos originais (Poly Haven) têm 1 a 2 milhões de triângulos por árvore;
# aqui as folhas e galhos são reduzidos até ~4-8% (de longe ficam iguais).
# Uso: blender -b -P modelos_celular.py -- PASTA_MODELOS PASTA_SAIDA
import bpy, sys, os, glob

argv = sys.argv[sys.argv.index('--') + 1:]
ENTRA, SAI = argv[0], argv[1]
os.makedirs(SAI, exist_ok=True)

# fração mantida por tipo de material
def fracao(nome_mat, total):
    n = nome_mat.lower()
    if 'leaves' in n:
        return 0.08
    if 'branches' in n:
        return 0.035
    if 'trunk' in n or n.startswith('island_tree'):
        return 0.25
    # pedras e arbustos: mira ~6 mil triângulos
    return min(1.0, 6000.0 / max(total, 1))


for f in sorted(glob.glob(os.path.join(ENTRA, '*', '*_1k.gltf'))):
    nome = os.path.basename(f).replace('_1k.gltf', '')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=f)
    antes = depois = 0
    for o in [o for o in bpy.data.objects if o.type == 'MESH']:
        antes += len(o.data.polygons)
        # separa por material para reduzir cada parte na medida certa
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        if len(o.data.materials) > 1:
            bpy.ops.mesh.separate(type='MATERIAL')
    for o in [o for o in bpy.data.objects if o.type == 'MESH']:
        m = o.data.materials[0].name if o.data.materials else ''
        r = fracao(m, len(o.data.polygons))
        if r < 1.0:
            mod = o.modifiers.new('reduzir', 'DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = r
            mod.use_collapse_triangulate = True
            with bpy.context.temp_override(object=o, active_object=o):
                bpy.ops.object.modifier_apply(modifier=mod.name)
        depois += len(o.data.polygons)
    saida = os.path.join(SAI, nome + '.glb')
    bpy.ops.export_scene.gltf(filepath=saida, export_format='GLB', export_yup=True, export_apply=True,
                              export_image_format='JPEG', export_jpeg_quality=88)
    print('CELULAR', nome, antes, '->', depois, 'faces', round(os.path.getsize(saida) / 1e6, 1), 'MB')
