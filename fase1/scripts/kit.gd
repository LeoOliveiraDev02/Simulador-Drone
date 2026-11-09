class_name Kit
extends RefCounted
## Caixa de ferramentas para montar as peças dos drones por código.
## Tudo em metros. Cada peça é um Node3D com metadados:
##   meta "peca"     -> chave em dados/pecas.json
##   meta "rotulo"   -> nome específico (ex.: "Motor 1 - frente direita (anti-horário)")
##   meta "explodir" -> deslocamento da vista explodida

var cache := {}
const SH_CARBONO := preload("res://shaders/carbono.gdshader")
const SH_PCB := preload("res://shaders/pcb.gdshader")


# ------------------------------------------------------------------ materiais

func cor(c: Color, rug := 0.5, metal := 0.0, verniz := 0.0) -> StandardMaterial3D:
	var k := "cor_%s_%s_%s_%s" % [c.to_html(), rug, metal, verniz]
	if cache.has(k):
		return cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rug
	m.metallic = metal
	if verniz > 0.0:
		m.clearcoat_enabled = true
		m.clearcoat = verniz
		m.clearcoat_roughness = 0.2
	m.resource_name = "cor|%s|%s|%s|%s" % [_c(c), rug, metal, verniz]
	cache[k] = m
	return m


func carbono(escala := 260.0) -> ShaderMaterial:
	var k := "carbono_%s" % escala
	if cache.has(k):
		return cache[k]
	var m := ShaderMaterial.new()
	m.shader = SH_CARBONO
	m.set_shader_parameter("escala", escala)
	m.resource_name = "carbono|%s" % escala
	cache[k] = m
	return m


func pcb(verniz: Color, trilha: Color, semente := 0.0) -> ShaderMaterial:
	var k := "pcb_%s_%s_%s" % [verniz.to_html(), trilha.to_html(), semente]
	if cache.has(k):
		return cache[k]
	var m := ShaderMaterial.new()
	m.shader = SH_PCB
	m.set_shader_parameter("cor_verniz", Vector3(verniz.r, verniz.g, verniz.b))
	m.set_shader_parameter("cor_trilha", Vector3(trilha.r, trilha.g, trilha.b))
	m.set_shader_parameter("semente", semente)
	m.resource_name = "pcb|%s|%s|%s" % [_c(verniz), _c(trilha), semente]
	cache[k] = m
	return m


func translucido(c: Color, rug := 0.2) -> StandardMaterial3D:
	var k := "tr_%s_%s" % [c.to_html(), rug]
	if cache.has(k):
		return cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rug
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.resource_name = "tr|%s|%s|%s" % [_c(c), c.a, rug]
	cache[k] = m
	return m


## Plástico injetado: rugosidade com microtextura e verniz leve.
func plastico(c: Color, rug := 0.45, verniz := 0.2) -> StandardMaterial3D:
	var k := "pl_%s_%s_%s" % [c.to_html(), rug, verniz]
	if cache.has(k):
		return cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rug
	m.metallic = 0.0
	m.specular = 0.45
	if verniz > 0.0:
		m.clearcoat_enabled = true
		m.clearcoat = verniz
		m.clearcoat_roughness = 0.35
	m.detail_enabled = true
	m.detail_normal = _ruido_normal()
	m.detail_uv_layer = BaseMaterial3D.DETAIL_UV_1
	m.uv1_triplanar = true
	m.uv1_world_triplanar = false
	m.uv1_scale = Vector3.ONE * 180.0
	m.resource_name = "pl|%s|%s|%s" % [_c(c), rug, verniz]
	cache[k] = m
	return m


## Alumínio anodizado escovado (sino dos motores): metálico com brilho alongado.
func metal_anodizado(c: Color) -> StandardMaterial3D:
	var k := "an_%s" % c.to_html()
	if cache.has(k):
		return cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = c.lightened(0.08)
	m.metallic = 0.9
	m.roughness = 0.28
	m.anisotropy_enabled = true
	m.anisotropy = 0.65
	m.clearcoat_enabled = true
	m.clearcoat = 0.3
	m.clearcoat_roughness = 0.15
	m.detail_enabled = true
	m.detail_normal = _ruido_normal(true)
	m.uv1_triplanar = true
	m.uv1_scale = Vector3.ONE * 120.0
	m.resource_name = "an|%s" % _c(c)
	cache[k] = m
	return m


