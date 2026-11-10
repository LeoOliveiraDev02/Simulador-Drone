extends CanvasLayer
class_name Hud
## Painel na tela: modo, altura, velocidade, vento, hélices, avisos e a ajuda dos controles.

var painel: PanelContainer
var info: Label
var helices: Array[Label] = []
var aviso: Label
var ajuda: PanelContainer
var tempo_aviso := 0.0
var seta_vento: Control
var ang_vento := 0.0
var controle_txt: Label
var diagrama: Control
var explica: Label
var _empuxo: Array = [0.0, 0.0, 0.0, 0.0]
var _ok: Array = [true, true, true, true]
var _sentido: Array = [1.0, -1.0, 1.0, -1.0]
var _giro: Array = [0.0, 0.0, 0.0, 0.0]


func _ready() -> void:
	painel = PanelContainer.new()
	painel.position = Vector2(18, 16)
	painel.add_theme_stylebox_override("panel", _fundo(Color(0.02, 0.03, 0.04, 0.55)))
	add_child(painel)
	var cx := VBoxContainer.new()
	cx.add_theme_constant_override("separation", 6)
	painel.add_child(cx)
	var titulo := Label.new()
	titulo.text = "E88  •  drone dobrável"
	titulo.add_theme_font_size_override("font_size", 22)
	titulo.add_theme_color_override("font_color", Color(0.95, 0.97, 1.0))
	cx.add_child(titulo)
	info = Label.new()
	info.add_theme_font_size_override("font_size", 18)
	info.add_theme_color_override("font_color", Color(0.85, 0.9, 0.95))
	cx.add_child(info)
	var linha := HBoxContainer.new()
	linha.add_theme_constant_override("separation", 10)
	cx.add_child(linha)
	var lh := Label.new()
	lh.text = "Hélices:"
	lh.add_theme_font_size_override("font_size", 18)
	linha.add_child(lh)
	for nome in ["FD", "FE", "TE", "TD"]:
		var l := Label.new()
		l.text = nome
		l.add_theme_font_size_override("font_size", 18)
		linha.add_child(l)
		helices.append(l)
	var lv := HBoxContainer.new()
	cx.add_child(lv)
	var t := Label.new()
	t.text = "Vento:"
	t.add_theme_font_size_override("font_size", 18)
	lv.add_child(t)
	seta_vento = Control.new()
	seta_vento.custom_minimum_size = Vector2(34, 34)
	seta_vento.draw.connect(_desenhar_seta)
	lv.add_child(seta_vento)
	controle_txt = Label.new()
	controle_txt.add_theme_font_size_override("font_size", 15)
	controle_txt.add_theme_color_override("font_color", Color(0.7, 0.75, 0.8))
	cx.add_child(controle_txt)

	# diagrama dos motores visto de cima: mostra como o drone se move mudando a força de cada um
	var pd := PanelContainer.new()
	pd.add_theme_stylebox_override("panel", _fundo(Color(0.02, 0.03, 0.04, 0.55)))
	pd.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	pd.position = Vector2(-250, 16)
	add_child(pd)
	var vd := VBoxContainer.new()
	pd.add_child(vd)
	var td := Label.new()
	td.text = "Força de cada motor"
	td.add_theme_font_size_override("font_size", 16)
	td.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vd.add_child(td)
	diagrama = Control.new()
	diagrama.custom_minimum_size = Vector2(210, 190)
	diagrama.draw.connect(_desenhar_motores)
	vd.add_child(diagrama)
	explica = Label.new()
	explica.add_theme_font_size_override("font_size", 14)
	explica.add_theme_color_override("font_color", Color(0.8, 0.88, 0.95))
	explica.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	explica.custom_minimum_size = Vector2(210, 0)
	vd.add_child(explica)

	aviso = Label.new()
	aviso.add_theme_font_size_override("font_size", 34)
	aviso.add_theme_color_override("font_color", Color(1, 0.95, 0.85))
	aviso.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	aviso.add_theme_constant_override("outline_size", 8)
	aviso.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	aviso.set_anchors_preset(Control.PRESET_CENTER_TOP)
	aviso.position = Vector2(-500, 90)
	aviso.size = Vector2(1000, 60)
	add_child(aviso)

	ajuda = PanelContainer.new()
	ajuda.add_theme_stylebox_override("panel", _fundo(Color(0.02, 0.03, 0.04, 0.78)))
	ajuda.set_anchors_preset(Control.PRESET_CENTER)
	add_child(ajuda)
	var la := Label.new()
	la.add_theme_font_size_override("font_size", 19)
	la.text = """COMO PILOTAR O E88   (Start ou H fecha esta ajuda)

CONTROLE (modo 2, igual ao rádio do E88)
  Analógico esquerdo ↑↓ ....... subir / descer (no meio = trava a altura)
  Analógico esquerdo ←→ ....... girar no próprio eixo
  Analógico direito ↑↓ ........ ir para frente / para trás
  Analógico direito ←→ ........ ir para os lados
  A ......... decolar / pousar sozinho          Y ........ modo estabilizado / acro
  X ......... recomeçar na base                 B ........ desligar motores (emergência)
  Setas ↑↓ .. vento mais forte / mais fraco     Setas ←→ . câmera mais perto / longe
  LB ........ liga/desliga as rajadas            RB ....... muda a direção do vento

TECLADO
  W/S subir/descer   A/D girar   ↑↓←→ frente/trás/lados   Espaço decolar/pousar
  M modo   R recomeçar   B desligar   +/- vento   PgUp/PgDn câmera   G rajadas   H ajuda

MODOS
  ESTABILIZADO: o drone se nivela sozinho e trava a altura. Soltou o controle, ele freia e para.
  ACRO: você comanda o giro direto; ele NÃO se nivela sozinho e o acelerador é manual.

CUIDADO: bater a hélice girando quebra ela; pouso muito forte também. Água derruba o drone.
"""
	ajuda.add_child(la)
	ajuda.visible = false


