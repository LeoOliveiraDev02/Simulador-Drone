extends SceneTree

func _init() -> void:
	for nome in ["island_tree_01", "island_tree_02", "island_tree_03", "tree_small_02", "jacaranda_tree", "shrub_02", "shrub_04"]:
		for pasta in ["modelos_pc", "modelos_movel"]:
			var p := "res://recursos/%s/%s.glb" % [pasta, nome]
			if not ResourceLoader.exists(p):
				p = "res://recursos/modelos/%s/%s_1k.gltf" % [nome, nome]
			var no: Node = (load(p) as PackedScene).instantiate()
			print("== ", nome, " ", pasta, " ", p)
			_listar(no, Transform3D())
			no.free()
	quit()

func _listar(n: Node, xf: Transform3D) -> void:
	var t := xf
	if n is Node3D:
		t = xf * (n as Node3D).transform
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		for s in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(s)
			var tri: int = mi.mesh.surface_get_array_index_len(s) / 3
			var transp := ""
			if m is BaseMaterial3D:
				transp = str((m as BaseMaterial3D).transparency)
			print("  ", mi.name, " s", s, " mat=", m.resource_name if m else "-", " transp=", transp, " tri=", tri, " aabb=", t * mi.get_aabb())
	for f in n.get_children():
		_listar(f, t)
