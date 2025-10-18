// Family Hub - Admin Logic

const API_BASE_URL = window.location.origin;
let CURRENT_ADMIN_USER = null;

function initPushForm() {
    const pushForm = document.getElementById('pushForm');
    const pushStatus = document.getElementById('pushStatus');

    if (!pushForm || !pushStatus) return;

    pushForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(pushForm);
        const title = formData.get('title');
        const body = formData.get('body');
        const url = formData.get('url') || '/';

        const payload = { title, body, url };

        // Visuelles Feedback
        pushStatus.style.display = 'block';
        pushStatus.textContent = 'Sende Nachricht...';
        pushStatus.style.background = 'rgba(245, 158, 11, 0.1)'; // Warning color
        pushStatus.style.color = 'var(--color-warning)';

        // Disable submit to prevent double send
        const submitBtn = pushForm.querySelector('button[type="submit"]');
        const prevDisabled = submitBtn?.disabled;
        if (submitBtn) {
            submitBtn.disabled = true;
        }

        try {
            const response = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/push/admin/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            let result;
            const ct = response.headers.get('content-type') || '';
            if (ct.includes('application/json')) {
                result = await response.json();
            } else {
                const text = await response.text();
                if (!response.ok) {
                    throw new Error(text || `HTTP ${response.status}`);
                }
                result = { message: text };
            }

            if (!response.ok) {
                throw new Error(result.detail || result.message || 'Fehler beim Senden');
            }

            pushStatus.textContent = `✅ Nachricht erfolgreich an ${result.success} von ${result.total_subscriptions} Geräten gesendet.`;
            pushStatus.style.background = 'rgba(16, 185, 129, 0.1)'; // Success color
            pushStatus.style.color = 'var(--color-success)';
            pushForm.reset();

        } catch (error) {
            pushStatus.textContent = `⚠️ Fehler: ${error.message}`;
            pushStatus.style.background = 'rgba(239, 68, 68, 0.1)'; // Error color
            pushStatus.style.color = 'var(--color-error)';
        }
        finally {
            if (submitBtn) {
                submitBtn.disabled = !!prevDisabled ? prevDisabled : false;
            }
        }
    });
}

function formatEndpoint(endpoint) {
    if (endpoint.length > 80) {
        return `${endpoint.substring(0, 40)}...${endpoint.substring(endpoint.length - 40)}`;
    }
    return endpoint;
}

function initSubscriptionManagement() {
    const loadButton = document.getElementById('loadSubscriptions');
    const subList = document.getElementById('subscriptionList');
    const subStatus = document.getElementById('subscriptionStatus');

    if (!loadButton || !subList || !subStatus) return;

    const showStatus = (message, isError = false) => {
        subStatus.textContent = message;
        subStatus.style.display = 'block';
        subStatus.style.background = isError ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)';
        subStatus.style.color = isError ? 'var(--color-error)' : 'var(--color-success)';
    };

    const renderSubscriptions = (subscriptions) => {
        subList.innerHTML = '';
        if (subscriptions.length === 0) {
            subList.innerHTML = '<p>Keine Abonnements gefunden.</p>';
            return;
        }

        subscriptions.forEach(sub => {
            const item = document.createElement('div');
            item.className = 'subscription-item';
            item.dataset.id = sub.id;

            const endpointWrapper = document.createElement('div');
            endpointWrapper.className = 'subscription-item__endpoint-wrapper';

            const endpoint = document.createElement('div');
            endpoint.className = 'subscription-item__endpoint';
            endpoint.textContent = formatEndpoint(sub.endpoint);
            endpoint.title = sub.endpoint;

            const copyButton = document.createElement('button');
            copyButton.className = 'btn btn--secondary btn--small';
            copyButton.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
            copyButton.onclick = () => {
                navigator.clipboard.writeText(sub.endpoint);
                const originalText = copyButton.innerHTML;
                copyButton.innerHTML = 'Copied!';
                setTimeout(() => {
                    copyButton.innerHTML = originalText;
                }, 2000);
            };

            endpointWrapper.appendChild(endpoint);
            endpointWrapper.appendChild(copyButton);

            const deleteButton = document.createElement('button');
            deleteButton.className = 'btn btn--secondary';
            deleteButton.textContent = 'Löschen';

            deleteButton.addEventListener('click', () => {
                if (!confirm('Möchten Sie dieses Abonnement wirklich löschen?')) return;

                showStatus('Lösche Abonnement...');
                window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/push/subscriptions/${sub.id}`, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Fehler beim Löschen des Abonnements.');
                    }
                    return response.json();
                })
                .then(() => {
                    showStatus('✅ Abonnement gelöscht.', false);
                    item.remove();
                })
                .catch(error => {
                    showStatus(`⚠️ ${error.message}`, true);
                });
            });

            item.appendChild(endpointWrapper);
            item.appendChild(deleteButton);
            subList.appendChild(item);
        });
    };

    const loadSubscriptions = async () => {
        showStatus('Lade Abonnements...');
        try {
            const response = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/push/subscriptions`);
            if (!response.ok) {
                throw new Error('Fehler beim Laden der Abonnements.');
            }
            const subscriptions = await response.json();
            renderSubscriptions(subscriptions);
            showStatus(`✅ ${subscriptions.length} Abonnements geladen.`, false);
        } catch (error) {
            showStatus(`⚠️ ${error.message}`, true);
        }
    };

    loadButton.addEventListener('click', loadSubscriptions);
}

// === USER MANAGEMENT ===

function formatDateTime(value) {
    try {
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return '';
        return new Intl.DateTimeFormat('de-DE', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
        }).format(d);
    } catch {
        return '';
    }
}

