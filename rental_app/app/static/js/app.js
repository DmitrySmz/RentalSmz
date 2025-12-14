async function apiFetch(url, options = {}) {
  const opts = {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "include", // ВАЖНО: чтобы браузер принял/set-cookie sid
    body: options.body ? JSON.stringify(options.body) : undefined,
  };


  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) ? (data.detail || data.message) : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function $(id) { return document.getElementById(id); }

function setMsg(el, text, kind) {
  if (!el) return;
  el.classList.remove("err", "ok");
  if (kind) el.classList.add(kind);
  el.textContent = text || "";
}

async function doLogin() {
  const kind = $("loginKind")?.value || "client";
  const password = $("loginPassword")?.value || "";
  const remember = !!$("loginRemember")?.checked;

  try {
    if (kind === "client") {
      const email = $("clientEmail")?.value || "";
      await apiFetch("/auth/client/login", { method: "POST", body: { email, password, remember } });
    } else {
      const login = $("employeeLogin")?.value || "";
      await apiFetch("/auth/employee/login", { method: "POST", body: { login, password, remember } });
    }
    window.location.href = "/dashboard";
  } catch (e) {
    setMsg($("loginMsg"), e.message, "err");
  }
}

async function doRegister() {
  const body = {
    email: $("regEmail")?.value || "",
    password: $("regPassword")?.value || "",
    phone: $("regPhone")?.value || null,
    first_name: $("regFirstName")?.value || null,
    last_name: $("regLastName")?.value || null,
    remember: !!$("regRemember")?.checked,
  };

  try {
    await apiFetch("/auth/client/register", { method: "POST", body });
    window.location.href = "/dashboard";
  } catch (e) {
    setMsg($("registerMsg"), e.message, "err");
  }
}

function wireLoginKindToggle() {
  const sel = $("loginKind");
  if (!sel) return;

  const clientFields = $("clientFields");
  const employeeFields = $("employeeFields");

  const apply = () => {
    const kind = sel.value;
    if (kind === "client") {
      if (clientFields) clientFields.style.display = "";
      if (employeeFields) employeeFields.style.display = "none";
    } else {
      if (clientFields) clientFields.style.display = "none";
      if (employeeFields) employeeFields.style.display = "";
    }
    setMsg($("loginMsg"), "", null);
  };

  sel.addEventListener("change", apply);
  apply();
}

async function doLogout(e) {
  if (e) e.preventDefault();
  // можно просто перейти на /logout (сервер почистит куки)
  window.location.href = "/logout";
}

document.addEventListener("DOMContentLoaded", () => {
  // login page
  if ($("loginBtn")) {
    wireLoginKindToggle();
    $("loginBtn").addEventListener("click", doLogin);
  }

  // register page
  if ($("registerBtn")) {
    $("registerBtn").addEventListener("click", doRegister);
  }

  // logout
  const lnk = $("logoutLink");
  if (lnk) lnk.addEventListener("click", doLogout);
});

