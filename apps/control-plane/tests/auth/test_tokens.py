import hashlib
import re

import pytest
from pullfrog_azure_api.auth.tokens import csrf_matches, digest_token, new_opaque_token


def test_new_opaque_token_has_at_least_256_bits_of_url_safe_entropy() -> None:
    token = new_opaque_token()

    assert len(token) >= 43
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token) is not None


def test_digest_token_returns_a_sha256_digest() -> None:
    digest = digest_token("browser-visible-token")

    assert digest == hashlib.sha256(b"browser-visible-token").digest()
    assert len(digest) == 32


def test_csrf_matches_equal_raw_values_and_the_stored_digest() -> None:
    csrf_token = "csrf-token"

    assert csrf_matches(csrf_token, csrf_token, digest_token(csrf_token)) is True


@pytest.mark.parametrize(
    ("cookie_value", "header_value", "stored_token"),
    (
        (None, "csrf-token", "csrf-token"),
        ("csrf-token", None, "csrf-token"),
        ("csrf-token", "different-token", "csrf-token"),
        ("csrf-token", "csrf-token", "different-token"),
    ),
)
def test_csrf_matches_rejects_missing_or_mismatched_values(
    cookie_value: str | None,
    header_value: str | None,
    stored_token: str,
) -> None:
    assert csrf_matches(cookie_value, header_value, digest_token(stored_token)) is False
