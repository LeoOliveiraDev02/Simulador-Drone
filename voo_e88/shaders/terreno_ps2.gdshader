shader_type spatial;
// Chão no estilo PS2 (ver PDF "Otimização da velha guarda", cap. 2, 3 e 7):
//  - sem cálculo de luz por pixel: a luz do sol, a sombra dos morros e das árvores e a luz do céu
//    vêm prontas nos vértices (UV2.x = sol, UV2.y = céu), calculadas em mapa.gd ao trocar a hora;
//  - texturas de 128 px e 16 cores, sem mapa de normal e sem rugosidade;
//  - estrada, lama e terra batida vêm de uma máscara de 2 m por pixel, com a borda recortada
//    pelo próprio desenho do capim (sem textura extra de ruído).
render_mode unshaded, cull_back;

uniform sampler2D capim_verde : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D capim_seco : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D terra_vermelha : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D terra_batida : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D mascara : filter_linear_mipmap, repeat_disable;
uniform vec4 mascara_area = vec4(-512.0, -1536.0, 1024.0, 2048.0);  // x0, z0, largura, comprimento (m)

uniform vec3 sol_cor : source_color = vec3(1.0, 0.96, 0.9);
uniform float sol_forca = 1.0;
uniform vec3 ceu_cor : source_color = vec3(0.66, 0.76, 0.9);
uniform float ceu_forca = 0.5;
uniform float escala = 3.5;   // metros por repetição da textura

varying vec3 wpos;
varying vec2 luz;
varying float secura;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	luz = UV2;
	secura = COLOR.a;
}

void fragment() {
	vec2 uv = wpos.xz / escala;
	vec3 verde = texture(capim_verde, uv).rgb;
	vec3 seco = texture(capim_seco, uv * 0.73 + vec2(0.31, 0.57)).rgb;
	// o brilho do capim serve de ruído para as bordas não ficarem retas
	float ruido = clamp((dot(verde, vec3(0.3, 0.55, 0.15)) - 0.08) * 6.0, 0.0, 1.0);
	vec3 c = mix(verde, seco, smoothstep(0.3, 0.7, secura + (ruido - 0.5) * 0.35));

	vec3 m = texture(mascara, (wpos.xz - mascara_area.xy) / mascara_area.zw).rgb;  // r estrada, g lama, b terra
	float borda = (ruido - 0.5) * 0.45;
	float solo = smoothstep(0.42, 0.58, max(m.g, m.b * 0.9) + borda);
	float estrada = smoothstep(0.44, 0.56, m.r + borda);
	vec3 terra = texture(terra_batida, uv * 0.8).rgb * mix(1.0, 0.7, m.g);   // lama do açude mais escura
	c = mix(c, terra, solo);
	c = mix(c, texture(terra_vermelha, uv).rgb, estrada);

	ALBEDO = c * (sol_cor * sol_forca * luz.x + ceu_cor * ceu_forca * luz.y);
}
