extends GPUParticles3D
class_name Poeira
## Poeira levantada pelo vento das hélices quando o drone voa baixo (mais forte na terra
## e no concreto da base, quase nada no capim).

var drone: E88
var mapa: Mapa


func _ready() -> void:
	amount = 160
	lifetime = 1.4
	explosiveness = 0.0
	randomness = 0.6
	local_coords = false
	draw_order = GPUParticles3D.DRAW_ORDER_VIEW_DEPTH
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	pm.emission_ring_axis = Vector3.UP
	pm.emission_ring_radius = 0.12
	pm.emission_ring_inner_radius = 0.05
	pm.emission_ring_height = 0.01
	pm.direction = Vector3(1, 0.15, 0)
	pm.spread = 180.0
	pm.flatness = 0.85
	pm.initial_velocity_min = 0.6
	pm.initial_velocity_max = 1.6
	pm.gravity = Vector3(0, 0.05, 0)
	pm.damping_min = 1.2
	pm.damping_max = 2.2
	pm.scale_min = 0.6
	pm.scale_max = 1.8
	var curva := Curve.new()
	curva.add_point(Vector2(0, 0.3))
	curva.add_point(Vector2(1, 1.4))
	var ct := CurveTexture.new()
	ct.curve = curva
	pm.scale_curve = ct
	var g := Gradient.new()
	g.set_color(0, Color(0.72, 0.64, 0.52, 0.0))
	g.add_point(0.15, Color(0.72, 0.64, 0.52, 0.35))
	g.set_color(g.get_point_count() - 1, Color(0.72, 0.64, 0.52, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = g
	pm.color_ramp = gt
	process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(0.12, 0.12)
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	var tex := GradientTexture2D.new()
	var g2 := Gradient.new()
	g2.set_color(0, Color(1, 1, 1, 1))
	g2.set_color(1, Color(1, 1, 1, 0))
	tex.gradient = g2
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(0.5, 0.0)
	m.albedo_texture = tex
	q.material = m
	draw_pass_1 = q
	emitting = false
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _process(_delta: float) -> void:
	if drone == null or mapa == null:
		return
	var p := drone.global_position
	var h := p.y - 0.026 - drone.chao_y
	var soma := 0.0
	for e in drone.empuxo:
		soma += e
	var forca := clampf(soma / (E88.MASSA * E88.G), 0.0, 1.6)
	# superfície: base de concreto e estrada soltam mais poeira que o capim
	var mascara := mapa._mascara(p.x, p.z)
	var solto := clampf(mascara.r + mascara.b * 0.7, 0.15, 1.0)
	var nivel := forca * clampf(1.0 - h / 0.6, 0.0, 1.0) * solto
	emitting = drone.armado and nivel > 0.08
	amount_ratio = clampf(nivel, 0.0, 1.0)
	global_position = Vector3(p.x, drone.chao_y + 0.02, p.z)
	speed_scale = lerpf(0.7, 1.3, clampf(forca, 0.0, 1.0))
