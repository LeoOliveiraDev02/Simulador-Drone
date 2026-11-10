extends Node
class_name Vento
## Vento do mapa: direção e força ajustáveis, com rajadas que mudam no tempo e no espaço.
## Perto do chão o vento é mais fraco (atrito com o capim), como na vida real.

var velocidade := 2.5          # m/s a 10 m de altura
var direcao := deg_to_rad(35)  # para onde o vento sopra (0 = +Z)
var rajadas := true
var tempo := 0.0
var ruido := FastNoiseLite.new()
var ruido_dir := FastNoiseLite.new()
var rajada_atual := 0.0         # 0..1 (para a grama e a biruta)


func _ready() -> void:
	ruido.seed = 5
	ruido.frequency = 0.08
	ruido.fractal_octaves = 3
	ruido_dir.seed = 9
	ruido_dir.frequency = 0.03


func _physics_process(delta: float) -> void:
	tempo += delta
	rajada_atual = clampf(ruido.get_noise_2d(tempo, 0.0) * 0.5 + 0.5, 0.0, 1.0)


func no_ponto(p: Vector3, altura_chao: float) -> Vector3:
	if velocidade <= 0.01:
		return Vector3.ZERO
	# perfil do vento: fraco rente ao chão, forte lá em cima (rugosidade do pasto 3 cm)
	var h := clampf(altura_chao, 0.05, 120.0)
	var perfil := clampf(log(h / 0.03) / log(10.0 / 0.03), 0.3, 1.35)
	var forca := velocidade * perfil
	var dir := direcao
	if rajadas:
		# a rajada chega com atraso conforme a posição (ela "passa" pelo mapa)
		var fase := (p.x * sin(direcao) + p.z * cos(direcao)) / maxf(velocidade, 1.0) * 0.6
		var r := ruido.get_noise_2d(tempo - fase, p.x * 0.01 + p.z * 0.01)
		forca *= 1.0 + 0.55 * r
		dir += ruido_dir.get_noise_2d(tempo, 7.0) * 0.45
	return Vector3(sin(dir), 0.0, cos(dir)) * maxf(forca, 0.0)


func texto() -> String:
	if velocidade <= 0.01:
		return "sem vento"
	return "%.1f m/s (%d km/h)%s" % [velocidade, roundi(velocidade * 3.6), " com rajadas" if rajadas else ""]
