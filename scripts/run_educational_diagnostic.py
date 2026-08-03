from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from universal_cutup.application.educational import (
    create_educational_plan,
    propose_educational_candidates,
    resolve_educational_request,
    select_educational_for_request,
)
from universal_cutup.application.sdk import execute_cut_plan
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sources import MediaBinding, MediaSource
from universal_cutup.domain.specs import (
    OutputSpec,
    QualityPreset,
    RenderSpec,
    ResolutionMode,
    SubtitleMode,
    SubtitleSpec,
)
from universal_cutup.domain.transcript import TranscriptArtifact


def _write_model(path: Path, model: BaseModel) -> None:
    path.write_text(model.model_dump_json(indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and render an educational plan from a raw transcript without "
            "candidate IDs or reference timestamps."
        )
    )
    parser.add_argument("transcript", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("media", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--mode",
        type=ControlMode,
        choices=(ControlMode.AUTO, ControlMode.DIRECTED),
        default=ControlMode.AUTO,
    )
    parser.add_argument("--instruction", default="")
    args = parser.parse_args()

    transcript = TranscriptArtifact.model_validate_json(args.transcript.read_text())
    source = MediaSource.model_validate_json(args.source.read_text())
    request = resolve_educational_request(args.mode, args.instruction)
    candidates = propose_educational_candidates(transcript)
    selection = select_educational_for_request(candidates, request)
    output_spec = OutputSpec(
        render=RenderSpec(
            quality_preset=QualityPreset.REVIEW,
            resolution_mode=ResolutionMode.P720,
        ),
        subtitle=SubtitleSpec(
            mode=SubtitleMode.SOURCE_BURN_IN,
            language=transcript.language,
        ),
    )
    plan = create_educational_plan(
        source,
        transcript,
        request,
        output_spec=output_spec,
    )
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    _write_model(output_root / "educational-request.json", request)
    (output_root / "educational-candidates.json").write_text(
        "[\n"
        + ",\n".join(candidate.model_dump_json(indent=2) for candidate in candidates)
        + "\n]\n"
    )
    _write_model(output_root / "educational-selection.json", selection)
    _write_model(output_root / "cut-plan.json", plan)
    execution = execute_cut_plan(
        plan,
        binding=MediaBinding(
            source_id=source.source_id,
            local_path=str(args.media.resolve(strict=True)),
        ),
        output_root=output_root,
    )
    _write_model(output_root / "execution-record.json", execution)
    print(execution.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
