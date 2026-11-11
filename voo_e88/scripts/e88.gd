extends RigidBody3D
class_name E88
## Drone dobrável E88 com física de voo de verdade:
## - 4 motores, cada um com empuxo próprio, atraso de resposta e torque de reação (yaw)
## - modo ESTABILIZADO (igual ao E88 real: altitude travada; soltou o controle, ele freia e para no ar)
## - modo ACRO (manual: o controle comanda a velocidade de giro, sem nivelar sozinho)
## - arrasto do ar contra o vento (o vento empurra o drone), efeito solo perto do chão,
##   turbulência perto de paredes/árvores e no próprio vento das hélices
## - colisão: hélice que bate forte quebra e voa longe; pouso brusco também quebra

signal mensagem(texto: String, segundos: float)
signal helice_quebrou(indice: int)
signal bateu(velocidade: float)

# ---------------------------------------------------------------- números do E88
const MASSA := 0.098              # kg (com a bateria)
const T_MAX := 0.62               # N de empuxo máximo por motor (≈ 2,5 vezes o peso no total)
const T_MARCHA_LENTA := 0.035     # N com o drone armado e parado no chão
const TAU_MOTOR := 0.045          # s: o motor demora isso para mudar de rotação
const K_TORQUE := 0.016           # m: torque de reação da hélice por newton de empuxo
const R_HELICE := 0.071           # m: raio da hélice
const RPS_MAX := 210.0            # voltas por segundo da hélice no máximo
const G := 9.8

const INCLINACAO_MAX := deg_to_rad(30.0)   # modo estabilizado
const VEL_MAX_HORIZ := 7.0                 # m/s comandados com o controle no fim
const SUBIDA_MAX := 2.2                    # m/s
const DESCIDA_MAX := 1.6                   # m/s
const GIRO_YAW_MAX := deg_to_rad(160.0)    # °/s no modo estabilizado
const GIRO_ACRO_MAX := deg_to_rad(420.0)   # °/s no modo acro

enum Modo { ESTABILIZADO, ACRO }
var modo := Modo.ESTABILIZADO
var armado := false
var estado := "pousado"     # pousado, decolando, voando, pousando, caido
var auto_alvo_altura := 1.3  # m acima do chão na decolagem automática
var sem_cabeca := false      # modo "sem cabeça" do E88: frente = frente do piloto, não do drone
var frente_piloto := Vector3.FORWARD
var flip_fase := 0           # 0 parado, 1 sobe, 2 gira, 3 recupera
var flip_t := 0.0
var flip_giro := 0.0
var flip_eixo := Vector3.RIGHT

# entradas (-1..1), já com zona morta e expo
var e_acel := 0.0
var e_yaw := 0.0
var e_pitch := 0.0
var e_roll := 0.0

var mapa: Mapa
var vento: Node   # vento.gd
var modelo: Node3D

var motores: Array[Vector3] = []     # posição de cada motor no corpo
var sentido: Array[float] = []       # +1 = hélice gira anti-horário (visto de cima)
var empuxo: Array[float] = [0.0, 0.0, 0.0, 0.0]
var travada: Array[float] = [0.0, 0.0, 0.0, 0.0]   # s que a hélice fica parada depois de raspar
var helice_ok: Array[bool] = [true, true, true, true]
var no_helice: Array[Node3D] = []
var disco: Array[MeshInstance3D] = []
var malhas_helice: Array = []        # malhas de cada hélice (some quando vira disco)
var ang_helice: Array[float] = [0.0, 0.0, 0.0, 0.0]
var rps: Array[float] = [0.0, 0.0, 0.0, 0.0]
var forma_helice: Dictionary = {}    # índice da forma de colisão -> hélice
var forma_pe: Dictionary = {}

var mixer_inv: Array = []            # matriz 4x4 que transforma (empuxo total, torques) em motores
var altura_ref := 0.0
var int_vz := 0.0
var v_anterior := Vector3.ZERO
var altura_chao := 1.0
var chao_y := 0.0
var turb_f := Vector3.ZERO
var turb_t := Vector3.ZERO
var turb_nivel := 0.0
var efeito_solo := 1.0
var tempo_capotado := 0.0
var tempo_no_chao := 0.0
var rng := RandomNumberGenerator.new()
var inercia := Vector3(0.00042, 0.00078, 0.00045)
var ultima_vel_impacto := 0.0
var _passo_turb := 0
var _nivel_paredes := 0.0
var _esteira := 0.0


