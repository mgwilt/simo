#include "simo/context_engine.hpp"

#include <flecs.h>

#include <algorithm>
#include <atomic>
#include <deque>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <tuple>
#include <unordered_map>
#include <utility>

namespace simo {
namespace {

struct TranscriptSegment {
    std::uint64_t sequence;
    std::string speaker;
    std::string text;
    bool is_final;
};

struct ContextCandidate {
    float salience;
};

struct ConversationIdentity {
    std::string alias_id;
    std::string conversation_id;
    std::string local_participant_id;
};

struct ParticipantIdentity : ParticipantInput {};

struct MemoryClaimComponent : MemoryClaimInput {
    std::uint64_t refresh_generation{0};
};

struct MemoryAboutParticipant {};

struct PendingTranscript {
    std::uint64_t sequence;
    std::string speaker;
    std::string text;
    bool is_final;
};

struct KnowledgeConceptComponent : KnowledgeConceptInput {
    std::uint64_t refresh_generation{0};
};

struct ReferencesKnowledge {};

[[nodiscard]] float score(const TranscriptSegment& segment) {
    const auto bounded_length = std::min<std::size_t>(segment.text.size(), 200U);
    const auto length_score = static_cast<float>(bounded_length) / 200.0F;
    return (segment.is_final ? 1.0F : 0.25F) + length_score;
}

[[nodiscard]] std::string escape_json(const std::string& value) {
    std::ostringstream output;
    for (const unsigned char character : value) {
        switch (character) {
            case '"':
                output << "\\\"";
                break;
            case '\\':
                output << "\\\\";
                break;
            case '\b':
                output << "\\b";
                break;
            case '\f':
                output << "\\f";
                break;
            case '\n':
                output << "\\n";
                break;
            case '\r':
                output << "\\r";
                break;
            case '\t':
                output << "\\t";
                break;
            default:
                if (character < 0x20U) {
                    output << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                           << static_cast<unsigned int>(character) << std::dec;
                } else {
                    output << static_cast<char>(character);
                }
        }
    }
    return output.str();
}

}  // namespace

class ContextEngine::Impl {
public:
    explicit Impl(EngineConfig engine_config)
        : config(std::move(engine_config)),
          conversation(world.entity("simo.Conversation")),
          current_snapshot(std::make_shared<const ContextSnapshot>(ContextSnapshot{
              0U,
              0U,
              config.alias_id,
              config.conversation_id,
              config.local_participant_id,
              {},
              {},
              {},
          })),
          current_knowledge_snapshot(std::make_shared<const KnowledgeSnapshot>()) {
        if (config.queue_capacity == 0U) {
            throw std::invalid_argument("queue_capacity must be greater than zero");
        }
        if (config.max_segments == 0U) {
            throw std::invalid_argument("max_segments must be greater than zero");
        }
        if (config.alias_id.empty() || config.conversation_id.empty() ||
            config.local_participant_id.empty()) {
            throw std::invalid_argument("context scope identity must not be empty");
        }

        world.component<TranscriptSegment>();
        world.component<ContextCandidate>();
        world.component<ConversationIdentity>();
        world.component<ParticipantIdentity>();
        world.component<MemoryClaimComponent>();
        world.component<MemoryAboutParticipant>();
        world.component<KnowledgeConceptComponent>();
        world.component<ReferencesKnowledge>();
        conversation.set<ConversationIdentity>({
            config.alias_id,
            config.conversation_id,
            config.local_participant_id,
        });

        world.observer<TranscriptSegment>("simo.ObserveTranscriptStructure")
            .event(flecs::OnSet)
            .each([this](const TranscriptSegment&) {
                structural_observations.fetch_add(1U, std::memory_order_relaxed);
            });

        world.system<const TranscriptSegment>("simo.ScoreContext")
            .kind(flecs::OnUpdate)
            .each([](flecs::entity entity, const TranscriptSegment& segment) {
                entity.set<ContextCandidate>({score(segment)});
            });
    }

