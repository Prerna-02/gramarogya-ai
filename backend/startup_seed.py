"""Idempotent startup seeding for cloud deployment (Hugging Face Space, etc.).

Unlike ``scripts/init_db.py`` this never issues ``CREATE DATABASE`` — a managed
Postgres provider (Neon, Supabase, …) already gives you a ready database, and
the login role usually cannot create new databases. This module instead:

  1. creates any missing tables,
  2. applies the small post-release column migrations,
  3. seeds demand/resource/staff/facility data *only if the database is empty*
     (so data created at runtime survives container restarts),
  4. ensures an administrator login exists.

It is safe to run on every container start. Controlled by environment:
  SEED_ON_STARTUP  '1' (default) to run, '0' to skip entirely.
  ADMIN_USERNAME   default 'admin'
  ADMIN_PASSWORD   default 'admin123'
"""
from __future__ import annotations

import os

from sqlalchemy import inspect, select, text

from backend.auth import hash_password
from backend.db import Base, SessionLocal, engine
import backend.db_models  # noqa: F401  (registers models)
from backend.db_models import User


def _database_is_empty() -> bool:
    """True on a fresh database (no seeded demand rows yet)."""
    insp = inspect(engine)
    if not insp.has_table("daily_demand"):
        return True
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM daily_demand")).scalar()
    return not count


def _ensure_admin() -> str:
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            db.add(User(username=username, password_hash=hash_password(password),
                        role="administrator"))
        else:
            user.password_hash = hash_password(password)
            user.role = "administrator"
        db.commit()
    return username


def run() -> None:
    if os.environ.get("SEED_ON_STARTUP", "1") == "0":
        print("[startup_seed] SEED_ON_STARTUP=0 — skipping.")
        return

    # 1. Tables + 2. post-release migrations.
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE nearby_facilities ADD COLUMN IF NOT EXISTS latitude double precision"))
        conn.execute(text("ALTER TABLE nearby_facilities ADD COLUMN IF NOT EXISTS longitude double precision"))

    # 3. Seed data only on a fresh database.
    if _database_is_empty():
        from backend.seed_database import seed
        print("[startup_seed] Empty database — seeding from data/ CSVs …")
        seed()
    else:
        print("[startup_seed] Data already present — skipping data seed.")

    # 4. Admin login (always ensured; password can be rotated via env).
    username = _ensure_admin()
    print(f"[startup_seed] Ready. Administrator login: {username}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 — never let seeding crash the container
        print(f"[startup_seed] WARNING: seeding failed ({exc!r}); starting the API anyway.")
