extends Node3D
## Voo do E88: monta o mapa, o vento, o drone, a câmera e o painel; lê o controle.
##
## Argumentos (depois de "--"):
##   --qualidade=baixa   menos grama/árvores e sem efeitos pesados (PC fraco)
##   --teste-voo         voo automático sem tela, imprime os números (para testar a física)
##   --prints            tira prints do voo e fecha

const ZONA_MORTA := 0.08

var mapa: Mapa
var vento: Vento
var drone: E88
var camera: CameraSegue
var hud: Hud
var qualidade_baixa := false
var modo_teste := false
var modo_prints := false
var teclado_vel := {"acel": 0.0, "yaw": 0.0, "pitch": 0.0, "roll": 0.0}
var segurando_armar := 0.0
var pausado_ajuda := false
var lado_portal: Array[float] = []
var portais_feitos := 0
var tempo_volta := -1.0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--qualidade=baixa":
			qualidade_baixa = true
		elif a == "--teste-voo":
			modo_teste = true
		elif a == "--prints":
			modo_prints = true
		elif a == "--previa":
			qualidade_baixa = true
	if qualidade_baixa:
		get_viewport().msaa_3d = Viewport.MSAA_DISABLED
		get_viewport().use_taa = false

	mapa = Mapa.new()
	mapa.name = "Mapa"
	mapa.previa = "--previa" in OS.get_cmdline_user_args()
	add_child(mapa)
	mapa.montar(qualidade_baixa or modo_teste)

	vento = Vento.new()
	vento.name = "Vento"
	add_child(vento)

	drone = E88.new()
	drone.name = "E88"
	add_child(drone)
	drone.preparar(load("res://drone/e88.glb"))
	drone.mapa = mapa
	drone.vento = vento
	drone.recomecar(mapa.ponto_partida(), 0.0)
	if not modo_teste:
		var som := SomMotor.new()
		som.drone = drone
		drone.add_child(som)
		drone.bateu.connect(som.impacto)
		drone.bateu.connect(_bateu)
		var poeira := Poeira.new()
		poeira.drone = drone
		poeira.mapa = mapa
		add_child(poeira)

	camera = CameraSegue.new()
	add_child(camera)
	camera.alvo = drone
	camera.current = true
	camera.posicionar_ja()

	hud = Hud.new()
	add_child(hud)
	drone.mensagem.connect(hud.mostrar)
	drone.helice_quebrou.connect(func(_k): _vibrar(0.9, 0.5))
	hud.mostrar("Aperte A (ou Espaço) para decolar  •  Start/H: ajuda", 6.0)

	if modo_teste:
		_teste_voo()
	elif modo_prints:
		_tirar_prints()


# ---------------------------------------------------------------- entrada

func _eixo(dev: int, eixo: JoyAxis) -> float:
	var v := Input.get_joy_axis(dev, eixo)
	if absf(v) < ZONA_MORTA:
		return 0.0
	return signf(v) * (absf(v) - ZONA_MORTA) / (1.0 - ZONA_MORTA)


func _expo(v: float, e: float) -> float:
	return v * (1.0 - e) + v * v * v * e


func _rampa(nome: String, alvo: float, delta: float) -> float:
	# tecla vira um movimento suave (não liga 100% de uma vez)
	teclado_vel[nome] = move_toward(teclado_vel[nome], alvo, delta * 3.5)
	return teclado_vel[nome]


