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

document.addEventListener('DOMContentLoaded', () => {
    initPushForm();
});