    EngineConfig config;
    flecs::world world;
    flecs::entity conversation;
    mutable std::mutex world_mutex;

    mutable std::mutex queue_mutex;
    std::deque<PendingTranscript> pending;
    std::uint64_t next_sequence{1};
    std::uint64_t accepted{0};
    std::uint64_t dropped{0};
    std::atomic<std::uint64_t> processed{0};
    std::atomic<std::uint64_t> structural_observations{0};

    mutable std::mutex snapshot_mutex;
    std::shared_ptr<const ContextSnapshot> current_snapshot;
    std::unordered_map<std::string, flecs::entity_t> participant_entities;
    std::uint64_t memory_generation{0};
    bool memory_refresh_active{false};
    std::unordered_map<std::string, flecs::entity_t> memory_entities;

    std::uint64_t knowledge_generation{0};
    bool knowledge_refresh_active{false};
    std::unordered_map<std::string, flecs::entity_t> knowledge_entities;
    std::vector<KnowledgeLinkView> pending_knowledge_links;
    std::shared_ptr<const KnowledgeSnapshot> current_knowledge_snapshot;
};

std::string ContextSnapshot::to_json() const {
    std::ostringstream output;
    output << "{\"revision\":" << revision << ",\"memory_revision\":"
           << memory_revision << ",\"alias_id\":\""
           << escape_json(alias_id) << "\",\"conversation_id\":\""
           << escape_json(conversation_id) << "\",\"local_participant_id\":\""
           << escape_json(local_participant_id) << "\",\"participants\":[";
    for (std::size_t index = 0; index < participants.size(); ++index) {
        const auto& participant = participants[index];
        if (index != 0U) {
            output << ',';
        }
        output << "{\"participant_id\":\"" << escape_json(participant.participant_id)
               << "\",\"kind\":\"" << escape_json(participant.kind)
               << "\",\"alias_id\":\"" << escape_json(participant.alias_id)
               << "\",\"display_name\":\"" << escape_json(participant.display_name)
               << "\",\"transport_participant_id\":\""
               << escape_json(participant.transport_participant_id) << "\"}";
    }
    output << "],\"memories\":[";
    for (std::size_t index = 0; index < memories.size(); ++index) {
        const auto& memory = memories[index];
        if (index != 0U) {
            output << ',';
        }
        output << "{\"claim_id\":\"" << escape_json(memory.claim_id)
               << "\",\"subject_id\":\"" << escape_json(memory.subject_id)
               << "\",\"claim_key\":\"" << escape_json(memory.claim_key)
               << "\",\"claim_class\":\"" << escape_json(memory.claim_class)
               << "\",\"content\":\"" << escape_json(memory.content)
               << "\",\"source_conversation_id\":\""
               << escape_json(memory.source_conversation_id)
               << "\",\"source_event_id\":\"" << escape_json(memory.source_event_id)
               << "\",\"stale_after\":\"" << escape_json(memory.stale_after)
               << "\",\"confidence\":" << memory.confidence << '}';
    }
    output << "],\"items\":[";
    for (std::size_t index = 0; index < items.size(); ++index) {
        const auto& item = items[index];
        if (index != 0U) {
            output << ',';
        }
        output << "{\"sequence\":" << item.sequence << ",\"speaker\":\""
               << escape_json(item.speaker) << "\",\"text\":\"" << escape_json(item.text)
               << "\",\"is_final\":" << (item.is_final ? "true" : "false")
               << ",\"salience\":" << item.salience << '}';
    }
    output << "]}";
    return output.str();
}

std::string KnowledgeSnapshot::to_json() const {
    std::ostringstream output;
    output << "{\"revision\":" << revision << ",\"concepts\":[";
    for (std::size_t index = 0; index < concepts.size(); ++index) {
        const auto& item = concepts[index];
        if (index != 0U) {
            output << ',';
        }
        output << "{\"okf_id\":\"" << escape_json(item.okf_id)
               << "\",\"stable_id\":\"" << escape_json(item.stable_id)
               << "\",\"type\":\"" << escape_json(item.type)
               << "\",\"title\":\"" << escape_json(item.title)
               << "\",\"status\":\"" << escape_json(item.status)
               << "\",\"authority\":\"" << escape_json(item.authority)
               << "\",\"source_path\":\"" << escape_json(item.source_path)
               << "\",\"verified_at\":\"" << escape_json(item.verified_at)
               << "\",\"stale_after\":\"" << escape_json(item.stale_after)
               << "\",\"content_hash\":\"" << escape_json(item.content_hash)
               << "\"}";
    }
    output << "],\"links\":[";
    for (std::size_t index = 0; index < links.size(); ++index) {
        const auto& link = links[index];
        if (index != 0U) {
            output << ',';
        }
        output << "{\"source_okf_id\":\"" << escape_json(link.source_okf_id)
               << "\",\"target_okf_id\":\"" << escape_json(link.target_okf_id)
               << "\",\"relation\":\"" << escape_json(link.relation) << "\"}";
    }
    output << "]}";
    return output.str();
}

ContextEngine::ContextEngine(EngineConfig config) : impl_(std::make_unique<Impl>(config)) {}

ContextEngine::~ContextEngine() = default;
ContextEngine::ContextEngine(ContextEngine&&) noexcept = default;
ContextEngine& ContextEngine::operator=(ContextEngine&&) noexcept = default;

EnqueueResult ContextEngine::enqueue_transcript(
    std::string speaker,
    std::string text,
    const bool is_final) {
    std::lock_guard lock(impl_->queue_mutex);
    const auto sequence = impl_->next_sequence++;
    std::optional<std::uint64_t> dropped_sequence;

    if (impl_->pending.size() == impl_->config.queue_capacity) {
        ++impl_->dropped;
        if (impl_->config.drop_policy == DropPolicy::drop_newest) {
            return {.accepted = false, .sequence = sequence, .dropped_sequence = sequence};
        }
        dropped_sequence = impl_->pending.front().sequence;
        impl_->pending.pop_front();
    }

    impl_->pending.push_back(
        PendingTranscript{sequence, std::move(speaker), std::move(text), is_final});
    ++impl_->accepted;
    return {.accepted = true, .sequence = sequence, .dropped_sequence = dropped_sequence};
}

void ContextEngine::upsert_participant(ParticipantInput input) {
    if (input.participant_id.empty() || input.kind.empty() || input.display_name.empty()) {
        throw std::invalid_argument("participant identity fields must not be empty");
    }
    std::lock_guard world_lock(impl_->world_mutex);
    auto iterator = impl_->participant_entities.find(input.participant_id);
    flecs::entity entity;
    if (iterator == impl_->participant_entities.end()) {
        entity = impl_->world.entity().child_of(impl_->conversation);
        impl_->participant_entities.emplace(input.participant_id, entity.id());
    } else {
        entity = impl_->world.entity(iterator->second);
    }
    ParticipantIdentity component;
    static_cast<ParticipantInput&>(component) = input;
    entity.set<ParticipantIdentity>(std::move(component));

    std::vector<ParticipantView> participants;
    participants.reserve(impl_->participant_entities.size());
    for (const auto& [participant_id, entity_id] : impl_->participant_entities) {
        static_cast<void>(participant_id);
        const auto* current = impl_->world.entity(entity_id).try_get<ParticipantIdentity>();
        if (current != nullptr) {
            participants.push_back({static_cast<const ParticipantInput&>(*current)});
        }
    }
    std::ranges::sort(participants, {}, &ParticipantView::participant_id);
    std::lock_guard snapshot_lock(impl_->snapshot_mutex);
    impl_->current_snapshot = std::make_shared<const ContextSnapshot>(ContextSnapshot{
        impl_->current_snapshot->revision,
        impl_->current_snapshot->memory_revision,
        impl_->config.alias_id,
        impl_->config.conversation_id,
        impl_->config.local_participant_id,
        std::move(participants),
        impl_->current_snapshot->memories,
        impl_->current_snapshot->items,
    });
}

void ContextEngine::begin_memory_refresh() {
    std::lock_guard lock(impl_->world_mutex);
    ++impl_->memory_generation;
    impl_->memory_refresh_active = true;
    for (const auto& [claim_id, entity_id] : impl_->memory_entities) {
        static_cast<void>(claim_id);
        impl_->world.entity(entity_id).remove<MemoryAboutParticipant>(flecs::Wildcard);
    }
}

void ContextEngine::upsert_memory_claim(MemoryClaimInput input) {
    if (input.claim_id.empty() || input.subject_id.empty() || input.claim_key.empty() ||
        input.claim_class.empty() || input.content.empty() || input.confidence < 0.0F ||
        input.confidence > 1.0F) {
        throw std::invalid_argument("memory claim fields are invalid");
    }
    std::lock_guard lock(impl_->world_mutex);
    if (!impl_->memory_refresh_active) {
        throw std::logic_error("memory refresh is not active");
    }
    auto iterator = impl_->memory_entities.find(input.claim_id);
    flecs::entity entity;
    if (iterator == impl_->memory_entities.end()) {
        entity = impl_->world.entity().child_of(impl_->conversation);
        impl_->memory_entities.emplace(input.claim_id, entity.id());
    } else {
        entity = impl_->world.entity(iterator->second);
    }
    const auto subject = impl_->participant_entities.find(input.subject_id);
    if (subject != impl_->participant_entities.end()) {
        entity.add<MemoryAboutParticipant>(impl_->world.entity(subject->second));
    }
    MemoryClaimComponent component;
    static_cast<MemoryClaimInput&>(component) = std::move(input);
    component.refresh_generation = impl_->memory_generation;
    entity.set<MemoryClaimComponent>(std::move(component));
}

MemoryRefreshStats ContextEngine::commit_memory_refresh() {
    std::lock_guard world_lock(impl_->world_mutex);
    if (!impl_->memory_refresh_active) {
        throw std::logic_error("memory refresh is not active");
    }
    std::size_t removed = 0U;
    for (auto iterator = impl_->memory_entities.begin(); iterator != impl_->memory_entities.end();) {
        const auto entity = impl_->world.entity(iterator->second);
        const auto* item = entity.try_get<MemoryClaimComponent>();
        if (item == nullptr || item->refresh_generation != impl_->memory_generation) {
            entity.destruct();
            iterator = impl_->memory_entities.erase(iterator);
            ++removed;
        } else {
            ++iterator;
        }
    }
    std::vector<MemoryClaimView> memories;
    memories.reserve(impl_->memory_entities.size());
    for (const auto& [claim_id, entity_id] : impl_->memory_entities) {
        static_cast<void>(claim_id);
        const auto* item = impl_->world.entity(entity_id).try_get<MemoryClaimComponent>();
        if (item != nullptr) {
            memories.push_back({static_cast<const MemoryClaimInput&>(*item)});
        }
    }
    std::ranges::sort(memories, {}, &MemoryClaimView::claim_id);
    std::lock_guard snapshot_lock(impl_->snapshot_mutex);
    const auto revision = impl_->current_snapshot->memory_revision + 1U;
    impl_->current_snapshot = std::make_shared<const ContextSnapshot>(ContextSnapshot{
        impl_->current_snapshot->revision,
        revision,
        impl_->config.alias_id,
        impl_->config.conversation_id,
        impl_->config.local_participant_id,
        impl_->current_snapshot->participants,
        std::move(memories),
        impl_->current_snapshot->items,
    });
    impl_->memory_refresh_active = false;
    return {revision, impl_->current_snapshot->memories.size(), removed};
}

std::size_t ContextEngine::tick() {
    std::deque<PendingTranscript> events;
    {
        std::lock_guard lock(impl_->queue_mutex);
        if (impl_->pending.empty()) {
            return 0U;
        }
        events.swap(impl_->pending);
    }

    std::lock_guard world_lock(impl_->world_mutex);
    std::ranges::sort(events, {}, &PendingTranscript::sequence);
    for (auto& event : events) {
        impl_->world.entity()
            .child_of(impl_->conversation)
            .set<TranscriptSegment>({
                event.sequence,
                std::move(event.speaker),
                std::move(event.text),
                event.is_final,
            });
    }
    impl_->processed.fetch_add(events.size(), std::memory_order_relaxed);

    impl_->world.progress(0.0F);

    std::vector<std::pair<std::uint64_t, flecs::entity>> retained_entities;
    auto transcript_query = impl_->world.query<const TranscriptSegment>();
    transcript_query.each(
        [&retained_entities](flecs::entity entity, const TranscriptSegment& segment) {
            retained_entities.emplace_back(segment.sequence, entity);
        });
    std::ranges::sort(retained_entities, {}, &std::pair<std::uint64_t, flecs::entity>::first);
    const auto excess = retained_entities.size() > impl_->config.max_segments
                            ? retained_entities.size() - impl_->config.max_segments
                            : 0U;
    for (std::size_t index = 0; index < excess; ++index) {
        retained_entities[index].second.destruct();
    }

    std::vector<ContextItem> items;
    auto snapshot_query = impl_->world.query<const TranscriptSegment, const ContextCandidate>();
    snapshot_query.each(
        [&items](
            flecs::entity,
            const TranscriptSegment& segment,
            const ContextCandidate& candidate) {
            items.push_back({
                segment.sequence,
                segment.speaker,
                segment.text,
                segment.is_final,
                candidate.salience,
            });
        });
    std::ranges::sort(items, {}, &ContextItem::sequence);

    std::lock_guard lock(impl_->snapshot_mutex);
    const auto next_revision = impl_->current_snapshot->revision + 1U;
    impl_->current_snapshot = std::make_shared<const ContextSnapshot>(ContextSnapshot{
        next_revision,
        impl_->current_snapshot->memory_revision,
        impl_->config.alias_id,
        impl_->config.conversation_id,
        impl_->config.local_participant_id,
        impl_->current_snapshot->participants,
        impl_->current_snapshot->memories,
        std::move(items),
    });
    return events.size();
}

std::shared_ptr<const ContextSnapshot> ContextEngine::snapshot() const {
    std::lock_guard lock(impl_->snapshot_mutex);
    return impl_->current_snapshot;
}

EngineStats ContextEngine::stats() const {
    EngineStats result;
    {
        std::lock_guard lock(impl_->queue_mutex);
        result.accepted = impl_->accepted;
        result.dropped = impl_->dropped;
        result.queued = impl_->pending.size();
    }
    result.processed = impl_->processed.load(std::memory_order_relaxed);
    result.structural_observations =
        impl_->structural_observations.load(std::memory_order_relaxed);
    result.retained = snapshot()->items.size();
    return result;
}

void ContextEngine::begin_knowledge_refresh() {
    std::lock_guard lock(impl_->world_mutex);
    ++impl_->knowledge_generation;
    impl_->knowledge_refresh_active = true;
    impl_->pending_knowledge_links.clear();
    for (const auto& [okf_id, entity_id] : impl_->knowledge_entities) {
        static_cast<void>(okf_id);
        impl_->world.entity(entity_id).remove<ReferencesKnowledge>(flecs::Wildcard);
    }
}

void ContextEngine::upsert_knowledge_concept(KnowledgeConceptInput input) {
    if (input.okf_id.empty() || input.stable_id.empty() || input.type.empty() ||
        input.source_path.empty()) {
        throw std::invalid_argument("knowledge concept identity fields must not be empty");
    }
    std::lock_guard lock(impl_->world_mutex);
    if (!impl_->knowledge_refresh_active) {
        throw std::logic_error("knowledge refresh is not active");
    }
    auto iterator = impl_->knowledge_entities.find(input.okf_id);
    flecs::entity entity;
    if (iterator == impl_->knowledge_entities.end()) {
        entity = impl_->world.entity();
        impl_->knowledge_entities.emplace(input.okf_id, entity.id());
    } else {
        entity = impl_->world.entity(iterator->second);
    }
    KnowledgeConceptComponent component;
    static_cast<KnowledgeConceptInput&>(component) = std::move(input);
    component.refresh_generation = impl_->knowledge_generation;
    entity.set<KnowledgeConceptComponent>(std::move(component));
}

void ContextEngine::add_knowledge_reference(
    const std::string& source_okf_id,
    const std::string& target_okf_id) {
    std::lock_guard lock(impl_->world_mutex);
    if (!impl_->knowledge_refresh_active) {
        throw std::logic_error("knowledge refresh is not active");
    }
    const auto source = impl_->knowledge_entities.find(source_okf_id);
    const auto target = impl_->knowledge_entities.find(target_okf_id);
    if (source == impl_->knowledge_entities.end() ||
        target == impl_->knowledge_entities.end()) {
        throw std::invalid_argument("knowledge reference endpoint does not exist");
    }
    auto source_entity = impl_->world.entity(source->second);
    const auto target_entity = impl_->world.entity(target->second);
    source_entity.add<ReferencesKnowledge>(target_entity);
    if (!source_entity.has<ReferencesKnowledge>(target_entity)) {
        throw std::runtime_error("failed to create Flecs knowledge relation");
    }
    impl_->pending_knowledge_links.push_back(
        {source_okf_id, target_okf_id, "references"});
}

KnowledgeRefreshStats ContextEngine::commit_knowledge_refresh() {
    std::lock_guard lock(impl_->world_mutex);
    if (!impl_->knowledge_refresh_active) {
        throw std::logic_error("knowledge refresh is not active");
    }
    std::size_t removed = 0U;
    for (auto iterator = impl_->knowledge_entities.begin();
         iterator != impl_->knowledge_entities.end();) {
        const auto entity = impl_->world.entity(iterator->second);
        const auto* item = entity.try_get<KnowledgeConceptComponent>();
        if (item == nullptr || item->refresh_generation != impl_->knowledge_generation) {
            entity.destruct();
            iterator = impl_->knowledge_entities.erase(iterator);
            ++removed;
        } else {
            ++iterator;
        }
    }

    std::vector<KnowledgeConceptView> concepts;
    concepts.reserve(impl_->knowledge_entities.size());
    for (const auto& [okf_id, entity_id] : impl_->knowledge_entities) {
        static_cast<void>(okf_id);
        const auto* component =
            impl_->world.entity(entity_id).try_get<KnowledgeConceptComponent>();
        if (component != nullptr) {
            concepts.push_back({static_cast<const KnowledgeConceptInput&>(*component)});
        }
    }
    std::ranges::sort(concepts, {}, &KnowledgeConceptView::okf_id);
    auto links = impl_->pending_knowledge_links;
    std::ranges::sort(links, [](const auto& left, const auto& right) {
        return std::tie(left.source_okf_id, left.target_okf_id, left.relation) <
               std::tie(right.source_okf_id, right.target_okf_id, right.relation);
    });
    links.erase(std::unique(links.begin(), links.end(), [](const auto& left, const auto& right) {
                    return left.source_okf_id == right.source_okf_id &&
                           left.target_okf_id == right.target_okf_id &&
                           left.relation == right.relation;
                }),
                links.end());
    const auto revision = impl_->current_knowledge_snapshot->revision + 1U;
    impl_->current_knowledge_snapshot = std::make_shared<const KnowledgeSnapshot>(
        KnowledgeSnapshot{revision, std::move(concepts), std::move(links)});
    impl_->knowledge_refresh_active = false;
    return {
        revision,
        impl_->current_knowledge_snapshot->concepts.size(),
        impl_->current_knowledge_snapshot->links.size(),
        removed,
    };
}

std::shared_ptr<const KnowledgeSnapshot> ContextEngine::knowledge_snapshot() const {
    std::lock_guard lock(impl_->world_mutex);
    return impl_->current_knowledge_snapshot;
}

}  // namespace simo
