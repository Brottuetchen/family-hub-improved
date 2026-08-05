/* Hermes Family OS — Frontend SPA */

const TOKEN_KEY = "hermes_token";
const MODULES = [
  { id: "dashboard", label: "Dashboard" },
  { id: "assistant", label: "Hermes" },
  { id: "calendar", label: "Kalender" },
  { id: "tasks", label: "Aufgaben" },
  { id: "shopping", label: "Einkauf" },
  { id: "meals", label: "Essen" },
  { id: "reminders", label: "Erinnerungen" },
  { id: "documents", label: "Dokumente" },
  { id: "finance", label: "Finanzen" },
  { id: "inventory", label: "Inventar" },
  { id: "maintenance", label: "Wartung" },
  { id: "smarthome", label: "Smart Home" },
  { id: "media", label: "Medien" },
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
  maybeIOSHint();
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
  $("#btn-ai").addEventListener("click", () => navigate("assistant"));
  $("#btn-search").addEventListener("click", () => navigate("search"));
  $("#btn-profile").addEventListener("click", profileMenu);

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

/* ---------- Profile menu (Dropdown) ---------- */
function profileMenu() {
  const existing = document.getElementById("profile-menu");
  if (existing) { existing.remove(); return; }
  const menu = document.createElement("div");
  menu.id = "profile-menu";
  menu.className = "menu";
  menu.innerHTML =
    `<div class="mhead">${esc(currentUser.full_name || currentUser.username)} · ${esc(currentUser.role)}</div>` +
    `<button data-m="push">🔔 Benachrichtigungen aktivieren</button>` +
    `<button data-m="theme">🌓 Design wechseln</button>` +
    `<button data-m="logout" class="danger">↩︎ Abmelden</button>`;
  document.body.appendChild(menu);
  menu.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-m]");
    if (!b) return;
    const m = b.dataset.m;
    menu.remove();
    if (m === "push") enablePush();
    else if (m === "theme") toggleTheme();
    else if (m === "logout") {
      try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {}
      localStorage.removeItem(TOKEN_KEY);
      location.href = "/login.html";
    }
  });
  setTimeout(() => {
    document.addEventListener("click", function close(ev) {
      if (!menu.contains(ev.target) && ev.target.id !== "btn-profile") {
        menu.remove();
        document.removeEventListener("click", close);
      }
    });
  }, 0);
}

