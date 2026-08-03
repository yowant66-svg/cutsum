from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from universal_cutup.domain.errors import CutupError, ErrorCode


@dataclass(frozen=True, slots=True)
class SafePathPolicy:
    output_root: Path

    def resolved_root(self) -> Path:
        return self.output_root.resolve(strict=False)

    def resolve_output(self, relative_path: str) -> Path:
        posix_path = PurePosixPath(relative_path)
        windows_path = PureWindowsPath(relative_path)
        if (
            posix_path.is_absolute()
            or ".." in posix_path.parts
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or ".." in windows_path.parts
        ):
            raise CutupError(
                ErrorCode.PATH_OUTSIDE_ROOT,
                "output path must be relative and cannot traverse parents",
                category="permission/policy",
            )
        root = self.resolved_root()
        candidate = (root / posix_path).resolve(strict=False)
        if not candidate.is_relative_to(root):
            raise CutupError(
                ErrorCode.PATH_OUTSIDE_ROOT,
                "output path resolves outside output root",
                category="permission/policy",
            )
        if candidate.exists():
            raise CutupError(
                ErrorCode.OUTPUT_EXISTS,
                f"output already exists: {posix_path.name}",
                category="conflict",
            )
        return candidate
