/* Hermes Family OS — Frontend SPA */

const TOKEN_KEY = "hermes_token";
const MODULES = [
  { id: "dashboard", label: "Dashboard" },
  { id: "calendar", label: "Kalender" },
  { id: "tasks", label: "Aufgaben" },
  { id: "shopping", label: "Einkauf" },
  { id: "reminders", label: "Erinnerungen" },
  { id: "documents", label: "Dokumente" },
  { id: "inventory", label: "Inventar" },
  { id: "smarthome", label: "Smart Home" },
  { id: "family", label: "Familie" },
  { id: "system", label: "System" },
];

let currentUser = null;
let currentView = "dashboard";

/* ---------- API ---------- */
function authHeader() {
  const t = localStorage.getItem(TOKEN_KEY);
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function tryRefresh() {
  try {
    const res = await fetch("/api/auth/refresh", { method: "POST", credentials: "include" });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.access_token) { localStorage.setItem(TOKEN_KEY, data.access_token); return true; }
  } catch (_) {}
  return false;
}

async function api(path, opts = {}, _retried = false) {
  const res = await fetch(path, {
    ...opts,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeader(), ...(opts.headers || {}) },
  });
  if (res.status === 401) {
    if (!_retried && (await tryRefresh())) return api(path, opts, true);
    localStorage.removeItem(TOKEN_KEY);
    location.href = "/login.html";
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || detail; } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}

/* ---------- Helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}
function fmtDay(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleDateString("de-DE", { weekday: "short" });
}
function fmtDate(iso) {
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleDateString("de-DE", { day: "2-digit", month: "short" });
}

/* ---------- Boot ---------- */
async function boot() {
  if (!localStorage.getItem(TOKEN_KEY)) {
    if (!(await tryRefresh())) { location.href = "/login.html"; return; }
  }
  try {
    currentUser = await api("/api/auth/me");
  } catch (_) { return; }

  $("#btn-profile").textContent = (currentUser.full_name || currentUser.username || "?")[0].toUpperCase();
  initTheme();
  renderNav();
  bindChrome();
  navigate("dashboard");
  registerServiceWorker();
}

function renderNav() {
  $("#nav").innerHTML = MODULES.map(
    (m) => `<button data-nav="${m.id}" class="${m.id === currentView ? "active" : ""}">${m.label}</button>`
  ).join("");
}

function bindChrome() {
  $("#nav").addEventListener("click", (e) => {
    const b = e.target.closest("[data-nav]");
    if (b) navigate(b.dataset.nav);
  });
  $("#btn-theme").addEventListener("click", toggleTheme);
  $("#btn-ai").addEventListener("click", openAI);
  $("#ai-close").addEventListener("click", closeAI);
  $("#overlay").addEventListener("click", closeAI);
  $("#btn-search").addEventListener("click", () => navigate("search"));
  $("#btn-profile").addEventListener("click", profileMenu);
  $("#ai-send").addEventListener("click", sendAI);
  $("#ai-text").addEventListener("keydown", (e) => { if (e.key === "Enter") sendAI(); });

  // Event delegation for view actions
  $("#view").addEventListener("click", onViewClick);
  $("#view").addEventListener("submit", onViewSubmit);
}

function navigate(view) {
  currentView = view;
  document.querySelectorAll("[data-nav]").forEach((b) => b.classList.toggle("active", b.dataset.nav === view));
  const fn = VIEWS[view];
  if (fn) fn();
}

/* ---------- Theme ---------- */
function initTheme() {
  const saved = localStorage.getItem("hermes_theme");
  if (saved) document.documentElement.dataset.theme = saved;
}
function toggleTheme() {
  const cur = document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = cur === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("hermes_theme", next);
}

/* ---------- Profile ---------- */
async function profileMenu() {
  const action = prompt(
    `Angemeldet als ${currentUser.username} (${currentUser.role}).\n\n` +
    `Tippe eine Aktion:\n- "logout" zum Abmelden\n- "push" für Benachrichtigungen`
  );
  if (action === "logout") {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {}
    localStorage.removeItem(TOKEN_KEY);
    location.href = "/login.html";
  } else if (action === "push") {
    enablePush();
  }
}

