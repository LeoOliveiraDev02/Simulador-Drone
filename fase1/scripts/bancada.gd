extends Node3D
## Fase 1 — os drones em cima da bancada.
## Escolha o drone embaixo, gire com o mouse e clique nas peças para ver o que
## cada uma é, o que faz e com o que se conecta. "Vista explodida" separa as peças.
##
## Argumentos depois de "--":  --prints  (tira prints de todos os drones e fecha)
##                            --esperar=N  quadros antes de cada print
##                            --leve       sem sombras suaves/SSIL (máquina sem placa de vídeo)

const ALTURA_BANCADA := 0.9

var dados_drones: Array = []
var dados_pecas := {}
var montador := Drones.new()
var drone_atual: Node3D
var indice := 0
var cache_drones := {}

# câmera orbital
var camera: Camera3D
var alvo := Vector3(0, ALTURA_BANCADA + 0.05, 0)
var alvo_desejado := alvo
var yaw := 0.6
var pitch := -0.35
var dist := 0.8
var dist_desejada := 0.8
var dist_min := 0.1
var dist_max := 4.0
var arrastando := false
var movendo := false
var parado_ha := 0.0

# seleção
var mat_destaque: ShaderMaterial
var mat_selecao: ShaderMaterial
var peca_mouse: Node3D
var peca_sel: Node3D
var explodido := false
var tween_expl: Tween

# interface
var ui: Control
var lbl_titulo: Label
var lbl_cat: Label
var lbl_resumo: Label
var grade_ficha: GridContainer
var painel_peca: PanelContainer
var lbl_peca_nome: Label
var lbl_peca_rotulo: Label
var txt_peca: RichTextLabel
var dica_mouse: Label
var botoes_drone: Array[Button] = []
var btn_explodir: Button

var modo_prints := false
var leve := false
var quadros_espera := 90
var so_drone := ""


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--prints":
			modo_prints = true
		elif a == "--leve":
			leve = true
		elif a == "--exportar":
			var pasta := ProjectSettings.globalize_path("res://modelos/final")
			DirAccess.make_dir_recursive_absolute(pasta)
			var dd: Array = JSON.parse_string(FileAccess.get_file_as_string("res://dados/drones.json"))["drones"]
			for info in dd:
				montador.exportar(info["id"], pasta)
				print("exportado ", info["id"])
			get_tree().quit()
			return
		elif a.begins_with("--so="):
			so_drone = a.split("=")[1]
		elif a == "--cad":
			montador.usar_final = false
		elif a.begins_with("--esperar="):
			quadros_espera = int(a.split("=")[1])
	if leve:
		get_viewport().msaa_3d = Viewport.MSAA_DISABLED
	dados_drones = JSON.parse_string(FileAccess.get_file_as_string("res://dados/drones.json"))["drones"]
	dados_pecas = JSON.parse_string(FileAccess.get_file_as_string("res://dados/pecas.json"))
	mat_destaque = ShaderMaterial.new()
	mat_destaque.shader = load("res://shaders/destaque.gdshader")
	mat_selecao = ShaderMaterial.new()
	mat_selecao.shader = mat_destaque.shader
	mat_selecao.set_shader_parameter("cor", Color(1.0, 0.6, 0.15))
	mat_selecao.set_shader_parameter("forca", 0.8)
	_montar_ambiente()
	_montar_bancada()
	_montar_camera()
	_montar_interface()
	_mostrar_drone(0)
	if modo_prints:
		_tirar_prints()


# ------------------------------------------------------------------ cenário

