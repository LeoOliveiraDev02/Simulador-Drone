extends Node
class_name Benchmark
## Teste automático de desempenho. Liga quando existe "benchmark.txt" ao lado do executável
## (ou com --benchmark). Passa por vistas fixas em cada qualidade gráfica, mede o FPS e salva
## benchmark_resultado.txt e prints bench_*.jpg na mesma pasta; depois fecha o jogo.

var voo: Node
var pasta := ""
var linhas: PackedStringArray = []

const VISTAS := [
	# nome, posição (x, altura acima do chão, z), olhar para (x, z)
	["partida_casa", Vector3(0, 2.0, 0), Vector2(-47, -60)],
	["partida_eucaliptos", Vector3(0, 3.0, 0), Vector2(-150, -240)],
	["partida_oposto", Vector3(0, 2.0, 0), Vector2(60, 200)],
	["alto_mapa", Vector3(10, 45.0, 30), Vector2(-60, -160)],
	["perto_arvore", Vector3(-24, 3.0, -8), Vector2(-33, -20)],
	["perto_galpao", Vector3(-30, 4.0, -45), Vector2(-47, -60)],
]


static func ativo() -> bool:
	if "--benchmark" in OS.get_cmdline_user_args() or "--benchmark" in OS.get_cmdline_args():
		return true
	var f := OS.get_executable_path().get_base_dir().path_join("benchmark.txt")
	return FileAccess.file_exists(f) and FileAccess.get_file_as_string(f).strip_edges().begins_with("rodar")


func rodar() -> void:
	pasta = OS.get_executable_path().get_base_dir()
	if OS.has_feature("editor"):
		pasta = ProjectSettings.globalize_path("res://prints")
		DirAccess.make_dir_recursive_absolute(pasta)
	var vp := get_viewport()
	_linha("Simulador de Drone E88 — benchmark  %s" % Time.get_datetime_string_from_system())
	_linha("GPU: %s | driver: %s | %s" % [RenderingServer.get_video_adapter_name(), RenderingServer.get_video_adapter_api_version(), RenderingServer.get_current_rendering_driver_name()])
	_linha("Tela: %s | escala 3D: %.2f | modo: %d" % [str(vp.get_visible_rect().size), vp.scaling_3d_scale, vp.scaling_3d_mode])
	_linha("FSR: %s" % str(ProjectSettings.get_setting("rendering/amd_fsr/status", "")))
	_linha("Gerador de quadros pedido: %s" % str(ProjectSettings.get_setting("rendering/amd_fsr/frame_generation", false)))
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	var drone: RigidBody3D = voo.drone
	drone.freeze = true
	await _esperar(2.0)
	for q in [3, 2, 1, 0]:
		voo.qualidade_pc = q
		voo.mapa.nivel_grafico_pc(q)
		_linha("")
		_linha("=== Qualidade %s ===" % ["BAIXA", "MÉDIA", "ALTA", "ULTRA"][q])
		for v in VISTAS:
			var p: Vector3 = v[1]
			var alvo: Vector2 = v[2]
			var chao: float = voo.mapa.altura(p.x, p.z)
			var yaw := atan2(-(alvo.x - p.x), -(alvo.y - p.z))
			drone.global_transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(p.x, chao + p.y, p.z))
			voo.camera.posicionar_ja()
			await _esperar(2.5)
			var r := await _medir(4.0)
			var info := "prims=%dk draws=%d" % [RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME) / 1000, RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)]
			_linha("%-20s média %5.1f FPS | pior 1%% %5.1f FPS | %s | VRAM %d MB" % [v[0], r[0], r[1], info, RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / 1048576])
			if q == 2 or v[0] == "partida_casa":
				var img := get_viewport().get_texture().get_image()
				img.resize(img.get_width() / 2, img.get_height() / 2)
				img.save_jpg(pasta.path_join("bench_q%d_%s.jpg" % [q, v[0]]), 0.85)
	_linha("")
	_linha("FSR no fim: %s" % str(ProjectSettings.get_setting("rendering/amd_fsr/status", "")))
	_salvar()
	# mostra o resultado na tela por 2 minutos (para conferir com um print) e fecha
	var cl := CanvasLayer.new()
	cl.layer = 100
	add_child(cl)
	var fundo := ColorRect.new()
	fundo.color = Color(0, 0, 0, 0.92)
	fundo.set_anchors_preset(Control.PRESET_FULL_RECT)
	cl.add_child(fundo)
	var lb := Label.new()
	lb.text = "\n".join(linhas)
	lb.position = Vector2(30, 20)
	lb.add_theme_font_size_override("font_size", 22)
	lb.add_theme_font_override("font", SystemFont.new())
	cl.add_child(lb)
	var mono := SystemFont.new()
	mono.font_names = PackedStringArray(["Consolas", "Courier New", "monospace"])
	lb.add_theme_font_override("font", mono)
	await _esperar(120.0)
	get_tree().quit()


func _esperar(s: float) -> void:
	await get_tree().create_timer(s, true, false, true).timeout


func _medir(s: float) -> Array:
	var tempos: Array[float] = []
	var t0 := Time.get_ticks_usec()
	var ant := t0
	while Time.get_ticks_usec() - t0 < int(s * 1e6):
		await get_tree().process_frame
		var agora := Time.get_ticks_usec()
		tempos.append(float(agora - ant) / 1e6)
		ant = agora
	if tempos.is_empty():
		return [0.0, 0.0]
	var soma := 0.0
	for t in tempos:
		soma += t
	var media := tempos.size() / soma
	tempos.sort()
	var n := maxi(1, tempos.size() / 100)
	var pior := 0.0
	for i in n:
		pior += tempos[tempos.size() - 1 - i]
	pior = n / pior
	return [media, pior]


func _linha(t: String) -> void:
	linhas.append(t)
	print(t)
	_salvar()


func _salvar() -> void:
	var f := FileAccess.open(pasta.path_join("benchmark_resultado.txt"), FileAccess.WRITE)
	if f:
		f.store_string("\n".join(linhas) + "\n")
