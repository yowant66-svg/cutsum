# CutSum Model-Tier Routing Design

## Goal

Add provider-neutral model routing so a host can reserve expensive reasoning for a small number of
ambiguous or high-value editing decisions while keeping deterministic media work outside LLMs. The
feature must expose routing recommendations and preserve the actual model, tier, reason, and cost in
existing provenance records. It must not call a network provider or bind CutSum to a model vendor.

## Considered approaches

1. **Documentation only.** Add a model table to the Skill. This is cheap but unenforceable and leaves
   no machine-readable audit trail.
2. **Skill-only orchestration.** Tell the host to delegate tasks by tier. This improves behavior but
   still cannot validate escalation or persist decisions.
3. **Protocol-backed host routing (selected).** Put stable task/tier/reason contracts and a
   deterministic recommendation function in CutSum, then teach the Skill to use them. The host maps
   generic tiers to available model IDs and performs any authorized calls.

## Boundaries

- CutSum never chooses a vendor-specific model ID.
- CutSum never starts a paid or network model call.
- `deterministic` means Python/FFmpeg/schema work and is not a model tier that may be silently mapped
  to an LLM.
- The routing policy does not replace Highlight14, educational qualification, sports qualification,
  or final CutPlan validation.
- A required tier above the host's configured maximum is blocked and reported, not silently
  downgraded.

## Contract

Create a focused domain module with:

- `ModelTask`: stable editing-stage roles.
- `ModelTier`: `deterministic`, `economy`, `balanced`, and `frontier`.
- `EscalationReason`: structured uncertainty and quality-gate reasons.
- `ModelRoutingRequest`: task, observed reasons, host ceiling, and remaining frontier-call budget.
- `ModelRoutingDecision`: base tier, selected tier, status, reasons, and explanation.

The deterministic router assigns:

- deterministic: validation, hashing, aggregation, selection arithmetic, subtitle layout, FFmpeg;
- economy: cleanup, language/segment labeling, keyword extraction, candidate prefilter, title drafts;
- balanced: content profile, intent interpretation, candidate proposal, Highlight14 evidence,
  semantic subtitle grouping, ordinary contextual translation;
- frontier: final semantic selection, cross-segment ambiguity resolution, specialist translation
  review, and final editorial-quality review.

Non-final uncertainty reasons promote an economy or balanced task by one tier. A final quality gate,
unresolved semantic conflict, or cross-segment ambiguity requires frontier. If the host ceiling or
frontier-call budget prevents the required tier, the decision is `blocked`.

## Provenance

Extend `ProviderRecord` with optional backward-compatible routing fields:

- task;
- selected generic tier;
- base tier;
- escalation reasons;
- routing decision ID.

Existing `model_id`, `cost_minor_units`, and `currency` remain the source of truth for the actual
provider model and spend. A validator rejects partial or contradictory routing metadata. Because
ProviderRecord already travels with CutPlan and ExecutionRecord, no second provenance graph is
introduced.

## Public surfaces

- Export the routing models and `route_model_task` from the stable SDK.
- Add a CLI command that accepts a task and optional escalation/ceiling/budget inputs and emits a
  JSON `ModelRoutingDecision`.
- Export the new JSON Schema.
- Update the repo-local Skill with the tier table, escalation rules, budget behavior, and the rule
  that every actual model call must produce a ProviderRecord carrying the routing decision.

## Tests

- Contract tests for base task-to-tier mapping.
- Promotion tests for low confidence and close candidate margins.
- Frontier tests for semantic conflict, cross-segment reasoning, specialist review, and final gate.
- Fail-closed tests for tier ceilings and exhausted frontier budgets.
- ProviderRecord compatibility and invalid-partial-metadata tests.
- CLI, SDK export, schema drift, and Skill contract tests.
- Full existing suite and branch coverage gate after implementation.

## Success criteria

- The host can ask CutSum which generic tier a stage needs without naming a vendor model.
- Simple bulk work does not default to frontier.
- High-value ambiguous decisions cannot be silently downgraded.
- Actual model ID and cost remain auditable in the same ProviderRecord chain.
- Old plans and records without routing metadata continue to validate.
