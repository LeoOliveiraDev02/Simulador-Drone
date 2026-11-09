extends Node3D
## Cena de teste gráfico do Simulador de Drone.
## Monta o campo aberto inteiro por código: terreno, pasto, estrada, açude,
## base de pouso, galpão, cercas, postes, biruta, portais, árvores e um drone.
##
## Argumentos (depois de "--" na linha de comando):
##   --prints            tira os prints das 3 vistas e fecha
##   --esperar=N         quadros de espera antes de cada print (padrão 120)
##   --qualidade=baixa   menos grama/árvores e sem SDFGI (para máquina fraca)
##
## Controles: botão direito + mouse olha, WASD/QE anda, Shift corre,
## 1/2/3 trocam de vista, F12 tira print.

const REC := "res://recursos/"

var qualidade_baixa := false
var modo_prints := false
var quadros_espera := 120

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

var camera: Camera3D
var vistas: Array = []
var vista_atual := 0
var olhando := false
var yaw := 0.0
var pitch := 0.0
var drone: Node3D
var helices: Array = []
var biruta: Node3D

var cache_mat := {}
var cache_cena := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--prints":
			modo_prints = true
		elif a.begins_with("--esperar="):
			quadros_espera = int(a.split("=")[1])
		elif a == "--qualidade=baixa":
			qualidade_baixa = true

	rng.seed = 2026
	if qualidade_baixa:
		# prévia em máquina sem placa de vídeo: sem MSAA e com menos detalhe
		get_viewport().msaa_3d = Viewport.MSAA_DISABLED
		get_viewport().use_taa = false
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
	nivel_agua = _altura_bruta(ACUDE_C.x, ACUDE_C.y) - 0.9

	var t0 := Time.get_ticks_msec()
	_montar_ambiente()
	_montar_terreno()
	_montar_agua()
	_montar_grama()
	_montar_base_pouso()
	_montar_biruta()
	_montar_galpao()
	_montar_cercas()
	_montar_postes()
	_montar_portais()
	_montar_vegetacao()
	_montar_pedras()
	_montar_drone()
	_montar_camera()
	print("Cena montada em %d ms" % (Time.get_ticks_msec() - t0))

	if modo_prints:
		_tirar_prints()


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
	var b := 1.0 - smoothstep(9.3, 12.5, d)
	b = maxf(b, 1.0 - smoothstep(9.0, 15.0, Vector2(x, z).distance_to(GALPAO_C)))
	return Color(r, g, b, 1.0)


# ------------------------------------------------------------------ ambiente

func _montar_ambiente() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var ceu := Sky.new()
	var pano := PanoramaSkyMaterial.new()
	pano.panorama = load(REC + "ceu/farm_field_puresky.hdr")
	pano.energy_multiplier = 1.0
	ceu.sky_material = pano
	ceu.radiance_size = Sky.RADIANCE_SIZE_512
	env.sky = ceu
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY

	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.05

	env.ssao_enabled = true
	env.ssao_radius = 1.4
	env.ssao_intensity = 1.8
	env.ssil_enabled = not qualidade_baixa
	env.ssr_enabled = true
	env.ssr_max_steps = 96

	env.sdfgi_enabled = not qualidade_baixa
	env.sdfgi_use_occlusion = true
	env.sdfgi_cascades = 6
	env.sdfgi_min_cell_size = 0.25
	env.sdfgi_y_scale = Environment.SDFGI_Y_SCALE_75_PERCENT

	env.glow_enabled = true
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
	sol.directional_shadow_max_distance = 420.0
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
	_malha(disco, sm, Vector3(ACUDE_C.x, nivel_agua, ACUDE_C.y), Vector3.ZERO, Vector3(ACUDE_R.x * 1.05, 1.0, ACUDE_R.y * 1.05))


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
	var folha := _malha_folha()
	# grama em blocos de 20 x 20 m para o motor descartar o que está fora da tela
	var tam_bloco := 20.0
	var raio := 70.0 if qualidade_baixa else 150.0
	var dens_max := 18.0 if qualidade_baixa else 70.0
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
				if p.length() < 9.4:
					continue
				if distancia_estrada(p) < 3.6 + rng.randf() * 1.2:
					continue
				if _acude_e(x, z) < 1.05:
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
				mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if dist > 60.0 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
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
	_malha(_cilindro(9.0, 9.15, 0.4, 96), sm, Vector3(0, altura_centro - 0.08, 0))


