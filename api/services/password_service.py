from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


class PasswordService:
    ALGORITHM = "pbkdf2_sha256"
    ITERATIONS = 260000
    SALT_BYTES = 16

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = secrets.token_bytes(cls.SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            cls.ITERATIONS,
        )
        salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
        hash_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
        return f"{cls.ALGORITHM}${cls.ITERATIONS}${salt_b64}${hash_b64}"

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        try:
            algorithm, iterations_str, salt_b64, hash_b64 = stored_hash.split("$", 3)
            if algorithm != cls.ALGORITHM:
                return False

            iterations = int(iterations_str)
            salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
            expected_hash = base64.urlsafe_b64decode(hash_b64.encode("ascii"))

            current_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                iterations,
            )
            return hmac.compare_digest(current_hash, expected_hash)
        except Exception:
            return False
