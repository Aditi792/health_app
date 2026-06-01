'use strict';

const API = '/api/patients';
let allPatients = [];
let deleteTargetId = null;

// ── Utilities ──────────────────────────────────────────────

function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = 'toast'; }, 3200);
}

function setLoading(loading) {
  const btn = document.getElementById('submitBtn');
  const label = btn.querySelector('.btn-label');
  const spinner = document.getElementById('submitSpinner');
  btn.disabled = loading;
  label.style.display = loading ? 'none' : '';
  spinner.style.display = loading ? '' : 'none';
}

function clearErrors() {
  document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
  document.querySelectorAll('input.error').forEach(el => el.classList.remove('error'));
}

function showErrors(errors) {
  const map = {
    'Full name': 'fullName',
    'Date of birth': 'dateOfBirth',
    'Email': 'email',
    'Glucose': 'glucose',
    'Haemoglobin': 'haemoglobin',
    'Cholesterol': 'cholesterol',
  };
  errors.forEach(err => {
    const field = Object.keys(map).find(k => err.toLowerCase().includes(k.toLowerCase()));
    if (field) {
      const id = map[field];
      const errEl = document.getElementById('err-' + id);
      const input = document.getElementById(id);
      if (errEl) errEl.textContent = err;
      if (input) input.classList.add('error');
    }
  });
}

// ── Colour classification for blood values ──

function glucoseClass(v) {
  if (v < 70 || v >= 126) return 'val-high';
  if (v >= 100) return 'val-warn';
  return 'val-normal';
}
function hgbClass(v) {
  if (v < 10 || v > 17.5) return 'val-high';
  if (v < 12 || v > 15.5) return 'val-warn';
  return 'val-normal';
}
function cholClass(v) {
  if (v >= 240) return 'val-high';
  if (v >= 200) return 'val-warn';
  return 'val-normal';
}

// ── Render Table ──────────────────────────────────────────