func _montar_biruta() -> void:
	var x := -15.0
	var z := 3.0
	var y := altura(x, z)
	var metal := _mat_cor(Color(0.72, 0.72, 0.7), 0.45, 0.8)
	_malha(_cilindro(0.045, 0.06, 6.2, 12), metal, Vector3(x, y + 3.1, z))
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
				if anterior != Vector3.INF:
					for alt: float in [0.45, 0.85, 1.2]:
						var p1: Vector3 = anterior + Vector3(0, alt, 0)
						var p2: Vector3 = topo + Vector3(0, alt, 0)
						tf.append(_segmento(p1, p2, 1.0))
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
		_malha(aro, laranja, Vector3(p.x, y + 2.35, p.y), Vector3(PI / 2, deg_to_rad(8), 0))
		for s: float in [-1.0, 1.0]:
			_malha(_caixa(Vector3(0.9, 0.12, 0.25)), preto, Vector3(p.x + s * 0.75, y + 0.06, p.y))


# ------------------------------------------------------------------ árvores, arbustos e pedras

func _cena(nome: String) -> PackedScene:
	if cache_cena.has(nome):
		return cache_cena[nome]
	var c: PackedScene = load(REC + "modelos/%s/%s_1k.gltf" % [nome, nome])
	cache_cena[nome] = c
	return c


func _ajustar_folhas(n: Node) -> void:
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s)
			if m is BaseMaterial3D:
				var bm := m as BaseMaterial3D
				if bm.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
					bm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
					bm.alpha_scissor_threshold = 0.3
					bm.alpha_antialiasing_mode = BaseMaterial3D.ALPHA_ANTIALIASING_ALPHA_TO_COVERAGE
					bm.cull_mode = BaseMaterial3D.CULL_DISABLED
					bm.backlight_enabled = true
					bm.backlight = Color(0.22, 0.28, 0.1)
	for f in n.get_children():
		_ajustar_folhas(f)


func _definir_lod(n: Node, vies: float) -> void:
	if n is GeometryInstance3D:
		(n as GeometryInstance3D).lod_bias = vies
	for f in n.get_children():
		_definir_lod(f, vies)


func _plantar(nome: String, x: float, z: float, escala: float, giro := -1.0) -> Node3D:
	var no: Node3D = _cena(nome).instantiate()
	add_child(no)
	no.position = Vector3(x, altura(x, z) - 0.05, z)
	no.rotation.y = rng.randf() * TAU if giro < 0.0 else giro
	no.scale = Vector3.ONE * escala
	# folhas são geometria fina: o LOD automático apagava as copas, então
	# as árvores pedem mais detalhe (mais forte perto da câmera)
	var vies := 8.0 if Vector2(x, z).length() < 200.0 else 3.0
	_definir_lod(no, vies)
	if not cache_cena.has(nome + "_ok"):
		_ajustar_folhas(no)
		cache_cena[nome + "_ok"] = true
	return no


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
			var nome := "tree_small_02" if rng.randf() < 0.6 else "island_tree_03"
			_plantar(nome, x + rng.randf_range(-1.5, 1.5) + fila * 3.0, z, rng.randf_range(2.8, 3.5))
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
		if not _livre(px, pz, -12.0) and Vector2(px, pz).length() < 10.5:
			continue
		var no := _plantar("boulder_01", px, pz, rng.randf_range(0.35, 0.9))
		no.position.y -= 0.15
	for i in 120:
		var px := rng.randf_range(-40.0, 40.0)
		var pz := rng.randf_range(-40.0, 22.0)
		if Vector2(px, pz).length() < 9.6:
			continue
		var nome := "stone_01" if rng.randf() < 0.5 else "rock_07"
		_plantar(nome, px, pz, rng.randf_range(1.5, 4.0))


