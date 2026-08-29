/**
 * Sessions.js — Class Sessions Hub & Bulk Entry logic
 *
 * Features:
 *   - Live Class creation vs Immediate Bulk logging
 *   - 3 student selection modes: Class roster, Excel upload, Multiline Paste
 *   - Auto PC assignment configuration
 *   - Session history
 */

let classesData = [];
let selectedStudentsSet = new Set();
let currentSelectionMode = 'class'; // 'class', 'excel', 'paste'

document.addEventListener('DOMContentLoaded', () => {
    // Load embedded classes data
    const jsonEl = document.getElementById('classesJsonData');
    if (jsonEl) {
        try {
            classesData = JSON.parse(jsonEl.textContent || '[]');
        } catch (e) {
            classesData = [];
        }
    }

    // Set default date & times
    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];
    const dateInput = document.getElementById('sessionDate');
    if (dateInput && !dateInput.value) dateInput.value = todayStr;

    const startInput = document.getElementById('sessionStartTime');
    const endInput = document.getElementById('sessionEndTime');
    if (startInput && !startInput.value) {
        const h = String(now.getHours()).padStart(2, '0');
        startInput.value = `${h}:00`;
    }
    if (endInput && !endInput.value) {
        const endH = String((now.getHours() + 2) % 24).padStart(2, '0');
        endInput.value = `${endH}:00`;
    }

    // Setup Drag and Drop
    setupDropzone();

    // Form submit listener
    const form = document.getElementById('createSessionForm');
    if (form) {
        form.addEventListener('submit', handleSessionSubmit);
    }
});


// ── Tab Switching (Live vs Bulk vs History) ──────────────────────

function switchSessionTab(tab) {
    const liveBtn = document.getElementById('tabLiveBtn');
    const bulkBtn = document.getElementById('tabBulkBtn');
    const historyBtn = document.getElementById('tabHistoryBtn');
    const formCard = document.getElementById('sessionFormCard');
    const historyCard = document.getElementById('sessionHistoryCard');
    const isCompletedBulkInput = document.getElementById('isCompletedBulk');

    const liveBadge = document.getElementById('liveBadge');
    const bulkBadge = document.getElementById('bulkBadge');
    const liveSubmit = document.getElementById('liveSubmitGroup');
    const bulkSubmit = document.getElementById('bulkSubmitGroup');
    const lateGroup = document.getElementById('lateThresholdGroup');

    // Reset button states
    liveBtn?.classList.remove('active');
    bulkBtn?.classList.remove('active');
    historyBtn?.classList.remove('active');

    if (tab === 'history') {
        historyBtn?.classList.add('active');
        formCard?.classList.add('hidden');
        historyCard?.classList.remove('hidden');
        return;
    }

    formCard?.classList.remove('hidden');
    historyCard?.classList.add('hidden');

    if (tab === 'live') {
        liveBtn?.classList.add('active');
        if (isCompletedBulkInput) isCompletedBulkInput.value = 'false';
        liveBadge?.classList.remove('hidden');
        bulkBadge?.classList.add('hidden');
        liveSubmit?.classList.remove('hidden');
        bulkSubmit?.classList.add('hidden');
        lateGroup?.classList.remove('hidden');
        document.getElementById('formTitle').textContent = '1. Live Class Details';
    } else if (tab === 'bulk') {
        bulkBtn?.classList.add('active');
        if (isCompletedBulkInput) isCompletedBulkInput.value = 'true';
        liveBadge?.classList.add('hidden');
        bulkBadge?.classList.remove('hidden');
        liveSubmit?.classList.add('hidden');
        bulkSubmit?.classList.remove('hidden');
        lateGroup?.classList.add('hidden');
        document.getElementById('formTitle').textContent = '1. Completed Class Details';
    }
}


// ── Student Selection Sub-Tabs ───────────────────────────────────

function switchStudentTab(mode) {
    currentSelectionMode = mode;
    document.querySelectorAll('.sub-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.selector-pane').forEach(p => p.classList.add('hidden'));

    if (mode === 'class') {
        document.getElementById('subTabClass')?.classList.add('active');
        document.getElementById('paneClass')?.classList.remove('hidden');
    } else if (mode === 'excel') {
        document.getElementById('subTabExcel')?.classList.add('active');
        document.getElementById('paneExcel')?.classList.remove('hidden');
    } else if (mode === 'paste') {
        document.getElementById('subTabPaste')?.classList.add('active');
        document.getElementById('panePaste')?.classList.remove('hidden');
    }
}


// ── Class Roster Selection ───────────────────────────────────────

