extends Node3D
## Voo do E88: monta o mapa, o vento, o drone, a câmera e o painel; lê o controle.
##
## Argumentos (depois de "--"):
##   --qualidade=baixa   menos grama/árvores e sem efeitos pesados (PC fraco)
##   --teste-voo         voo automático sem tela, imprime os números (para testar a física)
##   --prints            tira prints do voo e fecha

const ZONA_MORTA := 0.08
const ORDENS_RADIO := [["A", "E", "T", "R"], ["T", "A", "E", "R"], ["A", "E", "R", "T"]]
const NOMES_MAPA := ["Controle de videogame (modo 2)", "Rádio USB — canais AETR", "Rádio USB — canais TAER", "Rádio USB — canais AERT"]

var mapa: Mapa
var vento: Vento
var drone: E88
var camera: CameraSegue
var hud: Hud
var toque: ControleToque
var movel_ativo := false
var grafico := 1                  # celular: 0 baixo, 1 médio, 2 alto (ajusta sozinho se o FPS cair)
var grafico_auto := true
var _tempo_fps_baixo := 0.0
var _tempo_fps_alto := 0.0
const ESCALA_3D := [0.5, 0.67, 0.85]
var qualidade_baixa := false
var modo_teste := false
var modo_prints := false
var teclado_vel := {"acel": 0.0, "yaw": 0.0, "pitch": 0.0, "roll": 0.0}
var segurando_armar := 0.0
var pausado_ajuda := false
var mapa_controle := -1          # -1 automático; 0 gamepad; 1..3 rádio
var inverter_pitch := false
var inverter_acel := false
var lado_portal: Array[float] = []
var portais_feitos := 0
var tempo_volta := -1.0
var passo_tutorial := 0      # primeiro voo guiado (T liga/desliga)
var tutorial_ligado := true
var tutorial_t := 0.0
var yaw_inicio := 0.0
var pos_inicio := Vector3.ZERO
var estado_antes := "pousado"
var ja_voou := false

# PC: qualidade da imagem. Na placa AMD (RX 7000/9000) o modo FSR vira FSR 4.1 com IA;
# nas outras placas o Godot usa o FSR 2.2. "Nativo AA" não reduz a resolução, só tira o serrilhado.
const MODOS_PC := [
	["Sem FSR (MSAA + TAA)", 1.0],
	["FSR Nativo AA", 1.0],
	["FSR Qualidade", 0.67],
	["FSR Equilibrado", 0.59],
	["FSR Desempenho", 0.5],
]
const CFG_GRAFICOS := "user://graficos.cfg"
var modo_pc := 1
var gerador_ao_abrir := false
const NOMES_QUALIDADE := ["BAIXA", "MÉDIA", "ALTA"]
const LIMITES_FPS := [0, 60, 120, 144, 165, 240]
var qualidade_pc := 2
var qualidade_pc_auto := true
var marcha_cfg := 1
var vsync_ligado := true
var limite_fps_i := 0
var menu: MenuConfig
var _tempo_pc_baixo := 0.0


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
	var movel := OS.has_feature("mobile") or "--movel" in OS.get_cmdline_user_args()
	if movel:
		qualidade_baixa = true
		# celular: física a 120 Hz (sem acumular passos atrasados), 3D em 70% da
		# resolução com nitidez FSR e no máximo 60 quadros
		Engine.physics_ticks_per_second = 120
		Engine.max_physics_steps_per_frame = 3
		Engine.max_fps = 60
		get_viewport().scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR
		get_viewport().scaling_3d_scale = 0.7
		get_viewport().fsr_sharpness = 0.4
		movel_ativo = true
	if qualidade_baixa:
		get_viewport().msaa_3d = Viewport.MSAA_DISABLED
		get_viewport().use_taa = false
	elif not movel:
		_carregar_cfg_pc()
		_aplicar_modo_pc(false)

	var carregando := Carregamento.new()
	add_child(carregando)
	await get_tree().process_frame
	if modo_prints:
		carregando.definir(0.4, "Capim")
		await get_tree().process_frame
		await get_tree().process_frame
		_salvar_print("00_carregando")
	mapa = Mapa.new()
	mapa.name = "Mapa"
	mapa.previa = "--previa" in OS.get_cmdline_user_args()
	mapa.movel = movel
	mapa.progresso.connect(carregando.definir)
	add_child(mapa)
	await mapa.montar(qualidade_baixa or modo_teste)
	carregando.definir(0.88, "Montando o E88")
	await get_tree().process_frame

	vento = Vento.new()
	vento.name = "Vento"
	vento.mapa = mapa
	add_child(vento)

	drone = E88.new()
	drone.name = "E88"
	add_child(drone)
	drone.preparar(load("res://drone/e88.glb"))
	drone.mapa = mapa
	drone.vento = vento
	drone.recomecar(mapa.ponto_partida(), 0.0)
	drone.marcha = marcha_cfg
	if not movel and not qualidade_baixa:
		mapa.nivel_grafico_pc(qualidade_pc)
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
	hud.mostrar("Start ou H: ajuda dos controles", 5.0)
	if (movel or DisplayServer.is_touchscreen_available() or "--toque" in OS.get_cmdline_user_args()) and not modo_teste:
		toque = ControleToque.new()
		add_child(toque)
		toque.botao.connect(_botao_toque)
		hud.missao.position.y = -260
		hud.mostrar("Use os dois analógicos da tela  •  arraste no meio da tela para olhar em volta", 6.0)
	if movel_ativo:
		_aplicar_grafico()
	if not movel and not modo_teste and not modo_prints:
		menu = MenuConfig.new()
		menu.voo = self
		add_child(menu)
		hud.mostrar("Esc (ou Start): configurações  •  H: ajuda dos controles", 6.0)

	carregando.definir(0.92, "Preparando os gráficos na placa de vídeo")
	if not modo_teste:
		await _aquecer_graficos()
	carregando.definir(1.0, "Pronto")
	carregando.sumir()

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


