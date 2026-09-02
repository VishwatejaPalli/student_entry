/**
 * Sessions.js — Class Sessions Hub & Bulk Entry logic with direct Class & Semester Batch Selection
 *
 * Features:
 *   - Auto-loads initial class & batch pills on page load so batches are immediately visible
 *   - Fixed Semester Batch Partitioning (e.g. 70 students divided into 2 or 3 batches)
 *   - 1-Click Save to SQLite Semester Database
 *   - 2-way synchronization between Section 1 (Class/Batch inputs) and Section 2 (Roster & Batch Pills)
 *   - 1-Click Batch Filtering & Auto-Selection
 *   - Auto PC assignment configuration
 *   - Customizable session dynamic fields
 *   - Session history
 */

let classesData = [];
let selectedStudentsSet = new Set();
let currentSelectionMode = 'class'; // 'class', 'excel', 'paste'

let currentLoadedClass = null;
let currentActiveBatch = 'ALL';

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

    // Automatically select the first class (e.g. ECE-A) if available so batches and roster are immediately visible
    if (classesData.length > 0) {
        const firstClass = classesData.find(c => c.class_name !== 'General') || classesData[0];
        const classDropdown = document.getElementById('classDropdown');
        if (classDropdown) {
            classDropdown.value = firstClass.class_name;
        }
        loadClassStudents(firstClass.class_name);
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


// ── Two-Way Synchronized Inputs in Section 1 ─────────────────────

function onSessionClassInput(val) {
    const classObj = classesData.find(c => c.class_name.toUpperCase() === val.trim().toUpperCase());
    if (classObj) {
        const classDropdown = document.getElementById('classDropdown');
        if (classDropdown) classDropdown.value = classObj.class_name;
        loadClassStudents(classObj.class_name);
    }
}

function onSessionBatchInput(val) {
    const b = val.trim().toUpperCase();
    if (!b || b === 'ALL' || b === 'ALL BATCHES') {
        filterByBatch('ALL');
    } else {
        filterByBatch(b);
    }
}


// ── Class Roster Selection & Batch Labels ────────────────────────

function loadClassStudents(className) {
    const grid = document.getElementById('rosterGrid');
    const pillsBar = document.getElementById('batchPillsBar');
    const classDropdown = document.getElementById('classDropdown');
    if (!grid) return;

    if (classDropdown && classDropdown.value !== className) {
        classDropdown.value = className;
    }

    if (!className) {
        currentLoadedClass = null;
        pillsBar?.classList.add('hidden');
        grid.innerHTML = `
            <div class="empty-state" style="padding: var(--space-xl); grid-column: 1 / -1;">
                <div class="icon"><span class="material-symbols-outlined" style="font-size: 3rem;">group</span></div>
                <p class="text-muted">Select a class from the dropdown above to load student rosters and batch labels.</p>
            </div>`;
        selectedStudentsSet.clear();
        updateSelectedCount();
        return;
    }

    const classObj = classesData.find(c => c.class_name === className);
    if (!classObj || !classObj.students.length) {
        currentLoadedClass = classObj || { class_name: className, students: [], batches: [] };
        pillsBar?.classList.add('hidden');
        grid.innerHTML = `
            <div class="empty-state" style="padding: var(--space-xl); grid-column: 1 / -1;">
                <div class="icon"><span class="material-symbols-outlined" style="font-size: 3rem;">group</span></div>
                <p class="text-muted">No students registered under ${className}.</p>
            </div>`;
        selectedStudentsSet.clear();
        updateSelectedCount();
        return;
    }

    currentLoadedClass = classObj;
    currentActiveBatch = 'ALL';

    // Auto-fill Section 1 class & name
    const classInput = document.getElementById('sessionClass');
    if (classInput) classInput.value = className;

    const nameInput = document.getElementById('sessionName');
    if (nameInput) nameInput.value = `${className} Lab Session`;

    const batchInput = document.getElementById('sessionBatch');
    if (batchInput) batchInput.value = 'All Batches';

    // Clear set and select all by default
    selectedStudentsSet.clear();
    let html = '';

    for (const st of classObj.students) {
        selectedStudentsSet.add(st.roll_no);
        const batchTag = st.batch ? `<span class="badge badge--batch" style="margin-left: auto;">${st.batch}</span>` : '';
        html += `
        <label class="roster-item-card selected" id="card-${st.roll_no}" data-batch="${st.batch || ''}" onclick="toggleRosterItem('${st.roll_no}', event)">
            <input type="checkbox" value="${st.roll_no}" checked onclick="event.stopPropagation(); toggleRosterItem('${st.roll_no}')">
            <div class="roster-item-info" style="flex: 1;">
                <div class="flex items-center justify-between">
                    <span class="roster-item-roll">${st.roll_no}</span>
                    ${batchTag}
                </div>
                <span class="roster-item-name">${st.name || '—'}</span>
            </div>
        </label>`;
    }

    grid.innerHTML = html;
    updateSelectedCount();

    // Render Batch Labels / Filter Pills immediately
    renderBatchPills(classObj);
}

function renderBatchPills(classObj) {
    const pillsBar = document.getElementById('batchPillsBar');
    const pillsList = document.getElementById('batchPillsList');
    if (!pillsBar || !pillsList) return;

    const batches = classObj.batches || [];
    currentActiveBatch = 'ALL';

    // Count per batch
    const batchCounts = {};
    classObj.students.forEach(st => {
        const b = st.batch || 'Unassigned';
        batchCounts[b] = (batchCounts[b] || 0) + 1;
    });

    let pillsHtml = `
        <button type="button" class="batch-pill active" id="pill-ALL" onclick="filterByBatch('ALL')">
            All Students <span class="pill-count">${classObj.students.length}</span>
        </button>
    `;

    batches.forEach(b => {
        const count = batchCounts[b] || 0;
        pillsHtml += `
            <button type="button" class="batch-pill" id="pill-${b}" onclick="filterByBatch('${b}')">
                ${b.startsWith('Batch') ? b : 'Batch ' + b} <span class="pill-count">${count}</span>
            </button>
        `;
    });

    pillsList.innerHTML = pillsHtml;
    pillsBar.classList.remove('hidden');
}

function filterByBatch(batchName) {
    currentActiveBatch = batchName;
    document.querySelectorAll('.batch-pill').forEach(btn => btn.classList.remove('active'));

    const activePill = document.getElementById(`pill-${batchName}`);
    if (activePill) activePill.classList.add('active');

    const grid = document.getElementById('rosterGrid');
    if (!grid || !currentLoadedClass) return;

    selectedStudentsSet.clear();

    grid.querySelectorAll('.roster-item-card').forEach(card => {
        const cardBatch = (card.getAttribute('data-batch') || '').toUpperCase();
        const bTarget = batchName.toUpperCase();
        const cb = card.querySelector('input[type="checkbox"]');
        const roll = cb?.value;

        // Match exact batch or variations like "1" vs "BATCH 1" vs "A1"
        const isMatch = (bTarget === 'ALL') ||
                        (cardBatch === bTarget) ||
                        (cardBatch.replace('BATCH ', '') === bTarget.replace('BATCH ', '')) ||
                        (cardBatch.replace('BATCH-', '') === bTarget.replace('BATCH-', ''));

        if (isMatch) {
            card.style.display = 'flex';
            card.classList.add('selected');
            if (cb) cb.checked = true;
            if (roll) selectedStudentsSet.add(roll);
        } else {
            card.style.display = 'none';
            card.classList.remove('selected');
            if (cb) cb.checked = false;
        }
    });

    // Auto-update Session 1 inputs
    const batchInput = document.getElementById('sessionBatch');
    if (batchInput) {
        batchInput.value = batchName === 'ALL' ? 'All Batches' : batchName;
    }

    const nameInput = document.getElementById('sessionName');
    if (nameInput && currentLoadedClass) {
        if (batchName !== 'ALL') {
            const bLabel = batchName.startsWith('Batch') ? batchName : `Batch ${batchName}`;
            nameInput.value = `${currentLoadedClass.class_name} ${bLabel} Lab`;
        } else {
            nameInput.value = `${currentLoadedClass.class_name} Lab Session`;
        }
    }

    updateSelectedCount();
}


// ── Semester Batch Allocator Modal ───────────────────────────────

function openBatchAllocatorModal() {
    if (!currentLoadedClass || !currentLoadedClass.students.length) {
        showToast('Please select a class with registered students first', 'info');
        return;
    }

    const classInput = document.getElementById('allocatorClass');
    if (classInput) classInput.value = currentLoadedClass.class_name;

    updateBatchAllocatorPreview();
    openModal('batchAllocatorModal');
}

function updateBatchAllocatorPreview() {
    const listEl = document.getElementById('allocatorPreviewList');
    if (!listEl || !currentLoadedClass || !currentLoadedClass.students.length) return;

    const splitCount = parseInt(document.getElementById('allocatorSplitCount')?.value || '2');
    const prefix = document.getElementById('allocatorPrefix')?.value || 'Batch ';
    const students = currentLoadedClass.students;
    const total = students.length;
    const chunkSize = Math.ceil(total / splitCount);

    let previewHtml = '';
    for (let b = 1; b <= splitCount; b++) {
        const startIdx = (b - 1) * chunkSize;
        const endIdx = Math.min(total, b * chunkSize);
        if (startIdx < total) {
            const count = endIdx - startIdx;
            const firstRoll = students[startIdx]?.roll_no;
            const lastRoll = students[endIdx - 1]?.roll_no;
            const bName = `${prefix}${b}`;

            previewHtml += `
                <div class="flex items-center justify-between p-xs" style="background: var(--bg-tertiary); border-radius: var(--radius-sm);">
                    <div>
                        <strong class="text-primary">${bName}</strong>
                        <span class="text-secondary text-xs">(${count} students)</span>
                    </div>
                    <span class="text-muted text-xs font-mono">${firstRoll} ... ${lastRoll}</span>
                </div>
            `;
        }
    }

    listEl.innerHTML = previewHtml;
}

async function saveSemesterBatchAllocation() {
    if (!currentLoadedClass || !currentLoadedClass.students.length) return;

    const splitCount = parseInt(document.getElementById('allocatorSplitCount')?.value || '2');
    const prefix = document.getElementById('allocatorPrefix')?.value || 'Batch ';
    const className = currentLoadedClass.class_name;

    const btn = document.getElementById('saveBatchAllocBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving to Database...';
    }

    try {
        const result = await apiCall('/api/sessions/assign-batches', 'POST', {
            class_name: className,
            split_count: splitCount,
            prefix: prefix,
        });

        showToast(result.message || 'Semester batches saved', 'success');
        closeModal('batchAllocatorModal');

        // Refresh class list from database
        const freshClasses = await apiCall('/api/sessions/classes');
        classesData = freshClasses;

        // Re-load the class roster with the new persistent batches
        loadClassStudents(className);

        // Filter to Batch 1 by default
        const firstBatch = `${prefix}1`;
        filterByBatch(firstBatch);
    } catch (err) {
        showToast(err.message || 'Failed to save batch allocation', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" height="16px" viewBox="0 -960 960 960" width="16px" fill="currentColor"><path d="M840-680v480q0 33-23.5 56.5T760-120H200q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h480l160 160Zm-80 34L646-760H200v560h560v-446ZM565-275q35-35 35-85t-35-85q-35-35-85-35t-85 35q-35 35-35 85t35 85q35 35 85 35t85-35ZM240-560h360v-160H240v160Zm-40-86v446-560 114Z"/></svg><span>Save to Semester Database</span>';
        }
    }
}


// ── Roster Item Toggling ─────────────────────────────────────────

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
        if (card.style.display !== 'none') {
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
        }
    });

    updateSelectedCount();
}

