// app/static/js/app.js

async function apiFetch(url, options = {}) {
  const opts = { credentials: "include", ...options };

  if (opts.body !== undefined && opts.body !== null && !(opts.body instanceof FormData)) {
    // поддержка body как объекта (само JSON.stringify)
    if (typeof opts.body === "object") {
      opts.body = JSON.stringify(opts.body);
    }
    opts.headers = { ...(opts.headers || {}), "Content-Type": "application/json" };
  }

  const res = await fetch(url, opts);
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json")
    ? await res.json().catch(() => null)
    : await res.text().catch(() => null);

  if (!res.ok) {
    const msg =
      data && data.detail ? data.detail : typeof data === "string" ? data : `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function setMsg(el, text, kind = "") {
  if (!el) return;
  el.textContent = text || "";
  el.className = "msg " + (kind ? `msg--${kind}` : "");
}

function todayISO() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}
function addDaysISO(iso, days) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function initLogout() {
  const link = document.getElementById("logoutLink");
  if (!link) return;
  link.addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/";
    }
  });
}

function initDashboard() {
  const meBox = document.getElementById("meBox");
  if (!meBox) return;
  apiFetch("/auth/me")
    .then((me) => {
      if (me.kind === "client") {
        meBox.textContent = `Вы: ${me.email || ""} ${me.first_name || ""} ${me.last_name || ""}`.trim();
      } else {
        meBox.textContent = `Сотрудник: ${me.login} (${me.role})`;
      }
    })
    .catch(() => {
      meBox.textContent = "Не удалось загрузить профиль.";
    });
}

/* ---------------- AUTH ---------------- */
/**
 * Поддерживает ОБА шаблона логина:
 * - login.html (select #loginKind, input #clientEmail)
 * - auth_login.html (табы #tabClient/#tabEmployee, input #loginEmail)
 * Бэкенд не трогаем.
 */
function initLogin() {
  const btn = document.getElementById("loginBtn");
  if (!btn) return;

  const msg = document.getElementById("loginMsg");

  const kindSelect = document.getElementById("loginKind"); // login.html
  const tabClient = document.getElementById("tabClient"); // auth_login.html
  const tabEmployee = document.getElementById("tabEmployee");

  const clientFields = document.getElementById("clientFields");
  const employeeFields = document.getElementById("employeeFields");

  let mode = "client";

  function applyMode(m) {
    mode = m === "employee" ? "employee" : "client";

    if (clientFields) clientFields.style.display = mode === "client" ? "" : "none";
    if (employeeFields) employeeFields.style.display = mode === "employee" ? "" : "none";

    if (tabClient) tabClient.classList.toggle("is-active", mode === "client");
    if (tabEmployee) tabEmployee.classList.toggle("is-active", mode === "employee");

    setMsg(msg, "");
  }

  if (kindSelect) {
    kindSelect.addEventListener("change", () => applyMode(kindSelect.value));
    applyMode(kindSelect.value || "client");
  } else if (tabClient || tabEmployee) {
    tabClient?.addEventListener("click", () => applyMode("client"));
    tabEmployee?.addEventListener("click", () => applyMode("employee"));
    applyMode("client");
  } else {
    applyMode("client");
  }

  btn.addEventListener("click", async () => {
    setMsg(msg, "");
    try {
      const remember = !!document.getElementById("loginRemember")?.checked;
      const password = (document.getElementById("loginPassword")?.value || "").trim();
      if (!password) throw new Error("Введите пароль.");

      if (mode === "client") {
        const email = (
          document.getElementById("loginEmail")?.value ||
          document.getElementById("clientEmail")?.value ||
          ""
        ).trim();
        if (!email) throw new Error("Введите email.");
        await apiFetch("/auth/client/login", {
          method: "POST",
          body: { email, password, remember },
        });
      } else {
        const login = (document.getElementById("employeeLogin")?.value || "").trim();
        if (!login) throw new Error("Введите логин сотрудника.");
        await apiFetch("/auth/employee/login", {
          method: "POST",
          body: { login, password, remember },
        });
      }

      window.location.href = "/dashboard";
    } catch (e) {
      setMsg(msg, e.message, "error");
    }
  });
}

function initRegister() {
  const btn = document.getElementById("registerBtn");
  if (!btn) return;

  const msg = document.getElementById("registerMsg");

  btn.addEventListener("click", async () => {
    setMsg(msg, "");
    try {
      const payload = {
        email: document.getElementById("regEmail")?.value || "",
        password: document.getElementById("regPassword")?.value || "",
        phone: document.getElementById("regPhone")?.value || null,
        first_name: document.getElementById("regFirstName")?.value || null,
        last_name: document.getElementById("regLastName")?.value || null,
        remember: !!document.getElementById("regRemember")?.checked,
      };

      await apiFetch("/auth/client/register", {
        method: "POST",
        body: payload,
      });

      window.location.href = "/dashboard";
    } catch (e) {
      setMsg(msg, e.message, "error");
    }
  });
}

/* ---------------- CATALOG ---------------- */

function specsLine(p) {
  const parts = [];
  if (p.volume_liters != null) parts.push(`объём: ${p.volume_liters}л`);
  if (p.people_count != null) parts.push(`людей: ${p.people_count}`);
  if (p.temperature_min != null) parts.push(`tmin: ${p.temperature_min}°C`);
  if (p.weight_grams != null) parts.push(`вес: ${p.weight_grams}г`);
  if (p.size_label) parts.push(`размер: ${p.size_label}`);
  return parts.join(" • ");
}

function shortDesc(s, n = 80) {
  if (!s) return "";
  const t = String(s).trim();
  if (t.length <= n) return t;
  return t.slice(0, n - 1) + "…";
}

function productRow(p, categoryName) {
  const tr = document.createElement("tr");
  tr.dataset.productId = String(p.product_id);

  const secondLine = [
    p.brand ? `бренд: ${p.brand}` : null,
    p.description ? shortDesc(p.description) : null,
  ].filter(Boolean).join(" • ");

  tr.innerHTML = `
    <td>${p.product_id}</td>
    <td>
      <div>${p.name}</div>
      <div class="muted small">${secondLine || ""}</div>
    </td>
    <td>${categoryName || p.category_id}</td>
    <td>${p.default_daily_price}</td>
    <td>${p.default_deposit}</td>
    <td class="muted small">${specsLine(p) || ""}</td>
    <td>
      <div class="row-actions">
        <button class="btn btn--sm" data-action="check">Доступность</button>
        <button class="btn btn--sm btn--primary" data-action="contract" disabled>Создать договор</button>
      </div>
      <div class="muted small" data-slot="avail"></div>
    </td>
  `;
  return tr;
}

function initCatalog() {
  const tbody = document.getElementById("productsTbody");
  if (!tbody) return;

  const msg = document.getElementById("catalogMsg");

  const startEl = document.getElementById("startDate");
  const endEl = document.getElementById("endDate");
  if (startEl && !startEl.value) startEl.value = todayISO();
  if (endEl && !endEl.value) endEl.value = addDaysISO(startEl.value || todayISO(), 2);

  const qCategory = document.getElementById("qCategory");
  const categoryMap = new Map();

  async function loadCategories() {
    if (!qCategory) return;
    qCategory.innerHTML = `<option value="">Все категории</option>`;
    try {
      const cats = await apiFetch("/catalog/categories");
      for (const c of cats) categoryMap.set(c.category_id, c.name);
      qCategory.innerHTML =
        `<option value="">Все категории</option>` +
        cats.map((c) => `<option value="${c.category_id}">${c.name}</option>`).join("");
    } catch (e) {
      // не ломаем каталог, просто оставляем без категорий
    }
  }

  function buildQuery() {
    const qs = new URLSearchParams();

    const name = (document.getElementById("qName")?.value || "").trim();
    const brand = (document.getElementById("qBrand")?.value || "").trim();
    const category_id = (document.getElementById("qCategory")?.value || "").trim();

    const price_max = (document.getElementById("qPriceMax")?.value || "").trim();
    const volume_liters_gte = (document.getElementById("qVolume")?.value || "").trim();
    const people_count = (document.getElementById("qPeople")?.value || "").trim();
    const temperature_min_lte = (document.getElementById("qTemp")?.value || "").trim();

    if (name) qs.set("name", name);
    if (brand) qs.set("brand", brand);
    if (category_id) qs.set("category_id", category_id);

    if (price_max) qs.set("price_max", price_max);
    if (volume_liters_gte) qs.set("volume_liters_gte", volume_liters_gte);
    if (people_count) qs.set("people_count", people_count);
    if (temperature_min_lte) qs.set("temperature_min_lte", temperature_min_lte);

    return qs;
  }

  async function loadProducts() {
    setMsg(msg, "");
    tbody.innerHTML = `<tr><td colspan="7" class="muted">Загрузка…</td></tr>`;

    const qs = buildQuery();

    try {
      const data = await apiFetch("/catalog/products" + (qs.toString() ? `?${qs}` : ""));
      tbody.innerHTML = "";
      if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="muted">Ничего не найдено</td></tr>`;
        return;
      }
      for (const p of data) {
        const catName = categoryMap.get(p.category_id) || "";
        tbody.appendChild(productRow(p, catName));
      }
    } catch (e) {
      setMsg(msg, e.message, "error");
      tbody.innerHTML = `<tr><td colspan="7" class="muted">Ошибка</td></tr>`;
    }
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

  async function checkAvailability(productId, slotEl, contractBtn, tr) {
    setMsg(msg, "");

    const pointId = Number(document.getElementById("pointId")?.value || 1);
    const start = document.getElementById("startDate")?.value;
    const end = document.getElementById("endDate")?.value;

    if (!start || !end) {
      slotEl.textContent = "Укажи даты start/end";
      return;
    }

    slotEl.textContent = "Проверяю…";
    contractBtn.disabled = true;
    tr.dataset.itemId = "";

    try {
      // Для совместимости: отправляем и point_id и rental_point_id
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

      if (ids.length > 0) contractBtn.disabled = false;
    } catch (e) {
      slotEl.textContent = `Ошибка: ${e.message}`;
    }
  }

  async function createContract(itemId) {
    setMsg(msg, "");
    const pointId = Number(document.getElementById("pointId")?.value || 1);
    const start_date = document.getElementById("startDate")?.value;
    const planned_end_date = document.getElementById("endDate")?.value;

    try {
      const contract = await apiFetch("/contracts", {
        method: "POST",
        body: {
          rental_point_id: pointId,
          start_date,
          planned_end_date,
          items: [{ item_id: Number(itemId) }],
        },
      });
      window.location.href = `/contracts/${contract.contract_id}/view`;
    } catch (e) {
      if (e.status === 401) {
        window.location.href = "/login";
        return;
      }
      setMsg(msg, e.message, "error");
    }
  }

  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;

    const tr = e.target.closest("tr");
    const productId = Number(tr?.dataset.productId);
    const action = btn.dataset.action;

    const slotEl = tr.querySelector('[data-slot="avail"]');
    const contractBtn = tr.querySelector('button[data-action="contract"]');

    if (action === "check") {
      await checkAvailability(productId, slotEl, contractBtn, tr);
    }

    if (action === "contract") {
      const itemId = tr.dataset.itemId;
      if (!itemId) {
        slotEl.textContent = "Сначала нажми “Доступность”";
        return;
      }
      await createContract(itemId);
    }
  });

  const reloadBtn = document.getElementById("reloadProducts");
  reloadBtn?.addEventListener("click", loadProducts);

  document.getElementById("resetProducts")?.addEventListener("click", () => {
    const ids = ["qName","qBrand","qCategory","qPriceMax","qVolume","qPeople","qTemp"];
    for (const id of ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      el.value = "";
    }
    loadProducts();
  });

  // Enter в любом поле фильтра — выполнить поиск
  document.querySelectorAll(".filters input, .filters select").forEach((el) => {
    el.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") loadProducts();
    });
    if (el.tagName === "SELECT") {
      el.addEventListener("change", () => {
        // удобно: категория/параметры сразу обновляют список
        if (el.id === "qCategory") loadProducts();
      });
    }
  });

  (async () => {
    await loadCategories();
    await loadProducts();
  })();
}

