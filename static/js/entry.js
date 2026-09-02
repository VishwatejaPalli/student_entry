/**
 * Entry.js — Fast Kiosk entry/exit logic with auto-reset
 *
 * Flow:
 *   1. Enter/scan roll number → identify student
 *   2. If inside → Exit instantly with duration summary
 *   3. If outside & no required fields → Check IN instantly with welcome card
 *   4. If outside & required fields → Open dynamic form
 */

let resetTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    const identifyForm = document.getElementById('identifyForm');
    const entryForm = document.getElementById('entryForm');

    // Step 1: Identify / Scan
    if (identifyForm) {
        identifyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const rollNo = document.getElementById('rollNoInput').value.trim().toUpperCase();
            if (!rollNo) return;

            const btn = document.getElementById('continueBtn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Processing...';
            }

            try {
                const result = await apiCall('/api/identify', 'POST', { roll_no: rollNo });

                if (result.is_inside) {
                    // Student is inside → Record Exit directly
                    const exitRes = await apiCall('/api/exit', 'POST', { roll_no: rollNo });
                    showExitScreen(exitRes);
                } else if (result.entry_recorded) {
                    // Student is outside & entry was recorded automatically
                    showEntryScreen(result);
                } else {
                    // Form has required fields → navigate to form
                    window.location.href = `/entry/form/${encodeURIComponent(rollNo)}`;
                }
            } catch (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<span class="material-symbols-outlined">flash_on</span><span>Check In / Out →</span>`;
                }
            }
        });

        // Auto-focus for barcode scanner
        document.getElementById('rollNoInput')?.focus();
    }

    // Step 2: Dynamic Entry Form Submit
    if (entryForm) {
        entryForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitEntryBtn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Submitting...';
            }

            const formData = new FormData(entryForm);
            const rollNo = formData.get('roll_no');

            // Collect custom field values
            const fieldValues = {};
            for (const [key, value] of formData.entries()) {
                if (key !== 'roll_no') {
                    fieldValues[key] = value;
                }
            }

            // Handle unchecked checkboxes
            entryForm.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                if (!cb.checked && cb.name && cb.name !== 'roll_no') {
                    fieldValues[cb.name] = 'false';
                }
            });

            try {
                const result = await apiCall('/api/entry', 'POST', {
                    roll_no: rollNo,
                    field_values: fieldValues,
                });

                showToast(result.message, 'success');

                setTimeout(() => {
                    window.location.href = '/';
                }, 1200);
            } catch (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = `<span class="material-symbols-outlined">how_to_reg</span><span>Record Entry</span>`;
                }
            }
        });
    }
});


// ── Entry Confirmation Screen ────────────────────────────────────

function showEntryScreen(data) {
    const stepIdentify = document.getElementById('stepIdentify');
    const stepEntryMessage = document.getElementById('stepEntryMessage');

    if (!stepEntryMessage) return;

    if (stepIdentify) stepIdentify.classList.add('hidden');
    stepEntryMessage.classList.remove('hidden');

    const nameEl = document.getElementById('entryStudentName');
    const rollEl = document.getElementById('entryRollNo');
    const deptSecEl = document.getElementById('entryDeptSec');
    const batchEl = document.getElementById('entryBatch');
    const timeEl = document.getElementById('entryTimeVal');
    const countdownEl = document.getElementById('entryCountdown');

    const sName = data.student_name || data.roll_no;
    if (nameEl) nameEl.textContent = sName;
    if (rollEl) rollEl.textContent = data.roll_no;

    let deptStr = data.department || '—';
    if (data.section) deptStr += ` (Section ${data.section})`;
    if (deptSecEl) deptSecEl.textContent = deptStr;

    if (batchEl) {
        batchEl.innerHTML = data.batch
            ? `<span class="badge badge--batch">${data.batch}</span>`
            : `<span class="text-muted text-xs">—</span>`;
    }

    if (timeEl) {
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        timeEl.textContent = `${hh}:${mm}`;
    }

    showToast(`Check-in recorded for ${sName}`, 'success');

    // 3-second countdown before auto-resetting
    let secondsLeft = 3;
    if (countdownEl) countdownEl.textContent = secondsLeft;

    if (resetTimer) clearInterval(resetTimer);
    resetTimer = setInterval(() => {
        secondsLeft--;
        if (countdownEl) countdownEl.textContent = secondsLeft;
        if (secondsLeft <= 0) {
            clearInterval(resetTimer);
            resetToScanInput();
        }
    }, 1000);
}


// ── Exit Screen Management ───────────────────────────────────────

function showExitScreen(data) {
    const stepIdentify = document.getElementById('stepIdentify');
    const stepExitMessage = document.getElementById('stepExitMessage');

    if (!stepExitMessage) return;

    if (stepIdentify) stepIdentify.classList.add('hidden');
    stepExitMessage.classList.remove('hidden');

    const greetingEl = document.getElementById('exitGreeting');
    const subEl = document.getElementById('exitSubMessage');
    const nameEl = document.getElementById('exitStudentName');
    const rollEl = document.getElementById('exitRollNo');
    const entryEl = document.getElementById('exitEntryTime');
    const exitEl = document.getElementById('exitTime');
    const durEl = document.getElementById('exitDuration');
    const countdownEl = document.getElementById('exitCountdown');

    if (greetingEl) greetingEl.textContent = `Goodbye, ${data.student_name || data.roll_no}!`;
    if (subEl) subEl.textContent = 'Exit recorded successfully';
    if (nameEl) nameEl.textContent = data.student_name || '—';
    if (rollEl) rollEl.textContent = data.roll_no;
    if (entryEl) entryEl.textContent = data.entry_time ? data.entry_time.slice(11, 16) : '—';
    if (exitEl) exitEl.textContent = data.exit_time ? data.exit_time.slice(11, 16) : '—';
    if (durEl) durEl.textContent = data.duration_formatted || `${data.duration_minutes || 0} min`;

    showToast(`Exit recorded for ${data.student_name || data.roll_no}`, 'success');

    // 3-second countdown before auto-resetting
    let secondsLeft = 3;
    if (countdownEl) countdownEl.textContent = secondsLeft;

    if (resetTimer) clearInterval(resetTimer);
    resetTimer = setInterval(() => {
        secondsLeft--;
        if (countdownEl) countdownEl.textContent = secondsLeft;
        if (secondsLeft <= 0) {
            clearInterval(resetTimer);
            resetToScanInput();
        }
    }, 1000);
}

function resetToScanInput() {
    if (resetTimer) clearInterval(resetTimer);

    const stepIdentify = document.getElementById('stepIdentify');
    const stepEntryMessage = document.getElementById('stepEntryMessage');
    const stepExitMessage = document.getElementById('stepExitMessage');
    const rollInput = document.getElementById('rollNoInput');
    const continueBtn = document.getElementById('continueBtn');

    if (stepEntryMessage) stepEntryMessage.classList.add('hidden');
    if (stepExitMessage) stepExitMessage.classList.add('hidden');
    if (stepIdentify) stepIdentify.classList.remove('hidden');

    if (rollInput) {
        rollInput.value = '';
        rollInput.focus();
    }
    if (continueBtn) {
        continueBtn.disabled = false;
        continueBtn.innerHTML = `<span class="material-symbols-outlined">flash_on</span><span>Check In / Out →</span>`;
    }
}
