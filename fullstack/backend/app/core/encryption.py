import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class FieldEncryptor:
    def __init__(self, key: str | None = None):
        configured_key = key or settings.field_encryption_key
        self._fernet: Fernet | None = None
        if configured_key:
            digest = hashlib.sha256(configured_key.encode("utf-8")).digest()
            self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        if not self._fernet:
            return value
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        if not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt value with current key") from exc


field_encryptor = FieldEncryptor()