func _ler_controles(delta: float) -> void:
	var acel := 0.0
	var yaw := 0.0
	var pitch := 0.0
	var roll := 0.0
	var pads := Input.get_connected_joypads()
	if pads.size() > 0:
		var d: int = pads[0]
		acel = -_eixo(d, JOY_AXIS_LEFT_Y)
		yaw = _eixo(d, JOY_AXIS_LEFT_X)
		pitch = -_eixo(d, JOY_AXIS_RIGHT_Y)
		roll = _eixo(d, JOY_AXIS_RIGHT_X)
	var k_acel := float(Input.is_key_pressed(KEY_W)) - float(Input.is_key_pressed(KEY_S))
	var k_yaw := float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))
	var k_pitch := float(Input.is_key_pressed(KEY_UP)) - float(Input.is_key_pressed(KEY_DOWN))
	var k_roll := float(Input.is_key_pressed(KEY_RIGHT)) - float(Input.is_key_pressed(KEY_LEFT))
	acel = clampf(acel + _rampa("acel", k_acel, delta), -1.0, 1.0)
	yaw = clampf(yaw + _rampa("yaw", k_yaw, delta), -1.0, 1.0)
	pitch = clampf(pitch + _rampa("pitch", k_pitch * 0.8, delta), -1.0, 1.0)
	roll = clampf(roll + _rampa("roll", k_roll * 0.8, delta), -1.0, 1.0)
	var acro := drone.modo == E88.Modo.ACRO
	drone.e_acel = acel
	drone.e_yaw = _expo(yaw, 0.25)
	drone.e_pitch = _expo(pitch, 0.45 if acro else 0.2)
	drone.e_roll = _expo(roll, 0.45 if acro else 0.2)
	# armar empurrando o acelerador (como no E88 real) se estiver no chão
	if not drone.armado and drone.estado == "pousado" and acel > 0.6:
		segurando_armar += delta
		if segurando_armar > 0.35:
			drone.armar()
			drone.estado = "voando"
			drone.altura_ref = drone.global_position.y + 0.4
	else:
		segurando_armar = 0.0


func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventJoypadButton and ev.pressed:
		match ev.button_index:
			JOY_BUTTON_A: drone.decolar_ou_pousar()
			JOY_BUTTON_Y: drone.trocar_modo()
			JOY_BUTTON_X: _recomecar()
			JOY_BUTTON_B: _emergencia()
			JOY_BUTTON_START, JOY_BUTTON_BACK: _ajuda()
			JOY_BUTTON_DPAD_UP: _vento(1.0)
			JOY_BUTTON_DPAD_DOWN: _vento(-1.0)
			JOY_BUTTON_DPAD_LEFT: camera.afastar(-0.3)
			JOY_BUTTON_DPAD_RIGHT: camera.afastar(0.3)
			JOY_BUTTON_LEFT_SHOULDER: _rajadas()
			JOY_BUTTON_RIGHT_SHOULDER: _girar_vento()
	elif ev is InputEventKey and ev.pressed and not ev.echo:
		match ev.keycode:
			KEY_SPACE: drone.decolar_ou_pousar()
			KEY_M: drone.trocar_modo()
			KEY_R: _recomecar()
			KEY_B: _emergencia()
			KEY_H, KEY_F1: _ajuda()
			KEY_EQUAL, KEY_KP_ADD: _vento(1.0)
			KEY_MINUS, KEY_KP_SUBTRACT: _vento(-1.0)
			KEY_PAGEUP: camera.afastar(-0.3)
			KEY_PAGEDOWN: camera.afastar(0.3)
			KEY_G: _rajadas()
			KEY_V: _girar_vento()
			KEY_F12: _salvar_print("print_%d" % Time.get_unix_time_from_system())
			KEY_ESCAPE: get_tree().quit()


func _bateu(v: float) -> void:
	if v > 1.5:
		_vibrar(clampf(v / 4.0, 0.2, 1.0), 0.25)


func _vibrar(forte: float, segundos: float) -> void:
	for d in Input.get_connected_joypads():
		Input.start_joy_vibration(d, forte * 0.6, forte, segundos)


func _recomecar() -> void:
	portais_feitos = 0
	tempo_volta = -1.0
	drone.recomecar(mapa.ponto_partida(), 0.0)
	camera.posicionar_ja()
	hud.mostrar("De volta na base. A (ou Espaço) decola", 3.0)


func _emergencia() -> void:
	if drone.armado:
		drone.armado = false
		if drone.estado != "caido":
			drone.estado = "voando"
		hud.mostrar("Motores desligados (emergência)", 2.0)


