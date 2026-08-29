/**
 * Entry.js — Student entry/exit page logic
 *
 * Two-step flow:
 *   1. Enter/scan roll number → identify student
 *   2. If inside → exit; if outside → show form → submit entry
 */

let exitTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    const identifyForm = document.getElementById('identifyForm');
    const entryForm = document.getElementById('entryForm');

    // Step 1: Identify / Scan
    if (identifyForm) {
        identifyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const rollNo = document.getElementById('rollNoInput').value.trim();
            if (!rollNo) return;

            const btn = document.getElementById('continueBtn');
            btn.disabled = true;
            btn.textContent = 'Processing...';

            try {
                const result = await apiCall('/api/identify', 'POST', { roll_no: rollNo });

                if (result.is_inside) {
                    // Student is inside → Record Exit directly and show Exit Message Screen
                    const exitRes = await apiCall('/api/exit', 'POST', { roll_no: rollNo });
                    showExitScreen(exitRes);
                } else {
                    // Student is outside → open dynamic entry form
                    window.location.href = `/entry/form/${encodeURIComponent(rollNo)}`;
                }
            } catch (err) {
                btn.disabled = false;
                btn.textContent = 'Continue →';
            }
        });

        // Auto-focus for barcode scanner
        document.getElementById('rollNoInput')?.focus();
    }

    // Step 2: Submit entry
    if (entryForm) {
        entryForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitEntryBtn');
            btn.disabled = true;
            btn.textContent = 'Submitting...';

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

                // Reset and go back to step 1 after delay
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            } catch (err) {
                btn.disabled = false;
                btn.textContent = '✓ Record Entry';
            }
        });
    }
});


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

    // 4-second countdown before auto-resetting
    let secondsLeft = 4;
    if (countdownEl) countdownEl.textContent = secondsLeft;

    if (exitTimer) clearInterval(exitTimer);
    exitTimer = setInterval(() => {
        secondsLeft--;
        if (countdownEl) countdownEl.textContent = secondsLeft;
        if (secondsLeft <= 0) {
            clearInterval(exitTimer);
            resetToScanInput();
        }
    }, 1000);
}

function resetToScanInput() {
    if (exitTimer) clearInterval(exitTimer);

    const stepIdentify = document.getElementById('stepIdentify');
    const stepExitMessage = document.getElementById('stepExitMessage');
    const rollInput = document.getElementById('rollNoInput');
    const continueBtn = document.getElementById('continueBtn');

    if (stepExitMessage) stepExitMessage.classList.add('hidden');
    if (stepIdentify) stepIdentify.classList.remove('hidden');

    if (rollInput) {
        rollInput.value = '';
        rollInput.focus();
    }
    if (continueBtn) {
        continueBtn.disabled = false;
        continueBtn.textContent = 'Continue →';
    }
}