function initUserManagement() {
    const form = document.getElementById('userCreateForm');
    const statusEl = document.getElementById('userStatus');
    const listEl = document.getElementById('userList');
    const loadBtn = document.getElementById('loadUsers');

    if (!form || !statusEl || !listEl || !loadBtn) return;

    const renderUsers = (users) => {
        listEl.innerHTML = '';
        if (!Array.isArray(users) || users.length === 0) {
            listEl.innerHTML = '<li class="placeholder">Keine Benutzer gefunden.</li>';
            return;
        }

        users.forEach((user) => {
            const li = document.createElement('li');
            li.className = 'newsletter-list__item';

            const title = document.createElement('div');
            title.className = 'newsletter-list__title';
            title.innerHTML = `
                <span>${user.username}</span>
                <span class="newsletter-list__badges">
                    ${user.is_admin ? '<span class="badge">Admin</span>' : ''}
                </span>
            `;

            const meta = document.createElement('div');
            meta.className = 'newsletter-list__meta';
            const email = user.email ? ` | ${user.email}` : '';
            const created = user.created_at ? `• angelegt: ${formatDateTime(user.created_at)}` : '';
            const lastLogin = user.last_login ? `• letzter Login: ${formatDateTime(user.last_login)}` : '';
            meta.textContent = `${user.full_name || ''}${email} ${created} ${lastLogin}`.trim();

            const actions = document.createElement('div');
            actions.style.marginTop = '8px';
            actions.style.display = 'flex';
            actions.style.gap = '8px';
            actions.style.flexWrap = 'wrap';

            // Admin toggle
            const adminWrap = document.createElement('label');
            adminWrap.style.display = 'inline-flex';
            adminWrap.style.alignItems = 'center';
            adminWrap.style.gap = '6px';
            const adminCb = document.createElement('input');
            adminCb.type = 'checkbox';
            adminCb.checked = !!user.is_admin;
            if (CURRENT_ADMIN_USER && CURRENT_ADMIN_USER.id === user.id) {
                adminCb.disabled = true;
                adminWrap.title = 'Eigene Admin-Rechte können nicht entfernt werden';
            }
            const adminLbl = document.createElement('span');
            adminLbl.textContent = 'Admin';
            adminWrap.appendChild(adminCb);
            adminWrap.appendChild(adminLbl);

            adminCb.addEventListener('change', async () => {
                const desired = adminCb.checked;
                try {
                    const resp = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/auth/users/${user.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ is_admin: desired })
                    });
                    if (!resp.ok) {
                        const t = await resp.text();
                        throw new Error(t || `HTTP ${resp.status}`);
                    }
                    statusEl.textContent = `✅ Admin-Recht ${desired ? 'gesetzt' : 'entfernt'} für ${user.username}`;
                    statusEl.style.display = 'block';
                    statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
                    statusEl.style.color = 'var(--color-success)';
                } catch (e) {
                    adminCb.checked = !desired; // revert
                    statusEl.textContent = `⚠️ Fehler: ${e.message}`;
                    statusEl.style.display = 'block';
                    statusEl.style.background = 'rgba(239, 68, 68, 0.1)';
                    statusEl.style.color = 'var(--color-error)';
                }
            });

            // Active toggle
            const activeWrap = document.createElement('label');
            activeWrap.style.display = 'inline-flex';
            activeWrap.style.alignItems = 'center';
            activeWrap.style.gap = '6px';
            const activeCb = document.createElement('input');
            activeCb.type = 'checkbox';
            activeCb.checked = !!user.is_active;
            if (CURRENT_ADMIN_USER && CURRENT_ADMIN_USER.id === user.id) {
                activeCb.disabled = true;
                activeWrap.title = 'Eigener Account kann nicht deaktiviert werden';
            }
            const activeLbl = document.createElement('span');
            activeLbl.textContent = 'Aktiv';
            activeWrap.appendChild(activeCb);
            activeWrap.appendChild(activeLbl);

            activeCb.addEventListener('change', async () => {
                const desired = activeCb.checked;
                try {
                    const resp = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/auth/users/${user.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ is_active: desired })
                    });
                    if (!resp.ok) {
                        const t = await resp.text();
                        throw new Error(t || `HTTP ${resp.status}`);
                    }
                    statusEl.textContent = `✅ Benutzer ${desired ? 'aktiviert' : 'deaktiviert'}: ${user.username}`;
                    statusEl.style.display = 'block';
                    statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
                    statusEl.style.color = 'var(--color-success)';
                } catch (e) {
                    activeCb.checked = !desired; // revert
                    statusEl.textContent = `⚠️ Fehler: ${e.message}`;
                    statusEl.style.display = 'block';
                    statusEl.style.background = 'rgba(239, 68, 68, 0.1)';
                    statusEl.style.color = 'var(--color-error)';
                }
            });

            const delBtn = document.createElement('button');
            delBtn.className = 'btn btn--secondary';
            delBtn.textContent = 'Löschen';
            if (CURRENT_ADMIN_USER && CURRENT_ADMIN_USER.id === user.id) {
                delBtn.disabled = true;
                delBtn.title = 'Eigener Account kann nicht gelöscht werden';
            }
            delBtn.addEventListener('click', async () => {
                if (!confirm(`Benutzer ${user.username} wirklich löschen?`)) return;
                statusEl.style.display = 'block';
                statusEl.textContent = 'Lösche Benutzer...';
                statusEl.style.background = 'rgba(245, 158, 11, 0.1)';
                statusEl.style.color = 'var(--color-warning)';
                try {
                    const resp = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/auth/users/${user.id}`, { method: 'DELETE' });
                    if (!resp.ok) {
                        const t = await resp.text();
                        throw new Error(t || `HTTP ${resp.status}`);
                    }
                    li.remove();
                    statusEl.textContent = '✅ Benutzer gelöscht';
                    statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
                    statusEl.style.color = 'var(--color-success)';
                } catch (e) {
                    statusEl.textContent = `⚠️ Fehler: ${e.message}`;
                    statusEl.style.background = 'rgba(239, 68, 68, 0.1)';
                    statusEl.style.color = 'var(--color-error)';
                }
            });

            // Reset password button
            const resetBtn = document.createElement('button');
            resetBtn.className = 'btn btn--secondary';
            resetBtn.textContent = 'Passwort setzen…';
            resetBtn.addEventListener('click', async () => {
                const pwd = window.prompt(`Neues Passwort für ${user.username}:`);
                if (!pwd) return;
                statusEl.style.display = 'block';
                statusEl.textContent = 'Setze Passwort...';
                statusEl.style.background = 'rgba(245, 158, 11, 0.1)';
                statusEl.style.color = 'var(--color-warning)';
                try {
                    const resp = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/auth/users/${user.id}/reset-password`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ new_password: pwd })
                    });
                    if (!resp.ok) {
                        const t = await resp.text();
                        throw new Error(t || `HTTP ${resp.status}`);
                    }
                    statusEl.textContent = `✅ Passwort gesetzt für ${user.username}`;
                    statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
                    statusEl.style.color = 'var(--color-success)';
                } catch (e) {
                    statusEl.textContent = `⚠️ Fehler: ${e.message}`;
                    statusEl.style.background = 'rgba(239, 68, 68, 0.1)';
                    statusEl.style.color = 'var(--color-error)';
                }
            });

            actions.appendChild(adminWrap);
            actions.appendChild(activeWrap);
            actions.appendChild(resetBtn);
            actions.appendChild(delBtn);

            li.appendChild(title);
            li.appendChild(meta);
            li.appendChild(actions);
            listEl.appendChild(li);
        });
    };

    const loadUsers = async () => {
        statusEl.style.display = 'block';
        statusEl.textContent = 'Lade Benutzer...';
        statusEl.style.background = 'rgba(245, 158, 11, 0.1)';
        statusEl.style.color = 'var(--color-warning)';
        try {
            const resp = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/auth/users`);
            if (!resp.ok) {
                const t = await resp.text();
                throw new Error(t || `HTTP ${resp.status}`);
            }
            const users = await resp.json();
            renderUsers(users);
            statusEl.textContent = `✅ ${users.length} Benutzer geladen`;
            statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
            statusEl.style.color = 'var(--color-success)';
        } catch (e) {
            statusEl.textContent = `⚠️ Fehler: ${e.message}`;
            statusEl.style.background = 'rgba(239, 68, 68, 0.1)';
            statusEl.style.color = 'var(--color-error)';
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const payload = {
            username: fd.get('username'),
            email: fd.get('email'),
            password: fd.get('password'),
            full_name: fd.get('full_name') || null,
            is_admin: fd.get('is_admin') === 'on',
        };

        statusEl.style.display = 'block';
        statusEl.textContent = 'Lege Benutzer an...';
        statusEl.style.background = 'rgba(245, 158, 11, 0.1)';
        statusEl.style.color = 'var(--color-warning)';

        const submitBtn = form.querySelector('button[type="submit"]');
        const prevDisabled = submitBtn?.disabled;
        if (submitBtn) submitBtn.disabled = true;

        try {
            const resp = await window.AuthUtils.authenticatedFetch(`${API_BASE_URL}/api/auth/users`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const ct = resp.headers.get('content-type') || '';
            const data = ct.includes('application/json') ? await resp.json() : await resp.text();
            if (!resp.ok) {
                throw new Error((data && data.detail) || (typeof data === 'string' ? data : 'Fehler beim Anlegen'));
            }
            statusEl.textContent = `✅ Benutzer ${data.username || payload.username} angelegt`;
            statusEl.style.background = 'rgba(16, 185, 129, 0.1)';
            statusEl.style.color = 'var(--color-success)';
            form.reset();
            await loadUsers();
        } catch (e) {
            statusEl.textContent = `⚠️ Fehler: ${e.message}`;
            statusEl.style.background = 'rgba(239, 68, 68, 0.1)';
            statusEl.style.color = 'var(--color-error)';
        } finally {
            if (submitBtn) submitBtn.disabled = !!prevDisabled ? prevDisabled : false;
        }
    });

    loadBtn.addEventListener('click', loadUsers);

    // Auto-load initially
    loadUsers();
}

document.addEventListener('DOMContentLoaded', async () => {
    // Require authentication and admin role for this page
    try {
        const isAuth = await window.AuthUtils.requireAuth();
        if (!isAuth) {
            return; // redirected to login
        }

        const user = await window.AuthUtils.getCurrentUser();
        CURRENT_ADMIN_USER = user;
        if (!user || !user.is_admin) {
            alert('Admin-Rechte erforderlich.');
            window.location.href = '/index.html';
            return;
        }
    } catch (e) {
        console.error('Auth guard failed:', e);
        window.location.href = '/login.html';
        return;
    }

    initPushForm();
    initSubscriptionManagement();
    initUserManagement();
});
