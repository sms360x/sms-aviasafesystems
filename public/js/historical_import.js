const API_URL = 'https://aviasafe-unified-platform.onrender.com';
let currentBatchId = null;
let currentFile = null;

const fileInput = document.getElementById('fileInput');
const dropzone = document.getElementById('dropzone');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const uploadBtn = document.getElementById('uploadBtn');
const browseBtn = document.getElementById('browseBtn');
const promoteBtn = document.getElementById('promoteBtn');
const cancelUploadBtn = document.getElementById('cancelUploadBtn');
const resetImportBtn = document.getElementById('resetImportBtn');

function showModal(title, message, type = "error") {
    const modal = document.getElementById('customAlertModal');
    const icon = document.getElementById('modalIcon');
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    if (type === "error") {
        icon.innerHTML = '<i class="fas fa-times-circle" style="color: #dc3545;"></i>';
    } else {
        icon.innerHTML = '<i class="fas fa-check-circle" style="color: #2e7d32;"></i>';
    }
    modal.style.display = 'flex';
}

function showStep(step) {
    document.querySelectorAll('.wizard-step').forEach(el => el.style.display = 'none');
    const el = document.getElementById(`import-step-${step}`);
    if (el) el.style.display = 'block';
}

async function getAuthHeaders() {
    const user = firebase.auth().currentUser;
    if (!user) throw new Error('Not authenticated');
    const token = await user.getIdToken();
    const appCheckToken = (typeof window.getAppCheckToken === 'function') ? await window.getAppCheckToken() : null;
    const headers = { 'Authorization': `Bearer ${token}` };
    if (appCheckToken) headers['X-Firebase-AppCheck'] = appCheckToken;
    return headers;
}

if (browseBtn) browseBtn.addEventListener('click', () => fileInput.click());
if (fileInput) fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        currentFile = e.target.files[0];
        fileName.textContent = currentFile.name;
        fileInfo.style.display = 'block';
    }
});

if (dropzone) {
    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            fileInput.dispatchEvent(new Event('change'));
        }
    });
}

if (uploadBtn) uploadBtn.addEventListener('click', async () => {
    if (!currentFile) return;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
    const formData = new FormData();
    formData.append('file', currentFile);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);
    try {
        const headers = await getAuthHeaders();
        let res;
        try {
            res = await fetch(`${API_URL}/api/v1/imports/master-logsheet`, {
                method: 'POST',
                headers: headers,
                body: formData,
                signal: controller.signal
            });
        } catch (netErr) {
            clearTimeout(timeoutId);
            if (netErr.name === 'AbortError') {
                throw new Error('The server took too long to respond. This may be due to a large file or a server error.');
            }
            throw new Error('Network error: ' + netErr.message);
        }
        clearTimeout(timeoutId);
        if (!res.ok) {
            const contentType = res.headers.get('content-type') || '';
            if (contentType.indexOf('application/json') !== -1) {
                const data = await res.json();
                throw new Error(data.detail || data.message || 'Request failed');
            } else {
                throw new Error(`Server error: ${res.status} ${res.statusText}`);
            }
        }
        const data = await res.json();
        currentBatchId = data.batch_id;
        renderPreview(data);
        showStep(2);
    } catch (err) {
        clearTimeout(timeoutId);
        showModal('Error', err.message, 'error');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload & Preview';
    }
});

function renderPreview(data) {
    document.getElementById('previewCount').textContent = data.staged_rows;
    const tbody = document.getElementById('previewTableBody');
    tbody.innerHTML = '';
    (data.preview || []).forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${row.row_number}</td><td>${(row.mapped_data?.description || 'No description').substring(0, 80)}</td><td><span class="badge badge-default">${(row.destination_tables || []).join(', ')}</span></td>`;
        tbody.appendChild(tr);
    });
    if (data.unmapped_columns && data.unmapped_columns.length) {
        document.getElementById('unmappedCols').textContent = data.unmapped_columns.join(', ');
        document.getElementById('unmappedWarning').style.display = 'block';
    } else {
        document.getElementById('unmappedWarning').style.display = 'none';
    }
}

if (promoteBtn) promoteBtn.addEventListener('click', async () => {
    if (!currentBatchId) return;
    promoteBtn.disabled = true;
    promoteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Importing...';
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);
    try {
        const headers = await getAuthHeaders();
        let res;
        try {
            res = await fetch(`${API_URL}/api/v1/imports/${currentBatchId}/promote`, {
                method: 'POST',
                headers: headers,
                signal: controller.signal
            });
        } catch (netErr) {
            clearTimeout(timeoutId);
            if (netErr.name === 'AbortError') {
                throw new Error('The server took too long to respond (30s). The import may still be processing in the background.');
            }
            throw new Error('Network error: ' + netErr.message);
        }
        clearTimeout(timeoutId);

        let data;
        try {
            data = await res.json();
        } catch (e) {
            const text = await res.text();
            throw new Error(`Server returned: ${res.status} ${res.statusText}\n${text.substring(0, 100)}`);
        }

        if (!res.ok) {
            throw new Error(data.detail || data.message || 'Promote failed');
        }

        document.getElementById('successCount').textContent = data.promoted_rows;
        showStep(3);
    } catch (err) {
        clearTimeout(timeoutId);
        showModal('Error', err.message, 'error');
    } finally {
        clearTimeout(timeoutId);
        promoteBtn.disabled = false;
        promoteBtn.textContent = 'Confirm & Import';
    }
});

if (cancelUploadBtn) cancelUploadBtn.addEventListener('click', () => { showStep(1); currentFile = null; currentBatchId = null; if (fileInput) fileInput.value = ''; if (fileInfo) fileInfo.style.display = 'none'; });
if (resetImportBtn) resetImportBtn.addEventListener('click', () => { currentFile = null; currentBatchId = null; if (fileInput) fileInput.value = ''; if (fileInfo) fileInfo.style.display = 'none'; showStep(1); });