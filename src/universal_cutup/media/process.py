from __future__ import annotations

import re
import signal
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import Event, Thread
from typing import BinaryIO

from universal_cutup.domain.execution import StepResult


class ProcessStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


SENSITIVE_FLAGS = frozenset(
    {
        "--api-key",
        "--cookie",
        "--cookies",
        "--password",
        "--secret",
        "--token",
    }
)
FILTER_PATH_PATTERN = re.compile(r"(filename=')([^']+)(')")
TRUNCATION_MARKER = b"\n... [output truncated] ...\n"
DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024


class _BoundedCapture:
    def __init__(self, limit: int) -> None:
        if limit < len(TRUNCATION_MARKER) + 2:
            raise ValueError("max_output_bytes is too small")
        self._limit = limit
        self._head_limit = (limit - len(TRUNCATION_MARKER)) // 2
        self._tail_limit = limit - len(TRUNCATION_MARKER) - self._head_limit
        self._head = bytearray()
        self._tail = bytearray()
        self.total_bytes = 0

    def feed(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        head_missing = self._head_limit - len(self._head)
        if head_missing > 0:
            self._head.extend(chunk[:head_missing])
            chunk = chunk[head_missing:]
        if chunk:
            self._tail.extend(chunk)
            if len(self._tail) > self._tail_limit:
                del self._tail[: -self._tail_limit]

    @property
    def truncated(self) -> bool:
        return self.total_bytes > self._limit

    def text(self) -> str:
        if self.truncated:
            payload = bytes(self._head) + TRUNCATION_MARKER + bytes(self._tail)
        else:
            payload = bytes(self._head) + bytes(self._tail)
        return payload.decode("utf-8", errors="replace")


def _drain(stream: BinaryIO, capture: _BoundedCapture) -> None:
    for chunk in iter(lambda: stream.read(64 * 1024), b""):
        capture.feed(chunk)


def _redact_filter_path(match: re.Match[str]) -> str:
    raw_path = match.group(2)
    if raw_path.startswith("<HOME>"):
        return match.group(0)
    posix_path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    if not posix_path.is_absolute() and not windows_path.is_absolute():
        return match.group(0)
    basename = windows_path.name if windows_path.is_absolute() else posix_path.name
    return f"{match.group(1)}<ABSOLUTE_PATH>/{basename or '<root>'}{match.group(3)}"


def redact_command(arguments: list[str]) -> tuple[str, ...]:
    redacted: list[str] = []
    hide_next = False
    for argument in arguments:
        if hide_next:
            redacted.append("***")
            hide_next = False
            continue
        normalized = argument.lower()
        if normalized in SENSITIVE_FLAGS:
            redacted.append(argument)
            hide_next = True
            continue
        if any(normalized.startswith(f"{flag}=") for flag in SENSITIVE_FLAGS):
            redacted.append(f"{argument.split('=', maxsplit=1)[0]}=***")
            continue
        home = str(Path.home())
        if argument == home:
            redacted.append("<HOME>")
        elif argument.startswith(f"{home}/") or argument.startswith(f"{home}\\"):
            home_relative = argument[len(home) :].replace("\\", "/")
            redacted.append(f"<HOME>{home_relative}")
        elif PurePosixPath(argument).is_absolute() or PureWindowsPath(argument).is_absolute():
            basename = (
                PureWindowsPath(argument).name
                if PureWindowsPath(argument).is_absolute()
                else PurePosixPath(argument).name
            )
            redacted.append(f"<ABSOLUTE_PATH>/{basename or '<root>'}")
        else:
            home_redacted = argument.replace(home, "<HOME>")
            redacted.append(FILTER_PATH_PATTERN.sub(_redact_filter_path, home_redacted))
    return tuple(redacted)


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    status: ProcessStatus
    return_code: int | None
    stdout: str
    stderr: str
    redacted_command: tuple[str, ...]
    recoverable: bool
    launch_error: str | None = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    termination_signal: str | None = None

    def to_step_result(self, step_id: str) -> StepResult:
        error_codes = {
            ProcessStatus.TIMED_OUT: "MEDIA_PROCESS_TIMEOUT",
            ProcessStatus.CANCELLED: "CANCELLED",
            ProcessStatus.FAILED: "MEDIA_PROCESS_FAILED",
        }
        return StepResult(
            step_id=step_id,
            status=self.status.value,
            recoverable=self.recoverable,
            error_code=error_codes.get(self.status),
            message=self.stderr[-1000:] or None,
        )


class ProcessRunner:
    def __init__(self, *, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None:
        if max_output_bytes < len(TRUNCATION_MARKER) + 2:
            raise ValueError("max_output_bytes is too small")
        self.max_output_bytes = max_output_bytes

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    @staticmethod
    def _termination_signal(return_code: int | None) -> str | None:
        if return_code is None or return_code >= 0:
            return None
        with suppress(ValueError):
            return signal.Signals(-return_code).name
        return None

    def run(
        self,
        arguments: list[str],
        *,
        timeout_seconds: float,
        cancellation: Event | None = None,
        cwd: Path | None = None,
    ) -> ProcessOutcome:
        if not arguments:
            raise ValueError("process arguments cannot be empty")
        redacted = redact_command(arguments)
        if cancellation is not None and cancellation.is_set():
            return ProcessOutcome(
                status=ProcessStatus.CANCELLED,
                return_code=None,
                stdout="",
                stderr="cancelled before process start",
                redacted_command=redacted,
                recoverable=True,
            )
        try:
            process = subprocess.Popen(
                arguments,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                shell=False,
            )
        except OSError as error:
            return ProcessOutcome(
                status=ProcessStatus.FAILED,
                return_code=None,
                stdout="",
                stderr=str(error),
                redacted_command=redacted,
                recoverable=True,
                launch_error=("not_found" if isinstance(error, FileNotFoundError) else "os_error"),
            )
        if process.stdout is None or process.stderr is None:
            process.kill()
            process.wait()
            raise RuntimeError("subprocess pipes were not created")
        stdout_capture = _BoundedCapture(self.max_output_bytes)
        stderr_capture = _BoundedCapture(self.max_output_bytes)
        stdout_reader = Thread(
            target=_drain,
            args=(process.stdout, stdout_capture),
            daemon=True,
        )
        stderr_reader = Thread(
            target=_drain,
            args=(process.stderr, stderr_capture),
            daemon=True,
        )
        stdout_reader.start()
        stderr_reader.start()
        deadline = time.monotonic() + timeout_seconds
        status: ProcessStatus
        while True:
            if cancellation is not None and cancellation.is_set():
                self._terminate_process(process)
                status = ProcessStatus.CANCELLED
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                status = ProcessStatus.TIMED_OUT
                break
            return_code = process.poll()
            if return_code is not None:
                status = (
                    ProcessStatus.COMPLETED
                    if return_code == 0
                    else ProcessStatus.FAILED
                )
                break
            time.sleep(min(0.05, remaining))

        stdout_reader.join(timeout=2)
        stderr_reader.join(timeout=2)
        if stdout_reader.is_alive() or stderr_reader.is_alive():
            process.stdout.close()
            process.stderr.close()
            stdout_reader.join(timeout=0.5)
            stderr_reader.join(timeout=0.5)
            status = ProcessStatus.FAILED
        return ProcessOutcome(
            status=status,
            return_code=process.returncode,
            stdout=stdout_capture.text(),
            stderr=stderr_capture.text(),
            redacted_command=redacted,
            recoverable=status is not ProcessStatus.COMPLETED,
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
            stdout_bytes=stdout_capture.total_bytes,
            stderr_bytes=stderr_capture.total_bytes,
            termination_signal=self._termination_signal(process.returncode),
        )
