shader_type spatial;
render_mode cull_disabled;

uniform vec3 laranja : source_color = vec3(0.95, 0.33, 0.08);
uniform vec3 branco : source_color = vec3(0.92, 0.9, 0.86);

void vertex() {
	// tremulação do tecido, mais forte na ponta
	float ponta = 1.0 - UV.y;
	VERTEX.x += sin(TIME * 7.0 + UV.y * 9.0) * 0.04 * ponta;
	VERTEX.z += cos(TIME * 5.0 + UV.y * 7.0) * 0.03 * ponta;
}

void fragment() {
	float faixa = step(0.5, fract(UV.y * 2.5));
	ALBEDO = mix(laranja, branco, faixa);
	ROUGHNESS = 0.85;
	BACKLIGHT = ALBEDO * 0.4;
}
