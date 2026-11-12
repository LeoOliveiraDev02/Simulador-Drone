shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;
#include "res://shaders/nuvens.gdshaderinc"
// folhas das árvores e arbustos balançando com o vento do mapa

uniform sampler2D alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D nor : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tom : source_color = vec4(1.0);
uniform vec3 luz_atras : source_color = vec3(0.22, 0.28, 0.1);
uniform vec2 vento_dir = vec2(1.0, 0.35);
uniform float vento_forca = 0.05;
uniform float altura_ref = 4.0;
uniform float corte = 0.3;
varying vec3 wpos_f;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	wpos_f = wp;
	float alt = clamp(VERTEX.y / altura_ref, 0.0, 1.0);
	float t = TIME;
	float balanco = sin(t * 1.1 + wp.x * 0.21 + wp.z * 0.17) * 0.55 + sin(t * 2.3 + wp.x * 0.5 - wp.z * 0.3) * 0.25;
	float tremor = sin(t * 8.0 + VERTEX.x * 7.0 + VERTEX.z * 5.0 + VERTEX.y * 3.0);
	vec3 dir = vec3(vento_dir.x, 0.0, vento_dir.y);
	vec3 desl = dir * (0.55 + balanco) * vento_forca * alt * alt;
	desl += vec3(tremor, tremor * 0.4, -tremor) * vento_forca * 0.12 * alt;
	VERTEX += inverse(mat3(MODEL_MATRIX)) * desl;
}

void fragment() {
	vec4 c = texture(alb, UV) * tom;
	ALBEDO = c.rgb * sombra_nuvem(wpos_f);
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = corte;
	NORMAL_MAP = texture(nor, UV).rgb;
	ROUGHNESS = 0.75;
	SPECULAR = 0.35;
	BACKLIGHT = luz_atras;
}
