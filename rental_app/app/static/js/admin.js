// static/js/admin.js

const AdminUI = {
  async loadCategoriesIntoSelect(selId) {
    const sel = document.getElementById(selId);
    if (!sel) return;
    sel.innerHTML = "";
    const cats = await apiFetch("/admin/categories");
    for (const c of cats) {
      const opt = document.createElement("option");
      opt.value = String(c.category_id);
      opt.textContent = `${c.category_id}: ${c.name}`;
      sel.appendChild(opt);
    }
  },

  initCatalog() {
    const page = document.getElementById("adminCatalogPage");
    if (!page) return;

    // ---- Categories ----
    const catMsg = document.getElementById("admCatMsg");
    const catTbody = document.getElementById("admCatTbody");

    const catId = document.getElementById("admCatId");
    const catName = document.getElementById("admCatName");
    const catDesc = document.getElementById("admCatDesc");

    async function reloadCats() {
      setMsg(catMsg, "");
      catTbody.innerHTML = `<tr><td colspan="4" class="muted">Загрузка…</td></tr>`;
      try {
        const cats = await apiFetch("/admin/categories");
        catTbody.innerHTML = "";
        for (const c of cats) {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${c.category_id}</td>
            <td>${c.name}</td>
            <td class="muted small">${c.description || ""}</td>
            <td class="row-actions">
              <button class="btn btn--sm" data-action="edit" data-id="${c.category_id}">Edit</button>
              <button class="btn btn--sm btn--danger" data-action="del" data-id="${c.category_id}">Del</button>
            </td>
          `;
          catTbody.appendChild(tr);
        }
        await AdminUI.loadCategoriesIntoSelect("admProdCategory");
      } catch (e) {
        setMsg(catMsg, e.message, "error");
      }
    }

    document.getElementById("admCatResetBtn")?.addEventListener("click", () => {
      if (catId) catId.value = "";
      if (catName) catName.value = "";
      if (catDesc) catDesc.value = "";
      setMsg(catMsg, "");
    });

    document.getElementById("admCatSaveBtn")?.addEventListener("click", async () => {
      setMsg(catMsg, "");
      try {
        const payload = { name: (catName?.value || "").trim(), description: (catDesc?.value || "").trim() || null };
        const id = Number((catId?.value || "").trim());
        if (id) {
          await apiFetch(`/admin/categories/${id}`, { method: "PUT", body: payload });
        } else {
          await apiFetch("/admin/categories", { method: "POST", body: payload });
        }
        setMsg(catMsg, "Сохранено.", "ok");
        await reloadCats();
      } catch (e) {
        setMsg(catMsg, e.message, "error");
      }
    });

    catTbody?.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      const id = Number(btn.dataset.id);

      if (action === "edit") {
        const cats = await apiFetch("/admin/categories");
        const c = cats.find(x => x.category_id === id);
        if (!c) return;
        catId.value = String(c.category_id);
        catName.value = c.name;
        catDesc.value = c.description || "";
      }

      if (action === "del") {
        if (!confirm(`Удалить категорию #${id}?`)) return;
        try {
          await apiFetch(`/admin/categories/${id}`, { method: "DELETE" });
          await reloadCats();
        } catch (err) {
          setMsg(catMsg, err.message, "error");
        }
      }
    });

    // ---- Products ----
    const prodMsg = document.getElementById("admProdMsg");
    const prodTbody = document.getElementById("admProdTbody");

    const prodId = document.getElementById("admProdId");
    const prodCategory = document.getElementById("admProdCategory");
    const prodName = document.getElementById("admProdName");
    const prodBrand = document.getElementById("admProdBrand");
    const prodDesc = document.getElementById("admProdDesc");
    const prodVol = document.getElementById("admProdVol");
    const prodPeople = document.getElementById("admProdPeople");
    const prodTemp = document.getElementById("admProdTemp");
    const prodPrice = document.getElementById("admProdPrice");
    const prodDeposit = document.getElementById("admProdDeposit");

    async function reloadProducts() {
      setMsg(prodMsg, "");
      prodTbody.innerHTML = `<tr><td colspan="6" class="muted">Загрузка…</td></tr>`;
      try {
        const rows = await apiFetch("/admin/products");
        prodTbody.innerHTML = "";
        for (const p of rows) {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${p.product_id}</td>
            <td>${p.name}</td>
            <td>${p.category_id}</td>
            <td>${p.default_daily_price}</td>
            <td>${p.default_deposit}</td>
            <td class="row-actions">
              <button class="btn btn--sm" data-action="edit" data-id="${p.product_id}">Edit</button>
              <button class="btn btn--sm btn--danger" data-action="del" data-id="${p.product_id}">Del</button>
            </td>
          `;
          prodTbody.appendChild(tr);
        }
      } catch (e) {
        setMsg(prodMsg, e.message, "error");
      }
    }

    function resetProdForm() {
      prodId.value = "";
      prodName.value = "";
      prodBrand.value = "";
      prodDesc.value = "";
      prodVol.value = "";
      prodPeople.value = "";
      prodTemp.value = "";
      prodPrice.value = "";
      prodDeposit.value = "";
    }

    document.getElementById("admProdResetBtn")?.addEventListener("click", () => {
      resetProdForm();
      setMsg(prodMsg, "");
    });

    document.getElementById("admProdSaveBtn")?.addEventListener("click", async () => {
      setMsg(prodMsg, "");
      try {
        const payload = {
          category_id: Number(prodCategory.value),
          name: (prodName.value || "").trim(),
          brand: (prodBrand.value || "").trim() || null,
          description: (prodDesc.value || "").trim() || null,
          volume_liters: prodVol.value ? Number(prodVol.value) : null,
          people_count: prodPeople.value ? Number(prodPeople.value) : null,
          temperature_min: prodTemp.value ? Number(prodTemp.value) : null,
          default_daily_price: Number(prodPrice.value || 0),
          default_deposit: Number(prodDeposit.value || 0),
        };
        const id = Number((prodId.value || "").trim());
        if (id) {
          await apiFetch(`/admin/products/${id}`, { method: "PUT", body: payload });
        } else {
          await apiFetch("/admin/products", { method: "POST", body: payload });
        }
        setMsg(prodMsg, "Сохранено.", "ok");
        await reloadProducts();
      } catch (e) {
        setMsg(prodMsg, e.message, "error");
      }
    });

    prodTbody?.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const id = Number(btn.dataset.id);

      if (btn.dataset.action === "edit") {
        const rows = await apiFetch("/admin/products");
        const p = rows.find(x => x.product_id === id);
        if (!p) return;

        prodId.value = String(p.product_id);
        prodCategory.value = String(p.category_id);
        prodName.value = p.name || "";
        prodBrand.value = p.brand || "";
        prodDesc.value = p.description || "";
        prodVol.value = p.volume_liters ?? "";
        prodPeople.value = p.people_count ?? "";
        prodTemp.value = p.temperature_min ?? "";
        prodPrice.value = p.default_daily_price ?? "";
        prodDeposit.value = p.default_deposit ?? "";
      }

      if (btn.dataset.action === "del") {
        if (!confirm(`Удалить продукт #${id}?`)) return;
        try {
          await apiFetch(`/admin/products/${id}`, { method: "DELETE" });
          await reloadProducts();
        } catch (err) {
          setMsg(prodMsg, err.message, "error");
        }
      }
    });

    (async () => {
      await reloadCats();
      await reloadProducts();
    })();
  },

  initInventory() {
    const page = document.getElementById("adminInventoryPage");
    if (!page) return;

    const msg = document.getElementById("admInvMsg");
    const tbody = document.getElementById("admInvTbody");

    async function reload() {
      setMsg(msg, "");
      tbody.innerHTML = `<tr><td colspan="7" class="muted">Загрузка…</td></tr>`;

      const point_id = (document.getElementById("admInvPoint")?.value || "").trim();
      const product_id = (document.getElementById("admInvProduct")?.value || "").trim();

      const qs = new URLSearchParams();
      if (point_id) qs.set("point_id", point_id);
      if (product_id) qs.set("product_id", product_id);

      try {
        const rows = await apiFetch("/admin/items" + (qs.toString() ? `?${qs}` : ""));
        tbody.innerHTML = "";
        if (!rows.length) {
          tbody.innerHTML = `<tr><td colspan="7" class="muted">Пусто</td></tr>`;
          return;
        }

        for (const it of rows) {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${it.item_id}</td>
            <td>${it.product_id} <span class="muted small">${it.product_name || ""}</span></td>
            <td>${it.rental_point_id}</td>
            <td>${it.inventory_number}</td>
            <td>${it.condition_status}</td>
            <td>${it.is_available}</td>
            <td class="row-actions">
              <button class="btn btn--sm" data-action="status" data-id="${it.item_id}">Status</button>
              <button class="btn btn--sm" data-action="move" data-id="${it.item_id}">Move</button>
            </td>
          `;
          tbody.appendChild(tr);
        }
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    }

    document.getElementById("admInvReload")?.addEventListener("click", reload);

    document.getElementById("admNewItemBtn")?.addEventListener("click", async () => {
      setMsg(msg, "");
      try {
        const payload = {
          product_id: Number(document.getElementById("admNewItemProd")?.value || 0),
          rental_point_id: Number(document.getElementById("admNewItemPoint")?.value || 0),
          inventory_number: (document.getElementById("admNewItemInv")?.value || "").trim(),
          color: (document.getElementById("admNewItemColor")?.value || "").trim() || null,
          size: (document.getElementById("admNewItemSize")?.value || "").trim() || null,
          condition_status: document.getElementById("admNewItemCond")?.value || "good",
          is_available: (document.getElementById("admNewItemAvail")?.value || "true") === "true",
        };
        await apiFetch("/admin/items", { method: "POST", body: payload });
        setMsg(msg, "Создано.", "ok");
        await reload();
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });

    tbody?.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;

      const item_id = Number(btn.dataset.id);
      const action = btn.dataset.action;

      if (action === "move") {
        const to_point_id = Number(prompt("to_point_id:", "1") || 0);
        if (!to_point_id) return;
        try {
          await apiFetch(`/admin/items/${item_id}/move`, { method: "POST", body: { to_point_id } });
          await reload();
        } catch (err) {
          setMsg(msg, err.message, "error");
        }
      }

      if (action === "status") {
        const condition_status = prompt("condition_status (new/good/worn/broken/lost):", "good");
        if (!condition_status) return;
        const is_available = prompt("is_available (true/false):", "true");
        if (is_available === null) return;
        try {
          await apiFetch(`/admin/items/${item_id}/status`, {
            method: "PUT",
            body: { condition_status, is_available: is_available === "true" },
          });
          await reload();
        } catch (err) {
          setMsg(msg, err.message, "error");
        }
      }
    });

    reload();
  },

  initReports() {
    const page = document.getElementById("adminReportsPage");
    if (!page) return;

    const msg = document.getElementById("admRepMsg");
    const box = document.getElementById("admRepBox");

    const fromEl = document.getElementById("admRepFrom");
    const toEl = document.getElementById("admRepTo");

    if (fromEl && !fromEl.value) fromEl.value = addDaysISO(todayISO(), -30);
    if (toEl && !toEl.value) toEl.value = todayISO();

    document.getElementById("admRepLoad")?.addEventListener("click", async () => {
      setMsg(msg, "");
      box.textContent = "";
      try {
        const point = Number(document.getElementById("admRepPoint")?.value || 1);
        const from = fromEl?.value;
        const to = toEl?.value;

        const qs = new URLSearchParams({ from, to });
        const data = await apiFetch(`/admin/reports/point/${point}?${qs.toString()}`);
        box.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        setMsg(msg, e.message, "error");
      }
    });
  },

  initContractsPage() {
    const mount = document.getElementById("adminContractsMount");
    if (!mount) return;

    mount.innerHTML = `
      <div class="filters">
        <div>
          <label>status</label>
          <select id="admCStatus">
            <option value="">любые</option>
            <option value="draft">draft</option>
            <option value="active">active</option>
            <option value="overdue">overdue</option>
            <option value="closed">closed</option>
            <option value="canceled">canceled</option>
          </select>
        </div>
        <div>
          <label>client_id</label>
          <input id="admCClient" type="number" min="1" />
        </div>
        <div>
          <label>from_date</label>
          <input id="admCFrom" type="date" />
        </div>
        <div>
          <label>to_date</label>
          <input id="admCTo" type="date" />
        </div>
        <div class="filters__actions">
          <button class="btn btn--primary" id="admCReload">Показать</button>
        </div>
      </div>

      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th><th>status</th><th>client</th><th>point</th>
              <th>start</th><th>end</th><th>rent</th><th>deposit</th><th></th>
            </tr>
          </thead>
          <tbody id="admCTbody"><tr><td colspan="9" class="muted">Загрузка…</td></tr></tbody>
        </table>
      </div>
      <div id="admCMsg" class="msg"></div>
    `;

    const tbody = document.getElementById("admCTbody");
    const msg = document.getElementById("admCMsg");

    async function load() {
      setMsg(msg, "");
      tbody.innerHTML = `<tr><td colspan="9" class="muted">Загрузка…</td></tr>`;

      const qs = new URLSearchParams();
      const status = (document.getElementById("admCStatus")?.value || "").trim();
      const client_id = (document.getElementById("admCClient")?.value || "").trim();
      const from_date = (document.getElementById("admCFrom")?.value || "").trim();
      const to_date = (document.getElementById("admCTo")?.value || "").trim();

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

    document.getElementById("admCReload")?.addEventListener("click", load);
    load();
  },
};

document.addEventListener("DOMContentLoaded", () => {
  AdminUI.initCatalog();
  AdminUI.initInventory();
  AdminUI.initReports();
  AdminUI.initContractsPage();
});
