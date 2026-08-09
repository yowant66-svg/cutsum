from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from universal_cutup.adapters.transcripts import (
    TranscriptParseContext,
    parse_json_transcript,
    parse_srt,
    parse_vtt,
)
from universal_cutup.domain.candidates import CutCandidate
from universal_cutup.domain.education import EducationalSelectionResult, EducationalTaskRequest
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.execution import ExecutionRecord
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.sources import MediaBinding, MediaSource, RightsAttestation
from universal_cutup.domain.specs import (
    OutputSpec,
    ReframeSpec,
    RenderSpec,
    SubtitleSafeAreaPreset,
    SubtitleSafeAreaSpec,
)
from universal_cutup.domain.sports import (
    SportsObservationBundle,
    SportsSelectionResult,
    SportsTaskRequest,
)
from universal_cutup.domain.transcript import TranscriptArtifact
from universal_cutup.media.capabilities import (
    MediaRuntimeCapabilities,
    SubtitleBackendCapabilities,
    detect_media_runtime_capabilities,
    detect_subtitle_capabilities,
)
from universal_cutup.media.executor import execute_external_plan
from universal_cutup.media.probe import probe_media
from universal_cutup.providers.sports import (
    FileSportsObservationProvider,
    ImportedSportsObservations,
    SportsFileProviderKind,
)
from universal_cutup.providers.sports_text import (
    DetectedSportsObservations,
    LocalSportsTextProvider,
    SportsTextProfile,
)
from universal_cutup.strategies.educational import (
    attach_education_signals,
    extract_education_signals,
    qualify_educational_candidate,
    select_educational_candidates,
)

from .educational import (
    build_educational_plan,
    create_educational_plan,
    prepare_educational_candidate,
    prepare_educational_duration,
    propose_educational_candidates,
    resolve_educational_request,
    select_educational_for_request,
)
from .intelligence import (
    aggregate_intelligence,
    create_adaptive_plan,
    resolve_intelligence_task,
    select_intelligence,
    validate_intelligence_document,
)
from .services import ApplicationContext, transcript_to_plan
from .sports import (
    build_sports_plan,
    create_sports_plan,
    propose_sports_candidates,
    resolve_sports_request,
    select_sports_for_request,
)
from .subtitle_display import (
    materialize_display_units,
    semantic_source_groups,
    semantic_source_spans,
)
from .subtitle_readability import assess_subtitle_readability

__all__ = [
    "DEFAULT_MAX_FULL_CLIPS",
    "CapabilityReport",
    "CapabilityState",
    "DetectedSportsObservations",
    "EducationalPlanningResult",
    "FullOfflineResult",
    "OperationCapability",
    "SourceInspection",
    "SportsPlanningResult",
    "SportsTextProfile",
    "SportsTranscriptPlanningResult",
    "TranscriptAnalysis",
    "aggregate_intelligence",
    "analyze_transcript",
    "assess_subtitle_readability",
    "attach_education_signals",
    "capability_report",
    "configure_reframe",
    "create_adaptive_plan",
    "create_educational_plan",
    "create_plan",
    "create_sports_plan",
    "detect_sports_transcript",
    "execute_cut_plan",
    "extract_education_signals",
    "inspect_source",
    "load_cut_plan",
    "load_sports_observations",
    "load_transcript",
    "materialize_display_units",
    "plan_educational_content",
    "plan_sports_content",
    "plan_sports_transcript",
    "prepare_educational_candidate",
    "prepare_educational_duration",
    "process_subtitles",
    "propose_candidates",
    "propose_educational_candidates",
    "propose_sports_candidates",
    "qualify_educational_candidate",
    "require_operation",
    "require_reframe_mode",
    "resolve_educational_request",
    "resolve_intelligence_task",
    "resolve_sports_request",
    "run_full_offline",
    "score_candidates",
    "select_educational_candidates",
    "select_educational_for_request",
    "select_intelligence",
    "select_sports_for_request",
    "semantic_source_groups",
    "semantic_source_spans",
    "subtitle_capabilities",
    "validate_intelligence_document",
]

DEFAULT_MAX_FULL_CLIPS = 24