function loadClassStudents(className) {
    const grid = document.getElementById('rosterGrid');
    if (!grid) return;

    if (!className) {
        grid.innerHTML = `<div class="empty-state" style="padding: var(--space-lg); grid-column: 1 / -1;"><p class="text-muted">Select a class from the dropdown above to load students.</p></div>`;
        return;
    }

    const classObj = classesData.find(c => c.class_name === className);
    if (!classObj || !classObj.students.length) {
        grid.innerHTML = `<div class="empty-state" style="padding: var(--space-lg); grid-column: 1 / -1;"><p class="text-muted">No students found registered under ${className}.</p></div>`;
        return;
    }

    // Auto-fill session class & name if empty
    const classInput = document.getElementById('sessionClass');
    if (classInput && !classInput.value) classInput.value = className;

    const nameInput = document.getElementById('sessionName');
    if (nameInput && !nameInput.value) nameInput.value = `${className} Lab Session`;

    // Clear set and select all by default for this class
    selectedStudentsSet.clear();
    let html = '';

    for (const st of classObj.students) {
        selectedStudentsSet.add(st.roll_no);
        html += `
        <label class="roster-item-card selected" id="card-${st.roll_no}" onclick="toggleRosterItem('${st.roll_no}', event)">
            <input type="checkbox" value="${st.roll_no}" checked onclick="event.stopPropagation(); toggleRosterItem('${st.roll_no}')">
            <div class="roster-item-info">
                <span class="roster-item-roll">${st.roll_no}</span>
                <span class="roster-item-name">${st.name || '—'}</span>
            </div>
        </label>`;
    }

    grid.innerHTML = html;
    updateSelectedCount();
}

function toggleRosterItem(rollNo, event) {
    if (event && event.target.tagName === 'INPUT') return;

    const card = document.getElementById(`card-${rollNo}`);
    const cb = card ? card.querySelector('input[type="checkbox"]') : null;

    if (selectedStudentsSet.has(rollNo)) {
        selectedStudentsSet.delete(rollNo);
        if (card) card.classList.remove('selected');
        if (cb) cb.checked = false;
    } else {
        selectedStudentsSet.add(rollNo);
        if (card) card.classList.add('selected');
        if (cb) cb.checked = true;
    }

    updateSelectedCount();
}

function selectAllRoster(select) {
    const grid = document.getElementById('rosterGrid');
    if (!grid) return;

    grid.querySelectorAll('.roster-item-card').forEach(card => {
        const cb = card.querySelector('input[type="checkbox"]');
        const roll = cb?.value;
        if (roll) {
            if (select) {
                selectedStudentsSet.add(roll);
                card.classList.add('selected');
                if (cb) cb.checked = true;
            } else {
                selectedStudentsSet.delete(roll);
                card.classList.remove('selected');
                if (cb) cb.checked = false;
            }
        }
    });

    updateSelectedCount();
}

function filterRoster(query) {
    const q = query.trim().toUpperCase();
    const grid = document.getElementById('rosterGrid');
    if (!grid) return;

    grid.querySelectorAll('.roster-item-card').forEach(card => {
        const text = card.textContent.toUpperCase();
        if (!q || text.includes(q)) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}


// ── File Upload / Drag & Drop ────────────────────────────────────

function setupDropzone() {
    const dropzone = document.getElementById('fileDropzone');
    const fileInput = document.getElementById('bulkFileInput');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('drag-over');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) {
            handleFileSelect(e.dataTransfer.files);
        }
    });
}

async function handleFileSelect(files) {
    if (!files || !files.length) return;
    const file = files[0];
    const resultBox = document.getElementById('fileUploadResult');

    const formData = new FormData();
    formData.append('file', file);

    if (resultBox) {
        resultBox.classList.remove('hidden');
        resultBox.innerHTML = `<span class="text-secondary">⏳ Parsing ${file.name}...</span>`;
    }

    try {
        const response = await fetch('/api/sessions/parse-file', {
            method: 'POST',
            body: formData,
        });
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || 'Failed to parse file');

        selectedStudentsSet.clear();
        data.roll_numbers.forEach(r => selectedStudentsSet.add(r));

        if (resultBox) {
            resultBox.innerHTML = `
                <div class="flex items-center justify-between">
                    <div>
                        <strong class="text-success">✓ ${data.count} roll numbers parsed from ${file.name}</strong>
                        <div class="text-xs text-muted mt-xs">${data.roll_numbers.slice(0, 8).join(', ')}${data.count > 8 ? '...' : ''}</div>
                    </div>
                    <button type="button" class="btn btn-ghost btn-sm text-danger" onclick="clearUploadedFile()">Clear</button>
                </div>
            `;
        }
        updateSelectedCount();
        showToast(`${data.count} roll numbers loaded from file`, 'success');
    } catch (err) {
        if (resultBox) {
            resultBox.innerHTML = `<span class="text-danger">✕ Error: ${err.message}</span>`;
        }
        showToast(err.message, 'error');
    }
}