/* iOS: Hinweis zum Installieren als App (nötig für Push auf iPhone) */
function maybeIOSHint() {
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = window.navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;
  if (!isIOS || standalone || localStorage.getItem("hermes_ios_hint")) return;
  const b = document.createElement("div");
  b.className = "ios-hint";
  b.innerHTML = `📲 Für App-Feeling &amp; Push: <b>Teilen</b> → <b>Zum Home-Bildschirm</b> <button title="Ausblenden">✕</button>`;
  document.querySelector(".app").insertBefore(b, document.querySelector(".greeting"));
  b.querySelector("button").addEventListener("click", () => { b.remove(); localStorage.setItem("hermes_ios_hint", "1"); });
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

  // Holiday banner (full width, above grid)
  if (d.holidays && d.holidays.today) {
    parts.push(`<div class="card span-2" style="margin-bottom:14px;background:linear-gradient(135deg,var(--primary-soft),var(--bg-elev))"><div class="insight"><div class="ic">🎉</div><div><div class="t">Feiertag: ${esc(d.holidays.today)}</div><div class="m">Heute ist frei.</div></div></div></div>`);
  }

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
            <div class="body"><div class="t">${esc(r.title)}</div><div class="s">${r.due_at ? "Fällig " + fmtDate(r.due_at) + " " + fmtTime(r.due_at) : ""}${recSuffix(r.recurrence)}</div></div>
            <span class="pill ${esc(r.priority)}">${esc(r.priority)}</span>
          </div>`).join(""))
      : empty("Keine Erinnerungen")));

  // Packages
  if (d.packages && d.packages.length) {
    parts.push(card("📦 Pakete", "dashboard",
      list(d.packages.map((p) => rowHTML({ lead: "📦", t: (p.carrier || "").toUpperCase() + (p.description ? " – " + p.description : ""), s: p.status, trail: p.expected_at ? fmtDate(p.expected_at) : "" })))));
  }

  // Meals today
  if (d.meals_today && d.meals_today.length) {
    parts.push(card("🍽️ Essen heute", "meals",
      list(d.meals_today.map((m) => rowHTML({ lead: "🍽️", t: m.title, s: mealLabel(m.meal_type) })))));
  }

  // Maintenance due
  if (d.maintenance_due && d.maintenance_due.length) {
    parts.push(card("🔧 Wartung fällig", "maintenance",
      list(d.maintenance_due.map((m) => rowHTML({ lead: "🔧", t: m.title, s: m.category, trail: fmtDate(m.next_due) })))));
  }

  // Finance summary
  if (d.finance && d.finance.count > 0) {
    parts.push(card("💶 Fixkosten", "finance",
      `<div class="weather-now"><div><div class="temp">${d.finance.monthly_total.toFixed(2)} €</div><div class="desc">pro Monat · ${d.finance.count} Posten</div></div></div>`));
  }

  // Now playing (media)
  if (d.now_playing && d.now_playing.length) {
    parts.push(card("▶️ Läuft gerade", "media",
      list(d.now_playing.map((s) => rowHTML({ lead: s.icon || "▶️", t: s.title, s: [s.subtitle, s.user].filter(Boolean).join(" · ") })))));
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
function list(rows) { return `<div class="list">${Array.isArray(rows) ? rows.join("") : rows}</div>`; }
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
      <div class="body"><div class="t">${esc(r.title)}</div><div class="s">${r.due_at ? "Fällig " + fmtDate(r.due_at) + " " + fmtTime(r.due_at) : "Ohne Termin"}${recSuffix(r.recurrence)}</div></div>
      <span class="pill ${esc(r.priority)}">${esc(r.priority)}</span></div>`,
    emptyMsg: "Keine Erinnerungen",
    form: `<form class="add-row" data-form="add-reminder" style="flex-wrap:wrap">
      <input class="input" name="title" placeholder="Woran erinnern? (z.B. Müll rausbringen)" style="flex:1 1 100%">
      <input class="input" name="due_at" type="datetime-local" style="flex:1 1 46%">
      <select class="input" name="recurrence" style="flex:1 1 46%">
        <option value="none">Einmalig</option>
        <option value="daily">Täglich</option>
        <option value="weekdays">Werktags (Mo–Fr)</option>
        <option value="weekly">Wöchentlich</option>
        <option value="monthly">Monatlich</option>
      </select>
      <button class="btn block">Erinnerung hinzufügen</button></form>`,
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

VIEWS.media = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const [np, reqs, recent, upcoming, queue] = await Promise.all([
      api("/api/media/now-playing"),
      api("/api/media/requests").catch(() => []),
      api("/api/media/recent?limit=6").catch(() => []),
      api("/api/media/upcoming?days=14").catch(() => []),
      api("/api/media/queue").catch(() => []),
    ]);
    let html = `<div class="card"><h3>▶️ Läuft gerade <span class="count">${np.count}</span></h3>`;
    html += np.streams.length
      ? list(np.streams.map((s) => rowHTML({ lead: s.icon || "▶️", t: s.title, s: [s.subtitle, s.user].filter(Boolean).join(" · ") })))
      : empty("Gerade läuft nichts (oder Medien-Connectoren nicht konfiguriert)");
    html += `</div>`;
    if (queue.length) {
      html += `<div class="card" style="margin-top:14px"><h3>⬇️ Downloads <span class="count">${queue.length}</span></h3>` +
        list(queue.map((q) => rowHTML({ lead: q.icon || "⬇️", t: q.title, s: `${q.progress}%${q.status ? " · " + q.status : ""}` }))) + `</div>`;
    }
    if (upcoming.length) {
      html += `<div class="card" style="margin-top:14px"><h3>🗓️ Demnächst</h3>` +
        list(upcoming.slice(0, 15).map((u) => rowHTML({ lead: u.icon || "•", t: u.title, s: [u.subtitle, (u.date || "").slice(0, 10)].filter(Boolean).join(" · ") }))) + `</div>`;
    }
    if (reqs.length) {
      html += `<div class="card" style="margin-top:14px"><h3>🎞️ Offene Anfragen <span class="count">${reqs.length}</span></h3>` +
        list(reqs.map((r) => rowHTML({ lead: r.type === "tv" ? "📺" : "🎬", t: r.title, s: "von " + r.requested_by }))) + `</div>`;
    }
    if (recent.length) {
      html += `<div class="card" style="margin-top:14px"><h3>🆕 Neu bei Plex</h3>` +
        list(recent.map((r) => rowHTML({ lead: "🎬", t: r.title, s: r.year ? String(r.year) : "" }))) + `</div>`;
    }
    if (["partner", "admin"].includes(currentUser && currentUser.role)) {
      html += `<div class="card" style="margin-top:14px"><h3>➕ Serie/Film anlegen</h3>
        <form class="add-row" data-form="add-media" style="flex-wrap:wrap">
          <select class="input" name="kind" style="flex:0 0 auto"><option value="series">📺 Serie</option><option value="movie">🎬 Film</option></select>
          <input class="input" name="query" placeholder="Titel suchen …" style="flex:1 1 55%">
          <button class="btn">Suchen &amp; anlegen</button>
        </form>
        <div class="s" style="color:var(--text-soft);margin-top:6px">Legt den Titel in Sonarr/Radarr an und startet die Suche.</div></div>`;
    }
    v.innerHTML = html;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
};

