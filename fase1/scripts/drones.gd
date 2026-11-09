class_name Drones
extends RefCounted
## Monta cada drone: carrega o modelo CAD (modelos/<id>.glb), transforma cada
## grupo "chave__N" numa peça clicável, melhora os materiais e completa com
## as peças que o CAD não trazia (feitas pelo Kit).

var kit := Kit.new()

const ROTULOS_POSICAO_4 := ["frente direita", "trás direita", "trás esquerda", "frente esquerda"]


const PASTA_FINAL := "res://modelos/final/"
var usar_final := true


func montar(id: String) -> Node3D:
	if usar_final and ResourceLoader.exists(PASTA_FINAL + id + ".glb"):
		return montar_final(id)
	return montar_cad(id)


func montar_cad(id: String) -> Node3D:
	if id == "whoop65":
		return _montar_whoop()
	var raiz := Node3D.new()
	raiz.name = id
	var cena: PackedScene = load("res://modelos/%s.glb" % id)
	var modelo := cena.instantiate()
	var pecas := {}
	for filho in modelo.find_children("*", "MeshInstance3D", true, false):
		var mi := filho as MeshInstance3D
		var partes := mi.name.split("__")
		if partes.size() < 2:
			continue
		var chave := partes[0]
		var num := int(partes[1])
		var nome_peca := "%s__%d" % [chave, num]
		if not pecas.has(nome_peca):
			pecas[nome_peca] = kit.peca(raiz, chave, _rotulo(id, chave, num))
		var dono: Node3D = pecas[nome_peca]
		var t := mi.global_transform if mi.is_inside_tree() else _transform_global(mi)
		mi.get_parent().remove_child(mi)
		dono.add_child(mi)
		mi.transform = t
		_melhorar_material(id, chave, mi)
	modelo.free()
	match id:
		"quad450": _completar_quad450(raiz)
		"fpv5": _completar_fpv5(raiz)
		"hexa_agro": _completar_hexa(raiz)
	_definir_explosao(raiz)
	return raiz


func _transform_global(n: Node3D) -> Transform3D:
	var t := n.transform
	var p := n.get_parent()
	while p is Node3D:
		t = (p as Node3D).transform * t
		p = p.get_parent()
	return t


func _rotulo(id: String, chave: String, num: int) -> String:
	if num <= 0:
		return ""
	var n_motores := 6 if id == "hexa_agro" else 4
	var pos := ""
	if n_motores == 4:
		pos = ROTULOS_POSICAO_4[(num - 1) % 4]
	else:
		pos = "posição %d" % num
	var nomes := {"motor": "Motor", "helice": "Hélice", "braco": "Braço", "bico": "Bico"}
	var base: String = nomes.get(chave, chave.capitalize())
	var sentido := ""
	if chave in ["motor", "helice"]:
		# em X: frente direita e trás esquerda giram anti-horário (padrão ArduPilot/Betaflight "props in")
		var horario := (num % 2 == 0)
		sentido = " — gira " + ("horário (CW)" if horario else "anti-horário (CCW)")
	return "%s %d (%s)%s" % [base, num, pos, sentido]


# ------------------------------------------------------------------ materiais

