-- scripts/seed.sql
-- Minimal seed to be able to login as employees.
-- Passwords (bcrypt):
--   admin/admin123
--   manager/manager123
--   cashier/cashier123


BEGIN;

-- 1) rental_points: гарантируем пункт 1
INSERT INTO rental_points (rental_point_id, name, address, phone)
SELECT 1, 'Main Point', 'Somewhere 1', '+000000000'
WHERE NOT EXISTS (
  SELECT 1 FROM rental_points WHERE rental_point_id = 1
);

-- 2) employees: три пользователя для входа
-- пароли:
--   admin    / admin123
--   manager  / manager123
--   cashier  / cashier123
-- bcrypt хэши заранее рассчитаны
INSERT INTO employees (login, password_hash, first_name, last_name, role, rental_point_id, is_active)
SELECT 'admin',
       '$2b$12$c50TBtAFnCoGbkcr5qcQv.Xk28bNxxd9tqIKpi369BVKwcbk1agei',
       'Admin', 'User', 'admin', 1, TRUE
WHERE NOT EXISTS (SELECT 1 FROM employees WHERE login = 'admin');

INSERT INTO employees (login, password_hash, first_name, last_name, role, rental_point_id, is_active)
SELECT 'manager',
       '$2b$12$t5FimX6aT2WYwFOmDKWtye6hHJm/uXk98N3/OWLTT20vuJzhwT83O',
       'Manager', 'User', 'manager', 1, TRUE
WHERE NOT EXISTS (SELECT 1 FROM employees WHERE login = 'manager');

INSERT INTO employees (login, password_hash, first_name, last_name, role, rental_point_id, is_active)
SELECT 'cashier',
       '$2b$12$KcFLdyDBKeNQK.hVwlpwG.hYnAI0RMB0Sm8bK7lruzacT1xTzoHSO',
       'Cashier', 'User', 'cashier', 1, TRUE
WHERE NOT EXISTS (SELECT 1 FROM employees WHERE login = 'cashier');

COMMIT;
