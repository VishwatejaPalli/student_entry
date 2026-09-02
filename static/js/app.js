/**
 * App.js — Shared utilities for the Room Entry System
 */

// ── Theme Management (Segmented Switch) ─────────────────────────

function setAppTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (document.body) {
        document.body.setAttribute('data-theme', theme);
    }
    localStorage.setItem('theme', theme);

    const lightBtn = document.getElementById('themeSegLight');
    const darkBtn = document.getElementById('themeSegDark');
    if (lightBtn && darkBtn) {
        if (theme === 'light') {
            lightBtn.classList.add('active');
            darkBtn.classList.remove('active');
        } else {
            darkBtn.classList.add('active');
            lightBtn.classList.remove('active');
        }
    }
}

function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    if (document.body) {
        document.body.setAttribute('data-theme', saved);
    }
    setAppTheme(saved);
}

// Run theme init immediately
initTheme();
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
});


// ── Toast Notifications ─────────────────────────────────────────

function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()" style="display: inline-flex; align-items: center; justify-content: center;"><span class="material-symbols-outlined" style="font-size: 1.1rem;">close</span></button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}


// ── API Helpers ──────────────────────────────────────────────────

async function apiCall(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(url, options);
        let data;
        const text = await response.text();
        try {
            data = text ? JSON.parse(text) : {};
        } catch {
            data = { error: text || `HTTP ${response.status} ${response.statusText}` };
        }

        if (!response.ok) {
            throw new Error(data.error || data.detail || data.message || `HTTP ${response.status}`);
        }
        return data;
    } catch (err) {
        showToast(err.message, 'error');
        throw err;
    }
}

async function apiUpload(url, file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
        });
        let data;
        const text = await response.text();
        try {
            data = text ? JSON.parse(text) : {};
        } catch {
            data = { error: text || `HTTP ${response.status} ${response.statusText}` };
        }

        if (!response.ok) {
            throw new Error(data.error || data.detail || data.message || `HTTP ${response.status}`);
        }
        return data;
    } catch (err) {
        showToast(err.message, 'error');
        throw err;
    }
}


// ── Modal Helpers ───────────────────────────────────────────────

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Close modal on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    }
});


// ── Date/Time Defaults ──────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initTheme();

    // Auto-set date fields with data-default-today="true"
    document.querySelectorAll('[data-default-today="true"]').forEach(input => {
        if (!input.value) {
            input.value = new Date().toISOString().split('T')[0];
        }
    });

    // Auto-set time fields with data-default-now="true"
    document.querySelectorAll('[data-default-now="true"]').forEach(input => {
        if (!input.value) {
            const now = new Date();
            input.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
        }
    });
});


// ── Utility ─────────────────────────────────────────────────────

function formatDuration(minutes) {
    if (!minutes && minutes !== 0) return '—';
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

function formatTime(isoStr) {
    if (!isoStr) return '—';
    return isoStr.substring(11, 16);
}

function formatDate(isoStr) {
    if (!isoStr) return '—';
    return isoStr.substring(0, 10);
}