/* ---------- Views ---------- */
const VIEWS = {};
const loading = () => `<div class="grid"><div class="card"><div class="skeleton" style="height:80px"></div></div><div class="card"><div class="skeleton" style="height:80px"></div></div></div>`;

VIEWS.dashboard = async function () {
  const v = $("#view");
  v.innerHTML = loading();
  try {
    const d = await api("/api/dashboard");
    $("#greeting").textContent = d.greeting || "Willkommen";
    $("#date").textContent = new Date(d.date).toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    v.innerHTML = dashboardHTML(d);
  } catch (e) {
    v.innerHTML = `<div class="card"><div class="empty">Dashboard konnte nicht geladen werden.<br>${esc(e.message)}</div></div>`;
  }
};

function dashboardHTML(d) {
  const parts = [];
  parts.push(`<div class="grid">`);

  // Insights (full width)
  if (d.insights && d.insights.length) {
    parts.push(`<div class="card span-2"><h3>💡 Hermes denkt mit</h3>` +
      d.insights.map((i) => `
        <div class="insight ${esc(i.priority)}">
          <div class="ic">${esc(i.icon || "•")}</div>
          <div><div class="t">${esc(i.title)}</div><div class="m">${esc(i.message)}</div></div>
        </div>`).join("") + `</div>`);
  }

  // Weather
  const w = d.weather && d.weather.current;
  if (w && w.temperature != null) {
    parts.push(`<div class="card"><h3>${esc(w.location || "Wetter")}</h3>
      <div class="weather-now"><div class="emoji">${esc(w.icon || "🌤️")}</div>
      <div><div class="temp">${Math.round(w.temperature)}°</div><div class="desc">${esc(w.description || "")}</div></div></div>
      <div class="forecast">${(d.weather.forecast || []).slice(1, 6).map((f) => `
        <div class="day"><div class="d">${fmtDay(f.date)}</div><div class="e">${esc(f.icon || "")}</div>
        <div>${Math.round(f.temp_max)}°</div></div>`).join("")}</div></div>`);
  }

  // Calendar today
  parts.push(card("📅 Heute", "calendar",
    (d.calendar && d.calendar.today && d.calendar.today.length)
      ? list(d.calendar.today.map((e) => rowHTML({
          lead: "•", leadColor: e.color, t: e.title,
          s: e.location || (e.all_day ? "Ganztägig" : e.calendar),
          trail: e.all_day ? "" : fmtTime(e.start),
        })))
      : empty("Keine Termine heute")));

  // Tasks
  parts.push(card(`✅ Aufgaben`, "tasks",
    (d.tasks && d.tasks.items && d.tasks.items.length)
      ? list(d.tasks.items.map((t) => rowHTML({ lead: "•", t: t.title, s: t.due_date ? "Fällig " + fmtDate(t.due_date) : "" })))
      : empty("Alles erledigt 🎉"), d.tasks ? d.tasks.open_count : 0));

  // Shopping (with quick add)
  parts.push(`<div class="card"><h3>🛒 Einkauf <span class="count">${d.shopping ? d.shopping.count : 0}</span></h3>` +
    ((d.shopping && d.shopping.items && d.shopping.items.length)
      ? list(d.shopping.items.map((i) => rowHTML({ lead: "•", t: i.name, s: i.category || "" })))
      : empty("Liste ist leer")) +
    `<form class="add-row" data-form="add-shopping"><input class="input" name="name" placeholder="Artikel hinzufügen …" autocomplete="off"><button class="btn">+</button></form></div>`);

  // Reminders
  parts.push(card("⏰ Erinnerungen", "reminders",
    (d.reminders && d.reminders.length)
      ? list(d.reminders.map((r) => `
          <div class="row">
            <button class="check" data-action="complete-reminder" data-id="${r.id}"></button>
            <div class="body"><div class="t">${esc(r.title)}</div><div class="s">${r.due_at ? "Fällig " + fmtDate(r.due_at) + " " + fmtTime(r.due_at) : ""}</div></div>
            <span class="pill ${esc(r.priority)}">${esc(r.priority)}</span>
          </div>`).join(""))
      : empty("Keine Erinnerungen")));

  // Packages
  if (d.packages && d.packages.length) {
    parts.push(card("📦 Pakete", "dashboard",
      list(d.packages.map((p) => rowHTML({ lead: "📦", t: (p.carrier || "").toUpperCase() + (p.description ? " – " + p.description : ""), s: p.status, trail: p.expected_at ? fmtDate(p.expected_at) : "" })))));
  }

  // Smart home
  const sh = d.smarthome;
  if (sh && (sh.lights_on != null)) {
    parts.push(card("🏠 Smart Home", "smarthome",
      `<div class="row"><div class="lead">💡</div><div class="body"><div class="t">${sh.lights_on} Lichter an</div></div></div>
       <div class="row"><div class="lead">🚪</div><div class="body"><div class="t">${sh.doors_windows_open} Türen/Fenster offen</div><div class="s">${(sh.open_entities || []).join(", ")}</div></div></div>`));
  }

  parts.push(`</div>`);
  return parts.join("");
}

