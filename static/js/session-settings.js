/**
 * Session-Settings.js — Logic for Customizable Bulk Session Presets & Custom Fields
 */

let settingsState = {
    rooms: [],
    subjects: [],
    faculties: [],
    batches: [],
    defaults: {
        pc_strategy: 'auto_sequential',
        pc_prefix: 'PC-',
        late_threshold_min: 15,
        bulk_status: 'PRESENT',
    },
    custom_fields: [],
};

document.addEventListener('DOMContentLoaded', () => {
    // Load embedded current config
    const jsonEl = document.getElementById('currentConfigJson');
    if (jsonEl) {
        try {
            const parsed = JSON.parse(jsonEl.textContent || '{}');
            settingsState.rooms = parsed.rooms || [];
            settingsState.subjects = parsed.subjects || [];
            settingsState.faculties = parsed.faculties || [];
            settingsState.batches = parsed.batches || [];
            settingsState.defaults = Object.assign(settingsState.defaults, parsed.defaults || {});
            settingsState.custom_fields = parsed.custom_fields || [];
        } catch (e) {
            console.error('Failed to parse settings JSON', e);
        }
    }

    renderAllTags();
    renderDefaults();
    renderCustomFields();
});


// ── Tag Chip Rendering ───────────────────────────────────────────

function renderAllTags() {
    renderTagGroup('rooms', 'roomsTagContainer');
    renderTagGroup('subjects', 'subjectsTagContainer');
    renderTagGroup('faculties', 'facultiesTagContainer');
    renderTagGroup('batches', 'batchesTagContainer');
}

function renderTagGroup(key, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const list = settingsState[key] || [];
    if (!list.length) {
        container.innerHTML = `<span class="text-muted text-xs">No presets added yet. Use the box below to add.</span>`;
        return;
    }

    let html = '';
    list.forEach((item, idx) => {
        html += `
        <span class="tag-chip">
            <span>${item}</span>
            <button type="button" class="remove-tag" onclick="removeTag('${key}', ${idx})" title="Remove"><span class="material-symbols-outlined" style="font-size: 0.9rem; vertical-align: middle;">close</span></button>
        </span>`;
    });

    container.innerHTML = html;
}

function addTag(key) {
    let inputId = '';
    if (key === 'rooms') inputId = 'newRoomInput';
    else if (key === 'subjects') inputId = 'newSubjectInput';
    else if (key === 'faculties') inputId = 'newFacultyInput';
    else if (key === 'batches') inputId = 'newBatchInput';

    const input = document.getElementById(inputId);
    if (!input) return;

    const val = input.value.trim();
    if (!val) return;

    if (!settingsState[key].includes(val)) {
        settingsState[key].push(val);
        renderTagGroup(key, `${key}TagContainer`);
    }

    input.value = '';
    input.focus();
}

function removeTag(key, idx) {
    if (settingsState[key] && settingsState[key][idx] !== undefined) {
        settingsState[key].splice(idx, 1);
        renderTagGroup(key, `${key}TagContainer`);
    }
}


// ── Defaults Rendering ───────────────────────────────────────────

function renderDefaults() {
    const pcStrat = document.getElementById('defaultPcStrategy');
    const pcPref = document.getElementById('defaultPcPrefix');
    const lateThresh = document.getElementById('defaultLateThreshold');
    const bulkStat = document.getElementById('defaultBulkStatus');

    if (pcStrat) pcStrat.value = settingsState.defaults.pc_strategy || 'auto_sequential';
    if (pcPref) pcPref.value = settingsState.defaults.pc_prefix || 'PC-';
    if (lateThresh) lateThresh.value = settingsState.defaults.late_threshold_min || 15;
    if (bulkStat) bulkStat.value = settingsState.defaults.bulk_status || 'PRESENT';
}


// ── Custom Fields Rendering ──────────────────────────────────────

