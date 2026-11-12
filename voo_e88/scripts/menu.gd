extends CanvasLayer
class_name MenuConfig
## Menu de configurações (Esc no teclado, Start no controle).
## Cada linha é um botão: clicar troca o valor. O jogo fica pausado enquanto o menu está aberto.

var voo: Node            # cena principal (voo.gd)
var fundo: ColorRect
var caixa: VBoxContainer
var status: Label
var linhas := []         # [Button, Callable texto, Callable acao]


func _ready() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	fundo = ColorRect.new()
	fundo.color = Color(0.02, 0.03, 0.04, 0.78)
	fundo.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(fundo)

	var painel := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.08, 0.10, 0.96)
	sb.set_corner_radius_all(16)
	sb.border_color = Color(0.95, 0.75, 0.25, 0.6)
	sb.set_border_width_all(2)
	sb.content_margin_left = 34
	sb.content_margin_right = 34
	sb.content_margin_top = 26
	sb.content_margin_bottom = 26
	painel.add_theme_stylebox_override("panel", sb)
	painel.set_anchors_preset(Control.PRESET_CENTER)
	painel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	painel.grow_vertical = Control.GROW_DIRECTION_BOTH
	fundo.add_child(painel)

	caixa = VBoxContainer.new()
	caixa.add_theme_constant_override("separation", 10)
	caixa.custom_minimum_size = Vector2(640, 0)
	painel.add_child(caixa)

	var titulo := Label.new()
	titulo.text = "Configurações"
	titulo.add_theme_font_size_override("font_size", 34)
	titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	caixa.add_child(titulo)

	status = Label.new()
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status.add_theme_font_size_override("font_size", 17)
	status.add_theme_color_override("font_color", Color(1.0, 0.86, 0.5))
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	caixa.add_child(status)

	_linha(func(): return "Continuar o voo", fechar)
	_linha(func(): return "Imagem: " + voo.texto_modo_pc(), voo.ciclar_modo_pc)
	_linha(func(): return "Gerador de quadros FSR: " + voo.texto_gerador(), voo.alternar_gerador_menu)
	_linha(func(): return "Qualidade gráfica: " + voo.texto_qualidade_pc(), voo.ciclar_qualidade_pc)
	_linha(func(): return "Velocidade do drone: " + voo.texto_marcha(), voo.ciclar_marcha)
	_linha(func(): return "Sincronia vertical (VSync): " + voo.texto_vsync(), voo.alternar_vsync)
	_linha(func(): return "Limite de FPS: " + voo.texto_limite_fps(), voo.ciclar_limite_fps)
	_linha(func(): return "Reabrir o jogo agora (liga o gerador de quadros)", voo.reabrir_jogo, true)
	_linha(func(): return "Ajuda e controles", func(): fechar(); voo.mostrar_ajuda())
	_linha(func(): return "Sair do jogo", func(): get_tree().quit())
	visible = false


func _linha(texto: Callable, acao: Callable, so_se_precisa := false) -> void:
	var b := Button.new()
	b.custom_minimum_size = Vector2(0, 50)
	b.add_theme_font_size_override("font_size", 21)
	b.focus_mode = Control.FOCUS_ALL
	b.pressed.connect(func():
		acao.call()
		atualizar())
	caixa.add_child(b)
	linhas.append([b, texto, so_se_precisa])


func abrir() -> void:
	visible = true
	get_tree().paused = true
	atualizar()
	(linhas[0][0] as Button).grab_focus()


func fechar() -> void:
	visible = false
	get_tree().paused = false


func atualizar() -> void:
	for l in linhas:
		var b: Button = l[0]
		b.text = (l[1] as Callable).call()
		if l[2]:
			b.visible = voo.precisa_reabrir()
	var fsr: String = ProjectSettings.get_setting("rendering/amd_fsr/status", "")
	status.text = "%d FPS" % Engine.get_frames_per_second() + ("   •   " + fsr if fsr != "" else "")


func _process(_d: float) -> void:
	if visible:
		status.text = "%d FPS" % Engine.get_frames_per_second() + ("   •   " + str(ProjectSettings.get_setting("rendering/amd_fsr/status", "")) if str(ProjectSettings.get_setting("rendering/amd_fsr/status", "")) != "" else "")


func _input(ev: InputEvent) -> void:
	var abre: bool = (ev is InputEventKey and ev.pressed and not ev.echo and ev.keycode == KEY_ESCAPE) \
		or (ev is InputEventJoypadButton and ev.pressed and ev.button_index == JOY_BUTTON_START)
	if not abre:
		if visible and ev is InputEventJoypadButton and ev.pressed and ev.button_index == JOY_BUTTON_B:
			fechar()
			get_viewport().set_input_as_handled()
		return
	if visible:
		fechar()
	else:
		abrir()
	get_viewport().set_input_as_handled()
