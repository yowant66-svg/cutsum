# Changelog

All notable changes will be documented here.

## Unreleased

## 0.1.0a4 — 2026-08-11

- Add `cutsum demo` as an installed, rights-safe, zero-network three-track execution proof.
- Bound subprocess diagnostic output while continuously draining stdout and stderr, retaining
  head/tail evidence, byte counts, truncation state, and termination signals.
- Package the repo-local `cutsum-intelligence` Skill as a reproducible OpenAI Plugin ZIP without
  duplicating its instruction source or claiming official marketplace inclusion.
- Add one-build Trusted Publishing gates for TestPyPI, PyPI, and GitHub Release distribution.
- Publish the first PyPI Alpha while retaining GitHub checksums, SBOM, provenance, and capability
  boundaries.

## 0.1.0a3 — 2026-08-10

- Return a valid, auditable empty sports CutPlan when transcript detection finds no qualified event.
- Extend explicit cancellation handling to delayed goal, try, touchdown, wicket, and point reversals
  while retaining the transcript-only heuristic Alpha boundary.
- Parse compound Chinese and multi-digit educational or sports clip counts without silently
  truncating hard constraints.
- Fail closed when one sports event class contains conflicting required and forbidden markers that
  the current protocol cannot represent safely.
- Reject an existing `execution-record.json` before `cut` or `full` renders media, and return a
  structured `OUTPUT_EXISTS` error for every no-overwrite JSON or plan output.
- Classify missing files, invalid JSON, permission failures, and unexpected CLI errors without
  leaking raw internal paths or mislabeling every exception as `INVALID_INPUT`.
- Keep the standalone Schema export script runnable directly from a clean source checkout.

## 0.1.0a2 — 2026-08-09

- Normalize quarter-turn video rotation metadata before resolution planning so rendered dimensions
  and `ExecutionRecord` provenance agree with the displayed media orientation.
- Reject candidates that materially exceed the declared source duration while allowing a 250 ms
  container-rounding tolerance.
- Redact standalone and embedded absolute filesystem paths from auditable process-error commands.
- Parse DIRECTED sports counts as whole, event-bound quantities so phrases such as `six saves`
  cannot also request a cricket score event and multi-digit counts remain intact.
- Refuse generic `full` execution above its default 24-clip safety limit unless the caller
  explicitly raises `--max-clips`, and expose the projected count in dry-run output.
- Add real FFmpeg pressure coverage for HEVC/AAC, AV1/Opus, variable frame rate, Unicode paths,
  rotation metadata, corrupt media, and media/transcript duration mismatch.
- Preserve independent educational clip boundaries, extend referential context, and enforce
  completeness at transcript-window edges.
- Enforce requested educational clip counts, output duration, and vertical canvas constraints.
- Bound subtitle cue duration, reading speed, vertical overlays, and bilingual display order.
- Reject unwritable output roots and unsupported audio burn-in before execution begins.
- Require auditable translation provenance before rendering translated or bilingual subtitles.
- Report correct media types for generated subtitle sidecars.
- Reserve one pixel of portrait ASS font height so libass background rounding stays within the
  single-language 14% subtitle-block limit across supported CI platforms.
- Render single-language burn-in from a canvas-aware ASS sidecar, redact POSIX absolute paths on
  Windows, and replace invalid subprocess output bytes without leaking or crashing reader threads.

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
