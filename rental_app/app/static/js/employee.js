// static/js/employee.js

function parseCsvIds(s) {
  const t = (s || "").trim();
  if (!t) return null;
  const ids = t.split(",").map(x => Number(x.trim())).filter(x => Number.isFinite(x) && x > 0);
  return ids.length ? ids : null;
}

const EmployeeUI = {
  initContracts() {
    const page = document.getElementById("empContractsPage");
    if (!page) return;

    const tbody = document.getElementById("empContractsTbody");
    const msg = document.getElementById("empContractsMsg");

    const btn = document.getElementById("empReload");
    const statusEl = document.getElementById("empStatus");
    const clientEl = document.getElementById("empClientId");
    const fromEl = document.getElementById("empFrom");
    const toEl = document.getElementById("empTo");

    async function load() {
      setMsg(msg, "");
      tbody.innerHTML = `<tr><td colspan="9" class="muted">Загрузка…</td></tr>`;

      const qs = new URLSearchParams();
      const status = (statusEl?.value || "").trim();
      const client_id = (clientEl?.value || "").trim();
      const from_date = (fromEl?.value || "").trim();
      const to_date = (toEl?.value || "").trim();

      if (status) qs.set("status", status);
      if (client_id) qs.set("client_id", client_id);
      if (from_date) qs.set("from_date", from_date);
      if (to_date) qs.set("to_date", to_date);

      try {
        const rows = await apiFetch("/contracts" + (qs.toString() ? `?${qs}` : ""));
        tbody.innerHTML = "";
        if (!rows.length) {
          tbody.innerHTML = `<tr><td colspan="9" class="muted">Пусто</td></tr>`;
          return;
        }
        for (const c of rows) {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${c.contract_id}</td>
            <td>${c.status}</td>
            <td>${c.client_id}</td>
            <td>${c.rental_point_id}</td>
            <td>${c.start_date}</td>
            <td>${c.planned_end_date}</td>
            <td>${c.total_rent_amount}</td>
            <td>${c.total_deposit_amount}</td>
            <td><a class="btn btn--sm btn--ghost" href="/contracts/${c.contract_id}/view">Открыть</a></td>
          `;
          tbody.appendChild(tr);
        }
      } catch (e) {
        setMsg(msg, e.message, "error");
        tbody.innerHTML = `<tr><td colspan="9" class="muted">Ошибка</td></tr>`;
      }
    }

    btn?.addEventListener("click", load);
    load();
  },

  initNewContract() {
    const page = document.getElementById("empNewContractPage");
    if (!page) return;

    const pointId = Number(page.dataset.pointId || 1);

    const msg = document.getElementById("empNewMsg");
    const startEl = document.getElementById("empNewStart");
    const endEl = document.getElementById("empNewEnd");
    const clientIdEl = document.getElementById("empNewClientId");

    if (startEl && !startEl.value) startEl.value = todayISO();
    if (endEl && !endEl.value) endEl.value = addDaysISO(startEl.value || todayISO(), 2);

    const qCategory = document.getElementById("empQCategory");
    const categoryMap = new Map();

    async function loadCategories() {
      if (!qCategory) return;
      qCategory.innerHTML = `<option value="">Все</option>`;
      try {
        const cats = await apiFetch("/catalog/categories");
        for (const c of cats) categoryMap.set(c.category_id, c.name);
        qCategory.innerHTML =
          `<option value="">Все</option>` +
          cats.map((c) => `<option value="${c.category_id}">${c.name}</option>`).join("");
      } catch (_) {}
    }

    function buildQuery() {
      const qs = new URLSearchParams();
      const name = (document.getElementById("empQName")?.value || "").trim();
      const brand = (document.getElementById("empQBrand")?.value || "").trim();
      const category_id = (document.getElementById("empQCategory")?.value || "").trim();
      if (name) qs.set("name", name);
      if (brand) qs.set("brand", brand);
      if (category_id) qs.set("category_id", category_id);
      return qs;
    }

    function row(p) {
      const tr = document.createElement("tr");
      tr.dataset.productId = String(p.product_id);
      tr.dataset.productName = String(p.name || "");
      tr.dataset.productDailyPrice = String(p.default_daily_price ?? "");
      tr.dataset.productDeposit = String(p.default_deposit ?? "");
      tr.innerHTML = `
        <td>${p.product_id}</td>
        <td>
          <div>${p.name}</div>
          <div class="muted small">${p.brand ? p.brand : ""}</div>
        </td>
        <td>${categoryMap.get(p.category_id) || p.category_id}</td>
        <td>${p.default_daily_price}</td>
        <td>${p.default_deposit}</td>
        <td>
          <div class="row-actions">
            <button class="btn btn--sm" data-action="check">Доступность</button>
            <button class="btn btn--sm btn--primary" data-action="draft" disabled>В черновик</button>
          </div>
          <div class="muted small" data-slot="avail"></div>
        </td>
      `;
      return tr;
    }

    function renderAvailability(slotEl, tr, ids, availableCount) {
      slotEl.innerHTML = "";
      const top = document.createElement("div");
      top.textContent = `Доступно: ${availableCount}`;
      slotEl.appendChild(top);

      if (!ids.length) return;

      const wrap = document.createElement("div");
      wrap.className = "row-actions";

      const label = document.createElement("span");
      label.className = "muted small";
      label.textContent = "item_id:";

      const sel = document.createElement("select");
      sel.className = "select-inline";
      sel.innerHTML = ids.slice(0, 200).map((id) => `<option value="${id}">${id}</option>`).join("");
      tr.dataset.itemId = String(ids[0]);
      sel.addEventListener("change", () => (tr.dataset.itemId = sel.value));

      wrap.appendChild(label);
      wrap.appendChild(sel);
      slotEl.appendChild(wrap);
    }

    async function checkAvailability(productId, slotEl, draftBtn, tr) {
      setMsg(msg, "");
      const start = startEl?.value;
      const end = endEl?.value;
      if (!start || !end) {
        slotEl.textContent = "Укажи даты start/end";
        return;
      }

      slotEl.textContent = "Проверяю…";
      draftBtn.disabled = true;
      tr.dataset.itemId = "";

      try {
        const qs = new URLSearchParams({
          point_id: String(pointId),
          rental_point_id: String(pointId),
          product_id: String(productId),
          start,
          end,
        });

        const a = await apiFetch(`/availability?${qs.toString()}`);
        const ids = a.item_ids || [];
        renderAvailability(slotEl, tr, ids, a.available_count ?? ids.length);

        if (ids.length > 0) draftBtn.disabled = false;
      } catch (e) {
        slotEl.textContent = `Ошибка: ${e.message}`;
      }
    }

    function openDraftEmployee(itemId, tr) {
      setMsg(msg, "");
      const client_id = Number((clientIdEl?.value || "").trim());
      if (!client_id) {
        setMsg(msg, "Укажи client_id.", "error");
        return;
      }

      const start_date = startEl?.value;
      const planned_end_date = endEl?.value;
      if (!start_date || !planned_end_date) {
        setMsg(msg, "Укажи даты.", "error");
        return;
      }

      const draftId = Date.now();
      const draft = {
        draft_id: draftId,
        client_id,
        item_id: Number(itemId),
        product_id: Number(tr?.dataset.productId || 0),
        product_name: tr?.dataset.productName || "",
        daily_price: tr?.dataset.productDailyPrice || "",
        deposit_amount: tr?.dataset.productDeposit || "",
        rental_point_id: pointId,
        start_date,
        planned_end_date,
      };

      try {
        sessionStorage.setItem(`draft_contract_${draftId}`, JSON.stringify(draft));
      } catch (e) {
        setMsg(msg, "Не удалось сохранить черновик.", "error");
        return;
      }

      window.location.href = `/contracts/${draftId}/view?draft=1`;
    }

    async function loadProducts() {
      const tbody = document.getElementById("empProductsTbody");
      if (!tbody) return;

      setMsg(msg, "");
      tbody.innerHTML = `<tr><td colspan="6" class="muted">Загрузка…</td></tr>`;

      const qs = buildQuery();
      try {
        const data = await apiFetch("/catalog/products" + (qs.toString() ? `?${qs}` : ""));
        tbody.innerHTML = "";
        if (!data.length) {
          tbody.innerHTML = `<tr><td colspan="6" class="muted">Ничего не найдено</td></tr>`;
          return;
        }
        for (const p of data) tbody.appendChild(row(p));
      } catch (e) {
        setMsg(msg, e.message, "error");
        tbody.innerHTML = `<tr><td colspan="6" class="muted">Ошибка</td></tr>`;
      }
    }

    document.getElementById("empSearchProducts")?.addEventListener("click", loadProducts);

    document.getElementById("empProductsTbody")?.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const tr = e.target.closest("tr");
      const productId = Number(tr?.dataset.productId);
      const slotEl = tr.querySelector('[data-slot="avail"]');
      const draftBtn = tr.querySelector('button[data-action="draft"]');

      if (btn.dataset.action === "check") {
        await checkAvailability(productId, slotEl, draftBtn, tr);
      }
      if (btn.dataset.action === "draft") {
        const itemId = tr.dataset.itemId;
        if (!itemId) {
          slotEl.textContent = "Сначала нажми “Доступность”";
          return;
        }
        openDraftEmployee(itemId, tr);
      }
    });

    (async () => {
      await loadCategories();
      await loadProducts();
    })();
  },

  initContractOps() {
    const root = document.getElementById("contractView");
    if (!root) return;

    const contractId = Number(root.dataset.contractId);

    // Extend apply
    document.getElementById("empExtendApplyBtn")?.addEventListener("click", async () => {
      const msg = document.getElementById("empExtendMsg");
      setMsg(msg, "");
      try {
        const new_planned_end_date = document.getElementById("empExtendDate")?.value;
        const method = document.getElementById("empExtendMethod")?.value || "cash";
        await apiFetch(`/contracts/${contractId}/extend`, {
          method: "POST",
          body: { new_planned_end_date, approve: true, method },
        });
        setMsg(msg, "Продление применено.", "ok");
        window.location.reload();
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });

    // Change item apply
    document.getElementById("empChangeApplyBtn")?.addEventListener("click", async () => {
      const msg = document.getElementById("empChangeApplyMsg");
      setMsg(msg, "");
      try {
        const old_item_id = Number(document.getElementById("empChangeOldItem")?.value || 0);
        const new_item_id = Number(document.getElementById("empChangeNewItem")?.value || 0);
        const method = document.getElementById("empChangeMethod")?.value || "cash";
        await apiFetch(`/contracts/${contractId}/change-item`, {
          method: "POST",
          body: { old_item_id, new_item_id, method },
        });
        setMsg(msg, "Замена выполнена.", "ok");
        window.location.reload();
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });

    // Return
    document.getElementById("empReturnBtn")?.addEventListener("click", async () => {
      const msg = document.getElementById("empReturnMsg");
      setMsg(msg, "");
      try {
        const items = parseCsvIds(document.getElementById("empReturnItems")?.value);
        const penalty = Number(document.getElementById("empReturnPenalty")?.value || 0);
        const method = document.getElementById("empReturnMethod")?.value || "cash";

        let damage = null;
        const dmgRaw = (document.getElementById("empReturnDamage")?.value || "").trim();
        if (dmgRaw) damage = JSON.parse(dmgRaw);

        const body = {
          items,
          damage,
          penalties: penalty > 0 ? [{ amount: penalty, reason: "manual" }] : null,
          method,
        };

        await apiFetch(`/contracts/${contractId}/return`, { method: "POST", body });
        setMsg(msg, "Возврат обработан.", "ok");
        window.location.reload();
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });

    // Mark overdue
    document.getElementById("empMarkOverdueBtn")?.addEventListener("click", async () => {
      const msg = document.getElementById("empOverdueMsg");
      setMsg(msg, "");
      try {
        const r = await apiFetch(`/contracts/${contractId}/mark-overdue`, { method: "POST" });
        setMsg(msg, `ok=${r.ok}, penalty_amount=${r.penalty_amount}`, "ok");
        window.location.reload();
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });

    // Close as lost
    document.getElementById("empCloseLostBtn")?.addEventListener("click", async () => {
      const msg = document.getElementById("empLostMsg");
      setMsg(msg, "");
      try {
        const items = parseCsvIds(document.getElementById("empLostItems")?.value);
        const penalty_amount = Number(document.getElementById("empLostPenalty")?.value || 0);
        const method = document.getElementById("empLostMethod")?.value || "cash";

        const body = {
          items,
          penalty_amount: penalty_amount > 0 ? penalty_amount : null,
          method,
        };

        await apiFetch(`/contracts/${contractId}/close-as-lost`, { method: "POST", body });
        setMsg(msg, "Закрыто как утеря.", "ok");
        window.location.reload();
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });
  },
};

document.addEventListener("DOMContentLoaded", () => {
  EmployeeUI.initContracts();
  EmployeeUI.initNewContract();
  EmployeeUI.initContractOps();
});