VIEWS.family = simpleView("👪 Familie", async () => {
  const members = await api("/api/family");
  return members.length ? list(members.map((m) => `<div class="row"><span class="dot" style="background:${esc(m.color)}"></span>
    <div class="lead">${esc(m.avatar || "👤")}</div><div class="body"><div class="t">${esc(m.name)}</div><div class="s">${esc(m.role)}${m.birthday ? " · 🎂 " + esc(m.birthday) : ""}</div></div></div>`)) : empty("Noch keine Familienmitglieder angelegt");
});

function mealLabel(type) {
  return { breakfast: "Frühstück", lunch: "Mittagessen", dinner: "Abendessen" }[type] || type;
}

function recLabel(rec) {
  return { daily: "täglich", weekdays: "werktags", weekly: "wöchentlich", monthly: "monatlich" }[rec] || "";
}
function recSuffix(rec) {
  return rec && rec !== "none" ? ` · 🔁 ${recLabel(rec)}` : "";
}

VIEWS.meals = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const [plan, recipes] = await Promise.all([api("/api/meals/plan?days=7"), api("/api/recipes")]);
    let html = `<div class="card"><h3>🍽️ Wochenplan <span class="count">${plan.length}</span></h3>`;
    html += plan.length ? list(plan.map((e) => `<div class="row"><div class="lead">🍽️</div>
      <div class="body"><div class="t">${esc(e.title)}</div><div class="s">${esc(fmtDate(e.date))} · ${esc(mealLabel(e.meal_type))}</div></div>
      <button class="icon-btn" data-action="del-meal" data-id="${e.id}">✕</button></div>`)) : empty("Nichts geplant");
    html += `<button class="btn block" style="margin-top:12px" data-action="gen-shopping">🛒 Einkaufsliste aus Plan erzeugen</button></div>`;

    html += `<div class="card" style="margin-top:14px"><h3>📖 Rezepte <span class="count">${recipes.length}</span></h3>`;
    html += recipes.length ? list(recipes.map((r) => `<div class="row"><div class="lead">📖</div>
      <div class="body"><div class="t">${esc(r.title)}</div><div class="s">${(r.ingredients || []).length} Zutaten · ${r.servings} Port.</div></div>
      <button class="btn ghost" data-action="plan-today" data-recipe="${r.id}">Heute</button></div>`)) : empty("Keine Rezepte");
    html += `<form class="add-row" data-form="add-recipe" style="flex-wrap:wrap">
      <input class="input" name="title" placeholder="Rezeptname" style="flex:1 1 100%">
      <input class="input" name="ingredients" placeholder="Zutaten, komma, getrennt" style="flex:1 1 100%">
      <button class="btn block">Rezept speichern</button></form></div>`;
    v.innerHTML = html;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
};

