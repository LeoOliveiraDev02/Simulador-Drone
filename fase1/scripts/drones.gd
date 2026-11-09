class_name Drones
extends RefCounted
## Monta cada drone: carrega o modelo CAD (modelos/<id>.glb), transforma cada
## grupo "chave__N" numa peça clicável, melhora os materiais e completa com
## as peças que o CAD não trazia (feitas pelo Kit).

var kit := Kit.new()

const ROTULOS_POSICAO_4 := ["frente direita", "trás direita", "trás esquerda", "frente esquerda"]


func montar(id: String) -> Node3D:
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
		"whoop65": _completar_whoop(raiz)
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
		var lum := c.get_luminance()
		var novo: Material = null
		match chave:
			"frame_carbono", "braco":
				if id == "quad450" and chave == "braco":
					var frente := String(mi.name).begins_with("braco__1") or String(mi.name).begins_with("braco__4")
					novo = kit.cor(Color(0.72, 0.06, 0.05) if frente else Color(0.9, 0.9, 0.88), 0.38, 0.0, 0.5)
				elif id == "fpv5" or (id == "hexa_agro" and lum < 0.2):
					novo = kit.carbono(320.0 if id == "fpv5" else 140.0)
				elif id == "quad450":
					novo = kit.cor(c, 0.38, 0.0, 0.5)
			"frame", "pdb":
				if id == "quad450":
					novo = kit.pcb(Color(0.05, 0.06, 0.07) if chave == "frame" else Color(0.06, 0.07, 0.08), Color(0.12, 0.13, 0.15), 1.0 if chave == "frame" else 2.0)
			"motor":
				novo = kit.cor(c, 0.3, 0.85) if lum > 0.08 else kit.cor(c, 0.35, 0.6)
			"helice":
				novo = kit.cor(c, 0.42, 0.0, 0.3)
			"placa_aio", "fc_stack", "esc_4em1":
				if c.g > c.r * 1.5:
					novo = kit.pcb(Color(0.03, 0.14, 0.06), Color(0.06, 0.24, 0.1), 3.0)
				elif lum < 0.12:
					novo = kit.pcb(Color(0.03, 0.03, 0.035), Color(0.08, 0.08, 0.09), 4.0)
			"frame_dutos":
				if lum < 0.1:
					novo = kit.carbono(900.0)
				else:
					novo = kit.cor(c, 0.4, 0.0, 0.25)
		if novo == null:
			novo = kit.cor(c, 0.45, 0.0)
		mi.set_surface_override_material(s, novo)


