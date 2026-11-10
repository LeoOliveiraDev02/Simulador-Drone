# Monta o estúdio do drone dobrável (estilo E88 Pro) no Blender, no mesmo nível do FPV:
# plástico preto com acabamento realista, quinas arredondadas no render, hélices girando
# em velocidade constante, luzes de LED embaixo dos motores, bancada, luzes e câmeras.
# Só o drone (sem o rádio).
#
# Uso: blender -b -P montar_estudio_e88.py -- drone.glb PASTA_TEXTURAS SAIDA.blend
import bpy, math, sys, os
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
GLB, TEX, SAIDA = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
raiz = bpy.data.objects['drone']
# o CAD veio com o "para cima" no eixo Y: deita no Z e vira a frente (câmera) para -Y
raiz.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X') @ raiz.matrix_world
bpy.context.view_layer.update()
malhas = [o for o in bpy.data.objects if o.type == 'MESH']
for o in malhas:
    mw = o.matrix_world.copy()
    o.parent = None
    o.matrix_world = mw
    o.data = o.data.copy()
    o.data.transform(o.matrix_world)       # vértices em coordenadas do mundo (escala 1)
    o.matrix_world = Matrix()
bpy.data.objects.remove(raiz)

PECA = {
    'NAUO1': 'Carcaça de baixo', 'NAUO2': 'Carcaça de cima', 'NAUO7': 'Câmera',
    'NAUO3': 'Hélice FD', 'NAUO4': 'Hélice FE', 'NAUO5': 'Hélice TD', 'NAUO6': 'Hélice TE',
    'NAUO8': 'Braço', 'NAUO9': 'Braço', 'NAUO10': 'Braço', 'NAUO11': 'Braço',
    'NAUO13': 'Engrenagem', 'NAUO14': 'Engrenagem', 'NAUO17': 'Engrenagem', 'NAUO19': 'Engrenagem',
    'NAUO12': 'Motor', 'NAUO15': 'Motor', 'NAUO16': 'Motor', 'NAUO18': 'Motor',
}
tipo = {}
for o in malhas:
    t = PECA.get(o.name.split('.')[0], 'Outro')
    tipo[o] = t
for o in malhas:
    o.name = tipo[o]

# no chão (z = 0 é o tampo da bancada), centrado
pts = np.concatenate([np.array([v.co for v in o.data.vertices]) for o in malhas])
mn, mx = pts.min(0), pts.max(0)
desl = Vector((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2] + 0.0003))
for o in malhas:
    o.data.transform(Matrix.Translation(desl))
mn = np.array(mn) + np.array(desl); mx = np.array(mx) + np.array(desl)
print('drone', np.round(mx - mn, 3))

# se a câmera ficou atrás, gira 180° (frente do drone = -Y, igual ao FPV)
cam_obj = next(o for o in malhas if tipo[o] == 'Câmera')
if np.array([v.co for v in cam_obj.data.vertices])[:, 1].mean() > 0:
    for o in malhas:
        o.data.transform(Matrix.Rotation(math.pi, 4, 'Z'))
    print('virado para a frente')

# ------------------------------------------------------------------ materiais
def novo_mat(nome):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m, nt, bsdf