func _ruido_normal(escovado := false) -> NoiseTexture2D:
	var k := "rn_%s" % escovado
	if cache.has(k):
		return cache[k]
	var n := FastNoiseLite.new()
	n.frequency = 0.08 if not escovado else 0.02
	n.fractal_octaves = 3
	var t := NoiseTexture2D.new()
	t.noise = n
	t.width = 256
	t.height = 256 if not escovado else 16
	t.seamless = true
	t.as_normal_map = true
	t.bump_strength = 1.5 if not escovado else 3.0
	t.generate_mipmaps = true
	cache[k] = t
	return t


func _c(c: Color) -> String:
	return "%.4f,%.4f,%.4f" % [c.r, c.g, c.b]


func _cor_de(t: String) -> Color:
	var p := t.split(",")
	return Color(float(p[0]), float(p[1]), float(p[2]))


## Refaz um material a partir do nome (receita) gravado no .glb.
func de_receita(nome: String) -> Material:
	var p := nome.split("|")
	match p[0]:
		"cor": return cor(_cor_de(p[1]), float(p[2]), float(p[3]), float(p[4]))
		"carbono": return carbono(float(p[1]))
		"pcb": return pcb(_cor_de(p[1]), _cor_de(p[2]), float(p[3]))
		"tr":
			var c := _cor_de(p[1])
			c.a = float(p[2])
			return translucido(c, float(p[3]))
		"pl": return plastico(_cor_de(p[1]), float(p[2]), float(p[3]))
		"an": return metal_anodizado(_cor_de(p[1]))
	return null


# Cores comuns
func preto_fosco() -> StandardMaterial3D: return cor(Color(0.035, 0.035, 0.038), 0.7)
func plastico_preto() -> StandardMaterial3D: return cor(Color(0.05, 0.05, 0.055), 0.45)
func aluminio(c := Color(0.75, 0.76, 0.78)) -> StandardMaterial3D: return cor(c, 0.32, 1.0)
func cobre() -> StandardMaterial3D: return cor(Color(0.78, 0.42, 0.22), 0.3, 1.0)
func aco() -> StandardMaterial3D: return cor(Color(0.6, 0.6, 0.62), 0.25, 1.0)
func ouro() -> StandardMaterial3D: return cor(Color(0.9, 0.7, 0.35), 0.25, 1.0)


# ------------------------------------------------------------------ formas básicas

func peca(pai: Node3D, chave: String, rotulo := "", explodir := Vector3.ZERO) -> Node3D:
	var n := Node3D.new()
	n.name = (rotulo if rotulo != "" else chave).validate_node_name()
	n.set_meta("peca", chave)
	n.set_meta("rotulo", rotulo)
	n.set_meta("explodir", explodir)
	pai.add_child(n)
	return n


