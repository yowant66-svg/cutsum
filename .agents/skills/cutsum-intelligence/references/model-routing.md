# Model routing

CutSum recommends provider-neutral capability tiers. The host maps a selected tier to a model it can
actually use; CutSum must not call a network provider, choose a vendor model, or authorize paid use.

## Stage ownership

| Tier | Tasks |
| --- | --- |
| `deterministic` | Protocol validation, hashing/provenance, selection arithmetic, subtitle layout, FFmpeg/media execution |
| `economy` | Transcript cleanup, language/segment labeling, keyword extraction, candidate prefilter, title drafts |
| `balanced` | Content profile, intent interpretation, candidate proposal, Highlight14 evidence, semantic subtitle grouping, contextual translation |
| `frontier` | Editorial selection review, cross-segment ambiguity, specialist translation review, final quality review |

Run `cutsum model-route TASK` before a model stage. Repeat `--reason` for every observed reason. Use
`--maximum-tier` to preserve the host capability ceiling and `--frontier-calls-remaining` to enforce
an explicit frontier-call budget.

```text
cutsum model-route candidate_prefilter --reason low_confidence
cutsum model-route content_profile --reason semantic_conflict --maximum-tier balanced
cutsum model-route final_quality_review --frontier-calls-remaining 1
```

`low_confidence`, `close_candidate_margin`, and `specialist_terminology` promote a model task by one
tier. `cross_segment_ambiguity`, `semantic_conflict`, `directed_constraint_ambiguity`, and
`final_quality_gate` require frontier. A required tier above the host ceiling, or a required frontier
call with no remaining budget, returns `status=blocked` and no `selected_tier`. Stop or request a new
constraint; never silently downgrade.

## Provider mapping and cost

Resolve the generic tier against models available in the current host. Keep that mapping outside
CutSum core so a provider or model can be replaced without changing the protocol. Prefer the least
expensive model that satisfies the selected tier. Do not retry with a higher tier merely because of
a network, authentication, or validation error; those are operational errors, not semantic
escalation reasons.

For every actual model call, create one `ProviderRecord` with:

- `routing_decision_id` from the routing decision;
- `model_task`, `base_model_tier`, and `selected_model_tier`;
- `model_escalation_reasons` when present;
- the actual provider `model_id`;
- `cost_minor_units` and `currency` when known;
- input and output hashes without prompts, credentials, or raw private responses.

Legacy ProviderRecords remain valid without routing fields. Once any routing field is present, the
complete routing identity is required. Deterministic stages do not pretend to be model calls and do
not carry model-routing metadata.

## Batch discipline

1. Route bulk preprocessing and coarse filtering first.
2. Freeze the reduced candidate set before balanced assessment.
3. Escalate only the uncertain candidates, not the full transcript again.
4. Reserve frontier work for final competing candidates or explicit quality gates.
5. Sum actual ProviderRecord costs and stop when the host budget is exhausted.

Model routing controls cost and auditability; it does not change educational qualification,
sports qualification, Highlight14 weights, or deterministic selection rules.
