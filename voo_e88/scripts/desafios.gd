extends Node3D
class_name Desafios
## Desafios do mapa: balões, entrega de pacote, pouso de precisão e corrida dos portais.
## Escolha no menu (Esc) ou com a tecla J. Os recordes ficam salvos.

const NOMES := ["VOO LIVRE", "ESTOURAR OS BALÕES", "ENTREGA DE PACOTE", "POUSO DE PRECISÃO", "CORRIDA DOS PORTAIS"]
const RECORDES := "user://recordes.cfg"
const QTD_BALOES := 15

var voo: Node
var mapa: Mapa
var drone: E88
var modo := 0
var tempo := -1.0
var feitos := 0
var total := 0
var baloes: Array = []        # [nó, centro, fase]
var estouros: Array = []      # [nó, tempo]
var pacote: Node3D
var pacote_preso := false
var alvo: Node3D
var alvo_pos := Vector3.ZERO
var entregas_pos: Array = []
var pousos: Array = []        # [nome, ponto]
var marcador: Node3D
var notas: Array = []
var portais_inicio := 0
var _pousado_antes := true
var rng := RandomNumberGenerator.new()


func iniciar(m: int) -> void:
	_limpar()
	modo = m
	tempo = -1.0
	feitos = 0
	total = 0
	notas.clear()
	rng.randomize()
	if modo != 0:
		voo._recomecar()
	match modo:
		1: _iniciar_baloes()
		2: _iniciar_entrega()
		3: _iniciar_pouso()
		4:
			total = mapa.portais.size()
			portais_inicio = voo.portais_feitos
	if modo != 0:
		voo.hud.mostrar("Desafio: " + NOMES[modo] + "  —  " + _dica(), 5.0)


func _dica() -> String:
	match modo:
		1: return "passe por dentro dos %d balões o mais rápido que puder" % QTD_BALOES
		2: return "pouse em cima do caixote perto do galpão, pegue o pacote e leve até o anel verde"
		3: return "pouse bem no centro de cada marca amarela"
		4: return "passe por todos os portais laranja"
	return ""


func _limpar() -> void:
	for b in baloes:
		if is_instance_valid(b[0]):
			b[0].queue_free()
	baloes.clear()
	for n in [pacote, alvo, marcador]:
		if n and is_instance_valid(n):
			n.queue_free()
	pacote = null
	alvo = null
	marcador = null
	pacote_preso = false
	if drone:
		drone.peso_extra = 0.0


# ------------------------------------------------------------- balões