func _eixo_radio(dev: int, i: int) -> float:
	var v := Input.get_joy_axis(dev, i)
	return 0.0 if absf(v) < 0.03 else v


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
		if mapa_controle < 0:
			# controle de videogame conhecido = modo 2; o resto (rádio via USB) = canais AETR
			mapa_controle = 0 if Input.is_joy_known(d) else 1
		match mapa_controle:
			0:
				acel = -_eixo(d, JOY_AXIS_LEFT_Y)
				yaw = _eixo(d, JOY_AXIS_LEFT_X)
				pitch = -_eixo(d, JOY_AXIS_RIGHT_Y)
				roll = _eixo(d, JOY_AXIS_RIGHT_X)
			_:
				# rádio (EdgeTX/OpenTX em modo joystick): eixos 0..3 na ordem dos canais
				var ordem: Array = ORDENS_RADIO[mapa_controle - 1]
				var ch := {}
				for i in 4:
					ch[ordem[i]] = _eixo_radio(d, i)
				roll = ch["A"]
				pitch = -ch["E"] if not inverter_pitch else ch["E"]
				acel = ch["T"] if not inverter_acel else -ch["T"]
				yaw = ch["R"]
	var k_acel := float(Input.is_key_pressed(KEY_W)) - float(Input.is_key_pressed(KEY_S))
	var k_yaw := float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))
	var k_pitch := float(Input.is_key_pressed(KEY_UP)) - float(Input.is_key_pressed(KEY_DOWN))
	var k_roll := float(Input.is_key_pressed(KEY_RIGHT)) - float(Input.is_key_pressed(KEY_LEFT))
	acel = clampf(acel + _rampa("acel", k_acel, delta), -1.0, 1.0)
	yaw = clampf(yaw + _rampa("yaw", k_yaw, delta), -1.0, 1.0)
	pitch = clampf(pitch + _rampa("pitch", k_pitch * 0.8, delta), -1.0, 1.0)
	roll = clampf(roll + _rampa("roll", k_roll * 0.8, delta), -1.0, 1.0)
	if toque:
		acel = clampf(acel + toque.acel, -1.0, 1.0)
		yaw = clampf(yaw + toque.yaw, -1.0, 1.0)
		pitch = clampf(pitch + toque.pitch, -1.0, 1.0)
		roll = clampf(roll + toque.roll, -1.0, 1.0)
		toque.texto_decolar = "POUSAR" if drone.armado and drone.estado != "pousado" else "DECOLAR"
		if toque.olhar_delta != Vector2.ZERO:
			camera.olhar(toque.olhar_delta)
			toque.olhar_delta = Vector2.ZERO
		camera.olhando = toque.dedo_olhar >= 0
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
	if drone == null or hud == null:
		return
	if ev is InputEventJoypadButton and ev.pressed:
		match ev.button_index:
			JOY_BUTTON_A: drone.decolar_ou_pousar()
			JOY_BUTTON_Y: drone.trocar_modo()
			JOY_BUTTON_X: _recomecar()
			JOY_BUTTON_B: _emergencia()
			JOY_BUTTON_START:
				if menu == null:
					_ajuda()
			JOY_BUTTON_BACK: drone.trocar_sem_cabeca()
			JOY_BUTTON_RIGHT_STICK: drone.fazer_flip(Vector2(drone.e_roll, drone.e_pitch))
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
			KEY_F: drone.fazer_flip(Vector2(drone.e_roll, drone.e_pitch))
			KEY_K: drone.trocar_sem_cabeca()
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
			KEY_T:
				tutorial_ligado = not tutorial_ligado
				passo_tutorial = 0
				tutorial_t = 0.0
			KEY_F5:
				mapa_controle = (maxi(mapa_controle, 0) + 1) % NOMES_MAPA.size()
				hud.mostrar("Controle: " + NOMES_MAPA[mapa_controle], 2.5)
			KEY_F6:
				inverter_acel = not inverter_acel
				hud.mostrar("Acelerador " + ("invertido" if inverter_acel else "normal"), 2.0)
			KEY_F7:
				inverter_pitch = not inverter_pitch
				hud.mostrar("Frente/trás " + ("invertido" if inverter_pitch else "normal"), 2.0)
			KEY_F8:
				if not movel_ativo:
					ciclar_modo_pc()
					hud.mostrar("Imagem: " + texto_modo_pc() + "  (F8 troca)", 2.5)
			KEY_F9:
				if not movel_ativo:
					alternar_gerador_menu()
					hud.mostrar("Gerador de quadros: " + texto_gerador(), 4.0)
			KEY_F11:
				var w := get_window()
				w.mode = Window.MODE_MAXIMIZED if w.mode == Window.MODE_FULLSCREEN else Window.MODE_FULLSCREEN
			KEY_ESCAPE:
				if menu == null:
					_ajuda()
			KEY_N: drone.trocar_marcha()
			KEY_Q:
				if hud.ajuda.visible:
					get_tree().quit()


