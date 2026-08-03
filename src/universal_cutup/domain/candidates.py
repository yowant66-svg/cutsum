from __future__ import annotations

from pydantic import Field, model_validator

from .common import SHA256_PATTERN, FrozenModel
from .education import (
    EducationalCandidateProfile,
    EducationSignal,
    EducationVisualDependency,
)
from .intelligence import SemanticType
from .sports import SportsCandidateProfile, SportsEvent
from .subtitles import (
    ContextualTranslationRecord,
    SubtitleDisplayUnit,
    SubtitleSemanticSpan,
    SubtitleWordTiming,
)
from .transcript import SubtitleCue


class EvidenceRef(FrozenModel):
    evidence_id: str
    artifact_id: str
    segment_ids: tuple[str, ...] = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text_sha256: str = Field(pattern=SHA256_PATTERN)
    snapshot: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_range(self) -> EvidenceRef:
        if self.end_ms <= self.start_ms:
            raise ValueError("evidence end_ms must be greater than start_ms")
        return self


class EvidenceArtifactIdentity(FrozenModel):
    artifact_id: str
    source_id: str
    segment_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_segment_ids(self) -> EvidenceArtifactIdentity:
        if len(self.segment_ids) != len(set(self.segment_ids)):
            raise ValueError("evidence artifact segment IDs must be unique")
        return self


class DimensionScore(FrozenModel):
    dimension_id: str
    value: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: tuple[str, ...] = ()
    warning: str | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> DimensionScore:
        if self.value is not None and not self.evidence_refs:
            raise ValueError("non-null scores require evidence_refs")
        return self


class StrategyScore(FrozenModel):
    strategy_id: str
    strategy_version: str
    strategy_record_ref: str | None = None
    dimensions: tuple[DimensionScore, ...] = ()
    aggregate: float | None = Field(default=None, ge=0, le=1)
    warnings: tuple[str, ...] = ()


