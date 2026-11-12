/**************************************************************************/
/*  amd_fsr4.h                                                            */
/**************************************************************************/
/* AMD FSR 4.1 (upscaling por IA) e preparação do gerador de quadros FSR 4 */
/* no renderizador Forward+ do Godot. Só funciona no Windows com Vulkan e  */
/* placa AMD compatível; nos outros casos o Godot usa o FSR 2.2 embutido.  */
/**************************************************************************/

#pragma once

#include "core/math/projection.h"
#include "core/math/transform_3d.h"
#include "core/math/vector2.h"
#include "core/math/vector2i.h"
#include "core/templates/rid.h"

namespace RendererRD {

class AmdFsr4 {
public:
	struct Context;

	// FSR 4 pode ser usado neste quadro? (DLL presente, placa AMD, opção ligada, sem erro anterior)
	static bool is_available();
	// O gerador de quadros está pronto e ligado?
	static bool frame_generation_active();
	// Gerador de quadros: guarda uma cópia da imagem 3D antes dos textos/painéis (HUD), para o
	// gerador saber o que é interface e não deformar as letras nos quadros gerados.
	static void capture_hudless(RID p_render_target);

	static Context *create_context(const Size2i &p_internal_size, const Size2i &p_target_size);
	static void free_context(Context *p_context);

	struct Params {
		Context *context = nullptr;
		RID color;
		RID depth;
		RID velocity;
		RID output;
		Size2i internal_size;
		Size2i target_size;
		Vector2 jitter; // em pixels
		float sharpness = 0.0f; // 0 = sem nitidez extra, 1 = máximo
		float delta_time = 0.016f; // segundos
		float z_near = 0.05f;
		float z_far = 4000.0f;
		float fovy = 1.0f; // radianos
		Transform3D camera_transform;
	};

	// Grava o FSR 4 (e, se ligado, a preparação do gerador de quadros) no quadro atual.
	static void process(const Params &p_params);
};

} // namespace RendererRD
