shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform vec3 cor_base : source_color = vec3(0.07, 0.15, 0.03);
uniform vec3 cor_ponta : source_color = vec3(0.30, 0.50, 0.11);
uniform vec3 cor_seca : source_color = vec3(0.55, 0.52, 0.26);
uniform float vento_forca = 0.22;
uniform vec2 vento_dir = vec2(1.0, 0.35);
// vento das hélices do drone (empurra o capim para fora quando ele voa baixo)
uniform vec3 drone_pos = vec3(0.0, -1000.0, 0.0);
uniform float drone_forca = 0.0;

varying float altura_folha;
varying float seca;
varying float variacao;

void vertex() {
	altura_folha = UV.y;
	seca = INSTANCE_CUSTOM.r;
	variacao = INSTANCE_CUSTOM.g;
	vec3 wp = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float t = TIME;
	float rajada = sin(t * 0.6 + wp.x * 0.03 + wp.z * 0.02) * 0.5 + 0.5;
	float onda = sin(t * 1.9 + wp.x * 0.45 + wp.z * 0.25) * 0.6 + sin(t * 3.1 + wp.x * 1.3 - wp.z * 0.7) * 0.25;
	float curva = altura_folha * altura_folha;
	vec3 deslocamento = vec3(vento_dir.x, 0.0, vento_dir.y) * (onda * 0.5 + rajada * 0.8) * vento_forca * curva;
	vec3 rel = wp - drone_pos;
	float r2 = dot(rel.xz, rel.xz);
	float alt_d = drone_pos.y - wp.y;
	float sopro = drone_forca * exp(-r2 / 0.5) * clamp(1.0 - alt_d / 1.6, 0.0, 1.0) * step(-0.2, alt_d);
	vec2 para_fora = rel.xz / max(sqrt(r2), 0.05);
	float tremor = 0.75 + 0.25 * sin(t * 31.0 + wp.x * 17.0 + wp.z * 13.0);
	deslocamento += vec3(para_fora.x, -0.35, para_fora.y) * sopro * tremor * curva;
	// o deslocamento é aplicado no espaço do mundo
	VERTEX += (inverse(mat3(MODEL_MATRIX)) * deslocamento);
	// normal puxada para cima: a grama ilumina como o chão, sem brilho estranho
	NORMAL = normalize(mix(NORMAL, inverse(mat3(MODEL_MATRIX)) * vec3(0.0, 1.0, 0.0), 0.65));
}

void fragment() {
	vec3 c = mix(cor_base, cor_ponta, smoothstep(0.0, 1.0, altura_folha));
	c *= mix(0.82, 1.18, variacao);
	c = mix(c, cor_seca * mix(0.7, 1.1, altura_folha), seca);
	ALBEDO = c;
	ROUGHNESS = 0.62;
	SPECULAR = 0.3;
	AO = mix(0.3, 1.0, altura_folha);
	AO_LIGHT_AFFECT = 0.6;
	BACKLIGHT = c * 0.6;
}