function filterRoster(query) {
    const q = query.trim().toUpperCase();
    const grid = document.getElementById('rosterGrid');
    if (!grid) return;

    grid.querySelectorAll('.roster-item-card').forEach(card => {
        const cardBatch = (card.getAttribute('data-batch') || '').toUpperCase();
        const bTarget = currentActiveBatch.toUpperCase();
        const isMatchBatch = (bTarget === 'ALL') ||
                             (cardBatch === bTarget) ||
                             (cardBatch.replace('BATCH ', '') === bTarget.replace('BATCH ', ''));

        const text = card.textContent.toUpperCase();

        if (isMatchBatch && (!q || text.includes(q))) {
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
        if (e.dataTransfer.files && e.dataTransfer.files.length) {
            handleFileSelect(e.dataTransfer.files);
        }
    });
}

async function handleFileSelect(files) {
    if (!files || !files.length) return;
    const file = files[0];

    const resultBox = document.getElementById('fileUploadResult');
    if (resultBox) {
        resultBox.classList.remove('hidden');
        resultBox.innerHTML = `<p class="text-secondary">⏳ Parsing ${file.name}...</p>`;
    }

    try {
        const result = await apiUpload('/api/sessions/parse-file', file);
        if (result.success) {
            selectedStudentsSet.clear();
            result.roll_numbers.forEach(r => selectedStudentsSet.add(r));

            if (resultBox) {
                resultBox.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span class="material-symbols-outlined text-success" style="font-size: 1.5rem;">check_circle</span>
                            <div>
                                <strong class="text-success">Loaded ${result.count} roll numbers</strong>
                                <p class="text-muted text-sm">${file.name}</p>
                            </div>
                        </div>
                        <button type="button" class="btn btn-ghost btn-sm" onclick="clearUploadedFile()">Change</button>
                    </div>
                `;
            }
            updateSelectedCount();
            showToast(`Loaded ${result.count} students from ${file.name}`, 'success');
        }
    } catch (err) {
        if (resultBox) {
            resultBox.innerHTML = `<p class="text-danger" style="display: flex; align-items: center; gap: 4px;"><span class="material-symbols-outlined">error</span><span>${err.message}</span></p>`;
        }
    }
}

function clearUploadedFile() {
    const input = document.getElementById('bulkFileInput');
    if (input) input.value = '';
    const resultBox = document.getElementById('fileUploadResult');
    if (resultBox) resultBox.classList.add('hidden');
    selectedStudentsSet.clear();
    updateSelectedCount();
}


// ── Paste Roll Numbers ───────────────────────────────────────────

function parsePastedRolls(text) {
    if (!text) {
        selectedStudentsSet.clear();
        updateSelectedCount();
        const statsEl = document.getElementById('pasteStats');
        if (statsEl) statsEl.textContent = '0 roll numbers detected';
        return;
    }

    selectedStudentsSet.clear();
    const tokens = text
        .split(/[\n,\s\t]+/)
        .map(t => t.trim().toUpperCase())
        .filter(t => t.length >= 3);

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

    // Collect custom fields if any
    const customFields = {};
    document.querySelectorAll('.session-custom-input').forEach(input => {
        const name = input.getAttribute('data-cf-name');
        if (name && input.value.trim()) {
            customFields[name] = input.value.trim();
        }
    });

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
            custom_fields: customFields,
        };

        const result = await apiCall('/api/sessions', 'POST', payload);
        showToast(result.message || 'Session created', 'success');

        setTimeout(() => {
            window.location.href = result.redirect_url || '/sessions';
        }, 600);
    } catch (err) {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = isCompleted
                ? `<span class="material-symbols-outlined">fact_check</span><span>Create & Finalize Bulk Records</span>`
                : `<span class="material-symbols-outlined">rocket_launch</span><span>Launch Live Scanner Cockpit →</span>`;
        }
    }
}