def plastico(nome, cor, rug, coat=0.0, coat_rug=0.1, metal=0.0, raio=0.0004, textura=0.0, esc_tex=1.0):
    """Plástico injetado. 'textura' = leve granulado de molde (feito com imagem de ruído
    com mipmap, então não cintila em movimento)."""
    m, nt, bsdf = novo_mat(nome)
    bsdf.inputs['Base Color'].default_value = (*cor, 1)
    bsdf.inputs['Roughness'].default_value = rug
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Coat Roughness'].default_value = coat_rug
    bsdf.inputs['Specular IOR Level'].default_value = 0.32 if metal == 0 else 0.5
    bev = nt.nodes.new('ShaderNodeBevel'); bev.location = (-200, -300)
    bev.inputs['Radius'].default_value = raio; bev.samples = 6
    normal = bev.outputs['Normal']
    if textura > 0:
        tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1000, -400)
        mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-800, -400)
        mp.inputs['Scale'].default_value = (esc_tex,) * 3
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        ti = nt.nodes.new('ShaderNodeTexImage'); ti.location = (-550, -400)
        ti.image = img_grao; ti.projection = 'BOX'; ti.projection_blend = 0.3
        nt.links.new(mp.outputs['Vector'], ti.inputs['Vector'])
        bump = nt.nodes.new('ShaderNodeBump'); bump.location = (0, -400)
        bump.inputs['Strength'].default_value = textura
        bump.inputs['Distance'].default_value = 0.00002
        nt.links.new(ti.outputs['Color'], bump.inputs['Height'])
        nt.links.new(normal, bump.inputs['Normal'])
        normal = bump.outputs['Normal']
    nt.links.new(normal, bsdf.inputs['Normal'])
    return m

img_grao = bpy.data.images.load(os.path.join(TEX, 'grao_plastico.png'))
img_grao.colorspace_settings.name = 'Non-Color'

M = {
    # carcaça de cima: preto com verniz acetinado (o "casco" do drone)
    'Carcaça de cima': plastico('Preto acetinado (carcaça)', (0.011, 0.011, 0.012), 0.45, coat=0.25, coat_rug=0.2, raio=0.0006, textura=0.08, esc_tex=180),
    # carcaça de baixo e braços: preto fosco com granulado de molde
    'Carcaça de baixo': plastico('Preto fosco texturizado', (0.012, 0.012, 0.013), 0.7, raio=0.0005, textura=0.18, esc_tex=260),
    'Braço': plastico('Preto fosco (braço)', (0.013, 0.013, 0.014), 0.55, coat=0.1, raio=0.0005, textura=0.12, esc_tex=260),
    'Hélice': plastico('Hélice preta (nylon)', (0.012, 0.012, 0.013), 0.4, coat=0.1, raio=0.0003),
    'Engrenagem': plastico('Cinza grafite (topo do motor)', (0.11, 0.11, 0.115), 0.36, coat=0.2, raio=0.0002),
    'Motor': plastico('Motor (aço)', (0.6, 0.6, 0.62), 0.25, metal=1.0, raio=0.0002),
    'Câmera': plastico('Câmera (plástico preto)', (0.01, 0.01, 0.011), 0.35, coat=0.3, raio=0.0003),
}
mat_tampa = plastico('Tampa da hélice (cinza)', (0.42, 0.42, 0.43), 0.32, coat=0.4, raio=0.0002)

def mat_vidro():
    m, nt, bsdf = novo_mat('Lente (vidro)')
    bsdf.inputs['Base Color'].default_value = (0.01, 0.012, 0.02, 1)
    bsdf.inputs['Roughness'].default_value = 0.02
    bsdf.inputs['Coat Weight'].default_value = 1.0
    bsdf.inputs['Coat Roughness'].default_value = 0.0
    bsdf.inputs['Specular IOR Level'].default_value = 1.0
    # reflexo arroxeado do tratamento antirreflexo
    bsdf.inputs['Thin Film Thickness'].default_value = 380
    return m
mat_lente = mat_vidro()

def mat_led(nome, cor, forca):
    """Difusor branco leitoso do LED que fica embaixo de cada motor."""
    m, nt, bsdf = novo_mat(nome)
    bsdf.inputs['Base Color'].default_value = (0.85, 0.85, 0.85, 1)
    bsdf.inputs['Roughness'].default_value = 0.25
    bsdf.inputs['Coat Weight'].default_value = 0.5
    bsdf.inputs['Emission Color'].default_value = (*cor, 1)
    bsdf.inputs['Emission Strength'].default_value = forca
    return m
