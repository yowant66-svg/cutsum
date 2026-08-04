from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Literal

import pytest

from universal_cutup.application.subtitle_display import (
    materialize_display_units,
    source_group_text,
)
from universal_cutup.domain.candidates import (
    CutCandidate,
    EvidenceArtifactIdentity,
    EvidenceRef,
)
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.selection import (
    SelectionDecision,
    SelectionResult,
    SelectionStatus,
)
from universal_cutup.domain.sources import MediaBinding, MediaSource, RightsAttestation
from universal_cutup.domain.specs import (
    OutputSpec,
    QualityPreset,
    RenderSpec,
    ResolutionMode,
    SubtitleMode,
    SubtitleSidecarFormat,
    SubtitleSpec,
)
from universal_cutup.domain.subtitles import (
    ContextualTranslationRecord,
    subtitle_text_sha256,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.media.executor import execute_external_plan
from universal_cutup.media.probe import probe_media
from universal_cutup.media.process import (
    ProcessOutcome,
    ProcessRunner,
    ProcessStatus,
)

FIXED_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_plan(
    source_path: Path,
    *,
    subtitle_mode: Literal["sidecar", "burn_in"],
    kind: Literal["video", "audio"] = "video",
    container: Literal["mp4", "mov", "mkv"] = "mp4",
) -> CutPlan:
    source_hash = file_hash(source_path)
    evidence = EvidenceRef(
        evidence_id="evidence-1",
        artifact_id="transcript-1",
        segment_ids=("segment-1",),
        start_ms=500,
        end_ms=2500,
        text_sha256="a" * 64,
        snapshot="Gate D synthetic subtitle",
    )
    candidate = CutCandidate(
        candidate_id="candidate-1",
        source_id="source-1",
        start_ms=500,
        end_ms=2500,
        summary="Gate D synthetic subtitle",
        evidence_refs=(evidence,),
        subtitle_cues=(
            SubtitleCue(
                cue_id="cue-1",
                source_id="source-1",
                start_ms=250,
                end_ms=1250,
                text="first cue, not the summary",
                source_segment_ids=("segment-1",),
            ),
            SubtitleCue(
                cue_id="cue-2",
                source_id="source-1",
                start_ms=1750,
                end_ms=2750,
                text="second cue",
                source_segment_ids=("segment-1",),
            ),
        ),
    )
    selection = SelectionResult(
        selection_id="selection-1",
        selection_strategy_id="external",
        selection_strategy_version="0.1.0",
        decisions=(
            SelectionDecision(
                candidate_id=candidate.candidate_id,
                status=SelectionStatus.SELECTED,
                reason="external plan",
                evidence_refs=(evidence.evidence_id,),
            ),
        ),
    )
    return CutPlan(
        document_type="cut_plan",
        created_at=FIXED_TIME,
        created_by="test-suite",
        plan_id="plan-1",
        source=MediaSource(
            source_id="source-1",
            media_id="media-1",
            kind=kind,
            sha256=source_hash,
            basename_hint=source_path.name,
            rights_attestation=RightsAttestation.OWNED,
        ),
        evidence_artifacts=(
            EvidenceArtifactIdentity(
                artifact_id="transcript-1",
                source_id="source-1",
                segment_ids=("segment-1",),
            ),
        ),
        candidates=(candidate,),
        selection_result=selection,
        output_spec=OutputSpec(
            render=RenderSpec(container=container, duration_tolerance_ms=200),
            subtitle=SubtitleSpec(mode=SubtitleMode(subtitle_mode)),
        ),
    )


@pytest.mark.parametrize("subtitle_mode", ["sidecar", "burn_in"])
def test_external_plan_produces_verified_artifacts(
    synthetic_media: Path,
    tmp_path: Path,
    subtitle_mode: Literal["sidecar", "burn_in"],
) -> None:
    before_hash = file_hash(synthetic_media)
    before_mtime = synthetic_media.stat().st_mtime_ns
    plan = make_plan(synthetic_media, subtitle_mode=subtitle_mode)
    output_root = tmp_path / f"output-{subtitle_mode}"
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(
            source_id=plan.source.source_id,
            local_path=str(synthetic_media),
        ),
        output_root=output_root,
    )
    assert execution.plan_id == plan.plan_id
    assert execution.status == "success"
    assert len(execution.artifacts) >= 1
    assert all(artifact.sha256 for artifact in execution.artifacts)
    video_artifact = next(
        artifact for artifact in execution.artifacts if artifact.artifact_type == "video"
    )
    probe = probe_media(output_root / video_artifact.relative_path)
    assert probe.has_video is True
    assert probe.has_audio is True
    assert probe.video_codec == "h264"
    assert probe.audio_codec == "aac"
    assert abs(probe.duration_ms - 2000) <= 200
    assert file_hash(synthetic_media) == before_hash
    assert synthetic_media.stat().st_mtime_ns == before_mtime
    if subtitle_mode == "sidecar":
        assert any(artifact.artifact_type == "subtitle" for artifact in execution.artifacts)
        subtitle_text = (output_root / "subtitles/candidate-1.srt").read_text(encoding="utf-8")
        assert "00:00:00,000 --> 00:00:00,750" in subtitle_text
        assert "00:00:01,250 --> 00:00:02,000" in subtitle_text
        assert "first cue, not the summary" in subtitle_text
        assert "Gate D synthetic subtitle" not in subtitle_text