class CutCandidate(FrozenModel):
    candidate_id: str
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    summary: str
    evidence_refs: tuple[EvidenceRef, ...] = Field(min_length=1)
    subtitle_cues: tuple[SubtitleCue, ...] = ()
    translated_subtitle_cues: tuple[SubtitleCue, ...] = ()
    subtitle_word_timings: tuple[SubtitleWordTiming, ...] = ()
    subtitle_semantic_spans: tuple[SubtitleSemanticSpan, ...] = ()
    subtitle_display_units: tuple[SubtitleDisplayUnit, ...] = ()
    contextual_translation_records: tuple[ContextualTranslationRecord, ...] = ()
    education_signals: tuple[EducationSignal, ...] = ()
    education_visual_dependencies: tuple[EducationVisualDependency, ...] = ()
    educational_profile: EducationalCandidateProfile | None = None
    sports_event: SportsEvent | None = None
    sports_profile: SportsCandidateProfile | None = None
    strategy_scores: tuple[StrategyScore, ...] = ()
    tags: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    semantic_types: tuple[SemanticType, ...] = ()
    semantic_structure: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    speakers: tuple[str, ...] = ()
    extension_reason: str | None = None
    series_group_id: str | None = None
    series_index: int | None = Field(default=None, ge=1)
    series_total: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_range(self) -> CutCandidate:
        if self.end_ms <= self.start_ms:
            raise ValueError("candidate end_ms must be greater than start_ms")
        cue_ids = [cue.cue_id for cue in self.subtitle_cues]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("subtitle cue IDs must be unique within a candidate")
        for cue in self.subtitle_cues:
            if cue.source_id != self.source_id:
                raise ValueError("subtitle cue source_id must match candidate source_id")
            if cue.end_ms <= self.start_ms or cue.start_ms >= self.end_ms:
                raise ValueError("subtitle cue must overlap the candidate time range")
        translated_cue_ids = [cue.cue_id for cue in self.translated_subtitle_cues]
        if len(translated_cue_ids) != len(set(translated_cue_ids)):
            raise ValueError("translated subtitle cue IDs must be unique within a candidate")
        for cue in self.translated_subtitle_cues:
            if cue.source_id != self.source_id:
                raise ValueError("translated subtitle cue source_id must match candidate source_id")
            if cue.end_ms <= self.start_ms or cue.start_ms >= self.end_ms:
                raise ValueError("translated subtitle cue must overlap the candidate time range")
        source_cues_by_id = {cue.cue_id: cue for cue in self.subtitle_cues}
        source_cue_ids = set(source_cues_by_id)
        word_timing_ids = [timing.word_timing_id for timing in self.subtitle_word_timings]
        if len(word_timing_ids) != len(set(word_timing_ids)):
            raise ValueError("subtitle word timing IDs must be unique")
        for timing in self.subtitle_word_timings:
            if timing.source_id != self.source_id:
                raise ValueError("subtitle word timing source_id must match candidate source_id")
            if not set(timing.source_cue_ids) <= source_cue_ids:
                raise ValueError("subtitle word timing references an unknown source cue")
            covered_cues = tuple(source_cues_by_id[cue_id] for cue_id in timing.source_cue_ids)
            if timing.start_ms < min(cue.start_ms for cue in covered_cues) or timing.end_ms > max(
                cue.end_ms for cue in covered_cues
            ):
                raise ValueError("word timing must stay within covered source cues")
        semantic_span_ids = [span.semantic_span_id for span in self.subtitle_semantic_spans]
        if len(semantic_span_ids) != len(set(semantic_span_ids)):
            raise ValueError("subtitle semantic span IDs must be unique")
        previous_semantic_start = self.start_ms
        for span in self.subtitle_semantic_spans:
            if span.source_id != self.source_id:
                raise ValueError("subtitle semantic span source_id must match candidate source_id")
            if not set(span.source_cue_ids) <= source_cue_ids:
                raise ValueError("subtitle semantic span references an unknown source cue")
            covered_cues = tuple(source_cues_by_id[cue_id] for cue_id in span.source_cue_ids)
            if span.start_ms < min(cue.start_ms for cue in covered_cues) or span.end_ms > max(
                cue.end_ms for cue in covered_cues
            ):
                raise ValueError("semantic span must stay within covered source cues")
            if span.start_ms < previous_semantic_start:
                raise ValueError("subtitle semantic spans must be ordered by start_ms")
            previous_semantic_start = span.start_ms
        translation_records_by_id = {
            record.translation_record_id: record for record in self.contextual_translation_records
        }
        translation_record_ids = set(translation_records_by_id)
        if len(translation_record_ids) != len(self.contextual_translation_records):
            raise ValueError("contextual translation record IDs must be unique")
        display_unit_ids = [unit.display_unit_id for unit in self.subtitle_display_units]
        if len(display_unit_ids) != len(set(display_unit_ids)):
            raise ValueError("subtitle display unit IDs must be unique")
        previous_display_start = self.start_ms
        for unit in self.subtitle_display_units:
            if unit.source_id != self.source_id:
                raise ValueError("subtitle display unit source_id must match candidate source_id")
            if unit.end_ms <= self.start_ms or unit.start_ms >= self.end_ms:
                raise ValueError("subtitle display unit must overlap candidate time range")
            if not set(unit.source_cue_ids) <= source_cue_ids:
                raise ValueError("subtitle display unit references an unknown source cue")
            if unit.translation_record_ref not in translation_record_ids:
                raise ValueError("subtitle display unit references an unknown translation record")
            covered_cues = tuple(source_cues_by_id[cue_id] for cue_id in unit.source_cue_ids)
            if unit.start_ms != min(cue.start_ms for cue in covered_cues):
                raise ValueError("subtitle display unit start_ms must derive from covered cues")
            if unit.end_ms != max(cue.end_ms for cue in covered_cues):
                raise ValueError("subtitle display unit end_ms must derive from covered cues")
            covered_text = " ".join(cue.text.strip() for cue in covered_cues)
            if unit.source_text != covered_text:
                raise ValueError("subtitle display unit source_text must preserve covered cues")
            translation_record = translation_records_by_id[unit.translation_record_ref]
            if unit.translated_text != translation_record.translated_text:
                raise ValueError("subtitle display unit translation must match its record")
            if unit.start_ms < previous_display_start:
                raise ValueError("subtitle display units must be ordered by start_ms")
            previous_display_start = unit.start_ms
        for record in self.contextual_translation_records:
            if not set(record.source_cue_ids) <= source_cue_ids:
                raise ValueError("translation record references an unknown source cue")
            covered_text = " ".join(
                source_cues_by_id[cue_id].text.strip() for cue_id in record.source_cue_ids
            )
            if record.source_text != covered_text:
                raise ValueError("translation record source_text must preserve source cues")
        evidence_ids = {evidence.evidence_id for evidence in self.evidence_refs}
        for signal in self.education_signals:
            if not set(signal.evidence_refs) <= evidence_ids:
                raise ValueError("education signal references unknown candidate evidence")
            if signal.end_ms <= self.start_ms or signal.start_ms >= self.end_ms:
                raise ValueError("education signal must overlap candidate time range")
        for dependency in self.education_visual_dependencies:
            if not set(dependency.evidence_refs) <= evidence_ids:
                raise ValueError(
                    "education visual dependency references unknown candidate evidence"
                )
            if dependency.end_ms <= self.start_ms or dependency.start_ms >= self.end_ms:
                raise ValueError("education visual dependency must overlap candidate time range")
        if (
            self.educational_profile is not None
            and self.educational_profile.candidate_id != self.candidate_id
        ):
            raise ValueError("educational profile candidate_id must match candidate")
        if self.sports_event is not None:
            if self.sports_event.source_id != self.source_id:
                raise ValueError("sports event source_id must match candidate")
            if (
                self.sports_event.end_ms <= self.start_ms
                or self.sports_event.start_ms >= self.end_ms
            ):
                raise ValueError("sports event must overlap candidate time range")
        if self.sports_profile is not None:
            if self.sports_profile.candidate_id != self.candidate_id:
                raise ValueError("sports profile candidate_id must match candidate")
            if self.sports_event is None:
                raise ValueError("sports profile requires a sports event")
            if self.sports_profile.event_id != self.sports_event.event_id:
                raise ValueError("sports profile event_id must match sports event")
        series_values = (self.series_group_id, self.series_index, self.series_total)
        if any(value is not None for value in series_values) and not all(
            value is not None for value in series_values
        ):
            raise ValueError("series_group_id, series_index, and series_total must be set together")
        if (
            self.series_index is not None
            and self.series_total is not None
            and self.series_index > self.series_total
        ):
            raise ValueError("series_index cannot exceed series_total")
        return self