function clearUploadedFile() {
    selectedStudentsSet.clear();
    const resultBox = document.getElementById('fileUploadResult');
    if (resultBox) resultBox.classList.add('hidden');
    const input = document.getElementById('bulkFileInput');
    if (input) input.value = '';
    updateSelectedCount();
}


// ── Paste Roll Numbers ───────────────────────────────────────────

function parsePastedRolls(text) {
    if (currentSelectionMode !== 'paste') return;

    selectedStudentsSet.clear();
    const tokens = text.split(/[\n,;\s]+/).map(t => t.trim().toUpperCase()).filter(t => t.length >= 4);

    tokens.forEach(r => selectedStudentsSet.add(r));

    const statsEl = document.getElementById('pasteStats');
    if (statsEl) {
        statsEl.textContent = `${selectedStudentsSet.size} unique roll numbers detected`;
    }

    updateSelectedCount();
}


// ── Helpers ──────────────────────────────────────────────────────

function updateSelectedCount() {
    const badge = document.getElementById('selectedCountBadge');
    if (badge) {
        badge.textContent = selectedStudentsSet.size;
    }
}

function togglePcPrefix(strategy) {
    const prefixWrap = document.getElementById('pcPrefixWrapper');
    if (prefixWrap) {
        if (strategy === 'auto_sequential') {
            prefixWrap.style.display = 'flex';
        } else {
            prefixWrap.style.display = 'none';
        }
    }
}


// ── Submit Session ───────────────────────────────────────────────

async function handleSessionSubmit(e) {
    e.preventDefault();

    const isCompleted = document.getElementById('isCompletedBulk')?.value === 'true';
    const sessionName = document.getElementById('sessionName')?.value.trim();
    const className = document.getElementById('sessionClass')?.value.trim();
    const subject = document.getElementById('sessionSubject')?.value.trim();
    const room = document.getElementById('sessionRoom')?.value.trim();
    const faculty = document.getElementById('sessionFaculty')?.value.trim();
    const dateStr = document.getElementById('sessionDate')?.value;
    const startTimeStr = document.getElementById('sessionStartTime')?.value;
    const endTimeStr = document.getElementById('sessionEndTime')?.value;
    const lateThreshold = parseInt(document.getElementById('lateThreshold')?.value || '15');
    const pcStrategy = document.getElementById('pcStrategy')?.value || 'none';
    const pcPrefix = document.getElementById('pcPrefix')?.value.trim() || 'PC-';
    const bulkStatus = document.getElementById('bulkStatusSelect')?.value || 'PRESENT';

    if (!sessionName) {
        showToast('Please enter a Session Name', 'error');
        return;
    }

    if (!dateStr || !startTimeStr || !endTimeStr) {
        showToast('Please select Date, Start Time, and End Time', 'error');
        return;
    }

    const scheduledStart = `${dateStr}T${startTimeStr}:00`;
    const scheduledEnd = `${dateStr}T${endTimeStr}:00`;

    // Ensure we parse paste box if user is currently on paste tab
    if (currentSelectionMode === 'paste') {
        const pasteVal = document.getElementById('pasteRollNumbers')?.value || '';
        parsePastedRolls(pasteVal);
    }

    const studentRolls = Array.from(selectedStudentsSet);

    if (studentRolls.length === 0 && isCompleted) {
        showToast('Please select or paste at least one student for bulk entry', 'error');
        return;
    }

    const submitBtn = isCompleted ? document.getElementById('createBulkBtn') : document.getElementById('startLiveBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Processing...';
    }

    try {
        const payload = {
            session_name: sessionName,
            class_name: className,
            subject: subject,
            room: room,
            faculty: faculty,
            scheduled_start: scheduledStart,
            scheduled_end: scheduledEnd,
            late_threshold_min: lateThreshold,
            pc_strategy: pcStrategy,
            pc_prefix: pcPrefix,
            students: studentRolls,
            is_completed_bulk: isCompleted,
            bulk_status: bulkStatus,
        };

        const result = await apiCall('/api/sessions', 'POST', payload);
        showToast(result.message || 'Session created', 'success');

        setTimeout(() => {
            window.location.href = result.redirect_url || '/sessions';
        }, 600);
    } catch (err) {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = isCompleted ? '✓ Create & Finalize Bulk Records' : '⚡ Launch Live Scanner Cockpit →';
        }
    }
}
