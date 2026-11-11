extends CanvasLayer
class_name ControleToque
## Controle na tela do celular, igual ao rádio do E88 (modo 2):
## analógico da esquerda = subir/descer e girar; da direita = frente/trás e lados.
## Os dois voltam para o meio quando você solta (altura travada, drone freia).
## Aceita vários dedos ao mesmo tempo (os dois analógicos + um botão).

signal botao(nome: String)

const RAIO := 165.0
var acel := 0.0
var yaw := 0.0
var pitch := 0.0
var roll := 0.0

var tela: Control
var dedo_esq := -1
var dedo_dir := -1
var pos_esq := Vector2.ZERO      # deslocamento do dedo em relação ao centro
var pos_dir := Vector2.ZERO
var botoes := []                 # [nome, texto, retângulo]
var apertado := {}               # dedo -> nome do botão
var texto_decolar := "DECOLAR"
var dedo_olhar := -1
var olhar_delta := Vector2.ZERO   # quanto o dedo arrastou para olhar em volta (lido pela câmera)


func _ready() -> void:
	layer = 5
	tela = Control.new()
	tela.set_anchors_preset(Control.PRESET_FULL_RECT)
	tela.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tela.draw.connect(_desenhar)
	add_child(tela)


func _tamanho() -> Vector2:
	return tela.get_viewport_rect().size


func _centro_esq() -> Vector2:
	var t := _tamanho()
	return Vector2(250, t.y - 250)


func _centro_dir() -> Vector2:
	var t := _tamanho()
	return Vector2(t.x - 250, t.y - 250)


func _montar_botoes() -> void:
	var t := _tamanho()
	botoes.clear()
	var nomes := [["decolar", texto_decolar], ["flip", "FLIP"], ["modo", "MODO"], ["recomecar", "RECOMEÇAR"]]
	var w := 200.0
	var gap := 18.0
	var x0 := t.x * 0.5 - (w * 4 + gap * 3) * 0.5
	for i in nomes.size():
		botoes.append([nomes[i][0], nomes[i][1], Rect2(x0 + i * (w + gap), t.y - 110, w, 82)])
	var cima := [["ajuda", "AJUDA"], ["cam_perto", "CÂMERA −"], ["cam_longe", "CÂMERA +"], ["vento", "VENTO"], ["grafico", "GRÁFICO"]]
	var w2 := 150.0
	var x1 := t.x * 0.5 - (w2 * cima.size() + gap * (cima.size() - 1)) * 0.5
	for i in cima.size():
		botoes.append([cima[i][0], cima[i][1], Rect2(x1 + i * (w2 + gap), 18, w2, 62)])


func _input(ev: InputEvent) -> void:
	if ev is InputEventScreenTouch:
		var p: Vector2 = ev.position
		if ev.pressed:
			for b in botoes:
				if (b[2] as Rect2).has_point(p):
					apertado[ev.index] = b[0]
					botao.emit(b[0])
					get_viewport().set_input_as_handled()
					tela.queue_redraw()
					return
			# perto de um analógico = analógico; no resto da tela = olhar em volta
			if p.distance_to(_centro_esq()) < RAIO * 1.6 and dedo_esq < 0:
				dedo_esq = ev.index
				pos_esq = _limitar(p - _centro_esq())
			elif p.distance_to(_centro_dir()) < RAIO * 1.6 and dedo_dir < 0:
				dedo_dir = ev.index
				pos_dir = _limitar(p - _centro_dir())
			elif dedo_olhar < 0:
				dedo_olhar = ev.index
		else:
			apertado.erase(ev.index)
			if ev.index == dedo_olhar:
				dedo_olhar = -1
			if ev.index == dedo_esq:
				dedo_esq = -1
				pos_esq = Vector2.ZERO
			elif ev.index == dedo_dir:
				dedo_dir = -1
				pos_dir = Vector2.ZERO
		_atualizar()
		get_viewport().set_input_as_handled()
	elif ev is InputEventScreenDrag:
		if ev.index == dedo_esq:
			pos_esq = _limitar(ev.position - _centro_esq())
		elif ev.index == dedo_dir:
			pos_dir = _limitar(ev.position - _centro_dir())
		elif ev.index == dedo_olhar:
			olhar_delta += ev.relative
		_atualizar()
		get_viewport().set_input_as_handled()


func _limitar(v: Vector2) -> Vector2:
	return v.limit_length(RAIO)


func _atualizar() -> void:
	acel = -pos_esq.y / RAIO
	yaw = pos_esq.x / RAIO
	pitch = -pos_dir.y / RAIO
	roll = pos_dir.x / RAIO
	tela.queue_redraw()


func _process(_d: float) -> void:
	_montar_botoes()
	tela.queue_redraw()


func _desenhar() -> void:
	var fonte := ThemeDB.fallback_font
	for lado in [[_centro_esq(), pos_esq, "SOBE / GIRA"], [_centro_dir(), pos_dir, "FRENTE / LADOS"]]:
		var c: Vector2 = lado[0]
		tela.draw_circle(c, RAIO, Color(0, 0, 0, 0.22))
		tela.draw_arc(c, RAIO, 0, TAU, 64, Color(1, 1, 1, 0.45), 3.0)
		tela.draw_line(c - Vector2(RAIO * 0.85, 0), c + Vector2(RAIO * 0.85, 0), Color(1, 1, 1, 0.15), 2.0)
		tela.draw_line(c - Vector2(0, RAIO * 0.85), c + Vector2(0, RAIO * 0.85), Color(1, 1, 1, 0.15), 2.0)
		tela.draw_circle(c + lado[1], 62, Color(0.85, 0.9, 1.0, 0.55))
		tela.draw_string(fonte, c + Vector2(-90, RAIO + 34), lado[2], HORIZONTAL_ALIGNMENT_CENTER, 180, 20, Color(1, 1, 1, 0.7))
	for b in botoes:
		var r: Rect2 = b[2]
		var ativo: bool = b[0] in apertado.values()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.95, 0.75, 0.25, 0.85) if ativo else Color(0.05, 0.06, 0.08, 0.6)
		sb.set_corner_radius_all(14)
		sb.border_color = Color(1, 1, 1, 0.5)
		sb.set_border_width_all(2)
		tela.draw_style_box(sb, r)
		var tam := 24 if r.size.y > 70 else 19
		tela.draw_string(fonte, r.position + Vector2(0, r.size.y * 0.5 + tam * 0.35), b[1], HORIZONTAL_ALIGNMENT_CENTER, r.size.x, tam, Color(1, 1, 1))
