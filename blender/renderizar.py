# Renderiza as câmeras do estúdio usando a placa de vídeo (AMD HIP; tenta também OptiX/CUDA).
# Uso: blender -b fpv_estudio.blend -P renderizar.py -- PASTA_SAIDA [AMOSTRAS] [LARGURA] [cam1,cam2...]
import bpy, sys, os, time

argv = sys.argv[sys.argv.index('--') + 1:]
saida = argv[0]
amostras = int(argv[1]) if len(argv) > 1 else 0
largura = int(argv[2]) if len(argv) > 2 else 0
so = argv[3].split(',') if len(argv) > 3 and argv[3] else None
scn = bpy.context.scene
os.makedirs(saida, exist_ok=True)

scn.render.engine = 'CYCLES'
scn.cycles.device = 'CPU'
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for tipo in ('HIP', 'OPTIX', 'CUDA', 'ONEAPI'):
        try:
            prefs.compute_device_type = tipo
        except Exception:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == tipo]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == tipo
            scn.cycles.device = 'GPU'
            print('PLACA DE VIDEO:', tipo, [d.name for d in gpus], flush=True)
            break
except Exception as e:
    print('sem GPU:', e, flush=True)
if scn.cycles.device == 'CPU':
    print('USANDO O PROCESSADOR (sem placa de video)', flush=True)

if amostras:
    scn.cycles.samples = amostras
if largura:
    scn.render.resolution_y = int(scn.render.resolution_y * largura / scn.render.resolution_x)
    scn.render.resolution_x = largura

cams = sorted([o for o in bpy.data.objects if o.type == 'CAMERA'], key=lambda o: o.name)
for c in cams:
    if so and c.name not in so:
        continue
    t0 = time.time()
    scn.camera = c
    scn.render.filepath = os.path.join(saida, c.name + '.png')
    bpy.ops.render.render(write_still=True)
    print('RENDER', c.name, round(time.time() - t0), 's', flush=True)
