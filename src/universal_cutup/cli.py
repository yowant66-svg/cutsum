from __future__ import annotations

import json
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from pydantic import BaseModel

from universal_cutup.application.blind_runs import (
    freeze_blind_run,
    load_blind_run_input,
    load_reference_after_freeze,
    verify_frozen_blind_run,
)
from universal_cutup.application.sdk import (
    DEFAULT_MAX_FULL_CLIPS,
    aggregate_intelligence,
    analyze_transcript,
    capability_report,
    configure_reframe,
    create_adaptive_plan,
    create_plan,
    execute_cut_plan,
    inspect_source,
    load_cut_plan,
    load_sports_observations,
    load_transcript,
    plan_educational_content,
    plan_sports_content,
    plan_sports_transcript,
    propose_candidates,
    require_operation,
    require_reframe_mode,
    resolve_intelligence_task,
    run_full_offline,
    score_candidates,
    select_intelligence,
    subtitle_capabilities,
    validate_intelligence_document,
)
from universal_cutup.domain.assessments import (
    AggregateBundle,
    AssessmentBundle,
    CandidateProposalBundle,
)
from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.domain.intelligence import (
    ContentProfile,
    ControlMode,
    HostIntent,
    ResolvedTaskProfile,
)
from universal_cutup.domain.plans import CutPlan
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.sources import MediaBinding, MediaSource, RightsAttestation
from universal_cutup.domain.specs import (
    OutputSpec,
    QualityPreset,
    ReframeMode,
    ReframeSafeAreaPreset,
    ReframeSpec,
    RenderSpec,
    ResolutionMode,
    SubtitleMode,
    SubtitleSpec,
)
from universal_cutup.domain.transcript import TranscriptArtifact
from universal_cutup.providers.files import FileContentIntelligenceProvider
from universal_cutup.providers.sports import SportsFileProviderKind
from universal_cutup.providers.sports_text import SportsTextProfile
from universal_cutup.serialization import SerializationProfile, serialize_document

app = typer.Typer(no_args_is_help=True, help="CutSum offline media planning and execution engine.")


class SupportedSportsTextProfile(StrEnum):
    FOOTBALL = "football"
    AMERICAN_FOOTBALL = "american_football"
    RUGBY = "rugby"
    BASKETBALL = "basketball"
    TENNIS = "tennis"
    CRICKET = "cricket"


def _emit(value: BaseModel | dict[str, Any] | tuple[Any, ...]) -> None:
    def normalize(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json", exclude_none=True)
        if isinstance(item, dict):
            return {key: normalize(nested) for key, nested in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(nested) for nested in item]
        return item

    payload = normalize(value)
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _error(error: Exception) -> None:
    if isinstance(error, CutupError):
        payload = error.as_dict()
        exit_code = 3 if error.code is ErrorCode.CAPABILITY_UNAVAILABLE else 2
    else:
        payload = {
            "code": "INVALID_INPUT",
            "category": "validation",
            "message": str(error),
            "step": None,
            "recoverable": False,
            "details": {},
        }
        exit_code = 2
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True), err=True)
    raise typer.Exit(exit_code)


def _transcript(path: Path, source_id: str) -> TranscriptArtifact:
    return load_transcript(
        path,
        source_id=source_id,
        created_by="cutup-cli",
    )


def _sports_provider_kind(value: str) -> SportsFileProviderKind:
    supported = {"fixture", "host_ai_file", "human_file"}
    if value not in supported:
        raise CutupError(
            ErrorCode.PROTOCOL_INVALID,
            "unsupported sports observation provider kind",
            step="load_sports_observations",
            details={"provider_kind": value, "supported": sorted(supported)},
        )
    return cast(SportsFileProviderKind, value)


def _plan(path: Path) -> CutPlan:
    return load_cut_plan(path)


