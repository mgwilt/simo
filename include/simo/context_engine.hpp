#pragma once

#include "simo/export.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace simo {

enum class DropPolicy : std::uint8_t {
    drop_oldest = 0,
    drop_newest = 1,
};

struct EngineConfig {
    std::size_t queue_capacity{256};
    std::size_t max_segments{64};
    DropPolicy drop_policy{DropPolicy::drop_oldest};
    std::string alias_id{"ephemeral:unscoped"};
    std::string conversation_id{"ephemeral:unscoped"};
    std::string local_participant_id{"alias:unscoped"};
};

struct EnqueueResult {
    bool accepted{false};
    std::uint64_t sequence{0};
    std::optional<std::uint64_t> dropped_sequence{};
};

struct ContextItem {
    std::uint64_t sequence{0};
    std::string speaker;
    std::string text;
    bool is_final{false};
    float salience{0.0F};
};

struct ParticipantInput {
    std::string participant_id;
    std::string kind;
    std::string alias_id;
    std::string display_name;
    std::string transport_participant_id;
};

struct ParticipantView : ParticipantInput {};

struct MemoryClaimInput {
    std::string claim_id;
    std::string subject_id;
    std::string claim_key;
    std::string claim_class;
    std::string content;
    std::string source_conversation_id;
    std::string source_event_id;
    std::string stale_after;
    float confidence{0.0F};
};

struct MemoryClaimView : MemoryClaimInput {};

struct ContextSnapshot {
    std::uint64_t revision{0};
    std::uint64_t memory_revision{0};
    std::string alias_id;
    std::string conversation_id;
    std::string local_participant_id;
    std::vector<ParticipantView> participants;
    std::vector<MemoryClaimView> memories;
    std::vector<ContextItem> items;

    [[nodiscard]] std::string to_json() const;
};

struct EngineStats {
    std::uint64_t accepted{0};
    std::uint64_t dropped{0};
    std::uint64_t processed{0};
    std::uint64_t structural_observations{0};
    std::size_t queued{0};
    std::size_t retained{0};
};

struct MemoryRefreshStats {
    std::uint64_t revision{0};
    std::size_t claims{0};
    std::size_t removed{0};
};

struct KnowledgeConceptInput {
    std::string okf_id;
    std::string stable_id;
    std::string type;
    std::string title;
    std::string status;
    std::string authority;
    std::string source_path;
    std::string verified_at;
    std::string stale_after;
    std::string content_hash;
};

struct KnowledgeConceptView : KnowledgeConceptInput {};

struct KnowledgeLinkView {
    std::string source_okf_id;
    std::string target_okf_id;
    std::string relation;
};

struct KnowledgeSnapshot {
    std::uint64_t revision{0};
    std::vector<KnowledgeConceptView> concepts;
    std::vector<KnowledgeLinkView> links;

    [[nodiscard]] std::string to_json() const;
};

struct KnowledgeRefreshStats {
    std::uint64_t revision{0};
    std::size_t concepts{0};
    std::size_t links{0};
    std::size_t removed{0};
};

class SIMO_API ContextEngine final {
public:
    explicit ContextEngine(EngineConfig config = {});
    ~ContextEngine();

    ContextEngine(const ContextEngine&) = delete;
    ContextEngine& operator=(const ContextEngine&) = delete;
    ContextEngine(ContextEngine&&) noexcept;
    ContextEngine& operator=(ContextEngine&&) noexcept;

    [[nodiscard]] EnqueueResult enqueue_transcript(
        std::string speaker,
        std::string text,
        bool is_final = true);
    void upsert_participant(ParticipantInput input);
    void begin_memory_refresh();
    void upsert_memory_claim(MemoryClaimInput input);
    [[nodiscard]] MemoryRefreshStats commit_memory_refresh();
    [[nodiscard]] std::size_t tick();
    [[nodiscard]] std::shared_ptr<const ContextSnapshot> snapshot() const;
    [[nodiscard]] EngineStats stats() const;
    void begin_knowledge_refresh();
    void upsert_knowledge_concept(KnowledgeConceptInput input);
    void add_knowledge_reference(
        const std::string& source_okf_id,
        const std::string& target_okf_id);
    [[nodiscard]] KnowledgeRefreshStats commit_knowledge_refresh();
    [[nodiscard]] std::shared_ptr<const KnowledgeSnapshot> knowledge_snapshot() const;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace simo