/* ---------------- MY CONTRACTS ---------------- */

function initMyContracts() {
  const tbody = document.getElementById("myContractsTbody");
  if (!tbody) return;

  const msg = document.getElementById("contractsMsg");

  async function load() {
    setMsg(msg, "");
    tbody.innerHTML = `<tr><td colspan="7" class="muted">Загрузка…</td></tr>`;
    try {
      const rows = await apiFetch("/contracts/my");
      tbody.innerHTML = "";

      if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="muted">Пока нет договоров</td></tr>`;
        return;
      }

      for (const c of rows) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${c.contract_id}</td>
          <td>${c.status}</td>
          <td>${c.rental_point_id}</td>
          <td>${c.start_date}</td>
          <td>${c.planned_end_date}</td>
          <td>${c.actual_end_date ?? ""}</td>
          <td><a class="btn btn--sm btn--ghost" href="/contracts/${c.contract_id}/view">Открыть</a></td>
        `;
        tbody.appendChild(tr);
      }
    } catch (e) {
      setMsg(msg, e.message, "error");
      tbody.innerHTML = `<tr><td colspan="7" class="muted">Ошибка</td></tr>`;
    }
  }

  load();
}

/* ---------------- CONTRACT VIEW ---------------- */

function initContractView() {
  const root = document.getElementById("contractView");
  if (!root) return;

  const contractId = Number(root.dataset.contractId);
  const header = document.getElementById("contractHeader");
  const itemsTbody = document.getElementById("itemsTbody");
  const paymentsTbody = document.getElementById("paymentsTbody");
  const contractMsg = document.getElementById("contractMsg");
  const extendMsg = document.getElementById("extendMsg");
  const changeMsg = document.getElementById("changeMsg");

  async function loadContract() {
    const c = await apiFetch(`/contracts/${contractId}`);
    header.textContent = `Статус: ${c.status} | Пункт: ${c.rental_point_id} | ${c.start_date} → ${c.planned_end_date} | rent_total: ${c.total_rent_amount} | deposit_total: ${c.total_deposit_amount}`;
    return c;
  }

  async function loadItems(c) {
    itemsTbody.innerHTML = "";
    const items = c.items || [];
    if (!items.length) {
      itemsTbody.innerHTML = `<tr><td colspan="4" class="muted">Нет позиций</td></tr>`;
      return;
    }
    for (const it of items) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${it.item_id}</td>
        <td>${it.product_id}</td>
        <td>${it.daily_price}</td>
        <td>${it.deposit_amount}</td>
      `;
      itemsTbody.appendChild(tr);
    }
  }

  async function loadPayments() {
    const pays = await apiFetch(`/contracts/${contractId}/payments`);
    paymentsTbody.innerHTML = "";
    if (!pays.length) {
      paymentsTbody.innerHTML = `<tr><td colspan="5" class="muted">Платежей нет</td></tr>`;
      return;
    }
    for (const p of pays) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${p.payment_id}</td>
        <td>${p.payment_date}</td>
        <td>${p.type}</td>
        <td>${p.method ?? ""}</td>
        <td>${p.amount}</td>
      `;
      paymentsTbody.appendChild(tr);
    }
  }

  async function refreshAll() {
    setMsg(contractMsg, "");
    try {
      const c = await loadContract();
      await loadItems(c);
      await loadPayments();
    } catch (e) {
      setMsg(contractMsg, e.message, "error");
    }
  }

  document.getElementById("payBtn")?.addEventListener("click", async () => {
    setMsg(contractMsg, "");
    try {
      const amount = Number(document.getElementById("payAmount")?.value || 0);
      const type = document.getElementById("payType")?.value;
      const method = document.getElementById("payMethod")?.value;

      await apiFetch(`/contracts/${contractId}/payments`, {
        method: "POST",
        body: { amount, type, method },
      });

      setMsg(contractMsg, "Оплата добавлена.", "ok");
      await refreshAll();
    } catch (e) {
      setMsg(contractMsg, e.message, "error");
    }
  });

  document.getElementById("extendReqBtn")?.addEventListener("click", async () => {
    setMsg(extendMsg, "");
    try {
      const new_planned_end_date = document.getElementById("extendDate")?.value;
      const r = await apiFetch(`/contracts/${contractId}/extend-request`, {
        method: "POST",
        body: { new_planned_end_date },
      });
      setMsg(
        extendMsg,
        `ok=${r.ok}, extra_rent=${r.extra_rent}${r.reasons?.length ? " | " + r.reasons.join("; ") : ""}`,
        r.ok ? "ok" : "warn"
      );
    } catch (e) {
      setMsg(extendMsg, e.message, "error");
    }
  });

  document.getElementById("changeReqBtn")?.addEventListener("click", async () => {
    setMsg(changeMsg, "");
    try {
      const old_item_id = Number(document.getElementById("changeOldItem")?.value || 0);
      const new_product_id = Number(document.getElementById("changeNewProduct")?.value || 0);

      const r = await apiFetch(`/contracts/${contractId}/change-item-request`, {
        method: "POST",
        body: { old_item_id, new_product_id },
      });

      setMsg(changeMsg, JSON.stringify(r), "ok");
    } catch (e) {
      setMsg(changeMsg, e.message, "error");
    }
  });

  document.getElementById("cancelBtn")?.addEventListener("click", async () => {
    setMsg(contractMsg, "");
    try {
      await apiFetch(`/contracts/${contractId}/cancel`, { method: "POST" });
      setMsg(contractMsg, "Договор отменён.", "ok");
      await refreshAll();
    } catch (e) {
      setMsg(contractMsg, e.message, "error");
    }
  });

  refreshAll();
}

/* ---------------- BOOT ---------------- */

document.addEventListener("DOMContentLoaded", () => {
  initLogout();
  initLogin();
  initRegister();
  initCatalog();
  initMyContracts();
  initContractView();
  initDashboard();
});