function card(title, navTo, inner, count) {
  const c = count != null ? `<span class="count">${count}</span>` : "";
  return `<div class="card">${navTo ? `<h3 data-nav="${navTo}" style="cursor:pointer">${title} ${c}</h3>` : `<h3>${title} ${c}</h3>`}${inner}</div>`;
}
function list(rows) { return `<div class="list">${rows}</div>`; }
function empty(msg) { return `<div class="empty">${esc(msg)}</div>`; }
function rowHTML({ lead, leadColor, t, s, trail }) {
  const leadEl = leadColor ? `<span class="dot" style="background:${esc(leadColor)}"></span>` : `<div class="lead">${esc(lead || "•")}</div>`;
  return `<div class="row">${leadEl}<div class="body"><div class="t">${esc(t)}</div>${s ? `<div class="s">${esc(s)}</div>` : ""}</div>${trail ? `<div class="trail">${esc(trail)}</div>` : ""}</div>`;
}

/* Simple module views */
VIEWS.calendar = simpleView("📅 Termine (7 Tage)", async () => {
  const ev = await api("/api/calendar/events?days=7");
  return ev.length ? list(ev.map((e) => rowHTML({ lead: "•", leadColor: e.color, t: e.title, s: e.calendar, trail: (e.all_day ? fmtDate(e.start) : fmtDate(e.start) + " " + fmtTime(e.start)) }))) : empty("Keine Termine oder Kalender nicht konfiguriert");
});

VIEWS.tasks = async function () {
  await renderListView({
    title: "✅ Aufgaben",
    fetch: () => api("/api/tasks"),
    row: (t) => rowHTML({ lead: "•", t: t.title, s: t.due_date ? "Fällig " + fmtDate(t.due_date) : "" }),
    emptyMsg: "Keine offenen Aufgaben (oder Vikunja nicht konfiguriert)",
    form: `<form class="add-row" data-form="add-task"><input class="input" name="title" placeholder="Neue Aufgabe …"><button class="btn">+</button></form>`,
  });
};

VIEWS.shopping = async function () {
  await renderListView({
    title: "🛒 Einkaufsliste",
    fetch: () => api("/api/shopping"),
    row: (i) => rowHTML({ lead: "•", t: i.name, s: i.category || "" }),
    emptyMsg: "Liste ist leer (oder KitchenOwl nicht konfiguriert)",
    form: `<form class="add-row" data-form="add-shopping"><input class="input" name="name" placeholder="Artikel hinzufügen …"><button class="btn">+</button></form>`,
  });
};