function buildQuery(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) {
    if (v === null || v === undefined) continue;
    if (typeof v === "string" && v.trim() === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function apiGet(path, params) {
  return apiFetch(path + buildQuery(params), { method: "GET" });
}

const CatalogUI = {
  async initCatalog() {
    await this.loadCategories();
    await this.loadProducts();

    const btn = document.getElementById("catSearchBtn");
    btn.addEventListener("click", async () => {
      await this.loadProducts();
    });
  },

  getFilters() {
    return {
      category_id: document.getElementById("catCategory").value || null,
      name: document.getElementById("catName").value || null,
      brand: document.getElementById("catBrand").value || null,
    };
  },

  getAdvancedFilters() {
    return {
      category_id: document.getElementById("catCategory").value || null,
      brand: document.getElementById("catBrand").value || null,
      price_max: document.getElementById("catPriceMax").value || null,
      volume_liters_gte: document.getElementById("catVolGte").value || null,
      people_count: document.getElementById("catPeople").value || null,
      temperature_min_lte: document.getElementById("catTempLte").value || null,
    };
  },

  async loadCategories() {
    const sel = document.getElementById("catCategory");
    const cats = await apiGet("/catalog/categories");
    // cats: [{category_id, name, ...}]
    for (const c of cats) {
      const opt = document.createElement("option");
      opt.value = c.category_id;
      opt.textContent = c.name;
      sel.appendChild(opt);
    }
  },

  async loadProducts() {
    const list = document.getElementById("catList");
    const empty = document.getElementById("catEmpty");
    list.innerHTML = "";
    empty.style.display = "none";

    const adv = this.getAdvancedFilters();
    const usingAdvanced =
      adv.price_max || adv.volume_liters_gte || adv.people_count || adv.temperature_min_lte;

    let products = [];
    try {
      if (usingAdvanced) {
        products = await apiGet("/catalog/search", adv);
      } else {
        products = await apiGet("/catalog/products", this.getFilters());
      }
    } catch (e) {
      toast(e.message);
      return;
    }

    if (!products || products.length === 0) {
      empty.style.display = "";
      return;
    }

    for (const p of products) {
      list.appendChild(this.renderProductCard(p));
    }
  },

  renderProductCard(p) {
    const el = document.createElement("div");
    el.className = "prod";
    el.innerHTML = `
      <h3>${escapeHtml(p.name)}</h3>
      <div class="meta">
        <div><b>Brand:</b> ${escapeHtml(p.brand || "-")}</div>
        <div><b>Volume:</b> ${p.volume_liters ?? "-"}</div>
        <div><b>People:</b> ${p.people_count ?? "-"}</div>
        <div><b>Temp min:</b> ${p.temperature_min ?? "-"}</div>
      </div>
      <div class="price">
        <div><b>Daily:</b> <span class="code">${p.default_daily_price}</span></div>
        <div><b>Deposit:</b> <span class="code">${p.default_deposit}</span></div>
      </div>

      <button class="smallbtn" data-action="check" data-product="${p.product_id}">
        Проверить доступность
      </button>

      <div class="avail" id="avail-${p.product_id}">
        <div class="msg" style="margin:0;">Пока не проверяли</div>
      </div>
    `;

    el.querySelector('[data-action="check"]').addEventListener("click", async () => {
      await this.checkAvailability(p.product_id);
    });

    return el;
  },

  async checkAvailability(productId) {
    const pointId = document.getElementById("avPointId").value;
    const start = document.getElementById("avStart").value;
    const end = document.getElementById("avEnd").value;

    const box = document.getElementById(`avail-${productId}`);

    if (!pointId || !start || !end) {
      box.innerHTML = `<div class="msg err">Укажи point_id, start и end</div>`;
      return;
    }

    box.innerHTML = `<div class="msg">Проверяю...</div>`;

    try {
      const res = await apiGet("/availability", {
        point_id: pointId,
        product_id: productId,
        start,
        end,
      });

      const ids = (res.item_ids || []).slice(0, 20);
      box.innerHTML = `
        <div class="msg ok">
          Доступно: <b>${res.available_count}</b>
        </div>
        <div class="meta">
          item_ids (первые 20): <span class="code">${ids.join(", ") || "-"}</span>
        </div>
      `;
    } catch (e) {
      box.innerHTML = `<div class="msg err">${escapeHtml(e.message)}</div>`;
    }
  },
};

window.CatalogUI = CatalogUI;

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// app/static/js/app.js
function qs(id) { return document.getElementById(id); }

function todayISO() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function addDaysISO(iso, days) {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

async function fetchJSON(url) {
  const r = await fetch(url, { credentials: "include" });
  const txt = await r.text();
  let data;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = txt; }
  if (!r.ok) {
    const msg = (data && data.detail) ? data.detail : `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

function productParams(p) {
  const parts = [];
  if (p.volume_liters != null) parts.push(`объём: ${p.volume_liters}л`);
  if (p.people_count != null) parts.push(`мест: ${p.people_count}`);
  if (p.temperature_min != null) parts.push(`t° min: ${p.temperature_min}`);
  return parts.length ? parts.join(", ") : "—";
}

async function loadProducts() {
  const msg = qs("catalogMsg");
  const tbody = qs("productsTbody");
  const qName = qs("qName").value.trim();

  msg.textContent = "Загрузка...";
  tbody.innerHTML = "";

  const params = new URLSearchParams();
  if (qName) params.set("name", qName);
  params.set("limit", "200");

  const url = `/catalog/products?${params.toString()}`;
  const products = await fetchJSON(url);

  if (!products.length) {
    msg.textContent = "Товары не найдены.";
    return;
  }

  msg.textContent = `Найдено: ${products.length}`;

  for (const p of products) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${p.product_id}</td>
      <td>${p.name}</td>
      <td>${p.brand ?? "—"}</td>
      <td><span class="badge">${productParams(p)}</span></td>
      <td>
        <div><span class="badge">day: ${p.default_daily_price}</span></div>
        <div style="margin-top:6px;"><span class="badge">dep: ${p.default_deposit}</span></div>
      </td>
      <td>
        <button class="btn" data-action="check" data-product-id="${p.product_id}">
          Проверить доступность
        </button>
        <div class="msg" id="avail-${p.product_id}"></div>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function checkAvailability(productId) {
  const pointId = Number(qs("pointId").value || 1);
  const start = qs("startDate").value;
  const end = qs("endDate").value;

  const out = qs(`avail-${productId}`);
  out.textContent = "Проверяем...";

  if (!start || !end) {
    out.textContent = "Укажи даты start/end.";
    return;
  }

  const params = new URLSearchParams({
    point_id: String(pointId),
    product_id: String(productId),
    start,
    end,
  });

  const data = await fetchJSON(`/availability?${params.toString()}`);
  out.innerHTML = `
    <div>Доступно: <b>${data.available_count}</b></div>
    <div class="mono" style="margin-top:6px; word-break:break-all;">
      item_ids: ${data.item_ids.join(", ")}
    </div>
  `;
}

document.addEventListener("DOMContentLoaded", async () => {
  // Если это не страница каталога — просто выходим
  if (!qs("productsTable")) return;

  const start = qs("startDate");
  const end = qs("endDate");
  const base = todayISO();
  start.value = addDaysISO(base, 1);
  end.value = addDaysISO(base, 3);

  qs("btnReload").addEventListener("click", async () => {
    try { await loadProducts(); } catch (e) { qs("catalogMsg").textContent = `Ошибка: ${e.message}`; }
  });

  qs("productsTbody").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action='check']");
    if (!btn) return;
    const pid = Number(btn.dataset.productId);
    btn.disabled = true;
    try { await checkAvailability(pid); }
    catch (err) { qs(`avail-${pid}`).textContent = `Ошибка: ${err.message}`; }
    finally { btn.disabled = false; }
  });

  try { await loadProducts(); }
  catch (e) { qs("catalogMsg").textContent = `Ошибка: ${e.message}`; }
});

