from __future__ import annotations


def normalize_youtube_json3(
    payload: object,
    *,
    maximum_end_ms: int | None = None,
) -> dict[str, list[dict[str, int | str]]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("YouTube JSON3 must contain an events array")
    content_events: list[tuple[int, int, str]] = []
    for event in payload["events"]:
        if not isinstance(event, dict):
            raise ValueError("YouTube JSON3 events must be objects")
        segments = event.get("segs")
        start_ms = event.get("tStartMs")
        if not isinstance(segments, list) or not isinstance(start_ms, int):
            continue
        text_parts: list[str] = []
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(segment.get("utf8"), str):
                raise ValueError("YouTube JSON3 caption segments must contain utf8 text")
            text_parts.append(segment["utf8"])
        text = " ".join("".join(text_parts).split())
        if not text:
            continue
        duration_ms = event.get("dDurationMs")
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            duration_ms = 1
        content_events.append((start_ms, start_ms + duration_ms, text))

    normalized: list[dict[str, int | str]] = []
    for index, (start_ms, indicated_end_ms, text) in enumerate(content_events):
        if maximum_end_ms is not None and start_ms >= maximum_end_ms:
            break
        next_start_ms = (
            content_events[index + 1][0] if index + 1 < len(content_events) else indicated_end_ms
        )
        end_ms = min(indicated_end_ms, next_start_ms)
        if maximum_end_ms is not None:
            end_ms = min(end_ms, maximum_end_ms)
        if end_ms <= start_ms:
            continue
        normalized.append({"start_ms": start_ms, "end_ms": end_ms, "text": text})
    if not normalized:
        raise ValueError("YouTube JSON3 contains no usable caption events")
    return {"segments": normalized}