func _bateu(v: float) -> void:
	if v > 1.5:
		_vibrar(clampf(v / 4.0, 0.2, 1.0), 0.25)


func _vibrar(forte: float, segundos: float) -> void:
	for d in Input.get_connected_joypads():
		Input.start_joy_vibration(d, forte * 0.6, forte, segundos)


func _botao_toque(nome: String) -> void:
	match nome:
		"decolar": drone.decolar_ou_pousar()
		"flip": drone.fazer_flip(Vector2(drone.e_roll, drone.e_pitch))
		"modo": drone.trocar_modo()
		"recomecar": _recomecar()
		"ajuda": _ajuda()
		"cam_perto": camera.afastar(-0.3)
		"cam_longe": camera.afastar(0.3)
		"grafico":
			grafico = (grafico + 1) % 3
			grafico_auto = false
			_aplicar_grafico()
			hud.mostrar("Gráfico: " + ["BAIXO", "MÉDIO", "ALTO"][grafico], 2.0)
		"vento":
			vento.velocidade = fmod(vento.velocidade + 1.5, 9.0)
			hud.mostrar("Vento: " + vento.texto(), 1.5)


func _aplicar_grafico() -> void:
	get_viewport().scaling_3d_scale = ESCALA_3D[grafico]
	mapa.nivel_grafico(grafico)


func _ajuste_automatico(delta: float) -> void:
	# PC: se ficar abaixo de 45 FPS por 4 s, baixa a qualidade sozinho (só enquanto você não escolher no menu)
	if not movel_ativo and qualidade_pc_auto and not qualidade_baixa and mapa and not get_tree().paused:
		_tempo_pc_baixo = _tempo_pc_baixo + delta if Engine.get_frames_per_second() < 45 else 0.0
		if _tempo_pc_baixo > 4.0 and qualidade_pc > 0:
			_tempo_pc_baixo = -6.0
			qualidade_pc -= 1
			mapa.nivel_grafico_pc(qualidade_pc)
			hud.mostrar("Qualidade gráfica ajustada para " + NOMES_QUALIDADE[qualidade_pc] + " (FPS baixo). Esc para escolher.", 3.0)
	# mínimo de 30 FPS: se ficar abaixo de 32 por 3 s, baixa o gráfico; se sobrar folga (55+) por 12 s, sobe
	if not movel_ativo or not grafico_auto:
		return
	var fps := Engine.get_frames_per_second()
	_tempo_fps_baixo = _tempo_fps_baixo + delta if fps < 32 else 0.0
	_tempo_fps_alto = _tempo_fps_alto + delta if fps >= 55 else 0.0
	if _tempo_fps_baixo > 3.0 and grafico > 0:
		grafico -= 1
		_aplicar_grafico()
		hud.mostrar("Gráfico ajustado para " + ["BAIXO", "MÉDIO", "ALTO"][grafico] + " (FPS)", 2.0)
		_tempo_fps_baixo = 0.0
	elif _tempo_fps_alto > 12.0 and grafico < 2:
		grafico += 1
		_aplicar_grafico()
		_tempo_fps_alto = 0.0


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