def _json_payload(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_no_overwrite(path: Path, document: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as file_handle:
        file_handle.write(document.model_dump_json(exclude_none=True))
        file_handle.write("\n")


def _emit_or_write(document: BaseModel, output: Path | None) -> None:
    if output is not None:
        _write_json_no_overwrite(output, document)
    _emit(document)


@app.command(name="blind-validate")
def blind_validate(
    blind_input: Path,
    blind_input_root: Path,
) -> None:
    """Validate an isolated Gate H input containing only raw artifacts and natural language."""
    try:
        validated = load_blind_run_input(blind_input, blind_input_root=blind_input_root)
        _emit({"valid": True, "blind_input": validated})
    except Exception as error:
        _error(error)


@app.command(name="blind-freeze")
def blind_freeze(
    result_root: Path,
    blind_run_id: str,
) -> None:
    """Hash-freeze blind results before any curated-reference comparison."""
    try:
        _emit(freeze_blind_run(result_root, blind_run_id=blind_run_id))
    except Exception as error:
        _error(error)


@app.command(name="blind-verify")
def blind_verify(manifest: Path) -> None:
    """Verify that a frozen blind run remains byte-identical."""
    try:
        _emit({"valid": True, "manifest": verify_frozen_blind_run(manifest)})
    except Exception as error:
        _error(error)


@app.command(name="blind-reference-open")
def blind_reference_open(reference: Path, manifest: Path) -> None:
    """Open curated reference only after the blind run passes freeze verification."""
    try:
        payload = load_reference_after_freeze(reference, manifest_path=manifest)
        _emit({"reference_opened_after_freeze": True, "reference": payload})
    except Exception as error:
        _error(error)


@app.command(name="intelligence-validate")
def intelligence_validate(
    kind: str,
    document: Path,
) -> None:
    """Validate a host/content/task/proposal/assessment intelligence document."""
    try:
        validated = validate_intelligence_document(kind, _json_payload(document))
        _emit({"valid": True, "kind": kind, "document": validated})
    except Exception as error:
        _error(error)


@app.command(name="intelligence-resolve")
def intelligence_resolve(
    host_intent: Path,
    content_profile: Path | None = None,
    output: Path | None = None,
) -> None:
    """Resolve host-first task strategy from strict local JSON."""
    try:
        intent = HostIntent.model_validate(_json_payload(host_intent))
        profile = (
            ContentProfile.model_validate(_json_payload(content_profile))
            if content_profile is not None
            else None
        )
        resolved = resolve_intelligence_task(intent, profile)
        _emit_or_write(resolved, output)
    except Exception as error:
        _error(error)


@app.command(name="intelligence-aggregate")
def intelligence_aggregate(
    proposals: Path,
    assessments: Path,
    resolved_task: Path,
    output: Path | None = None,
) -> None:
    """Compute authoritative adaptive Highlight14 aggregates."""
    try:
        proposal_preview = CandidateProposalBundle.model_validate(_json_payload(proposals))
        assessment_preview = AssessmentBundle.model_validate(_json_payload(assessments))
        proposal_import = FileContentIntelligenceProvider(
            provider_kind=proposal_preview.provider_kind
        ).import_proposals(proposals)
        assessment_import = FileContentIntelligenceProvider(
            provider_kind=assessment_preview.provider_kind
        ).import_assessments(assessments)
        proposal_bundle = proposal_import.artifact
        assessment_bundle = assessment_import.artifact
        task = ResolvedTaskProfile.model_validate(_json_payload(resolved_task))
        aggregates = aggregate_intelligence(proposal_bundle, assessment_bundle, task)
        _emit_or_write(aggregates, output)
    except Exception as error:
        _error(error)


@app.command(name="intelligence-select")
def intelligence_select(
    proposals: Path,
    assessments: Path,
    aggregates: Path,
    resolved_task: Path,
    output: Path | None = None,
) -> None:
    """Apply deterministic constraints, overlap, duplicate, and diversity selection."""
    try:
        proposal_bundle = CandidateProposalBundle.model_validate(_json_payload(proposals))
        assessment_bundle = AssessmentBundle.model_validate(_json_payload(assessments))
        aggregate_bundle = AggregateBundle.model_validate(_json_payload(aggregates))
        task = ResolvedTaskProfile.model_validate(_json_payload(resolved_task))
        selection = select_intelligence(
            proposal_bundle,
            assessment_bundle,
            aggregate_bundle,
            task,
        )
        _emit_or_write(selection, output)
    except Exception as error:
        _error(error)


@app.command(name="intelligence-plan")
def intelligence_plan(
    source: Path,
    proposals: Path,
    assessments: Path,
    resolved_task: Path,
    output: Path | None = None,
    quality_preset: QualityPreset = QualityPreset.REVIEW,
    resolution_mode: ResolutionMode = ResolutionMode.P720,
    allow_upscale: bool = False,
    subtitle_mode: SubtitleMode = SubtitleMode.NONE,
    translation_record: Path | None = None,
) -> None:
    """Aggregate, select, and emit a portable adaptive CutPlan."""
    try:
        media_source = MediaSource.model_validate(_json_payload(source))
        proposal_preview = CandidateProposalBundle.model_validate(_json_payload(proposals))
        assessment_preview = AssessmentBundle.model_validate(_json_payload(assessments))
        proposal_import = FileContentIntelligenceProvider(
            provider_kind=proposal_preview.provider_kind
        ).import_proposals(proposals)
        assessment_import = FileContentIntelligenceProvider(
            provider_kind=assessment_preview.provider_kind
        ).import_assessments(assessments)
        extra_provider_records = (
            (ProviderRecord.model_validate(_json_payload(translation_record)),)
            if translation_record is not None
            else ()
        )
        proposal_bundle = proposal_import.artifact
        assessment_bundle = assessment_import.artifact
        task = ResolvedTaskProfile.model_validate(_json_payload(resolved_task))
        aggregates = aggregate_intelligence(proposal_bundle, assessment_bundle, task)
        selection = select_intelligence(
            proposal_bundle,
            assessment_bundle,
            aggregates,
            task,
        )
        plan_document = create_adaptive_plan(
            media_source,
            proposal_bundle,
            assessment_bundle,
            task,
            selection,
            provider_records=(
                proposal_import.provider_record,
                assessment_import.provider_record,
                *extra_provider_records,
            ),
            output_spec=OutputSpec(
                render=RenderSpec(
                    quality_preset=quality_preset,
                    resolution_mode=resolution_mode,
                    allow_upscale=allow_upscale,
                ),
                subtitle=SubtitleSpec(
                    mode=subtitle_mode,
                    language="en",
                    translation_language=(
                        "zh-CN"
                        if subtitle_mode
                        in {
                            SubtitleMode.TRANSLATED_SIDECAR,
                            SubtitleMode.BILINGUAL_SIDECAR,
                            SubtitleMode.TRANSLATED_BURN_IN,
                            SubtitleMode.BILINGUAL_BURN_IN,
                        }
                        else None
                    ),
                ),
            ),
        )
        _emit_or_write(plan_document, output)
    except Exception as error:
        _error(error)


@app.command()
def inspect(media: Path, source_id: str | None = None) -> None:
    """Inspect local video or audio without cloud services."""
    try:
        _emit(inspect_source(media, source_id=source_id))
    except Exception as error:
        _error(error)


@app.command()
def analyze(transcript: Path, source_id: str = "source-cli") -> None:
    """Analyze an existing local transcript."""
    try:
        _emit(analyze_transcript(_transcript(transcript, source_id)))
    except Exception as error:
        _error(error)


@app.command()
def propose(transcript: Path, source_id: str = "source-cli") -> None:
    """Propose deterministic candidates."""
    try:
        _emit(propose_candidates(_transcript(transcript, source_id)))
    except Exception as error:
        _error(error)


@app.command()
def score(transcript: Path, source_id: str = "source-cli") -> None:
    """Score deterministic candidates."""
    try:
        parsed = _transcript(transcript, source_id)
        _emit(score_candidates(propose_candidates(parsed)))
    except Exception as error:
        _error(error)


@app.command()
def plan(
    media: Path,
    transcript: Path,
    output: Path | None = None,
    rights: RightsAttestation = RightsAttestation.ANALYSIS_ONLY,
    dry_run: bool = False,
) -> None:
    """Create a portable CutPlan."""
    try:
        inspection = inspect_source(media, rights_attestation=rights)
        parsed = _transcript(transcript, inspection.source.source_id)
        cut_plan = create_plan(inspection.source, parsed)
        serialized = serialize_document(cut_plan, profile=SerializationProfile.PORTABLE)
        if output is not None and not dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized + "\n", encoding="utf-8")
        _emit({"dry_run": dry_run, "plan": json.loads(serialized)})
    except Exception as error:
        _error(error)


@app.command()
def cut(plan_file: Path, media: Path, output_dir: Path, dry_run: bool = False) -> None:
    """Execute a portable CutPlan against an explicit local binding."""
    try:
        cut_plan = _plan(plan_file)
        if dry_run:
            _emit({"dry_run": True, "plan_id": cut_plan.plan_id})
            return
        execution = execute_cut_plan(
            cut_plan,
            binding=MediaBinding(
                source_id=cut_plan.source.source_id,
                local_path=str(media.resolve(strict=True)),
            ),
            output_root=output_dir,
        )
        _write_json_no_overwrite(output_dir / "execution-record.json", execution)
        _emit(execution)
        if execution.status != "success":
            raise typer.Exit(4)
    except typer.Exit:
        raise
    except Exception as error:
        _error(error)


@app.command()
def subtitle(plan_file: Path, media: Path, output_dir: Path) -> None:
    """Execute a plan that requests sidecar or burn-in subtitles."""
    cut(plan_file, media, output_dir)


@app.command()
def transcribe() -> None:
    """Report the offline provider boundary."""
    try:
        _emit(require_operation("transcribe"))
    except Exception as error:
        _error(error)


@app.command()
def translate() -> None:
    """Report the offline provider boundary."""
    try:
        _emit(require_operation("translate"))
    except Exception as error:
        _error(error)


@app.command()
def reframe(
    mode: str = "none",
    plan_file: Annotated[
        Path | None,
        typer.Option("--plan", help="Portable CutPlan to derive."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="New derived CutPlan path."),
    ] = None,
    focus_x: float | None = None,
    focus_y: float | None = None,
    safe_area: ReframeSafeAreaPreset = ReframeSafeAreaPreset.NONE,
    target_width: int | None = None,
    target_height: int | None = None,
    allow_upscale: bool = False,
) -> None:
    """Report reframe capability or derive a deterministic 9:16 CutPlan."""
    try:
        capability = require_reframe_mode(mode)
        if (plan_file is None) != (output is None):
            raise CutupError(
                ErrorCode.PROTOCOL_INVALID,
                "reframe plan and output must be provided together",
                step="reframe",
            )
        if plan_file is not None and output is not None:
            original = _plan(plan_file)
            render = RenderSpec.model_validate(
                {
                    **original.output_spec.render.model_dump(mode="python"),
                    "target_width": target_width,
                    "target_height": target_height,
                    "allow_upscale": allow_upscale,
                }
            )
            derived = configure_reframe(
                original,
                ReframeSpec(
                    mode=cast(ReframeMode, mode),
                    focus_x=focus_x,
                    focus_y=focus_y,
                    safe_area_preset=safe_area,
                ),
                render_spec=render,
            )
            _write_json_no_overwrite(output, derived)
            _emit(derived)
            return
        _emit({"mode": mode, "available": True, "capability": capability})
    except Exception as error:
        _error(error)


@app.command()
def package() -> None:
    """Report the packaging capability boundary."""
    try:
        _emit(require_operation("package"))
    except Exception as error:
        _error(error)


@app.command()
def capabilities() -> None:
    """Report machine-readable SDK and CLI operation capabilities."""
    _emit(capability_report())


@app.command(name="education-plan")
def education_plan(
    media: Path,
    transcript: Path,
    instruction: str = "",
    mode: ControlMode = ControlMode.AUTO,
    output: Path | None = None,
    rights: RightsAttestation = RightsAttestation.ANALYSIS_ONLY,
    quality_preset: QualityPreset = QualityPreset.REVIEW,
    resolution_mode: ResolutionMode = ResolutionMode.P720,
    topic_group: Annotated[
        list[str] | None,
        typer.Option(
            "--topic-group",
            help="Repeatable group of equivalent host-resolved terms separated by '|'.",
        ),
    ] = None,
) -> None:
    """Create an education AUTO/DIRECTED CutPlan from raw local transcript evidence."""
    try:
        inspection = inspect_source(media, rights_attestation=rights)
        parsed = _transcript(transcript, inspection.source.source_id)
        required_topic_groups = tuple(
            tuple(term.strip() for term in value.split("|") if term.strip())
            for value in (topic_group or [])
        )
        if any(not group for group in required_topic_groups):
            raise CutupError(
                ErrorCode.PROTOCOL_INVALID,
                "education topic groups require at least one non-blank term",
                step="education_plan",
            )
        result = plan_educational_content(
            inspection.source,
            parsed,
            control_mode=mode,
            raw_instruction=instruction,
            required_topic_groups=required_topic_groups,
            output_spec=OutputSpec(
                render=RenderSpec(
                    quality_preset=quality_preset,
                    resolution_mode=resolution_mode,
                )
            ),
        )
        if output is not None:
            _write_json_no_overwrite(output, result.plan)
        _emit(result)
    except Exception as error:
        _error(error)


@app.command(name="sports-plan")
def sports_plan(
    media: Path,
    observations: Path,
    instruction: str = "",
    mode: ControlMode = ControlMode.AUTO,
    provider_kind: str = "fixture",
    output: Path | None = None,
    rights: RightsAttestation = RightsAttestation.ANALYSIS_ONLY,
    quality_preset: QualityPreset = QualityPreset.REVIEW,
    resolution_mode: ResolutionMode = ResolutionMode.P720,
) -> None:
    """Create a sports AUTO/DIRECTED CutPlan from a validated observation file."""
    try:
        imported = load_sports_observations(
            observations,
            provider_kind=_sports_provider_kind(provider_kind),
        )
        inspection = inspect_source(
            media,
            source_id=imported.artifact.source_id,
            rights_attestation=rights,
        )
        result = plan_sports_content(
            inspection.source,
            imported.artifact,
            control_mode=mode,
            raw_instruction=instruction,
            provider_records=(imported.provider_record,),
            output_spec=OutputSpec(
                render=RenderSpec(
                    quality_preset=quality_preset,
                    resolution_mode=resolution_mode,
                )
            ),
        )
        if output is not None:
            _write_json_no_overwrite(output, result.plan)
        _emit(result)
    except Exception as error:
        _error(error)


@app.command(name="sports-transcript-plan")
def sports_transcript_plan(
    media: Path,
    transcript: Path,
    profile: SupportedSportsTextProfile,
    instruction: str = "",
    mode: ControlMode = ControlMode.AUTO,
    output: Path | None = None,
    rights: RightsAttestation = RightsAttestation.ANALYSIS_ONLY,
    quality_preset: QualityPreset = QualityPreset.REVIEW,
    resolution_mode: ResolutionMode = ResolutionMode.P720,
) -> None:
    """Detect transcript sports events and create an AUTO/DIRECTED CutPlan."""
    try:
        inspection = inspect_source(media, rights_attestation=rights)
        parsed = _transcript(transcript, inspection.source.source_id)
        result = plan_sports_transcript(
            inspection.source,
            parsed,
            profile=SportsTextProfile(profile.value),
            control_mode=mode,
            raw_instruction=instruction,
            output_spec=OutputSpec(
                render=RenderSpec(
                    quality_preset=quality_preset,
                    resolution_mode=resolution_mode,
                )
            ),
        )
        if output is not None:
            _write_json_no_overwrite(output, result.plan)
        _emit(result)
    except Exception as error:
        _error(error)


@app.command(name="full")
def full_pipeline(
    media: Path,
    transcript: Path,
    output_dir: Path,
    rights: RightsAttestation = RightsAttestation.OWNED,
    subtitle_mode: SubtitleMode = SubtitleMode.SOURCE_SIDECAR,
    dry_run: bool = False,
    max_clips: Annotated[
        int,
        typer.Option(
            "--max-clips",
            min=1,
            help="Maximum selected clips allowed before full execution is refused.",
        ),
    ] = DEFAULT_MAX_FULL_CLIPS,
) -> None:
    """Run inspect-to-render entirely offline."""
    try:
        inspection = inspect_source(media, rights_attestation=rights)
        parsed = _transcript(transcript, inspection.source.source_id)
        output_spec = OutputSpec(subtitle=SubtitleSpec(mode=subtitle_mode))
        if dry_run:
            cut_plan = create_plan(inspection.source, parsed, output_spec=output_spec)
            selected_clip_count = len(cut_plan.selection_result.selected_candidate_ids)
            _emit(
                {
                    "dry_run": True,
                    "analysis": analyze_transcript(parsed),
                    "selected_clip_count": selected_clip_count,
                    "maximum_clip_count": max_clips,
                    "within_output_limit": selected_clip_count <= max_clips,
                }
            )
            return
        result = run_full_offline(
            media,
            parsed,
            output_root=output_dir,
            rights_attestation=rights,
            output_spec=output_spec,
            maximum_clip_count=max_clips,
        )
        _write_json_no_overwrite(output_dir / "execution-record.json", result.execution)
        _emit(result)
    except Exception as error:
        _error(error)


@app.command(name="subtitle-capabilities")
def subtitle_capability_report() -> None:
    """Report sidecar and burn-in subtitle backend capabilities."""
    _emit(asdict(subtitle_capabilities()))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
