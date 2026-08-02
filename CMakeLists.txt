cmake_minimum_required(VERSION 3.20)

project(simo LANGUAGES C CXX)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SIMO_BUILD_TESTS "Build Simo native tests" ON)

set(FLECS_STATIC ON CACHE BOOL "" FORCE)
set(FLECS_SHARED OFF CACHE BOOL "" FORCE)
set(FLECS_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory(vendor/flecs EXCLUDE_FROM_ALL)

add_library(simo_core SHARED
    src/context_engine.cpp
    src/context_engine_c.cpp
)
target_include_directories(simo_core PUBLIC include)
target_link_libraries(simo_core PRIVATE flecs::flecs_static)
target_compile_definitions(simo_core PRIVATE SIMO_CORE_BUILD)
set_target_properties(simo_core PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
)

if(MSVC)
    target_compile_options(simo_core PRIVATE /W4 /WX)
else()
    target_compile_options(simo_core PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

if(SIMO_BUILD_TESTS)
    enable_testing()
    add_executable(simo_context_engine_test tests/native/context_engine_test.cpp)
    target_link_libraries(simo_context_engine_test PRIVATE simo_core)
    if(MSVC)
        target_compile_options(simo_context_engine_test PRIVATE /W4 /WX)
    else()
        target_compile_options(simo_context_engine_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
    add_test(NAME simo_context_engine COMMAND simo_context_engine_test)
endif()
