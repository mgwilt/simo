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

typedef struct simo_knowledge_refresh_stats {
    uint64_t revision;
    size_t concepts;
    size_t links;
    size_t removed;
} simo_knowledge_refresh_stats;

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

SIMO_API int simo_context_engine_begin_knowledge_refresh(simo_context_engine* engine);
SIMO_API int simo_context_engine_upsert_knowledge_concept(
    simo_context_engine* engine,
    const char* okf_id,
    const char* stable_id,
    const char* type,
    const char* title,
    const char* status,
    const char* authority,
    const char* source_path,
    const char* verified_at,
    const char* stale_after,
    const char* content_hash);
SIMO_API int simo_context_engine_add_knowledge_reference(
    simo_context_engine* engine,
    const char* source_okf_id,
    const char* target_okf_id);
SIMO_API int simo_context_engine_commit_knowledge_refresh(
    simo_context_engine* engine,
    simo_knowledge_refresh_stats* stats);
SIMO_API size_t simo_context_engine_knowledge_snapshot_json(
    const simo_context_engine* engine,
    char* buffer,
    size_t capacity);

#ifdef __cplusplus
}
#endif
