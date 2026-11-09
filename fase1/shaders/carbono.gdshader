shader_type spatial;
// Fibra de carbono trançada (twill 2x2) feita só com matemática, sem textura.
uniform float escala = 260.0;   // fios por metro
uniform vec3 cor : source_color = vec3(0.028, 0.029, 0.032);
uniform float brilho_fio = 0.045;

varying vec3 lp;
varying vec3 ln;

void vertex() {
	lp = VERTEX;
	ln = NORMAL;
}

void fragment() {
	vec3 an = abs(ln);
	vec2 p;
	if (an.y > an.x && an.y > an.z) {
		p = lp.xz;
	} else if (an.x > an.z) {
		p = lp.zy;
	} else {
		p = lp.xy;
	}
	vec2 q = p * escala;
	vec2 c = floor(q);
	vec2 f = fract(q);
	float sentido = mod(c.x + floor(c.y * 0.5) * 2.0 + c.y, 4.0) < 2.0 ? 0.0 : 1.0;
	float fio = mix(f.y, f.x, sentido);
	float s = 0.5 + 0.5 * sin(fio * 6.28318);
	float borda = smoothstep(0.0, 0.08, f.x) * smoothstep(0.0, 0.08, f.y) * smoothstep(1.0, 0.92, f.x) * smoothstep(1.0, 0.92, f.y);
	ALBEDO = cor + vec3(brilho_fio) * s * borda;
	ROUGHNESS = mix(0.42, 0.28, s);
	SPECULAR = 0.55;
	CLEARCOAT = 0.7;
	CLEARCOAT_ROUGHNESS = 0.15;
}