led_frente = mat_led('LED da frente (branco)', (1.0, 0.95, 0.85), 1.5)
led_tras = mat_led('LED de trás (vermelho)', (1.0, 0.06, 0.03), 2.5)

def suavizar(o, ang=32):
    for p in o.data.polygons:
        p.use_smooth = True
    try:
        o.data.set_sharp_from_angle(angle=math.radians(ang))
    except Exception:
        pass

def junta_vertices(o):
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.000005)
    bm.to_mesh(o.data); bm.free()

helices = []
for o in malhas:
    t = tipo[o]
    junta_vertices(o)
    o.data.materials.clear()
    o.data.materials.append(M['Hélice' if t.startswith('Hélice') else t])
    suavizar(o)
    if t.startswith('Hélice'):
        helices.append(o)

def centro_xy(o):
    v = np.array([p.co for p in o.data.vertices]); return v[:, :2].mean(0)

# eixo de cada hélice = centro da tampinha de cima (o ponto mais alto do cubo)
eixos = {}
for h in helices:
    v = np.array([p.co for p in h.data.vertices])
    topo = v[v[:, 2] > v[:, 2].max() - 0.0015]
    eixos[h] = (topo[:, 0].mean(), topo[:, 1].mean(), v[:, 2].min(), v[:, 2].max())

for h in helices:   # nome pela posição (frente = -Y, direita = +X)
    h.name = 'Hélice ' + ('frente' if eixos[h][1] < 0 else 'trás') + (' direita' if eixos[h][0] > 0 else ' esquerda')

# tampinha cinza no centro da hélice (raio 4,3 mm em volta do eixo)
for h in helices:
    cx, cy, zmin, zmax = eixos[h]
    h.data.materials.append(mat_tampa)
    for p in h.data.polygons:
        c = p.center
        if math.hypot(c.x - cx, c.y - cy) < 0.0043 and c.z > zmin + 0.004:
            p.material_index = 1

# LED: a cúpula leitosa embaixo da ponta de cada braço. A malha é cortada numa altura
# fixa (linha reta e limpa) e as faces de baixo, perto do motor, viram o difusor do LED.
# Assim funciona igual no Blender e no Godot (material comum, sem truque de shader).
import bmesh
Z_CORTE_LED = 0.0115
for b in [o for o in malhas if tipo[o] == 'Braço']:
    v = np.array([p.co for p in b.data.vertices])
    cb = v[:, :2].mean(0)
    h = min(helices, key=lambda h: math.hypot(eixos[h][0] - cb[0], eixos[h][1] - cb[1]))
    cx, cy = eixos[h][0], eixos[h][1]
    led = led_frente if cy < 0 else led_tras
    b.data.materials.append(led)
    bm = bmesh.new(); bm.from_mesh(b.data)
    def perto(co): return math.hypot(co.x - cx, co.y - cy) < 0.022 and co.z < 0.03
    faces = [f for f in bm.faces if perto(f.calc_center_median())]
    geom = list({e for f in faces for e in f.edges}) + faces + list({v_ for f in faces for v_ in f.verts})
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, Z_CORTE_LED), plane_no=(0, 0, 1))
    n = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if perto(c) and c.z < Z_CORTE_LED:
            f.material_index = 1; n += 1
    bm.to_mesh(b.data); bm.free()
    suavizar(b)
    print('LED', b.name, n, 'faces')

# lente: faces da câmera viradas para a frente (-Y) e mais à frente
cv = np.array([p.co for p in cam_obj.data.vertices])
ymin = cv[:, 1].min()
cam_obj.data.materials.append(mat_lente)
nl = 0
for p in cam_obj.data.polygons:
    if p.normal.y < -0.8 and p.center.y < ymin + 0.0025:
        ccx, ccz = cv[:, 0].mean(), np.median(cv[cv[:, 1] < ymin + 0.003][:, 2])
        if math.hypot(p.center.x - ccx, p.center.z - ccz) < 0.0045:
            p.material_index = 1; nl += 1
print('lente', nl, 'faces')


