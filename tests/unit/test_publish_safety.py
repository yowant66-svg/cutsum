from __future__ import annotations

from pathlib import Path

from universal_cutup.media.executor import _publish_no_overwrite


def test_rollback_does_not_delete_a_path_replaced_by_another_process(tmp_path: Path) -> None:
    temporary = tmp_path / "temporary.bin"
    output = tmp_path / "output.bin"
    temporary.write_bytes(b"owned by this execution")
    published = _publish_no_overwrite(temporary, output)

    output.unlink()
    output.write_bytes(b"replacement owned by another process")
    published.rollback_if_owned()

    assert output.read_bytes() == b"replacement owned by another process"


def test_rollback_removes_the_file_published_by_this_execution(tmp_path: Path) -> None:
    temporary = tmp_path / "temporary.bin"
    output = tmp_path / "output.bin"
    temporary.write_bytes(b"owned by this execution")
    published = _publish_no_overwrite(temporary, output)

    published.rollback_if_owned()

    assert not output.exists()
