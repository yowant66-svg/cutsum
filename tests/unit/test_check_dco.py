from __future__ import annotations

from scripts.check_dco import has_dco_signoff


def test_dco_accepts_standard_signed_off_by_trailer() -> None:
    message = "feat: add example\n\nSigned-off-by: DXBATM <yowant66@gmail.com>\n"
    assert has_dco_signoff(message) is True


def test_dco_rejects_missing_or_malformed_trailers() -> None:
    assert has_dco_signoff("feat: unsigned change\n") is False
    assert has_dco_signoff("Signed-off-by: DXBATM\n") is False
    assert has_dco_signoff("Signed-off-by: <not-an-email>\n") is False