VIEWS.finance = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const [ov, expenses] = await Promise.all([api("/api/finance/overview"), api("/api/finance/expenses")]);
    let html = `<div class="card"><h3>💶 Übersicht</h3>
      <div class="weather-now"><div><div class="temp">${ov.monthly_total.toFixed(2)} €</div><div class="desc">pro Monat · ${ov.yearly_total.toFixed(2)} € / Jahr</div></div></div>`;
    const cats = Object.entries(ov.by_category || {});
    if (cats.length) html += `<div class="forecast">${cats.map(([c, val]) => `<div class="day"><div class="d">${esc(c)}</div><div>${val.toFixed(0)}€</div></div>`).join("")}</div>`;
    html += `</div>`;

    html += `<div class="card" style="margin-top:14px"><h3>🔁 Wiederkehrende Kosten <span class="count">${expenses.length}</span></h3>`;
    html += expenses.length ? list(expenses.map((e) => `<div class="row"><div class="lead">💶</div>
      <div class="body"><div class="t">${esc(e.name)}</div><div class="s">${esc(e.category)} · ${esc(e.interval)}</div></div>
      <div class="trail">${e.amount.toFixed(2)} €</div>
      <button class="icon-btn" data-action="del-expense" data-id="${e.id}">✕</button></div>`)) : empty("Noch nichts erfasst");
    html += `<form class="add-row" data-form="add-expense" style="flex-wrap:wrap">
      <input class="input" name="name" placeholder="Name (z.B. Haftpflicht)" style="flex:1 1 100%">
      <input class="input" name="amount" type="number" step="0.01" placeholder="Betrag €" style="flex:1 1 46%">
      <select class="input" name="interval" style="flex:1 1 46%"><option value="monthly">monatlich</option><option value="yearly">jährlich</option><option value="quarterly">quartal</option><option value="weekly">wöchentl.</option></select>
      <select class="input" name="category" style="flex:1 1 100%"><option value="insurance">Versicherung</option><option value="subscription">Abo</option><option value="rent">Miete</option><option value="utility">Nebenkosten</option><option value="loan">Kredit</option><option value="other">Sonstiges</option></select>
      <button class="btn block">Hinzufügen</button></form></div>`;
    v.innerHTML = html;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
};