func preparar(cena_modelo: PackedScene) -> void:
	rng.randomize()
	mass = MASSA
	inertia = inercia
	center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM
	center_of_mass = Vector3.ZERO
	continuous_cd = true
	contact_monitor = true
	max_contacts_reported = 8
	can_sleep = false
	linear_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	angular_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	linear_damp = 0.0
	angular_damp = 0.0
	var pm := PhysicsMaterial.new()
	pm.friction = 0.7
	pm.bounce = 0.12
	physics_material_override = pm

	modelo = cena_modelo.instantiate()
	add_child(modelo)
	# no Blender a frente é -Y, que no glTF vira +Z; no Godot a frente é -Z
	modelo.rotation.y = PI

	_ajustar_materiais(modelo)
	# eixos das hélices vêm do Blender com nomes "Eixo Hélice frente direita" etc.
	var eixos: Array[Node3D] = []
	_achar_eixos(modelo, eixos)
	var centro := Vector3.ZERO
	for e in eixos:
		centro += modelo.transform * e.position
	centro /= maxf(eixos.size(), 1)
	# o centro de massa fica no meio do corpo, uns 2,5 cm acima dos pés
	modelo.position = Vector3(-centro.x, -0.026, -centro.z)

	# ordem fixa: 0 frente-direita, 1 frente-esquerda, 2 trás-esquerda, 3 trás-direita
	var por_pos := {}
	for e in eixos:
		var p := modelo.transform * e.position
		var k := ("F" if p.z < 0 else "T") + ("D" if p.x > 0 else "E")
		por_pos[k] = e
	for k in ["FD", "FE", "TE", "TD"]:
		var e: Node3D = por_pos.get(k)
		if e == null:
			push_error("hélice não encontrada: " + k)
			continue
		no_helice.append(e)
		motores.append(modelo.transform * e.position)
		var m := []
		_coletar_malhas(e, m)
		malhas_helice.append(m)
	# hélices em X: diagonais giram no mesmo sentido (FD e TE anti-horário, FE e TD horário)
	sentido = [1.0, -1.0, 1.0, -1.0]
	_montar_mixer()
	_montar_colisao()
	_montar_discos()


## o glTF não traz o verniz (clearcoat) do Blender: refaz aqui nas peças brilhantes
func _ajustar_materiais(n: Node) -> void:
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if m == null:
				continue
			var nome := m.resource_name
			if nome.begins_with("Preto acetinado") or nome.begins_with("Câmera") or nome.begins_with("Tampa"):
				m.clearcoat_enabled = true
				m.clearcoat = 0.45
				m.clearcoat_roughness = 0.18
			elif nome.begins_with("Lente"):
				m.clearcoat_enabled = true
				m.clearcoat = 1.0
				m.clearcoat_roughness = 0.0
			elif nome.begins_with("LED"):
				m.emission_energy_multiplier = 2.0
				m.rim_enabled = false
	for f in n.get_children():
		_ajustar_materiais(f)


func _achar_eixos(n: Node, lista: Array[Node3D]) -> void:
	if n is Node3D and String(n.name).begins_with("Eixo"):
		lista.append(n)
		return
	for f in n.get_children():
		_achar_eixos(f, lista)


func _coletar_malhas(n: Node, lista: Array) -> void:
	if n is MeshInstance3D:
		lista.append(n)
	for f in n.get_children():
		_coletar_malhas(f, lista)


