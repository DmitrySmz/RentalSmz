
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_enum') THEN
    CREATE TYPE role_enum AS ENUM ('admin','manager','cashier');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'condition_status_enum') THEN
    CREATE TYPE condition_status_enum AS ENUM ('new','good','worn','broken','lost');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contract_status_enum') THEN
    CREATE TYPE contract_status_enum AS ENUM ('draft','active','closed','overdue','canceled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_type_enum') THEN
    CREATE TYPE payment_type_enum AS ENUM ('rent','deposit','deposit_refund','penalty');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method_enum') THEN
    CREATE TYPE payment_method_enum AS ENUM ('cash','card','online');
  END IF;
END$$;


CREATE TABLE IF NOT EXISTS clients (
  client_id      SERIAL PRIMARY KEY,
  email          VARCHAR(255) NOT NULL UNIQUE,
  password_hash  VARCHAR(255) NOT NULL,
  phone          VARCHAR(50),
  first_name     VARCHAR(100),
  last_name      VARCHAR(100),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS rental_points (
  rental_point_id  SERIAL PRIMARY KEY,
  name             VARCHAR(200) NOT NULL,
  address          VARCHAR(255),
  phone            VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS employees (
  employee_id     SERIAL PRIMARY KEY,
  login           VARCHAR(100) NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NOT NULL,
  first_name      VARCHAR(100),
  last_name       VARCHAR(100),
  role            role_enum NOT NULL,
  rental_point_id INT NOT NULL REFERENCES rental_points(rental_point_id) ON UPDATE CASCADE,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS categories (
  category_id   SERIAL PRIMARY KEY,
  name          VARCHAR(150) NOT NULL UNIQUE,
  description   TEXT
);

CREATE TABLE IF NOT EXISTS products (
  product_id           SERIAL PRIMARY KEY,
  category_id          INT NOT NULL REFERENCES categories(category_id) ON UPDATE CASCADE,
  name                 VARCHAR(200) NOT NULL,
  brand                VARCHAR(150),
  description          TEXT,
  volume_liters        INT,
  people_count         INT,
  temperature_min      INT,
  default_daily_price  NUMERIC(10,2) NOT NULL,
  default_deposit      NUMERIC(10,2) NOT NULL,
  CONSTRAINT ck_products_prices_nonneg CHECK (default_daily_price >= 0 AND default_deposit >= 0)
);

CREATE INDEX IF NOT EXISTS ix_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS ix_products_name ON products(name);

CREATE TABLE IF NOT EXISTS items (
  item_id           SERIAL PRIMARY KEY,
  product_id        INT NOT NULL REFERENCES products(product_id) ON UPDATE CASCADE,
  rental_point_id   INT NOT NULL REFERENCES rental_points(rental_point_id) ON UPDATE CASCADE,
  inventory_number  VARCHAR(100) NOT NULL UNIQUE,
  color             VARCHAR(50),
  size              VARCHAR(50),
  condition_status  condition_status_enum NOT NULL,
  is_available      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_items_product ON items(product_id);
CREATE INDEX IF NOT EXISTS ix_items_point_available ON items(rental_point_id, is_available);

CREATE TABLE IF NOT EXISTS rental_contracts (
  contract_id          SERIAL PRIMARY KEY,
  client_id            INT NOT NULL REFERENCES clients(client_id) ON UPDATE CASCADE,
  employee_id          INT NOT NULL REFERENCES employees(employee_id) ON UPDATE CASCADE,
  rental_point_id      INT NOT NULL REFERENCES rental_points(rental_point_id) ON UPDATE CASCADE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  start_date           DATE NOT NULL,
  planned_end_date     DATE NOT NULL,
  actual_end_date      DATE,
  status               contract_status_enum NOT NULL,
  total_rent_amount    NUMERIC(10,2),
  total_deposit_amount NUMERIC(10,2),
  CONSTRAINT ck_contract_dates CHECK (planned_end_date >= start_date),
  CONSTRAINT ck_contract_actual CHECK (actual_end_date IS NULL OR actual_end_date >= start_date),
  CONSTRAINT ck_contract_totals_nonneg CHECK (
    (total_rent_amount    IS NULL OR total_rent_amount    >= 0) AND
    (total_deposit_amount IS NULL OR total_deposit_amount >= 0)
  )
);

CREATE INDEX IF NOT EXISTS ix_contracts_client ON rental_contracts(client_id);
CREATE INDEX IF NOT EXISTS ix_contracts_status ON rental_contracts(status);
CREATE INDEX IF NOT EXISTS ix_contracts_period ON rental_contracts(start_date, planned_end_date);

CREATE TABLE IF NOT EXISTS contract_items (
  contract_item_id  SERIAL PRIMARY KEY,
  contract_id       INT NOT NULL REFERENCES rental_contracts(contract_id) ON DELETE CASCADE,
  item_id           INT NOT NULL REFERENCES items(item_id) ON UPDATE CASCADE,
  daily_price       NUMERIC(10,2) NOT NULL,
  deposit_amount    NUMERIC(10,2) NOT NULL,
  CONSTRAINT uq_contract_item UNIQUE (contract_id, item_id),
  CONSTRAINT ck_contract_item_prices_nonneg CHECK (daily_price >= 0 AND deposit_amount >= 0)
);

CREATE INDEX IF NOT EXISTS ix_contract_items_contract ON contract_items(contract_id);
CREATE INDEX IF NOT EXISTS ix_contract_items_item ON contract_items(item_id);

CREATE TABLE IF NOT EXISTS payments (
  payment_id   SERIAL PRIMARY KEY,
  contract_id  INT NOT NULL REFERENCES rental_contracts(contract_id) ON DELETE CASCADE,
  payment_date TIMESTAMPTZ NOT NULL DEFAULT now(),
  amount       NUMERIC(10,2) NOT NULL,
  type         payment_type_enum NOT NULL,
  method       payment_method_enum,
  CONSTRAINT ck_payment_nonzero CHECK (amount <> 0)
);

CREATE INDEX IF NOT EXISTS ix_payments_contract ON payments(contract_id);
CREATE INDEX IF NOT EXISTS ix_payments_date ON payments(payment_date);