VIEWS.reminders = async function () {
  await renderListView({
    title: "⏰ Erinnerungen",
    fetch: () => api("/api/reminders"),
    row: (r) => `<div class="row"><button class="check" data-action="complete-reminder" data-id="${r.id}"></button>
      <div class="body"><div class="t">${esc(r.title)}</div><div class="s">${r.due_at ? "Fällig " + fmtDate(r.due_at) + " " + fmtTime(r.due_at) : ""}</div></div>
      <span class="pill ${esc(r.priority)}">${esc(r.priority)}</span></div>`,
    emptyMsg: "Keine Erinnerungen",
    form: `<form class="add-row" data-form="add-reminder"><input class="input" name="title" placeholder="Woran erinnern?"><button class="btn">+</button></form>`,
  });
};

VIEWS.documents = simpleView("📄 Dokumente", async () => {
  const docs = await api("/api/documents/recent?limit=15");
  return docs.length ? list(docs.map((d) => rowHTML({ lead: "📄", t: d.title, s: d.created || "", trail: "" }))) : empty("Keine Dokumente (oder Paperless nicht konfiguriert)");
});

VIEWS.inventory = simpleView("📦 Inventar", async () => {
  const items = await api("/api/inventory?limit=50");
  return items.length ? list(items.map((i) => rowHTML({ lead: "📦", t: i.name, s: i.location || "", trail: "x" + (i.quantity || 1) }))) : empty("Kein Inventar (oder Homebox nicht konfiguriert)");
});

VIEWS.smarthome = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const ov = await api("/api/smarthome/overview");
    const lights = await api("/api/smarthome/states?domain=light").catch(() => []);
    let html = `<div class="card"><h3>🏠 Übersicht</h3>`;
    if (ov && ov.lights_on != null) {
      html += `<div class="row"><div class="lead">💡</div><div class="body"><div class="t">${ov.lights_on} Lichter an</div></div></div>
               <div class="row"><div class="lead">🚪</div><div class="body"><div class="t">${ov.doors_windows_open} offen</div><div class="s">${(ov.open_entities || []).join(", ")}</div></div></div>`;
      (ov.temperature_sensors || []).forEach((t) => { html += rowHTML({ lead: "🌡️", t: t.name, trail: t.value + (t.unit || "") }); });
    } else { html += empty("Home Assistant nicht konfiguriert"); }
    html += `</div>`;
    if (lights.length) {
      html += `<div class="card" style="margin-top:14px"><h3>💡 Lichter</h3>` + lights.map((l) => `
        <div class="row"><div class="lead">💡</div><div class="body"><div class="t">${esc(l.name)}</div></div>
        <button class="btn ghost" data-action="toggle-light" data-entity="${esc(l.entity_id)}" data-state="${esc(l.state)}">${l.state === "on" ? "Aus" : "An"}</button></div>`).join("") + `</div>`;
    }
    v.innerHTML = html;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
};

VIEWS.family = simpleView("👪 Familie", async () => {
  const members = await api("/api/family");
  return members.length ? list(members.map((m) => `<div class="row"><span class="dot" style="background:${esc(m.color)}"></span>
    <div class="lead">${esc(m.avatar || "👤")}</div><div class="body"><div class="t">${esc(m.name)}</div><div class="s">${esc(m.role)}${m.birthday ? " · 🎂 " + esc(m.birthday) : ""}</div></div></div>`)) : empty("Noch keine Familienmitglieder angelegt");
});

