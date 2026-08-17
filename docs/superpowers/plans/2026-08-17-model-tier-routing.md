# Model-Tier Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provider-neutral, fail-closed model-tier recommendations and preserve each actual model call's routing decision in CutSum provenance.

**Architecture:** A focused domain module owns generic task, tier, reason, request, decision, and deterministic routing rules. Existing `ProviderRecord` gains optional backward-compatible routing metadata so CutPlan and ExecutionRecord carry the audit trail without a second provenance graph. The stable SDK, CLI, exported Schema, and repo-local Skill expose the same contract; no provider call is added.

**Tech Stack:** Python 3.11–3.13, Pydantic v2 frozen models, Typer, pytest, JSON Schema.

---

### Task 1: Domain routing contract and deterministic decision function

**Files:**
- Create: `src/universal_cutup/domain/model_routing.py`
- Create: `tests/contract/test_model_routing.py`

- [ ] **Step 1: Write failing base-tier tests**

Add parametrized tests proving deterministic stages route to `deterministic`, bulk text stages to
`economy`, semantic planning stages to `balanced`, and final judgment stages to `frontier`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/pytest tests/contract/test_model_routing.py -q`
Expected: collection failure because `universal_cutup.domain.model_routing` does not exist.

- [ ] **Step 3: Implement enums, frozen request/decision models, and base mapping**

Define `ModelTask`, `ModelTier`, `EscalationReason`, `RoutingStatus`, `ModelRoutingRequest`,
`ModelRoutingDecision`, and `route_model_task`. Keep the task mapping immutable and vendor-neutral.

- [ ] **Step 4: Add escalation and fail-closed tests**

Test one-tier uncertainty promotion, mandatory-frontier reasons, host ceiling refusal, exhausted
frontier-call budget refusal, reason deduplication, and deterministic-stage refusal to accept model
escalation.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/contract/test_model_routing.py -q`
Expected: all model-routing tests pass.

- [ ] **Step 6: Commit**

Commit: `feat: add provider-neutral model routing contract`

### Task 2: Provider provenance integration

**Files:**
- Modify: `src/universal_cutup/domain/records.py`
- Modify: `tests/contract/test_records.py`

- [ ] **Step 1: Write failing provenance tests**

Add tests for a complete routing annotation, legacy records with no annotation, partial metadata
rejection, selected-tier mismatch rejection, and escalation-from-base consistency.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `.venv/bin/pytest tests/contract/test_records.py -q`
Expected: routing fields are absent or invalid metadata is accepted.

- [ ] **Step 3: Add optional routing fields and one cross-field validator**

Add `routing_decision_id`, `model_task`, `base_model_tier`, `selected_model_tier`, and
`model_escalation_reasons`. Require all routing identity fields together, forbid routing metadata on
deterministic tasks, and require escalation reasons when selected tier exceeds base tier.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/contract/test_records.py -q`
Expected: all record tests pass, including legacy compatibility.

- [ ] **Step 5: Commit**

Commit: `feat: record model routing provenance`

### Task 3: SDK, CLI, and Schema surfaces

**Files:**
- Modify: `src/universal_cutup/application/sdk.py`
- Modify: `src/universal_cutup/sdk.py`
- Modify: `src/universal_cutup/cli.py`
- Modify: `src/universal_cutup/schema.py`
- Modify: `tests/contract/test_public_sdk.py`
- Modify: `tests/contract/test_cli.py`
- Modify: `tests/contract/test_schema_export.py`
- Create: `schemas/model-routing-decision.schema.json`

- [ ] **Step 1: Write failing SDK, CLI, and Schema tests**

Assert that the stable SDK exports routing types and function; `cutsum model-route` emits a valid
decision; blocked routing remains structured JSON with `status=blocked`; and schema export includes
`model-routing-decision.schema.json`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/pytest tests/contract/test_public_sdk.py tests/contract/test_cli.py tests/contract/test_schema_export.py -q`
Expected: missing exports, command, and schema.

- [ ] **Step 3: Add public exports, Typer command, and Schema registration**

The command accepts `TASK`, repeatable `--reason`, `--maximum-tier`, and
`--frontier-calls-remaining`, then emits the decision without calling a provider.

- [ ] **Step 4: Export checked-in Schemas and verify GREEN**

Run: `.venv/bin/python -m universal_cutup.schema schemas`
Then rerun the focused pytest command. Expected: all focused tests pass and no unrelated schema
bytes change.

- [ ] **Step 5: Commit**

Commit: `feat: expose model routing through sdk and cli`

### Task 4: Repo-local Skill routing workflow

**Files:**
- Modify: `.agents/skills/cutsum-intelligence/SKILL.md`
- Create: `.agents/skills/cutsum-intelligence/references/model-routing.md`
- Modify: `.agents/skills/cutsum-intelligence/references/protocol-workflow.md`
- Modify: `.agents/skills/cutsum-intelligence/agents/openai.yaml` only if validation shows stale UI metadata
- Modify: `tests/contract/test_repo_skill.py`

- [ ] **Step 1: Write failing Skill contract tests**

Require the Skill to invoke `cutsum model-route`, distinguish deterministic/economy/balanced/frontier,
record actual calls in ProviderRecord, block silent downgrade, and defer detailed tables to the new
reference.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/pytest tests/contract/test_repo_skill.py -q`
Expected: assertions fail because routing guidance is absent.

- [ ] **Step 3: Add concise Skill workflow and detailed model-routing reference**

Document stage ownership, escalation conditions, frontier budgeting, provider model mapping,
provenance requirements, and the no-network/no-paid-call boundary.

- [ ] **Step 4: Validate the Skill and verify GREEN**

Run the Skill Creator `quick_validate.py` against `.agents/skills/cutsum-intelligence`, then run
`.venv/bin/pytest tests/contract/test_repo_skill.py -q`. Expected: validation and tests pass.

- [ ] **Step 5: Commit**

Commit: `docs: teach CutSum skill cost-aware model routing`

### Task 5: Full verification and release-facing documentation

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Document the public behavior and Alpha boundary**

Explain that routing returns generic recommendations, hosts choose actual model IDs, provider calls
need authorization, and deterministic media execution never requires an LLM.

- [ ] **Step 2: Run formatting, typing, test, coverage, schema, security, and diff checks**

Run `.venv/bin/ruff check .`, `.venv/bin/mypy src tests scripts examples`,
`.venv/bin/pytest --cov=universal_cutup --cov-branch --cov-report=term-missing --cov-fail-under=85`,
schema export plus `git diff --exit-code -- schemas`, `reuse lint`, credential-pattern scans, and
`git diff --check`.

- [ ] **Step 3: Review changed files for unintended scope**

Confirm no model IDs, credentials, network calls, ranking formulas, or unrelated sports/education
behavior entered the diff.

- [ ] **Step 4: Commit**

Commit: `docs: document model-tier routing`
