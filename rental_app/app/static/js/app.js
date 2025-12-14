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
