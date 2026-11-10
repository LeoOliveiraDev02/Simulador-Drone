# Monta o estúdio fotográfico do drone FPV (TBS Source One V6) no Blender.
# Parte do arquivo do próprio autor do CAD (drohne.blend), tira o cenário de grafite,
# refaz todos os materiais com acabamento realista (carbono trançado, alumínio
# anodizado, aço acetinado, hélices translúcidas, placas com verniz, bateria com
# etiqueta, fios de silicone), arredonda as quinas no render (nó Bevel), monta a
# bancada escura com tapete de corte, luzes de estúdio e 4 câmeras.
#
# Uso: blender -b drohne.blend -P montar_estudio_fpv.py -- PASTA_TEXTURAS SAIDA.blend
import bpy, math, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
TEX, SAIDA = argv[0], argv[1]

# ------------------------------------------------------------------ limpa o cenário
manter = set()
for raiz in ('Body1.009', 'SH1_0_6p_Tabbed_Plug_v2', 'Armature'):
    o = bpy.data.objects.get(raiz)
    if o:
        manter.add(o)
        manter.update(o.children_recursive)
for o in list(bpy.data.objects):
    if o not in manter:
        bpy.data.objects.remove(o, do_unlink=True)
if bpy.context.scene.rigidbody_world:
    bpy.ops.rigidbody.world_remove()
drone = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVE')]

# caixa do drone e posição sobre a bancada (z = 0 é o tampo)
mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
for o in drone:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
centro = (mn + mx) / 2
desl = Vector((-centro.x, -centro.y, -mn.z + 0.0005))
for o in bpy.data.objects:
    if o.parent is None:
        o.location += desl
bpy.context.view_layer.update()
tam = max(mx.x - mn.x, mx.y - mn.y)
alt = mx.z - mn.z
print('drone', round(tam, 3), 'x', round(alt, 3), 'm')

# ------------------------------------------------------------------ materiais
def novo_mat(nome):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m, nt, bsdf

def quinas(nt, bsdf, raio=0.00025, ruido=0.0, escala=3000.0):
    """Quinas arredondadas no render (Bevel) + microtextura opcional."""
    bev = nt.nodes.new('ShaderNodeBevel'); bev.location = (-200, -300)
    bev.inputs['Radius'].default_value = raio
    bev.samples = 6
    normal = bev.outputs['Normal']
    if ruido > 0:
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.location = (-500, -500)
        nz.inputs['Scale'].default_value = escala
        nz.inputs['Detail'].default_value = 4
        bump = nt.nodes.new('ShaderNodeBump'); bump.location = (0, -400)
        bump.inputs['Strength'].default_value = ruido
        bump.inputs['Distance'].default_value = 0.00002
        nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
        nt.links.new(normal, bump.inputs['Normal'])
        normal = bump.outputs['Normal']
    nt.links.new(normal, bsdf.inputs['Normal'])

def ajustar(bsdf, cor, rug, metal=0.0, coat=0.0, aniso=0.0, transm=0.0, ss=0.0):
    bsdf.inputs['Base Color'].default_value = (*cor[:3], 1)
    bsdf.inputs['Roughness'].default_value = rug
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Coat Roughness'].default_value = 0.08
    bsdf.inputs['Anisotropic'].default_value = aniso
    bsdf.inputs['Transmission Weight'].default_value = transm
    if ss > 0:
        bsdf.inputs['Subsurface Weight'].default_value = ss
        bsdf.inputs['Subsurface Radius'].default_value = (0.002, 0.002, 0.002)