func malha(pai: Node3D, m: Mesh, mat: Material, pos := Vector3.ZERO, rot := Vector3.ZERO, esc := Vector3.ONE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = m
	mi.material_override = mat
	pai.add_child(mi)
	mi.position = pos
	mi.rotation = rot
	mi.scale = esc
	return mi


func caixa(pai: Node3D, tam: Vector3, mat: Material, pos := Vector3.ZERO, rot := Vector3.ZERO) -> MeshInstance3D:
	var b := BoxMesh.new()
	b.size = tam
	return malha(pai, b, mat, pos, rot)


func cil(pai: Node3D, r: float, alt: float, mat: Material, pos := Vector3.ZERO, rot := Vector3.ZERO, lados := 24, r_base := -1.0) -> MeshInstance3D:
	var c := CylinderMesh.new()
	c.top_radius = r
	c.bottom_radius = r if r_base < 0.0 else r_base
	c.height = alt
	c.radial_segments = lados
	c.rings = 1
	return malha(pai, c, mat, pos, rot)


func tubo(pai: Node3D, r_ext: float, r_int: float, alt: float, mat: Material, pos := Vector3.ZERO, rot := Vector3.ZERO, lados := 32) -> MeshInstance3D:
	return malha(pai, malha_tubo(r_ext, r_int, alt, lados), mat, pos, rot)


func esfera(pai: Node3D, r: float, mat: Material, pos := Vector3.ZERO, esc := Vector3.ONE) -> MeshInstance3D:
	var s := SphereMesh.new()
	s.radius = r
	s.height = r * 2.0
	s.radial_segments = 24
	s.rings = 12
	return malha(pai, s, mat, pos, Vector3.ZERO, esc)


## Caixa com cantos arredondados (bateria, módulos).
func caixa_redonda(pai: Node3D, tam: Vector3, raio: float, mat: Material, pos := Vector3.ZERO, rot := Vector3.ZERO) -> MeshInstance3D:
	var pts := PackedVector2Array()
	var hx := tam.x / 2.0 - raio
	var hz := tam.z / 2.0 - raio
	var cantos := [Vector2(hx, hz), Vector2(-hx, hz), Vector2(-hx, -hz), Vector2(hx, -hz)]
	for i in 4:
		var c: Vector2 = cantos[i]
		for k in 7:
			var a := (i * 90.0 + k * 15.0) * PI / 180.0
			pts.append(c + Vector2(cos(a), sin(a)) * raio)
	return malha(pai, extrusao(pts, tam.y), mat, pos, rot)


## Extrusão de um polígono 2D (x, z) com altura em y, centrada em y = 0.
func extrusao(pts: PackedVector2Array, alt: float, furos: Array = []) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var h := alt / 2.0
	# contorno com furos: usa triangulação com pontes simples
	var contorno := pts
	if Geometry2D.is_polygon_clockwise(contorno):
		contorno = contorno.duplicate()
		contorno.reverse()
	var poligonos: Array = [contorno]
	for f in furos:
		var r: Array = Geometry2D.clip_polygons(poligonos[0], f)
		if r.size() > 0:
			poligonos = r
	for poly in poligonos:
		var p: PackedVector2Array = poly
		if Geometry2D.is_polygon_clockwise(p):
			continue
		var tri := Geometry2D.triangulate_polygon(p)
		for s: float in [1.0, -1.0]:
			st.set_normal(Vector3(0, s, 0))
			for i in range(0, tri.size(), 3):
				var ordem := [tri[i], tri[i + 1], tri[i + 2]] if s < 0 else [tri[i], tri[i + 2], tri[i + 1]]
				for idx in ordem:
					var v := p[idx]
					st.set_uv(v)
					st.add_vertex(Vector3(v.x, h * s, v.y))
	# paredes laterais (inclusive dos furos)
	var bordas: Array = []
	for poly in poligonos:
		bordas.append(poly)
	for poly in bordas:
		var p: PackedVector2Array = poly
		var n := p.size()
		for i in n:
			var a := p[i]
			var b := p[(i + 1) % n]
			var d := (b - a).normalized()
			var nrm := Vector3(d.y, 0, -d.x)
			if Geometry2D.is_polygon_clockwise(p):
				nrm = -nrm
			st.set_normal(nrm)
			var va := Vector3(a.x, -h, a.y)
			var vb := Vector3(b.x, -h, b.y)
			var vc := Vector3(b.x, h, b.y)
			var vd := Vector3(a.x, h, a.y)
			if Geometry2D.is_polygon_clockwise(p):
				for v in [va, vc, vb, va, vd, vc]:
					st.add_vertex(v)
			else:
				for v in [va, vb, vc, va, vc, vd]:
					st.add_vertex(v)
	st.generate_tangents()
	return st.commit()


func circulo(c: Vector2, r: float, lados := 20) -> PackedVector2Array:
	var p := PackedVector2Array()
	for i in lados:
		var a := TAU * i / lados
		p.append(c + Vector2(cos(a), sin(a)) * r)
	return p


func malha_tubo(r_ext: float, r_int: float, alt: float, lados := 32) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var h := alt / 2.0
	for i in lados:
		var a0 := TAU * i / lados
		var a1 := TAU * (i + 1) / lados
		var d0 := Vector3(cos(a0), 0, sin(a0))
		var d1 := Vector3(cos(a1), 0, sin(a1))
		# fora
		_quad(st, d0 * r_ext + Vector3(0, -h, 0), d1 * r_ext + Vector3(0, -h, 0), d1 * r_ext + Vector3(0, h, 0), d0 * r_ext + Vector3(0, h, 0), d0, d1)
		# dentro
		_quad(st, d1 * r_int + Vector3(0, -h, 0), d0 * r_int + Vector3(0, -h, 0), d0 * r_int + Vector3(0, h, 0), d1 * r_int + Vector3(0, h, 0), -d1, -d0)
		# tampas
		_quad(st, d0 * r_int + Vector3(0, h, 0), d0 * r_ext + Vector3(0, h, 0), d1 * r_ext + Vector3(0, h, 0), d1 * r_int + Vector3(0, h, 0), Vector3.UP, Vector3.UP)
		_quad(st, d1 * r_int + Vector3(0, -h, 0), d1 * r_ext + Vector3(0, -h, 0), d0 * r_ext + Vector3(0, -h, 0), d0 * r_int + Vector3(0, -h, 0), Vector3.DOWN, Vector3.DOWN)
	return st.commit()


func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, na: Vector3, nb: Vector3) -> void:
	# a-b embaixo, c-d em cima, sentido anti-horário visto de fora
	for par in [[a, na], [c, nb], [b, nb], [a, na], [d, na], [c, nb]]:
		st.set_normal(par[1])
		st.add_vertex(par[0])


