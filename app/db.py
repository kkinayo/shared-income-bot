"""PostgreSQL access layer (asyncpg). All money is NUMERIC on the database side."""
import ssl
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import asyncpg

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
PAYOUT_LOCK_ID = 727001  # any constant: serializes concurrent payouts


async def create_pool(dsn: str, use_ssl: bool) -> asyncpg.Pool:
    ssl_ctx = ssl.create_default_context() if use_ssl else None
    return await asyncpg.create_pool(dsn=dsn, ssl=ssl_ctx, min_size=1, max_size=5)


async def apply_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA.read_text(encoding="utf-8"))


async def add_income(pool: asyncpg.Pool, user_id: int, amount: Decimal) -> Decimal:
    """Insert an income row and return the new balance (one round trip)."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            WITH ins AS (
                INSERT INTO ledger (user_id, kind, amount)
                VALUES ($1, 'income', $2)
                RETURNING amount
            )
            SELECT coalesce((SELECT sum(amount) FROM ledger), 0) + (SELECT amount FROM ins)
            """,
            user_id,
            amount,
        )


async def get_balance(pool: asyncpg.Pool) -> Decimal:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT coalesce(sum(amount), 0) FROM ledger")


async def payout_all(pool: asyncpg.Pool, user_id: int) -> Decimal:
    """Record that the whole balance was paid out. Returns the amount, 0 if nothing to pay.

    The advisory lock makes two simultaneous payouts run one after another,
    so the same money cannot be paid out twice.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", PAYOUT_LOCK_ID)
            paid = await conn.fetchval(
                """
                INSERT INTO ledger (user_id, kind, amount)
                SELECT $1, 'payout', -sum(amount)
                FROM ledger
                HAVING sum(amount) > 0
                RETURNING -amount
                """,
                user_id,
            )
    return paid or Decimal("0")


async def history(pool: asyncpg.Pool, limit: int = 10) -> list[tuple[datetime, str, Decimal]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT created_at, kind, amount FROM ledger ORDER BY created_at DESC, id DESC LIMIT $1",
            limit,
        )
    return [(r["created_at"], r["kind"], r["amount"]) for r in rows]


async def monthly(pool: asyncpg.Pool, months: int = 6) -> list[asyncpg.Record]:
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT month, income_entries, income_total, paid_out "
            "FROM monthly_summary ORDER BY month DESC LIMIT $1",
            months,
        )
