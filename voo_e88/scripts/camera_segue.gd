extends Camera3D
class_name CameraSegue
## Câmera que segue atrás do drone, suave, sem atravessar o chão nem paredes.

var alvo: RigidBody3D
var distancia := 0.85
var altura := 0.32
var yaw := 0.0
var _pos := Vector3.ZERO
var iniciada := false
var olhar_yaw := 0.0      # olhar em volta arrastando o dedo (ou o botão direito do mouse)
var olhar_pitch := 0.0
var olhando := false


func _ready() -> void:
	fov = 62.0
	near = 0.02
	far = 6000.0


func posicionar_ja() -> void:
	if alvo == null:
		return
	yaw = _yaw_do_drone()
	_pos = _desejada()
	global_position = _pos
	look_at(alvo.global_position + Vector3(0, 0.05, 0), Vector3.UP)
	iniciada = true
	reset_physics_interpolation()


func _yaw_do_drone() -> float:
	# de cabeça para baixo (flip, capotando) a "frente" inverte: segura a câmera onde está
	if alvo.global_transform.basis.y.y < 0.4:
		return yaw
	var f := -alvo.global_transform.basis.z
	f.y = 0.0
	if f.length() < 0.05:
		return yaw
	return atan2(-f.x, -f.z)


func _desejada() -> Vector3:
	var y := yaw + olhar_yaw
	var atras := Vector3(sin(y), 0, cos(y))
	var base := alvo.global_position + atras * distancia + Vector3.UP * (altura + distancia * 0.12)
	if absf(olhar_pitch) < 0.001:
		return base
	# inclina a órbita para cima/baixo em volta do drone
	var rel := base - alvo.global_position
	var eixo := atras.cross(Vector3.UP).normalized()
	return alvo.global_position + rel.rotated(eixo, olhar_pitch)


func olhar(delta_px: Vector2) -> void:
	olhar_yaw = wrapf(olhar_yaw - delta_px.x * 0.006, -PI, PI)
	olhar_pitch = clampf(olhar_pitch + delta_px.y * 0.004, -0.5, 1.1)


func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton and ev.button_index == MOUSE_BUTTON_RIGHT:
		olhando = ev.pressed
	elif ev is InputEventMouseMotion and olhando:
		olhar(ev.relative)


func _physics_process(delta: float) -> void:
	if alvo == null:
		return
	if not iniciada:
		posicionar_ja()
	# acompanha o giro do drone com um pouco de atraso (fica natural)
	var vel := alvo.linear_velocity
	var y_alvo := _yaw_do_drone()
	yaw = lerp_angle(yaw, y_alvo, 1.0 - exp(-delta * 2.6))
	# soltou o dedo: a câmera volta devagar para trás do drone
	if not olhando:
		var k := 1.0 - exp(-delta * 1.2)
		olhar_yaw = lerpf(olhar_yaw, 0.0, k)
		olhar_pitch = lerpf(olhar_pitch, 0.0, k)
	var desejada := _desejada()
	_pos = _pos.lerp(desejada, 1.0 - exp(-delta * (6.0 + vel.length() * 0.6)))
	# não deixa a câmera entrar em parede, árvore ou no chão
	var espaco := get_world_3d().direct_space_state
	var origem := alvo.global_position + Vector3(0, 0.08, 0)
	var q := PhysicsRayQueryParameters3D.create(origem, _pos)
	q.exclude = [alvo.get_rid()]
	var r := espaco.intersect_ray(q)
	var final := _pos
	if not r.is_empty():
		final = r.position + (origem - r.position).normalized() * 0.08
	var q2 := PhysicsRayQueryParameters3D.create(final + Vector3(0, 3, 0), final + Vector3(0, -3, 0))
	q2.exclude = [alvo.get_rid()]
	var r2 := espaco.intersect_ray(q2)
	if not r2.is_empty() and final.y < r2.position.y + 0.12:
		final.y = r2.position.y + 0.12
	global_position = final
	var olhar := alvo.global_position + Vector3(0, 0.04, 0)
	if global_position.distance_to(olhar) > 0.05:
		look_at(olhar, Vector3.UP)


func afastar(d: float) -> void:
	distancia = clampf(distancia + d, 0.5, 6.0)