## Cabo flexível passando pelos pontos (curva suave).
func cabo(pai: Node3D, pontos: Array, r: float, mat: Material) -> MeshInstance3D:
	var curva := Curve3D.new()
	for i in pontos.size():
		var p: Vector3 = pontos[i]
		var t_in := Vector3.ZERO
		var t_out := Vector3.ZERO
		if i > 0 and i < pontos.size() - 1:
			var tg: Vector3 = (pontos[i + 1] - pontos[i - 1]) * 0.25
			t_in = -tg
			t_out = tg
		curva.add_point(p, t_in, t_out)
	curva.bake_interval = r * 2.0
	var pts := curva.get_baked_points()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var lados := 8
	var aneis: Array = []
	var ref := Vector3.UP
	for i in pts.size():
		var tg := (pts[mini(i + 1, pts.size() - 1)] - pts[maxi(i - 1, 0)]).normalized()
		if absf(tg.dot(ref)) > 0.95:
			ref = Vector3.RIGHT
		var u := tg.cross(ref).normalized()
		var v := tg.cross(u).normalized()
		var anel: Array = []
		for k in lados:
			var a := TAU * k / lados
			anel.append([pts[i] + (u * cos(a) + v * sin(a)) * r, (u * cos(a) + v * sin(a))])
		aneis.append(anel)
	for i in aneis.size() - 1:
		for k in lados:
			var a: Array = aneis[i][k]
			var b: Array = aneis[i][(k + 1) % lados]
			var c: Array = aneis[i + 1][(k + 1) % lados]
			var d: Array = aneis[i + 1][k]
			for q in [a, b, c, a, c, d]:
				st.set_normal(q[1])
				st.add_vertex(q[0])
	return malha(pai, st.commit(), mat)


# ------------------------------------------------------------------ componentes

