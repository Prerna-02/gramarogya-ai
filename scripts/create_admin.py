"""Create (or update) an administrator user (Phase 9).

Usage:
    python scripts/create_admin.py <username> <password> [email] [role]

Defaults: role=administrator. Passwords are stored hashed (bcrypt).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from backend.auth import hash_password
from backend.db import SessionLocal
from backend.db_models import User


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    username, password = sys.argv[1], sys.argv[2]
    email = sys.argv[3] if len(sys.argv) > 3 else None
    role = sys.argv[4] if len(sys.argv) > 4 else "administrator"

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user:
            user.password_hash = hash_password(password)
            user.role = role
            if email:
                user.email = email
            action = "updated"
        else:
            db.add(User(username=username, email=email, password_hash=hash_password(password), role=role))
            action = "created"
        db.commit()
    print(f"Admin user '{username}' {action} (role={role}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
