from __future__ import annotations

from universal_cutup.application.subtitle_display import (
    materialize_display_units,
    source_group_text,
)
from universal_cutup.domain.candidates import CutCandidate, EvidenceRef
from universal_cutup.domain.education import EducationSignalType
from universal_cutup.domain.subtitles import (
    ContextualTranslationRecord,
    subtitle_text_sha256,
)
from universal_cutup.domain.transcript import SubtitleCue
from universal_cutup.strategies.educational import (
    attach_education_signals,
    select_educational_candidates,
)


def _candidate(candidate_id: str, text: str, start_ms: int) -> CutCandidate:
    evidence = EvidenceRef(
        evidence_id=f"evidence-{candidate_id}",
        artifact_id="transcript-mit",
        segment_ids=(f"segment-{candidate_id}",),
        start_ms=start_ms,
        end_ms=start_ms + 20_000,
        text_sha256="a" * 64,
    )
    return CutCandidate(
        candidate_id=candidate_id,
        source_id="mit-source",
        start_ms=start_ms,
        end_ms=start_ms + 20_000,
        summary=text,
        evidence_refs=(evidence,),
        subtitle_cues=(
            SubtitleCue(
                cue_id=f"cue-{candidate_id}",
                source_id="mit-source",
                start_ms=start_ms,
                end_ms=start_ms + 20_000,
                text=text,
                language="en",
                source_segment_ids=(f"segment-{candidate_id}",),
            ),
        ),
    )


def test_educational_distillation_rejects_referential_definition_without_context() -> None:
    algorithm = attach_education_signals(
        _candidate("algorithm", "An algorithm is a function from inputs to outputs.", 0)
    )
    problem = attach_education_signals(
        _candidate(
            "problem",
            "That is really the formal definition of what a problem is.",
            30_000,
        )
    )
    hardware = attach_education_signals(
        _candidate("hardware", "Timing depends on the machine hardware.", 60_000)
    )
    result = select_educational_candidates(
        (algorithm, problem, hardware),
        required_types=(EducationSignalType.DEFINITION,),
        required_count=2,
    )
    assert result.selected_candidate_ids == ("algorithm",)
    assert result.unsatisfied_requirements == ("educational_required_count:2",)
    problem_types = {signal.signal_type for signal in problem.education_signals}
    assert EducationSignalType.DEFINITION in problem_types
    assert EducationSignalType.TEACHER_EMPHASIS in problem_types


def test_teacher_emphasis_cannot_qualify_without_structural_content() -> None:
    emphasis_only = attach_education_signals(
        _candidate("emphasis", "Pay attention. This is important.", 0)
    )
    result = select_educational_candidates(
        (emphasis_only,),
        required_types=(EducationSignalType.TEACHER_EMPHASIS,),
        required_count=1,
    )
    assert result.selected_candidate_ids == ()
    assert result.unsatisfied_requirements == ("educational_required_count:1",)
    assert result.qualifications[0].reasons == ("teacher_emphasis_alone_is_not_selectable",)


def test_teacher_emphasis_can_cross_source_cue_boundary() -> None:
    base = _candidate("cross-cue", "placeholder", 0)
    cues = (
        base.subtitle_cues[0].model_copy(
            update={"cue_id": "cue-formal", "end_ms": 10_000, "text": "This is the formal"}
        ),
        base.subtitle_cues[0].model_copy(
            update={
                "cue_id": "cue-definition",
                "start_ms": 10_000,
                "text": "definition of a problem.",
            }
        ),
    )
    source_text = source_group_text(cues)
    translation = "这是问题的形式化定义。"
    record = ContextualTranslationRecord(
        translation_record_id="translation-cross-cue",
        provider_record_ref="provider-test",
        source_language="en",
        translation_language="zh-CN",
        source_cue_ids=tuple(cue.cue_id for cue in cues),
        source_text=source_text,
        translated_text=translation,
        source_text_sha256=subtitle_text_sha256(source_text),
        translation_sha256=subtitle_text_sha256(translation),
    )
    candidate = base.model_copy(
        update={
            "subtitle_cues": cues,
            "contextual_translation_records": (record,),
            "subtitle_display_units": materialize_display_units(
                cues,
                (record,),
                source_id=base.source_id,
            ),
        }
    )

    signal_types = {
        signal.signal_type for signal in attach_education_signals(candidate).education_signals
    }

    assert EducationSignalType.DEFINITION not in signal_types
    assert EducationSignalType.TEACHER_EMPHASIS in signal_types