## Motor brushless: base, estator de cobre aparecendo, sino com janelas, eixo.
## d = diâmetro do sino, a = altura total. Retorna a peça; o eixo fica em y = a.
func motor(pai: Node3D, rotulo: String, pos: Vector3, d: float, a: float, cor_sino: Color, sentido_horario: bool, explodir := Vector3(0, 0.0, 0)) -> Node3D:
	var p := peca(pai, "motor", rotulo, explodir)
	p.position = pos
	var sino := cor(cor_sino, 0.3, 0.9)
	var r := d / 2.0
	var base_h := a * 0.18
	# base com 4 braços (cruz) e furos
	cil(p, r * 0.92, base_h, aluminio(Color(0.18, 0.18, 0.2)), Vector3(0, base_h / 2, 0), Vector3.ZERO, 32)
	for k in 4:
		var ang := PI / 4 + k * PI / 2
		caixa(p, Vector3(r * 0.5, base_h * 0.6, r * 2.2), aluminio(Color(0.16, 0.16, 0.18)), Vector3(0, base_h * 0.3, 0), Vector3(0, ang, 0))
	# estator: núcleo de cobre com dentes visíveis no vão
	var vao := a * 0.12
	cil(p, r * 0.8, vao, cobre(), Vector3(0, base_h + vao / 2, 0), Vector3.ZERO, 12)
	# sino: parede lateral + tampa com janelas (raios)
	var parede_h := a - base_h - vao - a * 0.12
	var y0 := base_h + vao
	tubo(p, r, r * 0.9, parede_h, sino, Vector3(0, y0 + parede_h / 2, 0), Vector3.ZERO, 40)
	# frisos de refrigeração na lateral
	for k in 12:
		var ang := TAU * k / 12.0
		caixa(p, Vector3(r * 0.06, parede_h * 0.55, r * 0.05), cor(cor_sino.darkened(0.35), 0.4, 0.9),
			Vector3(cos(ang) * r * 1.0, y0 + parede_h * 0.45, sin(ang) * r * 1.0), Vector3(0, -ang, 0))
	# imãs (escuros) aparecendo por dentro
	tubo(p, r * 0.9, r * 0.83, parede_h * 0.9, cor(Color(0.25, 0.25, 0.27), 0.35, 0.8), Vector3(0, y0 + parede_h * 0.45, 0), Vector3.ZERO, 28)
	var tampa_y := y0 + parede_h
	var tampa_h := a * 0.07
	tubo(p, r, r * 0.72, tampa_h, sino, Vector3(0, tampa_y + tampa_h / 2, 0), Vector3.ZERO, 40)
	cil(p, r * 0.3, tampa_h, sino, Vector3(0, tampa_y + tampa_h / 2, 0), Vector3.ZERO, 24)
	var raios := 5
	for k in raios:
		var ang := TAU * k / raios + (0.3 if sentido_horario else -0.3)
		caixa(p, Vector3(r * 0.5, tampa_h, r * 0.16), sino, Vector3(cos(ang) * r * 0.5, tampa_y + tampa_h / 2, sin(ang) * r * 0.5), Vector3(0, -ang + (0.35 if sentido_horario else -0.35), 0))
	# eixo
	cil(p, r * 0.11, a * 0.14, aco(), Vector3(0, tampa_y + tampa_h + a * 0.05, 0), Vector3.ZERO, 16)
	# 3 fios do motor (fases)
	var cores_fio := [Color(0.08, 0.08, 0.08), Color(0.08, 0.08, 0.08), Color(0.08, 0.08, 0.08)]
	for k in 3:
		var off := (k - 1) * r * 0.18
		cil(p, r * 0.05, r * 0.6, cor(cores_fio[k], 0.5), Vector3(off, base_h * 0.5, -r * 1.1), Vector3(PI / 2, 0, 0), 6)
	p.set_meta("sentido", "horário" if sentido_horario else "anti-horário")
	return p


## Hélice com pás torcidas de verdade (perfil e torção calculados pelo passo).
func helice(pai: Node3D, rotulo: String, pos: Vector3, diam: float, passo: float, pas: int, mat: Material, sentido_horario: bool, explodir := Vector3(0, 0.0, 0), corda_rel := 0.12) -> Node3D:
	var p := peca(pai, "helice", rotulo, explodir)
	p.position = pos
	var r_tot := diam / 2.0
	var r_cubo := maxf(r_tot * 0.08, 0.0035)
	cil(p, r_cubo, r_cubo * 1.6, mat, Vector3.ZERO, Vector3.ZERO, 20)
	var pa := _malha_pa(r_tot, r_cubo, passo, corda_rel, sentido_horario)
	for k in pas:
		malha(p, pa, mat, Vector3.ZERO, Vector3(0, TAU * k / pas, 0))
	# porca
	cil(p, r_cubo * 0.65, r_cubo * 1.2, aluminio(Color(0.7, 0.15, 0.12)), Vector3(0, r_cubo * 1.3, 0), Vector3.ZERO, 6)
	p.set_meta("sentido", "horário (CW)" if sentido_horario else "anti-horário (CCW)")
	return p