func _montar_colisao() -> void:
	var i := 0
	# corpo (carcaça)
	_forma(_caixa(Vector3(0.11, 0.04, 0.17)), Vector3(0, 0.0, 0))
	i += 1
	# braços: caixas finas do centro até cada motor
	for m in motores:
		var meio := Vector3(m.x * 0.6, -0.002, m.z * 0.6)
		var cs := CollisionShape3D.new()
		cs.shape = _caixa(Vector3(0.018, 0.016, Vector2(m.x, m.z).length() * 0.8))
		cs.position = meio
		cs.rotation.y = atan2(m.x, m.z)
		add_child(cs)
		i += 1
	# pés (cúpulas do LED): é neles que o drone pousa
	for k in motores.size():
		var m := motores[k]
		var pe := Vector3(m.x * 0.88, -0.026 + 0.012, m.z * 0.88)
		var sph := SphereShape3D.new()
		sph.radius = 0.012
		_forma(sph, pe)
		forma_pe[i] = k
		i += 1
	# discos das hélices (é aqui que costuma bater)
	for k in motores.size():
		var cil := CylinderShape3D.new()
		cil.radius = R_HELICE
		cil.height = 0.008
		_forma(cil, motores[k] + Vector3(0, 0.004, 0))
		forma_helice[i] = k
		i += 1


func _forma(s: Shape3D, pos: Vector3) -> void:
	var cs := CollisionShape3D.new()
	cs.shape = s
	cs.position = pos
	add_child(cs)


func _caixa(t: Vector3) -> BoxShape3D:
	var b := BoxShape3D.new()
	b.size = t
	return b


func _montar_discos() -> void:
	# disco borrado que aparece no lugar das pás quando a hélice gira rápido
	var sh := Shader.new()
	sh.code = """
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;
uniform float forca = 0.0;
uniform float giro = 0.0;
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float a = atan(p.y, p.x) + giro;
	float pas = 0.75 + 0.25 * cos(2.0 * a);
	float perfil = smoothstep(1.0, 0.86, r) * smoothstep(0.08, 0.2, r);
	float ponta = smoothstep(0.7, 0.95, r) * 0.35;
	ALBEDO = vec3(0.04) + ponta * vec3(0.1);
	ALPHA = clamp(forca * perfil * pas * (0.22 + ponta), 0.0, 1.0);
}
"""
	for k in no_helice.size():
		var q := QuadMesh.new()
		q.size = Vector2.ONE * R_HELICE * 2.0
		q.orientation = PlaneMesh.FACE_Y
		var mi := MeshInstance3D.new()
		mi.mesh = q
		var mat := ShaderMaterial.new()
		mat.shader = sh
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		mi.position = motores[k] + Vector3(0, 0.007, 0)
		disco.append(mi)


func _montar_mixer() -> void:
	# empuxo total = soma; torque X = -Σ z·T; torque Z = Σ x·T; torque Y = Σ sentido·K·T
	var m := []
	m.append([1.0, 1.0, 1.0, 1.0])
	m.append(motores.map(func(p): return -p.z))
	m.append(motores.map(func(p): return p.x))
	m.append([-sentido[0] * K_TORQUE, -sentido[1] * K_TORQUE, -sentido[2] * K_TORQUE, -sentido[3] * K_TORQUE])
	mixer_inv = _inverter4(m)


static func _inverter4(a: Array) -> Array:
	var n := 4
	var m := []
	for i in n:
		var linha := []
		for j in n:
			linha.append(float(a[i][j]))
		for j in n:
			linha.append(1.0 if i == j else 0.0)
		m.append(linha)
	for c in n:
		var piv := c
		for r in range(c + 1, n):
			if absf(m[r][c]) > absf(m[piv][c]):
				piv = r
		var tmp = m[c]; m[c] = m[piv]; m[piv] = tmp
		var d: float = m[c][c]
		for j in 2 * n:
			m[c][j] /= d
		for r in n:
			if r != c:
				var f: float = m[r][c]
				for j in 2 * n:
					m[r][j] -= f * m[c][j]
	var inv := []
	for i in n:
		inv.append(m[i].slice(n, 2 * n))
	return inv


func _mixar(total: float, tx: float, tz: float, ty: float) -> Array[float]:
	var v := [total, tx, tz, ty]
	var out: Array[float] = [0.0, 0.0, 0.0, 0.0]
	for i in 4:
		var s := 0.0
		for j in 4:
			s += mixer_inv[i][j] * v[j]
		out[i] = s
	return out


func _cabe(t: Array[float]) -> bool:
	for x in t:
		if x < 0.0 or x > T_MAX:
			return false
	return true


