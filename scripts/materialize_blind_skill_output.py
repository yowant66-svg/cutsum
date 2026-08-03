from __future__ import annotations

import argparse
import json
from pathlib import Path

from universal_cutup.application.skill_materialization import materialize_skill_output
from universal_cutup.domain.sources import RightsAttestation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize one raw repo-local Skill judgment into strict Gate H artifacts."
    )
    parser.add_argument("blind_input", type=Path)
    parser.add_argument("skill_output", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--rights",
        type=RightsAttestation,
        choices=list(RightsAttestation),
        required=True,
    )
    args = parser.parse_args()
    result = materialize_skill_output(
        args.blind_input,
        args.skill_output,
        args.output_root,
        rights_attestation=args.rights,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