func _malha_pa(r_tot: float, r_cubo: float, passo: float, corda_rel: float, cw: bool) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var secoes := 14
	var perfil := 10
	var s_dir := 1.0 if cw else -1.0
	var aneis: Array = []
	for i in secoes + 1:
		var t := float(i) / secoes
		var r := lerpf(r_cubo * 0.8, r_tot, t)
		# corda: cresce até ~30% e afina na ponta (ponta arredondada)
		var corda := r_tot * corda_rel * (0.55 + 1.3 * t * (1.0 - t) * 2.0) * (1.0 - pow(t, 6.0) * 0.85)
		var torc := atan2(passo, TAU * maxf(r, 0.001))
		var esp := corda * lerpf(0.16, 0.07, t)
		var anel: Array = []
		for k in perfil:
			var u := float(k) / perfil
			var ang := u * TAU
			var x := cos(ang) * 0.5 * corda
			var y := sin(ang) * esp * (0.75 if sin(ang) > 0 else 0.25)
			# gira a seção pela torção (ângulo de ataque)
			var xr := x * cos(torc) - y * sin(torc) * s_dir
			var yr := x * sin(torc) * s_dir + y * cos(torc)
			anel.append(Vector3(xr, yr, r))
		aneis.append(anel)
	for i in secoes:
		for k in perfil:
			var a: Vector3 = aneis[i][k]
			var b: Vector3 = aneis[i][(k + 1) % perfil]
			var c: Vector3 = aneis[i + 1][(k + 1) % perfil]
			var d: Vector3 = aneis[i + 1][k]
			var n := (b - a).cross(d - a).normalized()
			for v in [a, c, b, a, d, c]:
				st.set_normal(n)
				st.add_vertex(v)
	st.generate_normals()
	return st.commit()


func xt60(pai: Node3D, pos: Vector3, rot := Vector3.ZERO, esc := 1.0) -> Node3D:
	var n := Node3D.new()
	pai.add_child(n)
	n.position = pos
	n.rotation = rot
	n.scale = Vector3.ONE * esc
	caixa(n, Vector3(0.016, 0.008, 0.016), cor(Color(0.95, 0.75, 0.05), 0.4), Vector3.ZERO)
	caixa(n, Vector3(0.006, 0.0085, 0.004), cor(Color(0.8, 0.6, 0.04), 0.4), Vector3(0.006, 0, 0.0062))
	for s: float in [-1.0, 1.0]:
		cil(n, 0.0022, 0.004, ouro(), Vector3(s * 0.0038, 0, 0.0095), Vector3(PI / 2, 0, 0), 10)
	return n


## Bateria LiPo com etiqueta, cabos e conector.
func bateria(pai: Node3D, rotulo: String, pos: Vector3, tam: Vector3, cor_etiqueta: Color, texto_cor: Color, explodir := Vector3.ZERO, conector_esc := 1.0) -> Node3D:
	var p := peca(pai, "bateria", rotulo, explodir)
	p.position = pos
	var raio := minf(tam.y, tam.x) * 0.12
	# corpo prateado + etiqueta (capa encolhida) por cima
	caixa_redonda(p, Vector3(tam.x * 0.99, tam.y * 0.98, tam.z), raio, cor(Color(0.6, 0.6, 0.62), 0.35, 0.6), Vector3.ZERO, Vector3(PI / 2, 0, 0) * 0.0)
	caixa_redonda(p, Vector3(tam.x, tam.y, tam.z * 0.86), raio, cor(cor_etiqueta, 0.45, 0.0, 0.5))
	# faixas decorativas da etiqueta
	caixa(p, Vector3(tam.x * 1.002, tam.y * 0.25, tam.z * 0.5), cor(texto_cor, 0.5), Vector3(0, tam.y * 0.18, 0))
	caixa(p, Vector3(tam.x * 1.002, tam.y * 0.08, tam.z * 0.7), cor(texto_cor.lightened(0.3), 0.5), Vector3(0, -tam.y * 0.15, 0))
	# cabos de força saindo da ponta
	var saida := Vector3(0, tam.y * 0.1, tam.z / 2)
	var vermelho := cor(Color(0.75, 0.05, 0.04), 0.45)
	var preto := cor(Color(0.04, 0.04, 0.04), 0.45)
	var rr := tam.y * 0.07 * conector_esc
	cabo(p, [saida + Vector3(rr * 1.4, 0, 0), saida + Vector3(rr * 1.6, tam.y * 0.1, tam.z * 0.1), saida + Vector3(rr * 1.2, tam.y * 0.5, tam.z * 0.25)], rr, vermelho)
	cabo(p, [saida + Vector3(-rr * 1.4, 0, 0), saida + Vector3(-rr * 1.6, tam.y * 0.1, tam.z * 0.1), saida + Vector3(-rr * 1.2, tam.y * 0.5, tam.z * 0.25)], rr, preto)
	xt60(p, saida + Vector3(0, tam.y * 0.5, tam.z * 0.25 + 0.008 * conector_esc), Vector3(PI / 2, 0, 0), conector_esc)
	# cabo de balanceamento (fino, branco)
	var cb := Vector3(tam.x * 0.35, -tam.y * 0.2, tam.z / 2)
	cabo(p, [cb, cb + Vector3(0, -tam.y * 0.05, tam.z * 0.12), cb + Vector3(-tam.x * 0.05, -tam.y * 0.15, tam.z * 0.2)], rr * 0.45, cor(Color(0.85, 0.85, 0.82), 0.5))
	caixa(p, Vector3(rr * 4.0, rr * 1.6, rr * 2.0), cor(Color(0.95, 0.95, 0.92), 0.5), cb + Vector3(-tam.x * 0.05, -tam.y * 0.15, tam.z * 0.2 + rr))
	return p