## distribui para os motores; se não couber, abre mão primeiro do yaw e depois de parte do roll/pitch
func _comandar_motores(total: float, tq: Vector3) -> Array[float]:
	total = clampf(total, 0.0, T_MAX * 4.0)
	var t := _mixar(total, tq.x, tq.z, tq.y)
	if not _cabe(t):
		for k: float in [0.6, 0.3, 0.0]:
			t = _mixar(total, tq.x, tq.z, tq.y * k)
			if _cabe(t):
				break
		if not _cabe(t):
			for k: float in [0.8, 0.6, 0.4, 0.2]:
				t = _mixar(total, tq.x * k, tq.z * k, 0.0)
				if _cabe(t):
					break
	for i in 4:
		t[i] = clampf(t[i], 0.0, T_MAX)
	return t


# ---------------------------------------------------------------- comandos

func armar() -> void:
	if estado == "caido":
		return
	armado = true
	altura_ref = global_position.y
	int_vz = 0.0


func desarmar() -> void:
	armado = false
	if estado != "caido":
		estado = "pousado"


func decolar_ou_pousar() -> void:
	if estado == "caido":
		return
	if not armado or estado == "pousado":
		armar()
		estado = "decolando"
		altura_ref = chao_y + auto_alvo_altura + 0.026
		mensagem.emit("Decolagem automática", 1.5)
	elif estado == "voando" or estado == "decolando":
		estado = "pousando"
		mensagem.emit("Pouso automático", 1.5)
	elif estado == "pousando":
		estado = "voando"
		altura_ref = global_position.y


func trocar_modo() -> void:
	modo = Modo.ACRO if modo == Modo.ESTABILIZADO else Modo.ESTABILIZADO
	altura_ref = global_position.y
	int_vz = 0.0
	mensagem.emit("Modo " + nome_modo(), 2.0)


func nome_modo() -> String:
	return "ESTABILIZADO" if modo == Modo.ESTABILIZADO else "ACRO (manual)"


func recomecar(pos: Vector3, yaw := 0.0) -> void:
	PhysicsServer3D.body_set_state(get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM,
		Transform3D(Basis(Vector3.UP, yaw), pos))
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO
	global_transform = Transform3D(Basis(Vector3.UP, yaw), pos)
	armado = false
	estado = "pousado"
	modo = Modo.ESTABILIZADO
	flip_fase = 0
	sem_cabeca = false
	for k in 4:
		empuxo[k] = 0.0
		travada[k] = 0.0
		helice_ok[k] = true
		no_helice[k].visible = true
	v_anterior = Vector3.ZERO
	int_vz = 0.0
	reset_physics_interpolation()


func quebrar_helice(k: int, motivo: String) -> void:
	if not helice_ok[k]:
		return
	helice_ok[k] = false
	empuxo[k] = 0.0
	no_helice[k].visible = false
	disco[k].visible = false
	helice_quebrou.emit(k)
	mensagem.emit("Hélice quebrou! (" + motivo + ")", 3.0)
	_soltar_pedaco(k)


func _soltar_pedaco(k: int) -> void:
	# a hélice quebrada sai voando (corpo físico solto no mapa)
	var rb := RigidBody3D.new()
	rb.mass = 0.002
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = Vector3(0.14, 0.006, 0.014)
	cs.shape = b
	rb.add_child(cs)
	for m in malhas_helice[k]:
		var copia := (m as MeshInstance3D).duplicate()
		rb.add_child(copia)
		copia.transform = no_helice[k].global_transform.affine_inverse() * (m as MeshInstance3D).global_transform
	get_parent().add_child(rb)
	rb.global_transform = no_helice[k].global_transform
	var sai := (global_transform.basis * motores[k]).normalized()
	rb.linear_velocity = linear_velocity + sai * 3.0 + Vector3.UP * 1.5
	rb.angular_velocity = Vector3(rng.randf_range(-30, 30), rng.randf_range(20, 60), rng.randf_range(-30, 30))
	get_tree().create_timer(25.0).timeout.connect(rb.queue_free)


func cair(motivo: String) -> void:
	if estado == "caido":
		return
	estado = "caido"
	armado = false
	mensagem.emit(motivo + " — aperte X (ou R) para recomeçar", 30.0)


# ---------------------------------------------------------------- física