class SdkResult(BaseModel):
    model_config = ConfigDict(frozen=True)


class SourceInspection(SdkResult):
    source: MediaSource
    binding: MediaBinding
    has_video: bool
    has_audio: bool


class TranscriptAnalysis(SdkResult):
    transcript_id: str
    source_id: str
    segment_count: int
    duration_ms: int
    character_count: int


class FullOfflineResult(SdkResult):
    inspection: SourceInspection
    analysis: TranscriptAnalysis
    plan: CutPlan
    execution: ExecutionRecord


class EducationalPlanningResult(SdkResult):
    request: EducationalTaskRequest
    candidates: tuple[CutCandidate, ...]
    selection: EducationalSelectionResult
    plan: CutPlan


class SportsPlanningResult(SdkResult):
    request: SportsTaskRequest
    candidates: tuple[CutCandidate, ...]
    selection: SportsSelectionResult
    plan: CutPlan


class SportsTranscriptPlanningResult(SportsPlanningResult):
    observations: SportsObservationBundle
    provider_record: ProviderRecord


class CapabilityState(StrEnum):
    AVAILABLE = "available"
    PROVIDER_REQUIRED = "provider_required"
    UNAVAILABLE = "unavailable"


class OperationCapability(SdkResult):
    operation: str
    state: CapabilityState
    error_code: ErrorCode | None = None
    message: str
    available_modes: tuple[str, ...] = ()
    unavailable_modes: tuple[str, ...] = ()


class CapabilityReport(SdkResult):
    operations: tuple[OperationCapability, ...]
    media_runtime: MediaRuntimeCapabilities
    subtitle_backend: SubtitleBackendCapabilities


def subtitle_capabilities() -> SubtitleBackendCapabilities:
    return detect_subtitle_capabilities()


def _operation_capabilities() -> tuple[OperationCapability, ...]:
    available = (
        "inspect",
        "analyze",
        "propose",
        "score",
        "plan",
        "cut",
        "subtitle",
        "education_plan",
        "sports_plan",
        "sports_transcript_plan",
        "intelligence",
    )
    return (
        *(
            OperationCapability(
                operation=operation,
                state=CapabilityState.AVAILABLE,
                message="available offline",
            )
            for operation in available
        ),
        OperationCapability(
            operation="transcribe",
            state=CapabilityState.PROVIDER_REQUIRED,
            error_code=ErrorCode.PROVIDER_REQUIRED,
            message="transcribe requires a configured provider",
        ),
        OperationCapability(
            operation="translate",
            state=CapabilityState.PROVIDER_REQUIRED,
            error_code=ErrorCode.PROVIDER_REQUIRED,
            message="translate requires a configured provider",
        ),
        OperationCapability(
            operation="reframe",
            state=CapabilityState.AVAILABLE,
            message="basic deterministic 9:16 reframing is available offline",
            available_modes=(
                "none",
                "center_crop",
                "manual_focus",
                "fit_background",
                "fixed_subject",
            ),
            unavailable_modes=("tracked_focus",),
        ),
        OperationCapability(
            operation="package",
            state=CapabilityState.UNAVAILABLE,
            error_code=ErrorCode.CAPABILITY_UNAVAILABLE,
            message="media packaging is not implemented",
        ),
    )


def capability_report() -> CapabilityReport:
    return CapabilityReport(
        operations=_operation_capabilities(),
        media_runtime=detect_media_runtime_capabilities(),
        subtitle_backend=subtitle_capabilities(),
    )


def _capability(operation: str) -> OperationCapability:
    match = next(
        (item for item in _operation_capabilities() if item.operation == operation),
        None,
    )
    if match is None:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            f"unknown operation: {operation}",
            step="capability",
            details={"operation": operation},
        )
    return match


def require_operation(operation: str) -> OperationCapability:
    capability = _capability(operation)
    if capability.state is CapabilityState.AVAILABLE:
        return capability
    raise CutupError(
        capability.error_code or ErrorCode.CAPABILITY_UNAVAILABLE,
        capability.message,
        category=(
            "provider" if capability.state is CapabilityState.PROVIDER_REQUIRED else "capability"
        ),
        step=operation,
        recoverable=capability.state is CapabilityState.PROVIDER_REQUIRED,
        details={"operation": operation},
    )