## Fita/velcro que prende a bateria.
func fita(pai: Node3D, pos: Vector3, largura: float, contorno: Vector2, cor_fita := Color(0.06, 0.06, 0.07)) -> void:
	var m := cor(cor_fita, 0.9)
	var e := 0.0012
	caixa(pai, Vector3(contorno.x + e * 2, e, largura), m, pos + Vector3(0, contorno.y / 2 + e / 2, 0))
	caixa(pai, Vector3(contorno.x + e * 2, e, largura), m, pos + Vector3(0, -contorno.y / 2 - e / 2, 0))
	for s: float in [-1.0, 1.0]:
		caixa(pai, Vector3(e, contorno.y + e * 2, largura), m, pos + Vector3(s * (contorno.x / 2 + e / 2), 0, 0))
	# fivela
	caixa(pai, Vector3(largura * 0.8, e * 3, largura * 1.15), cor(Color(0.25, 0.25, 0.28), 0.35, 0.8), pos + Vector3(contorno.x * 0.25, contorno.y / 2 + e * 2, 0))


## Placa com componentes eletrônicos espalhados (ESC, receptor, etc.).
func placa(pai: Node3D, tam: Vector3, verniz: Color, semente: float, pos := Vector3.ZERO, rot := Vector3.ZERO, componentes := 10) -> Node3D:
	var n := Node3D.new()
	pai.add_child(n)
	n.position = pos
	n.rotation = rot
	caixa(n, tam, pcb(verniz, verniz.lightened(0.25), semente))
	var rng := RandomNumberGenerator.new()
	rng.seed = int(semente * 1000.0) + 7
	for i in componentes:
		var w := rng.randf_range(0.08, 0.22) * tam.x
		var d := rng.randf_range(0.08, 0.22) * tam.z
		var h := rng.randf_range(0.6, 2.0) * tam.y
		var x := rng.randf_range(-0.5, 0.5) * (tam.x - w)
		var z := rng.randf_range(-0.5, 0.5) * (tam.z - d)
		var tipo := rng.randi() % 3
		var m: Material = cor(Color(0.07, 0.07, 0.075), 0.4) if tipo != 2 else cor(Color(0.55, 0.45, 0.3), 0.5)
		caixa(n, Vector3(w, h, d), m, Vector3(x, tam.y / 2 + h / 2, z))
	return n


## Antena em "T" (receptor) ou fio reto, com ponta descascada.
func antena_fio(pai: Node3D, base: Vector3, direcao: Vector3, comp: float, r := 0.0009) -> void:
	var fim := base + direcao.normalized() * comp
	var meio := base.lerp(fim, 0.6)
	cabo(pai, [base, meio, fim], r, cor(Color(0.05, 0.05, 0.05), 0.5))
	cabo(pai, [fim, fim + direcao.normalized() * comp * 0.35], r * 0.6, cor(Color(0.85, 0.85, 0.85), 0.3))


## Parafuso de cabeça sextavada interna (enfeite fiel).
func parafuso(pai: Node3D, pos: Vector3, r: float, mat: Material = null, rot := Vector3.ZERO) -> void:
	var m := mat if mat != null else aco()
	cil(pai, r, r * 0.6, m, pos, rot, 16)
	cil(pai, r * 0.45, r * 0.62, cor(Color(0.08, 0.08, 0.08), 0.6), pos + Vector3(0, r * 0.02, 0), rot, 6)


## Espaçador (standoff) entre placas.
func espacador(pai: Node3D, pos: Vector3, r: float, alt: float, mat: Material) -> void:
	cil(pai, r, alt, mat, pos + Vector3(0, alt / 2, 0), Vector3.ZERO, 6)