func _ajuda() -> void:
	hud.ajuda.visible = not hud.ajuda.visible


func _vento(d: float) -> void:
	vento.velocidade = clampf(vento.velocidade + d, 0.0, 10.0)
	hud.mostrar("Vento: " + vento.texto(), 1.5)


func _rajadas() -> void:
	vento.rajadas = not vento.rajadas
	hud.mostrar("Rajadas " + ("ligadas" if vento.rajadas else "desligadas"), 1.5)


func _girar_vento() -> void:
	vento.direcao = fmod(vento.direcao + deg_to_rad(45), TAU)
	hud.mostrar("Direção do vento mudou", 1.5)


# ---------------------------------------------------------------- quadro a quadro

func _physics_process(delta: float) -> void:
	if not modo_teste:
		_ler_controles(delta)
	var p := drone.global_position
	# vento das hélices no capim (quanto mais força e mais baixo, mais deita)
	var forca := 0.0
	if drone.armado:
		var soma := 0.0
		for e in drone.empuxo:
			soma += e
		forca = clampf(soma / (E88.MASSA * E88.G), 0.0, 1.6) * 0.55
	mapa.set_drone_na_grama(p, forca)
	_checar_portais(p, delta)
	# limite da área de voo: depois de 60 m além do limite o drone volta pousando
	var dist := Vector2(p.x, p.z).length()
	if dist > Mapa.LIMITE + 60.0 and drone.armado and drone.estado != "pousando":
		drone.estado = "pousando"
		hud.mostrar("Sinal perdido: pousando sozinho", 4.0)


func _process(_delta: float) -> void:
	if hud and camera and drone:
		var p := drone.global_position
		var dist := Vector2(p.x, p.z).length()
		var nome := "Controle: " + Input.get_joy_name(Input.get_connected_joypads()[0]) if Input.get_connected_joypads().size() > 0 else "Sem controle conectado — usando o teclado"
		hud.atualizar(drone, vento, camera, nome, dist, Mapa.LIMITE)
		mapa.aplicar_vento(vento.direcao, vento.velocidade, vento.rajada_atual)


func _checar_portais(p: Vector3, delta: float) -> void:
	if tempo_volta >= 0.0:
		tempo_volta += delta
	if lado_portal.size() != mapa.portais.size():
		lado_portal.clear()
		for pt in mapa.portais:
			lado_portal.append(0.0)
	for i in mapa.portais.size():
		var c: Vector3 = mapa.portais[i][0]
		var n: Vector3 = mapa.portais[i][1]
		var d := (p - c).dot(n)
		var no_plano := (p - c) - n * d
		if lado_portal[i] != 0.0 and signf(d) != signf(lado_portal[i]) and no_plano.length() < 2.0 and drone.estado != "caido":
			portais_feitos += 1
			if tempo_volta < 0.0:
				tempo_volta = 0.0
				hud.mostrar("Passou pelo portal %d! Cronômetro ligado" % (i + 1), 2.5)
			else:
				hud.mostrar("Passou pelo portal %d!  (%d portais em %.1f s)" % [i + 1, portais_feitos, tempo_volta], 2.5)
		lado_portal[i] = d if absf(d) > 0.01 else lado_portal[i]


# ---------------------------------------------------------------- testes e prints

func _esperar(s: float) -> void:
	await get_tree().create_timer(s, true, true).timeout


func _log(rotulo: String) -> void:
	var p := drone.global_position
	var v := drone.linear_velocity
	var h := p.y - 0.026 - drone.chao_y
	var ang := rad_to_deg(acos(clampf(drone.global_transform.basis.y.y, -1, 1)))
	print("%-28s h=%.2f m  v=(%.2f, %.2f, %.2f)  inclinação=%.1f°  estado=%s  empuxo=%s  hélices=%s" % [
		rotulo, h, v.x, v.y, v.z, ang, drone.estado,
		str(drone.empuxo.map(func(x): return snappedf(x, 0.01))), str(drone.helice_ok)])


