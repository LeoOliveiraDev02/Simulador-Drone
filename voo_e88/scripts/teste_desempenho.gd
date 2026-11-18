class_name TesteDesempenho
extends CanvasLayer
## F3: teste de desempenho automático (~45 s). Mede o FPS desligando UMA coisa de cada vez
## (FSR, resolução, capim, árvores, sombra, física) e no fim tudo junto. Mostra uma tabela na tela,
## grava em user://teste_desempenho.txt e escreve no terminal. Serve para descobrir o que pesa
## numa placa fraca (ex.: Intel HD 2500 do OptiPlex) antes de cortar qualquer coisa.
## Para medir certo: deixar o drone pairando parado e não mexer em nada durante o teste.

const AQUECER := 1.5   # segundos ignorados depois de cada troca (a placa recompila/reacomoda)
const MEDIR := 5.0

var voo: Node
var mapa: Mapa

var _passos: Array = []      # [nome, id]
var _i := -1
var _t := 0.0
var _quadros := 0
var _t0 := 0
var _proc := 0.0
var _fis := 0.0
var _amostras := 0
var _tri := 0.0
var _chamadas := 0.0
var _res: Array = []
var _painel: Label
var _fundo: Panel
var _salvo := {}


func _ready() -> void:
	layer = 50
	_fundo = Panel.new()
	_fundo.position = Vector2(560, 120)
	_fundo.size = Vector2(800, 470)
	var est := StyleBoxFlat.new()
	est.bg_color = Color(0.04, 0.05, 0.07, 0.88)
	est.set_corner_radius_all(10)
	_fundo.add_theme_stylebox_override("panel", est)
	add_child(_fundo)
	_painel = Label.new()
	_painel.position = Vector2(24, 18)
	_painel.size = Vector2(760, 440)
	_painel.add_theme_font_size_override("font_size", 19)
	_fundo.add_child(_painel)
	_montar_passos()
	_texto("TESTE DE DESEMPENHO\n\nDeixe o drone parado e não mexa em nada.\nSão %d medições de %d s (uns %d s no total)." %
		[_passos.size(), int(AQUECER + MEDIR), int(_passos.size() * (AQUECER + MEDIR))])
	_proximo()


func _montar_passos() -> void:
	_passos.append(["Como está agora", "nada"])
	if voo.get("fsr1"):
		_passos.append(["Sem FSR 1 (aumento simples)", "fsr"])
	if mapa.chao_ps2 != null:
		_passos.append(["Chão atual no lugar do PS2" if mapa.chao_ps2_ativo else "Chão PS2 no lugar do atual", "chao"])
	_passos.append(["3D em 35% (menos pixels)", "escala"])
	_passos.append(["Sem capim e flores", "capim"])
	_passos.append(["Sem árvores e arbustos", "plantas"])
	_passos.append(["Sem sombra do sol", "sombra"])
	_passos.append(["Física a 60 Hz (menos processador)", "fisica"])
	_passos.append(["TUDO ISSO JUNTO (menos a física)", "tudo"])


func _desligar(id: String) -> void:
	var fsr = voo.get("fsr1")
	match id:
		"fsr":
			fsr.alternar()
		"escala":
			if fsr:
				_salvo["escala"] = fsr.escala
				fsr.escala = 0.35
				fsr._redimensionar()
			else:
				_salvo["escala"] = get_viewport().scaling_3d_scale
				get_viewport().scaling_3d_scale = 0.35
		"chao":
			mapa.ativar_chao_ps2(not mapa.chao_ps2_ativo)
		"capim":
			_ver_capim(false)
		"plantas":
			_ver_plantas(false)
		"sombra":
			_salvo["sombra"] = mapa.luz_sol.shadow_enabled
			mapa.luz_sol.shadow_enabled = false
		"fisica":
			_salvo["fis"] = Engine.physics_ticks_per_second
			Engine.physics_ticks_per_second = 60
		"tudo":
			for k in ["fsr", "escala", "capim", "plantas", "sombra"]:
				if k != "fsr" or fsr:
					_desligar(k)


func _religar(id: String) -> void:
	var fsr = voo.get("fsr1")
	match id:
		"fsr":
			fsr.alternar()
		"escala":
			if fsr:
				fsr.escala = _salvo["escala"]
				fsr._redimensionar()
			else:
				get_viewport().scaling_3d_scale = _salvo["escala"]
		"chao":
			mapa.ativar_chao_ps2(not mapa.chao_ps2_ativo)
		"capim":
			_ver_capim(true)
		"plantas":
			_ver_plantas(true)
		"sombra":
			mapa.luz_sol.shadow_enabled = _salvo["sombra"]
		"fisica":
			Engine.physics_ticks_per_second = _salvo["fis"]
		"tudo":
			for k in ["sombra", "plantas", "capim", "escala", "fsr"]:
				if k != "fsr" or fsr:
					_religar(k)


