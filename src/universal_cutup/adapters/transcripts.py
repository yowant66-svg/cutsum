from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from universal_cutup.domain.transcript import TranscriptArtifact, TranscriptSegment

TIMESTAMP_PATTERN = re.compile(
    r"^(?:(?P<hours>\d{2,}):)?(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d)"
    r"(?P<fraction>[.,]\d{3})$"
)
VTT_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class TranscriptParseContext:
    transcript_id: str
    source_id: str
    created_at: datetime
    created_by: str
    language: str | None = None


@dataclass(frozen=True, slots=True)
class RawTranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    cue_identifier: str | None = None
    speaker: str | None = None
    confidence: float | None = None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp_ms(value: str) -> int:
    matched = TIMESTAMP_PATTERN.fullmatch(value.strip())
    if matched is None:
        raise ValueError(f"invalid transcript timestamp: {value!r}")
    fraction_ms = int(matched.group("fraction")[1:])
    return (
        int(matched.group("hours") or 0) * 3_600_000
        + int(matched.group("minutes")) * 60_000
        + int(matched.group("seconds")) * 1000
        + fraction_ms
    )


def _normalize_text(lines: list[str]) -> str:
    joined = "\n".join(line.strip() for line in lines).strip()
    without_tags = VTT_TAG_PATTERN.sub("", joined)
    normalized = html.unescape(without_tags).strip()
    if not normalized:
        raise ValueError("transcript segment text cannot be empty")
    return normalized


def _artifact(
    raw_segments: list[RawTranscriptSegment],
    *,
    context: TranscriptParseContext,
) -> TranscriptArtifact:
    segments: list[TranscriptSegment] = []
    for index, raw_segment in enumerate(raw_segments, start=1):
        text_sha256 = _sha256_text(raw_segment.text)
        segments.append(
            TranscriptSegment(
                segment_id=f"segment-{index:04d}-{text_sha256[:8]}",
                source_id=context.source_id,
                start_ms=raw_segment.start_ms,
                end_ms=raw_segment.end_ms,
                text=raw_segment.text,
                text_sha256=text_sha256,
                cue_identifier=raw_segment.cue_identifier,
                speaker=raw_segment.speaker,
                confidence=raw_segment.confidence,
            )
        )
    return TranscriptArtifact(
        document_type="transcript",
        created_at=context.created_at,
        created_by=context.created_by,
        transcript_id=context.transcript_id,
        source_id=context.source_id,
        language=context.language,
        segments=tuple(segments),
    )


def _parse_caption_blocks(
    content: str,
    *,
    allow_numeric_index: bool,
) -> list[RawTranscriptSegment]:
    normalized = content.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = re.split(r"\n{2,}", normalized)
    raw_segments: list[RawTranscriptSegment] = []
    for block in blocks:
        lines = block.splitlines()
        if not lines or lines[0].strip() == "WEBVTT":
            continue
        if lines[0].strip().upper().startswith(("NOTE", "STYLE", "REGION")):
            continue
        cue_identifier: str | None = None
        if allow_numeric_index and lines[0].strip().isdigit():
            lines = lines[1:]
        elif "-->" not in lines[0] and len(lines) > 1 and "-->" in lines[1]:
            cue_identifier = lines[0].strip()
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_text, end_part = lines[0].split("-->", maxsplit=1)
        end_text = end_part.strip().split(maxsplit=1)[0]
        raw_segments.append(
            RawTranscriptSegment(
                start_ms=_timestamp_ms(start_text),
                end_ms=_timestamp_ms(end_text),
                text=_normalize_text(lines[1:]),
                cue_identifier=cue_identifier,
            )
        )
    if not raw_segments:
        raise ValueError("no transcript segments found")
    return raw_segments


def parse_srt(content: str, *, context: TranscriptParseContext) -> TranscriptArtifact:
    return _artifact(
        _parse_caption_blocks(content, allow_numeric_index=True),
        context=context,
    )


def parse_vtt(content: str, *, context: TranscriptParseContext) -> TranscriptArtifact:
    return _artifact(
        _parse_caption_blocks(content, allow_numeric_index=False),
        context=context,
    )


def parse_json_transcript(
    content: str,
    *,
    context: TranscriptParseContext,
) -> TranscriptArtifact:
    parsed: Any = json.loads(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("segments"), list):
        raise ValueError("JSON transcript must contain a segments array")
    raw_segments: list[RawTranscriptSegment] = []
    for raw_segment in parsed["segments"]:
        if not isinstance(raw_segment, dict):
            raise ValueError("each JSON transcript segment must be an object")
        start_ms = raw_segment.get("start_ms")
        end_ms = raw_segment.get("end_ms")
        text = raw_segment.get("text")
        if not isinstance(start_ms, int) or not isinstance(end_ms, int):
            raise ValueError("JSON transcript timestamps must be integer milliseconds")
        if not isinstance(text, str):
            raise ValueError("JSON transcript text must be a string")
        speaker = raw_segment.get("speaker")
        confidence = raw_segment.get("confidence")
        if speaker is not None and not isinstance(speaker, str):
            raise ValueError("JSON transcript speaker must be a string or null")
        if confidence is not None and not isinstance(confidence, (int, float)):
            raise ValueError("JSON transcript confidence must be numeric or null")
        raw_segments.append(
            RawTranscriptSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                text=_normalize_text([text]),
                speaker=speaker,
                confidence=float(confidence) if confidence is not None else None,
            )
        )
    return _artifact(raw_segments, context=context)