func _montar_ambiente() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.018, 0.021, 0.028)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.32, 0.36, 0.45)
	env.ambient_light_energy = 0.35
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.1
	env.ssao_enabled = true
	env.ssao_radius = 0.25
	env.ssao_intensity = 2.0
	env.ssao_detail = 1.0
	env.ssil_enabled = not leve
	env.ssil_radius = 1.0
	env.ssr_enabled = not leve
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.glow_bloom = 0.03
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.05
	env.adjustment_saturation = 1.05
	# reflexos suaves de um "estúdio" para metais e carbono
	var ceu := Sky.new()
	var ps := ProceduralSkyMaterial.new()
	ps.sky_top_color = Color(0.06, 0.08, 0.12)
	ps.sky_horizon_color = Color(0.12, 0.14, 0.18)
	ps.ground_bottom_color = Color(0.02, 0.02, 0.025)
	ps.ground_horizon_color = Color(0.08, 0.08, 0.09)
	ps.sun_angle_max = 1.0
	ceu.sky_material = ps
	env.sky = ceu
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	# sonda de reflexo: metais e carbono refletem a bancada e as luzes de verdade
	var sonda := ReflectionProbe.new()
	add_child(sonda)
	sonda.position = Vector3(0, ALTURA_BANCADA + 0.4, 0)
	sonda.size = Vector3(4, 2.5, 3)
	sonda.box_projection = true
	sonda.update_mode = ReflectionProbe.UPDATE_ONCE
	sonda.intensity = 1.0
	sonda.ambient_mode = ReflectionProbe.AMBIENT_DISABLED
	# painel de luz (softbox) que aparece refletido no carbono e nos motores
	var softbox := MeshInstance3D.new()
	var plano := QuadMesh.new()
	plano.size = Vector2(1.2, 0.6)
	softbox.mesh = plano
	var emis := StandardMaterial3D.new()
	emis.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	emis.albedo_color = Color(1.0, 0.97, 0.92) * 1.6
	softbox.material_override = emis
	softbox.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(softbox)
	softbox.look_at_from_position(Vector3(0.4, ALTURA_BANCADA + 1.7, 0.4), Vector3(0, ALTURA_BANCADA, 0), Vector3.UP)
	softbox.rotate_object_local(Vector3.RIGHT, PI)
	# luminária em cima da bancada (luz principal, quente)
	var lum := SpotLight3D.new()
	add_child(lum)
	lum.look_at_from_position(Vector3(0.35, ALTURA_BANCADA + 1.6, 0.55), Vector3(0, ALTURA_BANCADA, 0), Vector3.UP)
	lum.light_energy = 7.0
	lum.light_color = Color(1.0, 0.93, 0.84)
	lum.spot_range = 4.0
	lum.spot_angle = 38.0
	lum.spot_angle_attenuation = 0.8
	lum.shadow_enabled = true
	lum.shadow_blur = 1.5
	lum.light_size = 0.12
	# luz de preenchimento fria
	var fill := DirectionalLight3D.new()
	add_child(fill)
	fill.look_at_from_position(Vector3.ZERO, Vector3(0.6, -0.5, -0.5), Vector3.UP)
	fill.light_energy = 0.35
	fill.light_color = Color(0.7, 0.8, 1.0)
	fill.shadow_enabled = true
	fill.directional_shadow_max_distance = 6.0
	# contraluz azul ao fundo (estilo oficina do Monta PC)
	var azul := OmniLight3D.new()
	add_child(azul)
	azul.position = Vector3(-0.4, ALTURA_BANCADA + 0.5, -1.4)
	azul.light_color = Color(0.25, 0.5, 1.0)
	azul.light_energy = 4.0
	azul.omni_range = 3.5
	var azul2 := OmniLight3D.new()
	add_child(azul2)
	azul2.position = Vector3(1.6, ALTURA_BANCADA + 0.3, -0.8)
	azul2.light_color = Color(0.2, 0.45, 1.0)
	azul2.light_energy = 2.0
	azul2.omni_range = 3.0


func _tex(c: String) -> Texture2D:
	return load(c)


