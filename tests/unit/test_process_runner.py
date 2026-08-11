from __future__ import annotations

import sys
import time
from pathlib import Path
from threading import Event, Timer

import pytest

from universal_cutup.media.process import ProcessRunner, ProcessStatus, redact_command


def test_timeout_returns_recoverable_outcome() -> None:
    result = ProcessRunner().run(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout_seconds=0.05,
    )
    assert result.status is ProcessStatus.TIMED_OUT
    assert result.recoverable is True
    assert Path(result.redacted_command[0]).name.startswith("python")
    step = result.to_step_result("slow-process")
    assert step.status == "timed_out"
    assert step.error_code == "MEDIA_PROCESS_TIMEOUT"


def test_pre_cancelled_process_does_not_start() -> None:
    cancellation = Event()
    cancellation.set()
    result = ProcessRunner().run(
        [sys.executable, "-c", "raise SystemExit(99)"],
        timeout_seconds=1,
        cancellation=cancellation,
    )
    assert result.status is ProcessStatus.CANCELLED
    assert result.return_code is None


def test_running_process_cancellation_has_a_bounded_shutdown() -> None:
    cancellation = Event()
    timer = Timer(0.1, cancellation.set)
    timer.start()
    started = time.monotonic()
    try:
        result = ProcessRunner().run(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout_seconds=3,
            cancellation=cancellation,
        )
    finally:
        timer.cancel()

    assert result.status is ProcessStatus.CANCELLED
    assert result.recoverable is True
    assert time.monotonic() - started < 2


def test_sensitive_argument_is_redacted() -> None:
    result = ProcessRunner().run(
        [sys.executable, "-c", "print('ok')", "--token", "private-value"],
        timeout_seconds=1,
    )
    assert "private-value" not in result.redacted_command
    assert "***" in result.redacted_command


def test_missing_executable_returns_structured_failed_outcome() -> None:
    result = ProcessRunner().run(
        ["universal-cutup-command-that-does-not-exist"],
        timeout_seconds=1,
    )

    assert result.status is ProcessStatus.FAILED
    assert result.return_code is None
    assert result.recoverable is True
    assert result.launch_error == "not_found"


def test_home_directory_is_redacted_from_auditable_commands() -> None:
    private_media = Path.home() / "private" / "source.mp4"

    redacted = redact_command(["ffmpeg", "-i", str(private_media), "output.mp4"])

    assert str(Path.home()) not in " ".join(redacted)
    assert redacted[2] == "<HOME>/private/source.mp4"


def test_absolute_path_outside_home_is_reduced_to_basename() -> None:
    private_media = "/private/var/folders/session/source clip.mp4"

    redacted = redact_command(["ffprobe", "-i", private_media])

    assert "/private/var/folders/session" not in " ".join(redacted)
    assert redacted[2] == "<ABSOLUTE_PATH>/source clip.mp4"


def test_embedded_subtitle_filter_path_is_redacted() -> None:
    filter_value = "subtitles=filename='/private/var/session/private subtitle.ass'"

    redacted = redact_command(["ffmpeg", "-vf", filter_value])

    assert "/private/var/session" not in " ".join(redacted)
    assert redacted[2] == "subtitles=filename='<ABSOLUTE_PATH>/private subtitle.ass'"


def test_non_utf8_process_output_is_replaced_without_reader_failure() -> None:
    result = ProcessRunner().run(
        [sys.executable, "-c", "import os; os.write(2, bytes([0x8d]))"],
        timeout_seconds=1,
    )

    assert result.status is ProcessStatus.COMPLETED
    assert result.stderr == "�"


def test_large_stdout_and_stderr_are_drained_and_bounded() -> None:
    size = 2 * 1024 * 1024
    result = ProcessRunner(max_output_bytes=64 * 1024).run(
        [
            sys.executable,
            "-c",
            (
                "import os,sys; "
                f"os.write(1, b'A' * {size}); "
                f"os.write(2, b'B' * {size}); "
                "sys.exit(7)"
            ),
        ],
        timeout_seconds=10,
    )

    assert result.status is ProcessStatus.FAILED
    assert result.return_code == 7
    assert result.stdout_bytes == size
    assert result.stderr_bytes == size
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 64 * 1024
    assert len(result.stderr.encode("utf-8")) <= 64 * 1024
    assert result.stdout.startswith("A" * 100)
    assert result.stdout.endswith("A" * 100)
    assert "[output truncated]" in result.stdout


def test_small_output_is_not_marked_truncated() -> None:
    result = ProcessRunner(max_output_bytes=1024).run(
        [sys.executable, "-c", "print('ok')"], timeout_seconds=2
    )

    assert result.stdout == "ok\n"
    assert result.stdout_bytes == 3
    assert result.stdout_truncated is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")
def test_negative_return_code_records_signal_name() -> None:
    result = ProcessRunner().run(
        [
            sys.executable,
            "-c",
            "import os,signal; os.kill(os.getpid(), signal.SIGTERM)",
        ],
        timeout_seconds=2,
    )

    assert result.status is ProcessStatus.FAILED
    assert result.termination_signal == "SIGTERM"
