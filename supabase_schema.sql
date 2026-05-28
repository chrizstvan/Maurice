-- Run this in the Supabase SQL editor

-- Price history (Phase 0)
CREATE TABLE IF NOT EXISTS price_history (
    id          BIGSERIAL PRIMARY KEY,
    route_label TEXT    NOT NULL,
    price       NUMERIC NOT NULL,
    currency    TEXT    NOT NULL DEFAULT 'IDR',
    details     JSONB,
    checked_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Budgets (Phase 1)
CREATE TABLE IF NOT EXISTS budgets (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT    NOT NULL,
    type         TEXT    NOT NULL,  -- 'trip' | 'monthly'
    start_date   DATE    NOT NULL,
    end_date     DATE    NOT NULL,
    total_amount NUMERIC NOT NULL,
    currency     TEXT    NOT NULL DEFAULT 'IDR',
    active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budget_categories (
    id           BIGSERIAL PRIMARY KEY,
    budget_id    BIGINT REFERENCES budgets(id) ON DELETE CASCADE,
    name         TEXT    NOT NULL,
    limit_amount NUMERIC
);

CREATE TABLE IF NOT EXISTS expenses (
    id           BIGSERIAL PRIMARY KEY,
    budget_id    BIGINT REFERENCES budgets(id) ON DELETE CASCADE,
    category     TEXT    NOT NULL,
    amount       NUMERIC NOT NULL,
    currency     TEXT    NOT NULL DEFAULT 'IDR',
    description  TEXT,
    expense_date DATE    NOT NULL,
    source       TEXT    NOT NULL,  -- 'receipt' | 'manual' | 'recurring'
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recurring_expenses (
    id       BIGSERIAL PRIMARY KEY,
    name     TEXT    NOT NULL,
    category TEXT    NOT NULL,
    amount   NUMERIC NOT NULL,
    currency TEXT    NOT NULL DEFAULT 'IDR',
    active   BOOLEAN NOT NULL DEFAULT TRUE
);
