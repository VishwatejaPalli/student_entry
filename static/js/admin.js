/**
 * Admin.js — Student management & multi-column filtering logic
 */

// ── Student CRUD ────────────────────────────────────────────────

function showAddModal() {
    document.getElementById('studentModalTitle').textContent = 'Add Student';
    document.getElementById('studentSubmitBtn').textContent = 'Add Student';
    document.getElementById('editStudentId').value = '';
    document.getElementById('sRollNo').value = '';
    document.getElementById('sRollNo').disabled = false;
    document.getElementById('sName').value = '';
    document.getElementById('sDept').value = '';
    document.getElementById('sSection').value = '';
    document.getElementById('sBatch').value = '';
    document.getElementById('sYear').value = '';
    openModal('studentModal');
}

function editStudent(id, rollNo, name, dept, section, batch, year) {
    document.getElementById('studentModalTitle').textContent = 'Edit Student';
    document.getElementById('studentSubmitBtn').textContent = 'Save Changes';
    document.getElementById('editStudentId').value = id;
    document.getElementById('sRollNo').value = rollNo;
    document.getElementById('sRollNo').disabled = true;
    document.getElementById('sName').value = name;
    document.getElementById('sDept').value = dept;
    document.getElementById('sSection').value = section;
    document.getElementById('sBatch').value = batch || '';
    document.getElementById('sYear').value = year;
    openModal('studentModal');
}

document.getElementById('studentForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const studentId = document.getElementById('editStudentId').value;
    const rollNo = document.getElementById('sRollNo').value.trim().toUpperCase();
    const name = document.getElementById('sName').value.trim();
    const dept = document.getElementById('sDept').value.trim();
    const section = document.getElementById('sSection').value.trim();
    const batch = document.getElementById('sBatch').value.trim().toUpperCase();
    const year = document.getElementById('sYear').value.trim();

    try {
        if (studentId) {
            // Update
            await apiCall(`/api/students/${studentId}`, 'PUT', {
                name, department: dept, section, batch, year,
            });
            showToast('Student updated', 'success');
        } else {
            // Create
            await apiCall('/api/students', 'POST', {
                roll_no: rollNo, name, department: dept, section, batch, year,
            });
            showToast('Student added', 'success');
        }
        closeModal('studentModal');
        setTimeout(() => window.location.reload(), 500);
    } catch (err) {
        // Error shown by apiCall
    }
});


// ── Student Import ──────────────────────────────────────────────

function showImportModal() {
    document.getElementById('importFile').value = '';
    openModal('importModal');
}

async function importStudents() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];
    if (!file) {
        showToast('Select a file first', 'error');
        return;
    }

    try {
        const result = await apiUpload('/api/students/import', file);
        showToast(`Imported: ${result.imported}, Skipped: ${result.skipped}`, 'success');
        closeModal('importModal');
        setTimeout(() => window.location.reload(), 600);
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Multi-Column Row Filtering & Search ──────────────────────────

function applyStudentFilters() {
    const searchQuery = (document.getElementById('studentSearch')?.value || '').trim().toUpperCase();
    const filterDept = (document.getElementById('filterDept')?.value || '').trim().toUpperCase();
    const filterSec = (document.getElementById('filterSection')?.value || '').trim().toUpperCase();
    const filterBatch = (document.getElementById('filterBatch')?.value || '').trim().toUpperCase();
    const filterYear = (document.getElementById('filterYear')?.value || '').trim().toUpperCase();

    const tbody = document.getElementById('studentsBody');
    if (!tbody) return;

    const rows = tbody.querySelectorAll('tr[data-student-id]');
    let visibleCount = 0;

    rows.forEach(row => {
        const text = row.textContent.toUpperCase();
        const rowDept = (row.getAttribute('data-dept') || '').toUpperCase();
        const rowSec = (row.getAttribute('data-section') || '').toUpperCase();
        const rowBatch = (row.getAttribute('data-batch') || '').toUpperCase();
        const rowYear = (row.getAttribute('data-year') || '').toUpperCase();

        const matchSearch = !searchQuery || text.includes(searchQuery);
        const matchDept = !filterDept || rowDept === filterDept;
        const matchSec = !filterSec || rowSec === filterSec;
        const matchBatch = !filterBatch || rowBatch === filterBatch;
        const matchYear = !filterYear || rowYear === filterYear;

        if (matchSearch && matchDept && matchSec && matchBatch && matchYear) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });

    // Update count badge
    const countBadge = document.getElementById('studentCountBadge');
    if (countBadge) {
        countBadge.textContent = `(${visibleCount} shown)`;
    }

    // Handle empty state row
    let emptyRow = document.getElementById('noFilterMatchesRow');
    if (visibleCount === 0) {
        if (!emptyRow) {
            emptyRow = document.createElement('tr');
            emptyRow.id = 'noFilterMatchesRow';
            emptyRow.innerHTML = `
                <td colspan="7">
                    <div class="empty-state" style="padding: var(--space-xl);">
                        <div class="icon"><span class="material-symbols-outlined" style="font-size: 3rem;">search_off</span></div>
                        <p>No students match your filter criteria.</p>
                        <button class="btn btn-ghost btn-sm mt-sm" onclick="resetStudentFilters()" style="display: inline-flex; align-items: center; gap: 4px;"><span class="material-symbols-outlined" style="font-size: 1rem;">close</span><span>Reset Filters</span></button>
                    </div>
                </td>`;
            tbody.appendChild(emptyRow);
        } else {
            emptyRow.style.display = '';
        }
    } else if (emptyRow) {
        emptyRow.style.display = 'none';
    }
}

function resetStudentFilters() {
    const searchInput = document.getElementById('studentSearch');
    const deptSelect = document.getElementById('filterDept');
    const secSelect = document.getElementById('filterSection');
    const batchSelect = document.getElementById('filterBatch');
    const yearSelect = document.getElementById('filterYear');

    if (searchInput) searchInput.value = '';
    if (deptSelect) deptSelect.value = '';
    if (secSelect) secSelect.value = '';
    if (batchSelect) batchSelect.value = '';
    if (yearSelect) yearSelect.value = '';

    applyStudentFilters();
}


async function deleteStudent(id, rollNo, name) {
    const displayName = name ? `${rollNo} (${name})` : rollNo;
    if (!confirm(`Are you sure you want to remove student ${displayName} from the directory?`)) {
        return;
    }

    try {
        const res = await apiCall(`/api/students/${id}`, 'DELETE');
        showToast(res?.message || 'Student removed successfully', 'success');
        const row = document.getElementById(`studentRow-${id}`);
        if (row) {
            row.style.opacity = '0';
            row.style.transform = 'scale(0.95)';
            row.style.transition = 'all 0.3s ease';
            setTimeout(() => {
                row.remove();
                applyStudentFilters();
            }, 300);
        } else {
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Event listeners & Initialization ────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('studentSearch');
    const deptSelect = document.getElementById('filterDept');
    const secSelect = document.getElementById('filterSection');
    const batchSelect = document.getElementById('filterBatch');
    const yearSelect = document.getElementById('filterYear');
    const searchBtn = document.getElementById('studentSearchBtn');

    searchInput?.addEventListener('input', applyStudentFilters);
    searchInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            applyStudentFilters();
        }
    });

    deptSelect?.addEventListener('change', applyStudentFilters);
    secSelect?.addEventListener('change', applyStudentFilters);
    batchSelect?.addEventListener('change', applyStudentFilters);
    yearSelect?.addEventListener('change', applyStudentFilters);
    searchBtn?.addEventListener('click', (e) => {
        e.preventDefault();
        applyStudentFilters();
    });

    // Run initial filter check
    applyStudentFilters();
});