func _mat(cor: Color, emissao := 0.0, alfa := 1.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(cor.r, cor.g, cor.b, alfa)
	m.roughness = 0.25
	m.metallic_specular = 0.7
	if alfa < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if emissao > 0.0:
		m.emission_enabled = true
		m.emission = cor
		m.emission_energy_multiplier = emissao
	return m


func _iniciar_baloes() -> void:
	var cores := [Color(0.95, 0.15, 0.15), Color(0.15, 0.45, 0.95), Color(1.0, 0.8, 0.1), Color(0.2, 0.8, 0.3), Color(0.9, 0.3, 0.8), Color(1.0, 0.5, 0.1)]
	var esfera := SphereMesh.new()
	esfera.radius = 0.45
	esfera.height = 1.1
	var fio := CylinderMesh.new()
	fio.top_radius = 0.004
	fio.bottom_radius = 0.004
	fio.height = 1.6
	var mat_fio := _mat(Color(0.9, 0.9, 0.9))
	total = QTD_BALOES
	var tentativas := 0
	while baloes.size() < QTD_BALOES and tentativas < 500:
		tentativas += 1
		var ang := rng.randf() * TAU
		var r := rng.randf_range(12.0, 140.0)
		var x := cos(ang) * r
		var z := sin(ang) * r - 40.0
		if Vector2(x, z).distance_to(mapa.GALPAO_C) < 14.0:
			continue
		var y := mapa.altura(x, z) + rng.randf_range(2.5, 22.0)
		if mapa.folhagem_em(Vector3(x, y, z)) > 0.0:
			continue
		var no := Node3D.new()
		add_child(no)
		no.position = Vector3(x, y, z)
		var mi := MeshInstance3D.new()
		mi.mesh = esfera
		mi.material_override = _mat(cores[baloes.size() % cores.size()], 0.15)
		no.add_child(mi)
		var f := MeshInstance3D.new()
		f.mesh = fio
		f.material_override = mat_fio
		f.position.y = -1.35
		no.add_child(f)
		baloes.append([no, no.position, rng.randf() * TAU])


func _atualizar_baloes(delta: float, p: Vector3) -> void:
	var mais_perto := INF
	var dir_perto := Vector3.ZERO
	for i in range(baloes.size() - 1, -1, -1):
		var b: Array = baloes[i]
		var no: Node3D = b[0]
		b[2] += delta
		no.position = b[1] + Vector3(sin(b[2] * 0.7) * 0.25, sin(b[2] * 1.1) * 0.35, cos(b[2] * 0.6) * 0.25)
		no.rotation.y += delta * 0.3
		var d := p.distance_to(no.position)
		if d < 0.85:
			_estourar(no)
			baloes.remove_at(i)
			feitos += 1
			if tempo < 0.0:
				tempo = 0.0
			voo._vibrar(0.35, 0.15)
			if feitos >= total:
				_terminou("Estourou os %d balões" % total, tempo)
			continue
		if d < mais_perto:
			mais_perto = d
			dir_perto = no.position - p
	if baloes.size() > 0:
		voo.hud.missao.text = "BALÕES  %d/%d   •   %s   •   o mais perto: %s %d m%s" % [feitos, total, _tempo_txt(), _seta(dir_perto), roundi(mais_perto), _recorde_txt()]


func _estourar(no: Node3D) -> void:
	# o balão some num estalo: cresce rápido e fica transparente, soltando pedacinhos
	var mi: MeshInstance3D = no.get_child(0)
	var mat := mi.material_override as StandardMaterial3D
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var tw := create_tween()
	tw.set_parallel(true)
	tw.tween_property(mi, "scale", Vector3.ONE * 1.8, 0.12)
	tw.tween_property(mat, "albedo_color:a", 0.0, 0.12)
	var part := CPUParticles3D.new()
	part.one_shot = true
	part.emitting = true
	part.amount = 40
	part.lifetime = 1.4
	part.explosiveness = 1.0
	part.direction = Vector3.UP
	part.spread = 180.0
	part.initial_velocity_min = 2.0
	part.initial_velocity_max = 5.0
	part.gravity = Vector3(0, -6, 0)
	var pm := BoxMesh.new()
	pm.size = Vector3(0.05, 0.05, 0.005)
	part.mesh = pm
	part.material_override = _mat(mat.albedo_color)
	no.add_child(part)
	get_tree().create_timer(1.6).timeout.connect(no.queue_free)


# ------------------------------------------------------------- entrega

func _caixote() -> Node3D:
	var no: Node3D = mapa._cena("wooden_crate_01", "orig").instantiate()
	no.scale = Vector3.ONE * 0.22
	return no


func _iniciar_entrega() -> void:
	total = 3
	pacote = _caixote()
	add_child(pacote)
	var g: Vector2 = mapa.GALPAO_C
	var px := g.x + 14.0
	var pz := g.y + 2.0
	pacote.position = Vector3(px, mapa.altura(px, pz), pz)
	entregas_pos = [Vector2(28, -30), Vector2(-20, -100), Vector2(45, -90), Vector2(-75, -10), Vector2(10, 35), Vector2(-40, -150)]
	entregas_pos.shuffle()
	_novo_alvo()


func _novo_alvo() -> void:
	if alvo and is_instance_valid(alvo):
		alvo.queue_free()
	var q: Vector2 = entregas_pos[feitos % entregas_pos.size()]
	alvo_pos = Vector3(q.x, mapa.altura(q.x, q.y), q.y)
	alvo = _anel(Color(0.2, 1.0, 0.35), 1.3)
	alvo.position = alvo_pos
	add_child(alvo)


func _anel(cor: Color, raio: float) -> Node3D:
	var no := Node3D.new()
	var t := TorusMesh.new()
	t.inner_radius = raio - 0.08
	t.outer_radius = raio
	t.rings = 48
	var mi := MeshInstance3D.new()
	mi.mesh = t
	mi.material_override = _mat(cor, 2.5)
	mi.position.y = 0.05
	no.add_child(mi)
	# coluna de luz para achar de longe
	var c := CylinderMesh.new()
	c.top_radius = raio * 0.9
	c.bottom_radius = raio
	c.height = 30.0
	var col := MeshInstance3D.new()
	col.mesh = c
	var m := _mat(cor, 1.2, 0.12)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	col.material_override = m
	col.position.y = 15.0
	col.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	no.add_child(col)
	return no


func _atualizar_entrega(_delta: float, p: Vector3) -> void:
	var pousado := drone.estado == "pousado"
	if not pacote_preso and pacote and is_instance_valid(pacote):
		var hp := Vector2(p.x - pacote.position.x, p.z - pacote.position.z).length()
		if hp < 0.9 and p.y - pacote.position.y < 1.2 and (pousado or drone.global_position.y - pacote.position.y < 0.45):
			pacote_preso = true
			pacote.get_parent().remove_child(pacote)
			drone.add_child(pacote)
			pacote.position = Vector3(0, -0.13, 0)
			pacote.rotation = Vector3.ZERO
			pacote.scale = Vector3.ONE * 0.22 / drone.scale.x
			drone.peso_extra = 0.035
			if tempo < 0.0:
				tempo = 0.0
			voo.hud.mostrar("Pacote preso! Ele pesa 35 g: o E88 fica mais lento. Leve até o anel verde.", 3.5)
	if pacote_preso:
		var d := Vector2(p.x - alvo_pos.x, p.z - alvo_pos.z).length()
		if pousado and not _pousado_antes and d < 1.3:
			feitos += 1
			notas.append(d)
			pacote_preso = false
			drone.peso_extra = 0.0
			drone.remove_child(pacote)
			add_child(pacote)
			pacote.scale = Vector3.ONE * 0.22
			pacote.global_position = Vector3(p.x + 0.4, mapa.altura(p.x + 0.4, p.z), p.z)
			if feitos >= total:
				_terminou("Entregou os %d pacotes" % total, tempo)
				return
			voo.hud.mostrar("Entregue a %d cm do centro! Pegue o pacote de novo e vá ao próximo anel." % roundi(d * 100.0), 3.5)
			_novo_alvo()
	var destino := alvo_pos if pacote_preso else (pacote.position if pacote else alvo_pos)
	var dir := destino - p
	voo.hud.missao.text = "ENTREGA  %d/%d   •   %s   •   %s %s %d m%s" % [feitos, total, _tempo_txt(), "anel verde:" if pacote_preso else "pacote:", _seta(dir), roundi(Vector2(dir.x, dir.z).length()), _recorde_txt()]
	_pousado_antes = pousado


# ------------------------------------------------------------- pouso de precisão

func _iniciar_pouso() -> void:
	pousos = mapa.pontos_pouso.duplicate()
	pousos.append(["base (H)", Vector3(0, mapa.altura_centro, 0)])
	total = pousos.size()
	_novo_marcador()


func _novo_marcador() -> void:
	if marcador and is_instance_valid(marcador):
		marcador.queue_free()
	var alvo_p: Vector3 = pousos[feitos][1]
	marcador = _anel(Color(1.0, 0.85, 0.1), 0.55)
	marcador.position = alvo_p + Vector3(0, 0.01, 0)
	add_child(marcador)


func _atualizar_pouso(_delta: float, p: Vector3) -> void:
	if feitos >= total:
		return
	var nome: String = pousos[feitos][0]
	var alvo_p: Vector3 = pousos[feitos][1]
	var pousado := drone.estado == "pousado"
	if pousado and not _pousado_antes:
		var d := Vector2(p.x - alvo_p.x, p.z - alvo_p.z).length()
		if d < 0.6 and absf(p.y - alvo_p.y) < 0.5:
			if tempo < 0.0:
				tempo = 0.0
			feitos += 1
			notas.append(d)
			var nota := "PERFEITO" if d < 0.08 else ("ótimo" if d < 0.2 else "bom")
			if feitos >= total:
				var media := 0.0
				for n in notas:
					media += n
				media /= notas.size()
				_terminou("Pousos de precisão: média de %d cm do centro" % roundi(media * 100.0), tempo)
				return
			voo.hud.mostrar("Pouso %s em %s: %d cm do centro!" % [nota, nome, roundi(d * 100.0)], 3.5)
			_novo_marcador()
		elif d < 3.0:
			voo.hud.mostrar("Quase! Pousou a %d cm. Precisa ficar dentro do anel amarelo." % roundi(d * 100.0), 2.5)
	if tempo >= 0.0 or feitos == 0:
		var dir := alvo_p - p
		voo.hud.missao.text = "POUSO DE PRECISÃO  %d/%d   •   %s   •   %s: %s %d m%s" % [feitos, total, _tempo_txt(), nome, _seta(dir), roundi(Vector2(dir.x, dir.z).length()), _recorde_txt()]
	_pousado_antes = pousado


# ------------------------------------------------------------- comum

func atualizar(delta: float) -> void:
	if modo == 0 or drone == null:
		return
	if tempo >= 0.0:
		tempo += delta
	var p := drone.global_position
	match modo:
		1: _atualizar_baloes(delta, p)
		2: _atualizar_entrega(delta, p)
		3: _atualizar_pouso(delta, p)
		4:
			feitos = voo.portais_feitos - portais_inicio
			if feitos > 0 and tempo < 0.0:
				tempo = 0.0
			voo.hud.missao.text = "CORRIDA DOS PORTAIS  %d/%d   •   %s%s" % [mini(feitos, total), total, _tempo_txt(), _recorde_txt()]
			if feitos >= total:
				_terminou("Passou pelos %d portais" % total, tempo)


func _terminou(texto: String, t: float) -> void:
	var cfg := ConfigFile.new()
	cfg.load(RECORDES)
	var chave := "modo_%d" % modo
	var antigo := float(cfg.get_value("recordes", chave, 0.0))
	var novo_recorde := antigo <= 0.0 or t < antigo
	if novo_recorde:
		cfg.set_value("recordes", chave, t)
		cfg.save(RECORDES)
	voo.hud.mostrar("%s em %s!%s  (J ou Esc: outro desafio)" % [texto, _fmt(t), "  NOVO RECORDE!" if novo_recorde else "  Recorde: " + _fmt(antigo)], 8.0)
	voo._vibrar(0.6, 0.4)
	var m := modo
	_limpar()
	modo = 0
	voo.hud.missao.text = ""
	if m == 2 and pacote == null:
		pass


func _recorde_txt() -> String:
	var cfg := ConfigFile.new()
	if cfg.load(RECORDES) != OK:
		return ""
	var r := float(cfg.get_value("recordes", "modo_%d" % modo, 0.0))
	return "" if r <= 0.0 else "   •   recorde " + _fmt(r)


func _tempo_txt() -> String:
	return "⏱ " + (_fmt(tempo) if tempo >= 0.0 else "0:00.0")


func _fmt(t: float) -> String:
	return "%d:%04.1f" % [int(t) / 60, fmod(t, 60.0)]


func _seta(dir: Vector3) -> String:
	# direção em relação à câmera: ↑ em frente, ← esquerda, → direita, ↓ atrás; ▲▼ acima/abaixo
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam == null:
		return ""
	var f := -cam.global_transform.basis.z
	f.y = 0.0
	f = f.normalized()
	var r := cam.global_transform.basis.x
	r.y = 0.0
	r = r.normalized()
	var a := atan2(dir.dot(r), dir.dot(f))
	var s := "↑"
	if absf(a) > 2.4:
		s = "↓"
	elif a > 0.6:
		s = "→"
	elif a < -0.6:
		s = "←"
	if dir.y > 3.0:
		s += "▲"
	elif dir.y < -3.0:
		s += "▼"
	return s
