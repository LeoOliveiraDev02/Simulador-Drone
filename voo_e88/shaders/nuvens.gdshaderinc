// sombra das nuvens que passam (o mapa move o ruído com o vento)
global uniform sampler2D nuvem_ruido : filter_linear_mipmap, repeat_enable;
global uniform float nuvem_forca;
global uniform vec2 nuvem_desloc;

float sombra_nuvem(vec3 p) {
	if (nuvem_forca <= 0.001) {
		return 1.0;
	}
	float n = texture(nuvem_ruido, (p.xz + nuvem_desloc) / 520.0).r;
	n = n * 0.75 + texture(nuvem_ruido, (p.xz + nuvem_desloc * 1.3) / 190.0).r * 0.25;
	return 1.0 - nuvem_forca * smoothstep(0.5, 0.66, n);
}