func _melhorar_material(id: String, chave: String, mi: MeshInstance3D) -> void:
	for s in mi.mesh.get_surface_count():
		var orig := mi.mesh.surface_get_material(s)
		var c := Color(0.7, 0.7, 0.7)
		if orig is BaseMaterial3D:
			c = (orig as BaseMaterial3D).albedo_color
		elif orig is ShaderMaterial:
			mi.set_surface_override_material(s, orig)
			continue
		# branco puro estoura na luz: puxa para um branco de plástico real
		if c.get_luminance() > 0.85:
			c = c.darkened(0.12)
		var lum := c.get_luminance()
		var sat := c.s
		var novo: Material = null
		match chave:
			"frame_carbono", "braco":
				if id == "quad450" and chave == "braco":
					var frente := String(mi.name).begins_with("braco__1") or String(mi.name).begins_with("braco__4")
					novo = kit.plastico(Color(0.62, 0.05, 0.04) if frente else Color(0.82, 0.82, 0.8), 0.42)
				elif id == "fpv5" or (id == "hexa_agro" and lum < 0.2):
					novo = kit.carbono(320.0 if id == "fpv5" else 140.0)
			"frame", "pdb":
				if id == "quad450":
					novo = kit.pcb(Color(0.05, 0.06, 0.07) if chave == "frame" else Color(0.06, 0.07, 0.08), Color(0.12, 0.13, 0.15), 1.0 if chave == "frame" else 2.0)
			"motor":
				if lum < 0.05:
					novo = kit.metal_anodizado(Color(0.08, 0.08, 0.09))
				elif sat > 0.25 or lum > 0.08:
					novo = kit.metal_anodizado(c)
			"helice":
				novo = kit.plastico(c, 0.36, 0.45)
			"placa_aio", "fc_stack", "esc_4em1", "vtx":
				if c.g > c.r * 1.5 and c.g > c.b:
					novo = kit.pcb(Color(0.03, 0.14, 0.06), Color(0.06, 0.24, 0.1), 3.0)
				elif lum < 0.06:
					novo = kit.pcb(Color(0.025, 0.025, 0.03), Color(0.07, 0.07, 0.08), 4.0)
				elif c.r > 0.6 and c.g > 0.35 and c.b < 0.3:
					novo = kit.ouro()
			"frame_dutos":
				novo = kit.plastico(Color(0.1, 0.45, 0.85) if id == "" else c, 0.48, 0.2)
			"bateria":
				if lum < 0.05:
					novo = kit.plastico(Color(0.035, 0.035, 0.04), 0.55, 0.6)
			"pixhawk":
				if lum < 0.1:
					novo = kit.plastico(Color(0.07, 0.07, 0.075), 0.5, 0.25)
		if novo == null:
			if lum < 0.04:
				novo = kit.plastico(c.lightened(0.03), 0.5, 0.2)
			elif sat < 0.08 and lum > 0.25 and lum < 0.7:
				novo = kit.cor(c, 0.32, 0.9)   # cinza médio do CAD costuma ser metal (parafusos, eixos)
			else:
				novo = kit.plastico(c, 0.45, 0.2)
		mi.set_surface_override_material(s, novo)


# ------------------------------------------------------------------ acabamento do Blender

## Grava o drone montado em .glb (para o Blender assar a sombra de ambiente)
## e um .json com os dados de cada peça.
func exportar(id: String, pasta_abs: String) -> void:
	var d := montar_cad(id)
	var meta := {}
	var materiais := {}
	var receitas := {}
	var i := 0
	for p in d.get_children():
		if not p.has_meta("peca"):
			continue
		var nome := "p%02d__%s" % [i, p.get_meta("peca")]
		i += 1
		meta[nome] = {"peca": p.get_meta("peca"), "rotulo": p.get_meta("rotulo", ""), "explodir": var_to_str(p.get_meta("explodir", Vector3.ZERO))}
		p.name = nome
		for f in p.find_children("*", "MeshInstance3D", true, false):
			var mi := f as MeshInstance3D
			var malha := mi.mesh.duplicate() as Mesh
			for s in malha.get_surface_count():
				var m := mi.get_active_material(s)
				var ph := StandardMaterial3D.new()
				if m is BaseMaterial3D:
					ph = (m as BaseMaterial3D).duplicate()
				elif m is ShaderMaterial:
					ph.albedo_color = Color(0.05, 0.05, 0.05)
				var receita: String = m.resource_name if m else "cor|0.7,0.7,0.7|0.5|0|0"
				if not receitas.has(receita):
					receitas[receita] = "mat%03d" % receitas.size()
					materiais[receitas[receita]] = receita
				ph.resource_name = receitas[receita]
				malha.surface_set_material(s, ph)
				mi.set_surface_override_material(s, null)
			mi.mesh = malha
	var doc := GLTFDocument.new()
	var st := GLTFState.new()
	doc.append_from_scene(d, st)
	doc.write_to_filesystem(st, pasta_abs.path_join(id + "_src.glb"))
	meta["_materiais"] = materiais
	var f := FileAccess.open(pasta_abs.path_join(id + ".json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(meta, "\t"))
	d.free()


## Monta o drone a partir do .glb já assado no Blender (normais boas + AO no UV2).
func montar_final(id: String) -> Node3D:
	var raiz := Node3D.new()
	raiz.name = id
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PASTA_FINAL + id + ".json"))
	var ao: Texture2D = load(PASTA_FINAL + id + "_ao.png") if ResourceLoader.exists(PASTA_FINAL + id + "_ao.png") else null
	var cena: PackedScene = load(PASTA_FINAL + id + ".glb")
	var modelo := cena.instantiate()
	var pecas := {}
	var cache_ao := {}
	for filho in modelo.find_children("*", "MeshInstance3D", true, false):
		var mi := filho as MeshInstance3D
		# sobe até o nó da peça (nome "pNN__chave")
		var n: Node = mi
		var nome_peca := ""
		while n and n != modelo:
			var limpo := _sem_sufixo(String(n.name))
			if meta.has(limpo):
				nome_peca = limpo
				break
			n = n.get_parent()
		if nome_peca == "":
			continue
		if not pecas.has(nome_peca):
			var info: Dictionary = meta[nome_peca]
			pecas[nome_peca] = kit.peca(raiz, info["peca"], info["rotulo"], str_to_var(info["explodir"]))
		var t := _transform_global(mi)
		mi.get_parent().remove_child(mi)
		(pecas[nome_peca] as Node3D).add_child(mi)
		mi.transform = t
		for s in mi.mesh.get_surface_count():
			var orig := mi.mesh.surface_get_material(s)
			var nome_mat := _sem_sufixo(String(orig.resource_name)) if orig else ""
			var tabela: Dictionary = meta.get("_materiais", {})
			var base: Material = kit.de_receita(tabela.get(nome_mat, "")) if tabela.has(nome_mat) else null
			if base == null:
				base = orig if orig else kit.cor(Color(0.7, 0.7, 0.7))
			base = _ajuste_final(id, meta[nome_peca]["peca"], base)
			mi.set_surface_override_material(s, _com_ao(base, ao, cache_ao))
	modelo.free()
	return raiz