func _integrate_forces(st: PhysicsDirectBodyState3D) -> void:
	var dt := st.step
	var b := st.transform.basis
	var pos := st.transform.origin
	var v := st.linear_velocity
	var w := st.angular_velocity
	var b_inv := b.inverse()
	var w_b := b_inv * w
	var cima := b.y

	_medir_chao(st, pos)
	var h := pos.y - 0.026 - chao_y    # altura dos pés acima do chão

	# ------------------ colisões
	_tratar_contatos(st)

	# ------------------ comando dos motores
	var alvo: Array[float] = [0.0, 0.0, 0.0, 0.0]
	if armado:
		var total := 0.0
		var tq := Vector3.ZERO
		if flip_fase > 0:
			var r := _controle_flip(b, cima, w_b, dt)
			total = r[0]; tq = r[1]
		elif modo == Modo.ESTABILIZADO:
			var r := _controle_estabilizado(b, cima, v, w_b, pos, h, dt)
			total = r[0]; tq = r[1]
		else:
			var r := _controle_acro(w_b)
			total = r[0]; tq = r[1]
		alvo = _comandar_motores(total, tq)
		for k in 4:
			alvo[k] = maxf(alvo[k], T_MARCHA_LENTA)
		if estado == "pousado" and modo == Modo.ESTABILIZADO:
			for k in 4:
				alvo[k] = T_MARCHA_LENTA

	# ------------------ motores (atraso de rotação) e efeito solo
	var a := 1.0 - exp(-dt / TAU_MOTOR)
	efeito_solo = 1.0
	if h < 0.5:
		var hh := maxf(h + 0.01, R_HELICE * 0.3)
		efeito_solo = clampf(1.0 / (1.0 - pow(R_HELICE / (4.0 * hh), 2.0)), 1.0, 1.32)
	var soma := 0.0
	for k in 4:
		if not helice_ok[k]:
			empuxo[k] = 0.0
			continue
		var alvo_k := alvo[k] if armado else 0.0
		if travada[k] > 0.0:
			travada[k] -= dt
			alvo_k = 0.0
		empuxo[k] += (alvo_k - empuxo[k]) * a
		var f := empuxo[k] * efeito_solo
		soma += f
		var ponto := b * motores[k]
		st.apply_force(cima * f, ponto)
		# torque de reação da hélice (é assim que o drone gira no próprio eixo)
		st.apply_torque(cima * (-sentido[k] * K_TORQUE * empuxo[k]))
		rps[k] = RPS_MAX * sqrt(empuxo[k] / T_MAX)

	# ------------------ ar: arrasto contra o vento
	var ar := Vector3.ZERO
	if vento:
		ar = vento.no_ponto(pos, h)
	var vr := v - ar
	var vh := Vector3(vr.x, 0, vr.z)
	var rotor := clampf(soma / (MASSA * G), 0.0, 1.5)
	# hélices girando "seguram" o ar (arrasto do rotor) + arrasto do corpo
	var c1h := 0.012 + 0.036 * rotor
	var c1v := 0.02 + 0.07 * rotor
	var c2 := 0.0065
	var f_ar := -vh * (c1h + c2 * vh.length()) - Vector3(0, vr.y, 0) * (c1v + c2 * absf(vr.y))
	st.apply_central_force(f_ar)
	# o ar amortece os giros
	st.apply_torque(b * (-w_b * 0.00022))

	# ------------------ turbulência (perto de paredes/árvores, no chão e na rajada)
	_turbulencia(st, b, pos, h, rotor, v, dt)

	v_anterior = v

	# ------------------ estado
	_atualizar_estado(cima, h, v, dt, pos)