func _montar_bancada() -> void:
	var kit := montador.kit
	var b := Node3D.new()
	b.name = "Bancada"
	add_child(b)
	var madeira := ORMMaterial3D.new()
	madeira.albedo_texture = _tex("res://texturas/dark_wood/diff.jpg")
	madeira.normal_enabled = true
	madeira.normal_texture = _tex("res://texturas/dark_wood/nor_gl.jpg")
	madeira.orm_texture = _tex("res://texturas/dark_wood/arm.jpg")
	madeira.uv1_triplanar = true
	madeira.uv1_scale = Vector3.ONE * 0.8
	madeira.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var metal := ORMMaterial3D.new()
	metal.albedo_color = Color(0.22, 0.23, 0.25)
	metal.albedo_texture = _tex("res://texturas/metal_plate/diff.jpg")
	metal.normal_enabled = true
	metal.normal_texture = _tex("res://texturas/metal_plate/nor_gl.jpg")
	metal.orm_texture = _tex("res://texturas/metal_plate/arm.jpg")
	metal.metallic = 1.0
	metal.uv1_triplanar = true
	metal.uv1_scale = Vector3.ONE * 3.0
	var L := 2.6
	var P := 1.5
	var esp := 0.05
	kit.caixa(b, Vector3(L, esp, P), madeira, Vector3(0, ALTURA_BANCADA - esp / 2, 0))
	# tapete de borracha escuro com marcações (onde o drone fica)
	var tapete := StandardMaterial3D.new()
	tapete.albedo_color = Color(0.022, 0.025, 0.028)
	tapete.roughness = 0.85
	kit.caixa(b, Vector3(1.9, 0.003, 1.15), tapete, Vector3(0, ALTURA_BANCADA + 0.0015, 0.0))
	var linha := StandardMaterial3D.new()
	linha.albedo_color = Color(0.075, 0.09, 0.11)
	linha.roughness = 0.8
	for i in range(-9, 10):
		kit.caixa(b, Vector3(0.0015, 0.0005, 1.12), linha, Vector3(i * 0.1, ALTURA_BANCADA + 0.0032, 0))
	for j in range(-5, 6):
		kit.caixa(b, Vector3(1.87, 0.0005, 0.0015), linha, Vector3(0, ALTURA_BANCADA + 0.0032, j * 0.1))
	# pés e travessas de metal
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			kit.caixa(b, Vector3(0.06, ALTURA_BANCADA - esp, 0.06), metal, Vector3(sx * (L / 2 - 0.1), (ALTURA_BANCADA - esp) / 2, sz * (P / 2 - 0.1)))
	for sz: float in [-1.0, 1.0]:
		kit.caixa(b, Vector3(L - 0.2, 0.05, 0.04), metal, Vector3(0, 0.25, sz * (P / 2 - 0.1)))
	kit.caixa(b, Vector3(L - 0.25, 0.08, 0.03), metal, Vector3(0, ALTURA_BANCADA - esp - 0.04, P / 2 - 0.04))
	# chão (some na escuridão)
	var chao := StandardMaterial3D.new()
	chao.albedo_color = Color(0.03, 0.032, 0.036)
	chao.roughness = 0.7
	kit.caixa(b, Vector3(12, 0.02, 12), chao, Vector3(0, -0.01, 0))


# ------------------------------------------------------------------ drones

func _mostrar_drone(i: int) -> void:
	indice = i
	if drone_atual:
		drone_atual.visible = false
	var info: Dictionary = dados_drones[i]
	var id: String = info["id"]
	if not cache_drones.has(id):
		var d := montador.montar(id)
		add_child(d)
		d.position = Vector3(0, ALTURA_BANCADA + 0.003, 0)
		_criar_colisoes(d)
		cache_drones[id] = d
	drone_atual = cache_drones[id]
	drone_atual.visible = true
	explodido = false
	_aplicar_explosao(false, true)
	_selecionar(null)
	# enquadra a câmera
	var b := _aabb_global(drone_atual)
	var tam := maxf(b.size.x, b.size.z)
	alvo_desejado = b.get_center()
	dist_desejada = tam * 1.25 + 0.05
	dist_min = tam * 0.25
	dist_max = tam * 4.0 + 0.6
	if modo_prints:
		alvo = alvo_desejado
		dist = dist_desejada
	# interface
	lbl_titulo.text = info["nome"]
	lbl_cat.text = info["categoria"]
	lbl_resumo.text = info["resumo"]
	for f in grade_ficha.get_children():
		f.queue_free()
	var ficha: Dictionary = info["ficha"]
	for k in ficha:
		var a := Label.new()
		a.text = k
		a.add_theme_color_override("font_color", Color(0.55, 0.65, 0.78))
		a.add_theme_font_size_override("font_size", 15)
		grade_ficha.add_child(a)
		var v := Label.new()
		v.text = ficha[k]
		v.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		v.custom_minimum_size.x = 230
		v.add_theme_font_size_override("font_size", 15)
		grade_ficha.add_child(v)
	for k in botoes_drone.size():
		botoes_drone[k].button_pressed = (k == i)


