"""Create the gramarogya database (if needed) and all tables (Phase 4).

Reads DATABASE_URL from `.env`. Connects to the server's maintenance database
to CREATE DATABASE, then creates every table from the SQLAlchemy models.

Usage:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import settings  # noqa: E402


def main() -> int:
    url = make_url(settings.database_url)
    target_db = url.database
    if not target_db:
        print("DATABASE_URL has no database name.")
        return 1

    server_url = url.set(database="postgres")
    print(f"Connecting to server {server_url.host}:{server_url.port} as {server_url.username} ...")
    try:
        eng = create_engine(server_url, isolation_level="AUTOCOMMIT")
        with eng.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target_db}
            ).scalar()
            if exists:
                print(f"Database '{target_db}' already exists.")
            else:
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
                print(f"Created database '{target_db}'.")
    except Exception as e:  # noqa: BLE001
        print(f"\nCould not connect / create database: {e}")
        print("Check the password and host in .env (DATABASE_URL).")
        return 1

    # Create tables in the target database.
    from backend.db import Base, engine
    import backend.db_models  # noqa: F401  (registers models)

    Base.metadata.create_all(engine)

    # Lightweight migrations for columns added after the first release.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE nearby_facilities ADD COLUMN IF NOT EXISTS latitude double precision"))
        conn.execute(text("ALTER TABLE nearby_facilities ADD COLUMN IF NOT EXISTS longitude double precision"))

    print(f"Created {len(Base.metadata.tables)} tables: {', '.join(sorted(Base.metadata.tables))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
