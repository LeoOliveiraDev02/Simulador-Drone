extends Node3D
class_name Mapa
## Campo aberto do voo do E88 (1 x 1 km de área de voo), montado por código:
## terreno, pasto, estrada, açude, base de pouso com H, galpão, cercas, rede elétrica,
## biruta, portais de treino, árvores, arbustos e pedras — agora com colisão em tudo
## (o drone bate, quebra hélice e cai).

const REC := "res://recursos/"

var qualidade_baixa := false
var blocos_grama: Array[MultiMeshInstance3D] = []
var luz_sol: DirectionalLight3D
var ambiente: Environment
var arvores_longe: Array[Node3D] = []
var movel := false    # celular (Android): menos capim, árvores mais simples, sombras menores
var previa := false   # prévia no servidor sem placa de vídeo: quase sem capim

var ruido_a := FastNoiseLite.new()
var ruido_b := FastNoiseLite.new()
var ruido_c := FastNoiseLite.new()
var rng := RandomNumberGenerator.new()

# estrada de terra: pontos (x, z) do eixo
var estrada: PackedVector2Array = PackedVector2Array([
	Vector2(120, 90), Vector2(66, 22), Vector2(49, -40), Vector2(46, -130),
	Vector2(58, -260), Vector2(86, -480), Vector2(132, -900), Vector2(200, -1500),
	Vector2(260, -2300)])
const ACUDE_C := Vector2(-6, -122)
const ACUDE_R := Vector2(34, 19)
const GALPAO_C := Vector2(-47, -60)
var altura_centro := 0.0
var nivel_agua := 0.0
var altura_galpao := 0.0

var biruta: Node3D

var cache_mat := {}
var cache_cena := {}


const ESCALA_BASE := 0.5
const LIMITE := 500.0          # área de voo: 1 x 1 km em volta da base

var corpo_estatico: StaticBody3D
var mat_grama: ShaderMaterial
var biruta_pano: MeshInstance3D
var pos_portais: Array[Vector2] = []
var portais: Array = []   # [centro, normal] de cada aro
var pontos_pouso: Array = []  # [nome, ponto em cima] para o desafio de pouso
var folhagens: Array = []   # [inverso do transform, dados das folhas, caixa] — copas e arbustos
var pano_ceu: PanoramaSkyMaterial
var hora_atual := 0
var nuvem_desloc := Vector2.ZERO
var nuvens_ligadas := true
var vento_vel := Vector2(1.0, 0.3)
# céus (Poly Haven, CC0): arquivo, azimute e elevação do sol na foto, cor e força do sol, nuvens, exposição, neblina
const HORAS := [
	["kloofendal_48d_partly_cloudy_puresky_godot.hdr", 34.2, 47.9, Color(1.0, 0.96, 0.9), 1.85, 0.42, 1.0, Color(0.66, 0.76, 0.9)],
	["kloppenheim_06_puresky_godot.hdr", 38.5, 9.5, Color(1.0, 0.66, 0.38), 1.6, 0.18, 1.2, Color(0.95, 0.72, 0.52)],
	["farm_field_puresky_godot.hdr", 36.6, 51.0, Color(1.0, 0.96, 0.9), 1.7, 0.0, 1.05, Color(0.66, 0.76, 0.9)],
]
const NOMES_HORA := ["TARDE COM NUVENS", "PÔR DO SOL", "CÉU LIMPO"]
var obstaculos: Array = []  # [centro xz, raio, altura do topo] — fazem sombra de vento


signal progresso(fracao: float, texto: String)


func _passo(f: float, texto: String) -> void:
	progresso.emit(f, texto)
	await get_tree().process_frame
	await get_tree().process_frame


func montar(baixa := false) -> void:
	qualidade_baixa = baixa
	rng.seed = 2026
	ruido_a.seed = 11
	ruido_a.frequency = 1.0
	ruido_a.fractal_octaves = 4
	ruido_b.seed = 23
	ruido_b.frequency = 1.0
	ruido_b.fractal_octaves = 3
	ruido_c.seed = 37
	ruido_c.frequency = 1.0
	ruido_c.fractal_octaves = 2
	altura_centro = _altura_bruta(0.0, 0.0)
	altura_galpao = _altura_bruta(GALPAO_C.x, GALPAO_C.y)
	nivel_agua = _altura_bruta(ACUDE_C.x, ACUDE_C.y) - 0.6

	corpo_estatico = StaticBody3D.new()
	corpo_estatico.name = "Colisao"
	add_child(corpo_estatico)

	var t0 := Time.get_ticks_msec()
	await _passo(0.02, "Céu e luz do sol")
	_montar_ambiente()
	await _passo(0.08, "Relevo do pasto")
	_montar_terreno()
	await _passo(0.2, "Chão firme (colisão do terreno)")
	_colisao_terreno()
	await _passo(0.3, "Açude")
	_montar_agua()
	await _passo(0.36, "Capim")
	_montar_grama()
	await _passo(0.46, "Base de pouso, biruta e galpão")
	_montar_base_pouso()
	_montar_biruta()
	_montar_galpao()
	await _passo(0.54, "Cercas")
	_montar_cercas()
	await _passo(0.6, "Rede elétrica")
	_montar_postes()
	await _passo(0.64, "Portais de treino")
	_montar_portais()
	await _passo(0.68, "Árvores e eucaliptos")
	_montar_vegetacao()
	await _passo(0.8, "Pedras")
	_montar_pedras()
	await _passo(0.84, "Jacarandás, píer e objetos da fazenda")
	_montar_extras()
	await _passo(0.86, "Flores do campo")
	_montar_flores()
	_iniciar_nuvens()
	definir_hora(hora_atual)
	print("Mapa montado em %d ms" % (Time.get_ticks_msec() - t0))


# ------------------------------------------------------------------ relevo

func _altura_bruta(x: float, z: float) -> float:
	var d := Vector2(x, z).length()
	var h := ruido_a.get_noise_2d(x * 0.0035, z * 0.0035) * 7.0
	h += ruido_b.get_noise_2d(x * 0.018, z * 0.018) * 1.1
	h += ruido_c.get_noise_2d(x * 0.09, z * 0.09) * 0.12
	var morro := ruido_b.get_noise_2d(x * 0.0011 + 40.0, z * 0.0011) * 0.5 + 0.5
	h += smoothstep(320.0, 1700.0, d) * (40.0 + morro * 150.0)
	return h