func _aabb_global(n: Node3D) -> AABB:
	var r := AABB()
	var primeiro := true
	for f in n.find_children("*", "MeshInstance3D", true, false):
		var mi := f as MeshInstance3D
		var b := mi.global_transform * mi.get_aabb()
		if primeiro:
			r = b
			primeiro = false
		else:
			r = r.merge(b)
	return r


func _criar_colisoes(d: Node3D) -> void:
	for p in d.get_children():
		if not p.has_meta("peca"):
			continue
		for f in p.find_children("*", "MeshInstance3D", true, false):
			var mi := f as MeshInstance3D
			if mi.mesh == null or mi.mesh.get_faces().size() == 0:
				continue
			mi.create_trimesh_collision()


func _aplicar_explosao(ligar: bool, instantaneo := false) -> void:
	if tween_expl:
		tween_expl.kill()
	if not instantaneo:
		tween_expl = create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	for p in drone_atual.get_children():
		if not p.has_meta("peca"):
			continue
		if not p.has_meta("pos_original"):
			p.set_meta("pos_original", p.position)
		var destino: Vector3 = p.get_meta("pos_original")
		if ligar:
			destino += p.get_meta("explodir", Vector3.ZERO)
		if instantaneo:
			p.position = destino
		else:
			tween_expl.tween_property(p, "position", destino, 0.9)
	if btn_explodir:
		btn_explodir.text = "Juntar peças" if ligar else "Vista explodida"


# ------------------------------------------------------------------ câmera e mouse

func _montar_camera() -> void:
	camera = Camera3D.new()
	camera.fov = 40.0
	camera.near = 0.005
	camera.far = 50.0
	add_child(camera)


func _process(delta: float) -> void:
	if camera == null:
		return
	parado_ha += delta
	if not modo_prints and parado_ha > 6.0 and peca_sel == null:
		yaw += delta * 0.12
	alvo = alvo.lerp(alvo_desejado, 1.0 - exp(-delta * 6.0))
	dist = lerpf(dist, dist_desejada, 1.0 - exp(-delta * 8.0))
	pitch = clampf(pitch, -1.45, 0.15)
	var dir := Vector3(sin(yaw) * cos(pitch), -sin(pitch), cos(yaw) * cos(pitch))
	camera.position = alvo + dir * dist
	camera.look_at(alvo, Vector3.UP)
	# hélices paradas, mas dá pra fazer girar depois na Fase 2


func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton:
		var mb := ev as InputEventMouseButton
		parado_ha = 0.0
		if mb.button_index == MOUSE_BUTTON_LEFT:
			if mb.pressed:
				arrastando = true
				set_meta("clique_ini", mb.position)
			else:
				arrastando = false
				var ini: Vector2 = get_meta("clique_ini", mb.position)
				if ini.distance_to(mb.position) < 5.0:
					_selecionar(_peca_sob(mb.position))
		elif mb.button_index == MOUSE_BUTTON_RIGHT or mb.button_index == MOUSE_BUTTON_MIDDLE:
			movendo = mb.pressed
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			dist_desejada = clampf(dist_desejada * 0.88, dist_min, dist_max)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			dist_desejada = clampf(dist_desejada * 1.13, dist_min, dist_max)
	elif ev is InputEventMouseMotion:
		var mm := ev as InputEventMouseMotion
		if arrastando:
			yaw -= mm.relative.x * 0.006
			pitch -= mm.relative.y * 0.006
			parado_ha = 0.0
		elif movendo:
			var dx := camera.global_transform.basis.x * (-mm.relative.x * dist * 0.0012)
			var dy := camera.global_transform.basis.y * (mm.relative.y * dist * 0.0012)
			alvo_desejado += dx + dy
			parado_ha = 0.0
		else:
			_passar_mouse(_peca_sob(mm.position), mm.position)
	elif ev is InputEventKey and ev.pressed and not ev.echo:
		match (ev as InputEventKey).keycode:
			KEY_LEFT: _mostrar_drone((indice + dados_drones.size() - 1) % dados_drones.size())
			KEY_RIGHT: _mostrar_drone((indice + 1) % dados_drones.size())
			KEY_E: _alternar_explosao()
			KEY_ESCAPE: _selecionar(null)
			KEY_F12: _salvar_print("manual_%d" % Time.get_unix_time_from_system())


