// AMD FidelityFX Super Resolution 1.0 — EASU (Edge Adaptive Spatial Upsampling)
// Portado à mão do ffx_fsr1.h (AMD, licença MIT) para o renderizador de Compatibilidade (OpenGL) do Godot,
// que não tem o FSR 1 embutido. Lê a imagem pequena do 3D (TEXTURE) e desenha no tamanho da tela.
// 12 amostras em volta do pixel; detecta a direção da borda e usa um filtro tipo Lanczos esticado nela.
shader_type canvas_item;
render_mode unshaded, blend_disabled;

vec3 px(sampler2D t, ivec2 p, ivec2 m) {
	return texelFetch(t, clamp(p, ivec2(0), m), 0).rgb;
}

// brilho aproximado usado pelo FSR (verde + metade de vermelho e azul)
float luma(vec3 c) {
	return c.g + 0.5 * (c.r + c.b);
}

// acumula direção e "comprimento" da borda numa das 4 posições bilineares
// a = acima, b = esquerda, c = centro, d = direita, e = abaixo
void easu_set(inout vec2 dir, inout float len, float w, float la, float lb, float lc, float ld, float le) {
	float dc = ld - lc;
	float cb = lc - lb;
	float len_x = max(abs(dc), abs(cb));
	float dir_x = ld - lb;
	dir.x += dir_x * w;
	len_x = clamp(abs(dir_x) / max(len_x, 1e-8), 0.0, 1.0);
	len += len_x * len_x * w;

	float ec = le - lc;
	float ca = lc - la;
	float len_y = max(abs(ec), abs(ca));
	float dir_y = le - la;
	dir.y += dir_y * w;
	len_y = clamp(abs(dir_y) / max(len_y, 1e-8), 0.0, 1.0);
	len += len_y * len_y * w;
}

// peso de uma amostra (aproximação polinomial do Lanczos 2, como no original)
void easu_tap(inout vec3 acc, inout float acc_w, vec2 off, vec2 dir, vec2 len2, float lob, float clp, vec3 c) {
	vec2 v = vec2(off.x * dir.x + off.y * dir.y, off.x * (-dir.y) + off.y * dir.x);
	v *= len2;
	float d2 = min(dot(v, v), clp);
	float wb = 0.4 * d2 - 1.0;
	float wa = lob * d2 - 1.0;
	wb *= wb;
	wa *= wa;
	wb = 1.5625 * wb - 0.5625;
	float w = wb * wa;
	acc += c * w;
	acc_w += w;
}

void fragment() {
	vec2 tam = 1.0 / TEXTURE_PIXEL_SIZE;
	ivec2 m = ivec2(tam) - ivec2(1);
	// posição do pixel de saída na imagem pequena (centro do pixel)
	vec2 pp = UV * tam - 0.5;
	vec2 fp = floor(pp);
	pp -= fp;
	ivec2 f0 = ivec2(fp);

	//    b c
	//  e f g h
	//  i j k l
	//    n o
	vec3 b = px(TEXTURE, f0 + ivec2(0, -1), m);
	vec3 c = px(TEXTURE, f0 + ivec2(1, -1), m);
	vec3 e = px(TEXTURE, f0 + ivec2(-1, 0), m);
	vec3 f = px(TEXTURE, f0, m);
	vec3 g = px(TEXTURE, f0 + ivec2(1, 0), m);
	vec3 h = px(TEXTURE, f0 + ivec2(2, 0), m);
	vec3 i = px(TEXTURE, f0 + ivec2(-1, 1), m);
	vec3 j = px(TEXTURE, f0 + ivec2(0, 1), m);
	vec3 k = px(TEXTURE, f0 + ivec2(1, 1), m);
	vec3 l = px(TEXTURE, f0 + ivec2(2, 1), m);
	vec3 n = px(TEXTURE, f0 + ivec2(0, 2), m);
	vec3 o = px(TEXTURE, f0 + ivec2(1, 2), m);

	float bl = luma(b); float cl = luma(c); float el = luma(e); float fl = luma(f);
	float gl = luma(g); float hl = luma(h); float il = luma(i); float jl = luma(j);
	float kl = luma(k); float ll = luma(l); float nl = luma(n); float ol = luma(o);

	vec2 dir = vec2(0.0);
	float len = 0.0;
	easu_set(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bl, el, fl, gl, jl);
	easu_set(dir, len, pp.x * (1.0 - pp.y), cl, fl, gl, hl, kl);
	easu_set(dir, len, (1.0 - pp.x) * pp.y, fl, il, jl, kl, nl);
	easu_set(dir, len, pp.x * pp.y, gl, jl, kl, ll, ol);

	// normaliza a direção (sem borda: usa o eixo x)
	vec2 dir2 = dir * dir;
	float dir_r = dir2.x + dir2.y;
	bool zero = dir_r < (1.0 / 32768.0);
	dir_r = zero ? 1.0 : inversesqrt(dir_r);
	dir.x = zero ? 1.0 : dir.x;
	dir *= dir_r;

	// quanto mais forte a borda, mais o filtro estica ao longo dela
	len = len * 0.5;
	len *= len;
	float stretch = dot(dir, dir) / max(abs(dir.x), abs(dir.y));
	vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);
	float lob = 0.5 - 0.29 * len;
	float clp = 1.0 / lob;

	vec3 acc = vec3(0.0);
	float acc_w = 0.0;
	easu_tap(acc, acc_w, vec2(0.0, -1.0) - pp, dir, len2, lob, clp, b);
	easu_tap(acc, acc_w, vec2(1.0, -1.0) - pp, dir, len2, lob, clp, c);
	easu_tap(acc, acc_w, vec2(-1.0, 1.0) - pp, dir, len2, lob, clp, i);
	easu_tap(acc, acc_w, vec2(0.0, 1.0) - pp, dir, len2, lob, clp, j);
	easu_tap(acc, acc_w, vec2(0.0, 0.0) - pp, dir, len2, lob, clp, f);
	easu_tap(acc, acc_w, vec2(-1.0, 0.0) - pp, dir, len2, lob, clp, e);
	easu_tap(acc, acc_w, vec2(1.0, 1.0) - pp, dir, len2, lob, clp, k);
	easu_tap(acc, acc_w, vec2(2.0, 1.0) - pp, dir, len2, lob, clp, l);
	easu_tap(acc, acc_w, vec2(2.0, 0.0) - pp, dir, len2, lob, clp, h);
	easu_tap(acc, acc_w, vec2(1.0, 0.0) - pp, dir, len2, lob, clp, g);
	easu_tap(acc, acc_w, vec2(1.0, 2.0) - pp, dir, len2, lob, clp, o);
	easu_tap(acc, acc_w, vec2(0.0, 2.0) - pp, dir, len2, lob, clp, n);

	// sem "anel" escuro/claro: limita ao mínimo/máximo das 4 amostras do meio
	vec3 mn = min(min(f, g), min(j, k));
	vec3 mx = max(max(f, g), max(j, k));
	COLOR = vec4(clamp(acc / max(acc_w, 1e-6), mn, mx), 1.0);
}
