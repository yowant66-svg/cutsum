# Changelog

All notable changes will be documented here.

## Unreleased

- Normalize quarter-turn video rotation metadata before resolution planning so rendered dimensions
  and `ExecutionRecord` provenance agree with the displayed media orientation.
- Reject candidates that materially exceed the declared source duration while allowing a 250 ms
  container-rounding tolerance.
- Redact standalone and embedded absolute filesystem paths from auditable process-error commands.
- Add real FFmpeg pressure coverage for HEVC/AAC, AV1/Opus, variable frame rate, Unicode paths,
  rotation metadata, corrupt media, and media/transcript duration mismatch.

## 0.1.0a1 — 2026-08-04

- Adopted the public project and distribution identity `CutSum` / `cutsum`, with `DXBATM` as the
  copyright holder and `yowant66@gmail.com` as the maintainer and security contact.
- Added DCO 1.1 sign-off policy and Contributor Covenant 2.1 governance.
- Added the `cutsum` CLI while preserving `cutup`, the `universal_cutup` import namespace, and stable
  protocol/evidence identifiers for compatibility.
- Carried forward the frozen transcript-only heuristic Sports Alpha after its final six-case context
  regression and 293-test review.
- Added verified Ubuntu, macOS, and Windows CI, an explicit 85% branch-coverage gate, DCO
  enforcement, protected-main governance, and GitHub security reporting.
- Added three rights-safe public examples, deterministic release manifests, CycloneDX 1.6 SBOM,
  SHA-256 checksums, and fresh-wheel media execution evidence.
- Published wheel and source distribution on GitHub. No PyPI package is published by this release.

## 0.1.0rc2 — Internal sports-hardening candidate, not publicly released

- Hardened the transcript-only Sports Alpha against ambiguous rugby, cricket, and football terms;
  added bounded cross-cue context, multi-event captions, rolling-caption deduplication, and
  decisive-score intent qualification.
- Added sports StrategyRecord provenance, candidate-specific rejection reasons, and bounded
  transcript excerpts in EvidenceRef snapshots.

## 0.1.0rc1 — Internal candidate, not publicly released

- Added portable CutPlan creation and verified, no-overwrite local media execution.
- Added semantic source/translated/bilingual subtitles and capability-gated burn-in.
- Added education V1, sports Alpha, adaptive Highlight14, and four-track regression protocols.
- Added stable Python SDK, CLI, repository-local Skill, and structured capability/error contracts.
- Added deterministic 9:16 composition and platform subtitle safe areas.
- Hardened path validation, process cancellation, output rollback ownership, privacy redaction, and
  read-only cross-platform CI configuration.
- Froze 22 protocol schemas, reproducible wheel/sdist hashes, and a media-free internal review pack.
- Public release remains blocked on the open items in `docs/open-source-readiness.md`.
