extends SceneTree
## Gera recursos/colisao/<nome>.res para cada árvore/arbusto:
##  - a forma de colisão EXATA da casca (tronco + galhos), triângulo por triângulo;
##  - meta "folhas": células (cubinhos) onde existe folha de verdade (lê a transparência
##    da textura, então o vazio entre as folhas não conta).
## Rodar com tela (xvfb-run), porque precisa ler as texturas:
##   xvfb-run godot --path . --script ferramentas/gerar_colisao_arvores.gd

# nome, tamanho do cubinho em unidades do modelo (~15 cm no mundo depois da escala do mapa)
const ITENS := [
	["island_tree_01", 0.055],
	["island_tree_02", 0.055],
	["island_tree_03", 0.045],
	["tree_small_02", 0.065],
	["jacaranda_tree", 0.15],
	["shrub_02", 0.1],
	["shrub_04", 0.025],
]

var faces := PackedVector3Array()
var celulas := {}
var cel := 0.1
var origem := Vector3.ZERO
var dims := Vector3i.ONE
var cache_img := {}


func _init() -> void:
	DirAccess.make_dir_recursive_absolute("res://recursos/colisao")
	var so := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--so="):
			so = a.get_slice("=", 1)
	for item in ITENS:
		if so != "" and item[0] != so:
			continue
		_gerar(item[0], item[1])
	quit()


func _caminho(nome: String) -> String:
	for p in ["res://recursos/modelos_pc/%s.glb" % nome, "res://recursos/modelos/%s/%s_1k.gltf" % [nome, nome], "res://recursos/modelos_movel/%s.glb" % nome]:
		if ResourceLoader.exists(p):
			return p
	return ""


func _gerar(nome: String, tam_cel: float) -> void:
	var t0 := Time.get_ticks_msec()
	var raiz: Node3D = (load(_caminho(nome)) as PackedScene).instantiate()
	faces = PackedVector3Array()
	celulas = {}
	cel = tam_cel
	# 1ª passada: caixa das folhas (para montar a grade)
	var caixa := AABB()
	var tem := false
	for par in _malhas(raiz):
		var mi: MeshInstance3D = par[0]
		var xf: Transform3D = par[1]
		for s in mi.mesh.get_surface_count():
			if _eh_folha(mi.mesh.surface_get_material(s)):
				var verts: PackedVector3Array = mi.mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX]
				for v in verts:
					var w := xf * v
					if not tem:
						caixa = AABB(w, Vector3.ZERO)
						tem = true
					else:
						caixa = caixa.expand(w)
	origem = caixa.position - Vector3.ONE * cel
	dims = Vector3i((caixa.size / cel).ceil()) + Vector3i(3, 3, 3)
	# 2ª passada: casca vira triângulos de colisão; folhas viram células
	var n_folha := 0
	for par in _malhas(raiz):
		var mi: MeshInstance3D = par[0]
		var xf: Transform3D = par[1]
		for s in mi.mesh.get_surface_count():
			var arr := mi.mesh.surface_get_arrays(s)
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
			if idx.is_empty():
				idx.resize(verts.size())
				for i in verts.size():
					idx[i] = i
			var mat := mi.mesh.surface_get_material(s)
			if _eh_folha(mat):
				var uvs: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
				var img := _imagem(mat)
				n_folha += idx.size() / 3
				_marcar_folhas(verts, idx, uvs, img, xf)
			else:
				for i in idx.size():
					faces.append(xf * verts[idx[i]])
	var chaves := PackedInt32Array(celulas.keys())
	chaves.sort()
	var forma := ConcavePolygonShape3D.new()
	forma.backface_collision = true
	forma.set_faces(faces)
	forma.set_meta("folhas", chaves)
	forma.set_meta("cel", cel)
	forma.set_meta("origem", origem)
	forma.set_meta("dims", dims)
	forma.set_meta("caixa_folhas", caixa)
	var destino := "res://recursos/colisao/%s.res" % nome
	ResourceSaver.save(forma, destino, ResourceSaver.FLAG_COMPRESS)
	print("%s: casca %d triângulos, folhas %d triângulos -> %d células de %.3f (%d ms)" % [nome, faces.size() / 3, n_folha, chaves.size(), cel, Time.get_ticks_msec() - t0])
	raiz.free()


func _malhas(raiz: Node) -> Array:
	var lista := []
	var pilha := [[raiz, Transform3D()]]
	while pilha.size() > 0:
		var item: Array = pilha.pop_back()
		var n: Node = item[0]
		var xf: Transform3D = item[1]
		for f in n.get_children():
			var xf2 := xf
			if f is Node3D:
				xf2 = xf * (f as Node3D).transform
			if f is MeshInstance3D:
				lista.append([f, xf2])
			pilha.append([f, xf2])
	return lista


func _eh_folha(m: Material) -> bool:
	return m is BaseMaterial3D and (m as BaseMaterial3D).transparency != BaseMaterial3D.TRANSPARENCY_DISABLED


func _imagem(m: Material) -> Image:
	var bm := m as BaseMaterial3D
	if bm.albedo_texture == null:
		return null
	if cache_img.has(bm.albedo_texture):
		return cache_img[bm.albedo_texture]
	var img := bm.albedo_texture.get_image()
	if img and img.is_compressed():
		img.decompress()
	if img and img.get_width() > 512:
		img.resize(512, 512 * img.get_height() / img.get_width(), Image.INTERPOLATE_BILINEAR)
	cache_img[bm.albedo_texture] = img
	return img


func _marcar_folhas(verts: PackedVector3Array, idx: PackedInt32Array, uvs: PackedVector2Array, img: Image, xf: Transform3D) -> void:
	var w := img.get_width() if img else 1
	var h := img.get_height() if img else 1
	var passo_max := cel * 0.5
	for t in range(0, idx.size(), 3):
		var a := xf * verts[idx[t]]
		var b := xf * verts[idx[t + 1]]
		var c := xf * verts[idx[t + 2]]
		var ua := uvs[idx[t]]
		var ub := uvs[idx[t + 1]]
		var uc := uvs[idx[t + 2]]
		var lado := maxf(a.distance_to(b), maxf(b.distance_to(c), c.distance_to(a)))
		# pontos no meio de cada triangulinho (os cantos do cartão de folha costumam ser transparentes)
		var n := clampi(int(ceil(lado / passo_max)), 3, 16)
		for i in n:
			for j in n - i:
				for tipo in (2 if i + j < n - 1 else 1):
					var u := (float(i) + (1.0 / 3.0 if tipo == 0 else 2.0 / 3.0)) / n
					var v := (float(j) + (1.0 / 3.0 if tipo == 0 else 2.0 / 3.0)) / n
					var k := 1.0 - u - v
					if img:
						var uv := ua * k + ub * u + uc * v
						var px := posmod(int(uv.x * w), w)
						var py := posmod(int(uv.y * h), h)
						if img.get_pixel(px, py).a < 0.5:
							continue
					var p := a * k + b * u + c * v
					var q := Vector3i(((p - origem) / cel).floor())
					if q.x < 0 or q.y < 0 or q.z < 0 or q.x >= dims.x or q.y >= dims.y or q.z >= dims.z:
						continue
					celulas[q.x + q.y * dims.x + q.z * dims.x * dims.y] = true
