// app/static/js/demo_concurrency.js
(function () {
  function byId(id) {
    return document.getElementById(id);
  }

  function num(v, fallback = 0) {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  }

  function initDemoConcurrency() {
    const page = byId("demoConcurrencyPage");
    if (!page) return;

    const msg = byId("demoMsg");
    const pointEl = byId("demoPointId");
    const productEl = byId("demoProductId");
    const itemEl = byId("demoItemId");
    const startEl = byId("demoStart");
    const endEl = byId("demoEnd");
    const delayEl = byId("demoDelay");

    const availBox = byId("demoAvailBox");
    const balanceBox = byId("demoBalanceBox");
    const lastBox = byId("demoLastResult");

    const btnFetchAvail = byId("demoFetchAvailBtn");
    const btnNoLock = byId("demoNoLockBtn");
    const btnWithLock = byId("demoWithLockBtn");
    const btnRefresh = byId("demoRefreshBtn");
    const btnReset = byId("demoResetBtn");

    if (startEl && !startEl.value) startEl.value = todayISO();
    if (endEl && !endEl.value) endEl.value = addDaysISO(startEl.value || todayISO(), 2);

    async function fetchAvailability() {
      setMsg(msg, "");
      availBox.textContent = "";

      const point_id = num(pointEl?.value || 1, 1);
      const product_id = num(productEl?.value || 0, 0);
      const start = startEl?.value || "";
      const end = endEl?.value || "";

      if (!product_id) {
        setMsg(msg, "Укажи product_id.", "error");
        return;
      }
      if (!start || !end) {
        setMsg(msg, "Укажи даты start/end.", "error");
        return;
      }

      try {
        const qs = new URLSearchParams({
          point_id: String(point_id),
          rental_point_id: String(point_id),
          product_id: String(product_id),
          start,
          end,
        });
        const a = await apiFetch(`/availability?${qs.toString()}`);
        const ids = a.item_ids || [];
        availBox.textContent = JSON.stringify(a, null, 2);
        if (ids.length > 0) {
          itemEl.value = String(ids[0]);
          setMsg(msg, `Найдено item_id: ${ids.length}. Выбран item_id=${ids[0]}`, "ok");
        } else {
          setMsg(msg, "Свободных item_id не найдено на этот период.", "error");
        }
      } catch (e) {
        setMsg(msg, `Ошибка: ${e.message}`, "error");
        availBox.textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
      } finally {
        await refreshBalance();
      }
    }

    async function refreshBalance() {
      balanceBox.textContent = "";

      const item_id = num(itemEl?.value || 0, 0);
      const start = startEl?.value || "";
      const end = endEl?.value || "";
      if (!item_id || !start || !end) {
        balanceBox.textContent = "Укажи item_id и даты start/end.";
        return;
      }

      try {
        const qs = new URLSearchParams({ item_id: String(item_id), start, end });
        const data = await apiFetch(`/demo/concurrency/item-balance?${qs.toString()}`);
        balanceBox.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        balanceBox.textContent = `Ошибка: ${e.message}`;
      }
    }

    async function createContract(mode) {
      setMsg(msg, "");
      lastBox.textContent = "";

      const rental_point_id = num(pointEl?.value || 1, 1);
      const item_id = num(itemEl?.value || 0, 0);
      const start_date = startEl?.value || "";
      const planned_end_date = endEl?.value || "";
      const delay_ms = num(delayEl?.value || 0, 0);

      if (!item_id) {
        setMsg(msg, "Укажи item_id (или нажми «Получить доступные item_id»).", "error");
        return;
      }
      if (!start_date || !planned_end_date) {
        setMsg(msg, "Укажи start/end.", "error");
        return;
      }

      const body = {
        rental_point_id,
        start_date,
        planned_end_date,
        items: [{ item_id }],
      };

      const path =
        mode === "no-lock" ? "/demo/concurrency/contracts/no-lock" : "/demo/concurrency/contracts/with-lock";
      const url = `${path}?delay_ms=${encodeURIComponent(String(delay_ms))}`;

      try {
        const res = await apiFetch(url, { method: "POST", body });
        setMsg(msg, `OK: создан contract_id=${res.contract_id}`, "ok");
        lastBox.textContent = JSON.stringify(res, null, 2);
      } catch (e) {
        setMsg(msg, `Ошибка: ${e.message}`, "error");
        lastBox.textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
      } finally {
        await refreshBalance();
      }
    }

    async function resetMyDrafts() {
      setMsg(msg, "");
      lastBox.textContent = "";

      const item_id = num(itemEl?.value || 0, 0);
      const start = startEl?.value || "";
      const end = endEl?.value || "";
      if (!item_id || !start || !end) {
        setMsg(msg, "Нужно указать item_id, start, end.", "error");
        return;
      }

      try {
        const qs = new URLSearchParams({ item_id: String(item_id), start, end });
        const res = await apiFetch(`/demo/concurrency/reset-my-drafts?${qs.toString()}`, { method: "POST" });
        setMsg(msg, "Сброс выполнен.", "ok");
        lastBox.textContent = JSON.stringify(res, null, 2);
      } catch (e) {
        setMsg(msg, `Ошибка: ${e.message}`, "error");
        lastBox.textContent = JSON.stringify(e.data || { error: e.message }, null, 2);
      } finally {
        await refreshBalance();
      }
    }

    btnFetchAvail?.addEventListener("click", fetchAvailability);
    btnNoLock?.addEventListener("click", () => createContract("no-lock"));
    btnWithLock?.addEventListener("click", () => createContract("with-lock"));
    btnRefresh?.addEventListener("click", refreshBalance);
    btnReset?.addEventListener("click", resetMyDrafts);

    itemEl?.addEventListener("change", refreshBalance);
    startEl?.addEventListener("change", refreshBalance);
    endEl?.addEventListener("change", refreshBalance);

    refreshBalance();
  }

  document.addEventListener("DOMContentLoaded", initDemoConcurrency);
})();
