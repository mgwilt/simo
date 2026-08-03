#include "simo/context_engine_c.h"

#include "simo/context_engine.hpp"

#include <cstring>
#include <memory>
#include <new>
#include <string>

struct simo_context_engine {
    explicit simo_context_engine(simo::EngineConfig config) : value(config) {}
    simo::ContextEngine value;
};

extern "C" {

simo_context_engine* simo_context_engine_create(
    const size_t queue_capacity,
    const size_t max_segments,
    const simo_drop_policy drop_policy) {
    try {
        if (drop_policy != SIMO_DROP_OLDEST && drop_policy != SIMO_DROP_NEWEST) {
            return nullptr;
        }
        const auto policy = drop_policy == SIMO_DROP_NEWEST ? simo::DropPolicy::drop_newest
                                                            : simo::DropPolicy::drop_oldest;
        return new simo_context_engine({queue_capacity, max_segments, policy});
    } catch (...) {
        return nullptr;
    }
}

void simo_context_engine_destroy(simo_context_engine* engine) {
    delete engine;
}

int simo_context_engine_enqueue_transcript(
    simo_context_engine* engine,
    const char* speaker,
    const char* text,
    const int is_final,
    uint64_t* sequence) {
    if (engine == nullptr || speaker == nullptr || text == nullptr) {
        return -1;
    }
    try {
        const auto result = engine->value.enqueue_transcript(speaker, text, is_final != 0);
        if (sequence != nullptr) {
            *sequence = result.sequence;
        }
        return result.accepted ? 1 : 0;
    } catch (...) {
        return -1;
    }
}

size_t simo_context_engine_tick(simo_context_engine* engine) {
    if (engine == nullptr) {
        return 0U;
    }
    try {
        return engine->value.tick();
    } catch (...) {
        return 0U;
    }
}

size_t simo_context_engine_snapshot_json(
    const simo_context_engine* engine,
    char* buffer,
    const size_t capacity) {
    if (engine == nullptr) {
        return 0U;
    }
    try {
        const std::string json = engine->value.snapshot()->to_json();
        const auto required = json.size() + 1U;
        if (buffer != nullptr && capacity >= required) {
            std::memcpy(buffer, json.c_str(), required);
        }
        return required;
    } catch (...) {
        return 0U;
    }
}

int simo_context_engine_stats(const simo_context_engine* engine, simo_engine_stats* stats) {
    if (engine == nullptr || stats == nullptr) {
        return -1;
    }
    try {
        const auto value = engine->value.stats();
        *stats = {
            value.accepted,
            value.dropped,
            value.processed,
            value.structural_observations,
            value.queued,
            value.retained,
        };
        return 0;
    } catch (...) {
        return -1;
    }
}

int simo_context_engine_begin_knowledge_refresh(simo_context_engine* engine) {
    if (engine == nullptr) {
        return -1;
    }
    try {
        engine->value.begin_knowledge_refresh();
        return 0;
    } catch (...) {
        return -1;
    }
}

int simo_context_engine_upsert_knowledge_concept(
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
    const char* content_hash) {
    if (engine == nullptr || okf_id == nullptr || stable_id == nullptr || type == nullptr ||
        title == nullptr || status == nullptr || authority == nullptr ||
        source_path == nullptr || verified_at == nullptr || stale_after == nullptr ||
        content_hash == nullptr) {
        return -1;
    }
    try {
        engine->value.upsert_knowledge_concept({
            okf_id,
            stable_id,
            type,
            title,
            status,
            authority,
            source_path,
            verified_at,
            stale_after,
            content_hash,
        });
        return 0;
    } catch (...) {
        return -1;
    }
}

int simo_context_engine_add_knowledge_reference(
    simo_context_engine* engine,
    const char* source_okf_id,
    const char* target_okf_id) {
    if (engine == nullptr || source_okf_id == nullptr || target_okf_id == nullptr) {
        return -1;
    }
    try {
        engine->value.add_knowledge_reference(source_okf_id, target_okf_id);
        return 0;
    } catch (...) {
        return -1;
    }
}

int simo_context_engine_commit_knowledge_refresh(
    simo_context_engine* engine,
    simo_knowledge_refresh_stats* stats) {
    if (engine == nullptr || stats == nullptr) {
        return -1;
    }
    try {
        const auto value = engine->value.commit_knowledge_refresh();
        *stats = {value.revision, value.concepts, value.links, value.removed};
        return 0;
    } catch (...) {
        return -1;
    }
}

size_t simo_context_engine_knowledge_snapshot_json(
    const simo_context_engine* engine,
    char* buffer,
    const size_t capacity) {
    if (engine == nullptr) {
        return 0U;
    }
    try {
        const std::string json = engine->value.knowledge_snapshot()->to_json();
        const auto required = json.size() + 1U;
        if (buffer != nullptr && capacity >= required) {
            std::memcpy(buffer, json.c_str(), required);
        }
        return required;
    } catch (...) {
        return 0U;
    }
}

}  // extern "C"
