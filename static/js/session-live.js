/**
 * Session-Live.js — Real-Time Live Session Scanner Cockpit
 *
 * Features:
 *   - High-speed Barcode Scanner input with permanent autofocus
 *   - Web Audio synthesizer for instant pleasant chime feedback
 *   - Live DOM updates of student roster, counters, and progress bar
 *   - Manual status overrides & PC edits
 *   - Session finalization (marking absentees and computing durations)
 */

let sessionId = null;
let soundEnabled = true;
let audioCtx = null;
let currentFilter = 'ALL';

document.addEventListener('DOMContentLoaded', () => {
    sessionId = document.getElementById('currentSessionId')?.value;
    const scanInput = document.getElementById('liveScanInput');

    // Auto-focus barcode input
    scanInput?.focus();

    // Re-focus scanner on click outside inputs/buttons
    document.addEventListener('click', (e) => {
        if (!['INPUT', 'BUTTON', 'A', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
            scanInput?.focus();
        }
    });

    // Initialize Web Audio on first user interaction
    document.addEventListener('keydown', initAudio, { once: true });
    document.addEventListener('click', initAudio, { once: true });

    // Set initial meter bar width from data-initial-pct
    const meter = document.getElementById('meterBarFill');
    if (meter) {
        const pct = meter.dataset.initialPct || '0';
        meter.style.width = `${pct}%`;
    }
});


// ── Web Audio Synth Sounds ───────────────────────────────────────

function initAudio() {
    if (!audioCtx) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
            audioCtx = new AudioContextClass();
        }
    }
}

function playSynthSound(type) {
    if (!soundEnabled) return;
    initAudio();
    if (!audioCtx) return;

    try {
        const now = audioCtx.currentTime;

        if (type === 'success') {
            // High two-tone positive chime (D5 -> A5)
            playTone(587.33, now, 0.12, 'sine');
            playTone(880.00, now + 0.08, 0.18, 'sine');
        } else if (type === 'late') {
            // Notice chime (A4 -> F4)
            playTone(440.00, now, 0.14, 'triangle');
            playTone(349.23, now + 0.10, 0.20, 'triangle');
        } else if (type === 'info') {
            // Soft blip (C5)
            playTone(523.25, now, 0.10, 'sine');
        } else {
            // Warning low buzz (D3)
            playTone(146.83, now, 0.22, 'sawtooth');
        }
    } catch (e) {
        // Silently continue if audio fails
    }
}

