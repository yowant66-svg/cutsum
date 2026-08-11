from __future__ import annotations

import io
import json

import pytest

from scripts.verify_published_release import verify_pypi_release


class JsonResponse(io.BytesIO):
    def __enter__(self) -> JsonResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_verify_pypi_release_accepts_exact_distribution_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "info": {"version": "0.1.0a4"},
        "urls": [
            {"filename": "cutsum-0.1.0a4.tar.gz", "digests": {"sha256": "a" * 64}},
            {
                "filename": "cutsum-0.1.0a4-py3-none-any.whl",
                "digests": {"sha256": "b" * 64},
            },
        ],
    }
    monkeypatch.setattr(
        "scripts.verify_published_release.urlopen",
        lambda *_args, **_kwargs: JsonResponse(json.dumps(payload).encode()),
    )

    observed = verify_pypi_release(
        repository_url="https://pypi.example",
        version="0.1.0a4",
        expected_hashes={
            "cutsum-0.1.0a4.tar.gz": "a" * 64,
            "cutsum-0.1.0a4-py3-none-any.whl": "b" * 64,
        },
    )

    assert observed == {
        "cutsum-0.1.0a4.tar.gz": "a" * 64,
        "cutsum-0.1.0a4-py3-none-any.whl": "b" * 64,
    }


@pytest.mark.parametrize(
    "published",
    [
        {"cutsum-0.1.0a4.tar.gz": "a" * 64},
        {
            "cutsum-0.1.0a4.tar.gz": "a" * 64,
            "cutsum-0.1.0a4-py3-none-any.whl": "c" * 64,
        },
    ],
)
def test_verify_pypi_release_rejects_missing_or_changed_files(
    monkeypatch: pytest.MonkeyPatch,
    published: dict[str, str],
) -> None:
    payload = {
        "info": {"version": "0.1.0a4"},
        "urls": [
            {"filename": filename, "digests": {"sha256": digest}}
            for filename, digest in published.items()
        ],
    }
    monkeypatch.setattr(
        "scripts.verify_published_release.urlopen",
        lambda *_args, **_kwargs: JsonResponse(json.dumps(payload).encode()),
    )

    with pytest.raises(ValueError, match="hashes do not match"):
        verify_pypi_release(
            repository_url="https://pypi.example",
            version="0.1.0a4",
            expected_hashes={
                "cutsum-0.1.0a4.tar.gz": "a" * 64,
                "cutsum-0.1.0a4-py3-none-any.whl": "b" * 64,
            },
        )