def require_reframe_mode(mode: str) -> OperationCapability:
    capability = _capability("reframe")
    if mode in capability.available_modes:
        return capability
    raise CutupError(
        ErrorCode.CAPABILITY_UNAVAILABLE,
        f"reframe mode {mode!r} unavailable",
        category="capability",
        step="reframe",
        details={
            "operation": "reframe",
            "requested_mode": mode,
            "available_modes": list(capability.available_modes),
        },
    )


def configure_reframe(
    plan: CutPlan,
    reframe_spec: ReframeSpec,
    *,
    render_spec: RenderSpec | None = None,
    sync_subtitle_safe_area: bool = True,
    created_at: datetime | None = None,
) -> CutPlan:
    require_reframe_mode(reframe_spec.mode)
    subtitle_spec = plan.output_spec.subtitle
    if sync_subtitle_safe_area:
        subtitle_spec = subtitle_spec.model_copy(
            update={
                "safe_area": SubtitleSafeAreaSpec(
                    preset=SubtitleSafeAreaPreset(reframe_spec.safe_area_preset.value),
                    vertical_position=subtitle_spec.safe_area.vertical_position,
                    left_ratio=subtitle_spec.safe_area.left_ratio,
                    right_ratio=subtitle_spec.safe_area.right_ratio,
                    top_ratio=subtitle_spec.safe_area.top_ratio,
                    bottom_ratio=subtitle_spec.safe_area.bottom_ratio,
                )
            }
        )
    output_spec = plan.output_spec.model_copy(
        update={
            "render": render_spec or plan.output_spec.render,
            "reframe": reframe_spec,
            "subtitle": subtitle_spec,
        }
    )
    fingerprint = hashlib.sha256(
        (f"{plan.plan_id}\0{output_spec.model_dump_json(exclude_none=True)}").encode()
    ).hexdigest()[:12]
    return plan.model_copy(
        update={
            "plan_id": f"plan-reframe-{fingerprint}",
            "derived_from_plan_id": plan.plan_id,
            "created_at": created_at or datetime.now(UTC),
            "created_by": "universal-cutup-reframe",
            "output_spec": output_spec,
        }
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_transcript(
    path: Path,
    *,
    source_id: str,
    transcript_id: str | None = None,
    created_at: datetime | None = None,
    created_by: str = "universal-cutup-sdk",
) -> TranscriptArtifact:
    try:
        resolved = path.resolve(strict=True)
        content = resolved.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise CutupError(
            ErrorCode.SOURCE_NOT_FOUND,
            "transcript file could not be read",
            category="source",
            step="load_transcript",
            details={"path": path.name},
        ) from error
    context = TranscriptParseContext(
        transcript_id=transcript_id or f"transcript-{_file_sha256(resolved)[:16]}",
        source_id=source_id,
        created_at=created_at or datetime.now(UTC),
        created_by=created_by,
    )
    parsers = {
        ".srt": parse_srt,
        ".vtt": parse_vtt,
        ".json": parse_json_transcript,
    }
    parser = parsers.get(resolved.suffix.lower())
    if parser is None:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            "transcript must use .srt, .vtt, or .json",
            step="load_transcript",
            details={
                "path": resolved.name,
                "supported_suffixes": sorted(parsers),
            },
        )
    return parser(content, context=context)


def load_cut_plan(path: Path) -> CutPlan:
    if path.suffix.casefold() != ".json":
        raise CutupError(
            ErrorCode.PROTOCOL_UNSUPPORTED_EXTENSION,
            "CutPlan files must use the .json extension",
            step="load_cut_plan",
            details={"path": path.name},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "document" in payload:
            payload = payload["document"]
        return CutPlan.model_validate(payload)
    except OSError as error:
        raise CutupError(
            ErrorCode.SOURCE_NOT_FOUND,
            "CutPlan file could not be read",
            category="source",
            step="load_cut_plan",
            details={"path": path.name},
        ) from error
    except ValueError as error:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            "CutPlan JSON is invalid",
            step="load_cut_plan",
            details={"path": path.name},
        ) from error