# ------------------------------------------------------------------ utilidades

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
	var y_topo := topo.end.y
	var c := topo.get_center()
	var branco := kit.cor(Color(0.88, 0.88, 0.86), 0.45)
	# Pixhawk 2.4.8 sobre amortecedor
	var px := kit.peca(r, "pixhawk", "Controladora Pixhawk 2.4.8")
	px.position = Vector3(c.x, y_topo, c.z - 0.005)
	kit.caixa(px, Vector3(0.05, 0.004, 0.05), kit.cor(Color(0.1, 0.1, 0.1), 0.8), Vector3(0, 0.002, 0))
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			kit.esfera(px, 0.0045, kit.cor(Color(0.15, 0.15, 0.17), 0.7), Vector3(sx * 0.019, 0.007, sz * 0.019))
	kit.caixa_redonda(px, Vector3(0.05, 0.016, 0.082), 0.004, branco, Vector3(0, 0.019, 0))
	kit.caixa(px, Vector3(0.042, 0.002, 0.07), kit.cor(Color(0.2, 0.2, 0.22), 0.5), Vector3(0, 0.0275, 0))
	kit.caixa(px, Vector3(0.01, 0.0025, 0.022), kit.cor(Color(0.9, 0.5, 0.1), 0.4), Vector3(0, 0.029, 0.012))  # seta de orientação
	kit.caixa(px, Vector3(0.006, 0.0025, 0.01), kit.cor(Color(0.9, 0.5, 0.1), 0.4), Vector3(0, 0.029, 0.026), Vector3(0, PI / 4, 0))
	for i in 8:
		kit.caixa(px, Vector3(0.004, 0.005, 0.004), kit.cor(Color(0.95, 0.95, 0.93), 0.5), Vector3(-0.018 + i * 0.005, 0.016, -0.042))
	# mastro com GPS
	var gps := kit.peca(r, "gps", "GPS + bússola (M8N)")
	gps.position = Vector3(c.x, y_topo, c.z - 0.065)
	kit.cil(gps, 0.012, 0.004, kit.preto_fosco(), Vector3(0, 0.002, 0))
	kit.cil(gps, 0.003, 0.11, kit.carbono(400.0), Vector3(0, 0.058, 0), Vector3.ZERO, 12)
	kit.cil(gps, 0.03, 0.014, kit.cor(Color(0.08, 0.08, 0.09), 0.35, 0.0, 0.5), Vector3(0, 0.12, 0), Vector3.ZERO, 40)
	kit.cil(gps, 0.026, 0.002, kit.cor(Color(0.12, 0.12, 0.13), 0.3), Vector3(0, 0.128, 0), Vector3.ZERO, 40)
	kit.caixa(gps, Vector3(0.006, 0.0015, 0.016), kit.cor(Color(0.9, 0.9, 0.9), 0.4), Vector3(0, 0.1295, 0.004))
	kit.cabo(gps, [Vector3(0, 0.115, 0.005), Vector3(0.006, 0.06, 0.01), Vector3(0.0, 0.02, 0.03)], 0.0012, kit.cor(Color(0.85, 0.85, 0.85), 0.5))
	# bateria 3S 5000 mAh embaixo do frame, presa com fita
	var altura_bat := 0.027
	var y_bat := baixo.position.y - altura_bat / 2 - 0.002
	var bat := kit.bateria(r, "Bateria LiPo 3S 5000 mAh", Vector3(c.x, y_bat, c.z), Vector3(0.048, altura_bat, 0.14), Color(0.12, 0.12, 0.14), Color(0.85, 0.1, 0.1), Vector3.ZERO, 1.0)
	kit.fita(bat, Vector3(0, 0, -0.03), 0.02, Vector2(0.048, altura_bat))
	kit.fita(bat, Vector3(0, 0, 0.035), 0.02, Vector2(0.048, altura_bat))
	# 4 ESCs presos nos braços
	var motores := _pecas(r, "motor")
	for i in motores.size():
		var m := _aabb(motores[i]).get_center()
		var dir := Vector3(m.x - c.x, 0, m.z - c.z)
		var p := Vector3(c.x, 0, c.z) + dir * 0.45
		var esc := kit.peca(r, "esc", "ESC %d (30 A)" % (i + 1))
		esc.position = Vector3(p.x, _aabb(_pecas(r, "braco")[i]).end.y - 0.006, p.z)
		esc.rotation.y = atan2(dir.x, dir.z)
		kit.caixa_redonda(esc, Vector3(0.022, 0.008, 0.05), 0.003, kit.translucido(Color(0.15, 0.35, 0.8, 0.85), 0.3), Vector3(0, 0.004, 0))
		kit.placa(esc, Vector3(0.019, 0.0012, 0.046), Color(0.05, 0.12, 0.3), 10.0 + i, Vector3(0, 0.003, 0), Vector3.ZERO, 6)
		for k in 3:
			kit.cabo(esc, [Vector3(-0.005 + k * 0.005, 0.004, 0.025), Vector3(-0.005 + k * 0.005, 0.006, 0.05), Vector3(-0.004 + k * 0.004, 0.003, 0.075)], 0.0011, kit.cor(Color(0.05, 0.05, 0.05), 0.5))
		kit.cabo(esc, [Vector3(0.004, 0.004, -0.025), Vector3(0.004, 0.003, -0.05), Vector3(0.0, 0.0, -0.07)], 0.0013, kit.cor(Color(0.75, 0.05, 0.04), 0.45))
		kit.cabo(esc, [Vector3(-0.004, 0.004, -0.025), Vector3(-0.004, 0.003, -0.05), Vector3(0.0, 0.0, -0.068)], 0.0013, kit.cor(Color(0.04, 0.04, 0.04), 0.45))
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
	kit.xt60(me, Vector3(0, -0.005, 0.02), Vector3(PI / 2, 0, 0))


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
	# fita da bateria
	var bat := _pecas(r, "bateria")
	if bat.size() > 0:
		var b := _aabb(bat[0])
		var fita := Node3D.new()
		bat[0].add_child(fita)
		kit.fita(fita, b.get_center() + Vector3(0, 0, -b.size.z * 0.2), 0.02, Vector2(b.size.x, b.size.y), Color(0.75, 0.15, 0.05))
		kit.fita(fita, b.get_center() + Vector3(0, 0, b.size.z * 0.2), 0.02, Vector2(b.size.x, b.size.y), Color(0.75, 0.15, 0.05))


