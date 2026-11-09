shader_type spatial;

uniform sampler2D c_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D c_nor : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D c_arm : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D ruido : filter_linear_mipmap, repeat_enable;
uniform float raio = 9.0;

varying vec3 lp;

void vertex() {
	lp = VERTEX;
}

void fragment() {
	vec2 p = lp.xz;
	float r = length(p);
	vec2 uv = p / 3.5;
	vec3 base = texture(c_alb, uv).rgb * vec3(0.92, 0.9, 0.86);
	vec3 arm = texture(c_arm, uv).rgb;

	// anel e "H" pintados
	float anel = step(6.85, r) * step(r, 7.35);
	float barras = (step(abs(p.x + 2.15), 0.5) + step(abs(p.x - 2.15), 0.5)) * step(abs(p.y), 3.25);
	float travessa = step(abs(p.x), 1.65) * step(abs(p.y), 0.42);
	float tinta = clamp(anel + barras + travessa, 0.0, 1.0);
	float desgaste = smoothstep(0.3, 0.62, texture(ruido, p / 2.6).r);
	tinta *= mix(0.45, 1.0, desgaste);

	// sujeira de terra na borda
	float sujeira = smoothstep(raio - 1.6, raio, r) * smoothstep(0.35, 0.7, texture(ruido, p / 1.4).r);
	base = mix(base, base * vec3(0.78, 0.62, 0.48), sujeira * 0.8);

	ALBEDO = mix(base, vec3(0.9, 0.9, 0.88), tinta);
	NORMAL_MAP = texture(c_nor, uv).rgb;
	ROUGHNESS = mix(arm.g, 0.7, tinta);
	AO = arm.r;
}
