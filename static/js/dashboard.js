/**
 * Dashboard.js — Live occupancy roster, smart quick scan, and log filters
 */

let filterDebounceTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    // Auto-refresh occupancy every 15 seconds
    setInterval(refreshOccupancy, 15000);
});

// ── Smart Quick Scan (Auto-Toggles Entry vs Exit) ─────────────────

async function handleQuickScan(e) {
    if (e) e.preventDefault();

    const input = document.getElementById('quickRollNo');
    const btn = document.getElementById('quickScanBtn');
    const banner = document.getElementById('quickScanBanner');
    const rollNo = input?.value.trim().toUpperCase();

    if (!rollNo) return;

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Processing...';
    }

    try {
        const result = await apiCall('/api/dashboard/quick-scan', 'POST', { roll_no: rollNo });

        if (banner) {
            banner.classList.remove('hidden');
            const isEntry = result.action === 'ENTRY';
            banner.style.background = isEntry ? 'rgba(0, 230, 118, 0.12)' : 'rgba(255, 171, 64, 0.12)';
            banner.style.borderColor = isEntry ? 'var(--accent-success)' : 'var(--accent-warning)';
            banner.innerHTML = `
                <div class="flex items-center gap-sm">
                    <span class="material-symbols-outlined" style="color: ${isEntry ? 'var(--accent-success)' : 'var(--accent-warning)'}; font-size: 1.25rem;">${isEntry ? 'login' : 'logout'}</span>
                    <strong>${result.message}</strong>
                </div>`;

            setTimeout(() => {
                banner.classList.add('hidden');
            }, 5000);
        }

        showToast(result.message, 'success');

        if (input) {
            input.value = '';
            input.focus();
        }

        // Refresh stats & tables
        await refreshDashboard();
    } catch (err) {
        // Error shown by apiCall
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span class="material-symbols-outlined">flash_on</span><span>Instant Check In / Out</span>`;
        }
    }
}

async function checkOutStudent(rollNo) {
    try {
        const result = await apiCall('/api/exit', 'POST', { roll_no: rollNo });
        showToast(result.message || `Checked out ${rollNo}`, 'success');
        await refreshDashboard();
    } catch (err) {
        // Error handled
    }
}


// ── Dashboard Refresh ─────────────────────────────────────────────

async function refreshDashboard() {
    await Promise.all([
        refreshStats(),
        refreshOccupancy(),
        applyFilters(),
    ]);
}

async function refreshStats() {
    try {
        const stats = await apiCall('/api/dashboard/stats');
        const insideEl = document.getElementById('statInside');
        const todayEl = document.getElementById('statToday');
        const activeSessEl = document.getElementById('statActiveSessions');
        const totalStudEl = document.getElementById('statTotalStudents');

        if (insideEl) insideEl.textContent = stats.currently_inside;
        if (todayEl) todayEl.textContent = stats.today_visits;
        if (activeSessEl) activeSessEl.textContent = stats.active_sessions || 0;
        if (totalStudEl) totalStudEl.textContent = stats.total_students || 0;
    } catch (e) {
        console.error('Failed to refresh stats', e);
    }
}

async function refreshOccupancy() {
    try {
        const res = await apiCall('/api/dashboard/inside');
        const list = res.inside || [];
        const tbody = document.getElementById('insideTableBody');
        const countBadge = document.getElementById('insideCountBadge');

        if (countBadge) countBadge.textContent = list.length;

        if (!tbody) return;

        if (!list.length) {
            tbody.innerHTML = `
                <tr id="noInsideRow">
                    <td colspan="7">
                        <div class="empty-state" style="padding: var(--space-lg);">
                            <div class="icon"><span class="material-symbols-outlined" style="font-size: 3rem;">meeting_room</span></div>
                            <p class="text-muted">No students are currently inside the room.</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        let html = '';
        for (const st of list) {
            const batchBadge = st.batch ? `<span class="badge badge--batch">${st.batch}</span>` : `<span class="text-muted text-xs">—</span>`;
            html += `
            <tr id="inside-row-${st.roll_no}">
                <td><strong>${st.roll_no}</strong></td>
                <td>${st.student_name}</td>
                <td>${st.department || '—'}</td>
                <td>${batchBadge}</td>
                <td>${st.entry_time ? st.entry_time.slice(11, 16) : '—'}</td>
                <td>
                    <strong class="text-success">${st.duration_formatted}</strong>
                </td>
                <td style="text-align: right;">
                    <button type="button" class="btn btn-danger btn-sm" onclick="checkOutStudent('${st.roll_no}')" style="display: inline-flex; align-items: center; gap: 4px;">
                        <span class="material-symbols-outlined" style="font-size: 1rem;">logout</span>
                        <span>Check Out</span>
                    </button>
                </td>
            </tr>`;
        }
        tbody.innerHTML = html;
    } catch (e) {
        console.error('Failed to refresh occupancy', e);
    }
}


