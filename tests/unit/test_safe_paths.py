from __future__ import annotations

from pathlib import Path

import pytest

from universal_cutup.domain.errors import CutupError, ErrorCode
from universal_cutup.media.paths import SafePathPolicy


def test_output_path_must_stay_inside_root(tmp_path: Path) -> None:
    policy = SafePathPolicy(output_root=tmp_path / "output")
    with pytest.raises(CutupError) as caught:
        policy.resolve_output("../escape.mp4")
    assert caught.value.code is ErrorCode.PATH_OUTSIDE_ROOT


@pytest.mark.parametrize(
    "unsafe_path",
    [
        r"C:\\outside\\clip.mp4",
        r"\\\\server\\share\\clip.mp4",
        r"subdir\\..\\escape.mp4",
    ],
)
def test_windows_paths_are_rejected_consistently_on_every_host(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    policy = SafePathPolicy(output_root=tmp_path / "output")
    with pytest.raises(CutupError) as caught:
        policy.resolve_output(unsafe_path)
    assert caught.value.code is ErrorCode.PATH_OUTSIDE_ROOT


def test_symlink_escape_fails_before_execution(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    outside = tmp_path / "outside"
    output_root.mkdir()
    outside.mkdir()
    (output_root / "link").symlink_to(outside, target_is_directory=True)
    policy = SafePathPolicy(output_root=output_root)
    with pytest.raises(CutupError) as caught:
        policy.resolve_output("link/escape.mp4")
    assert caught.value.code is ErrorCode.PATH_OUTSIDE_ROOT


def test_existing_output_fails_by_default(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    existing = output_root / "existing.mp4"
    existing.write_bytes(b"existing")
    policy = SafePathPolicy(output_root=output_root)
    with pytest.raises(CutupError) as caught:
        policy.resolve_output("existing.mp4")
    assert caught.value.code is ErrorCode.OUTPUT_EXISTS
