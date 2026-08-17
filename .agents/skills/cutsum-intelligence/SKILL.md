---
name: cutsum-intelligence
description: Analyze complete local transcripts and translate host editing intent into validated CutSum content profiles, adaptive Highlight14 assessments, resolved task profiles, and offline cut plans. Use for AUTO, GUIDED, DIRECTED, PLAN ONLY, or EXECUTE EXISTING PLAN workflows involving SRT, VTT, JSON transcripts, or existing portable CutPlan files.
---

# CutSum Intelligence

Use the host model for content understanding. Use the Python package as the only authority for
validation, aggregation, selection, provenance, and media execution.

For Python integrations, import the stable surface from `universal_cutup.sdk`, not the internal
`universal_cutup.application` modules. Run `cutsum capabilities` before selecting an optional
operation; preserve the returned state and structured error instead of guessing that a provider or
media feature exists.

## Route model work

Before each host-model stage, run `cutsum model-route TASK` with every observed `--reason`, the
host's `--maximum-tier`, and the remaining `--frontier-calls-remaining` budget when one is set.
Map the returned provider-neutral tier to an actually available host model. Never silently replace
a blocked or required tier with a weaker model. If tiered delegation is unavailable, disclose that
the current host model performed the stage instead of claiming cost-aware routing occurred.

Keep validation, hashing, aggregation, selection arithmetic, subtitle layout, and FFmpeg execution
deterministic. Use economy for bulk cleanup and prefiltering, balanced for normal semantic planning,
and frontier only for required ambiguity resolution or final editorial review. Every actual model
call must create a `ProviderRecord` containing the routing decision, actual `model_id`, and known
cost. Read [references/model-routing.md](references/model-routing.md) for the task table, escalation
rules, budget behavior, and provenance fields.

## Choose the mode

- **AUTO**: Read the complete transcript, infer a multi-label ContentProfile, then resolve strategy.
- **GUIDED**: Preserve supplied count, duration, audience, platform, or other partial requirements;
  infer only missing decisions.
- **DIRECTED**: Preserve the raw instruction and every explicit constraint. Surface conflicts; never
  silently replace the requested objective.
- **PLAN ONLY**: Stop after producing and validating portable plan artifacts.
- **EXECUTE EXISTING PLAN**: Do not reinterpret content. Bind the existing plan to the explicit local
  media path and execute it.

## Workflow

1. Read the entire transcript and retain the exact host instruction.
2. Write `host-intent.json`. Keep `raw_instruction`; represent unknown requests in
   `unrecognized_requirements`.
3. For AUTO or content-aware GUIDED work, write `content-profile.json` with multiple labels when
   appropriate, evidence references, confidence, dependencies, and content tracks.
4. Run `cutsum intelligence-validate` on every generated JSON file.
5. Run `cutsum intelligence-resolve` to produce `resolved-task-profile.json`. Do not compute weights
   outside the core.
6. For lecture/course content, run `educational_distillation` qualification before general
   Highlight14 assessment. Preserve definitions, rules, reasoning, examples, procedures, summaries,
   mistakes, difficult points, teacher emphasis, and exam relevance as typed education signals.
   Start from the raw `TranscriptArtifact` with `propose_educational_candidates`; do not pass
   candidate IDs or reference timestamps as proposal input. Use `resolve_educational_request` for
   AUTO or pure natural-language DIRECTED intent, then `create_educational_plan` for a portable
   plan. AUTO must prefer distinct, self-contained knowledge types rather than repeated mentions of
   the same concept. For a topic-specific DIRECTED request, resolve each required concept into one
   group of transcript-language alternatives and repeat `--topic-group` for every required concept;
   separate alternatives inside a group with `|`. This is semantic qualification, not candidate
   steering: never supply candidate IDs or timestamps. If the host cannot resolve the topic groups,
   leave them absent and preserve the explicit `educational_topic_constraints_unresolved` result;
   the engine must fail closed instead of selecting an unrelated structural match.
   For a local planning entrypoint, use `cutsum education-plan MEDIA TRANSCRIPT` with `--mode auto`,
   or `--mode directed --instruction "..." --topic-group "term|equivalent"`. `--output` writes the
   portable CutPlan; stdout retains the full request/candidates/selection/plan result.
7. Generate cross-segment candidates and all 14 evidence-backed assessments. Mark an inapplicable
   dimension unavailable; never give it a zero merely because it is not applicable. Education
   eligibility and structure remain authoritative; Highlight14 is supplementary.