## Correções de cor aplicadas ao carregar o modelo assado.
func _ajuste_final(id: String, chave: String, m: Material) -> Material:
	if chave == "helice":
		var cores := {"quad450": Color(0.07, 0.07, 0.075), "fpv5": Color(0.55, 0.25, 0.95, 1.0), "hexa_agro": Color(0.06, 0.06, 0.065)}
		if cores.has(id):
			return kit.plastico(cores[id], 0.34, 0.5)
	if chave == "pixhawk" and m is BaseMaterial3D and (m as BaseMaterial3D).albedo_color.get_luminance() > 0.6:
		return kit.plastico(Color(0.7, 0.71, 0.72), 0.4, 0.3)
	if m is BaseMaterial3D and (m as BaseMaterial3D).albedo_color.get_luminance() > 0.8:
		var b := m as BaseMaterial3D
		return kit.plastico(b.albedo_color.darkened(0.18), maxf(b.roughness, 0.4), 0.2)
	return m


## Tira o ".001" que o Blender põe em nomes repetidos.
func _sem_sufixo(t: String) -> String:
	var re := RegEx.create_from_string("\\.\\d{3}$")
	return re.sub(t, "")


func _com_ao(base: Material, ao: Texture2D, cache_ao: Dictionary) -> Material:
	if ao == null:
		return base
	if cache_ao.has(base):
		return cache_ao[base]
	var m := base.duplicate()
	if m is BaseMaterial3D:
		var bm := m as BaseMaterial3D
		if bm.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
			bm.ao_enabled = true
			bm.ao_texture = ao
			bm.ao_on_uv2 = true
			bm.ao_light_affect = 0.35
			bm.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	elif m is ShaderMaterial:
		(m as ShaderMaterial).set_shader_parameter("ao_tex", ao)
		(m as ShaderMaterial).set_shader_parameter("usar_ao", true)
	cache_ao[base] = m
	return m


# ------------------------------------------------------------------ utilidades

## Coloca uma peça vinda do CAD (modelos/pecas/<arquivo>.glb) dentro do nó `pai`.
func _cad(pai: Node3D, arquivo: String, chave: String, pos := Vector3.ZERO, rot := Vector3.ZERO, esc := 1.0) -> Node3D:
	var cena: PackedScene = load("res://modelos/pecas/%s.glb" % arquivo)
	var inst := cena.instantiate()
	var n := Node3D.new()
	n.name = arquivo
	pai.add_child(n)
	n.position = pos
	n.rotation = rot
	n.scale = Vector3.ONE * esc
	for f in inst.find_children("*", "MeshInstance3D", true, false):
		var mi := f as MeshInstance3D
		var t := _transform_global(mi)
		mi.get_parent().remove_child(mi)
		n.add_child(mi)
		mi.transform = t
		_melhorar_material("", chave, mi)
	inst.free()
	return n


