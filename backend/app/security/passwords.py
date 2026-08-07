"""Password hashing.

Argon2id, via argon2-cffi. It is the current OWASP recommendation and is memory-hard,
which is the property that actually degrades large-scale parallel cracking. bcrypt was
rejected because it silently truncates input at 72 bytes, turning a long passphrase into
a shorter secret than the user believes they chose. Werkzeug's PBKDF2 is available
without an extra dependency but is strictly weaker for no meaningful saving.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi's defaults track the library authors' current guidance, so they are used
# as given rather than hand-tuned to numbers that would silently go stale.
_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(password_hash: str, plain: str) -> bool:
    """Check a password, returning False rather than raising on any failure.

    Callers only ever need the boolean, and letting the distinction between a wrong
    password and a malformed stored hash escape as different exceptions invites a login
    handler that responds differently to each.
    """

    try:
        return _hasher.verify(password_hash, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Report whether a stored hash predates the current cost parameters.

    When argon2-cffi raises its defaults, existing hashes stay valid but weaker than
    they should be. The login handler rehashes on a successful verification, so accounts
    are upgraded as people sign in rather than needing a forced reset.
    """

    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
