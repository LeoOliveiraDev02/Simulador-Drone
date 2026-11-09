shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back;
// Brilho de contorno usado quando o mouse passa ou clica numa peça.
uniform vec4 cor : source_color = vec4(0.25, 0.7, 1.0, 1.0);
uniform float forca = 0.6;

void fragment() {
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.0);
	float pulso = 0.8 + 0.2 * sin(TIME * 5.0);
	ALBEDO = cor.rgb * (0.12 + fres * 1.2) * forca * pulso;
}
