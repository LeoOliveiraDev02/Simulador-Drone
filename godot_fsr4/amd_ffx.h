/**************************************************************************/
/*  amd_ffx.h                                                             */
/**************************************************************************/
/* Ponte entre o Godot (Vulkan) e o AMD FSR SDK 2.4 (FSR 4.1 + Frame      */
/* Generation 4). Carrega amd_fidelityfx_loader_vk.dll em tempo de        */
/* execução; se a DLL ou a placa não suportarem, tudo fica desligado e o  */
/* Godot continua usando o FSR 2.2 embutido.                              */
/**************************************************************************/

#pragma once

#include "core/string/ustring.h"
#include "drivers/vulkan/godot_vulkan.h"

#if defined(WINDOWS_ENABLED)
#define AMD_FFX_ENABLED
#include "thirdparty/amd_ffx/api/include/vk/ffx_api_vk.h"
#include "thirdparty/amd_ffx/framegeneration/include/ffx_framegeneration.h"
#include "thirdparty/amd_ffx/framegeneration/include/vk/ffx_api_framegeneration_vk.h"
#include "thirdparty/amd_ffx/upscalers/include/ffx_upscale.h"
#endif

#ifdef AMD_FFX_ENABLED
struct AmdFfxFunctions {
	PfnFfxCreateContext CreateContext = nullptr;
	PfnFfxDestroyContext DestroyContext = nullptr;
	PfnFfxConfigure Configure = nullptr;
	PfnFfxQuery Query = nullptr;
	PfnFfxDispatch Dispatch = nullptr;
};
#endif

class AmdFfx {
public:
	// Configurações do projeto (podem ser trocadas pelo jogo em tempo de execução).
	static constexpr const char *SETTING_UPSCALER = "rendering/amd_fsr/fsr4_upscaler";
	static constexpr const char *SETTING_FRAMEGEN = "rendering/amd_fsr/frame_generation";
	static constexpr const char *SETTING_STATUS = "rendering/amd_fsr/status";

	static bool library_present();
	static bool is_amd() { return vendor_is_amd; }
	static bool frame_generation_requested(); // Lido uma vez ao criar o device.
	static bool upscaler_enabled(); // Lido a cada quadro.
	static bool frame_generation_enabled(); // Lido a cada quadro.
	static void set_status(const String &p_status);
	static String get_status() { return status; }

	static inline bool vendor_is_amd = false;
	static inline bool upscaler_failed = false;
	static inline String status;

#ifdef AMD_FFX_ENABLED
	static inline AmdFfxFunctions fn;

	static inline VkDevice device = VK_NULL_HANDLE;
	static inline VkPhysicalDevice physical_device = VK_NULL_HANDLE;
	static inline PFN_vkGetDeviceProcAddr get_device_proc_addr = nullptr;
	static VkDeviceContext device_context();

	// Filas extras pedidas na criação do device para o gerador de quadros.
	static inline bool fg_queues_ready = false;
	static inline VkQueueInfoFFXAPI q_async = {};
	static inline VkQueueInfoFFXAPI q_present = {};
	static inline VkQueueInfoFFXAPI q_acquire = {};

	// Swapchain do gerador de quadros (substitui a do Godot).
	static inline ffxContext swapchain_context = nullptr;
	static inline VkSwapchainKHR fg_swapchain = VK_NULL_HANDLE;
	static inline ffxQueryDescSwapchainReplacementFunctionsVK replacement = {};
	static inline uint32_t display_width = 0;
	static inline uint32_t display_height = 0;
	static inline VkFormat display_format = VK_FORMAT_UNDEFINED;

	// Contexto do gerador de quadros (criado pelo renderizador quando precisa).
	static inline ffxContext fg_context = nullptr;
	static inline uint64_t fg_frame_id = 0;
	static inline bool fg_failed = false;

	static void destroy_fg_context();
	static bool ensure_fg_context(uint32_t p_max_render_width, uint32_t p_max_render_height);
	static String error_name(ffxReturnCode_t p_code);
#endif
};
