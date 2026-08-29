/**
 * Dashboard.js — Live dashboard logic
 *
 * Features:
 *   - Auto-refresh stats every 30 seconds
 *   - Quick entry/exit from dashboard
 *   - Record detail expansion
 *   - Filtering
 */

let refreshTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    // Start auto-refresh
    startAutoRefresh();

    // Quick entry on Enter key
    document.getElementById('quickRollNo')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            quickEntry();
        }
    });
});

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(refreshDashboard, 30000);
}

async function refreshDashboard() {
    try {
        const stats = await apiCall('/api/dashboard/stats');
        const insideEl = document.getElementById('statInside');
        const todayEl = document.getElementById('statToday');

        if (insideEl) insideEl.textContent = stats.currently_inside;
        if (todayEl) todayEl.textContent = stats.today_visits;

        // Refresh records table
        await refreshRecords();
    } catch (err) {
        // Silently fail on auto-refresh
    }
}

async function refreshRecords() {
    const params = getFilterParams();
    try {
        const result = await apiCall(`/api/dashboard/records?${params}`);
        renderRecords(result.records);

        const totalEl = document.getElementById('totalRecords');
        if (totalEl) totalEl.textContent = `${result.total} total`;
    } catch (err) {
        // Silent
    }
}

function getFilterParams() {
    const params = new URLSearchParams();
    const rollNo = document.getElementById('filterRollNo')?.value;
    const dateFrom = document.getElementById('filterDateFrom')?.value;
    const dateTo = document.getElementById('filterDateTo')?.value;

    if (rollNo) params.set('roll_no', rollNo);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    params.set('per_page', '50');

    return params.toString();
}

function renderRecords(records) {
    const tbody = document.getElementById('recordsBody');
    if (!tbody) return;

    if (records.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="8">
                <div class="empty-state">
                    <div class="icon">📋</div>
                    <p>No records found.</p>
                </div>
            </td></tr>`;
        return;
    }

    let html = '';
    for (const r of records) {
        const status = r.exit_time ? 'OUT' : 'IN';
        const badgeClass = status === 'IN' ? 'badge--in' : 'badge--out';
        const duration = r.duration_minutes ? `${r.duration_minutes} min` : '—';

        html += `
        <tr class="clickable" data-record-id="${r.id}">
            <td><strong>${r.roll_no}</strong></td>
            <td>${r.student_name || '—'}</td>
            <td>${formatDate(r.entry_time)}</td>
            <td>${formatTime(r.entry_time)}</td>
            <td>${formatTime(r.exit_time)}</td>
            <td>${duration}</td>
            <td><span class="badge ${badgeClass}">${status}</span></td>
            <td><button class="btn btn-ghost btn-sm" data-toggle-detail="${r.id}">▾</button></td>
        </tr>`;

        if (r.custom_fields && Object.keys(r.custom_fields).length > 0) {
            html += `
            <tr class="detail-row hidden" id="detail-${r.id}">
                <td colspan="8">
                    <div class="detail-panel">
                        <div class="detail-grid">`;
            for (const [label, value] of Object.entries(r.custom_fields)) {
                html += `
                            <div class="detail-item">
                                <span class="detail-label">${label}</span>
                                <span class="detail-value">${value || '—'}</span>
                            </div>`;
            }
            html += `
                        </div>
                    </div>
                </td>
            </tr>`;
        }
    }

    tbody.innerHTML = html;
}

function toggleDetail(recordId, event) {
    if (event) event.stopPropagation();
    const detailRow = document.getElementById(`detail-${recordId}`);
    if (detailRow) {
        detailRow.classList.toggle('hidden');
    }
}

// ── Delegated event listener for record detail expansion ────────

document.addEventListener('click', (e) => {
    const toggleBtn = e.target.closest('[data-toggle-detail]');
    if (toggleBtn) {
        e.preventDefault();
        e.stopPropagation();
        toggleDetail(toggleBtn.dataset.toggleDetail);
    }
});

async function quickEntry() {
    const input = document.getElementById('quickRollNo');
    const rollNo = input?.value.trim();
    if (!rollNo) {
        showToast('Enter a roll number', 'error');
        return;
    }

    try {
        const result = await apiCall('/api/identify', 'POST', { roll_no: rollNo });

        if (result.is_inside) {
            showToast(`${result.roll_no} is already inside. Use Exit instead.`, 'info');
        } else {
            // Redirect to entry form
            window.location.href = `/entry/form/${encodeURIComponent(rollNo)}`;
        }
    } catch (err) {
        // Error toast shown by apiCall
    }
}

async function quickExit() {
    const input = document.getElementById('quickRollNo');
    const rollNo = input?.value.trim();
    if (!rollNo) {
        showToast('Enter a roll number', 'error');
        return;
    }

    try {
        const result = await apiCall('/api/exit', 'POST', { roll_no: rollNo });
        showToast(result.message, 'success');
        input.value = '';
        input.focus();
        refreshDashboard();
    } catch (err) {
        // Error toast shown by apiCall
    }
}

function applyFilters() {
    refreshRecords();
}

function clearFilters() {
    document.getElementById('filterRollNo').value = '';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    refreshRecords();
}