def load_sports_observations(
    path: Path,
    *,
    provider_kind: SportsFileProviderKind,
) -> ImportedSportsObservations:
    return FileSportsObservationProvider(provider_kind=provider_kind).import_observations(path)


def detect_sports_transcript(
    transcript: TranscriptArtifact,
    *,
    profile: SportsTextProfile,
    clock: Callable[[], datetime] | None = None,
) -> DetectedSportsObservations:
    return LocalSportsTextProvider(profile=profile, clock=clock).detect(transcript)


def plan_educational_content(
    source: MediaSource,
    transcript: TranscriptArtifact,
    *,
    control_mode: ControlMode,
    raw_instruction: str,
    required_topic_groups: tuple[tuple[str, ...], ...] = (),
    output_spec: OutputSpec | None = None,
) -> EducationalPlanningResult:
    request = resolve_educational_request(
        control_mode,
        raw_instruction,
        required_topic_groups=required_topic_groups,
    )
    candidates = tuple(
        prepared
        for candidate in propose_educational_candidates(transcript)
        for prepared in prepare_educational_duration(candidate)
    )
    selection = select_educational_for_request(candidates, request)
    plan = build_educational_plan(
        source,
        transcript,
        request,
        candidates,
        selection,
        output_spec=output_spec,
    )
    return EducationalPlanningResult(
        request=request,
        candidates=candidates,
        selection=selection,
        plan=plan,
    )


def plan_sports_content(
    source: MediaSource,
    observations: SportsObservationBundle,
    *,
    control_mode: ControlMode,
    raw_instruction: str,
    provider_records: tuple[ProviderRecord, ...],
    output_spec: OutputSpec | None = None,
) -> SportsPlanningResult:
    if source.duration_ms is None:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            "sports planning requires source duration_ms",
            step="plan_sports_content",
            details={"source_id": source.source_id},
        )
    request = resolve_sports_request(control_mode, raw_instruction)
    candidates = propose_sports_candidates(
        observations,
        media_duration_ms=source.duration_ms,
    )
    selection = select_sports_for_request(candidates, request)
    plan = build_sports_plan(
        source,
        observations,
        request,
        candidates,
        selection,
        provider_records=provider_records,
        output_spec=output_spec,
    )
    return SportsPlanningResult(
        request=request,
        candidates=candidates,
        selection=selection,
        plan=plan,
    )


def plan_sports_transcript(
    source: MediaSource,
    transcript: TranscriptArtifact,
    *,
    profile: SportsTextProfile,
    control_mode: ControlMode,
    raw_instruction: str,
    output_spec: OutputSpec | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SportsTranscriptPlanningResult:
    if source.source_id != transcript.source_id:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            "sports transcript source_id must match media source",
            step="plan_sports_transcript",
        )
    detected = detect_sports_transcript(transcript, profile=profile, clock=clock)
    planned = plan_sports_content(
        source,
        detected.artifact,
        control_mode=control_mode,
        raw_instruction=raw_instruction,
        provider_records=(detected.provider_record,),
        output_spec=output_spec,
    )
    return SportsTranscriptPlanningResult(
        request=planned.request,
        candidates=planned.candidates,
        selection=planned.selection,
        plan=planned.plan,
        observations=detected.artifact,
        provider_record=detected.provider_record,
    )


def inspect_source(
    path: Path,
    *,
    source_id: str | None = None,
    media_id: str | None = None,
    rights_attestation: RightsAttestation = RightsAttestation.ANALYSIS_ONLY,
) -> SourceInspection:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise CutupError(
            ErrorCode.SOURCE_NOT_FOUND,
            "media source could not be read",
            category="source",
            step="inspect_source",
            details={"path": path.name},
        ) from error
    media_probe = probe_media(resolved)
    kind: Literal["video", "audio"] = "video" if media_probe.has_video else "audio"
    resolved_source_id = source_id or f"source-{_file_sha256(resolved)[:16]}"
    source = MediaSource(
        source_id=resolved_source_id,
        media_id=media_id or f"media-{_file_sha256(resolved)[:16]}",
        kind=kind,
        sha256=_file_sha256(resolved),
        basename_hint=resolved.name,
        rights_attestation=rights_attestation,
        duration_ms=media_probe.duration_ms,
    )
    return SourceInspection(
        source=source,
        binding=MediaBinding(source_id=source.source_id, local_path=str(resolved)),
        has_video=media_probe.has_video,
        has_audio=media_probe.has_audio,
    )


