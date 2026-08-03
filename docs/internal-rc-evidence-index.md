# CutSum (formerly Universal Cutup) 0.1.0rc2 internal evidence index

更新时间：2026-08-01

This index records an internal Release Candidate. It is not a public release, an editorial-quality
certification, a legal clearance, or a Codex for Open Source application.

The internal RC predates the public `CutSum` branding decision. Its distribution name, hashes,
identifiers, and evidence references below are historical records and are intentionally unchanged.

## Frozen identities

- Distribution: `universal-cutup 0.1.0rc2`
- Python: `>=3.11,<3.14`
- Protocol Schema: `0.1.0` (independent from distribution version)
- Schema files: 22
- Schema integrity: every file matches `schemas/manifest.json`; two independent exports are
  byte-identical.
- Strategy identities remain their recorded deterministic, adaptive, education Alpha, or sports
  Alpha versions. The RC version bump does not silently relabel Alpha strategies as final.

## Final local quality evidence

- Tests: 287 passed on local macOS; branch coverage 87.70% (required minimum 85%).
- Ruff format/check: passed.
- mypy strict: passed for `src`, `tests`, and `scripts`.
- REUSE: 210/210 files carry copyright and license information; no bad or missing licenses.
- Dependency audit: no known third-party vulnerabilities; the unpublished project itself is skipped
  because it does not exist on PyPI.
- wheel SHA-256: `7473eb5056418fc046220a49062c20007dd67f7fbde8ed44f9cfc0e7cbbaa9ff`
- sdist SHA-256: recorded in the repository-external reviewed evidence to avoid making the source
  archive self-referential.
- Reproducibility: two consecutive builds produced byte-identical wheel and sdist artifacts.
- Distribution inventory: wheel contains package source plus LICENSE/NOTICE and excludes benchmark,
  evaluation, repo-local Skill, media, fonts, credentials, and local evidence.

## Fresh-wheel user evidence

`local-evidence://sports-hardening-2026-08-01/` records a fresh Python 3.12 environment that
installed the RC2 wheel and imported it from site-packages.

- Chain: owned synthetic basketball video + SRT → DIRECTED `只要一个绝杀` → decisive-score
  semantic qualification → StrategyRecord-linked CutPlan → verified 640×360 H.264/AAC clip.
- CutPlan SHA-256: `d5d7945cf359d0c9ab01a1c34b17a800a37a41b77b66e8f46723a693b5044ab5`.
- Output clip SHA-256: `706e8b43db385c6e72f6a2d20fd4c1c1d5bd5e4f873e612828ce41b72ed82831`;
  duration 9.52 seconds.
- Content processing made zero Provider/API calls. Dependency installation used the normal package
  index and is not described as an offline-install test.
- Historical RC1 education and 9:16 offline-install evidence remains under
  `local-evidence://install-rc1/` and is not relabeled as RC2 evidence.

Other maintained local evidence references:

- `local-evidence://education-v1/final-verified/`
- `local-evidence://sports-alpha/`
- `local-evidence://sports-hardening-2026-08-01/`
- `local-evidence://four-track-v1/`
- `local-evidence://basic-9x16-v2/`
- `local-evidence://subtitle-layout/`

## Milestone commits before RC freeze

- Gate J baseline: `50f63fb`
- Subtitle productization: `b7abf67`
- Education V1: `98643a1`
- Sports Alpha: `2b25173`
- Four-track evaluation: `8f16eca`
- SDK/CLI/Skill closure: `98b2e4d`
- Basic 9:16: `6d04ca3`
- Reliability and cross-platform configuration: `b208fba`
- Installation/open-source engineering readiness: `312eecf`

## Claims that remain prohibited

- Do not claim legal originality, non-infringement, trademark clearance, or public-release approval.
- Do not claim Linux/Windows CI passed until the checked-in workflow actually runs remotely.
- Do not convert synthetic or curated protocol regression into content-quality approval.
- Do not call fixed-focus composition face, speaker, or motion tracking.
- Do not claim real sports OCR, replay detection, audio classification, motion detection, ASR,
  translation, YouTube downloading, packaging, publishing, or upload automation exists in core.
- Do not treat a transcript `decisive_score` cue as verified score change, game clock, lead change,
  championship state, historical importance, or MatchState.

## Public-release blockers

The authoritative list remains `docs/open-source-readiness.md` and `docs/risk-register.md`. The
copyright holder, public project name, public contacts, DCO, and conduct policy are now selected.
The highest-priority open items are CutSum name/trademark review, private predecessor provenance
review, benchmark rights review, actual remote CI, repository-side DCO/security configuration, and
maintainer viewing of real output packs.