VIEWS.maintenance = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const tasks = await api("/api/maintenance");
    let html = `<div class="card"><h3>🔧 Wartungspläne <span class="count">${tasks.length}</span></h3>`;
    html += tasks.length ? list(tasks.map((t) => `<div class="row"><div class="lead">🔧</div>
      <div class="body"><div class="t">${esc(t.title)}</div><div class="s">${esc(t.category)}${t.next_due ? " · fällig " + fmtDate(t.next_due) : ""}${t.interval_days ? " · alle " + t.interval_days + "T" : ""}</div></div>
      <button class="btn ghost" data-action="maint-done" data-id="${t.id}">Erledigt</button>
      <button class="icon-btn" data-action="del-maint" data-id="${t.id}">✕</button></div>`)) : empty("Keine Wartungen geplant");
    html += `<form class="add-row" data-form="add-maintenance" style="flex-wrap:wrap">
      <input class="input" name="title" placeholder="Was? (z.B. Rauchmelder testen)" style="flex:1 1 100%">
      <select class="input" name="category" style="flex:1 1 46%"><option value="home">Haus</option><option value="car">Auto</option><option value="garden">Garten</option><option value="appliance">Gerät</option><option value="other">Sonstiges</option></select>
      <input class="input" name="interval_days" type="number" placeholder="Intervall (Tage)" style="flex:1 1 46%">
      <button class="btn block">Plan anlegen</button></form></div>`;
    v.innerHTML = html;
  } catch (e) { v.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`; }
};

function connFormHTML(c) {
  const dot = c.configured === true ? "online" : (c.configured === false ? "disabled" : "");
  const fields = c.fields.map((f) => f.secret
    ? `<input class="input" name="${esc(f.key)}" type="password" autocomplete="off" placeholder="${f.is_set ? "•••••••• (gesetzt – leer = behalten)" : esc(f.label)}" style="flex:1 1 100%">`
    : `<input class="input" name="${esc(f.key)}" value="${esc(f.value)}" placeholder="${esc(f.label)}" style="flex:1 1 100%">`
  ).join("");
  return `<form class="add-row" data-form="admin-conn" style="flex-wrap:wrap;margin-top:12px">
    <div style="flex:1 1 100%;font-weight:700;font-size:13px;display:flex;align-items:center;gap:8px">
      <span class="status-dot ${dot}"></span>${esc(c.title)}</div>
    ${fields}
    <button class="btn">Speichern</button></form>`;
}

VIEWS.system = async function () {
  const v = $("#view"); v.innerHTML = loading();
  try {
    const isAdmin = currentUser && currentUser.role === "admin";
    const [health, conns, aiStatus, services, adminConns] = await Promise.all([
      api("/api/health"), api("/api/connectors/health"), api("/api/ai/status"),
      api("/api/connectors/services").catch(() => []),
      isAdmin ? api("/api/admin/settings").catch(() => []) : Promise.resolve([]),
    ]);
    let html = `<div class="card"><h3>🔌 Fachsysteme (Connectors)</h3>` + conns.map((c) => `
      <div class="row"><div class="lead">${esc(c.icon)}</div>
      <div class="body"><div class="t">${esc(c.display_name)}</div><div class="s">${c.configured ? "konfiguriert" : "nicht konfiguriert"}</div></div>
      <span class="status-dot ${esc(c.status)}" title="${esc(c.status)}"></span></div>`).join("") + `</div>`;

    if (adminConns.length) {
      html += `<div class="card" style="margin-top:14px"><h3>🔐 Verbindungen verwalten (Admin)</h3>
        <div class="s" style="color:var(--text-soft);margin-bottom:4px">URLs &amp; Tokens hier eintragen – sofort aktiv, kein Neustart. Tokens werden verschlüsselt gespeichert.</div>`
        + adminConns.map(connFormHTML).join("") + `</div>`;
    }

    if (services.length) {
      html += `<div class="card" style="margin-top:14px"><h3>🖥️ Homelab-Dienste</h3>` + services.map((s) => `
        <a class="row" href="${esc(s.url)}" target="_blank" rel="noopener"><div class="lead">${esc(s.icon || "🖥️")}</div>
        <div class="body"><div class="t">${esc(s.name)}</div><div class="s">${esc(s.category || "")}</div></div>
        <span class="status-dot ${esc(s.status)}" title="${esc(s.status)}"></span></a>`).join("") + `</div>`;
    }

    const aiLabel = aiStatus.connected
      ? `Hermes Agent verbunden${aiStatus.model ? " · " + esc(aiStatus.model) : ""}`
      : (aiStatus.configured ? "konfiguriert, nicht erreichbar" : "nicht verbunden");
    html += `<div class="card" style="margin-top:14px"><h3>✨ Hermes AI</h3>
      <div class="row"><div class="lead">🧠</div><div class="body"><div class="t">${aiLabel}</div><div class="s">${aiStatus.tool_count} Haushalts-Werkzeuge über MCP steuerbar</div></div></div></div>`;

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
  } else if (action === "gen-shopping") {
    try { const r = await api("/api/meals/shopping-list?days=7", { method: "POST" }); toast(r.message); }
    catch (err) { toast(err.message); }
  } else if (action === "plan-today") {
    try { await api("/api/meals/plan", { method: "POST", body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), recipe_id: Number(act.dataset.recipe) }) }); toast("Für heute eingeplant 🍽️"); navigate("meals"); }
    catch (err) { toast(err.message); }
  } else if (action === "del-meal") {
    try { await api(`/api/meals/plan/${act.dataset.id}`, { method: "DELETE" }); navigate("meals"); } catch (err) { toast(err.message); }
  } else if (action === "del-expense") {
    try { await api(`/api/finance/expenses/${act.dataset.id}`, { method: "DELETE" }); navigate("finance"); } catch (err) { toast(err.message); }
  } else if (action === "maint-done") {
    try { await api(`/api/maintenance/${act.dataset.id}/done`, { method: "POST" }); toast("Als erledigt markiert ✓"); navigate("maintenance"); } catch (err) { toast(err.message); }
  } else if (action === "del-maint") {
    try { await api(`/api/maintenance/${act.dataset.id}`, { method: "DELETE" }); navigate("maintenance"); } catch (err) { toast(err.message); }
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
      const payload = { title: data.title, priority: "info", recurrence: data.recurrence || "none" };
      if (data.due_at) payload.due_at = data.due_at; // datetime-local ist bereits lokale ISO-Zeit
      await api("/api/reminders", { method: "POST", body: JSON.stringify(payload) });
      toast("Erinnerung gespeichert ⏰");
    } else if (kind === "add-recipe") {
      if (!data.title) return;
      const ingredients = (data.ingredients || "").split(",").map((s) => s.trim()).filter(Boolean);
      await api("/api/recipes", { method: "POST", body: JSON.stringify({ title: data.title, ingredients }) });
      toast("Rezept gespeichert 📖");
    } else if (kind === "add-expense") {
      if (!data.name) return;
      await api("/api/finance/expenses", { method: "POST", body: JSON.stringify({ name: data.name, amount: parseFloat(data.amount) || 0, interval: data.interval, category: data.category }) });
      toast("Kostenposten hinzugefügt 💶");
    } else if (kind === "add-maintenance") {
      if (!data.title) return;
      await api("/api/maintenance", { method: "POST", body: JSON.stringify({ title: data.title, category: data.category, interval_days: data.interval_days ? parseInt(data.interval_days, 10) : null }) });
      toast("Wartungsplan angelegt 🔧");
    } else if (kind === "add-media") {
      if (!data.query) return;
      const path = data.kind === "movie" ? "/api/media/movie" : "/api/media/series";
      const r = await api(path, { method: "POST", body: JSON.stringify({ query: data.query }) });
      toast(`„${r.title}" wird gesucht ⬇️`);
    } else if (kind === "admin-conn") {
      await api("/api/admin/settings", { method: "PUT", body: JSON.stringify({ values: data }) });
      toast("Verbindung gespeichert ✓");
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

/* ---------- Assistent (Chat mit Streaming) ---------- */
let chatBusy = false;

VIEWS.assistant = async function () {
  const v = $("#view");
  v.innerHTML = `
    <div class="chat">
      <div class="chat-head">
        <div class="ttl"><span class="logo">☿</span> Hermes AI <span class="chat-mode" id="chat-mode"></span></div>
        <button class="btn ghost" id="chat-new">Neuer Chat</button>
      </div>
      <div class="chat-msgs" id="chat-msgs"></div>
      <div class="chips" id="chat-chips"></div>
      <form class="chat-input" id="chat-form">
        <button type="button" class="icon-btn" id="chat-mic" title="Sprache">🎤</button>
        <input class="input" id="chat-text" placeholder="Frag Hermes … z.B. „Plane Spaghetti für morgen“" autocomplete="off">
        <button class="icon-btn primary" type="submit">➤</button>
      </form>
    </div>`;

  const box = $("#chat-msgs");
  const hist = await api("/api/ai/history").catch(() => []);
  if (!hist.length) {
    appendChatMsg("bot", "Hallo! Ich bin Hermes 👋 Ich kann Termine, Aufgaben, Einkäufe, Erinnerungen, Smart Home, Medien und mehr für dich steuern – frag einfach.");
    renderChatChips();
  } else {
    hist.forEach((m) => appendChatMsg(m.role === "user" ? "user" : "bot", m.content, m.actions));
  }
  api("/api/ai/status").then((s) => {
    $("#chat-mode").textContent = s.connected
      ? `· ${s.model || "Nous Hermes Agent"}`
      : (s.configured ? "· nicht erreichbar" : "· nicht verbunden");
  }).catch(() => {});

  $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
  $("#chat-mic").addEventListener("click", () => toggleVoiceRecording($("#chat-mic")));
  $("#chat-new").addEventListener("click", async () => {
    try { await api("/api/ai/history", { method: "DELETE" }); } catch (_) {}
    navigate("assistant");
  });
  setTimeout(() => { const t = $("#chat-text"); if (t) t.focus(); }, 100);
};

function appendChatMsg(role, text, actions) {
  const box = $("#chat-msgs");
  if (!box) return null;
  const m = document.createElement("div");
  m.className = "msg " + (role === "user" ? "user" : "bot");
  m.textContent = text;
  if (actions && actions.length) addChatActions(m, actions);
  box.appendChild(m);
  box.scrollTop = box.scrollHeight;
  return m;
}

function addChatActions(el, actions) {
  const a = document.createElement("div");
  a.className = "act";
  a.textContent = "🔧 " + actions.join(", ");
  el.appendChild(a);
}

function renderChatChips() {
  const chips = ["Was steht heute an?", "Plane Spaghetti für morgen", "Mach das Licht im Wohnzimmer an", "Erinnere mich jeden Dienstag 19 Uhr an den Müll", "Was läuft gerade?"];
  const c = $("#chat-chips");
  if (!c) return;
  c.innerHTML = chips.map((x) => `<button class="chip">${esc(x)}</button>`).join("");
  c.querySelectorAll(".chip").forEach((el) => el.addEventListener("click", () => { $("#chat-text").value = el.textContent; sendChat(); }));
}

async function sendChat() {
  if (chatBusy) return;
  const input = $("#chat-text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  const chips = $("#chat-chips"); if (chips) chips.innerHTML = "";
  appendChatMsg("user", text);
  const bot = appendChatMsg("bot", "");
  bot.classList.add("typing");
  chatBusy = true;

  try {
    const res = await fetch("/api/ai/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      credentials: "include",
      body: JSON.stringify({ message: text }),
    });
    if (res.status === 401) {
      if (await tryRefresh()) { chatBusy = false; input.value = text; return sendChat(); }
      location.href = "/login.html"; return;
    }
    if (!res.ok || !res.body) {
      // Fallback: nicht-gestreamt
      const r = await api("/api/ai/chat", { method: "POST", body: JSON.stringify({ message: text }) });
      bot.textContent = r.reply || "(keine Antwort)";
      if (r.actions && r.actions.length) addChatActions(bot, r.actions);
    } else {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "", full = "";
      bot.textContent = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) >= 0) {
          const line = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);
          if (!line.startsWith("data:")) continue;
          let ev; try { ev = JSON.parse(line.slice(5).trim()); } catch (_) { continue; }
          if (ev.type === "delta") { full += ev.text; bot.textContent = full; $("#chat-msgs").scrollTop = 1e9; }
          else if (ev.type === "done") { if (ev.actions && ev.actions.length) addChatActions(bot, ev.actions); }
          else if (ev.type === "error") { bot.textContent = "Fehler: " + ev.message; }
        }
      }
    }
  } catch (err) {
    bot.textContent = "Fehler: " + err.message;
  } finally {
    bot.classList.remove("typing");
    chatBusy = false;
  }
}

