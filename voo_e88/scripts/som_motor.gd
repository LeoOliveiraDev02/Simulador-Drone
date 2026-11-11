extends AudioStreamPlayer3D
class_name SomMotor
## Zumbido dos 4 motores do E88, gerado na hora: o tom sobe com a rotação de cada hélice
## (frequência da passagem das pás + chiado do motor escovado) e o volume com a força.

var drone: E88
var gerador: AudioStreamGeneratorPlayback
var fase_pa: Array[float] = [0.0, 0.0, 0.0, 0.0]
var fase_motor: Array[float] = [0.0, 0.0, 0.0, 0.0]
var amp: Array[float] = [0.0, 0.0, 0.0, 0.0]
var freq: Array[float] = [0.0, 0.0, 0.0, 0.0]
var taxa := 16000.0
var rng := RandomNumberGenerator.new()
var ruido_filtrado := 0.0
var batida := 0.0        # energia do som de pancada (decai rápido)
var batida_tom := 0.0


func _ready() -> void:
	if OS.has_feature("mobile"):
		taxa = 11025.0
	var s := AudioStreamGenerator.new()
	s.mix_rate = taxa
	s.buffer_length = 0.12
	stream = s
	unit_size = 1.2
	max_db = 2.0
	attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	max_distance = 120.0
	doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_PHYSICS_STEP
	play()
	gerador = get_stream_playback()


func _process(_delta: float) -> void:
	if drone == null or gerador == null:
		return
	for k in 4:
		var t := drone.empuxo[k] / E88.T_MAX
		# alvo suave para não estalar
		var a_alvo := 0.0 if not drone.helice_ok[k] else clampf(sqrt(t) * 0.22, 0.0, 0.3)
		amp[k] = lerpf(amp[k], a_alvo, 0.2)
		freq[k] = lerpf(freq[k], drone.rps[k], 0.25)
	var n := gerador.get_frames_available()
	var inv := 1.0 / taxa
	for i in n:
		var s := 0.0
		for k in 4:
			if amp[k] < 0.001:
				continue
			# 2 pás = 2 pulsos por volta; motor escovado com engrenagem: chiado agudo (x7)
			fase_pa[k] = fmod(fase_pa[k] + freq[k] * 2.0 * inv, 1.0)
			fase_motor[k] = fmod(fase_motor[k] + freq[k] * 7.3 * inv, 1.0)
			var pa := (fase_pa[k] * 2.0 - 1.0) * 0.55 + sin(fase_pa[k] * TAU) * 0.45
			var mot := sin(fase_motor[k] * TAU) * 0.35
			s += (pa + mot) * amp[k]
		ruido_filtrado = lerpf(ruido_filtrado, rng.randf_range(-1.0, 1.0), 0.35)
		var total_amp := amp[0] + amp[1] + amp[2] + amp[3]
		s += ruido_filtrado * total_amp * 0.35
		if batida > 0.001:
			# pancada de plástico: ruído grave que some rápido
			batida_tom = lerpf(batida_tom, rng.randf_range(-1.0, 1.0), 0.12)
			s += batida_tom * batida * 2.2
			batida *= 0.9985
		gerador.push_frame(Vector2(s, s))


func impacto(forca: float) -> void:
	batida = clampf(batida + forca * 0.25, 0.0, 0.6)
