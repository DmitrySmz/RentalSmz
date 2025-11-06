CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  full_name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),
  is_active BOOLEAN DEFAULT TRUE,
  is_superuser BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE equipment_categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  description TEXT
);

CREATE TABLE equipment (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  category_id INT REFERENCES equipment_categories(id),
  price_per_day NUMERIC(10,2) NOT NULL,
  total_quantity INT NOT NULL CHECK (total_quantity >= 0),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE rental_orders (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id),
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, active, completed, cancelled
  total_cost NUMERIC(10,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  CHECK (end_date >= start_date)
);

CREATE TABLE rental_items (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES rental_orders(id) ON DELETE CASCADE,
  equipment_id INT NOT NULL REFERENCES equipment(id),
  quantity INT NOT NULL CHECK (quantity > 0),
  price_per_day NUMERIC(10,2) NOT NULL
);

CREATE INDEX idx_rental_period ON rental_orders (start_date, end_date);
CREATE INDEX idx_rental_items_equipment ON rental_items (equipment_id);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  order_id INT NOT NULL REFERENCES rental_orders(id) ON DELETE CASCADE,
  amount NUMERIC(10,2) NOT NULL,
  status VARCHAR(20) DEFAULT 'pending', -- pending, completed, failed
  payment_method VARCHAR(50),
  transaction_id VARCHAR(100),
  payment_date TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sessions (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id),
  jti UUID NOT NULL,    -- ID токена
  session_token VARCHAR(255) UNIQUE NOT NULL,
  user_agent TEXT,
  ip INET,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
