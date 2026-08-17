# Protocol workflow

The package exports authoritative schemas in `schemas/`.

Required document order:

1. `host-intent.schema.json`
2. `content-profile.schema.json` when AUTO or content inference is needed
3. `resolved-task-profile.schema.json`
4. `candidate-proposal-bundle.schema.json`
5. `assessment-bundle.schema.json`
6. `adaptive-selection-result.schema.json`

For host model routing, validate:

- `model-routing-decision.schema.json`

The decision contains a provider-neutral task and tier, not permission to call a provider. A
`blocked` decision must remain blocked until the host changes the tier ceiling, frontier-call
budget, or task requirements. Actual calls are recorded in ProviderRecord with the decision ID,
actual model ID, escalation reasons, and known cost.

For education-first workflows, also validate:

- `educational-task-request.schema.json`
- `educational-selection-result.schema.json`
- the final portable `cut-plan.schema.json`

For sports workflows, validate:

- `sports-observation-bundle.schema.json`
- `sports-task-request.schema.json`
- `sports-selection-result.schema.json`
- the final portable `cut-plan.schema.json`

For four-track evaluation, validate:

- `four-track-evaluation-manifest.schema.json`
- `four-track-evaluation-report.schema.json`
- `blind-run-input.schema.json`
- `blind-run-freeze-manifest.schema.json`

`pass@1`, `pass^k`, and capability pass rate describe protocol or deterministic behavior only.
Preserve `real_local`, `synthetic`, or `curated_protocol` evidence class and the human-review
status. Freeze blind output before reference loading; suite, case, and track identity must match.

All documents:

- use schema version `0.1.0`;
- use UTC timestamps;
- reject unknown fields;
- preserve source, evidence, provider, and strategy identities;
- carry fixture or provider provenance truthfully.

The 14 stable dimension keys are:

`insight`, `novelty`, `emotion`, `quotability`, `hook`, `standalone`, `clarity`,
`completion`, `shareability`, `silent_watchability`, `pace`, `editability`,
`subtitle_reliability`, `visual_independence`.

Every ResolvedTaskProfile registers all 14. Every candidate assessment supplies one entry for every
dimension. Use `unavailable_reason` instead of `score` when the evidence cannot support a score.
The core decides whether that unavailable value is advisory, disqualifying, or not applicable.

For bilingual display, `CutCandidate.subtitle_cues` remains immutable transcript evidence.
`subtitle_word_timings` records real or estimated word timing explicitly, and
`subtitle_semantic_spans` records sentence/clause/phrase grouping without modifying source evidence.
`contextual_translation_records` maps one or more source cue IDs to a context-aware translation,
and `subtitle_display_units` derives its time range from those covered cues. English/translation
layout wrapping is independent of timeline segmentation.

Sidecar formats are `srt`, `vtt`, or `ass`; modes may be source, translated, or bilingual.
Burn-in requires `ffmpeg-libass` or the declared macOS system overlay fallback. Never conceal an
unavailable burn-in backend.

For deterministic vertical delivery, `ReframeSpec` supports `center_crop`, `manual_focus`,
`fit_background`, and `fixed_subject`. Explicit vertical dimensions must be even 9:16 values;
upscaling requires an explicit opt-in. Platform safe-area selection is shared with subtitles.
`ExecutionRecord` stores typed crop box, normalized focus, output anchor, safe-area rectangle, and
composition reason. `tracked_focus` is unavailable, and `fixed_subject` never implies detection.

For lecture/course content, `education_signals` carries typed evidence for
`educational_distillation`. Teacher emphasis is supporting evidence and cannot qualify a candidate
without a structural teaching signal. `EducationalCandidateProfile` records key terms, context
roles, completeness confidence, and visual dependency types. A transcript proposal may retain an
unqualified candidate for audit, but AUTO selection rejects missing context and insufficient
statements. The default education window is 15–60 seconds; required context may extend to 120
seconds with an explicit reason, and longer material becomes ordered Parts. Topic-specific
DIRECTED education requests carry `required_topic_groups`. Every group is required, while terms
inside one group are alternatives in the transcript language. Topic qualification normally uses
the candidate's core semantic statement. A dependent statement such as one beginning with
`because` may also use the immediately required complete context, but an ordinary candidate cannot
borrow a topic from neighboring text added only for a clean media boundary. Unresolved topic
instructions and missing groups are explicit unsatisfied requirements.

`SportsObservationBundle` is detector output, not a selection verdict. Each observation records
modality, temporal role, confidence, correlation key, and Provider record. The core aggregates
observations into primary events and linked replay events. AUTO requires cross-modal confirmation,
a strong scoreboard outcome, or a high-confidence explicit textual outcome. Transcript-only
detection must remain labeled `provider_kind=local_detector` and retain its
no-audio/video/OCR Provider warning. AUTO rejects isolated peaks and excludes replay-only
duplicates by default. DIRECTED decisive-score requests require an explicit narrative cue, while
the cue remains transcript-only and must not be described as verified MatchState. Synthetic fixture
observations must remain labeled `provider_kind=fixture`.

Resolution priority:

`host_explicit > host_preset > content_inference > system_capability > fallback`

Capability boundaries may prevent execution but must not rewrite host intent.

Stable entrypoints:

- Python: `from universal_cutup.sdk import ...`
- Capability discovery: `cutsum capabilities`
- Education planning: `cutsum education-plan MEDIA TRANSCRIPT`
- Sports planning: `cutsum sports-plan MEDIA OBSERVATIONS`
- Local sports transcript planning: `cutsum sports-transcript-plan MEDIA TRANSCRIPT PROFILE`
- Vertical plan derivation: `cutsum reframe --plan PLAN --output DERIVED_PLAN --mode MODE`
- Plan execution: `cutsum cut PLAN MEDIA OUTPUT_DIR`

CLI errors are JSON on stderr. Preserve `code`, `category`, `message`, `step`, `recoverable`, and
`details`; SDK callers receive the same information from `CutupError.as_dict()`.
