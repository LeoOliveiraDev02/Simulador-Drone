// AMD FidelityFX Super Resolution 1.0 — RCAS (Robust Contrast Adaptive Sharpening)
// Portado à mão do ffx_fsr1.h (AMD, licença MIT). Segunda passada do FSR 1: devolve a nitidez
// depois do aumento (EASU), sem estourar bordas (o reforço é limitado pelos vizinhos).
shader_type canvas_item;
render_mode unshaded, blend_disabled;

// nitidez em "stops": 0 = máxima, 1 = metade, 2 = um quarto
uniform float nitidez : hint_range(0.0, 2.0) = 0.25;

vec3 px(sampler2D t, ivec2 p, ivec2 m) {
	return texelFetch(t, clamp(p, ivec2(0), m), 0).rgb;
}

void fragment() {
	vec2 tam = 1.0 / TEXTURE_PIXEL_SIZE;
	ivec2 m = ivec2(tam) - ivec2(1);
	ivec2 p = clamp(ivec2(UV * tam), ivec2(0), m);
	//   b
	// d e f
	//   h
	vec3 b = px(TEXTURE, p + ivec2(0, -1), m);
	vec3 d = px(TEXTURE, p + ivec2(-1, 0), m);
	vec3 e = px(TEXTURE, p, m);
	vec3 f = px(TEXTURE, p + ivec2(1, 0), m);
	vec3 h = px(TEXTURE, p + ivec2(0, 1), m);

	vec3 mn4 = min(min(b, d), min(f, h));
	vec3 mx4 = max(max(b, d), max(f, h));
	// quanto dá para reforçar sem passar do preto (hit_min) nem do branco (hit_max)
	vec3 hit_min = min(mn4, e) / (4.0 * mx4 + 1e-5);
	vec3 hit_max = (1.0 - max(mx4, e)) / (4.0 * min(mn4, e) - 4.0 - 1e-5);
	vec3 lobe3 = max(-hit_min, hit_max);
	float lobe = max(-0.1875, min(max(lobe3.r, max(lobe3.g, lobe3.b)), 0.0)) * exp2(-nitidez);
	vec3 cor = (lobe * (b + d + f + h) + e) / (4.0 * lobe + 1.0);
	COLOR = vec4(cor, 1.0);
}
