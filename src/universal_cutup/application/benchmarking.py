from __future__ import annotations

# ruff: noqa: RUF001
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from universal_cutup.application.resolution import resolve_task_profile
from universal_cutup.domain.assessments import (
    AdaptiveSelectionResult,
    AggregateBundle,
    AssessmentBundle,
    CandidateAssessment,
    CandidateProposalBundle,
    DimensionAssessment,
)
from universal_cutup.domain.benchmarks import (
    BenchmarkCategory,
    BenchmarkItem,
    BenchmarkManifest,
    BenchmarkScoreProfile,
    BenchmarkTaskSpec,
    CuratedBenchmarkItem,
    CuratedInputCollection,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.intelligence import (
    ContentProfile,
    ContentTrack,
    DimensionApplicability,
    DimensionKey,
    HostIntent,
    ResolvedTaskProfile,
)
from universal_cutup.domain.records import ProviderRecord
from universal_cutup.domain.sources import MediaSource, RightsAttestation
from universal_cutup.hashing import document_sha256
from universal_cutup.strategies.adaptive import aggregate_bundle, select_adaptive

from .intelligence import create_adaptive_plan

SCORE_BASE: dict[DimensionKey, float] = {
    DimensionKey.INSIGHT: 6,
    DimensionKey.NOVELTY: 6,
    DimensionKey.EMOTION: 6,
    DimensionKey.QUOTABILITY: 6,
    DimensionKey.HOOK: 6,
    DimensionKey.STANDALONE: 7,
    DimensionKey.CLARITY: 7,
    DimensionKey.COMPLETION: 6,
    DimensionKey.SHAREABILITY: 6,
    DimensionKey.SILENT_WATCHABILITY: 6,
    DimensionKey.PACE: 6,
    DimensionKey.EDITABILITY: 7,
    DimensionKey.SUBTITLE_RELIABILITY: 7,
    DimensionKey.VISUAL_INDEPENDENCE: 6,
}

SCORE_OVERRIDES: dict[BenchmarkScoreProfile, dict[DimensionKey, float]] = {
    BenchmarkScoreProfile.HOOK: {
        DimensionKey.HOOK: 9.8,
        DimensionKey.QUOTABILITY: 9,
        DimensionKey.STANDALONE: 8.5,
        DimensionKey.SHAREABILITY: 9,
        DimensionKey.PACE: 9,
        DimensionKey.COMPLETION: 3,
    },
    BenchmarkScoreProfile.CONCEPT: {
        DimensionKey.INSIGHT: 9,
        DimensionKey.CLARITY: 9,
        DimensionKey.STANDALONE: 8,
        DimensionKey.COMPLETION: 7.5,
        DimensionKey.EDITABILITY: 8,
    },
    BenchmarkScoreProfile.COMPLETE: {
        DimensionKey.INSIGHT: 8.5,
        DimensionKey.CLARITY: 9,
        DimensionKey.COMPLETION: 9.7,
        DimensionKey.STANDALONE: 9,
        DimensionKey.HOOK: 4,
        DimensionKey.PACE: 5,
    },
    BenchmarkScoreProfile.STORY: {
        DimensionKey.EMOTION: 8.5,
        DimensionKey.COMPLETION: 8,
        DimensionKey.STANDALONE: 8,
        DimensionKey.QUOTABILITY: 7.5,
    },
    BenchmarkScoreProfile.VISUAL: {
        DimensionKey.EMOTION: 8,
        DimensionKey.SILENT_WATCHABILITY: 9.5,
        DimensionKey.HOOK: 7.5,
        DimensionKey.VISUAL_INDEPENDENCE: 2,
        DimensionKey.SUBTITLE_RELIABILITY: 4,
    },
    BenchmarkScoreProfile.CONFLICT: {
        DimensionKey.EMOTION: 9.2,
        DimensionKey.HOOK: 8.7,
        DimensionKey.SHAREABILITY: 8.5,
        DimensionKey.PACE: 8,
        DimensionKey.COMPLETION: 7,
    },
    BenchmarkScoreProfile.EMOTION: {
        DimensionKey.EMOTION: 9.5,
        DimensionKey.SHAREABILITY: 8,
        DimensionKey.STANDALONE: 7.5,
        DimensionKey.HOOK: 7,
    },
}


def _score_map(profile: BenchmarkScoreProfile) -> dict[DimensionKey, float]:
    return {**SCORE_BASE, **SCORE_OVERRIDES[profile]}


def _write_json(path: Path, value: BaseModel | dict[str, Any] | list[Any]) -> None:
    if isinstance(value, BaseModel):
        payload: Any = value.model_dump(mode="json", exclude_none=True)
    else:
        payload = value
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_benchmark_inputs(
    manifest_path: Path,
    curated_inputs_path: Path,
) -> tuple[BenchmarkManifest, CuratedInputCollection]:
    manifest = BenchmarkManifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    curated = CuratedInputCollection.model_validate(
        json.loads(curated_inputs_path.read_text(encoding="utf-8"))
    )
    if {item.item_id for item in manifest.items} != {item.item_id for item in curated.items}:
        raise ValueError("manifest and curated input item IDs must match exactly")
    return manifest, curated


def _candidate_documents(
    item: BenchmarkItem,
    curated: CuratedBenchmarkItem,
    provider_record_ref: str,
) -> tuple[CandidateProposalBundle, dict[str, str]]:
    source_id = f"source-{item.item_id}"
    paraphrases: dict[str, str] = {}
    candidates: list[CutCandidate] = []
    for candidate in curated.candidates:
        evidence_id = f"evidence-{candidate.candidate_id}"
        paraphrases[candidate.candidate_id] = candidate.transcript_paraphrase
        evidence_hash = document_sha256(
            {
                "item_content_hash": item.content_hash,
                "candidate_id": candidate.candidate_id,
                "range": [candidate.start_ms, candidate.end_ms],
                "paraphrase": candidate.transcript_paraphrase,
            }
        )
        candidates.append(
            CutCandidate(
                candidate_id=candidate.candidate_id,
                source_id=source_id,
                start_ms=candidate.start_ms,
                end_ms=candidate.end_ms,
                summary=candidate.summary,
                evidence_refs=(
                    EvidenceRef(
                        evidence_id=evidence_id,
                        artifact_id=f"benchmark-artifact-{item.item_id}",
                        segment_ids=(f"segment-{candidate.candidate_id}",),
                        start_ms=candidate.start_ms,
                        end_ms=candidate.end_ms,
                        text_sha256=evidence_hash,
                        snapshot=candidate.transcript_paraphrase,
                    ),
                ),
                tags=(candidate.track_id, candidate.score_profile.value),
                warnings=("transcript text is a curator paraphrase, not a verbatim quotation",),
            )
        )
    input_hash = document_sha256(
        {
            "benchmark_item": item.model_dump(mode="json"),
            "curated_candidates": [
                candidate.model_dump(mode="json") for candidate in curated.candidates
            ],
        }
    )
    return (
        CandidateProposalBundle(
            document_type="candidate_proposal_bundle",
            created_at=item.accessed_at,
            created_by="benchmark-curation",
            proposal_bundle_id=f"proposals-{item.item_id}",
            source_id=source_id,
            provider_record_ref=provider_record_ref,
            provider_kind="host_ai_file",
            is_fixture=False,
            candidates=tuple(candidates),
            input_document_sha256=input_hash,
        ),
        paraphrases,
    )


def _content_profile(
    item: BenchmarkItem,
    curated: CuratedBenchmarkItem,
    proposals: CandidateProposalBundle,
    provider_record_ref: str,
) -> ContentProfile:
    candidate_by_track: dict[str, CutCandidate] = {}
    for candidate, curated_candidate in zip(proposals.candidates, curated.candidates, strict=True):
        candidate_by_track.setdefault(curated_candidate.track_id, candidate)
    tracks = tuple(
        ContentTrack(
            track_id=track.track_id,
            label=track.label,
            topic=track.topic,
            evidence_refs=(candidate_by_track[track.track_id].evidence_refs[0].evidence_id,),
        )
        for track in curated.tracks
    )
    evidence_refs = tuple(
        candidate.evidence_refs[0].evidence_id for candidate in proposals.candidates
    )
    return ContentProfile(
        document_type="content_profile",
        created_at=item.accessed_at,
        created_by="benchmark-curation",
        profile_id=f"profile-{item.item_id}",
        source_id=proposals.source_id,
        content_types=curated.content_types,
        primary_topic=curated.primary_topic,
        subtopics=curated.subtopics,
        structure_types=curated.structure_types,
        typical_audiences=("creators", "learners", "AI agents"),
        value_sources=curated.value_sources,
        density=curated.density,
        dependencies=curated.dependencies,
        language=item.language,
        confidence=0.82,
        supporting_evidence_refs=evidence_refs,
        tracks=tracks,
        provider_record_ref=provider_record_ref,
    )


def _host_intent(item: BenchmarkItem, task: BenchmarkTaskSpec) -> HostIntent:
    return HostIntent(
        document_type="host_intent",
        created_at=item.accessed_at,
        created_by="benchmark-maintainer",
        intent_id=f"intent-{task.task_id}",
        raw_instruction=task.raw_instruction,
        control_mode=task.control_mode,
        desired_outcomes=task.desired_outcomes,
        prohibited_outcomes=task.prohibited_outcomes,
        clip_constraints=task.clip_constraints,
        preserve_time_order=task.preserve_time_order,
        require_track_diversity=task.require_track_diversity,
        hard_include_candidate_ids=task.hard_include_candidate_ids,
        hard_exclude_candidate_ids=task.hard_exclude_candidate_ids,
    )


def _assessment_bundle(
    item: BenchmarkItem,
    curated: CuratedBenchmarkItem,
    proposals: CandidateProposalBundle,
    task_profile: ResolvedTaskProfile,
    provider_record_ref: str,
) -> AssessmentBundle:
    policies = {policy.dimension: policy for policy in task_profile.dimension_policies}
    assessments: list[CandidateAssessment] = []
    for candidate, curated_candidate in zip(proposals.candidates, curated.candidates, strict=True):
        scores = _score_map(curated_candidate.score_profile)
        evidence_id = candidate.evidence_refs[0].evidence_id
        dimensions: list[DimensionAssessment] = []
        for dimension in DimensionKey:
            if policies[dimension].applicability is DimensionApplicability.NOT_APPLICABLE:
                dimensions.append(
                    DimensionAssessment(
                        dimension=dimension,
                        score=None,
                        explanation=(
                            "Resolved as not applicable for this content and excluded "
                            "from aggregation."
                        ),
                        unavailable_reason="resolved_not_applicable",
                    )
                )
            else:
                dimensions.append(
                    DimensionAssessment(
                        dimension=dimension,
                        score=scores[dimension],
                        evidence_refs=(evidence_id,),
                        explanation=(
                            f"Provisional curator assessment using the "
                            f"{curated_candidate.score_profile.value} evidence profile."
                        ),
                        confidence=0.72,
                    )
                )
        assessments.append(
            CandidateAssessment(
                candidate_id=candidate.candidate_id,
                dimensions=tuple(dimensions),
                content_track_ids=(curated_candidate.track_id,),
            )
        )
    return AssessmentBundle(
        document_type="assessment_bundle",
        created_at=item.accessed_at,
        created_by="benchmark-curation",
        assessment_bundle_id=f"assessments-{item.item_id}-{task_profile.resolved_task_id}",
        source_id=proposals.source_id,
        provider_record_ref=provider_record_ref,
        provider_kind="host_ai_file",
        is_fixture=False,
        candidates=tuple(assessments),
        input_document_sha256=document_sha256(
            {
                "proposals": proposals.model_dump(mode="json"),
                "task_profile": task_profile.model_dump(mode="json"),
                "score_profiles": [
                    candidate.score_profile.value for candidate in curated.candidates
                ],
            }
        ),
    )


def _failures(item: BenchmarkItem) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if item.item_id == "film-wings-1927":
        failures.append(
            {
                "classification": "intertitle_only",
                "impact": "No continuous transcript; visual and intertitle evidence only.",
            }
        )
    if item.item_id == "film-all-quiet-1930":
        failures.append(
            {
                "classification": "transcript_unavailable",
                "impact": "Evaluation is based on the approved visual review window.",
            }
        )
    if item.item_id == "film-parasite-trailer-2019":
        failures.extend(
            [
                {
                    "classification": "subtitle_fetch_rate_limited",
                    "impact": "HTTP 429 was recorded; no cookie fallback or retry loop was used.",
                },
                {
                    "classification": "trailer_not_full_film",
                    "impact": "Results test montage understanding, not full-film understanding.",
                },
            ]
        )
    if item.category is BenchmarkCategory.EDUCATION_OR_KNOWLEDGE:
        failures.append(
            {
                "classification": "approved_window_truncation",
                "impact": "Only the first 30 minutes are evaluated by maintainer instruction.",
            }
        )
    return failures


def _format_ms(milliseconds: int) -> str:
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _result_markdown(
    item: BenchmarkItem,
    task: BenchmarkTaskSpec,
    profile: ContentProfile,
    task_profile: ResolvedTaskProfile,
    proposals: CandidateProposalBundle,
    selection: AdaptiveSelectionResult,
    paraphrases: dict[str, str],
    failures: list[dict[str, str]],
) -> str:
    candidates = {candidate.candidate_id: candidate for candidate in proposals.candidates}
    decisions = {decision.candidate_id: decision for decision in selection.decisions}
    lines = [
        f"# {item.title} — {task.task_id}",
        "",
        f"- 原始来源：[{item.canonical_subject}]({item.source_url})",
        f"- 素材范围：{_format_ms(item.execution_policy.analysis_window.start_ms)}–"
        f"{_format_ms(item.execution_policy.analysis_window.end_ms)}",
        f"- AI 认为内容是：{profile.primary_topic}",
        f"- AI 默认/最终目标：{', '.join(task_profile.final_objectives)}",
        f"- 宿主要求：{task.raw_instruction}",
        "- 媒体执行：未执行；本 Gate 只生成分析与 CutPlan。",
        "",
        "## 选中片段",
        "",
    ]
    for candidate_id in selection.selected_candidate_ids:
        candidate = candidates[candidate_id]
        decision = decisions[candidate_id]
        lines.extend(
            [
                f"### {candidate_id}",
                "",
                f"- 入点/出点：{_format_ms(candidate.start_ms)}–{_format_ms(candidate.end_ms)}",
                f"- 为什么选：{candidate.summary}；选择记录为 `{', '.join(decision.reasons)}`。",
                f"- transcript（意译，不是逐字转载）：{paraphrases[candidate_id]}",
                "",
            ]
        )
    lines.extend(["## 已知限制与失败分类", ""])
    if failures:
        lines.extend(
            f"- `{failure['classification']}`：{failure['impact']}" for failure in failures
        )
    else:
        lines.append("- 未记录来源级失败；仍需维护者进行内容质量评价。")
    lines.extend(
        [
            "",
            "## 请维护者评价",
            "",
            "1. 选段是否忠实于素材和宿主目标？（1–5）",
            "2. 入点和出点是否形成完整、自然的片段？（1–5）",
            "3. 是否存在漏掉的更佳片段？（是/否，并写明时间）",
            "4. 对视觉依赖、字幕可靠性或上下文依赖的说明是否准确？",
            "",
        ]
    )
    return "\n".join(lines)


def _human_form(item: BenchmarkItem, task: BenchmarkTaskSpec) -> str:
    return "\n".join(
        [
            f"# Human evaluation — {item.item_id} / {task.task_id}",
            "",
            "## Sample",
            "",
            f"- Category: {item.category.value}",
            f"- Mode: {task.control_mode.value}",
            f"- Host request: {task.raw_instruction}",
            "- Reviewer:",
            "- Review date:",
            "",
            "## Core scores",
            "",
            "Score each from 1 (poor) to 5 (excellent) and add one short reason.",
            "",
            "1. AI understood the original content:",
            "2. AUTO default judgment was professional (AUTO only):",
            "3. Host requirement adherence (DIRECTED only):",
            "4. Selected-segment value:",
            "5. Context and logical completeness:",
            "6. In/out boundary quality:",
            "7. Title, summary and rationale quality:",
            "8. Rendered-media usability (N/A because Gate G is plan-only):",
            "",
            "## Overall judgment",
            "",
            "- Keep as-is:",
            "- Keep after revision:",
            "- Reject:",
            "- Best missed timestamp, if any:",
            "- Incorrect or unsupported claim, if any:",
            "- Largest problem:",
            "- Smartest behavior:",
            "- Weakest behavior:",
            "- Primary failure class (content / task / dimensions / candidates / "
            "boundaries / subtitles-media / conflict handling / other):",
            "",
            "## Conclusion",
            "",
            "- Would continue using: yes / no / needs improvement",
            "- Overall score (1-10):",
            "- One-sentence conclusion:",
            "",
        ]
    )


def run_standard_benchmark(
    manifest_path: Path,
    curated_inputs_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    if output_directory.exists():
        raise FileExistsError(f"benchmark output already exists: {output_directory}")
    manifest, curated_collection = load_benchmark_inputs(manifest_path, curated_inputs_path)
    curated_by_id = {item.item_id: item for item in curated_collection.items}
    output_directory.mkdir(parents=True)
    runs: list[dict[str, Any]] = []

    for item in manifest.items:
        curated = curated_by_id[item.item_id]
        provider_record_id = f"provider-{item.item_id}"
        proposals, paraphrases = _candidate_documents(item, curated, provider_record_id)
        profile = _content_profile(item, curated, proposals, provider_record_id)
        tasks = (item.auto_task, *item.directed_tasks)
        for task in tasks:
            intent = _host_intent(item, task)
            resolved = resolve_task_profile(
                intent,
                profile,
                created_at=item.accessed_at,
                resolved_task_id=f"resolved-{task.task_id}",
            )
            assessments = _assessment_bundle(item, curated, proposals, resolved, provider_record_id)
            aggregates_tuple = aggregate_bundle(proposals.candidates, assessments, resolved)
            aggregates = AggregateBundle(
                document_type="aggregate_bundle",
                created_at=item.accessed_at,
                created_by="universal-cutup",
                aggregate_bundle_id=f"aggregates-{task.task_id}",
                source_id=proposals.source_id,
                resolved_task_id=resolved.resolved_task_id,
                aggregates=aggregates_tuple,
                input_document_sha256=document_sha256(
                    {
                        "proposals": proposals.model_dump(mode="json"),
                        "assessments": assessments.model_dump(mode="json"),
                        "resolved": resolved.model_dump(mode="json"),
                    }
                ),
            )
            selection = select_adaptive(
                proposals.candidates,
                assessments.candidates,
                aggregates.aggregates,
                resolved,
                created_at=item.accessed_at,
            ).model_copy(update={"selection_id": f"selection-{task.task_id}"})
            provider_record = ProviderRecord(
                provider_record_id=provider_record_id,
                provider_id=curated_collection.provider.provider_id,
                operation=curated_collection.provider.operation,
                model_id=curated_collection.provider.model_id,
                input_hashes=(item.content_hash,),
                output_hashes=(
                    document_sha256(profile),
                    document_sha256(proposals),
                    document_sha256(assessments),
                ),
                cost_minor_units=curated_collection.provider.cost_minor_units,
                currency=curated_collection.provider.currency,
                warnings=curated_collection.provider.warnings,
                started_at=curated_collection.created_at,
                completed_at=curated_collection.created_at,
            )
            source = MediaSource(
                source_id=proposals.source_id,
                media_id=f"media-{item.item_id}",
                kind="video",
                sha256=item.content_hash,
                basename_hint=f"{item.item_id}.source",
                duration_ms=item.duration_ms,
                rights_attestation=RightsAttestation.ANALYSIS_ONLY,
            )
            plan = create_adaptive_plan(
                source,
                proposals,
                assessments,
                resolved,
                selection,
                provider_records=(provider_record,),
                created_at=item.accessed_at,
            ).model_copy(update={"plan_id": f"plan-{task.task_id}"})
            failures = _failures(item)
            not_applicable_count = sum(
                assessment.score is None
                for candidate in assessments.candidates
                for assessment in candidate.dimensions
            )
            structure_hash = document_sha256(
                {
                    "objectives": resolved.final_objectives,
                    "policies": [
                        policy.model_dump(mode="json") for policy in resolved.dimension_policies
                    ],
                    "selected": selection.selected_candidate_ids,
                    "aggregates": [
                        {
                            "candidate_id": aggregate.candidate_id,
                            "overall": aggregate.overall,
                            "required_passed": aggregate.required_passed,
                        }
                        for aggregate in aggregates.aggregates
                    ],
                }
            )
            metrics = {
                "candidate_count": len(proposals.candidates),
                "selected_count": len(selection.selected_candidate_ids),
                "not_applicable_assessment_count": not_applicable_count,
                "unsatisfied_constraint_count": len(selection.unsatisfied_constraints),
                "provider_cost_minor_units": provider_record.cost_minor_units,
                "currency": provider_record.currency,
                "stable_structure_sha256": structure_hash,
            }

            task_directory = output_directory / "results" / item.item_id / task.task_id
            task_directory.mkdir(parents=True)
            _write_json(task_directory / "01-manifest-item.json", item.model_dump(mode="json"))
            _write_json(task_directory / "02-provider-record.json", provider_record)
            _write_json(task_directory / "03-content-profile.json", profile)
            _write_json(task_directory / "04-host-intent.json", intent)
            _write_json(task_directory / "05-resolved-task-profile.json", resolved)
            _write_json(task_directory / "06-candidates.json", proposals)
            _write_json(task_directory / "07-assessments.json", assessments)
            _write_json(task_directory / "08-aggregates.json", aggregates)
            _write_json(task_directory / "09-selection.json", selection)
            _write_json(task_directory / "10-cut-plan.json", plan)
            _write_json(task_directory / "11-metrics.json", metrics)
            _write_json(task_directory / "12-failures.json", failures)
            (task_directory / "00-result.md").write_text(
                _result_markdown(
                    item,
                    task,
                    profile,
                    resolved,
                    proposals,
                    selection,
                    paraphrases,
                    failures,
                ),
                encoding="utf-8",
            )
            (task_directory / "13-human-evaluation.md").write_text(
                _human_form(item, task),
                encoding="utf-8",
            )
            runs.append(
                {
                    "item_id": item.item_id,
                    "task_id": task.task_id,
                    "control_mode": task.control_mode.value,
                    "selected_candidate_ids": list(selection.selected_candidate_ids),
                    "stable_structure_sha256": structure_hash,
                    "result_page": str(
                        Path("results") / item.item_id / task.task_id / "00-result.md"
                    ),
                    "failures": failures,
                }
            )

    index = {
        "benchmark_id": manifest.benchmark_id,
        "benchmark_version": manifest.benchmark_version,
        "item_count": len(manifest.items),
        "task_count": len(runs),
        "external_model_api_calls": 0,
        "actual_cost_minor_units": 0,
        "currency": curated_collection.provider.currency,
        "runs": runs,
    }
    _write_json(output_directory / "run-index.json", index)
    (output_directory / "README.md").write_text(
        "\n".join(
            [
                "# Standard benchmark results",
                "",
                f"- Items: {len(manifest.items)}",
                f"- Tasks: {len(runs)} (1 AUTO + 2 DIRECTED per item)",
                "- External model API calls: 0",
                "- Actual incremental API cost: USD 0.00",
                "- Media execution: none; CutPlans only",
                "",
                "Open each task's `00-result.md` for a non-technical review page.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return index