func _aabb(n: Node3D) -> AABB:
	var r := AABB()
	var primeiro := true
	for f in n.find_children("*", "MeshInstance3D", true, false):
		var mi := f as MeshInstance3D
		var t := _transform_global(mi)
		var b := t * mi.get_aabb()
		if primeiro:
			r = b
			primeiro = false
		else:
			r = r.merge(b)
	return r


func _pecas(raiz: Node3D, chave: String) -> Array[Node3D]:
	var out: Array[Node3D] = []
	for f in raiz.get_children():
		if f.get_meta("peca", "") == chave:
			out.append(f)
	return out


func _definir_explosao(raiz: Node3D) -> void:
	var total := _aabb(raiz)
	var centro := total.get_center()
	var tam := maxf(total.size.x, total.size.z)
	for p in raiz.get_children():
		if not p.has_meta("peca"):
			continue
		if p.get_meta("explodir", Vector3.ZERO) != Vector3.ZERO:
			continue
		var b := _aabb(p)
		var d := b.get_center() - centro
		var chave: String = p.get_meta("peca")
		var sobe := 0.0
		match chave:
			"helice": sobe = 0.32
			"motor": sobe = 0.16
			"gps", "gps_rtk", "pixhawk", "fc_stack", "placa_aio", "controladora_agro", "antena_vtx", "receptor", "telemetria", "camera_fpv", "vtx": sobe = 0.28
			"bateria", "tanque", "bomba", "trem_pouso", "pdb", "esc_4em1": sobe = -0.12
			"frame", "frame_carbono", "frame_agro", "frame_dutos": sobe = 0.0
			_: sobe = 0.15
		var horiz := Vector3(d.x, 0, d.z)
		var fator := 0.18 if chave in ["helice", "motor", "braco", "bico", "esc"] else 0.08
		p.set_meta("explodir", horiz * fator + Vector3(0, sobe * tam * 0.35, 0))


# ------------------------------------------------------------------ peças extras