func _teste_voo() -> void:
	vento.velocidade = 0.0
	await _esperar(0.5)
	_log("parado no chão")
	drone.decolar_ou_pousar()
	for i in 6:
		await _esperar(0.5)
		_log("decolando %.1fs" % ((i + 1) * 0.5))
	drone.e_pitch = 1.0
	for i in 6:
		await _esperar(0.5)
		_log("frente total %.1fs" % ((i + 1) * 0.5))
	drone.e_pitch = 0.0
	for i in 5:
		await _esperar(0.5)
		_log("soltou (freando) %.1fs" % ((i + 1) * 0.5))
	drone.e_yaw = 1.0
	await _esperar(1.0)
	_log("girando 1s")
	print("   giro yaw (°/s): ", rad_to_deg(drone.angular_velocity.y))
	drone.e_yaw = 0.0
	drone.e_acel = 1.0
	await _esperar(1.5)
	_log("subindo 1,5s")
	drone.e_acel = 0.0
	await _esperar(1.5)
	_log("altura travada")
	vento.velocidade = 6.0
	for i in 4:
		await _esperar(1.0)
		_log("vento 6 m/s %ds" % (i + 1))
	vento.velocidade = 0.0
	drone.trocar_modo()
	drone.e_roll = 0.5
	await _esperar(0.3)
	_log("acro rolando")
	drone.e_roll = 0.0
	await _esperar(0.5)
	_log("acro solto")
	drone.trocar_modo()
	await _esperar(2.0)
	_log("estabilizado de novo")
	drone.decolar_ou_pousar()
	for i in 8:
		await _esperar(1.0)
		_log("pousando %ds" % (i + 1))
	# batida: voa rápido contra o galpão
	drone.recomecar(Vector3(Mapa.GALPAO_C.x + 0.0, mapa.altura(Mapa.GALPAO_C.x, Mapa.GALPAO_C.y) + 1.5, Mapa.GALPAO_C.y + 12.0), 0.0)
	drone.armar()
	drone.estado = "voando"
	drone.altura_ref = drone.global_position.y
	drone.e_pitch = 1.0
	for i in 8:
		await _esperar(0.5)
		_log("indo contra o galpão %.1fs" % ((i + 1) * 0.5))
	drone.e_pitch = 0.0
	await _esperar(3.0)
	_log("depois da batida")
	print("TESTE FIM")
	get_tree().quit()


func _salvar_print(nome: String) -> void:
	var pasta := ProjectSettings.globalize_path("res://prints")
	DirAccess.make_dir_recursive_absolute(pasta)
	var img := get_viewport().get_texture().get_image()
	img.save_png(pasta.path_join(nome + ".png"))
	print("print salvo: ", nome)


func _quadros(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _tirar_prints() -> void:
	# no servidor sem placa de vídeo cada quadro demora: posiciona o drone direto
	hud.ajuda.visible = false
	await _quadros(4)
	_salvar_print("01_no_chao")
	var base := mapa.ponto_partida()
	drone.freeze = true
	for k in 4:
		drone.rps[k] = 150.0
		drone.empuxo[k] = 0.25
	drone.armado = true
	drone.estado = "voando"
	drone.global_transform = Transform3D(Basis(Vector3.UP, 0.4), base + Vector3(0, 0.25, 0))
	camera.posicionar_ja()
	await _quadros(12)
	_salvar_print("02_pairando")
	drone.global_transform = Transform3D(Basis(Vector3.UP, 0.4) * Basis(Vector3.RIGHT, -0.38), base + Vector3(-6, 2.5, -14))
	camera.posicionar_ja()
	await _quadros(4)
	_salvar_print("03_voando")
	camera.distancia = 0.45
	camera.altura = 0.12
	camera.posicionar_ja()
	await _quadros(4)
	_salvar_print("04_perto")
	hud.ajuda.visible = true
	await _quadros(3)
	_salvar_print("05_ajuda")
	get_tree().quit()