func _fundo(c: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = c
	s.set_corner_radius_all(10)
	s.content_margin_left = 16
	s.content_margin_right = 16
	s.content_margin_top = 12
	s.content_margin_bottom = 12
	return s


func _desenhar_motores() -> void:
	var c := diagrama.size * 0.5 + Vector2(0, 6)
	var corpo := Color(0.75, 0.78, 0.82, 0.9)
	# posições na tela: 0 FD, 1 FE, 2 TE, 3 TD (frente para cima)
	var pos := [Vector2(52, -52), Vector2(-52, -52), Vector2(-52, 52), Vector2(52, 52)]
	for k in 4:
		diagrama.draw_line(c, c + pos[k], corpo, 6.0)
	diagrama.draw_rect(Rect2(c - Vector2(16, 26), Vector2(32, 52)), Color(0.15, 0.16, 0.18), true)
	diagrama.draw_rect(Rect2(c - Vector2(16, 26), Vector2(32, 52)), corpo, false, 2.0)
	diagrama.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -36), c + Vector2(-7, -27), c + Vector2(7, -27)]), Color(0.4, 0.85, 1.0))
	var fonte := ThemeDB.fallback_font
	for k in 4:
		var p: Vector2 = c + pos[k]
		var f: float = clampf(_empuxo[k] / E88.T_MAX, 0.0, 1.0)
		var cor := Color(1.0, 0.3, 0.25) if not _ok[k] else Color(0.25, 0.8, 0.45).lerp(Color(1.0, 0.75, 0.2), smoothstep(0.45, 0.9, f))
		diagrama.draw_circle(p, 30, Color(1, 1, 1, 0.06))
		diagrama.draw_arc(p, 30, 0, TAU, 40, Color(1, 1, 1, 0.25), 1.5)
		if _ok[k]:
			diagrama.draw_circle(p, 4.0 + 25.0 * f, Color(cor, 0.85))
			# setinha mostrando o sentido do giro da hélice
			var a0: float = _giro[k]
			var s: float = _sentido[k]
			diagrama.draw_arc(p, 34, a0, a0 + s * -1.6, 12, Color(0.85, 0.9, 1.0, 0.8), 2.0)
			diagrama.draw_string(fonte, p + Vector2(-14, 6), "%d%%" % roundi(f * 100.0), HORIZONTAL_ALIGNMENT_CENTER, 28, 13, Color(1, 1, 1))
		else:
			diagrama.draw_line(p - Vector2(14, 14), p + Vector2(14, 14), cor, 4.0)
			diagrama.draw_line(p - Vector2(14, -14), p + Vector2(14, -14), cor, 4.0)


func _desenhar_seta() -> void:
	var c := seta_vento.size * 0.5
	var d := Vector2(sin(ang_vento), -cos(ang_vento))
	var n := Vector2(-d.y, d.x)
	var cor := Color(0.6, 0.85, 1.0)
	seta_vento.draw_circle(c, 16, Color(1, 1, 1, 0.08))
	seta_vento.draw_line(c - d * 12, c + d * 10, cor, 3.0)
	seta_vento.draw_colored_polygon(PackedVector2Array([c + d * 14, c + d * 4 + n * 6, c + d * 4 - n * 6]), cor)


