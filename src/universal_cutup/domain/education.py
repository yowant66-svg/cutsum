from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from .common import FrozenModel
from .intelligence import ControlMode


class EducationSignalType(StrEnum):
    DEFINITION = "definition"
    THEOREM_OR_RULE = "theorem_or_rule"
    REASONING_CHAIN = "reasoning_chain"
    WORKED_EXAMPLE = "worked_example"
    PROCEDURE_OR_STEP = "procedure_or_step"
    SUMMARY = "summary"
    COMMON_MISTAKE = "common_mistake"
    DIFFICULT_POINT = "difficult_point"
    TEACHER_EMPHASIS = "teacher_emphasis"
    EXAM_RELEVANCE = "exam_relevance"


class EducationContextRole(StrEnum):
    SELF_CONTAINED = "self_contained"
    REQUIRES_PREVIOUS = "requires_previous"
    REQUIRES_FOLLOWING = "requires_following"
    REQUIRES_VISUAL = "requires_visual"


class EducationVisualDependencyType(StrEnum):
    SLIDE = "slide"
    BLACKBOARD = "blackboard"
    CODE = "code"
    FORMULA = "formula"
    DIAGRAM = "diagram"


STRUCTURAL_EDUCATION_SIGNAL_TYPES = frozenset(
    {
        EducationSignalType.DEFINITION,
        EducationSignalType.THEOREM_OR_RULE,
        EducationSignalType.REASONING_CHAIN,
        EducationSignalType.WORKED_EXAMPLE,
        EducationSignalType.PROCEDURE_OR_STEP,
        EducationSignalType.SUMMARY,
        EducationSignalType.COMMON_MISTAKE,
        EducationSignalType.DIFFICULT_POINT,
    }
)


class EducationSignal(FrozenModel):
    signal_id: str
    signal_type: EducationSignalType
    matched_text: str = Field(min_length=1)
    key_terms: tuple[str, ...] = ()
    context_roles: tuple[EducationContextRole, ...] = (EducationContextRole.SELF_CONTAINED,)
    language: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> EducationSignal:
        if self.end_ms <= self.start_ms:
            raise ValueError("education signal end_ms must be greater than start_ms")
        if len(self.key_terms) != len(set(self.key_terms)):
            raise ValueError("education signal key terms must be unique")
        if not self.context_roles:
            raise ValueError("education signal requires at least one context role")
        if len(self.context_roles) != len(set(self.context_roles)):
            raise ValueError("education signal context roles must be unique")
        return self


class EducationVisualDependency(FrozenModel):
    dependency_id: str
    dependency_type: EducationVisualDependencyType
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    description: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> EducationVisualDependency:
        if self.end_ms <= self.start_ms:
            raise ValueError("education visual dependency end_ms must be greater than start_ms")
        return self


class EducationalCandidateProfile(FrozenModel):
    candidate_id: str
    qualified: bool
    signal_types: tuple[EducationSignalType, ...]
    context_roles: tuple[EducationContextRole, ...]
    key_terms: tuple[str, ...]
    visual_dependency_types: tuple[EducationVisualDependencyType, ...]
    completeness_confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_profile(self) -> EducationalCandidateProfile:
        if len(self.signal_types) != len(set(self.signal_types)):
            raise ValueError("educational profile signal types must be unique")
        if len(self.context_roles) != len(set(self.context_roles)):
            raise ValueError("educational profile context roles must be unique")
        if len(self.key_terms) != len(set(self.key_terms)):
            raise ValueError("educational profile key terms must be unique")
        if len(self.visual_dependency_types) != len(set(self.visual_dependency_types)):
            raise ValueError("educational profile visual dependency types must be unique")
        if self.qualified and not (set(self.signal_types) & STRUCTURAL_EDUCATION_SIGNAL_TYPES):
            raise ValueError("qualified educational profile requires a structural signal")
        return self


class EducationalQualification(FrozenModel):
    candidate_id: str
    qualified: bool
    matched_types: tuple[EducationSignalType, ...]
    missing_types: tuple[EducationSignalType, ...] = ()
    reasons: tuple[str, ...] = ()


class EducationalSelectionResult(FrozenModel):
    strategy_id: str = "educational_distillation"
    strategy_version: str = "alpha-0.1.0"
    selected_candidate_ids: tuple[str, ...]
    qualifications: tuple[EducationalQualification, ...]
    unsatisfied_requirements: tuple[str, ...] = ()


class EducationalTaskRequest(FrozenModel):
    control_mode: ControlMode
    raw_instruction: str
    required_types: tuple[EducationSignalType, ...] = ()
    forbidden_types: tuple[EducationSignalType, ...] = ()
    target_count: int | None = Field(default=None, ge=1)
    required_topic_groups: tuple[tuple[str, ...], ...] = ()
    maximum_duration_ms: int | None = Field(default=None, gt=0)
    unresolved_semantic_instruction: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> EducationalTaskRequest:
        if set(self.required_types) & set(self.forbidden_types):
            raise ValueError("educational type cannot be both required and forbidden")
        if any(not group for group in self.required_topic_groups):
            raise ValueError("educational topic groups cannot be empty")
        normalized_groups = tuple(
            tuple(term.strip().casefold() for term in group)
            for group in self.required_topic_groups
        )
        if any(not term for group in normalized_groups for term in group):
            raise ValueError("educational topic terms cannot be blank")
        if any(len(group) != len(set(group)) for group in normalized_groups):
            raise ValueError("educational topic alternatives must be unique")
        if len(normalized_groups) != len(set(normalized_groups)):
            raise ValueError("educational topic groups must be unique")
        return self