# ------------------------------------------------------------------ otimização
def reduzir(o, alvo):
    n = len(o.data.polygons)
    if n <= alvo:
        return
    mod = o.modifiers.new('reduzir', 'DECIMATE')
    mod.decimate_type = 'COLLAPSE'; mod.ratio = max(alvo / n, 0.05)
    mod.use_collapse_triangulate = False
    with bpy.context.temp_override(object=o, active_object=o):
        bpy.ops.object.modifier_apply(modifier=mod.name)
antes = sum(len(o.data.polygons) for o in malhas)
for o in malhas:
    if tipo[o] == 'Motor':
        reduzir(o, 1500)          # fica escondido dentro do braço
    elif tipo[o] == 'Engrenagem':
        reduzir(o, 6000)
print('poligonos:', antes, '->', sum(len(o.data.polygons) for o in malhas))

# ------------------------------------------------------------------ hélices girando
cena = bpy.context.scene
cena.render.fps = 60
cena.frame_start = 0; cena.frame_end = 600
VOLTAS_POR_SEGUNDO = 6.0
for h in helices:
    cx, cy, zmin, zmax = eixos[h]
    eixo = bpy.data.objects.new('Eixo ' + h.name, None)
    cena.collection.objects.link(eixo)
    eixo.empty_display_size = 0.01
    eixo.location = (cx, cy, zmin)
    h.data.transform(Matrix.Translation((-cx, -cy, -zmin)))
    h.parent = eixo
    # diagonais opostas giram no mesmo sentido (FD/TE horário, FE/TD anti-horário)
    sentido = 1.0 if (cx > 0) == (cy > 0) else -1.0
    fc = eixo.driver_add('rotation_euler', 2)
    fc.driver.expression = f'{sentido} * frame * {2 * math.pi * VOLTAS_POR_SEGUNDO / 60.0:.6f}'
cena.render.use_motion_blur = True
cena.render.motion_blur_shutter = 0.5

# ------------------------------------------------------------------ bancada (igual ao FPV)
def plano_textura(nome, tam, z, dif, nor, rough=None, escala=1.0):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, z))
    p = bpy.context.active_object; p.name = nome
    p.scale = (tam[0], tam[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    m, nt, bsdf = novo_mat(nome)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1100, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-900, 0)
    mp.inputs['Scale'].default_value = (escala,) * 3
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    def tex(f, loc, cor=True):
        t = nt.nodes.new('ShaderNodeTexImage'); t.location = loc
        t.image = bpy.data.images.load(os.path.join(TEX, f))
        if not cor: t.image.colorspace_settings.name = 'Non-Color'
        nt.links.new(mp.outputs['Vector'], t.inputs['Vector'])
        return t
    nt.links.new(tex(dif, (-600, 200)).outputs['Color'], bsdf.inputs['Base Color'])
    if rough:
        nt.links.new(tex(rough, (-600, -50), False).outputs['Color'], bsdf.inputs['Roughness'])
    if nor:
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.location = (0, -300)
        nt.links.new(tex(nor, (-600, -300), False).outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    p.data.materials.append(m)
    return p, bsdf

tampo, _ = plano_textura('Tampo de madeira', (1.6, 1.0), -0.0005, 'dark_wood_diff.jpg', 'dark_wood_nor_gl.jpg', 'dark_wood_rough.jpg')
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.0255))
borda = bpy.context.active_object; borda.name = 'Tampo (espessura)'
borda.scale = (1.6, 1.0, 0.05); borda.data.materials.append(tampo.data.materials[0])
tapete, b_tap = plano_textura('Tapete de corte', (0.6, 0.45), 0.0, 'tapete.png', None)
b_tap.inputs['Roughness'].default_value = 0.7
b_tap.inputs['Specular IOR Level'].default_value = 0.3
tapete.rotation_euler.z = math.radians(8)

