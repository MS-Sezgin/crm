"""Password hashing. Passwords are stored as salted PBKDF2 hashes, never as plain text.

Stored format:  pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>
Only the Python standard library is used, so there is nothing extra to install.
"""
import hashlib
import hmac
import os


class PasswordHasher:
    ALGORITHM = "pbkdf2_sha256"

    def __init__(self, iterations=200_000):
        self.iterations = iterations

    def hash(self, password):
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return f"{self.ALGORITHM}${self.iterations}${salt.hex()}${digest.hex()}"

    def is_hashed(self, stored):
        return isinstance(stored, str) and stored.startswith(self.ALGORITHM + "$")

    def verify(self, password, stored):
        """True when the password matches the stored hash. A malformed hash never matches."""
        try:
            algorithm, iterations, salt_hex, hash_hex = stored.split("$")
            if algorithm != self.ALGORITHM:
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        except (ValueError, AttributeError):
            return False
        return hmac.compare_digest(digest.hex(), hash_hex)