func _controle_estabilizado(b: Basis, cima: Vector3, v: Vector3, w_b: Vector3, pos: Vector3, h: float, dt: float) -> Array:
	var frente := -b.z
	frente.y = 0.0
	if frente.length() < 0.1:
		frente = b.y
		frente.y = 0.0
		if frente.length() < 0.01:
			frente = Vector3.FORWARD
	frente = frente.normalized()
	if sem_cabeca:
		frente = frente_piloto
	var direita := frente.cross(Vector3.UP)

	# velocidade horizontal desejada pelo controle; soltou = freia até parar
	var v_alvo := (frente * e_pitch + direita * e_roll) * VEL_MAX_HORIZ
	if estado == "decolando" or estado == "pousando" or estado == "pousado":
		v_alvo = Vector3.ZERO
	var vh := Vector3(v.x, 0, v.z)
	var acel_h := (v_alvo - vh) * 2.0
	var lim := G * tan(INCLINACAO_MAX)
	if acel_h.length() > lim:
		acel_h = acel_h.normalized() * lim
	var cima_alvo := (acel_h + Vector3.UP * G).normalized()

	# altura: controle no meio = altura travada
	var vz_alvo := 0.0
	match estado:
		"decolando":
			vz_alvo = clampf((altura_ref - pos.y) * 1.6, -0.6, 1.0)
			if absf(altura_ref - pos.y) < 0.08:
				estado = "voando"
		"pousando":
			vz_alvo = -0.55 if h > 0.6 else -0.35
		_:
			if absf(e_acel) > 0.02:
				vz_alvo = e_acel * (SUBIDA_MAX if e_acel > 0 else DESCIDA_MAX)
				altura_ref = pos.y
			else:
				vz_alvo = clampf((altura_ref - pos.y) * 1.8, -1.0, 1.0)
	if estado == "pousado" and e_acel > 0.3:
		estado = "voando"
		altura_ref = pos.y + 0.3
	var erro_vz := vz_alvo - v.y
	int_vz = clampf(int_vz + erro_vz * dt, -1.5, 1.5)
	var acel_z := erro_vz * 4.5 + int_vz * 2.5
	var cos_inc := maxf(cima.dot(Vector3.UP), 0.5)
	var total := MASSA * (G + acel_z) / cos_inc
	if estado == "pousando" and h < 0.03:
		total *= 0.6

	# atitude: gira o "cima" do drone até o "cima" desejado
	var erro := cima.cross(cima_alvo)
	var erro_b := b.inverse() * erro
	var kp := 300.0
	var kd := 26.0
	var yaw_alvo := -e_yaw * GIRO_YAW_MAX
	var alfa := Vector3(kp * erro_b.x - kd * w_b.x, 9.0 * (yaw_alvo - w_b.y), kp * erro_b.z - kd * w_b.z)
	var tq := alfa * inercia
	return [total, tq]


func fazer_flip(direcao: Vector2) -> void:
	# cambalhota de 360° do E88 (botão de flip): precisa estar voando e com altura
	if not armado or estado != "voando" or flip_fase > 0:
		return
	if global_position.y - chao_y < 1.5:
		mensagem.emit("Suba mais para dar o flip (mínimo 1,5 m)", 1.5)
		return
	if direcao.length() < 0.3:
		direcao = Vector2(0, 1)
	# para frente = gira em volta do eixo X (nariz para baixo); para o lado = eixo Z
	if absf(direcao.y) >= absf(direcao.x):
		flip_eixo = Vector3(-signf(direcao.y), 0, 0)
	else:
		flip_eixo = Vector3(0, 0, -signf(direcao.x))
	flip_fase = 1
	flip_t = 0.0
	flip_giro = 0.0
	mensagem.emit("Flip!", 1.0)


func _controle_flip(b: Basis, cima: Vector3, w_b: Vector3, dt: float) -> Array:
	flip_t += dt
	var paira := MASSA * G
	match flip_fase:
		1:
			# sobe forte e nivelado para ganhar altura antes de girar
			var erro_b := b.inverse() * cima.cross(Vector3.UP)
			var alfa := Vector3(300.0 * erro_b.x - 26.0 * w_b.x, -9.0 * w_b.y, 300.0 * erro_b.z - 26.0 * w_b.z)
			if flip_t > 0.22:
				flip_fase = 2
				flip_t = 0.0
			return [T_MAX * 3.6, alfa * inercia]
		2:
			# perfil de giro: acelera até 1500°/s e freia a tempo de parar nos 360°
			flip_giro += w_b.dot(flip_eixo) * dt
			var falta := TAU - flip_giro
			var w_mod := minf(deg_to_rad(1500.0), sqrt(2.0 * 200.0 * maxf(falta, 0.0)))
			var w_alvo := flip_eixo * w_mod
			if falta < deg_to_rad(12.0) or flip_t > 0.9:
				flip_fase = 3
				flip_t = 0.0
			# gira com toda a diferença de força: um par de motores forte, o outro fraco
			return [T_MAX * 2.0, (w_alvo - w_b) * 60.0 * inercia]
		_:
			# recupera: o modo estabilizado nivela; aqui só dá força para não perder altura
			if flip_t > 0.25:
				flip_fase = 0
				altura_ref = global_position.y
				int_vz = 0.0
			var erro_b := b.inverse() * cima.cross(Vector3.UP)
			var alfa := Vector3(300.0 * erro_b.x - 26.0 * w_b.x, -9.0 * w_b.y, 300.0 * erro_b.z - 26.0 * w_b.z)
			return [paira * 1.5 / maxf(cima.y, 0.4), alfa * inercia]


