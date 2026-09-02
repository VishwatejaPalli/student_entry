/**
 * Form Builder JS — Admin form builder UI logic
 *
 * Features:
 *   - Create/edit forms
 *   - Add fields from component panel
 *   - Inline field editing
 *   - Reorder fields (up/down)
 *   - Delete fields (soft-delete)
 *   - Save form + fields to API
 */

let formId = null;

document.addEventListener('DOMContentLoaded', () => {
    formId = document.getElementById('formId')?.value || null;
    if (formId === '') formId = null;
});


// ── Save Form ───────────────────────────────────────────────────

async function saveForm() {
    const name = document.getElementById('formName')?.value.trim();
    const desc = document.getElementById('formDesc')?.value.trim();

    if (!name) {
        showToast('Form name is required', 'error');
        return;
    }

    try {
        if (formId) {
            // Update existing
            await apiCall(`/api/forms/${formId}`, 'PUT', { name, description: desc });
            showToast('Form saved', 'success');
        } else {
            // Create new
            const result = await apiCall('/api/forms', 'POST', { name, description: desc });
            formId = result.id;
            document.getElementById('formId').value = formId;
            showToast('Form created! Now add fields.', 'success');

            // Update URL
            window.history.replaceState(null, '', `/admin/forms/builder/${formId}`);
        }
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Add Field ───────────────────────────────────────────────────

async function addField(fieldType) {
    if (!formId) {
        // Auto-save the form first
        const name = document.getElementById('formName')?.value.trim();
        if (!name) {
            showToast('Save the form first (enter a form name)', 'error');
            return;
        }
        await saveForm();
        if (!formId) return;
    }

    const defaults = getFieldDefaults(fieldType);

    try {
        const result = await apiCall(`/api/forms/${formId}/fields`, 'POST', defaults);
        showToast(`${fieldType} field added`, 'success');
        // Reload to show new field
        window.location.reload();
    } catch (err) {
        // Error shown by apiCall
    }
}

function getFieldDefaults(fieldType) {
    const base = { field_type: fieldType, field_name: '', label: '', required: false, configuration: {} };

    switch (fieldType) {
        case 'heading':
            base.configuration = { level: 2, text: 'New Heading' };
            break;
        case 'paragraph':
            base.configuration = { text: 'Enter your text here.', style: 'info' };
            break;
        case 'divider':
            break;
        case 'text':
            base.field_name = 'new_text';
            base.label = 'Text Field';
            base.configuration = { placeholder: '', max_length: 255 };
            break;
        case 'number':
            base.field_name = 'new_number';
            base.label = 'Number Field';
            base.configuration = { min: null, max: null, step: 1 };
            break;
        case 'textarea':
            base.field_name = 'new_textarea';
            base.label = 'Text Area';
            base.configuration = { placeholder: '', max_length: 1000, rows: 4 };
            break;
        case 'dropdown':
            base.field_name = 'new_dropdown';
            base.label = 'Dropdown';
            base.configuration = { options: ['Option 1', 'Option 2', 'Option 3'], default: null };
            break;
        case 'radio':
            base.field_name = 'new_radio';
            base.label = 'Radio Group';
            base.configuration = { options: ['Option A', 'Option B'], default: null, inline: false };
            break;
        case 'checkbox':
            base.field_name = 'new_checkbox';
            base.label = 'Checkbox';
            base.configuration = { label: 'Check this box', default: false };
            break;
        case 'date':
            base.field_name = 'new_date';
            base.label = 'Date';
            base.configuration = { default_today: true };
            break;
        case 'time':
            base.field_name = 'new_time';
            base.label = 'Time';
            base.configuration = { default_today: true };
            break;
    }
    return base;
}


// ── Toggle Field Editor ─────────────────────────────────────────

function toggleFieldEditor(btn) {
    const fieldItem = btn.closest('.field-item');
    const editor = fieldItem.querySelector('.field-editor');
    if (editor) {
        editor.classList.toggle('hidden');
        fieldItem.classList.toggle('editing');
    }
}


// ── Save Field Changes ──────────────────────────────────────────

async function saveField(btn) {
    const fieldItem = btn.closest('.field-item');
    const fieldId = fieldItem.dataset.fieldId;
    const fieldType = fieldItem.dataset.fieldType;

    const payload = {};

    // Common data fields
    const nameInput = fieldItem.querySelector('.field-edit-name');
    const labelInput = fieldItem.querySelector('.field-edit-label');
    const requiredInput = fieldItem.querySelector('.field-edit-required');

    if (nameInput) payload.field_name = nameInput.value.trim();
    if (labelInput) payload.label = labelInput.value.trim();
    if (requiredInput) payload.required = requiredInput.checked;

    // Build configuration based on type
    const config = {};

    if (fieldType === 'heading') {
        const textInput = fieldItem.querySelector('.field-edit-heading-text');
        const levelSelect = fieldItem.querySelector('.field-edit-heading-level');
        if (textInput) config.text = textInput.value;
        if (levelSelect) config.level = parseInt(levelSelect.value);
    }

    if (fieldType === 'paragraph') {
        const textInput = fieldItem.querySelector('.field-edit-para-text');
        const styleSelect = fieldItem.querySelector('.field-edit-para-style');
        if (textInput) config.text = textInput.value;
        if (styleSelect) config.style = styleSelect.value;
    }

    if (fieldType === 'dropdown' || fieldType === 'radio') {
        const optionsTextarea = fieldItem.querySelector('.field-edit-options');
        if (optionsTextarea) {
            config.options = optionsTextarea.value.split('\n').map(s => s.trim()).filter(s => s);
        }
    }

    if (fieldType === 'text' || fieldType === 'textarea') {
        const placeholderInput = fieldItem.querySelector('.field-edit-placeholder');
        if (placeholderInput) config.placeholder = placeholderInput.value;
    }

    if (fieldType === 'checkbox') {
        const cbLabelInput = fieldItem.querySelector('.field-edit-cb-label');
        if (cbLabelInput) config.label = cbLabelInput.value;
    }

    if (Object.keys(config).length > 0) {
        payload.configuration = config;
    }

    try {
        await apiCall(`/api/forms/${formId}/fields/${fieldId}`, 'PUT', payload);
        showToast('Field updated', 'success');
        // Reload to reflect changes
        window.location.reload();
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Move Field ──────────────────────────────────────────────────

async function moveField(btn, direction) {
    const fieldItem = btn.closest('.field-item');
    const fieldList = document.getElementById('fieldList');
    const items = Array.from(fieldList.querySelectorAll('.field-item[data-field-id]'));
    const index = items.indexOf(fieldItem);

    if (direction === 'up' && index > 0) {
        fieldList.insertBefore(fieldItem, items[index - 1]);
    } else if (direction === 'down' && index < items.length - 1) {
        fieldList.insertBefore(items[index + 1], fieldItem);
    } else {
        return; // Can't move further
    }

    // Save new order
    const newOrder = Array.from(fieldList.querySelectorAll('.field-item[data-field-id]'))
        .map(item => parseInt(item.dataset.fieldId));

    try {
        await apiCall(`/api/forms/${formId}/fields/reorder`, 'PUT', { field_ids: newOrder });
        showToast('Order updated', 'success');
    } catch (err) {
        // Reload on error
        window.location.reload();
    }
}


// ── Delete Field ────────────────────────────────────────────────

async function deleteField(btn) {
    const fieldItem = btn.closest('.field-item');
    const fieldId = fieldItem.dataset.fieldId;

    if (!confirm('Remove this field? Existing data for this field will be preserved.')) return;

    try {
        await apiCall(`/api/forms/${formId}/fields/${fieldId}`, 'DELETE');
        fieldItem.style.opacity = '0';
        fieldItem.style.transform = 'translateX(50px)';
        fieldItem.style.transition = 'all 0.3s ease';
        setTimeout(() => fieldItem.remove(), 300);
        showToast('Field removed', 'success');
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Activate Form ───────────────────────────────────────────────

async function activateForm(id) {
    try {
        await apiCall(`/api/forms/${id}/activate`, 'PUT');
        showToast('Form activated', 'success');
        window.location.reload();
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Delete Form ─────────────────────────────────────────────────

async function deleteForm(id, name) {
    const displayName = name ? `"${name}"` : 'this form';
    if (!confirm(`Are you sure you want to permanently delete ${displayName}?\nAll custom field configurations for this form will be removed.`)) {
        return;
    }

    try {
        const res = await apiCall(`/api/forms/${id}`, 'DELETE');
        showToast(res?.message || 'Form deleted successfully', 'success');
        const row = document.getElementById(`formRow-${id}`);
        if (row) {
            row.style.opacity = '0';
            row.style.transform = 'scale(0.95)';
            row.style.transition = 'all 0.3s ease';
            setTimeout(() => {
                row.remove();
                // Check if any form rows remain
                const remaining = document.querySelectorAll('.field-list .field-item');
                if (remaining.length === 0) {
                    window.location.reload();
                }
            }, 300);
        } else {
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Delegated event listeners ───────────────────────────────────

document.addEventListener('click', (e) => {
    const activateBtn = e.target.closest('[data-activate-form]');
    if (activateBtn) {
        e.preventDefault();
        activateForm(activateBtn.dataset.activateForm);
    }

    const deleteBtn = e.target.closest('[data-delete-form]');
    if (deleteBtn) {
        e.preventDefault();
        deleteForm(deleteBtn.dataset.deleteForm, deleteBtn.dataset.formName);
    }
});
