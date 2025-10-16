// Family Hub - Admin Logic

const API_BASE_URL = window.location.origin;

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
            deleteButton.className = 'btn btn--danger';
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

document.addEventListener('DOMContentLoaded', () => {
    initPushForm();
    initSubscriptionManagement();
});

