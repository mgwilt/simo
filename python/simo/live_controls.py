"""Bounded operator overrides for one LAN process, never immutable alias versions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import cast

VOICE_RESPONSE_GUIDANCE = (
    "Speak naturally in complete sentences. Match the detail and length the user requests; "
    "when asked for a longer answer, develop the explanation with examples. "
    "Do not impose a two-sentence limit. Avoid markdown and stage directions in spoken replies."
)


@dataclass(frozen=True, slots=True)
class ConversationSettings:
    prompt: str
    voice_instruction: str
    max_tokens: int
    revision: int = 0

    def __post_init__(self) -> None:
        for name, value, limit in (
            ("prompt", self.prompt, 8_000),
            ("voice_instruction", self.voice_instruction, 2_000),
        ):
            if not value.strip() or len(value) > limit:
                raise ValueError(f"{name} must contain 1 to {limit} characters")
        if type(self.max_tokens) is not int or not 64 <= self.max_tokens <= 2_048:
            raise ValueError("max_tokens must be an integer between 64 and 2048")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a nonnegative integer")

    @property
    def instructions(self) -> str:
        return f"{VOICE_RESPONSE_GUIDANCE}\n\n{self.prompt.strip()}"

    def as_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


class StaleSettingsError(ValueError):
    """Another operator tab applied a newer revision."""


class LiveConversationControls:
    """Event-loop-owned atomic settings; each inference job takes a frozen snapshot."""

    def __init__(self, settings: ConversationSettings, *, voice_editable: bool = True) -> None:
        self._settings = settings
        self.voice_editable = voice_editable

    def snapshot(self) -> ConversationSettings:
        return self._settings

    def update(self, payload: dict[str, object]) -> ConversationSettings:
        if set(payload) != {"prompt", "voice_instruction", "max_tokens", "revision"}:
            raise ValueError("Provide only prompt, voice_instruction, max_tokens and revision")
        prompt, voice = payload["prompt"], payload["voice_instruction"]
        budget, revision = payload["max_tokens"], payload["revision"]
        if not isinstance(prompt, str) or not isinstance(voice, str):
            raise TypeError("Prompt and voice instruction must be text")
        if type(budget) is not int or type(revision) is not int:
            raise ValueError("Token budget and revision must be integers")
        candidate = ConversationSettings(prompt.strip(), voice.strip(), budget, revision)
        if candidate.revision != self._settings.revision:
            raise StaleSettingsError(
                "Settings changed in another tab; reload settings and try again"
            )
        if (
            not self.voice_editable
            and candidate.voice_instruction != self._settings.voice_instruction
        ):
            raise ValueError("Voice instructions require the Breeze backend")
        if candidate != self._settings:
            self._settings = replace(candidate, revision=candidate.revision + 1)
        return self._settings