func trocar_sem_cabeca() -> void:
	sem_cabeca = not sem_cabeca
	var f := -global_transform.basis.z
	f.y = 0.0
	frente_piloto = f.normalized() if f.length() > 0.1 else Vector3.FORWARD
	mensagem.emit("Modo sem cabeça LIGADO: a frente agora é a direção para onde o drone apontava" if sem_cabeca else "Modo sem cabeça desligado", 2.5)


func _controle_acro(w_b: Vector3) -> Array:
	# acelerador: no meio = paira, para cima = mais força, para baixo = menos
	var paira := MASSA * G
	var total := paira * (1.0 + e_acel) if e_acel < 0.0 else paira + e_acel * (T_MAX * 4.0 - paira)
	var w_alvo := Vector3(-e_pitch, -e_yaw * 0.8, -e_roll) * GIRO_ACRO_MAX
	var alfa := (w_alvo - w_b) * 28.0
	return [total, alfa * inercia]


func _medir_chao(st: PhysicsDirectBodyState3D, pos: Vector3) -> void:
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3(0, 0.05, 0), pos + Vector3(0, -60, 0))
	q.exclude = [get_rid()]
	var r := st.get_space_state().intersect_ray(q)
	if r.is_empty():
		chao_y = pos.y - 60.0
	else:
		chao_y = r.position.y


func _tratar_contatos(st: PhysicsDirectBodyState3D) -> void:
	var n := st.get_contact_count()
	if n == 0:
		return
	var b := st.transform.basis
	for i in n:
		var forma := st.get_contact_local_shape(i)
		var normal := st.get_contact_local_normal(i)
		var bater := maxf(-v_anterior.dot(normal), 0.0)
		ultima_vel_impacto = maxf(ultima_vel_impacto, bater)
		if bater > 0.6:
			bateu.emit(bater)
		if forma_helice.has(forma):
			var k: int = forma_helice[forma]
			if helice_ok[k] and empuxo[k] > 0.08:
				if bater > 1.3 or v_anterior.length() > 2.5:
					quebrar_helice(k, "bateu girando")
				elif travada[k] <= 0.0:
					travada[k] = 0.35
					mensagem.emit("A hélice raspou!", 1.2)
		elif bater > 3.2:
			# pancada no corpo: quebra a hélice mais perto de onde bateu
			var ponto_local := b.inverse() * (st.get_contact_local_position(i) - st.transform.origin)
			var melhor := 0
			for k in 4:
				if motores[k].distance_to(ponto_local) < motores[melhor].distance_to(ponto_local):
					melhor = k
			quebrar_helice(melhor, "pancada de %.1f m/s" % bater)
		elif forma_pe.has(forma) and bater > 2.4:
			quebrar_helice(forma_pe[forma], "pouso brusco de %.1f m/s" % bater)