func _peca_sob(pos: Vector2) -> Node3D:
	var origem := camera.project_ray_origin(pos)
	var fim := origem + camera.project_ray_normal(pos) * 20.0
	var q := PhysicsRayQueryParameters3D.create(origem, fim)
	var res := get_world_3d().direct_space_state.intersect_ray(q)
	if res.is_empty():
		return null
	var n: Node = res["collider"]
	while n and not n.has_meta("peca"):
		n = n.get_parent()
	if n and n.get_parent() == drone_atual:
		return n as Node3D
	return null


func _overlay(p: Node3D, m: Material) -> void:
	if p == null:
		return
	for f in p.find_children("*", "GeometryInstance3D", true, false):
		(f as GeometryInstance3D).material_overlay = m


func _passar_mouse(p: Node3D, pos: Vector2) -> void:
	if p != peca_mouse:
		if peca_mouse and peca_mouse != peca_sel:
			_overlay(peca_mouse, null)
		peca_mouse = p
		if p and p != peca_sel:
			_overlay(p, mat_destaque)
	if p:
		dica_mouse.text = _nome_peca(p)
		dica_mouse.position = pos + Vector2(18, 14)
		dica_mouse.visible = true
		Input.set_default_cursor_shape(Input.CURSOR_POINTING_HAND)
	else:
		dica_mouse.visible = false
		Input.set_default_cursor_shape(Input.CURSOR_ARROW)


func _nome_peca(p: Node3D) -> String:
	var rot: String = p.get_meta("rotulo", "")
	if rot != "":
		return rot
	var info: Dictionary = dados_pecas.get(p.get_meta("peca"), {})
	return info.get("nome", p.get_meta("peca"))


func _selecionar(p: Node3D) -> void:
	if peca_sel:
		_overlay(peca_sel, null)
	peca_sel = p
	if p == null:
		painel_peca.visible = false
		return
	_overlay(p, mat_selecao)
	var chave: String = p.get_meta("peca")
	var info: Dictionary = dados_pecas.get(chave, {})
	lbl_peca_nome.text = info.get("nome", chave)
	var rot: String = p.get_meta("rotulo", "")
	lbl_peca_rotulo.text = rot
	lbl_peca_rotulo.visible = rot != "" and rot != info.get("nome", "")
	var t := ""
	t += "[color=#7fb2ff][b]O que é[/b][/color]\n%s\n\n" % info.get("oque", "")
	t += "[color=#7fb2ff][b]Para que serve[/b][/color]\n%s\n\n" % info.get("funcao", "")
	t += "[color=#7fb2ff][b]Com o que se conecta[/b][/color]\n%s\n\n" % info.get("conecta", "")
	t += "[color=#ffb35c][b]Dica[/b][/color]\n%s" % info.get("dica", "")
	txt_peca.text = t
	painel_peca.visible = true
	# aproxima a câmera da peça
	var b := _aabb_global(p)
	alvo_desejado = b.get_center()
	var tam := maxf(maxf(b.size.x, b.size.y), b.size.z)
	dist_desejada = clampf(tam * 3.2 + 0.04, dist_min, dist_max)


func _alternar_explosao() -> void:
	explodido = not explodido
	_aplicar_explosao(explodido)
	parado_ha = 0.0


# ------------------------------------------------------------------ interface

func _estilo(cor: Color, raio := 10, borda := Color(0.25, 0.32, 0.42, 0.6)) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = cor
	s.set_corner_radius_all(raio)
	s.set_border_width_all(1)
	s.border_color = borda
	s.content_margin_left = 18
	s.content_margin_right = 18
	s.content_margin_top = 14
	s.content_margin_bottom = 14
	return s


