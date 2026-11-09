shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

// Pasto de perto (grass_ground) e de longe (aerial_grass_rock)
uniform sampler2D grama_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grama_nor : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grama_arm : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D aerea_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D aerea_nor : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
// Estrada de terra vermelha e lama seca
uniform sampler2D terra_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D terra_nor : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D terra_arm : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D lama_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D lama_nor : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
// Ruído para quebrar repetição e variar a cor do pasto
uniform sampler2D ruido : filter_linear_mipmap, repeat_enable;

uniform vec3 tom_verde : source_color = vec3(0.62, 0.86, 0.38);
uniform vec3 tom_seco : source_color = vec3(0.92, 0.95, 0.58);
uniform float escala_grama = 3.0;
uniform float escala_aerea = 42.0;
uniform float escala_terra = 4.5;

varying vec3 wpos;
varying vec4 mascara;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	mascara = COLOR;
	TANGENT = normalize(vec3(1.0, 0.0, 0.0) - NORMAL * NORMAL.x);
	BINORMAL = normalize(cross(NORMAL, TANGENT));
}

vec3 amostra_sem_repeticao(sampler2D t, vec2 uv, float mistura) {
	vec3 a = texture(t, uv).rgb;
	vec3 b = texture(t, uv * 0.43 + vec2(0.37, 0.71)).rgb;
	return mix(a, b, mistura);
}

void fragment() {
	float dist = length(wpos - CAMERA_POSITION_WORLD);
	float n_macro = texture(ruido, wpos.xz / 260.0).r;
	float n_medio = texture(ruido, wpos.xz / 31.0).r;
	float n_fino = texture(ruido, wpos.xz / 6.0).r;
	float mist = smoothstep(0.35, 0.65, n_medio);

	vec2 uv_g = wpos.xz / escala_grama;
	vec2 uv_a = wpos.xz / escala_aerea;
	vec2 uv_t = wpos.xz / escala_terra;

	// pasto
	vec3 g_perto = amostra_sem_repeticao(grama_alb, uv_g, mist);
	vec3 g_longe = texture(aerea_alb, uv_a).rgb;
	float longe = smoothstep(20.0, 140.0, dist);
	vec3 pasto = mix(g_perto, g_longe, longe * 0.75);
	pasto *= mix(tom_verde, tom_seco, smoothstep(0.45, 0.85, n_macro * 0.7 + n_fino * 0.3));
	// longe o pasto fica mais verde-azulado, como na foto de referência
	pasto = mix(pasto, pasto * vec3(0.78, 0.95, 0.8), smoothstep(150.0, 900.0, dist));
	vec3 nor_pasto = mix(texture(grama_nor, uv_g).rgb, texture(aerea_nor, uv_a).rgb, longe);
	vec3 arm_pasto = texture(grama_arm, uv_g).rgb;

	// estrada, lama do açude e terra batida perto da base/galpão
	float terra = smoothstep(0.38, 0.62, mascara.r + (n_fino - 0.5) * 0.35 + (n_medio - 0.5) * 0.2);
	float lama = smoothstep(0.32, 0.68, mascara.g + (n_medio - 0.5) * 0.35);
	float solo = smoothstep(0.35, 0.7, mascara.b + (n_fino - 0.5) * 0.5 + (n_medio - 0.5) * 0.25);

	vec3 c_terra = texture(terra_alb, uv_t).rgb;
	vec3 c_lama = texture(lama_alb, uv_t * 0.8).rgb;
	vec3 albedo = pasto;
	albedo = mix(albedo, c_lama, max(lama, solo * 0.75));
	albedo = mix(albedo, c_terra, terra);

	vec3 nor = nor_pasto;
	nor = mix(nor, texture(lama_nor, uv_t * 0.8).rgb, max(lama, solo * 0.75));
	nor = mix(nor, texture(terra_nor, uv_t).rgb, terra);
	vec3 arm = mix(arm_pasto, texture(terra_arm, uv_t).rgb, terra);

	ALBEDO = albedo;
	NORMAL_MAP = nor;
	NORMAL_MAP_DEPTH = mix(1.0, 0.4, longe);
	ROUGHNESS = clamp(arm.g * 1.05, 0.55, 1.0);
	AO = mix(arm.r, 1.0, longe);
	AO_LIGHT_AFFECT = 0.3;
	SPECULAR = 0.35;
}