VIEWS.system = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const [health, conns, aiStatus] = await Promise.all([
      api("/api/health"), api("/api/connectors/health"), api("/api/ai/status"),
    ]);
    let html = `<div class="card"><h3>🔌 Fachsysteme (Connectors)</h3>` + conns.map((c) => `
      <div class="row"><div class="lead">${esc(c.icon)}</div>
      <div class="body"><div class="t">${esc(c.display_name)}</div><div class="s">${c.configured ? "konfiguriert" : "nicht konfiguriert"}</div></div>
      <span class="status-dot ${esc(c.status)}" title="${esc(c.status)}"></span></div>`).join("") + `</div>`;

    html += `<div class="card" style="margin-top:14px"><h3>✨ Hermes AI</h3>
      <div class="row"><div class="lead">🧠</div><div class="body"><div class="t">Modus: ${esc(aiStatus.mode)}</div><div class="s">${aiStatus.tool_count} Werkzeuge verfügbar</div></div></div></div>`;

    html += `<div class="card" style="margin-top:14px"><h3>🔔 Benachrichtigungen</h3>
      <div class="row"><div class="body"><div class="t">Push ${health.features.push ? "aktiv" : "nicht konfiguriert"}</div>
      <div class="s">Web Push für Erinnerungen & Hinweise</div></div>
      <button class="btn ghost" data-action="enable-push">Aktivieren</button></div></div>`;

    html += `<div class="card" style="margin-top:14px"><h3>ℹ️ System</h3>
      <div class="s" style="color:var(--text-soft)">${esc(health.app)} v${esc(health.version)} · ${esc(health.environment)}</div></div>`;
    v.innerHTML = html;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
};

VIEWS.search = function () {
  $("#view").innerHTML = `<div class="card"><h3>🔍 Globale Suche</h3>
    <form class="add-row" data-form="search"><input class="input" name="q" placeholder="Suche in Dokumenten, Aufgaben, Inventar …" autofocus><button class="btn">Suchen</button></form>
    <div id="search-results" style="margin-top:12px"></div></div>`;
};

function simpleView(title, fetcher) {
  return async function () {
    const v = $("#view"); v.innerHTML = loading();
    try { v.innerHTML = `<div class="card"><h3>${title}</h3>${await fetcher()}</div>`; }
    catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
  };
}

async function renderListView({ title, fetch: fetcher, row, emptyMsg, form }) {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const items = await fetcher();
    v.innerHTML = `<div class="card"><h3>${title} <span class="count">${items.length}</span></h3>${items.length ? list(items.map(row)) : empty(emptyMsg)}${form || ""}</div>`;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div>${form || ""}</div>`; }
}

/* ---------- View interactions ---------- */
async function onViewClick(e) {
  const navEl = e.target.closest("[data-nav]");
  if (navEl && navEl.dataset.nav) { navigate(navEl.dataset.nav); return; }

  const act = e.target.closest("[data-action]");
  if (!act) return;
  const action = act.dataset.action;

  if (action === "complete-reminder") {
    act.classList.add("done"); act.innerHTML = "✓";
    try { await api(`/api/reminders/${act.dataset.id}`, { method: "PATCH", body: JSON.stringify({ completed: true }) }); toast("Erledigt ✓"); setTimeout(() => navigate(currentView), 500); }
    catch (err) { toast(err.message); }
  } else if (action === "toggle-light") {
    const on = act.dataset.state === "on";
    try {
      await api("/api/smarthome/service", { method: "POST", body: JSON.stringify({ domain: "light", service: on ? "turn_off" : "turn_on", entity_id: act.dataset.entity }) });
      toast("Gesendet"); setTimeout(() => navigate("smarthome"), 400);
    } catch (err) { toast(err.message); }
  } else if (action === "enable-push") {
    enablePush();
  }
}

async function onViewSubmit(e) {
  e.preventDefault();
  const form = e.target.closest("[data-form]");
  if (!form) return;
  const kind = form.dataset.form;
  const data = Object.fromEntries(new FormData(form).entries());

  try {
    if (kind === "add-shopping") {
      if (!data.name) return;
      await api("/api/shopping", { method: "POST", body: JSON.stringify({ name: data.name }) });
      toast("Zur Einkaufsliste hinzugefügt 🛒");
    } else if (kind === "add-task") {
      if (!data.title) return;
      await api("/api/tasks", { method: "POST", body: JSON.stringify({ title: data.title }) });
      toast("Aufgabe angelegt ✅");
    } else if (kind === "add-reminder") {
      if (!data.title) return;
      await api("/api/reminders", { method: "POST", body: JSON.stringify({ title: data.title, priority: "info" }) });
      toast("Erinnerung gespeichert ⏰");
    } else if (kind === "search") {
      const res = await api("/api/search?q=" + encodeURIComponent(data.q));
      $("#search-results").innerHTML = res.results.length
        ? list(res.results.map((r) => `<a class="row" href="${esc(r.url || "#")}" target="_blank"><div class="lead">${esc(r.icon || "•")}</div><div class="body"><div class="t">${esc(r.title)}</div><div class="s">${esc(r.source)}</div></div></a>`))
        : empty("Keine Treffer");
      return;
    }
    navigate(currentView);
  } catch (err) { toast(err.message); }
}

