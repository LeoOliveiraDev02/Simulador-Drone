extends Camera3D
class_name CameraSegue
## Câmera que segue atrás do drone, suave, sem atravessar o chão nem paredes.

var alvo: RigidBody3D
var distancia := 1.25
var altura := 0.38
var yaw := 0.0
var _pos := Vector3.ZERO
var iniciada := false


func _ready() -> void:
	fov = 68.0
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


func _yaw_do_drone() -> float:
	var f := -alvo.global_transform.basis.z
	f.y = 0.0
	if f.length() < 0.05:
		return yaw
	return atan2(-f.x, -f.z)


func _desejada() -> Vector3:
	var atras := Vector3(sin(yaw), 0, cos(yaw))
	return alvo.global_position + atras * distancia + Vector3.UP * (altura + distancia * 0.12)


func _physics_process(delta: float) -> void:
	if alvo == null:
		return
	if not iniciada:
		posicionar_ja()
	# acompanha o giro do drone com um pouco de atraso (fica natural)
	var vel := alvo.linear_velocity
	var y_alvo := _yaw_do_drone()
	yaw = lerp_angle(yaw, y_alvo, 1.0 - exp(-delta * 2.6))
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