def test_bilingual_burn_in_is_visible_and_preserves_timed_cues(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="burn_in")
    candidate = plan.candidates[0]
    translated = tuple(
        cue.model_copy(
            update={
                "cue_id": f"{cue.cue_id}-zh",
                "text": "对应的中文逐句字幕",
                "language": "zh-CN",
            }
        )
        for cue in candidate.subtitle_cues
    )
    bilingual_candidate = candidate.model_copy(update={"translated_subtitle_cues": translated})
    bilingual_plan = plan.model_copy(
        update={
            "candidates": (bilingual_candidate,),
            "output_spec": OutputSpec(
                render=RenderSpec(),
                subtitle=SubtitleSpec(
                    mode=SubtitleMode.BILINGUAL_BURN_IN,
                    language="en",
                    translation_language="zh-CN",
                ),
            ),
        }
    )
    execution = execute_external_plan(
        bilingual_plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=tmp_path / "bilingual",
    )
    assert execution.status == "success"
    assert execution.steps[0].details["subtitle_backend"] in {
        "ffmpeg-libass",
        "macos-system-overlay",
    }


def test_bilingual_vtt_sidecar_uses_one_timeline(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    candidate = plan.candidates[0]
    translated = tuple(
        cue.model_copy(
            update={
                "cue_id": f"{cue.cue_id}-zh",
                "text": "对应的中文逐句字幕",
                "language": "zh-CN",
            }
        )
        for cue in candidate.subtitle_cues
    )
    bilingual_plan = plan.model_copy(
        update={
            "candidates": (candidate.model_copy(update={"translated_subtitle_cues": translated}),),
            "output_spec": OutputSpec(
                subtitle=SubtitleSpec(
                    mode=SubtitleMode.BILINGUAL_SIDECAR,
                    sidecar_format=SubtitleSidecarFormat.VTT,
                    language="en",
                    translation_language="zh-CN",
                )
            ),
        }
    )

    output_root = tmp_path / "bilingual-vtt"
    execution = execute_external_plan(
        bilingual_plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=output_root,
    )

    sidecar = output_root / "subtitles/candidate-1.vtt"
    content = sidecar.read_text(encoding="utf-8")
    assert execution.status == "success"
    assert "subtitle_backend" not in execution.steps[0].details
    assert content.startswith("WEBVTT")
    assert "first cue, not the summary\n对应的中文逐句字幕" in content


def test_bilingual_burn_in_prefers_semantic_display_units_over_micro_cue_pairing(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="burn_in")
    candidate = plan.candidates[0]
    source_text = source_group_text(candidate.subtitle_cues)
    translation = "算法是一个函数，它把输入映射为满足问题要求的输出。"  # noqa: RUF001
    translation_record = ContextualTranslationRecord(
        translation_record_id="translation-semantic-1",
        provider_record_ref="provider-translation",
        source_language="en",
        translation_language="zh-CN",
        source_cue_ids=tuple(cue.cue_id for cue in candidate.subtitle_cues),
        source_text=source_text,
        preceding_context="The lecturer is defining an algorithm.",
        following_context="The lecturer next explains correctness.",
        translated_text=translation,
        glossary={"algorithm": "算法", "function": "函数"},
        source_text_sha256=subtitle_text_sha256(source_text),
        translation_sha256=subtitle_text_sha256(translation),
    )
    display_units = materialize_display_units(
        candidate.subtitle_cues,
        (translation_record,),
        source_id=candidate.source_id,
    )
    bilingual_candidate = candidate.model_copy(
        update={
            "subtitle_display_units": display_units,
            "contextual_translation_records": (translation_record,),
        }
    )
    provider_record = ProviderRecord(
        provider_record_id="provider-translation",
        provider_id="test-host",
        operation="translate_semantic_subtitle_unit",
        input_hashes=(translation_record.source_text_sha256,),
        output_hashes=(translation_record.translation_sha256,),
        cost_minor_units=0,
        currency="USD",
        started_at=FIXED_TIME,
        completed_at=FIXED_TIME,
    )
    bilingual_plan = plan.model_copy(
        update={
            "candidates": (bilingual_candidate,),
            "provider_records": (provider_record,),
            "output_spec": OutputSpec(
                render=RenderSpec(),
                subtitle=SubtitleSpec(
                    mode=SubtitleMode.BILINGUAL_BURN_IN,
                    language="en",
                    translation_language="zh-CN",
                ),
            ),
        }
    )
    execution = execute_external_plan(
        bilingual_plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=tmp_path / "semantic-bilingual",
    )
    assert execution.status == "success"
    assert len(bilingual_candidate.subtitle_display_units) == 1
    assert bilingual_candidate.translated_subtitle_cues == ()


def test_preview_downscale_matches_execution_record_and_ffprobe(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar").model_copy(
        update={
            "output_spec": OutputSpec(
                render=RenderSpec(
                    resolution_mode=ResolutionMode.P144,
                    quality_preset=QualityPreset.PREVIEW,
                ),
                subtitle=SubtitleSpec(mode=SubtitleMode.SOURCE_SIDECAR),
            )
        }
    )
    output_root = tmp_path / "preview"
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=output_root,
    )
    artifact = next(item for item in execution.artifacts if item.artifact_type == "video")
    probe = probe_media(output_root / artifact.relative_path)
    assert (probe.width, probe.height) == (256, 144)
    assert artifact.source_resolution == "320x180"
    assert artifact.actual_output_resolution == "256x144"
    assert artifact.quality_preset == "preview"