func _completar_quad450(r: Node3D) -> void:
	var topo := _aabb(_pecas(r, "frame")[0])
	var baixo := _aabb(_pecas(r, "pdb")[0])
	for bb in _pecas(r, "braco"):
		var frente := _aabb(bb).get_center().z < topo.get_center().z
		for f in bb.find_children("*", "MeshInstance3D", true, false):
			var mi := f as MeshInstance3D
			for k in mi.mesh.get_surface_count():
				mi.set_surface_override_material(k, kit.plastico(Color(0.62, 0.05, 0.04) if frente else Color(0.82, 0.82, 0.8), 0.42))
	var y_topo := topo.end.y
	var c := topo.get_center()
	var branco := kit.cor(Color(0.88, 0.88, 0.86), 0.45)
	# Pixhawk 2.4.8 (CAD) sobre a placa amortecedora
	var px := kit.peca(r, "pixhawk", "Controladora Pixhawk 2.4.8")
	px.position = Vector3(c.x, y_topo, c.z - 0.004)
	kit.caixa(px, Vector3(0.052, 0.003, 0.052), kit.cor(Color(0.06, 0.06, 0.065), 0.85), Vector3(0, 0.0015, 0))
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			kit.esfera(px, 0.0042, kit.cor(Color(0.12, 0.12, 0.13), 0.75), Vector3(sx * 0.02, 0.0055, sz * 0.02))
	kit.caixa(px, Vector3(0.05, 0.002, 0.075), kit.cor(Color(0.07, 0.07, 0.075), 0.8), Vector3(0, 0.0095, 0))
	_cad(px, "pixhawk", "pixhawk", Vector3(0, 0.0105, 0))
	# mastro dobrável com GPS M8N (CAD)
	var gps := kit.peca(r, "gps", "GPS + bússola (M8N)")
	gps.position = Vector3(c.x, y_topo, c.z + 0.07)
	_cad(gps, "gps", "gps", Vector3.ZERO, Vector3(0, PI, 0))
	# bateria 3S 5000 mAh (CAD) embaixo do frame, presa com duas fitas
	var bat := kit.peca(r, "bateria", "Bateria LiPo 3S 5000 mAh")
	var bat_h := 0.027
	bat.position = Vector3(c.x, baixo.position.y - bat_h - 0.002, c.z)
	_cad(bat, "bat3s", "bateria")
	kit.fita(bat, Vector3(0, bat_h / 2, -0.035), 0.02, Vector2(0.0445, bat_h), Color(0.08, 0.08, 0.09))
	kit.fita(bat, Vector3(0, bat_h / 2, 0.035), 0.02, Vector2(0.0445, bat_h), Color(0.08, 0.08, 0.09))
	# 4 ESCs 30 A (CAD) presos embaixo dos braços, com os fios indo para o motor
	var motores := _pecas(r, "motor")
	for i in motores.size():
		var m := _aabb(motores[i]).get_center()
		var dir := Vector3(m.x - c.x, 0, m.z - c.z)
		var p := Vector3(c.x, 0, c.z) + dir * 0.42
		var esc := kit.peca(r, "esc", "ESC %d (30 A)" % (i + 1))
		var braco_mais_perto := _pecas(r, "braco")[0]
		for bb in _pecas(r, "braco"):
			if _aabb(bb).get_center().distance_to(m) < _aabb(braco_mais_perto).get_center().distance_to(m):
				braco_mais_perto = bb
		esc.position = Vector3(p.x, topo.position.y + 0.002, p.z)
		esc.rotation.y = atan2(dir.x, dir.z)
		_cad(esc, "esc30", "esc", Vector3(0, 0, 0))
	# receptor e rádio de telemetria
	var rx := kit.peca(r, "receptor", "Receptor de rádio (FlySky iA6B)")
	rx.position = Vector3(c.x + 0.045, y_topo, c.z + 0.03)
	kit.caixa(rx, Vector3(0.024, 0.012, 0.042), kit.cor(Color(0.08, 0.08, 0.08), 0.5), Vector3(0, 0.006, 0))
	kit.caixa(rx, Vector3(0.018, 0.0005, 0.012), kit.cor(Color(0.85, 0.85, 0.85), 0.5), Vector3(0, 0.0123, 0.01))
	kit.antena_fio(rx, Vector3(0.005, 0.01, -0.021), Vector3(0.6, 0.3, -1), 0.035)
	kit.antena_fio(rx, Vector3(-0.005, 0.01, -0.021), Vector3(-0.2, 0.3, -1).rotated(Vector3.UP, 1.4), 0.035)
	var tl := kit.peca(r, "telemetria", "Rádio de telemetria 915 MHz")
	tl.position = Vector3(c.x - 0.045, y_topo, c.z + 0.03)
	kit.caixa(tl, Vector3(0.026, 0.01, 0.045), kit.cor(Color(0.1, 0.1, 0.11), 0.4, 0.3), Vector3(0, 0.005, 0))
	kit.cil(tl, 0.003, 0.012, kit.ouro(), Vector3(0, 0.005, 0.028), Vector3(PI / 2, 0, 0))
	kit.cil(tl, 0.0045, 0.075, kit.cor(Color(0.05, 0.05, 0.05), 0.5), Vector3(0, 0.04, 0.034), Vector3(0, 0, 0), 12)
	# buzzer e botão
	var bz := kit.peca(r, "buzzer", "Buzzer e botão de segurança")
	bz.position = Vector3(c.x, y_topo, c.z + 0.07)
	kit.cil(bz, 0.006, 0.008, kit.cor(Color(0.05, 0.05, 0.05), 0.5), Vector3(-0.012, 0.004, 0))
	kit.caixa(bz, Vector3(0.012, 0.008, 0.012), kit.cor(Color(0.08, 0.08, 0.08), 0.5), Vector3(0.012, 0.004, 0))
	kit.cil(bz, 0.004, 0.003, kit.translucido(Color(0.9, 0.15, 0.1, 0.8), 0.2), Vector3(0.012, 0.0095, 0))
	# módulo de energia
	var me := kit.peca(r, "modulo_energia", "Módulo de energia")
	me.position = Vector3(c.x, baixo.position.y + 0.001, c.z + 0.085)
	kit.placa(me, Vector3(0.022, 0.0016, 0.025), Color(0.05, 0.25, 0.1), 21.0, Vector3(0, -0.004, 0), Vector3.ZERO, 5)