/* ---------- AI Panel ---------- */
let aiHistory = [];
function openAI() {
  $("#overlay").classList.add("show");
  $("#ai-panel").classList.add("show");
  if (!$("#ai-msgs").childElementCount) {
    addAIMessage("bot", "Hallo! Ich bin Hermes 👋 Wie kann ich helfen?");
    renderChips(["Was steht heute an?", "Bestell Milch", "Wie ist das Wetter?", "Erinnere mich heute Abend an den Müll"]);
    api("/api/ai/status").then((s) => { $("#ai-mode").textContent = s.mode === "llm" ? "KI-Modell aktiv" : "Regelbasiert"; }).catch(() => {});
  }
  setTimeout(() => $("#ai-text").focus(), 250);
}
function closeAI() { $("#overlay").classList.remove("show"); $("#ai-panel").classList.remove("show"); }

function renderChips(items) {
  $("#ai-chips").innerHTML = items.map((c) => `<button class="chip">${esc(c)}</button>`).join("");
  $("#ai-chips").querySelectorAll(".chip").forEach((el) => el.addEventListener("click", () => { $("#ai-text").value = el.textContent; sendAI(); }));
}

function addAIMessage(role, text, actions) {
  const m = document.createElement("div");
  m.className = "msg " + (role === "user" ? "user" : "bot");
  m.textContent = text;
  if (actions && actions.length) { const a = document.createElement("div"); a.className = "act"; a.textContent = "🔧 " + actions.join(", "); m.appendChild(a); }
  $("#ai-msgs").appendChild(m);
  $("#ai-msgs").scrollTop = $("#ai-msgs").scrollHeight;
  return m;
}

async function sendAI() {
  const input = $("#ai-text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  $("#ai-chips").innerHTML = "";
  addAIMessage("user", text);
  const thinking = addAIMessage("bot", "…");
  try {
    const res = await api("/api/ai/chat", { method: "POST", body: JSON.stringify({ message: text, history: aiHistory.slice(-6) }) });
    thinking.textContent = res.reply || "(keine Antwort)";
    if (res.actions && res.actions.length) { const a = document.createElement("div"); a.className = "act"; a.textContent = "🔧 " + res.actions.join(", "); thinking.appendChild(a); }
    aiHistory.push({ role: "user", content: text }, { role: "assistant", content: res.reply || "" });
    if (res.actions && res.actions.length && currentView === "dashboard") navigate("dashboard");
  } catch (err) { thinking.textContent = "Fehler: " + err.message; }
}

/* ---------- Push ---------- */
function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch((e) => console.warn("SW registration failed", e));
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function enablePush() {
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) { toast("Push nicht unterstützt"); return; }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") { toast("Berechtigung abgelehnt"); return; }
    const reg = await navigator.serviceWorker.ready;
    const { publicKey } = await api("/api/notifications/vapid-public-key");
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(publicKey) });
    const json = sub.toJSON();
    await api("/api/notifications/subscribe", { method: "POST", body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }) });
    toast("Benachrichtigungen aktiviert 🔔");
  } catch (err) { toast("Push-Fehler: " + err.message); }
}

boot();
