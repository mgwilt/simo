#include "simo/context_engine.hpp"

#include <flecs.h>

#include <algorithm>
#include <atomic>
#include <deque>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <stdexcept>
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

struct PendingTranscript {
    std::uint64_t sequence;
    std::string speaker;
    std::string text;
    bool is_final;
};

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
          current_snapshot(std::make_shared<const ContextSnapshot>()) {
        if (config.queue_capacity == 0U) {
            throw std::invalid_argument("queue_capacity must be greater than zero");
        }
        if (config.max_segments == 0U) {
            throw std::invalid_argument("max_segments must be greater than zero");
        }

        world.component<TranscriptSegment>();
        world.component<ContextCandidate>();

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

    mutable std::mutex queue_mutex;
    std::deque<PendingTranscript> pending;
    std::uint64_t next_sequence{1};
    std::uint64_t accepted{0};
    std::uint64_t dropped{0};
    std::atomic<std::uint64_t> processed{0};
    std::atomic<std::uint64_t> structural_observations{0};

    mutable std::mutex snapshot_mutex;
    std::shared_ptr<const ContextSnapshot> current_snapshot;
};

std::string ContextSnapshot::to_json() const {
    std::ostringstream output;
    output << "{\"revision\":" << revision << ",\"items\":[";
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

std::size_t ContextEngine::tick() {
    std::deque<PendingTranscript> events;
    {
        std::lock_guard lock(impl_->queue_mutex);
        if (impl_->pending.empty()) {
            return 0U;
        }
        events.swap(impl_->pending);
    }

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
    impl_->current_snapshot =
        std::make_shared<const ContextSnapshot>(ContextSnapshot{next_revision, std::move(items)});
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

}  // namespace simo
