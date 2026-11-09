shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D ondas : hint_normal, filter_linear_mipmap, repeat_enable;
uniform vec3 cor_funda : source_color = vec3(0.04, 0.09, 0.08);
uniform vec3 cor_rasa : source_color = vec3(0.16, 0.20, 0.13);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = wpos.xz / 9.0;
	vec3 n1 = texture(ondas, uv + vec2(TIME * 0.012, TIME * 0.007)).rgb;
	vec3 n2 = texture(ondas, uv * 1.9 + vec2(-TIME * 0.009, TIME * 0.011)).rgb;
	NORMAL_MAP = mix(n1, n2, 0.5);
	NORMAL_MAP_DEPTH = 0.35;
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = mix(cor_rasa, cor_funda, 0.6 + 0.4 * fres);
	ROUGHNESS = 0.04;
	METALLIC = 0.0;
	SPECULAR = 0.55;
}
