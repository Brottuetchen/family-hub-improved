// Service Viewer Logic - In-App Browser für Family Hub

const params = new URLSearchParams(window.location.search);
const serviceUrl = params.get('url');
const serviceName = params.get('name');

const serviceFrame = document.getElementById('serviceFrame');
const serviceTitle = document.getElementById('serviceTitle');
const loadingOverlay = document.getElementById('loadingOverlay');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');

// Timeout für Frame-Laden
let loadTimeout;

function initServiceViewer() {
    if (!serviceUrl || !serviceName) {
        showError('Ungültige URL oder Service-Name fehlt.');
        return;
    }

    // Decode und setze Titel
    serviceTitle.textContent = decodeURIComponent(serviceName);

    // Lade Service im iframe
    loadService(serviceUrl);

    // Event Listener für iframe load
    serviceFrame.addEventListener('load', handleFrameLoad);
    serviceFrame.addEventListener('error', handleFrameError);

    // Speichere letzten besuchten Service
    localStorage.setItem('lastService', JSON.stringify({
        name: serviceName,
        url: serviceUrl,
        timestamp: Date.now()
    }));
}

function loadService(url) {
    const decodedUrl = decodeURIComponent(url);

    // Zeige Loading
    loadingOverlay.classList.remove('hidden');
    errorMessage.classList.remove('visible');

    // Setze Timeout (10 Sekunden)
    clearTimeout(loadTimeout);
    loadTimeout = setTimeout(() => {
        showError('Service lädt zu lange. Bitte prüfe die Verbindung.');
    }, 10000);

    try {
        serviceFrame.src = decodedUrl;
    } catch (error) {
        showError(`Fehler beim Laden: ${error.message}`);
    }
}

function handleFrameLoad() {
    clearTimeout(loadTimeout);

    // Verstecke Loading nach kurzer Verzögerung
    setTimeout(() => {
        loadingOverlay.classList.add('hidden');
    }, 500);

    // Versuche Titel aus iframe zu lesen (nur bei same-origin)
    try {
        const frameTitle = serviceFrame.contentDocument?.title;
        if (frameTitle) {
            serviceTitle.textContent = frameTitle;
        }
    } catch (e) {
        // Cross-origin - ignorieren
    }
}

function handleFrameError() {
    clearTimeout(loadTimeout);
    showError('Service konnte nicht geladen werden. Möglicherweise blockiert der Service iframe-Einbettung.');
}

function showError(message) {
    loadingOverlay.classList.add('hidden');
    errorMessage.classList.add('visible');
    errorText.textContent = message;
}

function goBack() {
    // Versuche Browser-History
    if (window.history.length > 1) {
        window.history.back();
    } else {
        // Fallback: Zurück zur Homepage
        window.location.href = '/';
    }
}

function reloadService() {
    errorMessage.classList.remove('visible');
    loadService(serviceUrl);
}

// iOS Viewport Fix für Safari
function fixiOSViewport() {
    // Setze viewport height für mobile Safari
    const setVH = () => {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    };

    setVH();
    window.addEventListener('resize', setVH);
}

// Keyboard Shortcuts
document.addEventListener('keydown', (e) => {
    // ESC = Zurück
    if (e.key === 'Escape') {
        goBack();
    }

    // F5 oder Cmd/Ctrl+R = Reload
    if (e.key === 'F5' || (e.key === 'r' && (e.metaKey || e.ctrlKey))) {
        e.preventDefault();
        reloadService();
    }
});

// Initialisierung
document.addEventListener('DOMContentLoaded', () => {
    initServiceViewer();
    fixiOSViewport();
});

// Cleanup bei Seiten-Verlassen
window.addEventListener('beforeunload', () => {
    clearTimeout(loadTimeout);
});
