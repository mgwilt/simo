#include "simo/context_engine.hpp"
#include "simo/context_engine_c.h"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace {

void test_drop_oldest_and_ordered_snapshot() {
    simo::ContextEngine engine({2U, 8U, simo::DropPolicy::drop_oldest});
    const auto first = engine.enqueue_transcript("user", "one");
    const auto second = engine.enqueue_transcript("user", "two");
    const auto third = engine.enqueue_transcript("agent", "three");

    assert(first.accepted);
    assert(second.accepted);
    assert(third.accepted);
    assert(third.dropped_sequence == first.sequence);
    assert(engine.tick() == 2U);

    const auto snapshot = engine.snapshot();
    assert(snapshot->revision == 1U);
    assert(snapshot->items.size() == 2U);
    assert(snapshot->items[0].sequence == second.sequence);
    assert(snapshot->items[0].text == "two");
    assert(snapshot->items[1].sequence == third.sequence);
    assert(snapshot->items[1].speaker == "agent");

    const auto stats = engine.stats();
    assert(stats.accepted == 3U);
    assert(stats.dropped == 1U);
    assert(stats.processed == 2U);
    assert(stats.structural_observations == 2U);
    assert(stats.queued == 0U);
    assert(stats.retained == 2U);
}

void test_drop_newest_and_retention() {
    simo::ContextEngine engine({1U, 1U, simo::DropPolicy::drop_newest});
    const auto first = engine.enqueue_transcript("user", "kept", false);
    const auto rejected = engine.enqueue_transcript("user", "rejected", true);
    assert(first.accepted);
    assert(!rejected.accepted);
    assert(engine.tick() == 1U);

    auto snapshot = engine.snapshot();
    assert(snapshot->items.size() == 1U);
    assert(snapshot->items[0].text == "kept");
    assert(!snapshot->items[0].is_final);
    assert(snapshot->items[0].salience >= 0.25F);

    const auto next = engine.enqueue_transcript("agent", "replacement", true);
    assert(next.accepted);
    assert(engine.tick() == 1U);
    snapshot = engine.snapshot();
    assert(snapshot->revision == 2U);
    assert(snapshot->items.size() == 1U);
    assert(snapshot->items[0].text == "replacement");
}

void test_snapshot_is_immutable_value() {
    simo::ContextEngine engine;
    static_cast<void>(engine.enqueue_transcript("user", "before"));
    assert(engine.tick() == 1U);
    const auto before = engine.snapshot();

    static_cast<void>(engine.enqueue_transcript("agent", "after"));
    assert(engine.tick() == 1U);
    const auto after = engine.snapshot();

    assert(before->revision == 1U);
    assert(before->items.size() == 1U);
    assert(after->revision == 2U);
    assert(after->items.size() == 2U);
}

void test_scoped_worlds_project_identity_without_cross_contamination() {
    simo::ContextEngine left({
        4U,
        4U,
        simo::DropPolicy::drop_oldest,
        "alias-left",
        "conversation-left",
        "participant-left",
    });
    simo::ContextEngine right({
        4U,
        4U,
        simo::DropPolicy::drop_oldest,
        "alias-right",
        "conversation-right",
        "participant-right",
    });
    left.upsert_participant(
        {"participant-left", "alias", "alias-left", "Left", "transport-left"});
    left.upsert_participant({"remote-right", "alias", "alias-right", "Right", "transport-right"});
    right.upsert_participant(
        {"participant-right", "alias", "alias-right", "Right", "transport-right"});
    right.upsert_participant({"remote-left", "alias", "alias-left", "Left", "transport-left"});

    static_cast<void>(left.enqueue_transcript("remote-right", "left world only"));
    static_cast<void>(right.enqueue_transcript("remote-left", "right world only"));
    assert(left.tick() == 1U);
    assert(right.tick() == 1U);

    const auto left_snapshot = left.snapshot();
    const auto right_snapshot = right.snapshot();
    assert(left_snapshot->alias_id == "alias-left");
    assert(left_snapshot->conversation_id == "conversation-left");
    assert(left_snapshot->local_participant_id == "participant-left");
    assert(left_snapshot->participants.size() == 2U);
    assert(left_snapshot->items[0].text == "left world only");
    assert(right_snapshot->alias_id == "alias-right");
    assert(right_snapshot->items[0].text == "right world only");
    assert(right_snapshot->to_json().find("left world only") == std::string::npos);
    assert(left_snapshot->to_json().find("entity_id") == std::string::npos);
}

