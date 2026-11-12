/**************************************************************************/
/*  amd_fsr4.cpp                                                          */
/**************************************************************************/

#include "amd_fsr4.h"

#include "servers/rendering/rendering_device.h"
#include "core/config/engine.h"
#include "core/templates/local_vector.h"

#if defined(VULKAN_ENABLED) && defined(WINDOWS_ENABLED)
#include "drivers/vulkan/amd_ffx.h"
#define AMD_FSR4_IMPL
#endif

namespace RendererRD {

#ifdef AMD_FSR4_IMPL

struct AmdFsr4::Context {
	ffxContext ffx = nullptr;
	ffxCreateBackendVKDesc backend = {};
	ffxCreateContextDescUpscaleVersion version = {};
	ffxCreateContextDescUpscale desc = {};
	Size2i internal_size;
	Size2i target_size;
	bool reset = true;
};

static void _ffx_message(uint32_t p_type, const wchar_t *p_message) {
	String msg = String::utf16((const char16_t *)p_message);
	if (p_type == FFX_API_MESSAGE_TYPE_ERROR) {
		ERR_PRINT("[AMD FSR] " + msg);
	} else {
		WARN_PRINT("[AMD FSR] " + msg);
	}
}

bool AmdFsr4::is_available() {
	return AmdFfx::device != VK_NULL_HANDLE && AmdFfx::upscaler_enabled();
}

bool AmdFsr4::frame_generation_active() {
	return AmdFfx::swapchain_context != nullptr && !AmdFfx::fg_failed && AmdFfx::frame_generation_enabled();
}

// Um contexto só, criado no tamanho da tela: trocar Qualidade/Equilibrado/Desempenho muda só a
// resolução interna, e o FSR aceita qualquer resolução até o máximo sem recriar nada.
// Destruir o contexto com a placa de vídeo ainda usando ele no quadro em andamento derrubava o jogo;
// agora um contexto antigo (janela mudou de tamanho) só é destruído alguns quadros depois.
static AmdFsr4::Context *_compartilhado = nullptr;
struct _Aposentado {
	AmdFsr4::Context *c = nullptr;
	uint64_t quadro = 0;
};
static LocalVector<_Aposentado> _aposentados;
static const uint64_t QUADROS_ESPERA = 8;

static void _destruir(AmdFsr4::Context *p_c);

static uint64_t _quadro_atual() {
	return Engine::get_singleton() ? Engine::get_singleton()->get_frames_drawn() : 0;
}

static void _recolher() {
	uint64_t agora = _quadro_atual();
	for (uint32_t i = 0; i < _aposentados.size();) {
		if (agora >= _aposentados[i].quadro + QUADROS_ESPERA) {
			_destruir(_aposentados[i].c);
			_aposentados.remove_at_unordered(i);
		} else {
			i++;
		}
	}
}

static void _aposentar(AmdFsr4::Context *p_c) {
	_Aposentado a;
	a.c = p_c;
	a.quadro = _quadro_atual();
	_aposentados.push_back(a);
}

AmdFsr4::Context *AmdFsr4::create_context(const Size2i &p_internal_size, const Size2i &p_target_size) {
	_recolher();
	if (_compartilhado != nullptr) {
		if (_compartilhado->target_size == p_target_size) {
			// mesmo tamanho de tela: reaproveita, só recomeça o histórico (a resolução interna mudou)
			_compartilhado->internal_size = p_internal_size;
			_compartilhado->reset = true;
			return _compartilhado;
		}
		_aposentar(_compartilhado);
		_compartilhado = nullptr;
	}

	Context *c = memnew(Context);
	c->internal_size = p_internal_size;
	c->target_size = p_target_size;

	c->backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK;
	c->backend.deviceContext = AmdFfx::device_context();

	c->version.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE_VERSION;
	c->version.header.pNext = &c->backend.header;
	c->version.version = FFX_UPSCALER_VERSION;

	c->desc.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;
	c->desc.header.pNext = &c->version.header;
	// A cor que o Godot entrega antes do tonemap é linear e HDR; a profundidade é invertida (reverse Z).
	c->desc.flags = FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE | FFX_UPSCALE_ENABLE_DEPTH_INVERTED;
	// resolução interna máxima = a da tela (serve para todos os modos, inclusive Nativo AA)
	c->desc.maxRenderSize = { (uint32_t)MAX(p_internal_size.width, p_target_size.width), (uint32_t)MAX(p_internal_size.height, p_target_size.height) };
	c->desc.maxUpscaleSize = { (uint32_t)p_target_size.width, (uint32_t)p_target_size.height };
	c->desc.fpMessage = _ffx_message;

	ffxReturnCode_t ret = AmdFfx::fn.CreateContext(&c->ffx, &c->desc.header, nullptr);
	if (ret != FFX_API_RETURN_OK || c->ffx == nullptr) {
		AmdFfx::upscaler_failed = true;
		AmdFfx::set_status("FSR 4 indisponível (" + AmdFfx::error_name(ret) + "), usando FSR 2.2");
		memdelete(c);
		return nullptr;
	}

	ffxQueryGetProviderVersion provider = {};
	provider.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;
	String name = "FSR";
	if (AmdFfx::fn.Query(&c->ffx, &provider.header) == FFX_API_RETURN_OK && provider.versionName != nullptr) {
		name = "FSR " + String::utf8(provider.versionName);
	}
	AmdFfx::set_status(name + " ativo");
	_compartilhado = c;
	return c;
}

static void _destruir(AmdFsr4::Context *p_c) {
	if (p_c == nullptr) {
		return;
	}
	if (p_c->ffx != nullptr) {
		AmdFfx::fn.DestroyContext(&p_c->ffx, nullptr);
	}
	memdelete(p_c);
}

void AmdFsr4::free_context(Context *p_context) {
	if (p_context == nullptr) {
		return;
	}
	if (p_context == _compartilhado) {
		// os buffers da imagem foram refeitos (troca de modo): o contexto continua vivo
		p_context->reset = true;
		return;
	}
	_aposentar(p_context);
}

static FfxApiResource _resource(RID p_rid, const Size2i &p_size, uint32_t p_usage, uint32_t p_state) {
	RenderingDevice *rd = RenderingDevice::get_singleton();
	VkImage image = (VkImage)rd->get_driver_resource(RD::DRIVER_RESOURCE_TEXTURE, p_rid);
	VkFormat format = (VkFormat)rd->get_driver_resource(RD::DRIVER_RESOURCE_TEXTURE_DATA_FORMAT, p_rid);

	FfxApiResource res = {};
	res.resource = (void *)image;
	res.state = p_state;
	res.description.type = FFX_API_RESOURCE_TYPE_TEXTURE2D;
	res.description.format = ffxApiGetSurfaceFormatVK(format);
	res.description.width = p_size.width;
	res.description.height = p_size.height;
	res.description.depth = 1;
	res.description.mipCount = 1;
	res.description.flags = FFX_API_RESOURCE_FLAGS_NONE;
	res.description.usage = p_usage;
	if (ffxApiIsDepthFormat(format)) {
		res.description.usage |= FFX_API_RESOURCE_USAGE_DEPTHTARGET;
	}
	if (ffxApiIsStencilFormat(format)) {
		res.description.usage |= FFX_API_RESOURCE_USAGE_STENCILTARGET;
	}
	return res;
}

struct AmdFsr4CallbackArgs {
	ffxContext *ffx = nullptr;
	FfxApiResource color = {};
	FfxApiResource depth = {};
	FfxApiResource motion = {};
	FfxApiResource output = {};
	Size2i internal_size;
	Size2i target_size;
	Vector2 jitter;
	float sharpness = 0.0f;
	float delta_ms = 16.6f;
	float z_near = 0.05f;
	float z_far = 4000.0f;
	float fovy = 1.0f;
	bool reset = false;
	bool frame_generation = false;
	bool frame_generation_configure_only = false;
	float camera_position[3] = {};
	float camera_up[3] = {};
	float camera_right[3] = {};
	float camera_forward[3] = {};
};

static ffxReturnCode_t _frame_generation_dispatch(ffxDispatchDescFrameGeneration *p_params, void *p_user) {
	return AmdFfx::fn.Dispatch((ffxContext *)p_user, &p_params->header);
}

static void _amd_fsr4_callback(RenderingDeviceDriver *p_driver, RenderingDeviceDriver::CommandBufferID p_command_buffer, void *p_userdata) {
	AmdFsr4CallbackArgs *a = (AmdFsr4CallbackArgs *)p_userdata;
	// CommandBufferInfo do driver Vulkan começa com o VkCommandBuffer.
	VkCommandBuffer cmd = *(VkCommandBuffer *)(p_command_buffer.id);

	if (a->ffx != nullptr && *a->ffx != nullptr) {
		ffxDispatchDescUpscale d = {};
		d.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE;
		d.commandList = (void *)cmd;
		d.color = a->color;
		d.depth = a->depth;
		d.motionVectors = a->motion;
		d.output = a->output;
		d.jitterOffset = { a->jitter.x, a->jitter.y };
		// Os vetores de movimento do Godot estão em UV (0..1).
		d.motionVectorScale = { (float)a->internal_size.width, (float)a->internal_size.height };
		d.renderSize = { (uint32_t)a->internal_size.width, (uint32_t)a->internal_size.height };
		d.upscaleSize = { (uint32_t)a->target_size.width, (uint32_t)a->target_size.height };
		d.enableSharpening = a->sharpness > 0.001f;
		d.sharpness = a->sharpness;
		d.frameTimeDelta = a->delta_ms;
		d.preExposure = 1.0f;
		d.reset = a->reset;
		d.cameraNear = a->z_near;
		d.cameraFar = a->z_far;
		d.cameraFovAngleVertical = a->fovy;
		d.viewSpaceToMetersFactor = 1.0f;
		d.flags = 0;
		ffxReturnCode_t ret = AmdFfx::fn.Dispatch(a->ffx, &d.header);
		if (ret != FFX_API_RETURN_OK) {
			AmdFfx::upscaler_failed = true;
			AmdFfx::set_status("FSR 4 falhou (" + AmdFfx::error_name(ret) + "), voltando para FSR 2.2");
		}
	}

	if ((a->frame_generation || a->frame_generation_configure_only) && AmdFfx::fg_context != nullptr) {
		// Ordem obrigatória do FSR FG 4: configurar, preparar, (a swapchain gera o quadro).
		ffxConfigureDescFrameGeneration cfg = {};
		cfg.header.type = FFX_API_CONFIGURE_DESC_TYPE_FRAMEGENERATION;
		cfg.swapChain = (void *)AmdFfx::fg_swapchain;
		cfg.presentCallback = nullptr;
		cfg.presentCallbackUserContext = nullptr;
		cfg.frameGenerationCallback = _frame_generation_dispatch;
		cfg.frameGenerationCallbackUserContext = &AmdFfx::fg_context;
		cfg.frameGenerationEnabled = a->frame_generation;
		cfg.allowAsyncWorkloads = false;
		cfg.HUDLessColor = {};
		cfg.flags = 0;
		cfg.onlyPresentGenerated = false;
		cfg.generationRect = { 0, 0, (int32_t)AmdFfx::display_width, (int32_t)AmdFfx::display_height };
		cfg.frameID = AmdFfx::fg_frame_id;
		ffxReturnCode_t ret = AmdFfx::fn.Configure(&AmdFfx::fg_context, &cfg.header);
		if (ret != FFX_API_RETURN_OK) {
			AmdFfx::fg_failed = true;
			AmdFfx::set_status_fg("Gerador de quadros falhou ao configurar (" + AmdFfx::error_name(ret) + ")");
		} else if (a->frame_generation) {
			ffxDispatchDescFrameGenerationPrepareV2 prep = {};
			prep.header.type = FFX_API_DISPATCH_DESC_TYPE_FRAMEGENERATION_PREPARE_V2;
			prep.frameID = AmdFfx::fg_frame_id;
			prep.flags = 0;
			prep.commandList = (void *)cmd;
			prep.renderSize = { (uint32_t)a->internal_size.width, (uint32_t)a->internal_size.height };
			prep.jitterOffset = { a->jitter.x, a->jitter.y };
			prep.motionVectorScale = { (float)a->internal_size.width, (float)a->internal_size.height };
			prep.frameTimeDelta = a->delta_ms;
			prep.reset = a->reset;
			prep.cameraNear = a->z_near;
			prep.cameraFar = a->z_far;
			prep.cameraFovAngleVertical = a->fovy;
			prep.viewSpaceToMetersFactor = 1.0f;
			prep.depth = a->depth;
			prep.motionVectors = a->motion;
			for (int i = 0; i < 3; i++) {
				prep.cameraPosition[i] = a->camera_position[i];
				prep.cameraUp[i] = a->camera_up[i];
				prep.cameraRight[i] = a->camera_right[i];
				prep.cameraForward[i] = a->camera_forward[i];
			}
			ret = AmdFfx::fn.Dispatch(&AmdFfx::fg_context, &prep.header);
			if (ret != FFX_API_RETURN_OK) {
				AmdFfx::fg_failed = true;
				AmdFfx::set_status_fg("Gerador de quadros falhou ao preparar (" + AmdFfx::error_name(ret) + ")");
			}
		}
		AmdFfx::fg_frame_id++;
	}

	memdelete(a);
}

void AmdFsr4::process(const Params &p_params) {
	ERR_FAIL_NULL(p_params.context);
	Context *c = p_params.context;
	_recolher();

	AmdFsr4CallbackArgs *a = memnew(AmdFsr4CallbackArgs);
	a->ffx = &c->ffx;
	const uint32_t read_state = FFX_API_RESOURCE_STATE_PIXEL_COMPUTE_READ;
	a->color = _resource(p_params.color, p_params.internal_size, FFX_API_RESOURCE_USAGE_READ_ONLY, read_state);
	a->depth = _resource(p_params.depth, p_params.internal_size, FFX_API_RESOURCE_USAGE_READ_ONLY, read_state);
	a->motion = _resource(p_params.velocity, p_params.internal_size, FFX_API_RESOURCE_USAGE_READ_ONLY, read_state);
	a->output = _resource(p_params.output, p_params.target_size, FFX_API_RESOURCE_USAGE_UAV, FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
	a->internal_size = p_params.internal_size;
	a->target_size = p_params.target_size;
	a->jitter = p_params.jitter;
	a->sharpness = p_params.sharpness;
	a->delta_ms = MAX(p_params.delta_time, 0.0001f) * 1000.0f;
	a->z_near = p_params.z_near;
	a->z_far = p_params.z_far;
	a->fovy = p_params.fovy;
	a->reset = c->reset;
	c->reset = false;

	// Gerador de quadros: precisa da swapchain da AMD criada na abertura do jogo.
	if (AmdFfx::swapchain_context != nullptr && !AmdFfx::fg_failed) {
		bool want = AmdFfx::frame_generation_enabled();
		if (want && AmdFfx::ensure_fg_context(p_params.internal_size.width, p_params.internal_size.height)) {
			a->frame_generation = true;
			AmdFfx::set_status_fg("gerador de quadros ATIVO");
		} else if (!want && AmdFfx::fg_context != nullptr) {
			a->frame_generation_configure_only = true; // desliga o gerador mantendo a ordem das chamadas
			AmdFfx::set_status_fg("gerador de quadros desligado");
		}
	}
	if (a->frame_generation) {
		const Transform3D &t = p_params.camera_transform;
		Vector3 pos = t.origin;
		Vector3 right = t.basis.get_column(0).normalized();
		Vector3 up = t.basis.get_column(1).normalized();
		Vector3 forward = -t.basis.get_column(2).normalized();
		for (int i = 0; i < 3; i++) {
			a->camera_position[i] = pos[i];
			a->camera_right[i] = right[i];
			a->camera_up[i] = up[i];
			a->camera_forward[i] = forward[i];
		}
	}

	RD::CallbackResource res[4] = {
		{ p_params.color, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
		{ p_params.depth, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
		{ p_params.velocity, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE },
		{ p_params.output, RD::CALLBACK_RESOURCE_TYPE_TEXTURE, RD::CALLBACK_RESOURCE_USAGE_STORAGE_IMAGE_READ_WRITE },
	};
	RD::get_singleton()->driver_callback_add(_amd_fsr4_callback, a, VectorView<RD::CallbackResource>(res, 4));
}

#else // Outras plataformas: FSR 4 não existe, o Godot usa o FSR 2.2.

struct AmdFsr4::Context {};

bool AmdFsr4::is_available() {
	return false;
}

bool AmdFsr4::frame_generation_active() {
	return false;
}

AmdFsr4::Context *AmdFsr4::create_context(const Size2i &, const Size2i &) {
	return nullptr;
}

void AmdFsr4::free_context(Context *) {}

void AmdFsr4::process(const Params &) {}

#endif

} // namespace RendererRD
