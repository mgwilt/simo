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

struct ContextSnapshot {
    std::uint64_t revision{0};
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
    [[nodiscard]] std::size_t tick();
    [[nodiscard]] std::shared_ptr<const ContextSnapshot> snapshot() const;
    [[nodiscard]] EngineStats stats() const;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace simo