// ── Records Filtering ─────────────────────────────────────────────

function applyFiltersDebounced() {
    if (filterDebounceTimer) clearTimeout(filterDebounceTimer);
    filterDebounceTimer = setTimeout(applyFilters, 300);
}

async function applyFilters() {
    const rollNo = document.getElementById('filterRollNo')?.value.trim() || '';
    const dateFrom = document.getElementById('filterDateFrom')?.value || '';
    const dateTo = document.getElementById('filterDateTo')?.value || '';

    const params = new URLSearchParams();
    if (rollNo) params.append('roll_no', rollNo);
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);

    try {
        const result = await apiCall(`/api/dashboard/records?${params.toString()}`);
        renderRecordsTable(result.records);

        const totalEl = document.getElementById('totalRecords');
        if (totalEl) totalEl.textContent = `${result.total} total entries`;
    } catch (err) {
        // Handled
    }
}

function clearFilters() {
    const r = document.getElementById('filterRollNo');
    const df = document.getElementById('filterDateFrom');
    const dt = document.getElementById('filterDateTo');
    if (r) r.value = '';
    if (df) df.value = '';
    if (dt) dt.value = '';
    applyFilters();
}

function renderRecordsTable(records) {
    const tbody = document.getElementById('recordsBody');
    if (!tbody) return;

    if (!records || !records.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9">
                    <div class="empty-state">
                        <div class="icon"><span class="material-symbols-outlined" style="font-size: 3rem;">receipt_long</span></div>
                        <p>No records found matching filters.</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    let html = '';
    for (const r of records) {
        const hasCustom = r.custom_fields && Object.keys(r.custom_fields).length > 0;
        const statusBadge = r.status === 'IN'
            ? `<span class="badge badge--in">IN</span>`
            : `<span class="badge badge--out">OUT</span>`;

        const typeBadge = r.is_session
            ? `<span class="badge badge--batch" title="${r.session_name}" style="display: inline-flex; align-items: center; gap: 4px;"><span class="material-symbols-outlined" style="font-size: 0.9rem;">school</span><span>${r.session_name || 'Class Session'}</span></span>`
            : `<span class="badge badge--individual" style="background: rgba(85, 72, 235, 0.1); color: var(--accent-primary); border: 1px solid var(--border-accent); display: inline-flex; align-items: center; gap: 4px;"><span class="material-symbols-outlined" style="font-size: 0.9rem;">person</span><span>Individual</span></span>`;

        html += `
        <tr class="clickable" data-record-id="${r.id}">
            <td><strong>${r.roll_no}</strong></td>
            <td>${r.student_name || '—'}</td>
            <td>${typeBadge}</td>
            <td>${r.entry_time ? r.entry_time.slice(0, 10) : '—'}</td>
            <td>${r.entry_time ? r.entry_time.slice(11, 16) : '—'}</td>
            <td>${r.exit_time ? r.exit_time.slice(11, 16) : '—'}</td>
            <td>${r.duration_minutes ? r.duration_minutes + ' min' : '—'}</td>
            <td>${statusBadge}</td>
            <td>
                ${hasCustom ? `<button type="button" class="btn btn-ghost btn-sm" onclick="toggleDetailRow(${r.id})" title="View Details" style="display: inline-flex; align-items: center; justify-content: center;"><span class="material-symbols-outlined" style="font-size: 1.1rem;">expand_more</span></button>` : ''}
            </td>
        </tr>`;

        if (hasCustom) {
            html += `
            <tr class="detail-row hidden" id="detail-${r.id}">
                <td colspan="9">
                    <div class="detail-panel">
                        <div class="detail-grid">`;
            for (const [label, val] of Object.entries(r.custom_fields)) {
                html += `
                    <div class="detail-item">
                        <span class="detail-label">${label}</span>
                        <span class="detail-value">${val || '—'}</span>
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

function toggleDetailRow(recordId) {
    const row = document.getElementById(`detail-${recordId}`);
    if (row) {
        row.classList.toggle('hidden');
    }
}