document.addEventListener('click', (e) => {
    const editBtn = e.target.closest('[data-edit-student]');
    if (editBtn) {
        e.preventDefault();
        editStudent(
            editBtn.dataset.editStudent,
            editBtn.dataset.roll,
            editBtn.dataset.name,
            editBtn.dataset.dept,
            editBtn.dataset.section,
            editBtn.dataset.batch,
            editBtn.dataset.year
        );
    }

    const deleteBtn = e.target.closest('[data-delete-student]');
    if (deleteBtn) {
        e.preventDefault();
        deleteStudent(
            deleteBtn.dataset.deleteStudent,
            deleteBtn.dataset.roll,
            deleteBtn.dataset.name
        );
    }
});

function onEditStudentBtn(btn) {
    const d = btn.dataset;
    editStudent(d.studentId, d.roll, d.name, d.dept, d.section, d.batch, d.year);
}

function onDeleteStudentBtn(btn) {
    const d = btn.dataset;
    deleteStudent(d.studentId, d.roll, d.name);
}


// ── Clear / Reset Data in One Go (Year Change) ────────────────────

function openClearDataModal() {
    const pwdInput = document.getElementById('clearAdminPassword');
    if (pwdInput) pwdInput.value = '';
    openModal('clearDataModal');
}

async function submitClearData() {
    const pwdInput = document.getElementById('clearAdminPassword');
    const password = pwdInput ? pwdInput.value.trim() : '';

    if (!password) {
        showToast('Please enter the Admin Password to proceed.', 'warning');
        pwdInput?.focus();
        return;
    }

    const selectedTarget = document.querySelector('input[name="clearTarget"]:checked')?.value || 'all';
    const targetLabel = {
        'students': 'all students and associated records',
        'logs': 'all activity logs and class sessions',
        'all': 'everything (all students, logs, and sessions)'
    }[selectedTarget] || 'the selected data';

    if (!confirm(`⚠️ ARE YOU SURE?\n\nYou are about to clear ${targetLabel} in one go.\n\nThis action cannot be undone!`)) {
        return;
    }

    const btn = document.getElementById('clearDataSubmitBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="material-symbols-outlined">hourglass_empty</span><span>Clearing Data...</span>`;
    }

    try {
        const result = await apiCall('/api/admin/clear-data', 'POST', {
            password: password,
            target: selectedTarget,
        });

        showToast(result.message || 'Data cleared successfully!', 'success');
        closeModal('clearDataModal');

        // Reload page to reflect empty / updated directory
        setTimeout(() => {
            window.location.reload();
        }, 1000);
    } catch (err) {
        // Error handled and shown by apiCall
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span class="material-symbols-outlined">delete_forever</span><span>Clear Selected Data in One Go</span>`;
        }
    }
}


// ── Global Exports ──────────────────────────────────────────────
window.showAddModal = showAddModal;
window.editStudent = editStudent;
window.deleteStudent = deleteStudent;
window.onEditStudentBtn = onEditStudentBtn;
window.onDeleteStudentBtn = onDeleteStudentBtn;
window.showImportModal = showImportModal;
window.importStudents = importStudents;
window.applyStudentFilters = applyStudentFilters;
window.resetStudentFilters = resetStudentFilters;
window.openClearDataModal = openClearDataModal;
window.submitClearData = submitClearData;