function renderTable(patients) {
  const tbody = document.getElementById('tableBody');
  const empty = document.getElementById('emptyState');

  if (!patients.length) {
    tbody.innerHTML = '';
    empty.style.display = 'flex';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = patients.map((p, idx) => `
    <tr data-id="${p.id}">
      <td style="color:var(--slate-400);font-size:12px">${idx + 1}</td>
      <td>
        <div class="patient-name">${escHtml(p.full_name)}</div>
      </td>
      <td>${formatDate(p.date_of_birth)}</td>
      <td><div class="patient-email">${escHtml(p.email)}</div></td>
      <td class="center">
        <span class="val-badge ${glucoseClass(p.glucose)}">${p.glucose}</span>
      </td>
      <td class="center">
        <span class="val-badge ${hgbClass(p.haemoglobin)}">${p.haemoglobin}</span>
      </td>
      <td class="center">
        <span class="val-badge ${cholClass(p.cholesterol)}">${p.cholesterol}</span>
      </td>
      <td>
        <div class="remarks-preview" onclick="openRemarks('${escAttr(p.full_name)}','${escAttr(p.remarks)}')" title="Click to read full remarks">
          ${escHtml(p.remarks || '—')}
        </div>
      </td>
      <td class="center">
        <div class="action-group">
          <button class="btn-action" onclick="editPatient(${p.id})" title="Edit">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn-action del" onclick="openDeleteModal(${p.id},'${escAttr(p.full_name)}')" title="Delete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}
function escAttr(str) {
  if (!str) return '';
  return String(str).replace(/'/g,"\\'").replace(/\n/g,' ');
}
function formatDate(d) {
  if (!d) return '';
  const parts = d.split('-');
  if (parts.length !== 3) return d;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

// ── Search / Filter ───────────────────────────────────────

function filterTable() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtered = q
    ? allPatients.filter(p =>
        p.full_name.toLowerCase().includes(q) ||
        p.email.toLowerCase().includes(q) ||
        (p.remarks || '').toLowerCase().includes(q))
    : allPatients;
  renderTable(filtered);
}

// ── Load Patients ─────────────────────────────────────────

async function loadPatients() {
  try {
    const res = await fetch(API);
    if (!res.ok) throw new Error('Server error');
    allPatients = await res.json();
    document.getElementById('totalCount').textContent = allPatients.length;
    filterTable();
  } catch (e) {
    toast('Failed to load patient records.', 'error');
  }
}

// ── Form Setup ────────────────────────────────────────────

function setMaxDob() {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('dateOfBirth').setAttribute('max', today);
}

function getFormData() {
  return {
    full_name: document.getElementById('fullName').value.trim(),
    date_of_birth: document.getElementById('dateOfBirth').value,
    email: document.getElementById('email').value.trim(),
    glucose: document.getElementById('glucose').value,
    haemoglobin: document.getElementById('haemoglobin').value,
    cholesterol: document.getElementById('cholesterol').value,
  };
}

function fillForm(p) {
  document.getElementById('patientId').value = p.id;
  document.getElementById('fullName').value = p.full_name;
  document.getElementById('dateOfBirth').value = p.date_of_birth;
  document.getElementById('email').value = p.email;
  document.getElementById('glucose').value = p.glucose;
  document.getElementById('haemoglobin').value = p.haemoglobin;
  document.getElementById('cholesterol').value = p.cholesterol;
}

function resetForm() {
  document.getElementById('patientId').value = '';
  document.getElementById('patientForm').reset();
  clearErrors();
  document.getElementById('formTitle').textContent = 'New Patient';
  document.getElementById('submitBtn').querySelector('.btn-label').textContent = 'Save & Predict';
  document.getElementById('cancelBtn').style.display = 'none';
  setMaxDob();
}

function cancelForm() {
  resetForm();
}

// ── Edit ──────────────────────────────────────────────────

async function editPatient(id) {
  try {
    const res = await fetch(`${API}/${id}`);
    if (!res.ok) throw new Error();
    const p = await res.json();
    fillForm(p);
    document.getElementById('formTitle').textContent = 'Edit Patient';
    document.getElementById('submitBtn').querySelector('.btn-label').textContent = 'Update & Re-predict';
    document.getElementById('cancelBtn').style.display = '';
    document.getElementById('formPanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch {
    toast('Could not load patient data.', 'error');
  }
}

// ── Submit (Create / Update) ──────────────────────────────

document.getElementById('patientForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearErrors();

  const id = document.getElementById('patientId').value;
  const data = getFormData();

  // Basic client-side presence check before hitting server
  const requiredFields = ['fullName','dateOfBirth','email','glucose','haemoglobin','cholesterol'];
  let hasEmpty = false;
  requiredFields.forEach(f => {
    const el = document.getElementById(f);
    if (!el.value.trim()) { el.classList.add('error'); hasEmpty = true; }
  });
  if (hasEmpty) { toast('Please fill in all required fields.', 'error'); return; }

  setLoading(true);

  try {
    const url  = id ? `${API}/${id}` : API;
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    const json = await res.json();

    if (!res.ok) {
      const errors = json.errors || [json.error || 'Unknown error.'];
      showErrors(errors);
      toast(errors[0], 'error');
      return;
    }

    toast(id ? 'Patient updated successfully.' : 'Patient added successfully.', 'success');
    resetForm();
    await loadPatients();
  } catch {
    toast('Network error. Please try again.', 'error');
  } finally {
    setLoading(false);
  }
});

// ── Delete ────────────────────────────────────────────────

function openDeleteModal(id, name) {
  deleteTargetId = id;
  document.getElementById('deletePatientName').textContent = name;
  document.getElementById('deleteModal').classList.add('open');
}
function closeDelete(e) {
  if (e && e.target !== document.getElementById('deleteModal')) return;
  document.getElementById('deleteModal').classList.remove('open');
  deleteTargetId = null;
}

document.getElementById('confirmDeleteBtn').addEventListener('click', async () => {
  if (!deleteTargetId) return;
  try {
    const res = await fetch(`${API}/${deleteTargetId}`, { method: 'DELETE' });
    const json = await res.json();
    if (!res.ok) { toast(json.error || 'Delete failed.', 'error'); return; }
    toast(json.message, 'success');
    document.getElementById('deleteModal').classList.remove('open');
    deleteTargetId = null;
    await loadPatients();
    // Clear form if we deleted the patient currently being edited
    resetForm();
  } catch {
    toast('Network error.', 'error');
  }
});

// ── Remarks Modal ─────────────────────────────────────────

function openRemarks(name, remarks) {
  document.getElementById('modalPatientName').textContent = name;
  document.getElementById('modalRemarks').textContent = remarks || 'No remarks available.';
  document.getElementById('remarksModal').classList.add('open');
}
function closeRemarks(e) {
  if (e && e.target !== document.getElementById('remarksModal')) return;
  document.getElementById('remarksModal').classList.remove('open');
}

// ── Export CSV ────────────────────────────────────────────

function exportCSV() {
  if (!allPatients.length) { toast('No patients to export.'); return; }
  const headers = ['ID','Full Name','Date of Birth','Email','Glucose (mg/dL)','Haemoglobin (g/dL)','Cholesterol (mg/dL)','Remarks','Created At'];
  const rows = allPatients.map(p => [
    p.id, p.full_name, p.date_of_birth, p.email,
    p.glucose, p.haemoglobin, p.cholesterol,
    `"${(p.remarks || '').replace(/"/g, '""')}"`,
    p.created_at
  ]);
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'health_predict_patients.csv';
  a.click(); URL.revokeObjectURL(url);
  toast('CSV exported.', 'success');
}

// ── Init ──────────────────────────────────────────────────

setMaxDob();
loadPatients();
