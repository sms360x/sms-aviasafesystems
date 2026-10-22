# ============================================================================
# FILE: apply_sql_migration.py
# PATH: backend/scripts/apply_sql_migration.py
# PURPOSE: Apply a Supabase-style .sql migration file to the configured
#          PostgreSQL database.
#
#   python backend/scripts/apply_sql_migration.py supabase/migrations/<file>.sql
#
# The file is executed as one simple-protocol batch, so it may contain
# multiple statements and dollar-quoted function bodies. The connection runs
# as the database owner (no request identity), which is required for DDL.
# ============================================================================

import asyncio
import logging
import sys
from pathlib import Path

# The full migration text is echoed by SQLAlchemy's engine logger; on a
# cp1252 console that crashes the logging handler, so keep the engine quiet.
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.session import get_engine  # noqa: E402


async def _apply(sql: str) -> None:
    engine = get_engine()
    async with engine.connect() as conn:
        # asyncpg's Connection.execute() with no arguments uses the simple
        # query protocol, which accepts a multi-statement batch (SQLAlchemy's
        # exec_driver_sql would try to PREPARE the whole file instead).
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(sql)
        await conn.commit()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: apply_sql_migration.py <migration.sql>")
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        print(f"migration not found: {path}")
        return 2
    sql = path.read_text(encoding="utf-8")
    if not settings.DATABASE_URL:
        print("DATABASE_URL is not configured (backend/.env)")
        return 2
    asyncio.run(_apply(sql))
    print(f"applied: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
