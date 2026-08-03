"""Fail-closed direct-claim learning for private alias memory."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import cast

from simo.context import ContextMemoryClaim, MemoryRefreshStats, NativeContextEngine
from simo.persistence import ConversationEvent, SimoStore

MAX_LEARNED_VALUE_CHARS = 240
_PROHIBITED = re.compile(
    r"\b(?:password|passcode|api[ -]?key|secret|access[ -]?token|credential|"
    r"social security|ssn|credit card|bank account|grant permission|authorize|"
    r"administrator|sudo|disable safety|ignore (?:prior|previous|hidden) instructions)\b",
    re.IGNORECASE,
)


class LearningStatus(StrEnum):
    PROMOTED = "promoted"
    DEDUPLICATED = "deduplicated"
    REJECTED = "rejected"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class LearningDecision:
    status: LearningStatus
    reason: str
    claim_id: str | None = None
    claim_class: str | None = None

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class _Candidate:
    claim_key: str
    claim_class: str
    content: str
    confidence: float
    contradiction: bool = False


class SafeMemoryLearner:
    """Promote only narrow first-person claims from final attributed turns."""

    def __init__(self, store: SimoStore) -> None:
        self._store = store

    def learn_event(
        self,
        owner_alias_id: str,
        subject_id: str,
        event: ConversationEvent,
        *,
        subject_alias_id: str | None = None,
    ) -> LearningDecision:
        if event.text is None or event.participant_id != subject_id:
            return LearningDecision(LearningStatus.REJECTED, "event attribution mismatch")
        if event.event_type != "user.transcript.final":
            return LearningDecision(LearningStatus.REJECTED, "event is not a final transcript")
        return self.learn_text(
            owner_alias_id,
            subject_id,
            event.text,
            conversation_id=event.conversation_id,
            event_id=event.event_id,
            subject_alias_id=subject_alias_id,
        )

    def learn_text(
        self,
        owner_alias_id: str,
        subject_id: str,
        text: str,
        *,
        conversation_id: str,
        event_id: str,
        subject_alias_id: str | None = None,
    ) -> LearningDecision:
        selected = text.strip()
        if not selected:
            return LearningDecision(LearningStatus.IGNORED, "empty transcript")
        if _PROHIBITED.search(selected):
            return LearningDecision(
                LearningStatus.REJECTED,
                "prohibited credential, permission, or policy class",
            )
        candidate = _extract_candidate(selected)
        if candidate is None:
            return LearningDecision(
                LearningStatus.IGNORED,
                "no allow-listed direct claim pattern",
            )
        if len(candidate.content) > MAX_LEARNED_VALUE_CHARS:
            return LearningDecision(LearningStatus.REJECTED, "claim exceeds the learning bound")
        existing = next(
            (
                claim
                for claim in self._store.list_memory_claims(
                    owner_alias_id,
                    subject_id=subject_id,
                    status="active",
                )
                if claim.claim_key == candidate.claim_key
            ),
            None,
        )
        claim = self._store.promote_memory_claim(
            owner_alias_id,
            subject_id,
            candidate.claim_key,
            candidate.claim_class,
            candidate.content,
            source_conversation_id=conversation_id,
            source_event_id=event_id,
            subject_alias_id=subject_alias_id,
            confidence=candidate.confidence,
            contradiction=candidate.contradiction,
        )
        status = (
            LearningStatus.DEDUPLICATED
            if existing is not None and existing.claim_id == claim.claim_id
            else LearningStatus.PROMOTED
        )
        return LearningDecision(status, "safe direct claim", claim.claim_id, claim.claim_class)


def refresh_memory_graph(
    engine: NativeContextEngine,
    store: SimoStore,
    owner_alias_id: str,
    participant_ids: set[str],
) -> MemoryRefreshStats:
    """Replace the world's active relationship-memory projection."""

    engine.begin_memory_refresh()
    for claim in store.list_memory_claims(owner_alias_id, status="active"):
        if claim.subject_id not in participant_ids:
            continue
        engine.upsert_memory_claim(
            ContextMemoryClaim(
                claim.claim_id,
                claim.subject_id,
                claim.claim_key,
                claim.claim_class,
                claim.content,
                claim.source_conversation_id or "",
                claim.source_event_id or "",
                claim.stale_after or "",
                claim.confidence,
            )
        )
    return engine.commit_memory_refresh()


def _extract_candidate(text: str) -> _Candidate | None:
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"^my name is (?P<value>.+?)[.!?]*$", re.IGNORECASE), "name"),
        (
            re.compile(r"^i no longer (?:like|love|enjoy) (?P<value>.+?)[.!?]*$", re.IGNORECASE),
            "unlike",
        ),
        (re.compile(r"^i (?:like|love|enjoy) (?P<value>.+?)[.!?]*$", re.IGNORECASE), "like"),
        (
            re.compile(
                r"^my favorite (?P<category>.+?) is (?P<value>.+?)[.!?]*$",
                re.IGNORECASE,
            ),
            "favorite",
        ),
        (re.compile(r"^my goal is (?P<value>.+?)[.!?]*$", re.IGNORECASE), "goal"),
        (
            re.compile(r"^i(?: am|'m) interested in (?P<value>.+?)[.!?]*$", re.IGNORECASE),
            "interest",
        ),
        (re.compile(r"^i will (?P<value>.+?)[.!?]*$", re.IGNORECASE), "commitment"),
    )
    for pattern, kind in patterns:
        match = pattern.fullmatch(text)
        if match is None:
            continue
        value = _clean_value(match.group("value"))
        if not value:
            return None
        if kind == "name":
            return _Candidate("identity.name", "identity", f"Name is {value}.", 0.99)
        if kind == "like":
            return _Candidate(
                f"preference.like:{_key_fragment(value)}",
                "preference",
                f"Likes {value}.",
                0.97,
            )
        if kind == "unlike":
            return _Candidate(
                f"preference.like:{_key_fragment(value)}",
                "preference",
                f"No longer likes {value}.",
                0.99,
                True,
            )
        if kind == "favorite":
            category = _clean_value(match.group("category"))
            if not category:
                return None
            return _Candidate(
                f"preference.favorite:{_key_fragment(category)}",
                "preference",
                f"Favorite {category} is {value}.",
                0.97,
            )
        if kind == "goal":
            return _Candidate("goal.current", "goal", f"Goal: {value}.", 0.95)
        if kind == "interest":
            return _Candidate(
                f"interest:{_key_fragment(value)}",
                "interest",
                f"Interested in {value}.",
                0.95,
            )
        return _Candidate(
            f"commitment:{_key_fragment(value)}",
            "commitment",
            f"Committed to {value}.",
            0.95,
        )
    return None


def _clean_value(value: str) -> str:
    return " ".join(value.strip(" \t\r\n.!?").split())


def _key_fragment(value: str) -> str:
    selected = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return selected[:96] or "value"
