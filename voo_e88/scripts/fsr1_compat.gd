class_name Fsr1Compat
extends Node
## FSR 1 (AMD FidelityFX Super Resolution 1.0) para o renderizador de Compatibilidade (OpenGL).
##
## Feito para PC com vídeo integrado antigo (ex.: Dell OptiPlex 7010 com Intel HD Graphics 2500 no Ubuntu).
## O Godot só tem o FSR 1 no Forward+ (Vulkan), que essa placa não roda; aqui ele é feito à mão:
##   1. o 3D é desenhado num SubViewport menor (escala 50%–85% da tela);
##   2. o EASU (shaders/fsr1_easu.gdshader) aumenta para o tamanho da tela seguindo as bordas;
##   3. o RCAS (shaders/fsr1_rcas.gdshader) devolve a nitidez.
## A tela principal deixa de desenhar 3D (disable_3d) e só mostra o resultado + o painel (HUD) por cima.
## A câmera de verdade (CameraSegue) continua no lugar; uma cópia dela dentro do SubViewport desenha a cena.

const ESCALA_MIN := 0.5
const ESCALA_MAX := 0.85

var camera_origem: Camera3D
var escala := 0.67
var ligado := true            # false = aumento bilinear simples (para comparar)
var nitidez := 0.25

var _pequena: SubViewport     # 3D em resolução reduzida
var _cam: Camera3D
var _saida: SubViewport       # EASU no tamanho da tela
var _easu: TextureRect
var _tela: TextureRect        # RCAS, desenhado atrás do painel
var _mat_easu: ShaderMaterial
var _mat_rcas: ShaderMaterial


func _ready() -> void:
	process_priority = 1000   # copia a câmera depois que todo o resto se mexeu no quadro
	_mat_easu = ShaderMaterial.new()
	_mat_easu.shader = load("res://shaders/fsr1_easu.gdshader")
	_mat_rcas = ShaderMaterial.new()
	_mat_rcas.shader = load("res://shaders/fsr1_rcas.gdshader")

	_saida = SubViewport.new()
	_saida.disable_3d = true
	_saida.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_saida)
	# o 3D fica DENTRO da viewport do EASU: assim é desenhado antes dela no mesmo quadro
	_pequena = SubViewport.new()
	_pequena.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_pequena.msaa_3d = Viewport.MSAA_DISABLED
	_pequena.audio_listener_enable_3d = true
	_saida.add_child(_pequena)
	_cam = Camera3D.new()
	_cam.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	_pequena.add_child(_cam)
	_cam.current = true

	_easu = TextureRect.new()
	_easu.texture = _pequena.get_texture()
	_easu.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_easu.stretch_mode = TextureRect.STRETCH_SCALE
	_easu.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	_saida.add_child(_easu)

	var camada := CanvasLayer.new()
	camada.layer = -100
	add_child(camada)
	_tela = TextureRect.new()
	_tela.texture = _saida.get_texture()
	_tela.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_tela.stretch_mode = TextureRect.STRETCH_SCALE
	_tela.set_anchors_preset(Control.PRESET_FULL_RECT)
	_tela.mouse_filter = Control.MOUSE_FILTER_IGNORE
	camada.add_child(_tela)

	var raiz := get_viewport()
	raiz.disable_3d = true
	raiz.audio_listener_enable_3d = false
	get_window().size_changed.connect(_redimensionar)
	_aplicar()
	_redimensionar()


func _process(_d: float) -> void:
	if camera_origem == null or not is_instance_valid(camera_origem):
		return
	var c := camera_origem
	_cam.global_transform = c.get_global_transform_interpolated()
	_cam.projection = c.projection
	_cam.fov = c.fov
	_cam.near = c.near
	_cam.far = c.far
	_cam.h_offset = c.h_offset
	_cam.v_offset = c.v_offset
	_cam.keep_aspect = c.keep_aspect
	_cam.cull_mask = c.cull_mask
	_cam.environment = c.environment
	_cam.attributes = c.attributes


func definir_escala(e: float) -> void:
	escala = clampf(e, ESCALA_MIN, ESCALA_MAX)
	_redimensionar()


func alternar() -> void:
	ligado = not ligado
	_aplicar()


func texto() -> String:
	return ("FSR 1 (AMD)" if ligado else "Bilinear (sem FSR)") + " • 3D em %d%%" % roundi(escala * 100.0)


func _aplicar() -> void:
	_easu.material = _mat_easu if ligado else null
	_tela.material = _mat_rcas if ligado else null
	_mat_rcas.set_shader_parameter("nitidez", nitidez)


func _redimensionar() -> void:
	var tam := get_window().size
	if tam.x < 2 or tam.y < 2:
		return
	_saida.size = tam
	_easu.size = Vector2(tam)
	_easu.position = Vector2.ZERO
	_pequena.size = Vector2i(maxi(16, roundi(tam.x * escala)), maxi(16, roundi(tam.y * escala)))