8. For sports content, require a validated `SportsObservationBundle` before
   `sports_highlight` selection. For an existing observation bundle, use
   `cutsum sports-plan MEDIA OBSERVATIONS` with the truthful `--provider-kind`; never relabel a
   fixture as detector output. For local SRT/VTT/JSON evidence, use
   `cutsum sports-transcript-plan MEDIA TRANSCRIPT PROFILE`; profiles keep American football and
   rugby separate. The deterministic transcript Provider may qualify explicit textual outcomes,
   carries a bounded adjacent-cue context, and distinguishes explicit decisive-score language from
   an ordinary score for DIRECTED requests. Its ProviderRecord must retain the
   no-audio/video/OCR warning. Textual decisive language is a narrative cue, not verified
   MatchState, score change, game clock, lead change, or championship state.
   A single audio peak or shot change is not a highlight. Neither is an ambiguous attempt or
   hypothetical/replay mention. AUTO excludes replay-only duplicates; DIRECTED may explicitly
   request replay inclusion.
9. For translated subtitles, group original cues into semantic sentences first. Translate each
   semantic unit with preceding/following context and a stable glossary, then materialize
   `SubtitleDisplayUnit` records. Preserve `exact` versus `estimated` timing precision.
   Layout wrapping must never create new timeline cues.
10. Before burn-in, run `cutsum subtitle-capabilities`. If the selected backend is `unavailable`,
   offer source, translated, or bilingual SRT/VTT/ASS sidecar output and report the limitation.
11. Evaluate subtitle readability for semantic fragments, characters per second, and visual line
   pressure. File generation alone is not a readability pass.
12. Run `cutsum intelligence-aggregate`, then `cutsum intelligence-select`.
13. Explain the inferred content type, host overrides, assumptions, selected evidence, and any
   unsatisfied constraints.
14. For evaluation, preserve the declared evidence class and human-review state. Report `pass@1`
   and `pass^k` only as protocol, capability, or deterministic-regression evidence; never convert
   them into a content-quality claim.
15. Before vertical delivery, choose a declared 9:16 mode: `center_crop` for centered material,
   `manual_focus` for a host-supplied normalized focus point, `fit_background` when preserving the
   full frame matters, or `fixed_subject` for an explicit/default fixed focus. Derive a new portable
   plan with `cutsum reframe --plan PLAN --output DERIVED_PLAN --mode MODE`; select a platform safe
   area so subtitle and composition constraints stay synchronized. `fixed_subject` performs no
   detection or tracking and may match center crop when its assumed focus is centered.
16. For PLAN ONLY, stop. For execution, call the existing `cutsum cut` path with an explicit local
   binding and rights attestation already present in the plan.

Read [references/protocol-workflow.md](references/protocol-workflow.md) before authoring JSON.

## Boundaries

- Do not embed a second scoring or ranking formula in this Skill.
- Do not translate or retime individual micro-cues merely to force equal source/translation counts.
- Do not treat viral, balanced, knowledge, or narrative as the universal default.
- Do not accept a model-reported overall score as authoritative.
- Do not call network providers, download media, publish, or access credentials without separate
  authorization.
- Do not bypass a blocked model-routing decision or hide a silent downgrade behind a generic
  ProviderRecord.
- Preserve `CutupError` fields `code`, `category`, `step`, `recoverable`, and `details`. A
  `provider_required` or `unavailable` capability report is an explicit boundary, not permission to
  install, configure, or silently substitute a provider.
- Do not hide host/content/capability conflicts.
- Do not treat a keyword mention, a named theorem without explanation, or a sentence that points to
  missing previous/following context as a complete educational clip.
- Do not claim that CutSum currently performs sports OCR, replay recognition, audio
  classification, or motion detection. The local transcript Provider detects explicit textual
  signals only, uses a bounded adjacent-cue context, and records the missing cross-modal
  confirmation. A detected `decisive_score` cue is not proof of the scoreboard, game clock, lead
  change, or historical importance. Alpha also accepts observation bundles from replaceable
  Providers; the checked-in fixture is synthetic.
- Do not route to `tracked_focus`: it is an explicit unavailable capability. Never describe
  `fixed_subject` as face detection, speaker tracking, or motion tracking.
- Label synthetic fixtures as synthetic; never claim they measure real model quality.
- Freeze blind-run outputs before loading references, and require suite, case, and track identities
  to match. Curated protocol inputs are not blind content-quality evidence.