void test_c_api_json_contract() {
    std::unique_ptr<simo_context_engine, decltype(&simo_context_engine_destroy)> engine(
        simo_context_engine_create_scoped(
            4U,
            4U,
            SIMO_DROP_OLDEST,
            "alias-c",
            "conversation-c",
            "participant-c"),
        &simo_context_engine_destroy);
    assert(engine != nullptr);
    assert(simo_context_engine_upsert_participant(
               engine.get(), "participant-c", "alias", "alias-c", "C", "transport-c") == 0);

    std::uint64_t sequence = 0;
    assert(simo_context_engine_enqueue_transcript(
               engine.get(), "user", "quote: \"ok\"", 1, &sequence) == 1);
    assert(sequence == 1U);
    assert(simo_context_engine_tick(engine.get()) == 1U);

    const auto required = simo_context_engine_snapshot_json(engine.get(), nullptr, 0U);
    assert(required > 1U);
    std::vector<char> buffer(required);
    assert(
        simo_context_engine_snapshot_json(engine.get(), buffer.data(), buffer.size()) == required);
    const std::string json(buffer.data());
    assert(json.find("\\\"ok\\\"") != std::string::npos);
    assert(json.find("\"conversation_id\":\"conversation-c\"") != std::string::npos);
}

simo::KnowledgeConceptInput knowledge_input(
    std::string okf_id,
    std::string stable_id,
    std::string title,
    std::string content_hash) {
    return {
        std::move(okf_id),
        std::move(stable_id),
        "Architecture Concept",
        std::move(title),
        "stable",
        "architecture",
        "docs/concept.md",
        "2026-08-03T00:00:00Z",
        "2026-09-03",
        std::move(content_hash),
    };
}

void test_incremental_knowledge_projection() {
    simo::ContextEngine engine;
    engine.begin_knowledge_refresh();
    engine.upsert_knowledge_concept(
        knowledge_input("architecture/one", "DOC-0001", "One", "hash-one"));
    engine.upsert_knowledge_concept(
        knowledge_input("interfaces/two", "DOC-0002", "Two", "hash-two"));
    engine.add_knowledge_reference("architecture/one", "interfaces/two");
    const auto first_stats = engine.commit_knowledge_refresh();
    assert(first_stats.revision == 1U);
    assert(first_stats.concepts == 2U);
    assert(first_stats.links == 1U);
    assert(first_stats.removed == 0U);
    const auto first = engine.knowledge_snapshot();
    assert(first->concepts[0].okf_id == "architecture/one");
    assert(first->concepts[0].stable_id == "DOC-0001");
    assert(first->links[0].relation == "references");

    engine.begin_knowledge_refresh();
    engine.upsert_knowledge_concept(
        knowledge_input("interfaces/two", "DOC-0002", "Two revised", "hash-three"));
    const auto second_stats = engine.commit_knowledge_refresh();
    assert(second_stats.revision == 2U);
    assert(second_stats.concepts == 1U);
    assert(second_stats.links == 0U);
    assert(second_stats.removed == 1U);
    const auto second = engine.knowledge_snapshot();
    assert(second->concepts[0].title == "Two revised");
    assert(second->concepts[0].content_hash == "hash-three");
    assert(first->concepts.size() == 2U);
    assert(first->links.size() == 1U);
}

}  // namespace

int main() {
    test_drop_oldest_and_ordered_snapshot();
    test_drop_newest_and_retention();
    test_snapshot_is_immutable_value();
    test_scoped_worlds_project_identity_without_cross_contamination();
    test_c_api_json_contract();
    test_incremental_knowledge_projection();
    return 0;
}
