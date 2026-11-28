#include <whisper.h>
#include <vulkan/vulkan.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

namespace {
struct BackendStatus {
    bool selected = false;
    bool failed = false;
};

void check_backend(enum ggml_log_level, const char *message, void *data) {
    auto &status = *static_cast<BackendStatus *>(data);
    // The pinned implementation can initialize a CPU context after GPU initialization fails.
    if (std::strstr(message, "whisper_backend_init_gpu: using Vulkan")) {
        status.selected = true;
    }
    if (std::strstr(message, "whisper_backend_init_gpu: failed to initialize")) {
        status.failed = true;
    }
    std::fputs(message, stderr);
}

int fail(const char *message) {
    std::cout << "ERROR " << message << std::endl;
    return 1;
}

std::string select_device() {
    VkApplicationInfo application{};
    application.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    application.apiVersion = VK_API_VERSION_1_2;
    VkInstanceCreateInfo create{};
    create.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create.pApplicationInfo = &application;
    VkInstance instance;
    if (vkCreateInstance(&create, nullptr, &instance) != VK_SUCCESS) {
        return {};
    }

    uint32_t count = 0;
    std::string name;
    if (vkEnumeratePhysicalDevices(instance, &count, nullptr) == VK_SUCCESS && count) {
        std::vector<VkPhysicalDevice> devices(count);
        if (vkEnumeratePhysicalDevices(instance, &count, devices.data()) == VK_SUCCESS) {
            for (uint32_t index = 0; index < count; ++index) {
                VkPhysicalDeviceProperties properties{};
                vkGetPhysicalDeviceProperties(devices[index], &properties);
                const bool hardware_gpu = properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU ||
                                          properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU;
                if (!hardware_gpu || properties.apiVersion < VK_API_VERSION_1_2 ||
                    (properties.vendorID != 0x8086 && properties.vendorID != 0x1002)) {
                    continue;
                }
                const auto selection = std::to_string(index);
#ifdef _WIN32
                if (_putenv_s("GGML_VK_VISIBLE_DEVICES", selection.c_str()) != 0) {
#else
                if (setenv("GGML_VK_VISIBLE_DEVICES", selection.c_str(), 1) != 0) {
#endif
                    break;
                }
                name = properties.deviceName;
                break;
            }
        }
    }
    vkDestroyInstance(instance, nullptr);
    return name;
}
}

int main() {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    std::cin.tie(nullptr);
    const auto device = select_device();
    if (device.empty()) {
        return fail("No compatible Intel or AMD Vulkan GPU found");
    }

    std::string model_path, language;
    if (!std::getline(std::cin, model_path) || !std::getline(std::cin, language)) {
        return fail("Missing model path or language");
    }
    if (language != "auto" && whisper_lang_id(language.c_str()) < 0) {
        return fail("Invalid transcription language");
    }
    auto context_params = whisper_context_default_params();
    context_params.use_gpu = true;
    BackendStatus backend;
    whisper_log_set(check_backend, &backend);
    std::unique_ptr<whisper_context, decltype(&whisper_free)> context(
        whisper_init_from_file_with_params(model_path.c_str(), context_params), whisper_free);
    if (!context || !backend.selected || backend.failed) {
        return fail("Could not initialize the Vulkan model");
    }

    auto params = whisper_full_default_params(WHISPER_SAMPLING_BEAM_SEARCH);
    params.beam_search.beam_size = 5;
    params.language = language.c_str();
    params.no_context = true;
    params.print_progress = false;
    params.print_realtime = false;
    params.print_timestamps = false;
    params.print_special = false;

    std::cout << "READY 1 " << device << std::endl;
    std::string request;
    while (std::getline(std::cin, request)) {
        int samples = 0;
        try {
            samples = std::stoi(request);
        } catch (const std::exception &) {
            return fail("Invalid audio frame size");
        }
        if (samples <= 0 || samples > 60 * WHISPER_SAMPLE_RATE) {
            return fail("Invalid audio frame size");
        }
        std::vector<float> audio(samples);
        if (!std::cin.read(reinterpret_cast<char *>(audio.data()), samples * sizeof(float))) {
            return fail("Incomplete audio frame");
        }
        if (whisper_full(context.get(), params, audio.data(), samples) != 0) {
            return fail("Vulkan inference failed");
        }

        const int segments = whisper_full_n_segments(context.get());
        std::cout << "SEGMENTS " << segments << '\n';
        for (int i = 0; i < segments; ++i) {
            const char *text = whisper_full_get_segment_text(context.get(), i);
            const auto size = std::strlen(text);
            std::cout << whisper_full_get_segment_t0(context.get(), i) << ' '
                      << whisper_full_get_segment_t1(context.get(), i) << ' '
                      << whisper_full_get_segment_no_speech_prob(context.get(), i) << ' '
                      << size << '\n';
            std::cout.write(text, size);
        }
        std::cout.flush();
    }
}
