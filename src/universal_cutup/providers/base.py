from __future__ import annotations

from typing import Protocol

from universal_cutup.domain.assessments import (
    AssessmentBundle,
    CandidateProposalBundle,
)
from universal_cutup.domain.intelligence import ContentProfile, HostIntent
from universal_cutup.domain.transcript import TranscriptArtifact


class ContentIntelligenceProvider(Protocol):
    provider_id: str

    def profile_content(
        self,
        transcript: TranscriptArtifact,
        host_intent: HostIntent,
    ) -> ContentProfile: ...

    def propose_candidates(
        self,
        transcript: TranscriptArtifact,
        host_intent: HostIntent,
        content_profile: ContentProfile,
    ) -> CandidateProposalBundle: ...

    def assess_candidates(
        self,
        transcript: TranscriptArtifact,
        host_intent: HostIntent,
        content_profile: ContentProfile,
        proposals: CandidateProposalBundle,
    ) -> AssessmentBundle: ...
