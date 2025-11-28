"""
PostgreSQL connection helper.

This module keeps a dedicated Postgres entry point in case other parts of the
app import `database_pg`. The main database logic now lives in `database.py`
and auto-switches between SQLite and Postgres via DATABASE_URL, but this file
offers an explicit connector if you need it.
"""

import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "psycopg2 is required for PostgreSQL support. "
        "Install the dependency listed in requirements.txt."
    ) from exc


def get_pg_connection():
    """
    Return a psycopg2 connection using the DATABASE_URL environment variable.

    Raises:
        RuntimeError: if DATABASE_URL is missing.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")

    # Render often provides postgres://; psycopg2 expects postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
