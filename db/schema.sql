-- Append-only ledger: every income and every payout is a row.
-- The balance is never stored; it is always SUM(amount).

CREATE TABLE IF NOT EXISTS ledger (
    id          BIGSERIAL     PRIMARY KEY,
    user_id     BIGINT        NOT NULL,
    kind        TEXT          NOT NULL CHECK (kind IN ('income', 'payout')),
    amount      NUMERIC(12,2) NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    -- incomes are positive, payouts are negative
    CONSTRAINT ledger_amount_sign CHECK (
        (kind = 'income' AND amount > 0) OR
        (kind = 'payout' AND amount < 0)
    )
);

CREATE INDEX IF NOT EXISTS ledger_created_at_idx ON ledger (created_at DESC);

-- Monthly totals for the /stats screen
CREATE OR REPLACE VIEW monthly_summary AS
SELECT
    date_trunc('month', created_at)::date                         AS month,
    count(*) FILTER (WHERE kind = 'income')                       AS income_entries,
    coalesce(sum(amount) FILTER (WHERE kind = 'income'), 0)       AS income_total,
    coalesce(-sum(amount) FILTER (WHERE kind = 'payout'), 0)      AS paid_out
FROM ledger
GROUP BY 1;
