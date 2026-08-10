# CutSum

CutSum is a provider-neutral engine for understanding long-form content, creating portable
clip plans, and rendering verified media outputs. It is designed for creators, course and podcast
teams, developers, automation workflows, and AI agents that need the same “find the right segment
and cut it” capability without coupling the workflow to one model or one video platform.

> Current release: [`0.1.0a3` public Alpha](https://github.com/yowant66-svg/cutsum/releases/tag/v0.1.0a3).
> The release is intentionally conservative: automated evidence proves engineering behavior, not
> universal editorial quality. Sports support remains transcript-only heuristic Alpha.

## What works now

- Local video/audio inspection and SRT, VTT, or JSON transcript loading.
- Portable, schema-validated CutPlan creation and no-overwrite execution.
- Host-first AUTO, GUIDED, and DIRECTED content planning with replaceable Highlight14 assessment.
- Education distillation for definitions, reasoning, examples, procedures, mistakes, and summaries.
- Sports-highlight Alpha from either a validated observation bundle or deterministic local
  transcript detection for football, American football, rugby, basketball, tennis, and cricket.
- Source, translated, and bilingual SRT/VTT/ASS sidecars plus capability-gated burn-in subtitles.
- Deterministic 9:16 center crop, manual focus, fit-over-blur, fixed-focus composition, and platform
  safe areas.
- Python SDK, CLI, and repository-local Codex/ChatGPT Skill using the same application logic.
- Offline deterministic operation with no API key; cloud or local model Providers can be added.

The current release does **not** download YouTube URLs, perform ASR or translation without a
configured Provider, verify sports events from audio/video/OCR, track faces or speakers, publish
media, or package platform uploads. Transcript-only sports detection is heuristic and explicitly
records that no cross-modal confirmation occurred. `fixed_subject` is a fixed-focus composition
mode, not detection or tracking.

## Requirements

- Python 3.11, 3.12, or 3.13.
- FFmpeg and ffprobe on `PATH` for media inspection and rendering.
- FFmpeg with libass for portable subtitle burn-in. On macOS, a Swift/AppKit system-font fallback is
  available when libass is absent. Sidecar subtitles remain available without a burn-in backend.

Check the real machine boundary before planning optional work:

```bash
cutsum capabilities
cutsum subtitle-capabilities
```

## Install

CutSum is not on PyPI. Install the reviewed wheel from the GitHub Alpha Release:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install \
  https://github.com/yowant66-svg/cutsum/releases/download/v0.1.0a3/cutsum-0.1.0a3-py3-none-any.whl
cutsum --help
```

Verify downloaded assets against `SHA256SUMS.txt` on the Release page before installation when the
distribution path is security-sensitive.

For development from a source checkout:

```bash
uv sync --locked --all-extras --dev
uv run cutsum capabilities
uv run pytest -q
```

## 5–10 minute rights-safe quickstart

Clone the repository after installing the reviewed Alpha wheel, then run one command to generate
owned synthetic media and produce playable interview, education, and sports examples:

```bash
python examples/run_quickstart.py cutsum-demo
```

The runner makes no network Provider calls and writes a shareable, machine-readable
`quickstart-report.json`. Follow the complete [5–10 minute quickstart](docs/quickstart.md) for
macOS, Linux, Windows PowerShell, expected outputs, and troubleshooting.

## Plan and cut your own authorized media

Use media you own or are authorized to edit. `--rights` is self-attestation and is not a legal
determination.

```bash
cutsum education-plan lecture.mp4 lecture.srt \
  --mode auto \
  --rights owned \
  --output lecture-plan.json

cutsum cut lecture-plan.json lecture.mp4 lecture-output
```

Create and execute a sports plan directly from a local transcript:

```bash
cutsum sports-transcript-plan game.mp4 commentary.srt basketball \
  --mode directed \
  --instruction "只要一个绝杀" \
  --rights owned \
  --output sports-plan.json

cutsum cut sports-plan.json game.mp4 sports-output
```

The public command accepts exactly `football`, `american_football`, `rugby`, `basketball`,
`tennis`, and `cricket`; unsupported sports are rejected instead of silently routed through a
generic detector. Profiles keep American football and rugby separate. The local detector filters common
hypothetical, replay, failed-attempt, and overturned-result language across a bounded adjacent-cue
context. Ambiguous rugby `try`, cricket `six`, and football `score` wording requires explicit event
language. A DIRECTED request for a buzzer beater, game winner, `绝杀`, or `压哨` requires a matching
textual narrative cue instead of accepting any earlier score. These are deterministic heuristics,
not MatchState: the detector does not infer score changes, game clock, equalizers, lead changes,
championship state, or historical importance, and it does not claim visual, audio, scoreboard, or
replay recognition.

Every selected clip is verified with ffprobe. The output directory is no-overwrite: rerunning into
the same paths returns a structured conflict instead of replacing files. Save the emitted
ExecutionRecord with the media when auditability matters.

The generic deterministic `cutsum full` command has a default 24-clip safety limit because it can
select one clip per transcript cue. Use `--dry-run` to inspect `selected_clip_count`; if a larger
batch is intentional, raise the bound explicitly with `--max-clips N` or create and inspect a
content-aware plan before execution.

Derive a new 9:16 plan without modifying the original:

```bash
cutsum reframe \
  --plan lecture-plan.json \
  --output lecture-vertical-plan.json \
  --mode fit_background \
  --safe-area youtube_shorts \
  --target-width 720 \
  --target-height 1280

cutsum cut lecture-vertical-plan.json lecture.mp4 lecture-vertical-output
```

For an explicit fixed point, choose `manual_focus` and provide normalized `--focus-x` and
`--focus-y` values between 0 and 1. Use `fit_background` when preserving the full source frame is
more important than filling the vertical canvas.

## Python SDK

Use the stable public surface, not internal application modules:

```python
from pathlib import Path

from universal_cutup.sdk import capability_report, execute_cut_plan, inspect_source, load_cut_plan

report = capability_report()
plan = load_cut_plan(Path("lecture-plan.json"))
inspection = inspect_source(
    Path("lecture.mp4"),
    source_id=plan.source.source_id,
    rights_attestation=plan.source.rights_attestation,
)
execution = execute_cut_plan(
    plan,
    binding=inspection.binding,
    output_root=Path("lecture-output"),
)
```

The distribution and project are named `cutsum`; the Python import namespace remains
`universal_cutup` for protocol and internal-RC continuity. The `cutsum` and legacy-compatible
`cutup` console commands invoke the same CLI.

See `universal_cutup.sdk.__all__` and the CLI help for the supported surface. SDK failures use
`CutupError`; CLI failures emit the same `code`, `category`, `step`, `recoverable`, and `details`
fields as JSON on stderr.

## Agent Skill

The repository-local Skill is in `.agents/skills/cutsum-intelligence/`. It tells a host
model to understand full transcripts while leaving validation, aggregation, selection, provenance,
and media execution to this package. The Skill does not contain a second ranking formula and does
not grant permission to download, publish, access credentials, or call paid Providers.

## Rights-safe examples

[`examples/`](examples/) contains three reproducible local workflows for interview-style,
educational, and sports-transcript planning. The examples use FFmpeg-generated test media and
maintainer-authored synthetic transcripts, so no downloaded media or third-party transcript is
required. Real testers can use the [public trial kit](docs/trial-kit/README.md) to record what they
personally ran and inspected without sharing private source material.

## Architecture and evidence

The dependency direction is:

```text
domain → application / strategies → media / providers → SDK / CLI / Skill
```

CutPlan is the portable boundary between analysis and execution. Provider records, evidence refs,
strategy versions, source hashes, rights attestation, execution steps, artifact hashes, crop
geometry, and subtitle timing precision remain explicit.

Automated benchmark success proves protocol or deterministic regression behavior only. It does not
prove that every selected clip is editorially good. Evidence classes and pending human review are
preserved instead of being converted into a content-quality claim.

Useful documents:

- [Release readiness](docs/release-readiness.md)
- [Risk register](docs/risk-register.md)
- [Engineering decisions](docs/decisions.md)
- [Open-source readiness](docs/open-source-readiness.md)
- [Standard benchmark boundary](docs/standard-benchmark-v1.md)

## Privacy, rights, and safety

- No credentials, cookies, private media, generated videos, or fonts belong in the repository.
- Local paths are accepted only where execution requires an explicit binding; auditable subprocess
  commands redact the home-directory prefix and common credential flags.
- Editing requires `owned`, `licensed`, `public_domain`, or `authorized_other` attestation.
- Source files are hash-checked before and after execution and are never overwritten.
- Benchmark source and rights notes are engineering records, not legal advice or final clearance.

Read [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), [NOTICE](NOTICE), and
[LICENSE](LICENSE) before sharing a build or contribution.

## Development gates

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests scripts
uv run pytest -q
uv run reuse lint
uv run pip-audit
uv build
git diff --check
```

The checked-in CI is read-only and contains no PyPI publish job. GitHub-hosted Ubuntu, macOS, and
Windows runs verify Python 3.11, while Ubuntu additionally verifies Python 3.12 and 3.13. A separate
job enforces at least 85% branch coverage, and pull requests require DCO sign-off.
