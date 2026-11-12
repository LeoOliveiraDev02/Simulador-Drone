shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx, cull_back, depth_draw_always;
// açude: cor pela profundidade, refração do fundo, reflexo do céu, espuma na margem e ondinhas com o vento

uniform sampler2D ondas : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D tela : hint_screen_texture, filter_linear_mipmap;
uniform sampler2D prof : hint_depth_texture, filter_linear_mipmap;
uniform vec3 cor_funda : source_color = vec3(0.025, 0.07, 0.06);
uniform vec3 cor_rasa : source_color = vec3(0.22, 0.26, 0.16);
uniform float turbidez = 0.55; // água de açude: barrenta

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = wpos.xz / 9.0;
	vec3 n1 = texture(ondas, uv + vec2(TIME * 0.012, TIME * 0.007)).rgb;
	vec3 n2 = texture(ondas, uv * 1.9 + vec2(-TIME * 0.009, TIME * 0.011)).rgb;
	vec3 n3 = texture(ondas, uv * 5.3 + vec2(TIME * 0.03, -TIME * 0.02)).rgb;
	vec3 nm = normalize(mix(mix(n1, n2, 0.5), n3, 0.3) * 2.0 - 1.0);
	NORMAL_MAP = nm * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = 0.45;

	// profundidade da água atrás deste pixel
	float d_cena = texture(prof, SCREEN_UV).r;
	vec4 p = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, d_cena, 1.0);
	p.xyz /= p.w;
	float espessura = clamp(-p.z - (-VERTEX.z), 0.0, 20.0);

	// refração: desloca um pouco o fundo conforme as ondas
	vec2 desloc = nm.xy * 0.02 * clamp(espessura, 0.0, 1.0);
	vec3 fundo = textureLod(tela, SCREEN_UV + desloc, 0.0).rgb;
	float absorve = 1.0 - exp(-espessura * turbidez);
	vec3 agua = mix(fundo * vec3(0.75, 0.85, 0.78), mix(cor_rasa, cor_funda, clamp(espessura / 3.0, 0.0, 1.0)), absorve);

	// espuma fina na margem
	float espuma = (1.0 - smoothstep(0.0, 0.18, espessura)) * smoothstep(0.35, 0.7, n3.r + 0.15 * sin(TIME * 1.5 + wpos.x * 2.0));
	agua = mix(agua, vec3(0.85, 0.85, 0.8), espuma * 0.6);

	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 5.0);
	// a cor vai na emissão (o fundo já vem iluminado); o reflexo do céu vem do brilho especular
	ALBEDO = vec3(0.0);
	EMISSION = agua * (1.0 - fres * 0.6);
	ROUGHNESS = mix(0.03, 0.4, espuma);
	METALLIC = 0.0;
	SPECULAR = 0.6;
}
