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
