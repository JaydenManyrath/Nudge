"""Set (or reset) a user's login password.

Usage:
    python -m scripts.set_password <email> <password>
    python -m scripts.set_password maya@nudge.local demo1234

Needed because the login flow requires a password_hash and the app has no
self-service signup. Also useful to give the seeded demo accounts a known
password on an already-initialized database.
"""

import sys

from werkzeug.security import generate_password_hash

from models import get_db


def set_password(email: str, password: str) -> bool:
    with get_db() as db:
        cursor = db.execute(
            "UPDATE users SET password_hash = ? WHERE lower(email) = lower(?)",
            (generate_password_hash(password), email),
        )
        db.commit()
        return cursor.rowcount > 0


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.set_password <email> <password>")
        raise SystemExit(2)

    email, password = sys.argv[1], sys.argv[2]
    if set_password(email, password):
        print(f"Password updated for {email}")
    else:
        print(f"No user found with email {email}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