func distancia_estrada(p: Vector2) -> float:
	# atalho: longe da faixa da estrada não precisa calcular
	if p.x < 25.0 or p.x > 290.0:
		return 1e9
	var melhor := 1e9
	for i in estrada.size() - 1:
		var a := estrada[i]
		var b := estrada[i + 1]
		var ab := b - a
		var t := clampf((p - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
		melhor = minf(melhor, p.distance_to(a + ab * t))
	return melhor


func _acude_e(x: float, z: float) -> float:
	var q := Vector2((x - ACUDE_C.x) / ACUDE_R.x, (z - ACUDE_C.y) / ACUDE_R.y)
	return q.length_squared()


func altura(x: float, z: float) -> float:
	var h := _altura_bruta(x, z)
	var d := Vector2(x, z).length()
	# área plana em volta da base de pouso
	h = lerpf(altura_centro, h, smoothstep(14.0, 45.0, d))
	# galpão no plano
	var dg := Vector2(x, z).distance_to(GALPAO_C)
	if dg < 24.0:
		h = lerpf(altura_galpao, h, smoothstep(11.0, 24.0, dg))
	# estrada levemente rebaixada
	var de := distancia_estrada(Vector2(x, z))
	h -= 0.14 * (1.0 - smoothstep(2.5, 4.5, de))
	# açude
	var e := _acude_e(x, z)
	h -= 2.6 * (1.0 - smoothstep(0.55, 1.35, e))
	return h


func _mascara(x: float, z: float) -> Color:
	var de := distancia_estrada(Vector2(x, z))
	var r := 1.0 - smoothstep(2.4, 4.3, de)
	var e := _acude_e(x, z)
	var g := 1.0 - smoothstep(1.0, 1.55, e)
	var d := Vector2(x, z).length()
	var b := 1.0 - smoothstep(4.7, 6.6, d)
	b = maxf(b, 1.0 - smoothstep(9.0, 15.0, Vector2(x, z).distance_to(GALPAO_C)))
	return Color(r, g, b, 1.0)


# ------------------------------------------------------------------ ambiente

func _montar_ambiente() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var ceu := Sky.new()
	var pano := PanoramaSkyMaterial.new()
	pano.panorama = load(REC + "ceu/" + HORAS[0][0])
	pano.energy_multiplier = 1.0
	pano_ceu = pano
	ceu.sky_material = pano
	ceu.radiance_size = Sky.RADIANCE_SIZE_256 if movel else Sky.RADIANCE_SIZE_1024
	env.sky = ceu
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY

	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.05

	env.ssao_enabled = not movel
	env.ssao_radius = 1.4
	env.ssao_intensity = 1.8
	env.ssil_enabled = false
	env.ssr_enabled = not movel
	env.ssr_max_steps = 48

	env.sdfgi_enabled = not qualidade_baixa
	env.sdfgi_use_occlusion = true
	env.sdfgi_cascades = 4
	env.sdfgi_min_cell_size = 0.25
	env.sdfgi_y_scale = Environment.SDFGI_Y_SCALE_75_PERCENT

	ambiente = env
	env.glow_enabled = not movel
	env.glow_intensity = 0.35
	env.glow_bloom = 0.04

	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	env.fog_light_color = Color(0.66, 0.76, 0.9)
	env.fog_density = 0.0006
	env.fog_aerial_perspective = 0.75
	env.fog_sky_affect = 0.12

	env.volumetric_fog_enabled = not qualidade_baixa
	env.volumetric_fog_density = 0.0035
	env.volumetric_fog_albedo = Color(0.9, 0.93, 1.0)
	env.volumetric_fog_anisotropy = 0.45
	env.volumetric_fog_length = 160.0

	env.adjustment_enabled = true
	env.adjustment_saturation = 1.08
	env.adjustment_contrast = 1.04

	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	# Sol: mesma direção do sol da foto HDRI (elevação ~50°)
	var sol := DirectionalLight3D.new()
	luz_sol = sol
	var elev := deg_to_rad(49.6)
	var dir_sol := Vector3(-0.602 * cos(elev), sin(elev), 0.799 * cos(elev)).normalized()
	add_child(sol)
	sol.look_at_from_position(Vector3.ZERO, -dir_sol, Vector3.UP)
	sol.light_energy = 1.7
	sol.light_color = Color(1.0, 0.96, 0.9)
	sol.light_angular_distance = 0.6
	sol.shadow_enabled = true
	sol.shadow_blur = 1.0
	sol.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sol.directional_shadow_max_distance = 420.0 if not movel else 45.0
	if movel:
		sol.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
		sol.shadow_blur = 0.6
	sol.directional_shadow_split_1 = 0.04
	sol.directional_shadow_split_2 = 0.14
	sol.directional_shadow_split_3 = 0.4
	sol.light_volumetric_fog_energy = 1.0


# ------------------------------------------------------------------ materiais

func _tex(caminho: String) -> Texture2D:
	return load(caminho)


func _mat_pbr(nome: String, escala: float, tom := Color.WHITE) -> ORMMaterial3D:
	var chave := "%s_%s_%s" % [nome, escala, tom]
	if cache_mat.has(chave):
		return cache_mat[chave]
	var m := ORMMaterial3D.new()
	var p := REC + "texturas/" + nome + "/"
	m.albedo_texture = _tex(p + "diff.jpg")
	m.albedo_color = tom
	m.normal_enabled = true
	m.normal_texture = _tex(p + "nor_gl.jpg")
	m.orm_texture = _tex(p + "arm.jpg")
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE / escala
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	cache_mat[chave] = m
	return m


func _mat_cor(cor: Color, rugosidade := 0.6, metalico := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = cor
	m.roughness = rugosidade
	m.metallic = metalico
	return m


func _ruido_tex(freq: float, normal := false, tam := 512) -> NoiseTexture2D:
	var n := FastNoiseLite.new()
	n.frequency = freq
	n.fractal_octaves = 5
	var t := NoiseTexture2D.new()
	t.noise = n
	t.width = tam
	t.height = tam
	t.seamless = true
	t.generate_mipmaps = true
	if normal:
		t.as_normal_map = true
		t.bump_strength = 6.0
	return t


func _malha(mesh: Mesh, mat: Material, pos: Vector3, rot := Vector3.ZERO, escala := Vector3.ONE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	add_child(mi)
	mi.position = pos
	mi.rotation = rot
	mi.scale = escala
	return mi


func _caixa(tam: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = tam
	return b


func _cilindro(r_topo: float, r_base: float, alt: float, lados := 16) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r_topo
	c.bottom_radius = r_base
	c.height = alt
	c.radial_segments = lados
	return c


# ------------------------------------------------------------------ terreno

func _montar_terreno() -> void:
	# grade não uniforme: células de ~0,8 m perto do centro e enormes no horizonte
	var n := 400 if qualidade_baixa else 640
	var A := 250.0
	var B := 2050.0
	var coords := PackedFloat32Array()
	coords.resize(n + 1)
	for i in n + 1:
		var t := -1.0 + 2.0 * float(i) / float(n)
		coords[i] = signf(t) * (A * absf(t) + B * pow(absf(t), 4.0))

	var verts := PackedVector3Array()
	var normais := PackedVector3Array()
	var cores := PackedColorArray()
	var uvs := PackedVector2Array()
	verts.resize((n + 1) * (n + 1))
	normais.resize(verts.size())
	cores.resize(verts.size())
	uvs.resize(verts.size())
	var alturas := PackedFloat32Array()
	alturas.resize(verts.size())

	for j in n + 1:
		var z := coords[j]
		for i in n + 1:
			var x := coords[i]
			var k := j * (n + 1) + i
			var h := altura(x, z)
			alturas[k] = h
			verts[k] = Vector3(x, h, z)
			uvs[k] = Vector2(x, z)
			cores[k] = _mascara(x, z) if absf(x) < 700.0 and absf(z) < 1700.0 else Color(0, 0, 0)

	for j in n + 1:
		for i in n + 1:
			var i0 := maxi(i - 1, 0)
			var i1 := mini(i + 1, n)
			var j0 := maxi(j - 1, 0)
			var j1 := mini(j + 1, n)
			var dx := coords[i1] - coords[i0]
			var dz := coords[j1] - coords[j0]
			var hx := alturas[j * (n + 1) + i1] - alturas[j * (n + 1) + i0]
			var hz := alturas[j1 * (n + 1) + i] - alturas[j0 * (n + 1) + i]
			normais[j * (n + 1) + i] = Vector3(-hx / dx, 1.0, -hz / dz).normalized()

	var indices := PackedInt32Array()
	indices.resize(n * n * 6)
	var c := 0
	for j in n:
		for i in n:
			var a := j * (n + 1) + i
			var b := a + 1
			var d := a + (n + 1)
			var e := d + 1
			indices[c] = a; indices[c + 1] = b; indices[c + 2] = d
			indices[c + 3] = b; indices[c + 4] = e; indices[c + 5] = d
			c += 6

	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = normais
	arr[Mesh.ARRAY_COLOR] = cores
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)

	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/terreno.gdshader")
	var t := REC + "texturas/"
	sm.set_shader_parameter("grama_alb", _tex(t + "grass_ground/diff.jpg"))
	sm.set_shader_parameter("grama_nor", _tex(t + "grass_ground/nor_gl.jpg"))
	sm.set_shader_parameter("grama_arm", _tex(t + "grass_ground/arm.jpg"))
	sm.set_shader_parameter("aerea_alb", _tex(t + "aerial_grass_rock/diff.jpg"))
	sm.set_shader_parameter("aerea_nor", _tex(t + "aerial_grass_rock/nor_gl.jpg"))
	sm.set_shader_parameter("terra_alb", _tex(t + "red_laterite_soil_stones/diff.jpg"))
	sm.set_shader_parameter("terra_nor", _tex(t + "red_laterite_soil_stones/nor_gl.jpg"))
	sm.set_shader_parameter("terra_arm", _tex(t + "red_laterite_soil_stones/arm.jpg"))
	sm.set_shader_parameter("lama_alb", _tex(t + "brown_mud_dry/diff.jpg"))
	sm.set_shader_parameter("lama_nor", _tex(t + "brown_mud_dry/nor_gl.jpg"))
	sm.set_shader_parameter("ruido", _ruido_tex(0.012))

	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = sm
	mi.name = "Terreno"
	add_child(mi)


func _montar_agua() -> void:
	# disco achatado em forma de elipse, do tamanho do buraco do açude
	var disco := _cilindro(1.0, 1.0, 0.02, 64)
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/agua.gdshader")
	sm.set_shader_parameter("ondas", _ruido_tex(0.03, true, 256))
	_malha(disco, sm, Vector3(ACUDE_C.x, nivel_agua, ACUDE_C.y), Vector3.ZERO, Vector3(ACUDE_R.x * 1.12, 1.0, ACUDE_R.y * 1.12))


# ------------------------------------------------------------------ grama

func _malha_folha() -> ArrayMesh:
	# folha de capim: 4 níveis, afinando até a ponta (altura 1, ajustada pela escala)
	var v := PackedVector3Array()
	var uv := PackedVector2Array()
	var nrm := PackedVector3Array()
	var larguras := [0.022, 0.019, 0.012, 0.0]
	var inclinacao := [0.0, 0.05, 0.14, 0.28]
	for k in 4:
		var y := float(k) / 3.0
		var w: float = larguras[k]
		var off: float = inclinacao[k]
		if k < 3:
			v.append(Vector3(-w, y, off)); uv.append(Vector2(0, y)); nrm.append(Vector3(0, 0.3, 1).normalized())
			v.append(Vector3(w, y, off)); uv.append(Vector2(1, y)); nrm.append(Vector3(0, 0.3, 1).normalized())
		else:
			v.append(Vector3(0, y, off)); uv.append(Vector2(0.5, 1)); nrm.append(Vector3(0, 0.3, 1).normalized())
	var idx := PackedInt32Array([0, 1, 2, 1, 3, 2, 2, 3, 4, 3, 5, 4, 4, 5, 6])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = v
	arr[Mesh.ARRAY_TEX_UV] = uv
	arr[Mesh.ARRAY_NORMAL] = nrm
	arr[Mesh.ARRAY_INDEX] = idx
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return m


func _montar_grama() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/grama.gdshader")
	mat_grama = mat
	var folha := _malha_folha()
	# grama em blocos de 20 x 20 m para o motor descartar o que está fora da tela
	var tam_bloco := 20.0
	var raio := 70.0 if qualidade_baixa else 150.0
	if movel:
		raio = 32.0
	if previa:
		raio = 25.0
	var dens_max := 18.0 if qualidade_baixa else 70.0
	if movel:
		dens_max = 9.0
	var cam_ref := Vector2(0, 26)
	var total := 0
	var bx := -raio
	while bx < raio:
		var bz := -raio - 40.0
		while bz < raio * 0.4:
			var centro := Vector2(bx + tam_bloco * 0.5, bz + tam_bloco * 0.5)
			var dist := centro.distance_to(cam_ref)
			if dist > raio:
				bz += tam_bloco
				continue
			var dens := lerpf(dens_max, dens_max * 0.12, smoothstep(10.0, raio, dist))
			var qtd := int(tam_bloco * tam_bloco * dens)
			var xs: Array[Transform3D] = []
			var custom: Array[Color] = []
			for i in qtd:
				var x := bx + rng.randf() * tam_bloco
				var z := bz + rng.randf() * tam_bloco
				var p := Vector2(x, z)
				if p.length() < 4.75:
					continue
				if distancia_estrada(p) < 3.6 + rng.randf() * 1.2:
					continue
				if _acude_e(x, z) < 1.16:
					continue
				if p.distance_to(GALPAO_C) < 10.0 + rng.randf() * 3.0:
					continue
				var mancha := ruido_c.get_noise_2d(x * 0.08, z * 0.08) * 0.5 + 0.5
				if mancha < 0.28 and rng.randf() < 0.7:
					continue
				var alt := lerpf(0.22, 0.62, rng.randf()) * lerpf(0.7, 1.25, mancha)
				var b := Basis(Vector3.UP, rng.randf() * TAU)
				b = b.rotated(Vector3(rng.randf() - 0.5, 0, rng.randf() - 0.5).normalized(), rng.randf() * 0.25)
				b = b.scaled(Vector3(lerpf(0.8, 1.4, rng.randf()), alt, 1.0))
				xs.append(Transform3D(b, Vector3(x, altura(x, z) - 0.02, z)))
				var seca := 0.6 * smoothstep(0.6, 0.9, ruido_b.get_noise_2d(x * 0.05, z * 0.05) * 0.5 + 0.5 + rng.randf() * 0.25)
				custom.append(Color(seca, rng.randf(), 0, 0))
			if xs.size() > 0:
				var mm := MultiMesh.new()
				mm.transform_format = MultiMesh.TRANSFORM_3D
				mm.use_custom_data = true
				mm.mesh = folha
				mm.instance_count = xs.size()
				for i in xs.size():
					mm.set_instance_transform(i, xs[i])
					mm.set_instance_custom_data(i, custom[i])
				var mmi := MultiMeshInstance3D.new()
				mmi.multimesh = mm
				mmi.material_override = mat
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if dist > 60.0 or movel else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
				blocos_grama.append(mmi)
				mmi.visibility_range_end = raio + 30.0
				add_child(mmi)
				total += xs.size()
			bz += tam_bloco
		bx += tam_bloco
	print("Folhas de capim: ", total)


# ------------------------------------------------------------------ base de pouso e biruta

func _montar_base_pouso() -> void:
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/base_pouso.gdshader")
	var t := REC + "texturas/concrete_floor_worn_001/"
	sm.set_shader_parameter("c_alb", _tex(t + "diff.jpg"))
	sm.set_shader_parameter("c_nor", _tex(t + "nor_gl.jpg"))
	sm.set_shader_parameter("c_arm", _tex(t + "arm.jpg"))
	sm.set_shader_parameter("ruido", _ruido_tex(0.05))
	# base de 9 m de diâmetro (proporcional ao E88; o desenho do H escala junto)
	_malha(_cilindro(9.0, 9.15, 0.4, 96), sm, Vector3(0, altura_centro - 0.08, 0), Vector3.ZERO, Vector3(ESCALA_BASE, 1.0, ESCALA_BASE))
	_col_cilindro(9.1 * ESCALA_BASE, 0.4, Transform3D(Basis(), Vector3(0, altura_centro - 0.08, 0)))


func _montar_biruta() -> void:
	var x := -15.0
	var z := 3.0
	var y := altura(x, z)
	var metal := _mat_cor(Color(0.72, 0.72, 0.7), 0.45, 0.8)
	var mastro := _cilindro(0.045, 0.06, 6.2, 12)
	_malha(mastro, metal, Vector3(x, y + 3.1, z))
	_col_convexa(mastro, Transform3D(Basis(), Vector3(x, y + 3.1, z)))
	_col_cilindro(0.35, 0.25, Transform3D(Basis(), Vector3(x, y + 0.1, z)))
	_malha(_cilindro(0.35, 0.35, 0.25, 24), _mat_pbr("concrete_floor_worn_001", 1.0), Vector3(x, y + 0.1, z))
	# a biruta aponta para onde o vento vai
	biruta = Node3D.new()
	add_child(biruta)
	biruta.position = Vector3(x, y + 5.9, z)
	biruta.rotation = Vector3(0, deg_to_rad(-25), 0)
	var aro := TorusMesh.new()
	aro.inner_radius = 0.33
	aro.outer_radius = 0.37
	var mi_aro := MeshInstance3D.new()
	mi_aro.mesh = aro
	mi_aro.material_override = metal
	mi_aro.rotation = Vector3(0, 0, PI / 2)
	mi_aro.position = Vector3(0.05, 0, 0)
	biruta.add_child(mi_aro)
	var cone := _cilindro(0.16, 0.35, 2.4, 24)
	cone.cap_top = false
	cone.cap_bottom = false
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/biruta.gdshader")
	var mi := MeshInstance3D.new()
	mi.mesh = cone
	mi.material_override = sm
	mi.rotation = Vector3(0, 0, -PI / 2 - 0.12)
	mi.position = Vector3(1.25, -0.12, 0)
	biruta.add_child(mi)
	biruta_pano = mi


# ------------------------------------------------------------------ galpão

func _montar_galpao() -> void:
	var g := Node3D.new()
	add_child(g)
	g.position = Vector3(GALPAO_C.x, altura(GALPAO_C.x, GALPAO_C.y), GALPAO_C.y)
	g.rotation.y = deg_to_rad(12)
	var parede := _mat_pbr("clay_plaster", 2.5, Color(1.0, 0.97, 0.9))
	var telha := _mat_pbr("clay_roof_tiles_02", 2.0)
	var madeira := _mat_pbr("fine_grained_wood", 1.2, Color(0.75, 0.62, 0.5))
	var piso := _mat_pbr("concrete_floor_worn_001", 3.0, Color(0.85, 0.8, 0.75))
	var L := 17.0
	var P := 7.5
	var H := 3.0

	_filho(g, _caixa(Vector3(L + 0.6, 0.3, P + 0.6)), piso, Vector3(0, 0.05, 0))
	_filho(g, _caixa(Vector3(L, H, 0.22)), parede, Vector3(0, H / 2, -P / 2))
	_filho(g, _caixa(Vector3(0.22, H, P)), parede, Vector3(-L / 2, H / 2, 0))
	_filho(g, _caixa(Vector3(0.22, H, P)), parede, Vector3(L / 2, H / 2, 0))
	# parede baixa na frente, só num trecho (como em galpão de fazenda)
	_filho(g, _caixa(Vector3(5.5, 1.1, 0.2)), parede, Vector3(-L / 2 + 2.9, 0.55, P / 2))
	for i in 6:
		var x := -L / 2 + 0.2 + i * (L - 0.4) / 5.0
		_filho(g, _cilindro(0.1, 0.11, H, 10), madeira, Vector3(x, H / 2, P / 2))
	_filho(g, _caixa(Vector3(L + 0.4, 0.22, 0.2)), madeira, Vector3(0, H, P / 2))
	_filho(g, _caixa(Vector3(L + 0.4, 0.22, 0.2)), madeira, Vector3(0, H, -P / 2))
	# telhado de duas águas com beiral
	var beiral := 0.9
	var meia := P / 2 + beiral
	var subida := 1.8
	var comp := sqrt(meia * meia + subida * subida)
	var ang := atan2(subida, meia)
	for s: float in [-1.0, 1.0]:
		_filho(g, _caixa(Vector3(L + 1.6, 0.14, comp)), telha,
			Vector3(0, H + subida / 2 - 0.15, s * meia / 2), Vector3(s * ang, 0, 0))
	_filho(g, _caixa(Vector3(L + 1.7, 0.2, 0.3)), telha, Vector3(0, H + subida - 0.1, 0))
	# oitões
	for s: float in [-1.0, 1.0]:
		var tri := _prisma(P, subida)
		_filho(g, tri, parede, Vector3(s * L / 2, H, 0))
	# alguns objetos de fazenda dentro e na frente
	for i in 4:
		var x := rng.randf_range(-L / 2 + 1, L / 2 - 1)
		_filho(g, _cilindro(0.3, 0.3, 0.85, 14), _mat_cor(Color(0.35, 0.3, 0.22), 0.8), Vector3(x, 0.62, rng.randf_range(-2.5, 1.5)))
	for i in 3:
		_filho(g, _caixa(Vector3(1.1, 0.5, 0.8)), madeira, Vector3(L / 2 - 1.5 - i * 1.3, 0.45, -2.6))
	_colidir_filhos(g)
	obstaculos.append([GALPAO_C, 9.0, g.position.y + 4.8])


func _prisma(base: float, alt: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pts := [Vector3(0, 0, -base / 2), Vector3(0, 0, base / 2), Vector3(0, alt, 0)]
	for lado: float in [1.0, -1.0]:
		st.set_normal(Vector3(lado, 0, 0))
		if lado > 0:
			for p: Vector3 in [pts[0], pts[2], pts[1]]:
				st.set_uv(Vector2(p.z, p.y))
				st.add_vertex(p + Vector3(0.11, 0, 0))
		else:
			for p: Vector3 in [pts[0], pts[1], pts[2]]:
				st.set_uv(Vector2(p.z, p.y))
				st.add_vertex(p - Vector3(0.11, 0, 0))
	st.generate_tangents()
	return st.commit()


func _filho(pai: Node3D, mesh: Mesh, mat: Material, pos: Vector3, rot := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	pai.add_child(mi)
	mi.position = pos
	mi.rotation = rot
	return mi


# ------------------------------------------------------------------ cercas

func _montar_cercas() -> void:
	var linhas: Array = []
	# cerca do pasto atravessando o campo
	linhas.append([Vector2(-110, -34), Vector2(-20, -31), Vector2(42, -33)])
	# cercas dos dois lados da estrada
	for lado: float in [-1.0, 1.0]:
		var pts: Array = []
		for i in range(1, estrada.size() - 3):
			var a := estrada[i]
			var b := estrada[i + 1]
			var dir := (b - a).normalized()
			var nrm := Vector2(-dir.y, dir.x) * lado * 7.5
			pts.append(a + nrm)
		linhas.append(pts)
	# curral ao lado do galpão
	var gc := GALPAO_C
	linhas.append([gc + Vector2(9, 6), gc + Vector2(24, 8), gc + Vector2(26, -6), gc + Vector2(10, -9)])

	var mourao := _cilindro(0.06, 0.075, 1.45, 8)
	var fio := _caixa(Vector3(1, 0.012, 0.012))
	var mm_m := MultiMesh.new()
	mm_m.transform_format = MultiMesh.TRANSFORM_3D
	mm_m.mesh = mourao
	var mm_f := MultiMesh.new()
	mm_f.transform_format = MultiMesh.TRANSFORM_3D
	mm_f.mesh = fio
	var tm: Array[Transform3D] = []
	var tf: Array[Transform3D] = []
	for linha in linhas:
		var anterior := Vector3.INF
		for s in linha.size() - 1:
			var a: Vector2 = linha[s]
			var b: Vector2 = linha[s + 1]
			var passos := maxi(1, int(a.distance_to(b) / 3.2))
			for k in passos + (1 if s == linha.size() - 2 else 0):
				var p := a.lerp(b, float(k) / passos)
				var y := altura(p.x, p.y)
				var inc := Basis(Vector3.FORWARD, rng.randf_range(-0.06, 0.06)).rotated(Vector3.RIGHT, rng.randf_range(-0.05, 0.05))
				var topo := Vector3(p.x, y, p.y)
				tm.append(Transform3D(inc, topo + Vector3(0, 0.62, 0)))
				_col_convexa(mourao, Transform3D(inc, topo + Vector3(0, 0.62, 0)))
				if anterior != Vector3.INF:
					for alt: float in [0.45, 0.85, 1.2]:
						var p1: Vector3 = anterior + Vector3(0, alt, 0)
						var p2: Vector3 = topo + Vector3(0, alt, 0)
						tf.append(_segmento(p1, p2, 1.0))
						_col_segmento(p1, p2, 0.006)
				anterior = topo
	mm_m.instance_count = tm.size()
	for i in tm.size():
		mm_m.set_instance_transform(i, tm[i])
	mm_f.instance_count = tf.size()
	for i in tf.size():
		mm_f.set_instance_transform(i, tf[i])
	var mi_m := MultiMeshInstance3D.new()
	mi_m.multimesh = mm_m
	mi_m.material_override = _mat_pbr("fine_grained_wood", 0.8, Color(0.62, 0.5, 0.38))
	add_child(mi_m)
	var mi_f := MultiMeshInstance3D.new()
	mi_f.multimesh = mm_f
	mi_f.material_override = _mat_cor(Color(0.45, 0.45, 0.43), 0.5, 0.7)
	mi_f.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi_f)


## transform de uma caixa de 1 m no eixo X esticada de p1 até p2
func _segmento(p1: Vector3, p2: Vector3, espessura: float) -> Transform3D:
	var d := p2 - p1
	var x := d.normalized()
	var up := Vector3.UP if absf(x.y) < 0.95 else Vector3.FORWARD
	var z := x.cross(up).normalized()
	var y := z.cross(x).normalized()
	var b := Basis(x * d.length(), y * espessura, z * espessura)
	return Transform3D(b, (p1 + p2) * 0.5)


# ------------------------------------------------------------------ postes de energia

func _montar_postes() -> void:
	var madeira := _mat_pbr("fine_grained_wood", 1.0, Color(0.5, 0.42, 0.34))
	var poste := _cilindro(0.11, 0.15, 9.5, 10)
	var cruzeta := _caixa(Vector3(2.4, 0.12, 0.12))
	var isolador := _cilindro(0.05, 0.07, 0.18, 8)
	var tp: Array[Transform3D] = []
	var tc: Array[Transform3D] = []
	var ti: Array[Transform3D] = []
	var tf: Array[Transform3D] = []
	var pontos_ant: Array = []
	var dist_acum := 0.0
	var proximo := 0.0
	for i in estrada.size() - 1:
		var a := estrada[i]
		var b := estrada[i + 1]
		var seg := a.distance_to(b)
		var dir := (b - a).normalized()
		var nrm := Vector2(-dir.y, dir.x) * -13.0
		while proximo <= dist_acum + seg:
			var p := a + dir * (proximo - dist_acum) + nrm
			var y := altura(p.x, p.y)
			var base := Vector3(p.x, y, p.y)
			var yaw := atan2(dir.x, dir.y)
			var bas := Basis(Vector3.UP, yaw)
			tp.append(Transform3D(bas.rotated(Vector3.RIGHT, rng.randf_range(-0.02, 0.02)), base + Vector3(0, 4.75, 0)))
			tc.append(Transform3D(bas, base + Vector3(0, 8.9, 0)))
			_col_convexa(poste, tp[tp.size() - 1])
			_col_caixa(Vector3(2.4, 0.12, 0.12), Transform3D(bas, base + Vector3(0, 8.9, 0)))
			var pontos: Array = []
			for off: float in [-1.0, 0.0, 1.0]:
				var pt := base + Vector3(0, 9.05, 0) + bas * Vector3(off, 0, 0)
				ti.append(Transform3D(bas, pt))
				pontos.append(pt + Vector3(0, 0.09, 0))
			if pontos_ant.size() == 3:
				for k in 3:
					var p1: Vector3 = pontos_ant[k]
					var p2: Vector3 = pontos[k]
					var partes := 10
					var ant := p1
					for s in range(1, partes + 1):
						var t := float(s) / partes
						var q := p1.lerp(p2, t) - Vector3(0, 1.1 * 4.0 * t * (1.0 - t), 0)
						tf.append(_segmento(ant, q, 0.018))
						_col_segmento(ant, q, 0.009)
						ant = q
			pontos_ant = pontos
			proximo += 48.0
		dist_acum += seg
	_multimesh(poste, madeira, tp)
	_multimesh(cruzeta, madeira, tc)
	_multimesh(isolador, _mat_cor(Color(0.85, 0.85, 0.82), 0.25), ti)
	_multimesh(_caixa(Vector3.ONE), _mat_cor(Color(0.12, 0.12, 0.12), 0.5, 0.3), tf)


func _multimesh(mesh: Mesh, mat: Material, xs: Array[Transform3D]) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = xs.size()
	for i in xs.size():
		mm.set_instance_transform(i, xs[i])
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	mi.material_override = mat
	add_child(mi)
	return mi


# ------------------------------------------------------------------ portais de treino

func _montar_portais() -> void:
	var laranja := _mat_cor(Color(0.95, 0.36, 0.07), 0.45)
	laranja.emission_enabled = true
	laranja.emission = Color(0.9, 0.3, 0.05)
	laranja.emission_energy_multiplier = 0.15
	var preto := _mat_cor(Color(0.08, 0.08, 0.08), 0.6)
	for p: Vector2 in [Vector2(-13, -52), Vector2(24, -66)]:
		var y := altura(p.x, p.y)
		var aro := TorusMesh.new()
		aro.inner_radius = 2.05
		aro.outer_radius = 2.35
		aro.rings = 64
		aro.ring_segments = 16
		var mi_aro := _malha(aro, laranja, Vector3(p.x, y + 2.35, p.y), Vector3(PI / 2, deg_to_rad(8), 0))
		pos_portais.append(p)
		portais.append([mi_aro.position, (mi_aro.basis * Vector3.UP).normalized()])
		# o aro com o formato exato (tubo de 15 cm de raio): só bate se encostar
		_add_forma(_forma_exata(aro), mi_aro.transform)
		for s: float in [-1.0, 1.0]:
			_malha(_caixa(Vector3(0.9, 0.12, 0.25)), preto, Vector3(p.x + s * 0.75, y + 0.06, p.y))
			_col_caixa(Vector3(0.9, 0.12, 0.25), Transform3D(Basis(), Vector3(p.x + s * 0.75, y + 0.06, p.y)))


# ------------------------------------------------------------------ árvores, arbustos e pedras

func _cena(nome: String, versao := "") -> PackedScene:
	# versões das árvores (blender/modelos_celular.py), do original de 1-2 milhões de triângulos:
	#   "movel" ~75-165 mil (celular e árvores longe no PC), "pc" ~190-410 mil (árvores perto no PC)
	if versao == "":
		versao = "movel" if movel else "orig"
	var chave := nome + "@" + versao
	if cache_cena.has(chave):
		return cache_cena[chave]
	var c: PackedScene
	if versao == "movel" and ResourceLoader.exists(REC + "modelos_movel/%s.glb" % nome):
		c = load(REC + "modelos_movel/%s.glb" % nome)
	elif versao == "pc" and ResourceLoader.exists(REC + "modelos_pc/%s.glb" % nome):
		c = load(REC + "modelos_pc/%s.glb" % nome)
	else:
		c = load(REC + "modelos/%s/%s_1k.gltf" % [nome, nome])
	cache_cena[chave] = c
	return c


var mats_folhas: Array[ShaderMaterial] = []
var mat_flores: ShaderMaterial
var blocos_flores: Array = []
var jacarandas: Array = []


func _ajustar_folhas(n: Node, alt_ref := 4.0) -> void:
	# folhas viram um shader que balança com o vento (mesmo visual: textura, recorte, luz por trás)
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s)
			if m is BaseMaterial3D:
				var bm := m as BaseMaterial3D
				if bm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED and bm.albedo_texture != null:
					var sm := ShaderMaterial.new()
					sm.shader = load("res://shaders/folhas.gdshader")
					sm.set_shader_parameter("alb", bm.albedo_texture)
					sm.set_shader_parameter("tom", bm.albedo_color)
					if bm.normal_enabled and bm.normal_texture:
						sm.set_shader_parameter("nor", bm.normal_texture)
					sm.set_shader_parameter("altura_ref", alt_ref)
					mi.mesh.surface_set_material(s, sm)
					mats_folhas.append(sm)
	for f in n.get_children():
		_ajustar_folhas(f, alt_ref)


func _definir_lod(n: Node, vies: float) -> void:
	if n is GeometryInstance3D:
		(n as GeometryInstance3D).lod_bias = vies
	for f in n.get_children():
		_definir_lod(f, vies)


func _plantar(nome: String, x: float, z: float, escala: float, giro := -1.0, escala_v := Vector3.ZERO) -> Node3D:
	var dist := Vector2(x, z).length()
	var arvore := nome.contains("tree")
	var versao := ""
	if not movel and arvore:
		# PC: árvores perto com bastante detalhe; as de longe (eucaliptal, horizonte) na versão leve
		versao = "pc" if dist < 160.0 else "movel"
	var no: Node3D = _cena(nome, versao).instantiate()
	add_child(no)
	no.position = Vector3(x, altura(x, z) - 0.05, z)
	no.rotation.y = rng.randf() * TAU if giro < 0.0 else giro
	no.scale = Vector3.ONE * escala if escala_v == Vector3.ZERO else escala_v
	# folhas são geometria fina: o LOD automático apagava as copas, então
	# as árvores pedem mais detalhe (mais forte perto da câmera)
	var vies := 1.5 if dist < 160.0 else 1.0
	if movel:
		vies = 1.0 if dist < 80.0 else 0.25
	_definir_lod(no, vies)
	if (movel and dist > 70.0) or (arvore and dist > 160.0):
		_sem_sombra(no)
	if Vector2(x, z).length() > 250.0:
		arvores_longe.append(no)
	if not cache_cena.has(nome + "@" + versao + "_ok"):
		_ajustar_folhas(no, 4.0 if arvore else 1.2)
		cache_cena[nome + "@" + versao + "_ok"] = true
	if absf(x) < LIMITE + 80.0 and absf(z) < LIMITE + 80.0:
		_colidir_planta(no, nome)
	return no


func _sem_sombra(n: Node) -> void:
	if n is GeometryInstance3D:
		(n as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for f in n.get_children():
		_sem_sombra(f)


func _livre(x: float, z: float, folga: float) -> bool:
	var p := Vector2(x, z)
	if p.length() < 18.0 + folga:
		return false
	if distancia_estrada(p) < 10.0 + folga:
		return false
	if _acude_e(x, z) < 1.4:
		return false
	if p.distance_to(GALPAO_C) < 14.0 + folga:
		return false
	return true


func _montar_vegetacao() -> void:
	# árvores de destaque, como na imagem de referência
	_plantar("island_tree_01", -33.0, -20.0, 2.9)
	_plantar("island_tree_02", -72.0, -98.0, 2.7)
	_plantar("island_tree_03", 14.0, -158.0, 3.6)
	_plantar("island_tree_01", 90.0, -58.0, 2.5)
	_plantar("island_tree_02", 142.0, -185.0, 2.9)
	_plantar("tree_small_02", -20.0, -150.0, 2.3)
	_plantar("island_tree_03", 30.0, -105.0, 2.8)

	# fileira de árvores altas ao fundo (lugar do eucaliptal)
	var passo := 6.5 if not qualidade_baixa else 13.0
	var x := -280.0
	while x < -30.0:
		for fila in 2:
			var z := -238.0 - fila * 7.0 + rng.randf_range(-2.0, 2.0)
			# eucalipto: árvore fina e bem alta (o modelo é esticado na vertical)
			var esc := rng.randf_range(2.4, 3.0)
			_plantar("tree_small_02", x + rng.randf_range(-1.5, 1.5) + fila * 3.0, z, esc, -1.0,
				Vector3(esc * 0.75, esc * rng.randf_range(1.9, 2.3), esc * 0.75))
		x += passo

	# árvores espalhadas pelo pasto até o horizonte
	var qtd := 25 if qualidade_baixa else 70
	var feitos := 0
	var tentativas := 0
	while feitos < qtd and tentativas < 2000:
		tentativas += 1
		var ang := rng.randf() * TAU
		var r := rng.randf_range(120.0, 1100.0)
		var px := cos(ang) * r
		var pz := sin(ang) * r
		if pz > 40.0:
			continue
		if not _livre(px, pz, 4.0):
			continue
		var nomes := ["island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02"]
		_plantar(nomes[rng.randi() % 4], px, pz, rng.randf_range(2.2, 3.4))
		feitos += 1

	# arbustos perto das cercas e ao pé das árvores
	for i in (30 if qualidade_baixa else 90):
		var px := rng.randf_range(-130.0, 110.0)
		var pz := rng.randf_range(-200.0, 15.0)
		if not _livre(px, pz, -6.0):
			continue
		var nome := "shrub_02" if rng.randf() < 0.55 else "shrub_04"
		_plantar(nome, px, pz, rng.randf_range(0.9, 1.6) if nome == "shrub_02" else rng.randf_range(1.5, 2.6))
	for i in (8 if qualidade_baixa else 26):
		var px := rng.randf_range(-110.0, 40.0)
		var pz := -33.0 + rng.randf_range(-1.5, 1.5)
		_plantar("shrub_02", px, pz, rng.randf_range(0.8, 1.3))


func _montar_pedras() -> void:
	for i in 22:
		var ang := rng.randf() * TAU
		var r := rng.randf_range(11.0, 45.0)
		var px := cos(ang) * r
		var pz := sin(ang) * r + 4.0
		if not _livre(px, pz, -12.0) and Vector2(px, pz).length() < 5.5:
			continue
		var no := _plantar("boulder_01", px, pz, rng.randf_range(0.35, 0.9))
		no.position.y -= 0.15
	for i in 120:
		var px := rng.randf_range(-40.0, 40.0)
		var pz := rng.randf_range(-40.0, 22.0)
		if Vector2(px, pz).length() < 5.0:
			continue
		var nome := "stone_01" if rng.randf() < 0.5 else "rock_07"
		_plantar(nome, px, pz, rng.randf_range(1.5, 4.0))




# ------------------------------------------------------------------ colisão

func _colisao_terreno() -> void:
	# grade de 2 m cobrindo a área de voo e mais uma folga
	var meia := LIMITE + 60.0
	var passo := 2.0
	var n := int(meia * 2.0 / passo) + 1
	var dados := PackedFloat32Array()
	dados.resize(n * n)
	for j in n:
		var z := -meia + j * passo
		for i in n:
			var x := -meia + i * passo
			dados[j * n + i] = altura(x, z) / passo   # a escala uniforme de 2 volta a altura
	var hm := HeightMapShape3D.new()
	hm.map_width = n
	hm.map_depth = n
	hm.map_data = dados
	var cs := CollisionShape3D.new()
	cs.shape = hm
	cs.scale = Vector3.ONE * passo
	corpo_estatico.add_child(cs)


var _formas_no_corpo := 0


func _add_forma(forma: Shape3D, xf: Transform3D) -> void:
	# o Jolt aceita poucas formas por corpo: abre um corpo novo a cada 128
	if _formas_no_corpo >= 128 or corpo_estatico.get_child_count() == 0 or corpo_estatico.name == "Colisao":
		corpo_estatico = StaticBody3D.new()
		corpo_estatico.name = "Colisao_%d" % get_child_count()
		add_child(corpo_estatico)
		_formas_no_corpo = 0
	var cs := CollisionShape3D.new()
	cs.shape = forma
	cs.transform = xf
	corpo_estatico.add_child(cs)
	_formas_no_corpo += 1


func _col_caixa(tam: Vector3, xf: Transform3D) -> void:
	var b := BoxShape3D.new()
	b.size = tam
	_add_forma(b, xf)


func _col_cilindro(r: float, h: float, xf: Transform3D) -> void:
	var c := CylinderShape3D.new()
	c.radius = r
	c.height = h
	_add_forma(c, xf)


func _col_esfera(r: float, xf: Transform3D) -> void:
	var e := SphereShape3D.new()
	e.radius = r
	_add_forma(e, xf)


## cápsula fina entre dois pontos (fios de cerca e da rede elétrica)
func _col_segmento(p1: Vector3, p2: Vector3, r: float) -> void:
	var d := p2 - p1
	var comp := d.length()
	if comp < 0.01:
		return
	var y := d / comp
	var x := y.cross(Vector3.UP if absf(y.y) < 0.95 else Vector3.RIGHT).normalized()
	var z := x.cross(y).normalized()
	var c := CapsuleShape3D.new()
	c.radius = r
	c.height = comp + 2.0 * r
	_add_forma(c, Transform3D(Basis(x, y, z), (p1 + p2) * 0.5))


var _formas_exatas := {}


## forma de colisão exata (triângulo por triângulo) de cada malha, reaproveitada entre cópias
func _forma_exata(mesh: Mesh) -> Shape3D:
	if not _formas_exatas.has(mesh):
		var f := mesh.create_trimesh_shape()
		if f is ConcavePolygonShape3D:
			(f as ConcavePolygonShape3D).backface_collision = true
		_formas_exatas[mesh] = f
	return _formas_exatas[mesh]


## forma convexa exata de uma malha simples (cilindro afinando, cone): reaproveitada
func _col_convexa(mesh: Mesh, xf: Transform3D) -> void:
	if not _formas_exatas.has(mesh):
		_formas_exatas[mesh] = mesh.create_convex_shape(true, false)
	_add_forma(_formas_exatas[mesh], xf)


func _colidir_filhos_rec(no: Node) -> void:
	# objetos (píer, mesa, tronco caído, barris, caixotes, pedras): o formato de verdade,
	# com os vãos abertos (dá para passar debaixo do píer e da mesa)
	for f in no.get_children():
		if f is MeshInstance3D:
			var mi := f as MeshInstance3D
			_add_forma(_forma_exata(mi.mesh), mi.global_transform)
		_colidir_filhos_rec(f)


## folhas: cada item é [inverso do transform da árvore, dados, caixa no mundo]
## (os dados vêm de recursos/colisao/<nome>.res, gerados por ferramentas/gerar_colisao_arvores.gd)
var _dados_arvore := {}


func _dados_colisao(nome: String) -> ConcavePolygonShape3D:
	if not _dados_arvore.has(nome):
		var caminho := REC + "colisao/%s.res" % nome
		_dados_arvore[nome] = load(caminho) if ResourceLoader.exists(caminho) else null
	return _dados_arvore[nome]


## true se o ponto está encostando numa folha de verdade
func folha_em(p: Vector3) -> bool:
	for f in folhagens:
		var cx: AABB = f[2]
		if not cx.has_point(p):
			continue
		var d: ConcavePolygonShape3D = f[1]
		var local: Vector3 = (f[0] as Transform3D) * p
		var cel: float = d.get_meta("cel")
		var q := Vector3i(((local - (d.get_meta("origem") as Vector3)) / cel).floor())
		var dims: Vector3i = d.get_meta("dims")
		if q.x < 0 or q.y < 0 or q.z < 0 or q.x >= dims.x or q.y >= dims.y or q.z >= dims.z:
			continue
		var chave := q.x + q.y * dims.x + q.z * dims.x * dims.y
		var lista: PackedInt32Array = d.get_meta("folhas")
		var i := lista.bsearch(chave)
		if i < lista.size() and lista[i] == chave:
			return true
	return false


## depuração (--ver-colisao): desenha as células de folha das plantas perto de um ponto
func mostrar_folhas_perto(centro: Vector3, raio: float) -> void:
	var xs: Array[Transform3D] = []
	for f in folhagens:
		var cx: AABB = f[2]
		if cx.get_center().distance_to(centro) > raio:
			continue
		var d: ConcavePolygonShape3D = f[1]
		var inv: Transform3D = f[0]
		var xf := inv.affine_inverse()
		var cel: float = d.get_meta("cel")
		var org: Vector3 = d.get_meta("origem")
		var dims: Vector3i = d.get_meta("dims")
		for chave in (d.get_meta("folhas") as PackedInt32Array):
			var ix := chave % dims.x
			var iy := (chave / dims.x) % dims.y
			var iz := chave / (dims.x * dims.y)
			var local := org + (Vector3(ix, iy, iz) + Vector3.ONE * 0.5) * cel
			xs.append(Transform3D(xf.basis * Basis.from_scale(Vector3.ONE * cel), xf * local))
	var m := _mat_cor(Color(1.0, 0.1, 0.6), 0.8)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color.a = 0.45
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_multimesh(_caixa(Vector3.ONE), m, xs)
	print("células de folha mostradas: ", xs.size())
	# formas de colisão (menos o chão) perto do ponto, em azul
	var mc := _mat_cor(Color(0.1, 0.8, 1.0), 0.8)
	mc.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mc.no_depth_test = true
	var n := 0
	for corpo in get_children():
		if not (corpo is StaticBody3D) or corpo.name == "Colisao":
			continue
		for cs in corpo.get_children():
			var c := cs as CollisionShape3D
			if c == null or c.shape is HeightMapShape3D or c.global_position.distance_to(centro) > raio:
				continue
			var mi := MeshInstance3D.new()
			mi.mesh = c.shape.get_debug_mesh()
			mi.material_override = mc
			add_child(mi)
			mi.global_transform = c.global_transform
			n += 1
	print("formas de colisão mostradas: ", n)


## compatibilidade (desafios: balão não nasce dentro de folha)
func folhagem_em(p: Vector3) -> float:
	return 1.0 if folha_em(p) else 0.0


func _colidir_filhos(no: Node3D) -> void:
	for f in no.get_children():
		if f is MeshInstance3D:
			var mi := f as MeshInstance3D
			_add_forma(mi.mesh.create_convex_shape(true, true), mi.global_transform)


func _caixa_global(no: Node) -> AABB:
	var caixa := AABB()
	var primeiro := true
	var pilha: Array = [no]
	while pilha.size() > 0:
		var n: Node = pilha.pop_back()
		if n is MeshInstance3D:
			var mi := n as MeshInstance3D
			var a := mi.global_transform * mi.get_aabb()
			caixa = a if primeiro else caixa.merge(a)
			primeiro = false
		pilha.append_array(n.get_children())
	return caixa


func _colidir_planta(no: Node3D, nome: String) -> void:
	var c := _caixa_global(no)
	if c.size.y < 0.25:
		return
	var dados := _dados_colisao(nome)
	if dados:
		# tronco e galhos: o formato exato da casca (passa rente ao tronco, debaixo do galho, no meio da forquilha)
		if dados.get_faces().size() > 0:
			_add_forma(dados, no.global_transform)
		# folhas: só encosta onde existe folha de verdade
		var cf: AABB = no.global_transform * (dados.get_meta("caixa_folhas") as AABB)
		folhagens.append([no.global_transform.affine_inverse(), dados, cf.grow(0.05)])
		if nome.contains("tree"):
			obstaculos.append([Vector2(c.get_center().x, c.get_center().z), minf(c.size.x, c.size.z) * 0.4, c.end.y])
	else:
		# pedras: o formato de verdade
		_colidir_filhos_rec(no)


# ------------------------------------------------------------------ consultas do voo

func na_agua(p: Vector3) -> bool:
	return _acude_e(p.x, p.z) < 1.3 and p.y < nivel_agua + 0.03 and altura(p.x, p.z) < nivel_agua


func ponto_partida() -> Vector3:
	return Vector3(0.0, altura_centro + 0.15, 2.0)


## vento na grama e na biruta (direção em radianos, para onde o vento vai)
func aplicar_vento(dir_rad: float, velocidade: float, rajada: float) -> void:
	var d := Vector2(sin(dir_rad), cos(dir_rad))
	var forca_folha := 0.02 + velocidade * 0.03 * (0.7 + 0.6 * rajada)
	for m in mats_folhas:
		m.set_shader_parameter("vento_dir", d)
		m.set_shader_parameter("vento_forca", forca_folha)
	if mat_grama:
		mat_grama.set_shader_parameter("vento_dir", d)
		mat_grama.set_shader_parameter("vento_forca", 0.05 + velocidade * 0.035 * (0.7 + 0.6 * rajada))
	if mat_flores:
		mat_flores.set_shader_parameter("vento_dir", d)
		mat_flores.set_shader_parameter("vento_forca", 0.05 + velocidade * 0.035 * (0.7 + 0.6 * rajada))
	vento_vel = d * maxf(velocidade, 1.0) * (1.0 + 0.4 * rajada)
	if biruta:
		# o eixo X local do pano aponta para onde o vento vai
		biruta.rotation.y = lerp_angle(biruta.rotation.y, atan2(-d.y, d.x), 0.05)
		if biruta_pano:
			var enche := clampf(velocidade / 7.0, 0.0, 1.0)
			biruta_pano.rotation.z = -PI / 2 - lerpf(1.25, 0.06, enche)
			biruta_pano.position = Vector3(1.25 * lerpf(0.25, 1.0, enche), -0.12 - lerpf(1.05, 0.0, enche), 0)


func set_drone_na_grama(p: Vector3, forca: float) -> void:
	if mat_grama:
		mat_grama.set_shader_parameter("drone_pos", p)
		mat_grama.set_shader_parameter("drone_forca", forca)


## nível de gráfico no celular: 0 baixo, 1 médio, 2 alto
func nivel_grafico(n: int) -> void:
	if luz_sol:
		luz_sol.shadow_enabled = n >= 1
	for b in blocos_grama:
		b.visibility_range_end = [18.0, 30.0, 60.0][n]
	for a in arvores_longe:
		a.visible = n >= 1
	if ambiente:
		ambiente.fog_enabled = n >= 1


## qualidade gráfica no PC: 0 baixa, 1 média, 2 alta, 3 ultra
func nivel_grafico_pc(n: int) -> void:
	if ambiente:
		ambiente.sdfgi_enabled = n >= 2      # luz rebatida em tempo real (pesada)
		ambiente.sdfgi_cascades = 6 if n >= 3 else 4
		ambiente.volumetric_fog_enabled = n >= 2
		ambiente.volumetric_fog_density = 0.006 if n >= 3 else 0.0035
		ambiente.ssr_enabled = n >= 2
		ambiente.ssao_enabled = n >= 1
		ambiente.ssil_enabled = n >= 3
		ambiente.glow_enabled = true
	if luz_sol:
		luz_sol.shadow_enabled = true
		luz_sol.directional_shadow_max_distance = [70.0, 140.0, 220.0, 320.0][n]
		luz_sol.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS if n == 0 else DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
		luz_sol.shadow_blur = 1.5 if n >= 3 else 1.0
	for b in blocos_grama:
		b.visibility_range_end = [35.0, 60.0, 95.0, 150.0][n]
	for b in blocos_flores:
		b.visibility_range_end = [30.0, 55.0, 90.0, 120.0][n]
	for a in arvores_longe:
		a.visible = n >= 1
	RenderingServer.global_shader_parameter_set("nuvem_forca", 0.0 if (movel or n == 0) else float(HORAS[hora_atual][5]))


# ------------------------------------------------------------------ hora do dia, nuvens

func definir_hora(i: int) -> void:
	hora_atual = clampi(i, 0, HORAS.size() - 1)
	var h: Array = HORAS[hora_atual]
	if pano_ceu:
		pano_ceu.panorama = load(REC + "ceu/" + h[0])
	if luz_sol:
		var az := deg_to_rad(float(h[1]))
		var el := deg_to_rad(float(h[2]))
		var dir_sol := Vector3(-sin(az) * cos(el), sin(el), cos(az) * cos(el)).normalized()
		luz_sol.global_transform = Transform3D.IDENTITY
		luz_sol.look_at_from_position(Vector3.ZERO, -dir_sol, Vector3.UP)
		luz_sol.light_color = h[3]
		luz_sol.light_energy = h[4]
	if ambiente:
		ambiente.tonemap_exposure = h[6]
		ambiente.fog_light_color = h[7]
		ambiente.volumetric_fog_albedo = Color(h[7]).lerp(Color.WHITE, 0.4)
	RenderingServer.global_shader_parameter_set("nuvem_forca", 0.0 if movel else float(h[5]))


func _iniciar_nuvens() -> void:
	var n := FastNoiseLite.new()
	n.frequency = 0.006
	n.fractal_octaves = 4
	n.seed = 77
	var t := NoiseTexture2D.new()
	t.noise = n
	t.width = 512
	t.height = 512
	t.seamless = true
	t.generate_mipmaps = true
	RenderingServer.global_shader_parameter_set("nuvem_ruido", t)


func _process(delta: float) -> void:
	# as sombras das nuvens andam com o vento (lá em cima venta mais)
	nuvem_desloc -= vento_vel * delta * 2.2
	RenderingServer.global_shader_parameter_set("nuvem_desloc", nuvem_desloc)


# ------------------------------------------------------------------ jacarandás, píer, objetos

func _cena_simples(nome: String) -> Node3D:
	var no: Node3D = _cena(nome, "orig").instantiate()
	add_child(no)
	return no


func _por_no_chao(no: Node3D, x: float, z: float, giro: float, escala := 1.0, afundar := 0.0) -> void:
	no.position = Vector3(x, altura(x, z) - afundar, z)
	no.rotation.y = giro
	no.scale = Vector3.ONE * escala


func _montar_extras() -> void:
	# jacarandás floridos (roxos), perto do galpão e da estrada
	for p in [Vector2(-66, -38), Vector2(-24, -78), Vector2(32, -48), Vector2(-88, -132), Vector2(58, -112)]:
		if _livre(p.x, p.y, 2.0):
			_plantar("jacaranda_tree", p.x, p.y, rng.randf_range(0.95, 1.15))
			jacarandas.append(p)
	# tronco caído no pasto
	var tronco := _cena_simples("dead_tree_trunk_02")
	_por_no_chao(tronco, 16.0, -27.0, 0.7, 1.0, 0.1)
	_colidir_filhos_rec(tronco)
	# píer de madeira no açude, saindo da margem sul para dentro da água
	if not movel:
		var pier := _cena_simples("modular_wooden_pier")
		var cx: float = ACUDE_C.x - 8.0
		var cz: float = ACUDE_C.y + ACUDE_R.y * 0.62
		pier.position = Vector3(cx, nivel_agua + 0.15, cz)
		var cx_box := _caixa_global(pier)
		# deixa o lado comprido apontando para o meio do açude (eixo z)
		if cx_box.size.x > cx_box.size.z:
			pier.rotation.y = PI * 0.5
		var b2 := _caixa_global(pier)
		pier.position.y += (nivel_agua + 0.55) - b2.end.y
		_colidir_filhos_rec(pier)
		var b3 := _caixa_global(pier)
		# ponta do píer (o lado mais dentro do açude)
		var ponta := Vector3(b3.get_center().x, b3.end.y, b3.position.z + 1.2)
		if absf(b3.end.z - ACUDE_C.y) < absf(b3.position.z - ACUDE_C.y):
			ponta.z = b3.end.z - 1.2
		pontos_pouso.append(["ponta do píer", ponta])
	# barris e caixotes encostados no galpão, mesa de piquenique perto da base
	var g := GALPAO_C
	for i in 3:
		var barril := _cena_simples("Barrel_01")
		_por_no_chao(barril, g.x + 9.6 + i * 0.75, g.y + 6.5 + (i % 2) * 0.5, rng.randf() * TAU)
		_colidir_filhos_rec(barril)
	var cx_topo: Node3D = null
	for i in 4:
		var cx2 := _cena_simples("wooden_crate_01")
		cx_topo = cx2
		var alto := 1 if i == 3 else 0
		_por_no_chao(cx2, g.x + 9.5 + (i % 3) * 0.95 - alto * 1.4, g.y - 6.0, rng.randf_range(-0.2, 0.2))
		if alto:
			cx2.position.y += _caixa_global(cx2).size.y * 0.98
		_colidir_filhos_rec(cx2)
	var mesa := _cena_simples("wooden_picnic_table")
	_por_no_chao(mesa, 9.0, 9.0, 0.4)
	_colidir_filhos_rec(mesa)
	var bm := _caixa_global(mesa)
	pontos_pouso.append(["mesa de piquenique", Vector3(bm.get_center().x, bm.end.y, bm.get_center().z)])
	var topo_cx := _caixa_global(cx_topo)
	pontos_pouso.append(["pilha de caixotes", Vector3(topo_cx.get_center().x, topo_cx.end.y, topo_cx.get_center().z)])


# ------------------------------------------------------------------ flores do campo

func _malha_flor() -> ArrayMesh:
	# caule (um quadradinho fino) + cabeça em cruz (dois quadrados): a cor/forma vem do shader
	var v := PackedVector3Array()
	var uv := PackedVector2Array()
	var nrm := PackedVector3Array()
	var idx := PackedInt32Array()
	var w := 0.004
	# caule: uv.x < 0 marca o caule
	for q in [[Vector3(-w, 0, 0), Vector3(w, 0, 0), Vector3(w, 1, 0), Vector3(-w, 1, 0)]]:
		var b := v.size()
		for k in 4:
			v.append(q[k]); nrm.append(Vector3(0, 0, 1))
		uv.append(Vector2(-1, 0)); uv.append(Vector2(-1, 0)); uv.append(Vector2(-1, 1)); uv.append(Vector2(-1, 1))
		idx.append_array([b, b + 1, b + 2, b, b + 2, b + 3])
	var r := 0.11
	for eixo in [Vector3(1, 0, 0), Vector3(0, 0, 1)]:
		var e: Vector3 = eixo
		var b := v.size()
		var up := Vector3(0, 1, 0)
		v.append(Vector3(0, 1, 0) - e * r - up * r * 0.2)
		v.append(Vector3(0, 1, 0) + e * r - up * r * 0.2)
		v.append(Vector3(0, 1, 0) + e * r + up * r * 1.8)
		v.append(Vector3(0, 1, 0) - e * r + up * r * 1.8)
		for k in 4:
			nrm.append(Vector3(0, 1, 0))
		uv.append(Vector2(0, 0)); uv.append(Vector2(1, 0)); uv.append(Vector2(1, 1)); uv.append(Vector2(0, 1))
		idx.append_array([b, b + 1, b + 2, b, b + 2, b + 3])
	# cabeça deitada (vista de cima, que é como o drone vê)
	var b3 := v.size()
	v.append(Vector3(-r, 1.0, -r)); v.append(Vector3(r, 1.0, -r)); v.append(Vector3(r, 1.0, r)); v.append(Vector3(-r, 1.0, r))
	for k in 4:
		nrm.append(Vector3(0, 1, 0))
	uv.append(Vector2(0, 0)); uv.append(Vector2(1, 0)); uv.append(Vector2(1, 1)); uv.append(Vector2(0, 1))
	idx.append_array([b3, b3 + 1, b3 + 2, b3, b3 + 2, b3 + 3])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = v
	arr[Mesh.ARRAY_TEX_UV] = uv
	arr[Mesh.ARRAY_NORMAL] = nrm
	arr[Mesh.ARRAY_INDEX] = idx
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return m


func _montar_flores() -> void:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/flores.gdshader")
	mat_flores = mat
	var malha := _malha_flor()
	var cores := [Color(1.0, 0.82, 0.12), Color(0.97, 0.96, 0.92), Color(0.62, 0.38, 0.86), Color(1.0, 0.55, 0.15), Color(0.95, 0.35, 0.45)]
	var tam := 20.0
	var raio := 40.0 if movel else 120.0
	var por_bloco := 90 if movel else 420
	var bx := -raio
	while bx < raio:
		var bz := -raio - 30.0
		while bz < raio * 0.5:
			var xs: Array[Transform3D] = []
			var cs: Array[Color] = []
			for i in por_bloco:
				var x := bx + rng.randf() * tam
				var z := bz + rng.randf() * tam
				var p := Vector2(x, z)
				if p.length() < 6.0 or p.length() > raio:
					continue
				var mancha := ruido_b.get_noise_2d(x * 0.045 + 100.0, z * 0.045) * 0.5 + 0.5
				if mancha < 0.52 or rng.randf() > (mancha - 0.45) * 2.2:
					continue
				if distancia_estrada(p) < 4.0 or _acude_e(x, z) < 1.2 or p.distance_to(GALPAO_C) < 11.0:
					continue
				var alt := rng.randf_range(0.22, 0.5)
				var bas := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(1.0, alt, 1.0) * rng.randf_range(0.8, 1.25))
				xs.append(Transform3D(bas, Vector3(x, altura(x, z) - 0.02, z)))
				# cor da mancha: cada mancha tende a uma cor
				var ci := int(floor((ruido_c.get_noise_2d(x * 0.02, z * 0.02) * 0.5 + 0.5) * cores.size() * 0.999))
				if rng.randf() < 0.2:
					ci = rng.randi() % cores.size()
				var c: Color = cores[clampi(ci, 0, cores.size() - 1)]
				cs.append(Color(c.r, c.g, c.b, rng.randf()))
			if xs.size() > 0:
				var mm := MultiMesh.new()
				mm.transform_format = MultiMesh.TRANSFORM_3D
				mm.use_custom_data = true
				mm.mesh = malha
				mm.instance_count = xs.size()
				for i in xs.size():
					mm.set_instance_transform(i, xs[i])
					mm.set_instance_custom_data(i, cs[i])
				var mmi := MultiMeshInstance3D.new()
				mmi.multimesh = mm
				mmi.material_override = mat
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				mmi.visibility_range_end = 90.0 if not movel else 35.0
				blocos_flores.append(mmi)
				add_child(mmi)
			bz += tam
		bx += tam
	# tapete de flores roxas caídas embaixo de cada jacarandá
	for j in jacarandas:
		var jp: Vector2 = j
		var xs2: Array[Transform3D] = []
		var cs2: Array[Color] = []
		for i in (900 if not movel else 250):
			var ang := rng.randf() * TAU
			var r := sqrt(rng.randf()) * 6.5
			var x := jp.x + cos(ang) * r
			var z := jp.y + sin(ang) * r
			var bas := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(0.35, 0.012, 0.35) * rng.randf_range(0.7, 1.3))
			xs2.append(Transform3D(bas, Vector3(x, altura(x, z) + 0.005, z)))
			var c := Color(0.55, 0.36, 0.85).lerp(Color(0.68, 0.5, 0.95), rng.randf())
			cs2.append(Color(c.r, c.g, c.b, 0.9))
		var mm2 := MultiMesh.new()
		mm2.transform_format = MultiMesh.TRANSFORM_3D
		mm2.use_custom_data = true
		mm2.mesh = malha
		mm2.instance_count = xs2.size()
		for i in xs2.size():
			mm2.set_instance_transform(i, xs2[i])
			mm2.set_instance_custom_data(i, cs2[i])
		var mmi2 := MultiMeshInstance3D.new()
		mmi2.multimesh = mm2
		mmi2.material_override = mat
		mmi2.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi2.visibility_range_end = 70.0
		blocos_flores.append(mmi2)
		add_child(mmi2)