def mat_carbono():
    m, nt, bsdf = novo_mat('Carbono trançado 3K')
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1400, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-1200, 0)
    mp.inputs['Scale'].default_value = (420, 420, 420)     # ~2,4 mm por trama
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1000, 0)
    nt.links.new(mp.outputs['Vector'], sep.inputs[0])
    # tramas em X e em Y (ondas) e um xadrez que decide qual fio fica por cima (twill)
    def onda(eixo, loc):
        w = nt.nodes.new('ShaderNodeTexWave'); w.location = loc
        w.wave_type = 'BANDS'; w.bands_direction = eixo
        w.inputs['Scale'].default_value = 2.0
        w.inputs['Distortion'].default_value = 0.0
        w.inputs['Detail'].default_value = 0.0
        nt.links.new(mp.outputs['Vector'], w.inputs['Vector'])
        return w
    wx = onda('X', (-800, 200)); wy = onda('Y', (-800, -100))
    ck = nt.nodes.new('ShaderNodeTexChecker'); ck.location = (-800, -400)
    ck.inputs['Scale'].default_value = 1.0
    ck.inputs['Color1'].default_value = (1, 1, 1, 1); ck.inputs['Color2'].default_value = (0, 0, 0, 1)
    nt.links.new(mp.outputs['Vector'], ck.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.location = (-550, 0); mix.data_type = 'FLOAT'
    nt.links.new(ck.outputs['Fac'], mix.inputs['Factor'])
    nt.links.new(wx.outputs['Fac'], mix.inputs['A']); nt.links.new(wy.outputs['Fac'], mix.inputs['B'])
    rmp = nt.nodes.new('ShaderNodeMapRange'); rmp.location = (-350, 100)
    rmp.inputs['To Min'].default_value = 0.012; rmp.inputs['To Max'].default_value = 0.055
    nt.links.new(mix.outputs['Result'], rmp.inputs['Value'])
    comb = nt.nodes.new('ShaderNodeCombineColor'); comb.location = (-150, 150)
    for i in range(3): nt.links.new(rmp.outputs['Result'], comb.inputs[i])
    nt.links.new(comb.outputs['Color'], bsdf.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.location = (-350, -150)
    rr.inputs['To Min'].default_value = 0.5; rr.inputs['To Max'].default_value = 0.3
    nt.links.new(mix.outputs['Result'], rr.inputs['Value'])
    nt.links.new(rr.outputs['Result'], bsdf.inputs['Roughness'])
    bsdf.inputs['Anisotropic'].default_value = 0.45
    bsdf.inputs['Specular IOR Level'].default_value = 0.25
    bsdf.inputs['Coat Weight'].default_value = 0.55
    bsdf.inputs['Coat Roughness'].default_value = 0.12
    bsdf.inputs['Coat IOR'].default_value = 1.5
    bump = nt.nodes.new('ShaderNodeBump'); bump.location = (0, -300)
    bump.inputs['Strength'].default_value = 0.25; bump.inputs['Distance'].default_value = 0.00004
    nt.links.new(mix.outputs['Result'], bump.inputs['Height'])
    bev = nt.nodes.new('ShaderNodeBevel'); bev.location = (-200, -500)
    bev.inputs['Radius'].default_value = 0.0004; bev.samples = 6
    nt.links.new(bev.outputs['Normal'], bump.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m

def mat_simples(nome, cor, rug, metal=0.0, coat=0.0, aniso=0.0, transm=0.0, ss=0.0, ruido=0.15, raio=0.00025):
    m, nt, bsdf = novo_mat(nome)
    ajustar(bsdf, cor, rug, metal, coat, aniso, transm, ss)
    quinas(nt, bsdf, raio=raio, ruido=ruido)
    return m

def mat_etiqueta():
    m, nt, bsdf = novo_mat('Bateria 6S (etiqueta)')
    img = bpy.data.images.load(os.path.join(TEX, 'etiqueta_bateria.png'))
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-900, 0)
    ti = nt.nodes.new('ShaderNodeTexImage'); ti.location = (-500, 0)
    ti.image = img; ti.projection = 'BOX'; ti.projection_blend = 0.05; ti.extension = 'EXTEND'
    nt.links.new(tc.outputs['Generated'], ti.inputs['Vector'])
    nt.links.new(ti.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.32
    bsdf.inputs['Coat Weight'].default_value = 0.6
    quinas(nt, bsdf, raio=0.0012, ruido=0.25, escala=800)
    return m

carbono = mat_carbono()
mats_cache = {}

def cor_lin(m):
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m.node_tree else None
    return tuple(b.inputs['Base Color'].default_value)[:3] if b else (0.6, 0.6, 0.6)

def lum(c): return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

def trocar(m):
    if m.name in mats_cache:
        return mats_cache[m.name]
    n = m.name
    c = cor_lin(m)
    L = lum(c); sat = max(c) - min(c)
    if 'CarbonFiber' in n:
        novo = carbono
    elif 'SteelSatin' in n:
        novo = mat_simples('Aço acetinado', (0.55, 0.56, 0.58), 0.28, metal=1.0, aniso=0.5, ruido=0.0, raio=0.0001)
    elif 'AluminumAnodized' in n:
        novo = mat_simples('Alumínio anodizado ' + n[-6:], c, 0.2, metal=1.0, coat=0.35, aniso=0.7, ruido=0.0, raio=0.0002)
    elif 'AluminumPolished' in n:
        novo = mat_simples('Alumínio polido', (0.9, 0.9, 0.9), 0.1, metal=1.0, ruido=0.0, raio=0.0001)
    elif '222114241' in n:
        # hélices de policarbonato translúcido
        novo = mat_simples('Hélice policarbonato', (0.75, 0.35, 0.9), 0.12, coat=0.5, transm=0.55, ruido=0.05, raio=0.0003)
    elif 'Nylon' in n or 'ABSWhite' in n:
        novo = mat_simples('Nylon branco ' + n[-4:], (0.78, 0.78, 0.76), 0.55, ss=0.08, ruido=0.3)
    elif L < 0.012:
        novo = mat_simples('Preto verniz ' + n[-10:], (max(c[0], 0.008), max(c[1], 0.008), max(c[2], 0.009)), 0.32, coat=0.45, ruido=0.2)
    elif sat > 0.25:
        novo = mat_simples('Colorido ' + n[-10:], c, 0.38, coat=0.25, ruido=0.2)
    elif L > 0.6:
        novo = mat_simples('Branco ' + n[-10:], tuple(x * 0.8 for x in c), 0.45, ss=0.04, ruido=0.25)
    else:
        # cinza médio do CAD costuma ser metal (parafusos, conectores, blindagens)
        novo = mat_simples('Metal ' + n[-10:], c, 0.3, metal=0.85, ruido=0.0, raio=0.00015)
    mats_cache[m.name] = novo
    return novo

malhas = [o for o in bpy.data.objects if o.type == 'MESH']
for o in malhas:
    for s in o.material_slots:
        if s.material:
            s.material = trocar(s.material)
    # normais suaves por ângulo
    for p in o.data.polygons:
        p.use_smooth = True
    try:
        o.data.set_sharp_from_angle(angle=math.radians(35))
    except Exception:
        pass

# bateria = maior peça branca: ganha a etiqueta
def volume(o):
    d = o.dimensions
    return d.x * d.y * d.z
brancos = [o for o in malhas if any(s.material and s.material.name.startswith('Branco') for s in o.material_slots)]
if brancos:
    bat = max(brancos, key=volume)
    et = mat_etiqueta()
    for s in bat.material_slots:
        s.material = et
    print('bateria:', bat.name, tuple(round(x, 3) for x in bat.dimensions))

# ------------------------------------------------------------------ bancada
def plano_textura(nome, tam, z, dif, nor, rough=None, escala=1.0, img_cor=None):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, z))
    p = bpy.context.active_object; p.name = nome
    p.scale = (tam[0], tam[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    m, nt, bsdf = novo_mat(nome)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1100, 0)
    mp = nt.nodes.new('ShaderNodeMapping'); mp.location = (-900, 0)
    mp.inputs['Scale'].default_value = (escala, escala, escala)
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

tampo, b_tampo = plano_textura('Tampo de madeira', (1.6, 1.0), -0.0005, 'dark_wood_diff.jpg', 'dark_wood_nor_gl.jpg', 'dark_wood_rough.jpg', 1.0)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.0255))
borda = bpy.context.active_object; borda.name = 'Tampo (espessura)'
borda.scale = (1.6, 1.0, 0.05); borda.data.materials.append(tampo.data.materials[0])
tapete, b_tap = plano_textura('Tapete de corte', (0.6, 0.45), 0.0, 'tapete.png', None, None, 1.0)
b_tap.inputs['Roughness'].default_value = 0.7
b_tap.inputs['Specular IOR Level'].default_value = 0.3
tapete.rotation_euler.z = math.radians(8)