# ------------------------------------------------------------------ luz e mundo
w = bpy.data.worlds.new('Estudio'); cena.world = w
w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputWorld')
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.07
escuro = nt.nodes.new('ShaderNodeBackground'); escuro.inputs['Color'].default_value = (0.004, 0.005, 0.007, 1)
lp = nt.nodes.new('ShaderNodeLightPath'); mx_ = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(env.outputs['Color'], bg.inputs['Color'])
nt.links.new(lp.outputs['Is Camera Ray'], mx_.inputs['Fac'])
nt.links.new(bg.outputs[0], mx_.inputs[1]); nt.links.new(escuro.outputs[0], mx_.inputs[2])
nt.links.new(mx_.outputs[0], out.inputs['Surface'])

def luz_area(nome, loc, alvo, tam, energia, cor=(1, 1, 1)):
    l = bpy.data.lights.new(nome, 'AREA'); l.shape = 'RECTANGLE'
    l.size = tam[0]; l.size_y = tam[1]; l.energy = energia; l.color = cor
    o = bpy.data.objects.new(nome, l); cena.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

# plástico preto precisa de reflexos grandes para mostrar a forma
luz_area('Softbox principal', (0.45, -0.55, 0.65), (0, 0, 0.02), (0.9, 0.6), 24, (1.0, 0.95, 0.88))
luz_area('Contraluz azul', (-0.55, 0.6, 0.3), (0, 0, 0.03), (0.7, 0.2), 32, (0.35, 0.55, 1.0))
luz_area('Preenchimento', (-0.6, -0.45, 0.35), (0, 0, 0.02), (0.5, 0.5), 4, (1.0, 0.85, 0.7))
luz_area('Faixa de cima', (0.0, 0.1, 0.8), (0, 0, 0), (1.0, 0.12), 5, (0.95, 0.97, 1.0))

# ------------------------------------------------------------------ câmeras
def camera(nome, loc, alvo, lente, f=5.6):
    c = bpy.data.cameras.new(nome); c.lens = lente; c.sensor_width = 36; c.clip_start = 0.005
    o = bpy.data.objects.new(nome, c); cena.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    c.dof.use_dof = True
    c.dof.focus_distance = (Vector(alvo) - Vector(loc)).length
    c.dof.aperture_fstop = f
    return o

alt = mx[2] - mn[2]
zc = alt * 0.45
camera('1_heroi', (0.5, -0.56, 0.3), (0, -0.01, zc), 65, 8.0)
camera('2_de_cima', (0.03, -0.2, 0.75), (0, 0, zc * 0.5), 50, 11.0)
# motor da frente à direita
hfd = max([h for h in helices if eixos[h][1] < 0], key=lambda h: eixos[h][0])
am = Vector((eixos[hfd][0], eixos[hfd][1], eixos[hfd][2] - 0.006))
camera('3_motor_macro', am + Vector((0.13, -0.14, 0.06)), am, 70, 5.6)
# câmera do drone, de frente
cc = Vector(cv.mean(0))
camera('4_camera_frontal', cc + Vector((-0.09, -0.2, 0.035)), cc, 85, 5.6)
cena.camera = bpy.data.objects['1_heroi']

# ------------------------------------------------------------------ render
cena.render.engine = 'CYCLES'
cena.cycles.samples = 1024
cena.cycles.adaptive_threshold = 0.008
cena.cycles.use_denoising = True
cena.cycles.denoiser = 'OPENIMAGEDENOISE'
cena.cycles.max_bounces = 12
cena.render.resolution_x = 3840; cena.render.resolution_y = 2160
cena.view_settings.view_transform = 'AgX'
cena.view_settings.look = 'AgX - Medium High Contrast'
cena.view_settings.exposure = -0.3
try:
    cena.render.image_settings.media_type = 'IMAGE'
except Exception:
    pass
cena.render.image_settings.file_format = 'PNG'
cena.render.image_settings.color_depth = '16'

bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=SAIDA, compress=True)
print('salvo', SAIDA)