func _montar_interface() -> void:
	var cl := CanvasLayer.new()
	add_child(cl)
	ui = Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cl.add_child(ui)

	# cabeçalho
	var topo := Label.new()
	topo.text = "SIMULADOR DE DRONE  ·  Fase 1 — conheça os drones"
	topo.add_theme_font_size_override("font_size", 15)
	topo.add_theme_color_override("font_color", Color(0.5, 0.62, 0.8))
	topo.position = Vector2(28, 20)
	ui.add_child(topo)

	# cartão do drone (esquerda)
	var cartao := PanelContainer.new()
	cartao.add_theme_stylebox_override("panel", _estilo(Color(0.04, 0.05, 0.07, 0.86)))
	cartao.position = Vector2(24, 56)
	cartao.custom_minimum_size = Vector2(400, 0)
	cartao.mouse_filter = Control.MOUSE_FILTER_STOP
	ui.add_child(cartao)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 8)
	cartao.add_child(vb)
	lbl_titulo = Label.new()
	lbl_titulo.add_theme_font_size_override("font_size", 30)
	vb.add_child(lbl_titulo)
	lbl_cat = Label.new()
	lbl_cat.add_theme_font_size_override("font_size", 16)
	lbl_cat.add_theme_color_override("font_color", Color(1.0, 0.62, 0.25))
	vb.add_child(lbl_cat)
	lbl_resumo = Label.new()
	lbl_resumo.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lbl_resumo.custom_minimum_size.x = 360
	lbl_resumo.add_theme_font_size_override("font_size", 15)
	lbl_resumo.add_theme_color_override("font_color", Color(0.8, 0.84, 0.9))
	vb.add_child(lbl_resumo)
	var sep := HSeparator.new()
	vb.add_child(sep)
	grade_ficha = GridContainer.new()
	grade_ficha.columns = 2
	grade_ficha.add_theme_constant_override("h_separation", 14)
	grade_ficha.add_theme_constant_override("v_separation", 4)
	vb.add_child(grade_ficha)

	# painel da peça (direita)
	painel_peca = PanelContainer.new()
	painel_peca.add_theme_stylebox_override("panel", _estilo(Color(0.04, 0.05, 0.07, 0.9), 10, Color(1.0, 0.6, 0.2, 0.55)))
	painel_peca.anchor_left = 1.0
	painel_peca.anchor_right = 1.0
	painel_peca.offset_left = -444
	painel_peca.offset_right = -24
	painel_peca.offset_top = 56
	painel_peca.visible = false
	painel_peca.mouse_filter = Control.MOUSE_FILTER_STOP
	ui.add_child(painel_peca)
	var vp := VBoxContainer.new()
	vp.add_theme_constant_override("separation", 6)
	painel_peca.add_child(vp)
	var linha_topo := HBoxContainer.new()
	vp.add_child(linha_topo)
	lbl_peca_nome = Label.new()
	lbl_peca_nome.add_theme_font_size_override("font_size", 24)
	lbl_peca_nome.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lbl_peca_nome.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	linha_topo.add_child(lbl_peca_nome)
	var fechar := Button.new()
	fechar.text = "✕"
	fechar.flat = true
	fechar.pressed.connect(func(): _selecionar(null))
	linha_topo.add_child(fechar)
	lbl_peca_rotulo = Label.new()
	lbl_peca_rotulo.add_theme_font_size_override("font_size", 15)
	lbl_peca_rotulo.add_theme_color_override("font_color", Color(1.0, 0.65, 0.3))
	lbl_peca_rotulo.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vp.add_child(lbl_peca_rotulo)
	txt_peca = RichTextLabel.new()
	txt_peca.bbcode_enabled = true
	txt_peca.fit_content = true
	txt_peca.scroll_active = false
	txt_peca.custom_minimum_size = Vector2(390, 0)
	txt_peca.add_theme_font_size_override("normal_font_size", 15)
	txt_peca.add_theme_font_size_override("bold_font_size", 15)
	vp.add_child(txt_peca)

	# barra de escolha (embaixo)
	var barra := PanelContainer.new()
	barra.add_theme_stylebox_override("panel", _estilo(Color(0.04, 0.05, 0.07, 0.86), 14))
	barra.anchor_left = 0.5
	barra.anchor_right = 0.5
	barra.anchor_top = 1.0
	barra.anchor_bottom = 1.0
	barra.grow_horizontal = Control.GROW_DIRECTION_BOTH
	barra.grow_vertical = Control.GROW_DIRECTION_BEGIN
	barra.offset_bottom = -22
	barra.mouse_filter = Control.MOUSE_FILTER_STOP
	ui.add_child(barra)
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 10)
	barra.add_child(hb)
	var grupo := ButtonGroup.new()
	for i in dados_drones.size():
		var b := Button.new()
		b.text = dados_drones[i]["nome"]
		b.toggle_mode = true
		b.button_group = grupo
		b.custom_minimum_size = Vector2(190, 46)
		b.add_theme_font_size_override("font_size", 16)
		b.add_theme_stylebox_override("normal", _estilo(Color(0.08, 0.1, 0.14), 8))
		b.add_theme_stylebox_override("hover", _estilo(Color(0.12, 0.16, 0.22), 8))
		b.add_theme_stylebox_override("pressed", _estilo(Color(0.85, 0.42, 0.1), 8, Color(1, 0.7, 0.4)))
		b.pressed.connect(_mostrar_drone.bind(i))
		hb.add_child(b)
		botoes_drone.append(b)
	hb.add_child(VSeparator.new())
	btn_explodir = Button.new()
	btn_explodir.text = "Vista explodida"
	btn_explodir.custom_minimum_size = Vector2(170, 46)
	btn_explodir.add_theme_font_size_override("font_size", 16)
	btn_explodir.add_theme_stylebox_override("normal", _estilo(Color(0.1, 0.2, 0.35), 8))
	btn_explodir.add_theme_stylebox_override("hover", _estilo(Color(0.14, 0.26, 0.45), 8))
	btn_explodir.pressed.connect(_alternar_explosao)
	hb.add_child(btn_explodir)

	# ajuda
	var ajuda := Label.new()
	ajuda.text = "Arrastar: girar   ·   Roda: zoom   ·   Botão direito: mover   ·   Clique numa peça para saber o que ela faz   ·   E: explodir   ·   ← →: trocar drone"
	ajuda.add_theme_font_size_override("font_size", 13)
	ajuda.add_theme_color_override("font_color", Color(0.45, 0.52, 0.62))
	ajuda.anchor_top = 1.0
	ajuda.anchor_bottom = 1.0
	ajuda.anchor_left = 0.5
	ajuda.anchor_right = 0.5
	ajuda.grow_horizontal = Control.GROW_DIRECTION_BOTH
	ajuda.offset_top = -112
	ajuda.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ui.add_child(ajuda)

	dica_mouse = Label.new()
	dica_mouse.add_theme_font_size_override("font_size", 15)
	var sd := _estilo(Color(0.02, 0.03, 0.05, 0.92), 6, Color(0.3, 0.6, 1.0, 0.7))
	sd.content_margin_left = 10
	sd.content_margin_right = 10
	sd.content_margin_top = 5
	sd.content_margin_bottom = 5
	dica_mouse.add_theme_stylebox_override("normal", sd)
	dica_mouse.visible = false
	dica_mouse.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(dica_mouse)
	if modo_prints:
		ajuda.visible = false