func _ver_capim(v: bool) -> void:
	for b in mapa.blocos_grama:
		if is_instance_valid(b):
			b.visible = v and not mapa.chao_ps2_ativo
	for b in mapa.blocos_flores:
		if is_instance_valid(b):
			b.visible = v and not mapa.chao_ps2_ativo


func _ver_plantas(v: bool) -> void:
	# religa só o que estava ligado (as árvores de longe ficam escondidas no gráfico baixo)
	if not v:
		_salvo["plantas"] = []
		for p in mapa.plantas:
			if is_instance_valid(p) and p.visible:
				_salvo["plantas"].append(p)
				p.visible = false
	else:
		for p in _salvo.get("plantas", []):
			if is_instance_valid(p):
				p.visible = true


func _proximo() -> void:
	if _i >= 0:
		_religar(_passos[_i][1])
	_i += 1
	if _i >= _passos.size():
		_terminar()
		return
	_desligar(_passos[_i][1])
	_t = 0.0
	_quadros = 0
	_proc = 0.0
	_fis = 0.0
	_amostras = 0
	_tri = 0.0
	_chamadas = 0.0
	_texto(_tabela() + "\nMedindo %d/%d: %s ..." % [_i + 1, _passos.size(), _passos[_i][0]])


func _process(d: float) -> void:
	if _i < 0 or _i >= _passos.size():
		return
	_t += d
	if _t < AQUECER:
		return
	if _quadros == 0:
		_t0 = Time.get_ticks_usec()
	_quadros += 1
	_proc += Performance.get_monitor(Performance.TIME_PROCESS)
	_fis += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
	_tri += Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
	_chamadas += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
	_amostras += 1
	if _t >= AQUECER + MEDIR:
		var dur := (Time.get_ticks_usec() - _t0) / 1e6
		var fps := (_quadros - 1) / maxf(dur, 0.001)
		var n := float(maxi(_amostras, 1))
		var hz := float(Engine.physics_ticks_per_second)
		# tempo de processador por quadro: scripts + física (a física roda hz/fps vezes por quadro)
		var cpu := (_proc / n + (_fis / n) * hz / maxf(fps, 1.0)) * 1000.0
		_res.append([_passos[_i][0], fps, 1000.0 / maxf(fps, 0.001), cpu, _tri / n, _chamadas / n])
		_proximo()


func _tabela() -> String:
	var s := "TESTE DE DESEMPENHO   (%s)\n\n" % RenderingServer.get_video_adapter_name()
	if _res.is_empty():
		return s
	var base: float = _res[0][1]
	for r in _res:
		var ganho := ""
		if r != _res[0]:
			ganho = "  (%+d%%)" % roundi((r[1] / maxf(base, 0.01) - 1.0) * 100.0)
		s += "%-34s %5.1f FPS%s\n" % [r[0], r[1], ganho]
	return s


func _terminar() -> void:
	var s := _tabela()
	s += "\nPronto! Tire um print desta tela e mande para o Claude."
	s += "\n(também salvo em teste_desempenho.txt; F3 fecha)"
	_texto(s)
	# detalhado no terminal e no arquivo
	var det := "TESTE DE DESEMPENHO — %s — %s\n" % [Time.get_datetime_string_from_system(), RenderingServer.get_video_adapter_name()]
	det += "janela %s, Godot %s, %s\n" % [str(get_window().size), Engine.get_version_info().string, RenderingServer.get_current_rendering_method()]
	det += "%-36s %7s %8s %9s %10s %8s\n" % ["passo", "FPS", "ms/quad", "ms CPU", "triâng.", "chamadas"]
	for r in _res:
		det += "%-36s %7.1f %8.1f %9.1f %10d %8d\n" % [r[0], r[1], r[2], r[3], int(r[4]), int(r[5])]
	print(det)
	var f := FileAccess.open("user://teste_desempenho.txt", FileAccess.WRITE)
	if f:
		f.store_string(det)
		print("salvo em: ", ProjectSettings.globalize_path("user://teste_desempenho.txt"))


func _texto(s: String) -> void:
	_painel.text = s
