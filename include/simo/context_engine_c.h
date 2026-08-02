#pragma once

#include "simo/export.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct simo_context_engine simo_context_engine;

typedef enum simo_drop_policy {
    SIMO_DROP_OLDEST = 0,
    SIMO_DROP_NEWEST = 1,
} simo_drop_policy;

typedef struct simo_engine_stats {
    uint64_t accepted;
    uint64_t dropped;
    uint64_t processed;
    uint64_t structural_observations;
    size_t queued;
    size_t retained;
} simo_engine_stats;

SIMO_API simo_context_engine* simo_context_engine_create(
    size_t queue_capacity,
    size_t max_segments,
    simo_drop_policy drop_policy);
SIMO_API void simo_context_engine_destroy(simo_context_engine* engine);

/* Returns 1 when accepted, 0 when rejected by policy, and -1 for invalid input. */
SIMO_API int simo_context_engine_enqueue_transcript(
    simo_context_engine* engine,
    const char* speaker,
    const char* text,
    int is_final,
    uint64_t* sequence);

SIMO_API size_t simo_context_engine_tick(simo_context_engine* engine);

/* Returns required bytes including the trailing NUL. No write occurs when capacity is too small. */
SIMO_API size_t simo_context_engine_snapshot_json(
    const simo_context_engine* engine,
    char* buffer,
    size_t capacity);

SIMO_API int simo_context_engine_stats(
    const simo_context_engine* engine,
    simo_engine_stats* stats);

#ifdef __cplusplus
}
#endif
