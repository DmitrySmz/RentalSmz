
CREATE OR REPLACE FUNCTION trg_check_item_point_match()
RETURNS TRIGGER AS $$
DECLARE
  v_contract_point INT;
  v_item_point INT;
BEGIN
  SELECT rental_point_id INTO v_contract_point FROM rental_contracts WHERE contract_id = NEW.contract_id;
  SELECT rental_point_id INTO v_item_point     FROM items             WHERE item_id     = NEW.item_id;

  IF v_contract_point IS NULL OR v_item_point IS NULL OR v_contract_point <> v_item_point THEN
    RAISE EXCEPTION 'Item and contract must belong to the same rental point';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS contract_items_check_point ON contract_items;
CREATE TRIGGER contract_items_check_point
BEFORE INSERT OR UPDATE ON contract_items
FOR EACH ROW EXECUTE FUNCTION trg_check_item_point_match();


CREATE OR REPLACE FUNCTION trg_prevent_item_overlap()
RETURNS TRIGGER AS $$
DECLARE
  v_start DATE; v_end DATE; v_status contract_status_enum;
  v_cnt INT;
BEGIN
  SELECT start_date, COALESCE(actual_end_date, planned_end_date), status
    INTO v_start, v_end, v_status
  FROM rental_contracts WHERE contract_id = NEW.contract_id;


  IF v_status IN ('active','overdue') THEN
    SELECT COUNT(*) INTO v_cnt
    FROM contract_items ci
    JOIN rental_contracts rc ON rc.contract_id = ci.contract_id
    WHERE ci.item_id = NEW.item_id
      AND rc.contract_id <> NEW.contract_id
      AND rc.status IN ('active','overdue')
      AND NOT (rc.planned_end_date < v_start OR rc.start_date > v_end);

    IF v_cnt > 0 THEN
      RAISE EXCEPTION 'Item % already busy in another active/overdue contract overlapping in time', NEW.item_id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS contract_items_prevent_overlap ON contract_items;
CREATE TRIGGER contract_items_prevent_overlap
BEFORE INSERT OR UPDATE ON contract_items
FOR EACH ROW EXECUTE FUNCTION trg_prevent_item_overlap();


CREATE OR REPLACE FUNCTION recalc_item_availability(p_item_id INT)
RETURNS VOID AS $$
DECLARE
  busy BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM contract_items ci
    JOIN rental_contracts rc ON rc.contract_id = ci.contract_id
    WHERE ci.item_id = p_item_id
      AND rc.status IN ('active','overdue')
  ) INTO busy;

  UPDATE items
     SET is_available = NOT busy
   WHERE item_id = p_item_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_recalc_item_after_ci()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM recalc_item_availability(NEW.item_id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_recalc_item_after_ci_delete()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM recalc_item_availability(OLD.item_id);
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS contract_items_after_change ON contract_items;
CREATE TRIGGER contract_items_after_change
AFTER INSERT OR UPDATE ON contract_items
FOR EACH ROW EXECUTE FUNCTION trg_recalc_item_after_ci();

DROP TRIGGER IF EXISTS contract_items_after_delete ON contract_items;
CREATE TRIGGER contract_items_after_delete
AFTER DELETE ON contract_items
FOR EACH ROW EXECUTE FUNCTION trg_recalc_item_after_ci_delete();


-- Изменения статуса/дат договора должны тоже пересчитывать доступность всех его предметов
CREATE OR REPLACE FUNCTION trg_recalc_items_after_contract_update()
RETURNS TRIGGER AS $$
BEGIN
  -- если статус/даты поменялись
  IF (OLD.status IS DISTINCT FROM NEW.status)
     OR (OLD.start_date IS DISTINCT FROM NEW.start_date)
     OR (OLD.planned_end_date IS DISTINCT FROM NEW.planned_end_date)
     OR (OLD.actual_end_date IS DISTINCT FROM NEW.actual_end_date)
  THEN
    PERFORM recalc_item_availability(ci.item_id)
    FROM contract_items ci
    WHERE ci.contract_id = NEW.contract_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rental_contracts_after_update ON rental_contracts;
CREATE TRIGGER rental_contracts_after_update
AFTER UPDATE ON rental_contracts
FOR EACH ROW EXECUTE FUNCTION trg_recalc_items_after_contract_update();
