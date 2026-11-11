extends CanvasLayer
class_name Carregamento
## Tela de carregamento: monta o mapa e prepara todos os gráficos ANTES do voo,
## para não engasgar quando aparece algo novo na tela.

const DICAS := [
	"O E88 tem 4 motores: dois giram para um lado e dois para o outro. É isso que deixa ele parado no ar sem rodar.",
	"Para ir para frente, os motores de trás ficam mais fortes e o drone inclina o nariz.",
	"Perto do chão o ar das hélices fica preso embaixo: é o efeito solo. Ele ganha força extra.",
	"Atrás do galpão e das árvores o vento vira redemoinho. O drone balança!",
	"Bater a hélice girando quebra ela. Pouse devagar no H.",
	"No modo ACRO o drone não se nivela sozinho: é você quem segura tudo.",
	"Arraste o dedo no meio da tela para olhar em volta do drone.",
]

var fundo: ColorRect
var barra: ProgressBar
var texto: Label
var dica: Label
var t := 0.0
var i_dica := 0


func _ready() -> void:
	layer = 50
	fundo = ColorRect.new()
	fundo.color = Color(0.03, 0.04, 0.05)
	fundo.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(fundo)
	var caixa := VBoxContainer.new()
	caixa.set_anchors_preset(Control.PRESET_CENTER)
	caixa.alignment = BoxContainer.ALIGNMENT_CENTER
	caixa.add_theme_constant_override("separation", 18)
	caixa.custom_minimum_size = Vector2(1000, 0)
	caixa.position = Vector2(-500, -330)
	fundo.add_child(caixa)
	var img := TextureRect.new()
	img.texture = load("res://icone.png")
	img.custom_minimum_size = Vector2(300, 300)
	img.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	img.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	caixa.add_child(img)
	var titulo := Label.new()
	titulo.text = "Simulador de Drone  •  E88"
	titulo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	titulo.add_theme_font_size_override("font_size", 44)
	caixa.add_child(titulo)
	barra = ProgressBar.new()
	barra.custom_minimum_size = Vector2(1000, 26)
	barra.max_value = 1.0
	barra.show_percentage = false
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.95, 0.75, 0.25)
	sb.set_corner_radius_all(8)
	barra.add_theme_stylebox_override("fill", sb)
	var sf := StyleBoxFlat.new()
	sf.bg_color = Color(1, 1, 1, 0.1)
	sf.set_corner_radius_all(8)
	barra.add_theme_stylebox_override("background", sf)
	caixa.add_child(barra)
	texto = Label.new()
	texto.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	texto.add_theme_font_size_override("font_size", 24)
	texto.add_theme_color_override("font_color", Color(0.8, 0.85, 0.9))
	caixa.add_child(texto)
	dica = Label.new()
	dica.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	dica.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dica.custom_minimum_size = Vector2(1000, 90)
	dica.add_theme_font_size_override("font_size", 22)
	dica.add_theme_color_override("font_color", Color(1.0, 0.9, 0.6))
	caixa.add_child(dica)
	dica.text = "Dica: " + DICAS[0]
	definir(0.0, "Começando")


func definir(f: float, msg: String) -> void:
	barra.value = f
	texto.text = msg + "…"


func _process(delta: float) -> void:
	t += delta
	if t > 5.0:
		t = 0.0
		i_dica = (i_dica + 1) % DICAS.size()
		dica.text = "Dica: " + DICAS[i_dica]


func sumir() -> void:
	var tw := create_tween()
	tw.tween_property(fundo, "modulate:a", 0.0, 0.6)
	tw.tween_callback(queue_free)
