/**
 * Admin.js — Student management & general admin page logic
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
    document.getElementById('sYear').value = '';
    openModal('studentModal');
}

function editStudent(id, rollNo, name, dept, section, year) {
    document.getElementById('studentModalTitle').textContent = 'Edit Student';
    document.getElementById('studentSubmitBtn').textContent = 'Save Changes';
    document.getElementById('editStudentId').value = id;
    document.getElementById('sRollNo').value = rollNo;
    document.getElementById('sRollNo').disabled = true;
    document.getElementById('sName').value = name;
    document.getElementById('sDept').value = dept;
    document.getElementById('sSection').value = section;
    document.getElementById('sYear').value = year;
    openModal('studentModal');
}

document.getElementById('studentForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const studentId = document.getElementById('editStudentId').value;
    const rollNo = document.getElementById('sRollNo').value.trim();
    const name = document.getElementById('sName').value.trim();
    const dept = document.getElementById('sDept').value.trim();
    const section = document.getElementById('sSection').value.trim();
    const year = document.getElementById('sYear').value.trim();

    try {
        if (studentId) {
            // Update
            await apiCall(`/api/students/${studentId}`, 'PUT', {
                name, department: dept, section, year,
            });
            showToast('Student updated', 'success');
        } else {
            // Create
            await apiCall('/api/students', 'POST', {
                roll_no: rollNo, name, department: dept, section, year,
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
        setTimeout(() => window.location.reload(), 500);
    } catch (err) {
        // Error shown by apiCall
    }
}


// ── Student Search ──────────────────────────────────────────────

let searchTimeout = null;

async function searchStudents(query) {
    if (searchTimeout) clearTimeout(searchTimeout);

    searchTimeout = setTimeout(async () => {
        if (!query.trim()) {
            window.location.reload();
            return;
        }

        try {
            const result = await apiCall(`/api/students?search=${encodeURIComponent(query)}`);
            renderStudents(result.students);
        } catch (err) {
            // Error shown by apiCall
        }
    }, 300);
}

function renderStudents(students) {
    const tbody = document.getElementById('studentsBody');
    if (!tbody) return;

    if (students.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6">
                <div class="empty-state">
                    <div class="icon">🔍</div>
                    <p>No students match your search.</p>
                </div>
            </td></tr>`;
        return;
    }

    let html = '';
    for (const s of students) {
        html += `
        <tr data-student-id="${s.id}">
            <td><strong>${s.roll_no}</strong></td>
            <td>${s.name || '—'}</td>
            <td>${s.department || '—'}</td>
            <td>${s.section || '—'}</td>
            <td>${s.year || '—'}</td>
            <td>
                <button class="btn btn-ghost btn-sm"
                        data-edit-student="${s.id}"
                        data-roll="${s.roll_no}"
                        data-name="${s.name || ''}"
                        data-dept="${s.department || ''}"
                        data-section="${s.section || ''}"
                        data-year="${s.year || ''}">
                    ✏️
                </button>
            </td>
        </tr>`;
    }

    tbody.innerHTML = html;
}

// ── Delegated event listeners ───────────────────────────────────

document.addEventListener('click', (e) => {
    const editBtn = e.target.closest('[data-edit-student]');
    if (editBtn) {
        e.preventDefault();
        editStudent(
            editBtn.dataset.editStudent,
            editBtn.dataset.roll || '',
            editBtn.dataset.name || '',
            editBtn.dataset.dept || '',
            editBtn.dataset.section || '',
            editBtn.dataset.year || ''
        );
    }
});
