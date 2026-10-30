# backend/scripts/normalize_report_statuses.py
"""Spec #7b - normalize reports.status to clean 'Open'/'Closed' values."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.session import get_engine
import asyncio

async def main():
    engine = get_engine()
    async with engine.begin() as conn:
        r1 = await conn.execute(__import__('sqlalchemy').text(
            "UPDATE reports SET status='Open' WHERE lower(trim(status)) IN ('open','new')"
        ))
        r2 = await conn.execute(__import__('sqlalchemy').text(
            "UPDATE reports SET status='Closed' WHERE lower(trim(status))='closed'"
        ))
        print("Open rows:", r1.rowcount, "Closed rows:", r2.rowcount)

asyncio.run(main())