## mostra tudo uma vez por trás da tela de carregamento: o celular prepara
## os sombreadores agora, e não no meio do voo (é o que causa os engasgos)
func _aquecer_graficos() -> void:
	var giros := 8
	for k in 4:
		drone.rps[k] = 150.0
	camera.olhando = true
	for i in giros:
		camera.olhar_yaw = TAU * i / giros
		camera.olhar_pitch = 0.6 if i % 2 == 0 else 0.0
		camera.posicionar_ja()
		await get_tree().process_frame
		await get_tree().process_frame
	# olha de longe (árvores com pouco detalhe, açude, galpão)
	camera.distancia = 40.0
	for i in 4:
		camera.olhar_yaw = TAU * i / 4.0
		camera.posicionar_ja()
		await get_tree().process_frame
	camera.distancia = 0.85
	camera.olhar_pitch = 0.0
	camera.olhar_yaw = 0.0
	camera.olhando = false
	for k in 4:
		drone.rps[k] = 0.0
	camera.posicionar_ja()
	await get_tree().process_frame


func _physics_process(delta: float) -> void:
	if drone == null or hud == null:
		return
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
	_tutorial(p, delta)
	_avaliar_pouso(p)
	# limite da área de voo: depois de 60 m além do limite o drone volta pousando
	var dist := Vector2(p.x, p.z).length()
	if dist > Mapa.LIMITE + 60.0 and drone.armado and drone.estado != "pousando":
		drone.estado = "pousando"
		hud.mostrar("Sinal perdido: pousando sozinho", 4.0)


func _process(_delta: float) -> void:
	if drone == null or hud == null:
		return
	_ajuste_automatico(_delta)
	if hud and camera and drone:
		var p := drone.global_position
		var dist := Vector2(p.x, p.z).length()
		var nome := "Controle na tela" if toque else "Sem controle conectado — usando o teclado"
		if Input.get_connected_joypads().size() > 0:
			nome = Input.get_joy_name(Input.get_connected_joypads()[0]) + " • " + NOMES_MAPA[maxi(mapa_controle, 0)] + " (F5 troca)"
		hud.atualizar(drone, vento, camera, nome, dist, Mapa.LIMITE)
		mapa.aplicar_vento(vento.direcao, vento.velocidade, vento.rajada_atual)


const TUTORIAL := [
	"Primeiro voo (1/6): aperte A (ou Espaço) para decolar",
	"(2/6) Muito bem! Empurre o analógico DIREITO para frente e voe uns 10 metros",
	"(3/6) Agora gire o drone: analógico ESQUERDO para os lados (dê meia volta)",
	"(4/6) Suba e desça com o analógico ESQUERDO para cima e para baixo",
	"(5/6) Voe até um dos portais laranja e passe por dentro dele",
	"(6/6) Volte para a base com o H e aperte A para pousar sozinho",
	"Primeiro voo completo! Agora é com você. (T mostra o tutorial de novo)",
]


func _tutorial(p: Vector3, delta: float) -> void:
	if not tutorial_ligado or modo_teste or modo_prints:
		hud.missao.text = ""
		return
	tutorial_t += delta
	var f := -drone.global_transform.basis.z
	var yaw := atan2(f.x, f.z)
	match passo_tutorial:
		0:
			if drone.estado == "voando":
				_proximo_passo(p, yaw)
		1:
			if Vector2(p.x - pos_inicio.x, p.z - pos_inicio.z).length() > 10.0:
				_proximo_passo(p, yaw)
		2:
			if absf(angle_difference(yaw, yaw_inicio)) > 2.6:
				_proximo_passo(p, yaw)
		3:
			if absf(p.y - pos_inicio.y) > 2.0:
				_proximo_passo(p, yaw)
		4:
			if portais_feitos > 0:
				_proximo_passo(p, yaw)
		5:
			if drone.estado == "pousado" and Vector2(p.x, p.z).length() < 5.0:
				_proximo_passo(p, yaw)
		6:
			if tutorial_t > 8.0:
				tutorial_ligado = false
	hud.missao.text = TUTORIAL[passo_tutorial] if passo_tutorial < TUTORIAL.size() else ""


