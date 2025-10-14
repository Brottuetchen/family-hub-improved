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
            const response = await fetch(`${API_BASE_URL}/api/push/admin/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || 'Fehler beim Senden');
            }

            pushStatus.textContent = `✅ Nachricht erfolgreich an ${result.success} von ${result.total_subscriptions} Geräten gesendet.`;
            pushStatus.style.background = 'rgba(16, 185, 129, 0.1)'; // Success color
            pushStatus.style.color = 'var(--color-success)';
            pushForm.reset();

        } catch (error) {
            pushStatus.textContent = `❌ Fehler: ${error.message}`;
            pushStatus.style.background = 'rgba(239, 68, 68, 0.1)'; // Error color
            pushStatus.style.color = 'var(--color-error)';
        }
    });
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

            const endpoint = document.createElement('div');
            endpoint.className = 'subscription-item__endpoint';
            endpoint.textContent = sub.endpoint;

            const deleteButton = document.createElement('button');
            deleteButton.className = 'btn btn--danger';
            deleteButton.textContent = 'Löschen';

            deleteButton.addEventListener('click', () => {
                if (!confirm('Möchten Sie dieses Abonnement wirklich löschen?')) return;

                showStatus('Lösche Abonnement...');
                fetch(`${API_BASE_URL}/api/push/subscriptions/${sub.id}`, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Fehler beim Löschen des Abonnements.');
                    }
                    return response.json();
                })
                .then(data => {
                    showStatus('✅ Abonnement gelöscht.', false);
                    item.remove();
                })
                .catch(error => {
                    showStatus(`❌ ${error.message}`, true);
                });
            });

            item.appendChild(endpoint);
            item.appendChild(deleteButton);
            subList.appendChild(item);
        });
    };

    const loadSubscriptions = async () => {
        showStatus('Lade Abonnements...');
        try {
            const response = await fetch(`${API_BASE_URL}/api/push/subscriptions`);
            if (!response.ok) {
                throw new Error('Fehler beim Laden der Abonnements.');
            }
            const subscriptions = await response.json();
            renderSubscriptions(subscriptions);
            showStatus(`✅ ${subscriptions.length} Abonnements geladen.`, false);
        } catch (error) {
            showStatus(`❌ ${error.message}`, true);
        }
    };

    loadButton.addEventListener('click', loadSubscriptions);
}

document.addEventListener('DOMContentLoaded', () => {
    initPushForm();
    initSubscriptionManagement();
});