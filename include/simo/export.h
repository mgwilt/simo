#pragma once

#if defined(_WIN32)
#if defined(SIMO_CORE_BUILD)
#define SIMO_API __declspec(dllexport)
#else
#define SIMO_API __declspec(dllimport)
#endif
#elif defined(__GNUC__) || defined(__clang__)
#define SIMO_API __attribute__((visibility("default")))
#else
#define SIMO_API
#endif