func atualizar(drone: E88, vento: Vento, camera: Camera3D, controle_nome: String, distancia_base: float, limite: float) -> void:
	var v := drone.linear_velocity
	var vh := Vector2(v.x, v.z).length()
	var h := drone.global_position.y - 0.026 - drone.chao_y
	var estado := {"pousado": "no chão", "decolando": "decolando", "voando": "voando", "pousando": "pousando", "caido": "CAÍDO"}
	var txt := "Modo: %s\n" % drone.nome_modo()
	txt += "Motores: %s   (%s)\n" % ["LIGADOS" if drone.armado else "desligados", estado.get(drone.estado, drone.estado)]
	txt += "Altura: %.1f m      Velocidade: %.1f m/s (%d km/h)\n" % [maxf(h, 0.0), vh, roundi(vh * 3.6)]
	txt += "Subida: %+.1f m/s    Distância da base: %d m\n" % [v.y, roundi(distancia_base)]
	txt += "Vento: %s" % vento.texto()
	if drone.efeito_solo > 1.03 and drone.armado:
		txt += "\nEfeito solo: +%d%% de força" % roundi((drone.efeito_solo - 1.0) * 100.0)
	if drone.turb_nivel > 0.15:
		txt += "\nTurbulência!"
	info.text = txt
	for k in 4:
		var ok := drone.helice_ok[k]
		helices[k].add_theme_color_override("font_color", Color(0.45, 0.95, 0.5) if ok else Color(1.0, 0.3, 0.25))
		helices[k].text = ("●" if ok else "✗") + ["FD", "FE", "TE", "TD"][k]
	# seta do vento relativa à câmera (para cima = vento empurrando para a frente da tela)
	var f := -camera.global_transform.basis.z
	f.y = 0.0
	f = f.normalized()
	var r := Vector3(-f.z, 0, f.x)
	var d := Vector3(sin(vento.direcao), 0, cos(vento.direcao))
	ang_vento = atan2(d.dot(r), d.dot(f))
	seta_vento.queue_redraw()
	for k in 4:
		_empuxo[k] = drone.empuxo[k]
		_ok[k] = drone.helice_ok[k]
		_giro[k] = fmod(_giro[k] - _sentido[k] * drone.rps[k] * 0.0006, TAU)
	diagrama.queue_redraw()
	explica.text = _explicacao(drone)
	controle_txt.text = controle_nome + "   •   Start/H: ajuda"
	if distancia_base > limite:
		mostrar("Longe demais! Volte para a área de voo", 0.3)


func mostrar(texto: String, segundos: float) -> void:
	aviso.text = texto
	tempo_aviso = segundos


func _process(delta: float) -> void:
	if ajuda.visible:
		ajuda.position = (get_viewport().get_visible_rect().size - ajuda.size) * 0.5
	if tempo_aviso > 0.0:
		tempo_aviso -= delta
		aviso.modulate.a = clampf(tempo_aviso * 2.0, 0.0, 1.0)
	else:
		aviso.modulate.a = 0.0


func _explicacao(d: E88) -> String:
	if d.helice_ok.count(false) > 0:
		return "Com uma hélice a menos o drone perde o equilíbrio: os outros 3 motores não conseguem segurar."
	if not d.armado:
		return "Motores parados. Cada motor gira uma hélice; duas giram para um lado e duas para o outro."
	if absf(d.e_yaw) > 0.25:
		return "Girar: as hélices de um sentido aceleram e as do outro desaceleram. A diferença de torque gira o drone."
	if d.e_pitch > 0.25:
		return "Para frente: os motores de trás ficam mais fortes, o drone inclina o nariz e o empuxo leva ele para frente."
	if d.e_pitch < -0.25:
		return "Para trás: os motores da frente ficam mais fortes e o drone inclina para trás."
	if absf(d.e_roll) > 0.25:
		return "Para o lado: os motores do lado oposto ficam mais fortes e o drone inclina para onde você quer ir."
	if d.e_acel > 0.25:
		return "Subir: os 4 motores aceleram juntos."
	if d.e_acel < -0.25:
		return "Descer: os 4 motores diminuem juntos."
	if d.turb_nivel > 0.15:
		return "Turbulência: o ar das hélices voltou batendo (chão, parede ou árvore). A controladora corrige sozinha."
	if d.efeito_solo > 1.05:
		return "Efeito solo: perto do chão o ar das hélices fica preso embaixo e o drone ganha força extra."
	return "Pairando: cada motor faz 1/4 do peso. A controladora corrige a inclinação centenas de vezes por segundo."
