import hashlib
import hmac
import secrets


def new_opaque_token() -> str:
    """Generate a browser token with at least 256 bits of URL-safe entropy."""
    return secrets.token_urlsafe(32)


def digest_token(token: str) -> bytes:
    """Return the SHA-256 digest retained for a browser-visible token."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def csrf_matches(
    cookie_value: str | None,
    header_value: str | None,
    stored_digest: bytes,
) -> bool:
    """Verify equal presented CSRF values against the persisted token digest."""
    if cookie_value is None or header_value is None:
        return False
    if not hmac.compare_digest(cookie_value, header_value):
        return False
    return hmac.compare_digest(digest_token(cookie_value), stored_digest)
