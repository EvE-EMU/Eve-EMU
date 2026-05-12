"""Fernet symmetric encryption for tokens at rest (``CORE_TOKEN_ENCRYPTION_KEY``)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class TokenCipher:
    def __init__(self, fernet: Fernet) -> None:
        self._fernet = fernet

    @classmethod
    def require(cls) -> TokenCipher:
        """Raise if encryption key is missing (required before persisting tokens)."""
        raw = (settings.token_encryption_key or "").strip()
        if not raw:
            raise RuntimeError(
                "CORE_TOKEN_ENCRYPTION_KEY is required to store user tokens. "
                "Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            return cls(Fernet(raw.encode("ascii")))
        except Exception as exc:
            raise RuntimeError("Invalid CORE_TOKEN_ENCRYPTION_KEY (must be a Fernet key)") from exc

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        try:
            return self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise ValueError("Could not decrypt token (wrong key or corrupt data)") from exc