function playTone(freq, startTime, duration, waveType = 'sine') {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = waveType;
    osc.frequency.setValueAtTime(freq, startTime);

    gain.gain.setValueAtTime(0.15, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start(startTime);
    osc.stop(startTime + duration);
}

function toggleAudioFeedback() {
    soundEnabled = !soundEnabled;
    const btn = document.getElementById('soundToggleBtn');
    if (btn) {
        btn.innerHTML = soundEnabled
            ? `<span class="material-symbols-outlined" style="font-size: 1rem;">volume_up</span><span>Sound ON</span>`
            : `<span class="material-symbols-outlined" style="font-size: 1rem;">volume_off</span><span>Muted</span>`;
        btn.classList.toggle('btn-secondary', soundEnabled);
        btn.classList.toggle('btn-ghost', !soundEnabled);
    }
    showToast(soundEnabled ? 'Audio feedback enabled' : 'Audio feedback muted', 'info');
}


// ── Barcode Scan & Rapid Entry ───────────────────────────────────

async function handleSessionScan(e) {
    e.preventDefault();

    const input = document.getElementById('liveScanInput');
    const rollNo = input?.value.trim().toUpperCase();
    if (!rollNo) return;

    input.value = '';
    input.focus();

    const card = document.getElementById('scannerCard');
    const feedback = document.getElementById('scanFeedback');
    const fIcon = document.getElementById('feedbackIcon');
    const fText = document.getElementById('feedbackText');
    const fSub = document.getElementById('feedbackSub');

    try {
        const result = await apiCall(`/api/sessions/${sessionId}/scan`, 'POST', { roll_no: rollNo });

        // Play audio chime
        playSynthSound(result.sound || (result.status === 'LATE' ? 'late' : 'success'));

        // Visual flash effect on card
        card?.classList.remove('flash-success', 'flash-late', 'flash-warning');
        const flashCls = result.status === 'LATE' ? 'flash-late' : 'flash-success';
        card?.classList.add(flashCls);
        setTimeout(() => card?.classList.remove(flashCls), 600);

        // Update feedback banner
        if (feedback) {
            feedback.classList.remove('hidden');
            if (fIcon) {
                fIcon.innerHTML = result.status === 'LATE'
                    ? `<span class="material-symbols-outlined text-warning">schedule</span>`
                    : `<span class="material-symbols-outlined text-success">check_circle</span>`;
            }
            if (fText) fText.textContent = `${result.student_name || result.roll_no} — ${result.status}`;
            if (fSub) {
                fSub.textContent = (result.pc_assigned ? `Assigned: ${result.pc_assigned} • ` : '') +
                                   (result.is_walk_in ? 'Walk-in Student • ' : '') +
                                   `Recorded at ${new Date().toLocaleTimeString().slice(0, 5)}`;
            }
        }

        // Update Live Roster DOM Table
        updateRosterRow(result);

        // Recalculate Metrics
        updateLiveMetrics();
    } catch (err) {
        playSynthSound('warning');
        card?.classList.add('flash-warning');
        setTimeout(() => card?.classList.remove('flash-warning'), 600);

        if (feedback) {
            feedback.classList.remove('hidden');
            if (fIcon) fIcon.innerHTML = `<span class="material-symbols-outlined text-danger">cancel</span>`;
            if (fText) fText.textContent = `Error: ${err.message}`;
            if (fSub) fSub.textContent = `Roll No: ${rollNo}`;
        }
    }
}


// ── Live Roster DOM Updates ──────────────────────────────────────

function updateRosterRow(data) {
    const tbody = document.getElementById('liveRosterBody');
    const emptyRow = document.getElementById('emptyRosterRow');
    if (emptyRow) emptyRow.remove();

    let row = document.getElementById(`row-${data.roll_no}`);
    const timeNowStr = new Date().toLocaleTimeString().slice(0, 5);

    const badgeHtml = data.status === 'LATE'
        ? `<span class="badge" style="background: rgba(255, 171, 64, 0.15); color: var(--accent-warning);">LATE</span>`
        : `<span class="badge badge--in">PRESENT</span>`;

    if (row) {
        // Update existing row
        row.dataset.status = data.status;
        row.cells[2].innerHTML = badgeHtml;
        row.cells[3].innerHTML = `<span class="pc-badge" id="pc-${data.roll_no}">${data.pc_assigned || '—'}</span>`;
        row.cells[4].textContent = timeNowStr;

        // Move row to top of table with highlight
        tbody.insertBefore(row, tbody.firstChild);
        row.style.background = 'rgba(0, 230, 118, 0.12)';
        setTimeout(() => row.style.background = '', 1200);
    } else {
        // Insert new Walk-in row at the top
        row = document.createElement('tr');
        row.id = `row-${data.roll_no}`;
        row.dataset.status = data.status;
        row.dataset.roll = data.roll_no;
        row.dataset.name = data.student_name || '';

        row.innerHTML = `
            <td><strong>${data.roll_no}</strong></td>
            <td>${data.student_name || '—'}</td>
            <td>${badgeHtml}</td>
            <td><span class="pc-badge" id="pc-${data.roll_no}">${data.pc_assigned || '—'}</span></td>
            <td>${timeNowStr}</td>
            <td><span class="text-xs text-muted">WALK_IN</span></td>
            <td>
                <div class="flex gap-xs">
                    <button type="button" class="btn btn-ghost btn-sm text-success" title="Mark Present" onclick="manualStatus('${data.roll_no}', 'PRESENT')"><span class="material-symbols-outlined" style="font-size: 1rem;">check</span></button>
                    <button type="button" class="btn btn-ghost btn-sm text-warning" title="Mark Late" onclick="manualStatus('${data.roll_no}', 'LATE')"><span class="material-symbols-outlined" style="font-size: 1rem;">schedule</span></button>
                    <button type="button" class="btn btn-ghost btn-sm text-danger" title="Mark Absent" onclick="manualStatus('${data.roll_no}', 'ABSENT')"><span class="material-symbols-outlined" style="font-size: 1rem;">close</span></button>
                    <button type="button" class="btn btn-ghost btn-sm" title="Edit PC" onclick="editPcPrompt('${data.roll_no}', '${data.pc_assigned}')"><span class="material-symbols-outlined" style="font-size: 1rem;">computer</span></button>
                </div>
            </td>
        `;
        tbody.insertBefore(row, tbody.firstChild);
        row.style.background = 'rgba(0, 230, 118, 0.15)';
        setTimeout(() => row.style.background = '', 1200);
    }
}


// ── Metric Recalculations ────────────────────────────────────────

function updateLiveMetrics() {
    const rows = Array.from(document.querySelectorAll('#liveRosterBody tr[data-status]'));
    const total = rows.length;

    let present = 0;
    let late = 0;
    let absent = 0;
    let pending = 0;

    rows.forEach(r => {
        const s = r.dataset.status;
        if (s === 'PRESENT') present++;
        else if (s === 'LATE') { present++; late++; }
        else if (s === 'ABSENT') absent++;
        else if (s === 'PENDING') pending++;
    });

    const elPres = document.getElementById('countPresent');
    const elLate = document.getElementById('countLate');
    const elPend = document.getElementById('countPending');
    const elTot = document.getElementById('countTotal');
    const elPct = document.getElementById('attendancePctText');
    const meter = document.getElementById('meterBarFill');

    if (elPres) elPres.textContent = present;
    if (elLate) elLate.textContent = late;
    if (elPend) elPend.textContent = pending;
    if (elTot) elTot.textContent = total;

    // Filter pill count badges
    const pAll = document.getElementById('pillAllCount');
    const pPres = document.getElementById('pillPresentCount');
    const pPend = document.getElementById('pillPendingCount');
    const pLate = document.getElementById('pillLateCount');
    const pAbs = document.getElementById('pillAbsentCount');

    if (pAll) pAll.textContent = total;
    if (pPres) pPres.textContent = present;
    if (pPend) pPend.textContent = pending;
    if (pLate) pLate.textContent = late;
    if (pAbs) pAbs.textContent = absent;

    const pct = total > 0 ? Math.round((present / total) * 100) : 0;
    if (elPct) elPct.textContent = `${pct}%`;
    if (meter) meter.style.width = `${pct}%`;
}


// ── Filter Roster ────────────────────────────────────────────────

function filterRosterByStatus(status, btn) {
    currentFilter = status;
    document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    if (btn) btn.classList.add('active');

    applyRosterFilters();
}

function searchLiveRoster(query) {
    applyRosterFilters();
}

function applyRosterFilters() {
    const searchVal = document.getElementById('rosterSearchLive')?.value.trim().toUpperCase() || '';
    const rows = document.querySelectorAll('#liveRosterBody tr[data-status]');

    rows.forEach(r => {
        const s = r.dataset.status;
        const roll = (r.dataset.roll || '').toUpperCase();
        const name = (r.dataset.name || '').toUpperCase();

        const matchStatus = (currentFilter === 'ALL') ||
                            (currentFilter === 'PRESENT' && (s === 'PRESENT' || s === 'LATE')) ||
                            (currentFilter === s);

        const matchSearch = !searchVal || roll.includes(searchVal) || name.includes(searchVal);

        if (matchStatus && matchSearch) {
            r.style.display = '';
        } else {
            r.style.display = 'none';
        }
    });
}


// ── Manual Status & PC Overrides ─────────────────────────────────

async function manualStatus(rollNo, newStatus) {
    try {
        await apiCall(`/api/sessions/${sessionId}/students/${rollNo}`, 'PUT', { status: newStatus });

        const row = document.getElementById(`row-${rollNo}`);
        if (row) {
            row.dataset.status = newStatus;
            let badgeHtml = '';
            if (newStatus === 'PRESENT') {
                badgeHtml = `<span class="badge badge--in">PRESENT</span>`;
                row.cells[4].textContent = new Date().toLocaleTimeString().slice(0, 5);
            } else if (newStatus === 'LATE') {
                badgeHtml = `<span class="badge" style="background: rgba(255, 171, 64, 0.15); color: var(--accent-warning);">LATE</span>`;
                row.cells[4].textContent = new Date().toLocaleTimeString().slice(0, 5);
            } else if (newStatus === 'ABSENT') {
                badgeHtml = `<span class="badge badge--out">ABSENT</span>`;
                row.cells[4].textContent = '—';
            }
            row.cells[2].innerHTML = badgeHtml;
        }

        updateLiveMetrics();
        showToast(`${rollNo} set to ${newStatus}`, 'success');
    } catch (err) {
        // Error shown by apiCall
    }
}

async function editPcPrompt(rollNo, currentPc) {
    const newPc = prompt(`Assign PC for ${rollNo}:`, currentPc || 'PC-01');
    if (newPc === null) return;

    try {
        await apiCall(`/api/sessions/${sessionId}/students/${rollNo}`, 'PUT', { pc_assigned: newPc.trim() });
        const pcEl = document.getElementById(`pc-${rollNo}`);
        if (pcEl) pcEl.textContent = newPc.trim() || '—';
        showToast(`PC updated for ${rollNo}`, 'success');
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── End Session Workflow ─────────────────────────────────────────

async function confirmEndSession() {
    const rows = Array.from(document.querySelectorAll('#liveRosterBody tr[data-status]'));
    const pendingCount = rows.filter(r => r.dataset.status === 'PENDING').length;

    let msg = 'End this class session?';
    if (pendingCount > 0) {
        msg += `\n\n⚠️ ${pendingCount} unscanned student(s) will automatically be marked as ABSENT.`;
    }

    if (!confirm(msg)) return;

    try {
        const result = await apiCall(`/api/sessions/${sessionId}/end`, 'POST');
        showToast('Class session finalized!', 'success');

        setTimeout(() => {
            window.location.href = '/sessions';
        }, 1000);
    } catch (err) {
        // Error shown by apiCall
    }
}
