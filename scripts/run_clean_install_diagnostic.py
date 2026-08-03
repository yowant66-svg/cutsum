from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    arguments: list[str],
    *,
    cwd: Path,
    timeout: float = 60,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    try:
        return subprocess.run(
            arguments,
            cwd=cwd,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"command failed with exit {error.returncode}: {arguments[0]}\n{error.stderr[-4000:]}"
        ) from error


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _generate_source(path: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25:duration=40",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=40",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        cwd=path.parent,
    )


def _write_transcript(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:00,000 --> 00:00:08,000",
                (
                    "Binary search is an algorithm that finds a target in a sorted list by "
                    "repeatedly halving the search interval."
                ),
                "",
                "2",
                "00:00:08,000 --> 00:00:16,000",
                (
                    "The rule is to compare the middle value with the target, then keep only "
                    "the half that can still contain it."
                ),
                "",
                "3",
                "00:00:16,000 --> 00:00:24,000",
                (
                    "For example, when searching for seven in one through fifteen, compare "
                    "eight first and continue in the lower half."
                ),
                "",
                "4",
                "00:00:24,000 --> 00:00:32,000",
                (
                    "A common mistake is applying binary search to unsorted data, because "
                    "discarding half is no longer logically valid."
                ),
                "",
                "5",
                "00:00:32,000 --> 00:00:40,000",
                (
                    "In summary, sorting provides the invariant and repeated halving gives "
                    "logarithmic search complexity."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def _environment_python(environment_root: Path) -> Path:
    return environment_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _install_fresh(
    uv: str,
    wheel: Path,
    environment_root: Path,
    *,
    python_version: str,
) -> Path:
    _run(
        [uv, "venv", "--python", python_version, str(environment_root)],
        cwd=environment_root.parent,
    )
    python = _environment_python(environment_root)
    _run(
        [
            uv,
            "pip",
            "install",
            "--offline",
            "--python",
            str(python),
            str(wheel),
        ],
        cwd=environment_root.parent,
    )
    return environment_root / ("Scripts/cutup.exe" if os.name == "nt" else "bin/cutup")


def _media_artifacts(record_path: Path, output_root: Path) -> list[Path]:
    record = json.loads(record_path.read_text(encoding="utf-8"))
    return [
        output_root / item["relative_path"]
        for item in record["artifacts"]
        if item["artifact_type"] in {"video", "audio"}
    ]


def _probe(path: Path, *, cwd: Path) -> dict[str, Any]:
    completed = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(path),
        ],
        cwd=cwd,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def _artifact_evidence(paths: list[Path], *, evidence_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(path.relative_to(evidence_root)),
            "sha256": _sha256(path),
            "ffprobe": _probe(path, cwd=evidence_root),
        }
        for path in paths
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify two fresh-wheel offline user chains.")
    parser.add_argument("wheel", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--python-version", default="3.12")
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    source = output_root / "owned-synthetic-lecture.mp4"
    transcript = output_root / "owned-synthetic-lecture.srt"
    _generate_source(source)
    _write_transcript(transcript)
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for the clean-install diagnostic")

    with TemporaryDirectory(prefix="universal-cutup-clean-a-") as first_temp:
        first_environment = Path(first_temp) / "venv"
        first_cutup = _install_fresh(
            uv,
            wheel,
            first_environment,
            python_version=args.python_version,
        )
        first_import = _run(
            [
                str(_environment_python(first_environment)),
                "-c",
                "import universal_cutup; print(universal_cutup.__file__)",
            ],
            cwd=output_root,
        ).stdout.strip()
        first_python_version = _run(
            [
                str(_environment_python(first_environment)),
                "--version",
            ],
            cwd=output_root,
        ).stdout.strip()
        package_version = _run(
            [
                str(_environment_python(first_environment)),
                "-c",
                "import universal_cutup; print(universal_cutup.__version__)",
            ],
            cwd=output_root,
        ).stdout.strip()
        first_capabilities = json.loads(
            _run([str(first_cutup), "capabilities"], cwd=output_root).stdout
        )
        horizontal_plan = output_root / "education-auto-plan.json"
        _run(
            [
                str(first_cutup),
                "education-plan",
                str(source),
                str(transcript),
                "--mode",
                "auto",
                "--rights",
                "owned",
                "--quality-preset",
                "preview",
                "--resolution-mode",
                "360p",
                "--output",
                str(horizontal_plan),
            ],
            cwd=output_root,
        )
        horizontal_output = output_root / "chain-a-horizontal"
        _run(
            [str(first_cutup), "cut", str(horizontal_plan), str(source), str(horizontal_output)],
            cwd=output_root,
            timeout=120,
        )

    with TemporaryDirectory(prefix="universal-cutup-clean-b-") as second_temp:
        second_environment = Path(second_temp) / "venv"
        second_cutup = _install_fresh(
            uv,
            wheel,
            second_environment,
            python_version=args.python_version,
        )
        second_import = _run(
            [
                str(_environment_python(second_environment)),
                "-c",
                "import universal_cutup; print(universal_cutup.__file__)",
            ],
            cwd=output_root,
        ).stdout.strip()
        vertical_plan = output_root / "vertical-derived-plan.json"
        _run(
            [
                str(second_cutup),
                "reframe",
                "--plan",
                str(horizontal_plan),
                "--output",
                str(vertical_plan),
                "--mode",
                "fit_background",
                "--safe-area",
                "youtube_shorts",
                "--target-width",
                "360",
                "--target-height",
                "640",
            ],
            cwd=output_root,
        )
        vertical_output = output_root / "chain-b-vertical"
        _run(
            [str(second_cutup), "cut", str(vertical_plan), str(source), str(vertical_output)],
            cwd=output_root,
            timeout=120,
        )

    horizontal_record = horizontal_output / "execution-record.json"
    vertical_record = vertical_output / "execution-record.json"
    horizontal_media = _media_artifacts(horizontal_record, horizontal_output)
    vertical_media = _media_artifacts(vertical_record, vertical_output)
    manifest = {
        "evidence_class": "synthetic_owned_local",
        "network_provider_calls": 0,
        "python_version": args.python_version,
        "installed_python": first_python_version,
        "package_version": package_version,
        "workflow_commands": [
            "uv pip install --offline --python <fresh-python> <wheel>",
            "cutup education-plan <media> <srt> --mode auto --rights owned --output <plan>",
            "cutup cut <plan> <media> <horizontal-output>",
            "cutup reframe --plan <plan> --output <vertical-plan> --mode fit_background",
            "cutup cut <vertical-plan> <media> <vertical-output>",
        ],
        "wheel": {"name": wheel.name, "sha256": _sha256(wheel)},
        "source": {"name": source.name, "sha256": _sha256(source)},
        "chain_a": {
            "fresh_import": first_import,
            "plan": horizontal_plan.name,
            "execution_record": str(horizontal_record.relative_to(output_root)),
            "artifacts": _artifact_evidence(horizontal_media, evidence_root=output_root),
            "media_runtime": first_capabilities["media_runtime"],
        },
        "chain_b": {
            "fresh_import": second_import,
            "derived_from": horizontal_plan.name,
            "plan": vertical_plan.name,
            "execution_record": str(vertical_record.relative_to(output_root)),
            "artifacts": _artifact_evidence(vertical_media, evidence_root=output_root),
        },
    }
    _write_json(output_root / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