# ------------------------------------------------------------------ prints

func _salvar_print(nome: String) -> void:
	var pasta := ProjectSettings.globalize_path("res://prints")
	DirAccess.make_dir_recursive_absolute(pasta)
	var img := get_viewport().get_texture().get_image()
	img.save_png(pasta.path_join(nome + ".png"))
	print("Print salvo: ", nome)


func _esperar(q: int) -> void:
	for f in q:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw


func _tirar_prints() -> void:
	for i in dados_drones.size():
		if so_drone != "" and dados_drones[i]["id"] != so_drone:
			continue
		_mostrar_drone(i)
		yaw = 0.75
		pitch = -0.42
		await _esperar(quadros_espera)
		_salvar_print("%d_%s" % [i + 1, dados_drones[i]["id"]])
		# vista explodida
		explodido = true
		_aplicar_explosao(true, true)
		dist = dist_desejada * 1.25
		dist_desejada = dist
		await _esperar(maxi(quadros_espera / 2, 3))
		_salvar_print("%d_%s_explodido" % [i + 1, dados_drones[i]["id"]])
		explodido = false
		_aplicar_explosao(false, true)
	# exemplo de peça selecionada
	_mostrar_drone(0)
	var motores := drone_atual.get_children().filter(func(n): return n.get_meta("peca", "") == "pixhawk")
	if motores.size() > 0:
		_selecionar(motores[0])
		alvo = alvo_desejado
		dist = dist_desejada
		yaw = 0.5
		pitch = -0.6
		await _esperar(quadros_espera)
		_salvar_print("5_peca_selecionada")
	get_tree().quit()
