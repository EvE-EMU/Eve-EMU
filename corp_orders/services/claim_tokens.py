from __future__ import annotations

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

_SIGNER = TimestampSigner(salt="corp-orders-claim-v1")
_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days — Discord link buttons stay valid


def make_claim_token(order_pk: int) -> str:
    return _SIGNER.sign(str(order_pk))


def read_claim_token(token: str) -> int | None:
    try:
        value = _SIGNER.unsign(token, max_age=_MAX_AGE_SECONDS)
        return int(value)
    except (BadSignature, SignatureExpired, ValueError):
        return None
