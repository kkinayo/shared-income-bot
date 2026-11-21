"""Integration tests against a real PostgreSQL. Skipped unless TEST_DATABASE_URL is set."""
import asyncio
import os
from decimal import Decimal

import pytest

from app import db

DSN = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL is not set")


async def fresh_pool():
    pool = await db.create_pool(DSN, use_ssl=False)
    async with pool.acquire() as conn:
        await conn.execute("DROP VIEW IF EXISTS monthly_summary; DROP TABLE IF EXISTS ledger;")
    await db.apply_schema(pool)
    return pool


def test_income_balance_payout():
    async def scenario():
        pool = await fresh_pool()
        try:
            assert await db.get_balance(pool) == 0
            assert await db.add_income(pool, 1, Decimal("100.10")) == Decimal("100.10")
            assert await db.add_income(pool, 2, Decimal("0.20")) == Decimal("100.30")
            assert await db.payout_all(pool, 1) == Decimal("100.30")
            assert await db.get_balance(pool) == 0
            assert await db.payout_all(pool, 1) == 0  # nothing left to pay
            rows = await db.history(pool)
            assert [k for _, k, _ in rows] == ["payout", "income", "income"]
            month = (await db.monthly(pool))[0]
            assert month["income_total"] == Decimal("100.30")
            assert month["paid_out"] == Decimal("100.30")
        finally:
            await pool.close()

    asyncio.run(scenario())


def test_concurrent_payouts_pay_once():
    async def scenario():
        pool = await fresh_pool()
        try:
            await db.add_income(pool, 1, Decimal("50.00"))
            results = await asyncio.gather(*(db.payout_all(pool, 1) for _ in range(5)))
            assert sorted(results) == [0, 0, 0, 0, Decimal("50.00")]
            assert await db.get_balance(pool) == 0
        finally:
            await pool.close()

    asyncio.run(scenario())


def test_constraints_reject_bad_rows():
    async def scenario():
        pool = await fresh_pool()
        try:
            async with pool.acquire() as conn:
                with pytest.raises(Exception):
                    await conn.execute("INSERT INTO ledger (user_id, kind, amount) VALUES (1, 'income', -5)")
                with pytest.raises(Exception):
                    await conn.execute("INSERT INTO ledger (user_id, kind, amount) VALUES (1, 'refund', 5)")
        finally:
            await pool.close()

    asyncio.run(scenario())
