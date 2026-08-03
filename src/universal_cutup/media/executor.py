from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import uuid4

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.execution import (
    CutArtifact,
    ExecutionRecord,
    ExecutionStatus,
    StepResult,
)
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.selection import SelectionStatus
from universal_cutup.domain.sources import (
    RIGHTS_ATTESTATION_NOTICE,
    MediaBinding,
    RightsAttestation,
)
from universal_cutup.domain.specs import SubtitleMode, SubtitleSidecarFormat
from universal_cutup.hashing import document_sha256

from .cut import cut_media
from .paths import SafePathPolicy
from .probe import probe_media
from .process import ProcessRunner
from .rendering import ReframeDecision, ResolutionDecision, resolve_reframe, resolve_resolution
from .subtitles import (
    RelativeSubtitleCue,
    burn_in_subtitle,
    clip_cues_to_candidate,
    clip_display_units_to_candidate,
    clip_semantic_spans_to_candidate,
    pair_bilingual_cues,
    write_bilingual_ass,
    write_bilingual_sidecar,
    write_sidecar,
)

EDIT_RIGHTS = frozenset(
    {
        RightsAttestation.OWNED,
        RightsAttestation.LICENSED,
        RightsAttestation.PUBLIC_DOMAIN,
        RightsAttestation.AUTHORIZED_OTHER,
    }
)
SIDECAR_MODES = frozenset(
    {
        SubtitleMode.SIDECAR,
        SubtitleMode.SOURCE_SIDECAR,
        SubtitleMode.TRANSLATED_SIDECAR,
        SubtitleMode.BILINGUAL_SIDECAR,
    }
)
BILINGUAL_MODES = frozenset(
    {
        SubtitleMode.BILINGUAL_SIDECAR,
        SubtitleMode.BILINGUAL_BURN_IN,
    }
)
BURN_IN_MODES = frozenset(
    {
        SubtitleMode.BURN_IN,
        SubtitleMode.SOURCE_BURN_IN,
        SubtitleMode.TRANSLATED_BURN_IN,
        SubtitleMode.BILINGUAL_BURN_IN,
    }
)
TRANSLATED_MODES = frozenset(
    {
        SubtitleMode.TRANSLATED_SIDECAR,
        SubtitleMode.TRANSLATED_BURN_IN,
    }
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(
    path: Path,
    *,
    output_root: Path,
    execution_id: str,
    candidate_id: str,
    artifact_type: Literal["video", "audio", "subtitle"],
    duration_ms: int | None,
    resolution: ResolutionDecision | None = None,
    video_codec: str | None = None,
    audio_codec: str | None = None,
    quality_preset: str | None = None,
    rate_control: str | None = None,
    reframe: ReframeDecision | None = None,
) -> CutArtifact:
    return CutArtifact(
        artifact_id=str(uuid4()),
        execution_id=execution_id,
        candidate_id=candidate_id,
        artifact_type=artifact_type,
        relative_path=str(path.relative_to(output_root)),
        sha256=_file_sha256(path),
        size_bytes=path.stat().st_size,
        duration_ms=duration_ms,
        mime_type=(
            {
                "mp4": "video/mp4",
                "mov": "video/quicktime",
                "mkv": "video/x-matroska",
            }.get(path.suffix.removeprefix("."), "application/octet-stream")
            if artifact_type == "video"
            else (
                {
                    "mp4": "audio/mp4",
                    "mov": "audio/quicktime",
                    "mkv": "audio/x-matroska",
                }.get(path.suffix.removeprefix("."), "application/octet-stream")
                if artifact_type == "audio"
                else "application/x-subrip"
            )
        ),
        source_resolution=(
            f"{resolution.source_width}x{resolution.source_height}"
            if resolution is not None
            else None
        ),
        actual_output_resolution=(
            f"{resolution.output_width}x{resolution.output_height}"
            if resolution is not None
            else None
        ),
        scale_reason=resolution.scale_reason if resolution is not None else None,
        upscale=resolution.upscale if resolution is not None else False,
        video_codec=video_codec,
        audio_codec=audio_codec,
        quality_preset=quality_preset,
        rate_control=rate_control,
        reframe_mode=reframe.mode if reframe is not None else None,
        crop_box=reframe.crop_box if reframe is not None else None,
        focus_point=reframe.source_focus if reframe is not None else None,
        output_anchor=reframe.output_anchor if reframe is not None else None,
        safe_area=reframe.safe_area if reframe is not None else None,
        composition_reason=(reframe.composition_reason if reframe is not None else None),
    )


def _validate_source(plan: CutPlan, binding: MediaBinding) -> tuple[Path, str, int]:
    if plan.source.rights_attestation not in EDIT_RIGHTS:
        raise CutupError(
            ErrorCode.RIGHTS_ATTESTATION_REQUIRED,
            "Media editing requires owned, licensed, public_domain, or authorized_other",
            category="permission/policy",
            details={"notice": RIGHTS_ATTESTATION_NOTICE},
        )
    if binding.source_id != plan.source.source_id:
        raise CutupError(
            ErrorCode.SOURCE_HASH_MISMATCH,
            "binding source_id does not match CutPlan source_id",
            category="source",
        )
    if binding.local_path is None:
        raise CutupError(
            ErrorCode.SOURCE_NOT_FOUND,
            "external CutPlan execution requires an explicit local source binding",
            category="source",
        )
    source_path = Path(binding.local_path).resolve(strict=True)
    source_hash = _file_sha256(source_path)
    if source_hash != plan.source.sha256:
        raise CutupError(
            ErrorCode.SOURCE_HASH_MISMATCH,
            "source SHA-256 does not match CutPlan binding",
            category="source",
        )
    return source_path, source_hash, source_path.stat().st_mtime_ns


@dataclass(frozen=True, slots=True)
class _PublishedOutput:
    path: Path
    device: int
    inode: int

    def rollback_if_owned(self) -> None:
        try:
            current = self.path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return
        if (current.st_dev, current.st_ino) == (self.device, self.inode):
            self.path.unlink(missing_ok=True)


def _publish_no_overwrite(temporary_path: Path, output_path: Path) -> _PublishedOutput:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(temporary_path, output_path)
    except FileExistsError as error:
        raise CutupError(
            ErrorCode.OUTPUT_EXISTS,
            f"output already exists: {output_path.name}",
            category="conflict",
        ) from error
    published = output_path.stat(follow_symlinks=False)
    return _PublishedOutput(
        path=output_path,
        device=published.st_dev,
        inode=published.st_ino,
    )


def execute_external_plan(
    plan: CutPlan,
    *,
    binding: MediaBinding,
    output_root: Path,
    runner: ProcessRunner | None = None,
) -> ExecutionRecord:
    execution_id = str(uuid4())
    started_at = datetime.now(UTC)
    plan_hash = document_sha256(plan)
    artifacts: list[CutArtifact] = []
    steps: list[StepResult] = []
    warnings: list[str] = []
    process_runner = runner or ProcessRunner()

    def finish(status: ExecutionStatus) -> ExecutionRecord:
        completed_at = datetime.now(UTC)
        return ExecutionRecord(
            document_type="execution_record",
            created_at=completed_at,
            created_by="universal-cutup",
            execution_id=execution_id,
            plan_id=plan.plan_id,
            plan_document_sha256=plan_hash,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            steps=tuple(steps),
            artifacts=tuple(artifacts),
            provider_records=plan.provider_records,
            warnings=tuple(warnings),
        )

    try:
        if plan.output_spec.reframe.mode == "tracked_focus":
            raise CutupError(
                ErrorCode.CAPABILITY_UNAVAILABLE,
                "tracked_focus requires a configured tracking provider",
                category="capability",
                step="preflight",
            )
        if plan.output_spec.reframe.mode != "none" and plan.source.kind != "video":
            raise CutupError(
                ErrorCode.CAPABILITY_UNAVAILABLE,
                "reframe requires a video source",
                category="capability",
                step="preflight",
            )
        source_path, source_hash, source_mtime_ns = _validate_source(plan, binding)
        output_root.mkdir(parents=True, exist_ok=True)
        resolved_output_root = output_root.resolve(strict=True)
        path_policy = SafePathPolicy(output_root=resolved_output_root)
    except (CutupError, OSError) as error:
        cutup_error = (
            error
            if isinstance(error, CutupError)
            else CutupError(ErrorCode.SOURCE_NOT_FOUND, str(error), category="source")
        )
        steps.append(
            StepResult(
                step_id="preflight",
                status="failed",
                error_code=cutup_error.code.value,
                message=str(cutup_error),
                recoverable=cutup_error.recoverable,
            )
        )
        return finish(ExecutionStatus.FAILED)

    candidates_by_id = {candidate.candidate_id: candidate for candidate in plan.candidates}
    try:
        source_probe = probe_media(source_path)
        reframe = (
            resolve_reframe(
                plan.output_spec.render,
                plan.output_spec.reframe,
                source_width=source_probe.width,
                source_height=source_probe.height,
            )
            if plan.output_spec.reframe.mode != "none"
            and source_probe.width is not None
            and source_probe.height is not None
            else None
        )
        resolution = (
            reframe.resolution
            if reframe is not None
            else (
                resolve_resolution(
                    plan.output_spec.render,
                    source_width=source_probe.width,
                    source_height=source_probe.height,
                )
                if source_probe.width is not None and source_probe.height is not None
                else None
            )
        )
    except CutupError as error:
        steps.append(
            StepResult(
                step_id="preflight",
                status="failed",
                error_code=error.code.value,
                message=str(error),
                recoverable=error.recoverable,
            )
        )
        return finish(ExecutionStatus.FAILED)
    selected_decisions = [
        decision
        for decision in plan.selection_result.decisions
        if decision.status is SelectionStatus.SELECTED
    ]
    candidate_output_paths: dict[str, tuple[Path, Path | None]] = {}
    try:
        extension = plan.output_spec.render.container
        subtitle_mode = plan.output_spec.subtitle.mode
        sidecar_format = plan.output_spec.subtitle.sidecar_format
        for decision in selected_decisions:
            candidate_output_paths[decision.candidate_id] = (
                path_policy.resolve_output(f"clips/{decision.candidate_id}.{extension}"),
                (
                    path_policy.resolve_output(
                        f"subtitles/{decision.candidate_id}.{sidecar_format.value}"
                    )
                    if subtitle_mode in SIDECAR_MODES
                    else None
                ),
            )
    except CutupError as error:
        steps.append(
            StepResult(
                step_id="preflight-output",
                status="failed",
                error_code=error.code.value,
                message=str(error),
                recoverable=error.recoverable,
            )
        )
        return finish(ExecutionStatus.FAILED)
    for decision in selected_decisions:
        candidate = candidates_by_id[decision.candidate_id]
        step_started_at = datetime.now(UTC)
        backend: str | None = None
        clip_path: Path | None = None
        sidecar_path: Path | None = None
        published_outputs: list[_PublishedOutput] = []
        try:
            extension = plan.output_spec.render.container
            clip_path, sidecar_path = candidate_output_paths[candidate.candidate_id]
            subtitle_mode = plan.output_spec.subtitle.mode
            duration_ms = candidate.end_ms - candidate.start_ms
            sidecar_format = plan.output_spec.subtitle.sidecar_format
            source_cues = clip_cues_to_candidate(
                candidate.subtitle_cues,
                candidate_start_ms=candidate.start_ms,
                candidate_end_ms=candidate.end_ms,
            )
            semantic_source_cues = clip_semantic_spans_to_candidate(
                candidate.subtitle_semantic_spans,
                candidate_start_ms=candidate.start_ms,
                candidate_end_ms=candidate.end_ms,
            )
            effective_source_cues = semantic_source_cues or source_cues
            translated_cues = clip_cues_to_candidate(
                candidate.translated_subtitle_cues,
                candidate_start_ms=candidate.start_ms,
                candidate_end_ms=candidate.end_ms,
            )
            display_pairs = clip_display_units_to_candidate(
                candidate.subtitle_display_units,
                candidate_start_ms=candidate.start_ms,
                candidate_end_ms=candidate.end_ms,
            )
            display_source_cues = tuple(
                RelativeSubtitleCue(
                    start_ms=cue.start_ms,
                    end_ms=cue.end_ms,
                    text=cue.source_text,
                )
                for cue in display_pairs
            )
            display_translated_cues = tuple(
                RelativeSubtitleCue(
                    start_ms=cue.start_ms,
                    end_ms=cue.end_ms,
                    text=cue.translation_text,
                )
                for cue in display_pairs
            )
            bilingual_pairs = (
                (
                    display_pairs
                    if display_pairs
                    else pair_bilingual_cues(source_cues, translated_cues)
                )
                if subtitle_mode in BILINGUAL_MODES
                else ()
            )
            timed_burn_cues = (
                tuple(
                    RelativeSubtitleCue(
                        start_ms=cue.start_ms,
                        end_ms=cue.end_ms,
                        text=f"{cue.source_text}\n{cue.translation_text}",
                    )
                    for cue in bilingual_pairs
                )
                if bilingual_pairs
                else (
                    (display_translated_cues or translated_cues)
                    if subtitle_mode in TRANSLATED_MODES
                    else (display_source_cues or effective_source_cues)
                )
            )
            with TemporaryDirectory(
                prefix=".cutup-",
                dir=resolved_output_root,
            ) as temporary_directory:
                temporary_root = Path(temporary_directory)
                temporary_clip = temporary_root / f"base-clip.{extension}"
                temporary_sidecar_format = (
                    SubtitleSidecarFormat.ASS
                    if subtitle_mode is SubtitleMode.BILINGUAL_BURN_IN
                    else (
                        sidecar_format
                        if subtitle_mode in SIDECAR_MODES
                        else SubtitleSidecarFormat.SRT
                    )
                )
                temporary_sidecar = temporary_root / (f"subtitle.{temporary_sidecar_format.value}")
                active_cues = (
                    (display_translated_cues or translated_cues)
                    if subtitle_mode in TRANSLATED_MODES
                    else (display_source_cues or effective_source_cues)
                )
                if subtitle_mode is SubtitleMode.BILINGUAL_BURN_IN:
                    if resolution is None:
                        raise CutupError(
                            ErrorCode.CAPABILITY_UNAVAILABLE,
                            "bilingual burn-in requires a video resolution",
                            category="capability",
                            step="subtitle",
                        )
                    write_bilingual_ass(
                        temporary_sidecar,
                        cues=bilingual_pairs,
                        spec=plan.output_spec.subtitle,
                        width=resolution.output_width,
                        height=resolution.output_height,
                    )
                elif subtitle_mode is SubtitleMode.BILINGUAL_SIDECAR:
                    write_bilingual_sidecar(
                        temporary_sidecar,
                        cues=bilingual_pairs,
                        sidecar_format=sidecar_format,
                        spec=plan.output_spec.subtitle,
                        width=resolution.output_width if resolution is not None else 1920,
                        height=resolution.output_height if resolution is not None else 1080,
                    )
                elif subtitle_mode in SIDECAR_MODES:
                    write_sidecar(
                        temporary_sidecar,
                        cues=active_cues,
                        sidecar_format=sidecar_format,
                        spec=plan.output_spec.subtitle,
                        width=resolution.output_width if resolution is not None else 1920,
                        height=resolution.output_height if resolution is not None else 1080,
                    )
                elif subtitle_mode in BURN_IN_MODES:
                    write_sidecar(temporary_sidecar, cues=active_cues)
                cut_media(
                    source_path,
                    temporary_clip,
                    start_ms=candidate.start_ms,
                    end_ms=candidate.end_ms,
                    render_spec=plan.output_spec.render,
                    source_kind=plan.source.kind,
                    runner=process_runner,
                    resolution=resolution,
                    reframe=reframe,
                    # A fixed 30-second budget incorrectly rejects valid long-form
                    # excerpts on slower local machines. Keep the short-clip floor,
                    # but allow up to two wall-clock seconds per media second.
                    timeout_seconds=max(30, (duration_ms / 1000) * 2),
                )
                if subtitle_mode in BURN_IN_MODES:
                    if plan.source.kind == "audio":
                        raise CutupError(
                            ErrorCode.CAPABILITY_UNAVAILABLE,
                            "burn-in subtitles require a video source",
                            category="capability",
                            step="subtitle",
                        )
                    burned_clip = temporary_root / f"burned-clip.{extension}"
                    backend = burn_in_subtitle(
                        temporary_clip,
                        temporary_sidecar,
                        burned_clip,
                        render_spec=plan.output_spec.render,
                        subtitle_spec=plan.output_spec.subtitle,
                        timed_cues=timed_burn_cues,
                        runner=process_runner,
                        working_directory=temporary_root,
                    )
                    temporary_clip = burned_clip
                    if backend == "macos-system-overlay":
                        warnings.append(
                            "macOS fallback renders combined cue text and ignores font_family"
                        )
                probe = probe_media(temporary_clip, runner=process_runner)
                if abs(probe.duration_ms - duration_ms) > (
                    plan.output_spec.render.duration_tolerance_ms
                ):
                    raise CutupError(
                        ErrorCode.MEDIA_PROCESS_FAILED,
                        "rendered clip duration exceeds plan tolerance",
                        category="media",
                        step="verify",
                    )
                published_outputs.append(_publish_no_overwrite(temporary_clip, clip_path))
                if sidecar_path is not None:
                    published_outputs.append(_publish_no_overwrite(temporary_sidecar, sidecar_path))
            if sidecar_path is not None:
                artifacts.append(
                    _artifact(
                        sidecar_path,
                        output_root=resolved_output_root,
                        execution_id=execution_id,
                        candidate_id=candidate.candidate_id,
                        artifact_type="subtitle",
                        duration_ms=None,
                    )
                )
            artifacts.append(
                _artifact(
                    clip_path,
                    output_root=resolved_output_root,
                    execution_id=execution_id,
                    candidate_id=candidate.candidate_id,
                    artifact_type=("video" if probe.has_video else "audio"),
                    duration_ms=probe.duration_ms,
                    resolution=resolution,
                    video_codec=probe.video_codec,
                    audio_codec=probe.audio_codec,
                    quality_preset=plan.output_spec.render.quality_preset.value,
                    rate_control=plan.output_spec.render.rate_control.model_dump_json(),
                    reframe=reframe,
                )
            )
            steps.append(
                StepResult(
                    step_id="execute-candidate",
                    candidate_id=candidate.candidate_id,
                    status="completed",
                    started_at=step_started_at,
                    completed_at=datetime.now(UTC),
                    details={
                        **({"subtitle_backend": backend} if backend else {}),
                        **({"reframe_mode": reframe.mode} if reframe is not None else {}),
                    },
                )
            )
        except (CutupError, OSError) as error:
            for published_output in published_outputs:
                published_output.rollback_if_owned()
            cutup_error = (
                error
                if isinstance(error, CutupError)
                else CutupError(ErrorCode.MEDIA_PROCESS_FAILED, str(error), category="media")
            )
            step_status: Literal["failed", "cancelled", "timed_out"]
            if cutup_error.code is ErrorCode.CANCELLED:
                step_status = "cancelled"
            elif cutup_error.code is ErrorCode.MEDIA_PROCESS_TIMEOUT:
                step_status = "timed_out"
            else:
                step_status = "failed"
            steps.append(
                StepResult(
                    step_id="execute-candidate",
                    candidate_id=candidate.candidate_id,
                    status=step_status,
                    started_at=step_started_at,
                    completed_at=datetime.now(UTC),
                    recoverable=cutup_error.recoverable,
                    error_code=cutup_error.code.value,
                    message=str(cutup_error),
                )
            )

    if (
        _file_sha256(source_path) != source_hash
        or source_path.stat().st_mtime_ns != source_mtime_ns
    ):
        steps.append(
            StepResult(
                step_id="verify-source",
                status="failed",
                error_code=ErrorCode.SOURCE_HASH_MISMATCH.value,
                message="source changed during execution",
            )
        )
    statuses = {step.status for step in steps}
    if "timed_out" in statuses and not artifacts:
        return finish(ExecutionStatus.TIMED_OUT)
    if "cancelled" in statuses and not artifacts:
        return finish(ExecutionStatus.CANCELLED)
    if ("failed" in statuses or "timed_out" in statuses or "cancelled" in statuses) and artifacts:
        return finish(ExecutionStatus.PARTIAL)
    if "failed" in statuses:
        return finish(ExecutionStatus.FAILED)
    return finish(ExecutionStatus.SUCCESS)
