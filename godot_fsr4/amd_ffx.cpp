/**************************************************************************/
/*  amd_ffx.cpp                                                           */
/**************************************************************************/

#include "amd_ffx.h"

#include "core/config/project_settings.h"
#include "core/io/file_access.h"
#include "core/os/os.h"

#ifdef AMD_FFX_ENABLED
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

static bool _ffx_tried = false;
static bool _ffx_present = false;

bool AmdFfx::library_present() {
#ifdef AMD_FFX_ENABLED
	if (_ffx_tried) {
		return _ffx_present;
	}
	_ffx_tried = true;
	// Para testes automáticos: o arquivo "forcar_fsr4.txt" ao lado do executável ignora o --sem-fsr4.
	bool forcar = false;
	if (OS::get_singleton()) {
		String exe_dir = OS::get_singleton()->get_executable_path().get_base_dir();
		String f = exe_dir.path_join("forcar_fsr4.txt");
		forcar = FileAccess::exists(f) && FileAccess::get_file_as_string(f).strip_edges().begins_with("sim");
	}
	if (!forcar && OS::get_singleton() && OS::get_singleton()->get_cmdline_args().find("--sem-fsr4") != nullptr) {
		set_status("FSR 4 desligado (--sem-fsr4)");
		return false;
	}
	// Procura a DLL ao lado do executável.
	String dir = OS::get_singleton() ? OS::get_singleton()->get_executable_path().get_base_dir() : String();
	String path = dir.path_join("amd_fidelityfx_loader_vk.dll").replace("/", "\\");
	HMODULE mod = LoadLibraryW((LPCWSTR)path.utf16().get_data());
	if (mod == nullptr) {
		mod = LoadLibraryW(L"amd_fidelityfx_loader_vk.dll");
	}
	if (mod == nullptr) {
		set_status("FSR 4: amd_fidelityfx_loader_vk.dll não encontrada");
		return false;
	}
	fn.CreateContext = (PfnFfxCreateContext)(void *)GetProcAddress(mod, "ffxCreateContext");
	fn.DestroyContext = (PfnFfxDestroyContext)(void *)GetProcAddress(mod, "ffxDestroyContext");
	fn.Configure = (PfnFfxConfigure)(void *)GetProcAddress(mod, "ffxConfigure");
	fn.Query = (PfnFfxQuery)(void *)GetProcAddress(mod, "ffxQuery");
	fn.Dispatch = (PfnFfxDispatch)(void *)GetProcAddress(mod, "ffxDispatch");
	_ffx_present = fn.CreateContext && fn.DestroyContext && fn.Configure && fn.Query && fn.Dispatch;
	if (!_ffx_present) {
		set_status("FSR 4: DLL da AMD incompleta");
	}
	return _ffx_present;
#else
	return false;
#endif
}

static bool _setting_bool(const char *p_name, bool p_default) {
	ProjectSettings *ps = ProjectSettings::get_singleton();
	if (ps == nullptr || !ps->has_setting(p_name)) {
		return p_default;
	}
	return bool(ps->get_setting(p_name));
}

bool AmdFfx::frame_generation_requested() {
	return library_present() && _setting_bool(SETTING_FRAMEGEN, false);
}

bool AmdFfx::upscaler_enabled() {
	return library_present() && vendor_is_amd && !upscaler_failed && _setting_bool(SETTING_UPSCALER, true);
}

bool AmdFfx::frame_generation_enabled() {
	return _setting_bool(SETTING_FRAMEGEN, false);
}

static void _publicar_status() {
	String s = AmdFfx::status_fsr;
	if (!AmdFfx::status_fg.is_empty()) {
		s += (s.is_empty() ? "" : " • ") + AmdFfx::status_fg;
	}
	if (AmdFfx::status == s) {
		return;
	}
	AmdFfx::status = s;
	print_line("[AMD FSR] " + s);
	ProjectSettings *ps = ProjectSettings::get_singleton();
	if (ps) {
		ps->set_setting(AmdFfx::SETTING_STATUS, s);
	}
}

void AmdFfx::set_status(const String &p_status) {
	status_fsr = p_status;
	_publicar_status();
}

void AmdFfx::set_status_fg(const String &p_status) {
	status_fg = p_status;
	_publicar_status();
}

#ifdef AMD_FFX_ENABLED

VkDeviceContext AmdFfx::device_context() {
	VkDeviceContext ctx = {};
	ctx.vkDevice = device;
	ctx.vkPhysicalDevice = physical_device;
	ctx.vkDeviceProcAddr = get_device_proc_addr;
	return ctx;
}

String AmdFfx::error_name(ffxReturnCode_t p_code) {
	switch (p_code) {
		case FFX_API_RETURN_OK:
			return "ok";
		case FFX_API_RETURN_ERROR:
			return "erro";
		case FFX_API_RETURN_ERROR_UNKNOWN_DESCTYPE:
			return "tipo desconhecido (driver antigo?)";
		case FFX_API_RETURN_ERROR_RUNTIME_ERROR:
			return "erro de execução";
		case FFX_API_RETURN_NO_PROVIDER:
			return "placa sem suporte";
		case FFX_API_RETURN_ERROR_MEMORY:
			return "sem memória";
		case FFX_API_RETURN_ERROR_PARAMETER:
			return "parâmetro inválido";
		default:
			return "código " + itos(p_code);
	}
}

void AmdFfx::destroy_fg_context() {
	if (fg_context != nullptr) {
		fn.DestroyContext(&fg_context, nullptr);
		fg_context = nullptr;
		set_status_fg("gerador de quadros pronto");
	}
	fg_frame_id = 0;
}

bool AmdFfx::ensure_fg_context(uint32_t p_max_render_width, uint32_t p_max_render_height) {
	if (fg_context != nullptr) {
		return true;
	}
	if (fg_failed || swapchain_context == nullptr) {
		return false;
	}

	VkDeviceContext dev = device_context();
	ffxCreateBackendVKDesc backend = {};
	backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK;
	backend.deviceContext = dev;

	ffxCreateContextDescFrameGenerationVersion version = {};
	version.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_FRAMEGENERATION_VERSION;
	version.header.pNext = &backend.header;
	version.version = FFX_FRAMEGENERATION_VERSION;

	// a cópia sem HUD vem do render target do Godot (RGBA8), a tela é BGRA8
	ffxCreateContextDescFrameGenerationHudless hudless = {};
	hudless.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_FRAMEGENERATION_HUDLESS;
	hudless.header.pNext = &version.header;
	hudless.hudlessBackBufferFormat = FFX_API_SURFACE_FORMAT_R8G8B8A8_UNORM;

	ffxCreateContextDescFrameGeneration desc = {};
	desc.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_FRAMEGENERATION;
	desc.header.pNext = &hudless.header;
	desc.flags = FFX_FRAMEGENERATION_ENABLE_DEPTH_INVERTED;
	desc.displaySize = { display_width, display_height };
	desc.maxRenderSize = { MAX(p_max_render_width, display_width), MAX(p_max_render_height, display_height) };
	desc.backBufferFormat = ffxApiGetSurfaceFormatVK(display_format);

	ffxReturnCode_t ret = fn.CreateContext(&fg_context, &desc.header, nullptr);
	if (ret != FFX_API_RETURN_OK) {
		fg_context = nullptr;
		fg_failed = true;
		set_status_fg("Gerador de quadros falhou ao iniciar: " + error_name(ret));
		return false;
	}
	fg_frame_id = 1;
	set_status_fg("gerador de quadros ATIVO");
	return true;
}

#endif