/* ---------- Voice-Messages (Aufnahme -> hermes-agent Transkription) ---------- */
let _mediaRecorder = null;
let _audioChunks = [];

async function toggleVoiceRecording(micBtn) {
  if (_mediaRecorder && _mediaRecorder.state === "recording") {
    _mediaRecorder.stop();
    return;
  }
  // Fallback: kein MediaRecorder -> Browser-Spracherkennung
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    startVoice($("#chat-text"), sendChat);
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    _audioChunks = [];
    _mediaRecorder = new MediaRecorder(stream);
    _mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) _audioChunks.push(e.data); };
    _mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      micBtn.textContent = "🎤";
      const blob = new Blob(_audioChunks, { type: (_mediaRecorder && _mediaRecorder.mimeType) || "audio/webm" });
      await uploadVoice(blob);
    };
    _mediaRecorder.start();
    micBtn.textContent = "⏹";
    toast("Aufnahme läuft … 🎙 erneut tippen zum Senden");
  } catch (err) {
    toast("Mikrofon nicht verfügbar");
  }
}

async function uploadVoice(blob, _retried) {
  const fd = new FormData();
  fd.append("audio", blob, "voice.webm");
  try {
    const res = await fetch("/api/ai/voice", { method: "POST", headers: { ...authHeader() }, credentials: "include", body: fd });
    if (res.status === 401 && !_retried) {
      if (await tryRefresh()) return uploadVoice(blob, true);
      location.href = "/login.html"; return;
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({}));
      toast(e.detail || "Transkription fehlgeschlagen");
      return;
    }
    const { text } = await res.json();
    if (text) { $("#chat-text").value = text; sendChat(); }
    else toast("Nichts erkannt");
  } catch (err) {
    toast("Voice-Fehler: " + err.message);
  }
}

/* ---------- Voice (Web Speech API, Fallback) ---------- */
function startVoice(targetInput, onDone) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { toast("Spracheingabe nicht unterstützt"); return; }
  const rec = new SR();
  rec.lang = "de-DE";
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  rec.onresult = (e) => {
    if (targetInput) targetInput.value = e.results[0][0].transcript;
    if (onDone) onDone();
  };
  rec.onerror = () => toast("Spracheingabe fehlgeschlagen");
  try { rec.start(); } catch (_) {}
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
