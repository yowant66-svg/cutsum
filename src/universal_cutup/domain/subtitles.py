from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import Field, model_validator

from .common import SHA256_PATTERN, FrozenModel

ISOLATED_CHINESE_FUNCTION_WORDS = frozenset(
    {"的", "了", "是", "在", "和", "与", "因", "此", "而", "或", "也", "就", "都"}
)


class SubtitleTimingPrecision(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"


class SubtitleSemanticLevel(StrEnum):
    SENTENCE = "sentence"
    CLAUSE = "clause"
    PHRASE = "phrase"


class SubtitleReadabilityCode(StrEnum):
    CHARACTERS_PER_SECOND = "characters_per_second"
    VISUAL_LINE_LIMIT = "visual_line_limit"
    SEMANTIC_FRAGMENT = "semantic_fragment"


def subtitle_text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ContextualTranslationRecord(FrozenModel):
    translation_record_id: str
    provider_record_ref: str
    source_language: str
    translation_language: str
    source_cue_ids: tuple[str, ...] = Field(min_length=1)
    source_text: str = Field(min_length=1)
    preceding_context: str = ""
    following_context: str = ""
    translated_text: str = Field(min_length=1)
    glossary: dict[str, str] = Field(default_factory=dict)
    source_text_sha256: str = Field(pattern=SHA256_PATTERN)
    translation_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_identity(self) -> ContextualTranslationRecord:
        if len(self.source_cue_ids) != len(set(self.source_cue_ids)):
            raise ValueError("translation source cue IDs must be unique")
        if self.source_text_sha256 != subtitle_text_sha256(self.source_text):
            raise ValueError("source_text_sha256 does not match source_text")
        if self.translation_sha256 != subtitle_text_sha256(self.translated_text):
            raise ValueError("translation_sha256 does not match translated_text")
        return self


class SubtitleDisplayUnit(FrozenModel):
    display_unit_id: str
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    source_cue_ids: tuple[str, ...] = Field(min_length=1)
    source_text: str = Field(min_length=1)
    translated_text: str = Field(min_length=1)
    source_language: str
    translation_language: str
    semantic_level: SubtitleSemanticLevel = SubtitleSemanticLevel.SENTENCE
    timing_precision: SubtitleTimingPrecision = SubtitleTimingPrecision.EXACT
    segmentation_reason: str
    translation_record_ref: str

    @model_validator(mode="after")
    def validate_display_unit(self) -> SubtitleDisplayUnit:
        if self.end_ms <= self.start_ms:
            raise ValueError("display unit end_ms must be greater than start_ms")
        if len(self.source_cue_ids) != len(set(self.source_cue_ids)):
            raise ValueError("display unit source cue IDs must be unique")
        if self.translated_text.strip() in ISOLATED_CHINESE_FUNCTION_WORDS:
            raise ValueError("translated display unit cannot be an isolated function word")
        return self


class SubtitleWordTiming(FrozenModel):
    word_timing_id: str
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)
    source_cue_ids: tuple[str, ...] = Field(min_length=1)
    timing_precision: SubtitleTimingPrecision

    @model_validator(mode="after")
    def validate_word_timing(self) -> SubtitleWordTiming:
        if self.end_ms <= self.start_ms:
            raise ValueError("word timing end_ms must be greater than start_ms")
        if len(self.source_cue_ids) != len(set(self.source_cue_ids)):
            raise ValueError("word timing source cue IDs must be unique")
        return self


class SubtitleSemanticSpan(FrozenModel):
    semantic_span_id: str
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    source_cue_ids: tuple[str, ...] = Field(min_length=1)
    text: str = Field(min_length=1)
    language: str
    semantic_level: SubtitleSemanticLevel
    timing_precision: SubtitleTimingPrecision

    @model_validator(mode="after")
    def validate_semantic_span(self) -> SubtitleSemanticSpan:
        if self.end_ms <= self.start_ms:
            raise ValueError("semantic span end_ms must be greater than start_ms")
        if len(self.source_cue_ids) != len(set(self.source_cue_ids)):
            raise ValueError("semantic span source cue IDs must be unique")
        if self.text.strip() in ISOLATED_CHINESE_FUNCTION_WORDS:
            raise ValueError("semantic span cannot be an isolated function word")
        return self


class SubtitleReadabilityFinding(FrozenModel):
    finding_id: str
    code: SubtitleReadabilityCode
    display_unit_id: str
    language: str
    observed: float = Field(ge=0)
    limit: float = Field(gt=0)


class SubtitleReadabilityReport(FrozenModel):
    passed: bool
    unit_count: int = Field(ge=0)
    maximum_characters_per_second: float = Field(ge=0)
    findings: tuple[SubtitleReadabilityFinding, ...] = ()

    @model_validator(mode="after")
    def validate_result(self) -> SubtitleReadabilityReport:
        if self.passed == bool(self.findings):
            raise ValueError("readability passed must be true exactly when findings are empty")
        return self
