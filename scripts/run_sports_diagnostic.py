from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel

from universal_cutup.application.sdk import (
    create_sports_plan,
    execute_cut_plan,
    inspect_source,
    propose_sports_candidates,
    resolve_sports_request,
    select_sports_for_request,
)
from universal_cutup.domain.intelligence import ControlMode
from universal_cutup.domain.sources import RightsAttestation
from universal_cutup.domain.specs import (
    OutputSpec,
    QualityPreset,
    RenderSpec,
    ResolutionMode,
)
from universal_cutup.providers.sports import FileSportsObservationProvider


def _write_model(path: Path, model: BaseModel) -> None:
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render sports highlights from a validated observation bundle."
    )
    parser.add_argument("media", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--mode",
        type=ControlMode,
        choices=(ControlMode.AUTO, ControlMode.DIRECTED),
        default=ControlMode.AUTO,
    )
    parser.add_argument("--instruction", default="")
    args = parser.parse_args()

    provider = FileSportsObservationProvider(provider_kind="fixture")
    imported = provider.import_observations(args.observations)
    inspection = inspect_source(
        args.media,
        source_id=imported.artifact.source_id,
        rights_attestation=RightsAttestation.OWNED,
    )
    request = resolve_sports_request(args.mode, args.instruction)
    candidates = propose_sports_candidates(
        imported.artifact,
        media_duration_ms=inspection.source.duration_ms or 0,
    )
    selection = select_sports_for_request(candidates, request)
    plan = create_sports_plan(
        inspection.source,
        imported.artifact,
        request,
        provider_records=(imported.provider_record,),
        output_spec=OutputSpec(
            render=RenderSpec(
                quality_preset=QualityPreset.REVIEW,
                resolution_mode=ResolutionMode.P720,
            )
        ),
    )
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    _write_model(output_root / "sports-request.json", request)
    (output_root / "sports-candidates.json").write_text(
        "[\n"
        + ",\n".join(candidate.model_dump_json(indent=2) for candidate in candidates)
        + "\n]\n",
        encoding="utf-8",
    )
    _write_model(output_root / "sports-selection.json", selection)
    _write_model(output_root / "cut-plan.json", plan)
    execution = execute_cut_plan(
        plan,
        binding=inspection.binding,
        output_root=output_root,
    )
    _write_model(output_root / "execution-record.json", execution)
    print(execution.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
