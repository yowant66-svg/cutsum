from __future__ import annotations

import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event

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
            redacted.append(f"<HOME>{argument[len(home) :]}")
        else:
            redacted.append(argument)
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
    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> tuple[str, str]:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            return process.communicate(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.communicate()

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
                text=True,
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
        deadline = time.monotonic() + timeout_seconds
        while True:
            if cancellation is not None and cancellation.is_set():
                stdout, stderr = self._terminate_process(process)
                return ProcessOutcome(
                    status=ProcessStatus.CANCELLED,
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    redacted_command=redacted,
                    recoverable=True,
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                stdout, stderr = process.communicate()
                return ProcessOutcome(
                    status=ProcessStatus.TIMED_OUT,
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    redacted_command=redacted,
                    recoverable=True,
                )
            try:
                stdout, stderr = process.communicate(timeout=min(0.05, remaining))
            except subprocess.TimeoutExpired:
                continue
            status = ProcessStatus.COMPLETED if process.returncode == 0 else ProcessStatus.FAILED
            return ProcessOutcome(
                status=status,
                return_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                redacted_command=redacted,
                recoverable=status is not ProcessStatus.COMPLETED,
            )
