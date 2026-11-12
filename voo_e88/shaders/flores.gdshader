shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/nuvens.gdshaderinc"
// flores do campo: caule verde e uma cabeça com pétalas recortadas (cor por instância)

uniform vec2 vento_dir = vec2(1.0, 0.35);
uniform float vento_forca = 0.2;

varying vec4 dados;
varying vec3 wpos;

void vertex() {
	dados = INSTANCE_CUSTOM;
	vec3 wp = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	wpos = wp;
	float t = TIME;
	float onda = sin(t * 1.7 + wp.x * 0.4 + wp.z * 0.3) * 0.6 + sin(t * 2.9 + wp.x * 1.1) * 0.3;
	float alt = clamp(VERTEX.y, 0.0, 1.3);
	vec3 desl = vec3(vento_dir.x, 0.0, vento_dir.y) * onda * vento_forca * 0.12 * alt * alt;
	VERTEX += inverse(mat3(MODEL_MATRIX)) * desl;
}

void fragment() {
	float sn = sombra_nuvem(wpos);
	if (UV.x < 0.0) {
		ALBEDO = vec3(0.16, 0.3, 0.07) * sn;
		ROUGHNESS = 0.7;
	} else {
		vec2 c = UV * 2.0 - 1.0;
		float r = length(c);
		float ang = atan(c.y, c.x);
		int tipo = int(dados.a * 3.0);
		float petalas = tipo == 0 ? 8.0 : (tipo == 1 ? 5.0 : 12.0);
		float borda = 0.62 + 0.32 * abs(cos(ang * petalas * 0.5));
		if (r > borda) {
			discard;
		}
		vec3 cor = dados.rgb;
		// miolo amarelo/marrom e pétalas mais claras na ponta
		float miolo = 1.0 - smoothstep(0.16, 0.24, r);
		cor = mix(cor * mix(0.75, 1.1, r), vec3(0.85, 0.6, 0.1), miolo);
		ALBEDO = cor * sn;
		ROUGHNESS = 0.55;
		BACKLIGHT = cor * 0.45;
	}
	SPECULAR = 0.3;
}