# ------------------------------------------------------------------ luz e mundo
scn = bpy.context.scene
w = bpy.data.worlds.new('Estudio'); scn.world = w
w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputWorld')
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.join(TEX, 'studio.hdr'))
bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.12
escuro = nt.nodes.new('ShaderNodeBackground'); escuro.inputs['Color'].default_value = (0.004, 0.005, 0.007, 1)
lp = nt.nodes.new('ShaderNodeLightPath')
mx_ = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(env.outputs['Color'], bg.inputs['Color'])
nt.links.new(lp.outputs['Is Camera Ray'], mx_.inputs['Fac'])
nt.links.new(bg.outputs[0], mx_.inputs[1]); nt.links.new(escuro.outputs[0], mx_.inputs[2])
nt.links.new(mx_.outputs[0], out.inputs['Surface'])

def luz_area(nome, loc, alvo, tam, energia, cor=(1, 1, 1), forma='RECTANGLE'):
    l = bpy.data.lights.new(nome, 'AREA'); l.shape = forma
    l.size = tam[0]; l.size_y = tam[1]; l.energy = energia; l.color = cor
    o = bpy.data.objects.new(nome, l); scn.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

luz_area('Softbox principal', (0.35, -0.45, 0.55), (0, 0, 0.02), (0.6, 0.4), 38, (1.0, 0.95, 0.88))
luz_area('Contraluz azul', (-0.45, 0.5, 0.25), (0, 0, 0.03), (0.5, 0.15), 40, (0.35, 0.55, 1.0))
luz_area('Preenchimento', (-0.5, -0.35, 0.3), (0, 0, 0.02), (0.4, 0.4), 6, (1.0, 0.85, 0.7))
luz_area('Recorte de cima', (0.0, 0.25, 0.7), (0, 0, 0), (0.3, 0.3), 9, (0.9, 0.95, 1.0))

