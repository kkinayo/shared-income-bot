# Shared Income Bot

[![CI](https://github.com/kkinayo/shared-income-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/kkinayo/shared-income-bot/actions/workflows/ci.yml)

Telegram bot for tracking shared income: send an amount to log it, see the balance, split it into buckets (for example 40 / 40 / 20 between a joint account, savings and personal money) and mark it as paid out. Data lives in PostgreSQL.

I first built it as a quick personal tool that kept one mutable balance row. This version rebuilds the data model properly: an append-only ledger with exact decimal money and database-enforced rules.

## Features

| Action | What happens |
|---|---|
| Send `1500` or `1 250,50` | Records an income, replies with the new balance |
| 📊 Баланс | Current balance |
| ✂️ Разделить | Balance split by the configured percentages, to the cent |
| 📜 История | Last 10 operations |
| 📈 По месяцам | Monthly income and payouts |
| ✅ Выплачено | Records a payout of the whole balance |
| `/id` | Shows your Telegram ID, to add to the allow-list |

## Data model

```sql
ledger (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT        NOT NULL,
    kind        TEXT          NOT NULL CHECK (kind IN ('income', 'payout')),
    amount      NUMERIC(12,2) NOT NULL,          -- + for income, − for payout
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
)
-- + view monthly_summary, index on created_at
```

Design decisions:

- **Ledger instead of a balance column.** Nothing is updated or deleted; the balance is `SUM(amount)`. Every change has an author and a timestamp, and history and monthly stats come for free.
- **`NUMERIC(12,2)`, not `float`.** Money stays exact; Python uses `Decimal` end to end.
- **Rules in the database.** A `CHECK` constraint makes incomes positive and payouts negative whatever the application sends.
- **Safe payouts.** "Pay out the balance" is one `INSERT … SELECT -SUM(amount) … HAVING SUM(amount) > 0` inside a transaction with `pg_advisory_xact_lock`, so two people pressing the button at the same moment cannot pay the same money twice. A test fires five payouts concurrently and checks that exactly one goes through.
- **New balance in one round trip.** Adding an income uses a data-modifying CTE (`WITH ins AS (INSERT … RETURNING …) SELECT …`).
- **Exact split.** Shares are rounded to cents and the remainder goes to the last bucket, so the parts always add up to the balance.

## Stack

Python 3.11 · aiogram 3 · asyncpg · PostgreSQL 16 · Docker Compose · pytest · GitHub Actions · Render (webhook) / Neon (managed Postgres)

## Run locally

```bash
cp .env.example .env        # put your BOT_TOKEN from @BotFather into .env
docker compose up --build   # starts PostgreSQL and the bot (polling mode)
```

Without Docker: create a PostgreSQL database, set `DATABASE_URL` and `DB_SSL=false` in the environment, then `pip install -r requirements.txt` and `python -m app.bot`. The schema is applied on start.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest                                   # unit tests (parsing, split)
TEST_DATABASE_URL=postgresql://... python -m pytest  # + integration tests on a real PostgreSQL
```

CI runs both on every push, with PostgreSQL as a service container.

## Deploy

`render.yaml` deploys the bot to Render as a web service in webhook mode; `DATABASE_URL` can point to a managed PostgreSQL such as Neon (`DB_SSL=true`).

## Project layout

```
app/
  bot.py      Telegram handlers, webhook / polling startup
  db.py       SQL queries (asyncpg)
  money.py    amount parsing and exact splitting (pure functions)
  config.py   settings from environment variables
db/schema.sql table, constraints, index, view
tests/        unit + PostgreSQL integration tests
```
