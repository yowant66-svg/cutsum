from __future__ import annotations

from pydantic import Field, model_validator

from .common import SHA256_PATTERN, DocumentHeader, FrozenModel


class TranscriptSegment(FrozenModel):
    segment_id: str
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=SHA256_PATTERN)
    cue_identifier: str | None = None
    speaker: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_range(self) -> TranscriptSegment:
        if self.end_ms <= self.start_ms:
            raise ValueError("segment end_ms must be greater than start_ms")
        return self


class SubtitleCue(FrozenModel):
    cue_id: str
    source_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)
    language: str | None = None
    speaker: str | None = None
    source_segment_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> SubtitleCue:
        if self.end_ms <= self.start_ms:
            raise ValueError("subtitle cue end_ms must be greater than start_ms")
        return self


class TranscriptArtifact(DocumentHeader):
    transcript_id: str
    source_id: str
    language: str | None = None
    segments: tuple[TranscriptSegment, ...]

    @model_validator(mode="after")
    def validate_segments(self) -> TranscriptArtifact:
        previous_start = 0
        seen_ids: set[str] = set()
        for segment in self.segments:
            if segment.source_id != self.source_id:
                raise ValueError("all segments must reference transcript source_id")
            if segment.segment_id in seen_ids:
                raise ValueError("segment IDs must be unique")
            if segment.start_ms < previous_start:
                raise ValueError("segments must be ordered by non-decreasing start_ms")
            previous_start = segment.start_ms
            seen_ids.add(segment.segment_id)
        return self
