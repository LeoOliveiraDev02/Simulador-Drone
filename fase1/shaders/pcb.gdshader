shader_type spatial;
// Placa de circuito: verniz colorido, trilhas e ilhas douradas.
uniform vec3 cor_verniz : source_color = vec3(0.03, 0.12, 0.06);
uniform vec3 cor_trilha : source_color = vec3(0.05, 0.2, 0.09);
uniform float escala = 900.0;
uniform float semente = 0.0;

varying vec3 lp;
varying vec3 ln;

float h(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)) + semente) * 43758.5453);
}

void vertex() {
	lp = VERTEX;
	ln = NORMAL;
}

void fragment() {
	vec3 cor = cor_verniz;
	float metal = 0.0;
	float rug = 0.35;
	if (abs(ln.y) > 0.7) {
		vec2 q = lp.xz * escala;
		vec2 c = floor(q / 6.0);
		vec2 f = fract(q / 6.0);
		float r = h(c);
		// trilhas horizontais e verticais
		float tr = (r < 0.5) ? step(abs(f.y - 0.5), 0.07) : step(abs(f.x - 0.5), 0.07);
		cor = mix(cor, cor_trilha, tr * step(0.25, h(c + 7.0)));
		// ilhas (pads) douradas
		vec2 g = fract(q / 3.0) - 0.5;
		float pad = step(max(abs(g.x), abs(g.y)), 0.18) * step(0.93, h(floor(q / 3.0) + 3.0));
		cor = mix(cor, vec3(0.85, 0.65, 0.3), pad);
		metal = pad;
		rug = mix(0.35, 0.25, pad);
	}
	ALBEDO = cor;
	METALLIC = metal;
	ROUGHNESS = rug;
	CLEARCOAT = 0.4;
}