# ------------------------------------------------------------------ drone

func _montar_drone() -> void:
	drone = Node3D.new()
	add_child(drone)
	drone.position = Vector3(0.6, altura_centro + 3.0, 1.0)
	drone.rotation = Vector3(deg_to_rad(-4), deg_to_rad(20), deg_to_rad(2))
	drone.scale = Vector3.ONE * 2.8
	var laranja := _mat_cor(Color(0.95, 0.38, 0.06), 0.35)
	laranja.clearcoat_enabled = true
	laranja.clearcoat = 0.4
	var carbono := _mat_cor(Color(0.05, 0.05, 0.055), 0.4, 0.2)
	var metal := _mat_cor(Color(0.25, 0.25, 0.27), 0.3, 0.9)
	var helice := _mat_cor(Color(0.05, 0.05, 0.05, 0.35), 0.4)
	helice.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	helice.cull_mode = BaseMaterial3D.CULL_DISABLED

	_filho(drone, _caixa(Vector3(0.2, 0.07, 0.3)), laranja, Vector3(0, 0, 0))
	_filho(drone, _caixa(Vector3(0.17, 0.035, 0.24)), carbono, Vector3(0, 0.05, -0.01))
	_filho(drone, _caixa(Vector3(0.12, 0.05, 0.08)), carbono, Vector3(0, -0.055, 0.02))
	for k in 4:
		var ang := PI / 4 + k * PI / 2
		var dirv := Vector3(sin(ang), 0, cos(ang))
		var braco := _filho(drone, _caixa(Vector3(0.028, 0.026, 0.34)), carbono, dirv * 0.2, Vector3(0, ang, 0))
		braco.position.y = 0.01
		var ponta := dirv * 0.36
		_filho(drone, _cilindro(0.032, 0.032, 0.045, 18), metal, ponta + Vector3(0, 0.03, 0))
		_filho(drone, _cilindro(0.034, 0.034, 0.02, 18), laranja, ponta + Vector3(0, 0.0, 0))
		var h := _filho(drone, _cilindro(0.19, 0.19, 0.003, 40), helice, ponta + Vector3(0, 0.06, 0))
		helices.append(h)
		_filho(drone, _caixa(Vector3(0.012, 0.004, 0.36)), carbono, ponta + Vector3(0, 0.062, 0), Vector3(0, ang + k, 0))
	# trem de pouso
	for s: float in [-1.0, 1.0]:
		_filho(drone, _caixa(Vector3(0.012, 0.13, 0.012)), carbono, Vector3(s * 0.08, -0.1, 0.07), Vector3(0, 0, s * 0.25))
		_filho(drone, _caixa(Vector3(0.012, 0.13, 0.012)), carbono, Vector3(s * 0.08, -0.1, -0.07), Vector3(0, 0, s * 0.25))
		_filho(drone, _caixa(Vector3(0.016, 0.016, 0.26)), carbono, Vector3(s * 0.11, -0.16, 0))
	# câmera no gimbal
	_filho(drone, _caixa(Vector3(0.05, 0.04, 0.04)), metal, Vector3(0, -0.08, 0.14))
	var lente := SphereMesh.new()
	lente.radius = 0.016
	lente.height = 0.032
	_filho(drone, lente, _mat_cor(Color(0.02, 0.03, 0.05), 0.05, 0.5), Vector3(0, -0.08, 0.16))
	# antena GPS
	_filho(drone, _cilindro(0.004, 0.004, 0.08, 6), carbono, Vector3(0, 0.1, -0.08))
	_filho(drone, _cilindro(0.025, 0.025, 0.012, 16), _mat_cor(Color(0.9, 0.9, 0.9), 0.4), Vector3(0, 0.14, -0.08))


