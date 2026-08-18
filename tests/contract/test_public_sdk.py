from __future__ import annotations

from pathlib import Path

import pytest

import universal_cutup.sdk as sdk
from universal_cutup.domain.errors import CutupError, ErrorCode


def test_public_sdk_exports_v1_planning_and_execution_surface() -> None:
    expected = {
        "capability_report",
        "inspect_source",
        "load_cut_plan",
        "load_transcript",
        "plan_educational_content",
        "plan_sports_content",
        "plan_sports_transcript",
        "create_plan",
        "execute_cut_plan",
        "run_full_offline",
    }

    assert expected <= set(sdk.__all__)
    assert all(callable(getattr(sdk, name)) for name in expected)
    assert {"DetectedSportsObservations", "SportsTextProfile"} <= set(sdk.__all__)


def test_public_sdk_exports_model_routing_surface() -> None:
    expected = {
        "EscalationReason",
        "ModelRoutingDecision",
        "ModelRoutingRequest",
        "ModelTask",
        "ModelTier",
        "ProviderRecord",
        "RoutingStatus",
        "route_model_task",
    }

    assert expected <= set(sdk.__all__)
    assert callable(sdk.route_model_task)
    assert sdk.ProviderRecord.__name__ == "ProviderRecord"
    decision = sdk.route_model_task(sdk.ModelRoutingRequest(task=sdk.ModelTask.CANDIDATE_PREFILTER))
    assert decision.selected_tier is sdk.ModelTier.ECONOMY


def test_public_sdk_load_plan_error_does_not_expose_parent_path(tmp_path: Path) -> None:
    missing = tmp_path / "private-location" / "missing.json"

    with pytest.raises(CutupError) as raised:
        sdk.load_cut_plan(missing)

    assert raised.value.code is ErrorCode.SOURCE_NOT_FOUND
    assert raised.value.details == {"path": "missing.json"}


def test_public_sdk_source_loaders_do_not_expose_missing_parent_paths(tmp_path: Path) -> None:
    missing_media = tmp_path / "private-location" / "missing.mp4"
    missing_transcript = tmp_path / "private-location" / "missing.srt"

    with pytest.raises(CutupError) as media_error:
        sdk.inspect_source(missing_media)
    with pytest.raises(CutupError) as transcript_error:
        sdk.load_transcript(missing_transcript, source_id="source-private")

    assert media_error.value.details == {"path": "missing.mp4"}
    assert transcript_error.value.details == {"path": "missing.srt"}


def test_capability_report_distinguishes_available_provider_and_unavailable() -> None:
    report = sdk.capability_report()
    capabilities = {item.operation: item for item in report.operations}

    assert capabilities["education_plan"].state == "available"
    assert capabilities["sports_plan"].state == "available"
    assert capabilities["transcribe"].state == "provider_required"
    assert capabilities["transcribe"].error_code is ErrorCode.PROVIDER_REQUIRED
    assert capabilities["package"].state == "unavailable"
    assert capabilities["package"].error_code is ErrorCode.CAPABILITY_UNAVAILABLE
    assert capabilities["reframe"].available_modes == (
        "none",
        "center_crop",
        "manual_focus",
        "fit_background",
        "fixed_subject",
    )
    assert capabilities["reframe"].unavailable_modes == ("tracked_focus",)
    assert report.media_runtime.platform_name
    assert report.media_runtime.media_execution_available is (
        report.media_runtime.ffmpeg_available and report.media_runtime.ffprobe_available
    )


@pytest.mark.parametrize(
    ("operation", "expected_code"),
    [
        ("transcribe", ErrorCode.PROVIDER_REQUIRED),
        ("translate", ErrorCode.PROVIDER_REQUIRED),
        ("package", ErrorCode.CAPABILITY_UNAVAILABLE),
    ],
)
def test_unavailable_sdk_operations_raise_structured_errors(
    operation: str,
    expected_code: ErrorCode,
) -> None:
    with pytest.raises(CutupError) as raised:
        sdk.require_operation(operation)

    payload = raised.value.as_dict()
    assert payload["code"] == expected_code.value
    assert payload["step"] == operation
    assert payload["details"]["operation"] == operation


def test_reframe_validation_reports_requested_and_available_modes() -> None:
    assert sdk.require_reframe_mode("none").state == "available"

    with pytest.raises(CutupError) as raised:
        sdk.require_reframe_mode("tracked_focus")

    assert raised.value.code is ErrorCode.CAPABILITY_UNAVAILABLE
    assert raised.value.step == "reframe"
    assert raised.value.details == {
        "operation": "reframe",
        "requested_mode": "tracked_focus",
        "available_modes": [
            "none",
            "center_crop",
            "manual_focus",
            "fit_background",
            "fixed_subject",
        ],
    }
