import hashlib
import secrets

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2 with SHA-256 and a random salt."""
    salt = secrets.token_hex(16)
    # Using 100,000 iterations for secure hashing
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"pbkdf2_sha256$100000${salt}${key.hex()}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a password against a PBKDF2 hash."""
    if not password_hash:
        return False
    try:
        parts = password_hash.split('$')
        if len(parts) != 4:
            return False
        algorithm, iterations, salt, key_hex = parts
        if algorithm != 'pbkdf2_sha256':
            return False
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            int(iterations)
        )
        return secrets.compare_digest(key.hex(), key_hex)
    except Exception:
        return False