func _turbulencia(st: PhysicsDirectBodyState3D, b: Basis, pos: Vector3, h: float, rotor: float, v: Vector3, dt: float) -> void:
	# perto de paredes, troncos e copas o ar das hélices volta "sujo"
	# (os raios são caros: mede a cada 4 passos e reaproveita)
	_passo_turb += 1
	if _passo_turb % 4 == 0:
		_nivel_paredes = 0.0
		var espaco := st.get_space_state()
		for d: Vector3 in [Vector3.RIGHT, Vector3.LEFT, Vector3.FORWARD, Vector3.BACK, Vector3.UP]:
			var q := PhysicsRayQueryParameters3D.create(pos, pos + d * 1.2)
			q.exclude = [get_rid()]
			var r := espaco.intersect_ray(q)
			if not r.is_empty():
				_nivel_paredes = maxf(_nivel_paredes, 1.0 - pos.distance_to(r.position) / 1.2)
		_esteira = vento.esteira(pos) if vento and vento.has_method("esteira") else 0.0
	var nivel := _nivel_paredes
	# no chão o vento das hélices bate e volta
	if h < 0.35 and armado:
		nivel = maxf(nivel, (1.0 - h / 0.35) * 0.45)
	# atrás do galpão e das árvores o vento vira redemoinho
	if vento:
		nivel = maxf(nivel, _esteira * clampf(vento.velocidade / 5.0, 0.0, 1.0) * 1.2)
	# descendo rápido dentro do próprio vento (anel de vórtice)
	if v.y < -1.5 and rotor > 0.5:
		nivel = maxf(nivel, clampf((-v.y - 1.5) / 1.5, 0.0, 1.0) * 0.8)
	turb_nivel = nivel * maxf(rotor, 0.6)
	# ruído suavizado (não treme quadro a quadro, balança)
	var s := 1.0 - exp(-dt * 9.0)
	turb_f = turb_f.lerp(Vector3(rng.randfn(), rng.randfn() * 0.5, rng.randfn()) * 0.09 * turb_nivel, s)
	turb_t = turb_t.lerp(Vector3(rng.randfn(), rng.randfn() * 0.3, rng.randfn()) * 0.0011 * turb_nivel, s)
	if turb_nivel > 0.01:
		st.apply_central_force(turb_f)
		st.apply_torque(b * turb_t)


func _atualizar_estado(cima: Vector3, h: float, v: Vector3, dt: float, pos: Vector3) -> void:
	if estado == "caido":
		return
	if mapa and mapa.na_agua(pos):
		for k in 4:
			helice_ok[k] = false
		cair("Caiu no açude")
		return
	var no_chao := h < 0.03 and v.length() < 0.25
	tempo_no_chao = tempo_no_chao + dt if no_chao else 0.0
	if cima.y < 0.2 and h < 0.15:
		tempo_capotado += dt
		if tempo_capotado > 0.8:
			cair("Capotou")
			return
	else:
		tempo_capotado = 0.0
	var quebradas := helice_ok.count(false)
	if quebradas > 0 and h < 0.2 and v.length() < 0.6:
		cair("Caiu com hélice quebrada")
		return
	if estado == "pousando" and tempo_no_chao > 0.4:
		desarmar()
		mensagem.emit("Pousou!", 2.0)
	elif estado == "voando" and modo == Modo.ESTABILIZADO and tempo_no_chao > 1.2 and e_acel < -0.3:
		desarmar()
		mensagem.emit("Motores desligados", 1.5)


# ---------------------------------------------------------------- visual das hélices

func _process(delta: float) -> void:
	for k in no_helice.size():
		if not helice_ok[k]:
			continue
		ang_helice[k] = fmod(ang_helice[k] + sentido[k] * rps[k] * TAU * delta, TAU)
		# pás visíveis girando devagar; acima disso viram um disco borrado
		var rapido := clampf((rps[k] - 12.0) / 20.0, 0.0, 1.0)
		var e := no_helice[k]
		e.rotation.y = ang_helice[k] if rapido < 1.0 else e.rotation.y + sentido[k] * delta * 1.7
		for m in malhas_helice[k]:
			(m as MeshInstance3D).visible = rapido < 0.75
		disco[k].visible = rapido > 0.0
		(disco[k].material_override as ShaderMaterial).set_shader_parameter("forca", lerpf(0.5, 1.0, rapido) * rapido)
		(disco[k].material_override as ShaderMaterial).set_shader_parameter("giro", ang_helice[k] * 0.02)


func velocidade_vento_relativo() -> Vector3:
	return linear_velocity - (vento.no_ponto(global_position, global_position.y - chao_y) if vento else Vector3.ZERO)