# ------------------------------------------------------------------ câmera, controles e prints

func _montar_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 58.0
	camera.near = 0.05
	camera.far = 9000.0
	add_child(camera)
	vistas = [
		["vista_base", Vector3(0, altura_centro + 8.5, 25.0), Vector3(0, altura_centro + 1.5, -40.0)],
		["vista_alta", Vector3(70, altura_centro + 55.0, 75.0), Vector3(-15, altura_centro, -90.0)],
		["vista_drone", Vector3(3.8, altura_centro + 3.6, 5.2), Vector3(0.4, altura_centro + 2.9, 0.6)],
	]
	_ir_para_vista(0)
	var rotulo := Label.new()
	rotulo.text = "Botão direito + mouse: olhar | WASD/QE: andar | Shift: correr | 1/2/3: vistas | F12: print"
	rotulo.position = Vector2(16, 12)
	rotulo.add_theme_color_override("font_shadow_color", Color.BLACK)
	rotulo.visible = not modo_prints
	var cl := CanvasLayer.new()
	add_child(cl)
	cl.add_child(rotulo)


func _ir_para_vista(i: int) -> void:
	vista_atual = i
	var v: Array = vistas[i]
	camera.look_at_from_position(v[1], v[2], Vector3.UP)
	yaw = camera.rotation.y
	pitch = camera.rotation.x


func _process(delta: float) -> void:
	for h in helices:
		h.rotate_y(delta * 60.0)
	if drone:
		drone.position.y = altura_centro + 3.0 + sin(Time.get_ticks_msec() * 0.0015) * 0.04
	if biruta:
		biruta.rotation.y = deg_to_rad(-25) + sin(Time.get_ticks_msec() * 0.0009) * 0.08
	if modo_prints:
		return
	var vel := 25.0 if Input.is_key_pressed(KEY_SHIFT) else 6.0
	var mov := Vector3.ZERO
	if Input.is_key_pressed(KEY_W): mov.z -= 1
	if Input.is_key_pressed(KEY_S): mov.z += 1
	if Input.is_key_pressed(KEY_A): mov.x -= 1
	if Input.is_key_pressed(KEY_D): mov.x += 1
	if Input.is_key_pressed(KEY_E): mov.y += 1
	if Input.is_key_pressed(KEY_Q): mov.y -= 1
	if mov != Vector3.ZERO:
		camera.translate(mov.normalized() * vel * delta)


func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton and ev.button_index == MOUSE_BUTTON_RIGHT:
		olhando = ev.pressed
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if olhando else Input.MOUSE_MODE_VISIBLE
	elif ev is InputEventMouseMotion and olhando:
		yaw -= ev.relative.x * 0.003
		pitch = clampf(pitch - ev.relative.y * 0.003, -1.5, 1.5)
		camera.rotation = Vector3(pitch, yaw, 0)
	elif ev is InputEventKey and ev.pressed and not ev.echo:
		match ev.keycode:
			KEY_1: _ir_para_vista(0)
			KEY_2: _ir_para_vista(1)
			KEY_3: _ir_para_vista(2)
			KEY_F12: _salvar_print("manual_%d" % Time.get_unix_time_from_system())


func _salvar_print(nome: String) -> void:
	var pasta := ProjectSettings.globalize_path("res://prints")
	DirAccess.make_dir_recursive_absolute(pasta)
	var img := get_viewport().get_texture().get_image()
	var caminho := pasta.path_join(nome + ".png")
	img.save_png(caminho)
	print("Print salvo: ", caminho)


func _tirar_prints() -> void:
	for i in vistas.size():
		_ir_para_vista(i)
		for f in quadros_espera:
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		_salvar_print(vistas[i][0])
	get_tree().quit()