function renderCustomFields() {
    const container = document.getElementById('customFieldsContainer');
    if (!container) return;

    if (!settingsState.custom_fields.length) {
        container.innerHTML = `
            <div class="empty-state" style="padding: var(--space-md);">
                <p class="text-muted text-sm">No custom fields configured. Click <strong>+ Add Field</strong> above if you wish to capture custom session attributes.</p>
            </div>`;
        return;
    }

    let html = `
        <div style="display: grid; grid-template-columns: 2fr 2fr 1fr 1fr auto; gap: var(--space-sm); font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: var(--space-xs); padding: 0 var(--space-sm);">
            <span>Field Key</span>
            <span>Display Label</span>
            <span>Type</span>
            <span>Required</span>
            <span></span>
        </div>
    `;

    settingsState.custom_fields.forEach((cf, idx) => {
        html += `
        <div class="custom-field-row">
            <input type="text" class="form-input form-input-sm" value="${cf.field_name}" placeholder="field_key" oninput="settingsState.custom_fields[${idx}].field_name = this.value.trim().toLowerCase().replace(/\\s+/g, '_')">
            <input type="text" class="form-input form-input-sm" value="${cf.label}" placeholder="Display Label" oninput="settingsState.custom_fields[${idx}].label = this.value.trim()">
            <select class="form-select form-select-sm" onchange="settingsState.custom_fields[${idx}].field_type = this.value">
                <option value="text" ${cf.field_type === 'text' ? 'selected' : ''}>Text</option>
                <option value="number" ${cf.field_type === 'number' ? 'selected' : ''}>Number</option>
                <option value="textarea" ${cf.field_type === 'textarea' ? 'selected' : ''}>Textarea</option>
            </select>
            <label class="flex items-center gap-xs text-sm" style="margin-bottom: 0; cursor: pointer;">
                <input type="checkbox" ${cf.required ? 'checked' : ''} onchange="settingsState.custom_fields[${idx}].required = this.checked">
                Required
            </label>
            <button type="button" class="btn btn-ghost btn-sm text-danger" onclick="removeCustomFieldRow(${idx})" title="Delete Field" style="display: inline-flex; align-items: center; justify-content: center;"><span class="material-symbols-outlined" style="font-size: 1rem;">close</span></button>
        </div>`;
    });

    container.innerHTML = html;
}

function addCustomFieldRow() {
    settingsState.custom_fields.push({
        field_name: `field_${settingsState.custom_fields.length + 1}`,
        label: `Custom Field ${settingsState.custom_fields.length + 1}`,
        field_type: 'text',
        required: false,
        placeholder: '',
    });
    renderCustomFields();
}

function removeCustomFieldRow(idx) {
    settingsState.custom_fields.splice(idx, 1);
    renderCustomFields();
}


// ── Save All Settings ────────────────────────────────────────────

async function saveAllSettings() {
    const btn = document.getElementById('saveConfigBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
    }

    // Collect defaults from inputs
    settingsState.defaults.pc_strategy = document.getElementById('defaultPcStrategy')?.value || 'auto_sequential';
    settingsState.defaults.pc_prefix = document.getElementById('defaultPcPrefix')?.value.trim() || 'PC-';
    settingsState.defaults.late_threshold_min = parseInt(document.getElementById('defaultLateThreshold')?.value || '15');
    settingsState.defaults.bulk_status = document.getElementById('defaultBulkStatus')?.value || 'PRESENT';

    // Sanitize custom fields
    settingsState.custom_fields = settingsState.custom_fields.filter(cf => cf.field_name && cf.label);

    try {
        const result = await apiCall('/api/sessions/settings', 'POST', settingsState);
        showToast(result.message || 'Settings saved successfully', 'success');

        setTimeout(() => {
            window.location.href = '/sessions';
        }, 800);
    } catch (err) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" height="16px" viewBox="0 -960 960 960" width="16px" fill="currentColor"><path d="M840-680v480q0 33-23.5 56.5T760-120H200q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h480l160 160Zm-80 34L646-760H200v560h560v-446ZM565-275q35-35 35-85t-35-85q-35-35-85-35t-85 35q-35 35-35 85t35 85q35 35 85 35t85-35ZM240-560h360v-160H240v160Zm-40-86v446-560 114Z"/></svg><span>Save All Presets</span>';
        }
    }
}