func _completar_fpv5(r: Node3D) -> void:
	var total := _aabb(r)
	var c := total.get_center()
	# receptor ExpressLRS com antena em T saindo pela traseira
	var rx := kit.peca(r, "receptor", "Receptor ExpressLRS")
	var fr := _aabb(_pecas(r, "frame_carbono")[0])
	rx.position = Vector3(c.x, fr.end.y - 0.022, fr.position.z + 0.035)
	kit.placa(rx, Vector3(0.012, 0.0012, 0.018), Color(0.03, 0.03, 0.035), 31.0, Vector3.ZERO, Vector3.ZERO, 4)
	kit.cabo(rx, [Vector3(0, 0.002, -0.008), Vector3(0, 0.008, -0.03), Vector3(0, 0.02, -0.05)], 0.0011, kit.cor(Color(0.05, 0.05, 0.05), 0.5))
	kit.cil(rx, 0.0025, 0.03, kit.cor(Color(0.1, 0.1, 0.1), 0.6), Vector3(0, 0.02, -0.065), Vector3(0, 0, PI / 2), 8)
	# capacitor na entrada da bateria
	var cap := kit.peca(r, "capacitor", "Capacitor 35 V 1000 µF")
	var esc := _aabb(_pecas(r, "esc_4em1")[0])
	cap.position = Vector3(esc.end.x - 0.004, esc.position.y + 0.004, esc.position.z - 0.006)
	kit.cil(cap, 0.005, 0.016, kit.cor(Color(0.05, 0.05, 0.06), 0.3, 0.0, 0.6), Vector3.ZERO, Vector3(PI / 2, 0, 0))
	kit.cil(cap, 0.0051, 0.004, kit.cor(Color(0.5, 0.5, 0.52), 0.35, 0.7), Vector3(0, 0, -0.0085), Vector3(PI / 2, 0, 0))
	# a bateria veio de lado no CAD: deita (gira 90° no eixo comprido) e assenta no frame
	var bat := _pecas(r, "bateria")
	if bat.size() > 0:
		var b0 := _aabb(bat[0])
		var cc := b0.get_center()
		var giro := Transform3D(Basis(Vector3.BACK, PI / 2), Vector3.ZERO)
		bat[0].transform = Transform3D(Basis(), cc) * giro * Transform3D(Basis(), -cc) * bat[0].transform
		var b1 := _aabb(bat[0])
		bat[0].position.y += b0.position.y - b1.position.y
		var b := _aabb(bat[0])
		var fita := Node3D.new()
		bat[0].add_child(fita)
		kit.fita(fita, b.get_center() + Vector3(0, 0, -b.size.z * 0.2), 0.02, Vector2(b.size.x, b.size.y), Color(0.75, 0.15, 0.05))
		kit.fita(fita, b.get_center() + Vector3(0, 0, b.size.z * 0.2), 0.02, Vector2(b.size.x, b.size.y), Color(0.75, 0.15, 0.05))