# ------------------------------------------------------------------ câmeras
def camera(nome, loc, alvo, lente, foco=None, f=4.0):
    c = bpy.data.cameras.new(nome); c.lens = lente; c.sensor_width = 36
    c.clip_start = 0.005
    o = bpy.data.objects.new(nome, c); scn.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(alvo) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if foco is not None:
        c.dof.use_dof = True
        c.dof.focus_distance = (Vector(foco) - Vector(loc)).length
        c.dof.aperture_fstop = f
    return o

zc = alt * 0.45
camera('1_heroi', (0.34, -0.36, 0.2), (0, 0, zc), 65, (0, 0, zc), 5.6)
camera('2_de_cima', (0.02, -0.12, 0.48), (0, 0, zc * 0.5), 50, (0, 0, zc), 8.0)
# close no motor da frente à direita (frente do drone = -Y, onde fica a câmera)
alvo_m = Vector((0.092, -0.077, 0.022))
camera('3_motor_macro', alvo_m + Vector((0.12, -0.11, 0.07)), alvo_m, 70, alvo_m, 5.6)
# close na câmera DJI O4 e no stack entre as placas
alvo_c = Vector((0.0, -0.06, 0.016))
camera('4_stack_e_camera', (-0.11, -0.2, 0.055), alvo_c, 85, alvo_c, 6.3)
scn.camera = bpy.data.objects['1_heroi']

# ------------------------------------------------------------------ render
scn.render.engine = 'CYCLES'
scn.cycles.samples = 1024
scn.cycles.adaptive_threshold = 0.008
scn.cycles.use_denoising = True
scn.cycles.denoiser = 'OPENIMAGEDENOISE'
scn.cycles.max_bounces = 12
scn.cycles.transmission_bounces = 12
scn.cycles.glossy_bounces = 8
scn.render.resolution_x = 3840
scn.render.resolution_y = 2160
scn.render.film_transparent = False
scn.view_settings.view_transform = 'AgX'
scn.view_settings.look = 'AgX - Medium High Contrast'
try:
    scn.render.image_settings.media_type = 'IMAGE'
except Exception:
    pass
scn.render.image_settings.file_format = 'PNG'
scn.render.image_settings.color_depth = '16'

# remove imagens do cenário antigo que não existem mais e empacota o resto
for im in list(bpy.data.images):
    if im.users == 0 or (im.filepath and not im.packed_file and not os.path.exists(bpy.path.abspath(im.filepath))):
        bpy.data.images.remove(im)
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=SAIDA, compress=True)
print('salvo', SAIDA)
