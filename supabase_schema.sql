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

-- Watched routes (dynamic — managed via Telegram bot)
CREATE TABLE IF NOT EXISTS watched_routes (
    id          BIGSERIAL PRIMARY KEY,
    type        TEXT    NOT NULL,             -- 'flights' | 'trains' | 'hotels'
    from_code   TEXT    NOT NULL,             -- IATA/KAI code, or destination for hotels
    to_code     TEXT    NOT NULL,
    label       TEXT    NOT NULL,             -- human-readable e.g. "CGK → DPS"
    travel_date DATE    NOT NULL,             -- departure date or check-in date
    max_price   NUMERIC NOT NULL,             -- per night for hotels
    currency    TEXT    NOT NULL DEFAULT 'IDR',
    seat_class  TEXT,                         -- trains only: EKS | BIS | EKO
    params      JSONB   DEFAULT '{}',         -- type-specific extras e.g. {check_out, guests}
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
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

-- Route subscribers — one row per (route, user) pair
CREATE TABLE IF NOT EXISTS route_subscribers (
    id         BIGSERIAL PRIMARY KEY,
    route_id   BIGINT NOT NULL REFERENCES watched_routes(id) ON DELETE CASCADE,
    chat_id    TEXT   NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (route_id, chat_id)
);

-- Run these if the tables already exist (migration for existing installs):
-- ALTER TABLE watched_routes ADD COLUMN IF NOT EXISTS params JSONB DEFAULT '{}';
-- CREATE TABLE IF NOT EXISTS route_subscribers (id BIGSERIAL PRIMARY KEY, route_id BIGINT NOT NULL REFERENCES watched_routes(id) ON DELETE CASCADE, chat_id TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE (route_id, chat_id));
