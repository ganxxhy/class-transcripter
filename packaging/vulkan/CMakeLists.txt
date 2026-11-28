cmake_minimum_required(VERSION 3.20)
project(studio_whisper_vulkan LANGUAGES C CXX)

include(FetchContent)
if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(GGML_VULKAN ON CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
find_package(Vulkan REQUIRED)
FetchContent_Declare(whisper_cpp
  URL https://codeload.github.com/ggml-org/whisper.cpp/tar.gz/2eeeba56e9edd762b4b38467bab96c2517163158
  URL_HASH SHA256=089b898aa83b24a8321e0fd554eeb0967fb03dd687e27f6374c72d3363b5b429)
FetchContent_MakeAvailable(whisper_cpp)

add_executable(studio-whisper-vulkan worker.cpp)
target_compile_features(studio-whisper-vulkan PRIVATE cxx_std_17)
target_link_libraries(studio-whisper-vulkan PRIVATE whisper Vulkan::Vulkan)