func _completar_whoop(r: Node3D) -> void:
	var placa := _aabb(_pecas(r, "placa_aio")[0])
	var c := placa.get_center()
	# o CAD traz as hélices como discos: troca por hélices de 3 pás em cima de cada motor
	for h in _pecas(r, "helice"):
		h.queue_free()
		r.remove_child(h)
	var motores := _pecas(r, "motor")
	for i in motores.size():
		var mb := _aabb(motores[i])
		var mc := mb.get_center()
		var ang := atan2(mc.x - c.x, -(mc.z - c.z))
		var idx := int(posmod(ang, TAU) / (PI / 2.0))
		motores[i].set_meta("rotulo", _rotulo("whoop65", "motor", idx + 1))
		var cw := idx % 2 == 1
		var mat := kit.cor(Color(0.85, 0.85, 0.82) if cw else Color(0.1, 0.1, 0.1), 0.45)
		kit.helice(r, _rotulo("whoop65", "helice", idx + 1), Vector3(mc.x, mb.end.y + 0.0006, mc.z), 0.031, 0.022, 3, mat, cw, Vector3.ZERO, 0.2)
	# placa AIO de verdade em cima da placa do CAD
	var aio := kit.peca(r, "placa_aio", "Placa AIO (FC + ESC + receptor + VTX)")
	aio.position = Vector3(c.x, placa.end.y + 0.0045, c.z)
	kit.placa(aio, Vector3(0.026, 0.0012, 0.026), Color(0.03, 0.03, 0.035), 41.0, Vector3.ZERO, Vector3.ZERO, 18)
	kit.caixa(aio, Vector3(0.0045, 0.0012, 0.0045), kit.cor(Color(0.06, 0.06, 0.07), 0.3), Vector3(0, 0.0012, 0))
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			kit.cil(aio, 0.0012, 0.0045, kit.cor(Color(0.1, 0.1, 0.1), 0.7), Vector3(sx * 0.0105, -0.0022, sz * 0.0105), Vector3.ZERO, 8)
	# câmera com capota (canopy)
	var cam := kit.peca(r, "camera_fpv", "Câmera FPV nano + capota")
	cam.position = Vector3(c.x, placa.end.y + 0.006, c.z + 0.004)
	var capota := kit.esfera(cam, 0.016, kit.translucido(Color(0.9, 0.35, 0.05, 0.55), 0.25), Vector3(0, 0.002, 0), Vector3(0.95, 0.75, 1.1))
	capota.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	kit.caixa(cam, Vector3(0.012, 0.012, 0.01), kit.cor(Color(0.05, 0.05, 0.05), 0.4), Vector3(0, 0.006, 0.006), Vector3(-0.35, 0, 0))
	kit.cil(cam, 0.0042, 0.006, kit.cor(Color(0.02, 0.02, 0.025), 0.1, 0.4), Vector3(0, 0.008, 0.013), Vector3(PI / 2 - 0.35, 0, 0), 20)
	kit.antena_fio(cam, Vector3(0, 0.004, -0.01), Vector3(0, 0.6, -1), 0.02, 0.0006)
	# bateria 1S embaixo
	kit.bateria(r, "Bateria LiPo 1S 300 mAh", Vector3(c.x, placa.position.y - 0.0055, c.z), Vector3(0.012, 0.0075, 0.046), Color(0.9, 0.85, 0.2), Color(0.1, 0.1, 0.1), Vector3.ZERO, 0.22)


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