def analyze_transcript(transcript: TranscriptArtifact) -> TranscriptAnalysis:
    duration_ms = max((segment.end_ms for segment in transcript.segments), default=0)
    return TranscriptAnalysis(
        transcript_id=transcript.transcript_id,
        source_id=transcript.source_id,
        segment_count=len(transcript.segments),
        duration_ms=duration_ms,
        character_count=sum(len(segment.text) for segment in transcript.segments),
    )


def propose_candidates(
    transcript: TranscriptArtifact,
    *,
    context: ApplicationContext | None = None,
    strategy_id: str = "deterministic",
) -> tuple[CutCandidate, ...]:
    sdk_context = context or ApplicationContext.default()
    return sdk_context.strategy_registry.proposal(strategy_id).propose(transcript)


def score_candidates(
    candidates: tuple[CutCandidate, ...],
    *,
    context: ApplicationContext | None = None,
    strategy_id: str = "deterministic",
) -> tuple[CutCandidate, ...]:
    sdk_context = context or ApplicationContext.default()
    record_id = f"strategy-record-scoring-{uuid4().hex[:16]}"
    return sdk_context.strategy_registry.scoring(strategy_id).score(
        candidates,
        strategy_record_id=record_id,
    )


def create_plan(
    source: MediaSource,
    transcript: TranscriptArtifact,
    *,
    context: ApplicationContext | None = None,
    strategy_id: str = "deterministic",
    output_spec: OutputSpec | None = None,
) -> CutPlan:
    plan = transcript_to_plan(
        source,
        transcript,
        context=context or ApplicationContext.default(),
        strategy_id=strategy_id,
    )
    return plan if output_spec is None else plan.model_copy(update={"output_spec": output_spec})


def execute_cut_plan(
    plan: CutPlan,
    *,
    binding: MediaBinding,
    output_root: Path,
) -> ExecutionRecord:
    return execute_external_plan(plan, binding=binding, output_root=output_root)


def process_subtitles(
    plan: CutPlan,
    *,
    binding: MediaBinding,
    output_root: Path,
) -> ExecutionRecord:
    if plan.output_spec.subtitle.mode == "none":
        raise ValueError("process_subtitles requires sidecar or burn_in subtitle mode")
    return execute_cut_plan(plan, binding=binding, output_root=output_root)


def run_full_offline(
    media_path: Path,
    transcript: TranscriptArtifact,
    *,
    output_root: Path,
    rights_attestation: RightsAttestation,
    output_spec: OutputSpec | None = None,
    maximum_clip_count: int | None = DEFAULT_MAX_FULL_CLIPS,
) -> FullOfflineResult:
    inspection = inspect_source(
        media_path,
        source_id=transcript.source_id,
        rights_attestation=rights_attestation,
    )
    analysis = analyze_transcript(transcript)
    plan = create_plan(
        inspection.source,
        transcript,
        output_spec=output_spec,
    )
    selected_clip_count = len(plan.selection_result.selected_candidate_ids)
    if maximum_clip_count is not None:
        if maximum_clip_count < 1:
            raise ValueError("maximum_clip_count must be positive or None")
        if selected_clip_count > maximum_clip_count:
            raise CutupError(
                ErrorCode.CAPABILITY_CONFLICT,
                "full workflow selected more clips than the configured safety limit",
                category="safety",
                step="full_output_guard",
                recoverable=True,
                details={
                    "maximum_clip_count": maximum_clip_count,
                    "selected_clip_count": selected_clip_count,
                },
            )
    execution = execute_cut_plan(
        plan,
        binding=inspection.binding,
        output_root=output_root,
    )
    return FullOfflineResult(
        inspection=inspection,
        analysis=analysis,
        plan=plan,
        execution=execution,
    )


def sdk_timestamp() -> datetime:
    return datetime.now(UTC)
