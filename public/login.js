/* Hermes Family OS — Login */

const TOKEN_KEY = "hermes_token";
const form = document.getElementById("login-form");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.classList.add("show");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.classList.remove("show");
  submitBtn.disabled = true;
  submitBtn.textContent = "Anmelden …";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      let detail = "Anmeldung fehlgeschlagen";
      try { const j = await res.json(); detail = j.detail || detail; } catch (_) {}
      if (res.status === 429) detail = "Zu viele Versuche. Bitte später erneut versuchen.";
      showError(typeof detail === "string" ? detail : "Anmeldung fehlgeschlagen");
      return;
    }

    const data = await res.json();
    if (data.access_token) localStorage.setItem(TOKEN_KEY, data.access_token);
    location.href = "/";
  } catch (err) {
    showError("Verbindungsfehler. Läuft das Backend?");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Anmelden";
  }
});