def test_each_replay_has_independent_execution_record(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    binding = MediaBinding(source_id="source-1", local_path=str(synthetic_media))
    first = execute_external_plan(plan, binding=binding, output_root=tmp_path / "first")
    second = execute_external_plan(plan, binding=binding, output_root=tmp_path / "second")
    assert first.execution_id != second.execution_id
    assert first.plan_document_sha256 == second.plan_document_sha256
    assert first.artifacts[0].execution_id == first.execution_id
    assert second.artifacts[0].execution_id == second.execution_id


def test_existing_output_fails_without_touching_source(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    output_root = tmp_path / "output"
    binding = MediaBinding(source_id="source-1", local_path=str(synthetic_media))
    execute_external_plan(plan, binding=binding, output_root=output_root)
    source_hash = file_hash(synthetic_media)
    execution = execute_external_plan(plan, binding=binding, output_root=output_root)
    assert execution.status == "failed"
    assert execution.steps[0].error_code == ErrorCode.OUTPUT_EXISTS.value
    assert file_hash(synthetic_media) == source_hash


def test_publish_race_rolls_back_only_outputs_owned_by_this_execution(
    synthetic_media: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from universal_cutup.media import executor as executor_module

    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    output_root = tmp_path / "publish-race"
    original_publish = executor_module._publish_no_overwrite
    call_count = 0

    def publish_with_sidecar_race(
        temporary_path: Path,
        output_path: Path,
    ) -> executor_module._PublishedOutput:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("created by another process", encoding="utf-8")
            raise CutupError(
                ErrorCode.OUTPUT_EXISTS,
                "simulated sidecar publish race",
                category="conflict",
            )
        return original_publish(temporary_path, output_path)

    monkeypatch.setattr(executor_module, "_publish_no_overwrite", publish_with_sidecar_race)
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=output_root,
    )

    assert execution.status == "failed"
    assert not (output_root / "clips/candidate-1.mp4").exists()
    assert (output_root / "subtitles/candidate-1.srt").read_text(encoding="utf-8") == (
        "created by another process"
    )
    assert not tuple(output_root.glob(".cutup-*"))


def test_all_selected_outputs_are_preflighted_before_rendering(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    first = plan.candidates[0]
    second_evidence = first.evidence_refs[0].model_copy(update={"evidence_id": "evidence-2"})
    second = first.model_copy(
        update={
            "candidate_id": "candidate-2",
            "evidence_refs": (second_evidence,),
        }
    )
    second_decision = plan.selection_result.decisions[0].model_copy(
        update={"candidate_id": "candidate-2", "evidence_refs": ("evidence-2",)}
    )
    two_candidate_plan = plan.model_copy(
        update={
            "candidates": (first, second),
            "selection_result": plan.selection_result.model_copy(
                update={"decisions": (*plan.selection_result.decisions, second_decision)}
            ),
        }
    )
    output_root = tmp_path / "preflight-all"
    conflict = output_root / "clips/candidate-2.mp4"
    conflict.parent.mkdir(parents=True)
    conflict.write_bytes(b"pre-existing")

    execution = execute_external_plan(
        two_candidate_plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=output_root,
    )

    assert execution.status == "failed"
    assert execution.steps[0].step_id == "preflight-output"
    assert execution.steps[0].error_code == ErrorCode.OUTPUT_EXISTS.value
    assert not (output_root / "clips/candidate-1.mp4").exists()
    assert conflict.read_bytes() == b"pre-existing"


def test_media_edit_requires_rights_attestation(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    unsafe_source = plan.source.model_copy(
        update={"rights_attestation": RightsAttestation.ANALYSIS_ONLY}
    )
    unsafe_plan = plan.model_copy(update={"source": unsafe_source})
    execution = execute_external_plan(
        unsafe_plan,
        binding=MediaBinding(
            source_id="source-1",
            local_path=str(synthetic_media),
        ),
        output_root=tmp_path / "output",
    )
    assert execution.status == "failed"
    assert execution.steps[0].error_code == ErrorCode.RIGHTS_ATTESTATION_REQUIRED.value


def test_portable_plan_rebinds_to_same_content_at_different_path(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    rebound_media = tmp_path / "different-location" / "rebound.mp4"
    rebound_media.parent.mkdir()
    shutil.copy2(synthetic_media, rebound_media)
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(
            source_id=plan.source.source_id,
            local_path=str(rebound_media),
        ),
        output_root=tmp_path / "rebound-output",
    )
    assert execution.artifacts


@pytest.mark.parametrize("container", ["mov", "mkv"])
def test_requested_container_is_real_output(
    synthetic_media: Path,
    tmp_path: Path,
    container: Literal["mov", "mkv"],
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar", container=container)
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=tmp_path / container,
    )
    artifact = next(item for item in execution.artifacts if item.artifact_type == "video")
    assert artifact.relative_path.endswith(f".{container}")
    assert (tmp_path / container / artifact.relative_path).exists()


def test_audio_only_source_produces_audio_artifact(
    synthetic_audio: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_audio, subtitle_mode="sidecar", kind="audio")
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_audio)),
        output_root=tmp_path / "audio",
    )
    media_artifact = next(item for item in execution.artifacts if item.artifact_type != "subtitle")
    assert execution.status == "success"
    assert media_artifact.artifact_type == "audio"
    assert media_artifact.mime_type == "audio/mp4"


def test_candidate_failure_after_success_returns_partial_record(
    synthetic_media: Path,
    tmp_path: Path,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    first = plan.candidates[0]
    second_evidence = first.evidence_refs[0].model_copy(update={"evidence_id": "evidence-2"})
    second = first.model_copy(
        update={
            "candidate_id": "candidate-2",
            "evidence_refs": (second_evidence,),
            "subtitle_cues": (),
        }
    )
    second_decision = plan.selection_result.decisions[0].model_copy(
        update={"candidate_id": "candidate-2", "evidence_refs": ("evidence-2",)}
    )
    partial_plan = plan.model_copy(
        update={
            "candidates": (first, second),
            "selection_result": plan.selection_result.model_copy(
                update={"decisions": (*plan.selection_result.decisions, second_decision)}
            ),
        }
    )
    execution = execute_external_plan(
        partial_plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=tmp_path / "partial",
    )
    assert execution.status == "partial"
    assert [step.status for step in execution.steps] == ["completed", "failed"]
    assert execution.steps[1].error_code == ErrorCode.SUBTITLE_CUES_REQUIRED.value


class FixedOutcomeRunner(ProcessRunner):
    def __init__(self, status: ProcessStatus) -> None:
        self.status = status

    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
        cancellation: Event | None = None,
        cwd: Path | None = None,
    ) -> ProcessOutcome:
        return ProcessOutcome(
            status=self.status,
            return_code=None,
            stdout="",
            stderr=self.status.value,
            redacted_command=tuple(arguments),
            recoverable=True,
        )


@pytest.mark.parametrize(
    ("process_status", "execution_status", "error_code"),
    [
        (ProcessStatus.CANCELLED, "cancelled", ErrorCode.CANCELLED),
        (ProcessStatus.TIMED_OUT, "timed_out", ErrorCode.MEDIA_PROCESS_TIMEOUT),
    ],
)
def test_cancelled_and_timed_out_attempts_return_records(
    synthetic_media: Path,
    tmp_path: Path,
    process_status: ProcessStatus,
    execution_status: str,
    error_code: ErrorCode,
) -> None:
    plan = make_plan(synthetic_media, subtitle_mode="sidecar")
    execution = execute_external_plan(
        plan,
        binding=MediaBinding(source_id="source-1", local_path=str(synthetic_media)),
        output_root=tmp_path / process_status.value,
        runner=FixedOutcomeRunner(process_status),
    )
    assert execution.status == execution_status
    assert execution.steps[0].error_code == error_code.value
    assert not tuple((tmp_path / process_status.value).glob(".cutup-*"))