func _montar_whoop() -> Node3D:
	var r := Node3D.new()
	r.name = "whoop65"
	# frame BetaFPV Meteor65 Pro (CAD)
	var fr := kit.peca(r, "frame_dutos", "Frame Meteor65 Pro (dutos)")
	_cad(fr, "meteor65", "frame_dutos")
	var d := 0.0231   # centro dos motores (65 mm na diagonal)
	var posicoes := [Vector2(d, -d), Vector2(d, d), Vector2(-d, d), Vector2(-d, -d)]
	for i in 4:
		var pz: Vector2 = posicoes[i]
		var cw := i % 2 == 1
		var m := kit.motor(r, _rotulo("whoop65", "motor", i + 1), Vector3(pz.x, 0.0024, pz.y), 0.0086, 0.0104, Color(0.82, 0.55, 0.12) if cw else Color(0.1, 0.1, 0.11), cw)
		m.rotation.y = atan2(pz.x, pz.y) + PI
		var mat := kit.cor(Color(0.1, 0.1, 0.11) if cw else Color(0.85, 0.85, 0.82), 0.38, 0.0, 0.4)
		kit.helice(r, _rotulo("whoop65", "helice", i + 1), Vector3(pz.x, 0.0024 + 0.0108, pz.y), 0.031, 0.022, 3, mat, cw, Vector3.ZERO, 0.22)
	# placa AIO 26x26 sobre borrachinhas
	var aio := kit.peca(r, "placa_aio", "Placa AIO (FC + 4 ESC + receptor ELRS + VTX)")
	aio.position = Vector3(0, 0.0085, 0)
	kit.placa(aio, Vector3(0.026, 0.0012, 0.026), Color(0.03, 0.03, 0.035), 41.0, Vector3.ZERO, Vector3.ZERO, 22)
	kit.caixa(aio, Vector3(0.005, 0.001, 0.005), kit.cor(Color(0.06, 0.06, 0.07), 0.3), Vector3(0, 0.0011, 0))
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			kit.cil(aio, 0.0013, 0.003, kit.cor(Color(0.85, 0.2, 0.1), 0.8), Vector3(sx * 0.0105, -0.0015, sz * 0.0105), Vector3.ZERO, 10)
	kit.caixa(aio, Vector3(0.006, 0.0025, 0.004), kit.cor(Color(0.85, 0.85, 0.82), 0.5), Vector3(0, 0.0013, -0.0125))  # conector da bateria
	# câmera nano + capota de plástico
	var cam := kit.peca(r, "camera_fpv", "Câmera FPV nano + capota")
	cam.position = Vector3(0, 0.01, 0.003)
	var capota := kit.esfera(cam, 0.0145, kit.translucido(Color(0.95, 0.4, 0.08, 0.5), 0.2), Vector3(0, 0.0, 0), Vector3(0.95, 0.62, 1.15))
	capota.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	kit.caixa(cam, Vector3(0.012, 0.012, 0.009), kit.cor(Color(0.05, 0.05, 0.05), 0.4), Vector3(0, 0.005, 0.007), Vector3(-0.3, 0, 0))
	kit.cil(cam, 0.004, 0.006, kit.cor(Color(0.02, 0.02, 0.025), 0.08, 0.4), Vector3(0, 0.0065, 0.0135), Vector3(PI / 2 - 0.3, 0, 0), 24)
	kit.antena_fio(cam, Vector3(0, 0.004, -0.012), Vector3(0, 0.6, -1), 0.02, 0.0006)
	# bateria 1S presa embaixo
	var bat := kit.bateria(r, "Bateria LiPo 1S 300 mAh", Vector3(0, -0.004, 0), Vector3(0.012, 0.0072, 0.045), Color(0.95, 0.8, 0.15), Color(0.1, 0.1, 0.1), Vector3.ZERO, 0.22)
	bat.rotation.y = 0.0
	_definir_explosao(r)
	return r


func _completar_hexa(r: Node3D) -> void:
	var corpo := _aabb(_pecas(r, "frame_agro")[0])
	var c := corpo.get_center()
	# controladora dentro do corpo (aparece na vista explodida)
	var fc := kit.peca(r, "controladora_agro", "Controladora agrícola")
	fc.position = Vector3(c.x, corpo.position.y + corpo.size.y * 0.55, c.z)
	kit.caixa_redonda(fc, Vector3(0.09, 0.025, 0.12), 0.008, kit.cor(Color(0.12, 0.12, 0.13), 0.35, 0.6), Vector3.ZERO)
	kit.caixa(fc, Vector3(0.05, 0.002, 0.06), kit.cor(Color(0.85, 0.35, 0.05), 0.5), Vector3(0, 0.0135, 0))
	# radar de terreno na frente, embaixo
	var rd := kit.peca(r, "radar", "Radar de terreno")
	rd.position = Vector3(c.x, corpo.position.y + 0.03, corpo.position.z - 0.02)
	kit.caixa_redonda(rd, Vector3(0.12, 0.03, 0.07), 0.01, kit.cor(Color(0.9, 0.9, 0.88), 0.4), Vector3.ZERO, Vector3(-0.5, 0, 0))
	kit.caixa(rd, Vector3(0.1, 0.002, 0.05), kit.cor(Color(0.15, 0.15, 0.17), 0.3), Vector3(0, -0.012, 0.012), Vector3(-0.5, 0, 0))