func _proximo_passo(p: Vector3, yaw: float) -> void:
	passo_tutorial += 1
	tutorial_t = 0.0
	pos_inicio = p
	yaw_inicio = yaw
	_vibrar(0.25, 0.12)


func _avaliar_pouso(p: Vector3) -> void:
	if drone.estado == "voando":
		ja_voou = true
	if estado_antes != "pousado" and drone.estado == "pousado" and ja_voou:
		var d := Vector2(p.x, p.z).length()
		if d < 4.5:
			var nota := "PERFEITO" if d < 0.3 else ("ótimo" if d < 0.8 else ("bom" if d < 2.0 else "dentro da base"))
			hud.mostrar("Pouso na base: %s — %d cm do centro do H" % [nota, roundi(d * 100.0)], 4.0)
		ja_voou = false
	estado_antes = drone.estado


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
	# flip para frente
	drone.decolar_ou_pousar()
	await _esperar(3.0)
	drone.e_acel = 1.0
	await _esperar(1.2)
	drone.e_acel = 0.0
	await _esperar(1.0)
	_log("antes do flip")
	drone.fazer_flip(Vector2(0, 1))
	for i in 6:
		await _esperar(0.2)
		_log("flip %.1fs" % ((i + 1) * 0.2))
	await _esperar(1.5)
	_log("depois do flip")
	# esteira: pairando atrás do galpão com vento forte
	vento.velocidade = 6.0
	var dv := Vector2(sin(vento.direcao), cos(vento.direcao))
	var atras := Mapa.GALPAO_C + dv * 14.0
	drone.recomecar(Vector3(atras.x, mapa.altura(atras.x, atras.y) + 1.6, atras.y), 0.0)
	drone.armar()
	drone.estado = "voando"
	drone.altura_ref = drone.global_position.y
	for i in 3:
		await _esperar(1.0)
		_log("atrás do galpão %ds" % (i + 1))
		print("   esteira=%.2f turbulência=%.2f" % [vento.esteira(drone.global_position), drone.turb_nivel])
	vento.velocidade = 0.0
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
	# pouso no pasto (terreno de verdade, longe da base)
	for pt: Vector2 in [Vector2(60, -20), Vector2(-150, 120), Vector2(300, -300)]:
		drone.recomecar(Vector3(pt.x, mapa.altura(pt.x, pt.y) + 3.0, pt.y), 0.0)
		drone.armar()
		drone.estado = "pousando"
		await _esperar(9.0)
		_log("pouso no pasto %s" % str(pt))
		print("   terreno=%.2f  drone_y=%.2f  chão medido=%.2f" % [mapa.altura(pt.x, pt.y), drone.global_position.y, drone.chao_y])
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
	if "--so-dois" in OS.get_cmdline_user_args():
		get_tree().quit()
		return
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
	hud.ajuda.visible = false
	drone.global_transform = Transform3D(Basis(Vector3.UP, 0.9), Vector3(-60, mapa.altura(-60, -150) + 12.0, -150))
	camera.distancia = 2.0
	camera.altura = 0.6
	camera.posicionar_ja()
	await _quadros(4)
	_salvar_print("06_eucaliptos")
	get_tree().quit()


# ---------- PC: configurações (menu Esc), FSR 4.1 e gerador de quadros ----------

func _carregar_cfg_pc() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CFG_GRAFICOS) == OK:
		modo_pc = clampi(int(cfg.get_value("jogo", "modo_pc", 1)), 0, MODOS_PC.size() - 1)
		if cfg.has_section_key("jogo", "qualidade_pc"):
			qualidade_pc = clampi(int(cfg.get_value("jogo", "qualidade_pc", 2)), 0, 2)
			qualidade_pc_auto = false
		marcha_cfg = clampi(int(cfg.get_value("jogo", "marcha", 1)), 0, 2)
		vsync_ligado = bool(cfg.get_value("jogo", "vsync", true))
		limite_fps_i = clampi(int(cfg.get_value("jogo", "limite_fps", 0)), 0, LIMITES_FPS.size() - 1)
	# o gerador de quadros só funciona se já estava ligado quando o jogo abriu
	gerador_ao_abrir = bool(ProjectSettings.get_setting("rendering/amd_fsr/frame_generation", false))
	_aplicar_vsync()


func _salvar_cfg_pc() -> void:
	# este arquivo também é lido pelo motor ao abrir (application/config/project_settings_override)
	var cfg := ConfigFile.new()
	cfg.set_value("rendering", "amd_fsr/frame_generation", bool(ProjectSettings.get_setting("rendering/amd_fsr/frame_generation", false)))
	cfg.set_value("jogo", "modo_pc", modo_pc)
	if not qualidade_pc_auto:
		cfg.set_value("jogo", "qualidade_pc", qualidade_pc)
	cfg.set_value("jogo", "marcha", drone.marcha if drone else marcha_cfg)
	cfg.set_value("jogo", "vsync", vsync_ligado)
	cfg.set_value("jogo", "limite_fps", limite_fps_i)
	cfg.save(CFG_GRAFICOS)


func _aplicar_modo_pc(_avisar: bool) -> void:
	var vp := get_viewport()
	if modo_pc == 0:
		vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
		vp.scaling_3d_scale = 1.0
		vp.msaa_3d = Viewport.MSAA_2X
		vp.use_taa = true
	else:
		vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
		vp.scaling_3d_scale = MODOS_PC[modo_pc][1]
		vp.fsr_sharpness = 1.0 # nitidez moderada
		vp.msaa_3d = Viewport.MSAA_DISABLED
		vp.use_taa = false


func _aplicar_vsync() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if vsync_ligado else DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = LIMITES_FPS[limite_fps_i]


func texto_modo_pc() -> String:
	return MODOS_PC[modo_pc][0]


func ciclar_modo_pc() -> void:
	modo_pc = (modo_pc + 1) % MODOS_PC.size()
	_aplicar_modo_pc(false)
	_salvar_cfg_pc()


func texto_gerador() -> String:
	var ligado := bool(ProjectSettings.get_setting("rendering/amd_fsr/frame_generation", false))
	if not ligado:
		return "DESLIGADO"
	return "LIGADO (reabra o jogo para começar)" if not gerador_ao_abrir else "LIGADO"


func alternar_gerador_menu() -> void:
	var ligado := not bool(ProjectSettings.get_setting("rendering/amd_fsr/frame_generation", false))
	ProjectSettings.set_setting("rendering/amd_fsr/frame_generation", ligado)
	if ligado and modo_pc == 0:
		modo_pc = 1 # o gerador de quadros usa os dados do FSR
		_aplicar_modo_pc(false)
	_salvar_cfg_pc()


func precisa_reabrir() -> bool:
	return bool(ProjectSettings.get_setting("rendering/amd_fsr/frame_generation", false)) and not gerador_ao_abrir


func reabrir_jogo() -> void:
	_salvar_cfg_pc()
	OS.create_process(OS.get_executable_path(), OS.get_cmdline_args())
	get_tree().quit()


func texto_qualidade_pc() -> String:
	return NOMES_QUALIDADE[qualidade_pc] + (" (automática)" if qualidade_pc_auto else "")


func ciclar_qualidade_pc() -> void:
	qualidade_pc = (qualidade_pc + 1) % 3
	qualidade_pc_auto = false
	if mapa:
		mapa.nivel_grafico_pc(qualidade_pc)
	_salvar_cfg_pc()


func texto_marcha() -> String:
	var m: int = drone.marcha if drone else marcha_cfg
	return "%s (até %d km/h)" % [E88.NOMES_MARCHA[m], roundi(float(E88.VEL_MARCHA[m]) * 3.6)]


func ciclar_marcha() -> void:
	if drone:
		drone.marcha = (drone.marcha + 1) % E88.VEL_MARCHA.size()
	_salvar_cfg_pc()


func texto_vsync() -> String:
	return "LIGADA" if vsync_ligado else "DESLIGADA"


func alternar_vsync() -> void:
	vsync_ligado = not vsync_ligado
	_aplicar_vsync()
	_salvar_cfg_pc()


func texto_limite_fps() -> String:
	var l: int = LIMITES_FPS[limite_fps_i]
	return "SEM LIMITE" if l == 0 else str(l)


func ciclar_limite_fps() -> void:
	limite_fps_i = (limite_fps_i + 1) % LIMITES_FPS.size()
	_aplicar_vsync()
	_salvar_cfg_pc()


func mostrar_ajuda() -> void:
	hud.ajuda.visible = true
