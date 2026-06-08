document.addEventListener('DOMContentLoaded', () => {
    // --- Global functions for buttons ---
    window.deleteNeuroEntry = async (id) => {
        if (!confirm("¿Desea eliminar definitivamente este turno?")) return;
        const res = await fetch(`/api/neuro/${id}`, { method: 'DELETE' });
        if (res.ok) { loadNeuro(); } else { alert("Error al eliminar."); }
    };

    const NEURO_REPORT_WHATSAPP_MESSAGE = "\u{1F4E9} Hola, buen d\u00eda! Les enviamos el informe de la evaluaci\u00f3n neurocognitiva correspondiente. Quedamos atentos ante cualquier novedad o indicaci\u00f3n. Saludos cordiales";

    function isLocalHostName(hostname) {
        return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
    }

    function getPublicPdfBaseUrl() {
        if (!isLocalHostName(window.location.hostname)) {
            return window.location.origin;
        }

        throw new Error("El PDF esta guardado en esta PC. Para enviarlo por WhatsApp, adjuntalo desde el equipo local.");
    }

    function isAbsoluteUrl(value) {
        return /^https?:\/\//i.test((value || "").trim());
    }

    async function markNeuroWhatsappSent(item) {
        item.aviso_estado = 1;
        item.aviso_tipo = 'whatsapp';
        const res = await fetch(`/api/neuro/${item.id}/mark-whatsapp-sent`, {
            method: 'POST'
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "No se pudo marcar el informe como enviado.");
        }
    }

    async function shareNeuroReportViaWhatsApp(item) {
        try {
            const phone = item.telefono1 ? item.telefono1.replace(/\D/g, '') : "";
            if (!phone) {
                throw new Error("Este paciente no tiene telefono cargado.");
            }
            if (!item.link_pdf) {
                throw new Error("Primero hay que vincular un informe PDF a este paciente.");
            }

            const pdfUrl = isAbsoluteUrl(item.link_pdf)
                ? item.link_pdf.trim()
                : new URL(item.link_pdf, `${getPublicPdfBaseUrl()}/`).toString();
            const fullPhone = phone.startsWith('54') ? phone : `54${phone}`;
            const message = `${NEURO_REPORT_WHATSAPP_MESSAGE}\n\n${pdfUrl}`;
            window.open(`https://wa.me/${fullPhone}?text=${encodeURIComponent(message)}`, '_blank');

            await markNeuroWhatsappSent(item);
            return true;
        } catch (error) {
            alert(error.message || "No se pudo enviar el informe por WhatsApp.");
            return false;
        }
    }

    window.openWaModal = (itemStr) => {
        const item = JSON.parse(decodeURIComponent(itemStr));
        currentWaItem = item;
        document.getElementById('wa-patient-name').innerText = "Paciente: " + item.paciente;
        document.getElementById('wa-modal').style.display = 'block';
    };

    window.editNeuroEntry = (itemStr) => {
        const item = JSON.parse(decodeURIComponent(itemStr));
        fillNeuroForm(item);
    };

    window.openHistoryModal = async (id, name) => {
        document.getElementById('history-patient-name').innerText = "Cronograma: " + name;
        document.getElementById('history-patient-name').setAttribute('data-id', id);
        await loadHistory(id);
        document.getElementById('history-modal').style.display = 'block';
    };

    window.editPatient = (itemStr) => {
        const p = JSON.parse(decodeURIComponent(itemStr));
        document.querySelector('.nav-btn[data-tab="register-tab"]').click();
        document.getElementById('reg-id').value = p.id;
        document.getElementById('reg-nombre').value = p.apellido_nombre;
        document.getElementById('reg-dni').value = p.dni;
        document.getElementById('reg-nacimiento').value = p.fecha_nacimiento;
        document.getElementById('reg-domicilio').value = p.domicilio;
        document.getElementById('reg-localidad').value = p.localidad;
        document.getElementById('reg-telefono').value = p.telefono;
        document.getElementById('reg-beneficio').value = p.num_beneficio;
        document.getElementById('reg-hc').value = p.num_hc;
        document.getElementById('reg-anio').value = p.anio_vigencia;
        document.getElementById('reg-mes').value = p.mes_renovacion;
        document.getElementById('reg-f-inicio').value = p.fecha_inicio || "";
        document.getElementById('reg-f-fin').value = p.fecha_fin || "";
        isExistingPatient = true;
        document.querySelector('#register-tab h1').innerText = "Editar Registro";
    };

    window.deletePatientConfirm = async (id, name) => {
        if (!confirm(`¿Estás seguro de que deseas eliminar permanentemente a ${name}?\nEsta acción no se puede deshacer.`)) return;
        const res = await fetch(`/api/patients/${id}/delete`, { method: 'POST' });
        if (res.ok) { loadPatients(); } else { alert("Error al eliminar el paciente."); }
    };

    window.openRenovationModal = (id, name) => {
        document.getElementById('ren-patient-name').innerText = name;
        const now = new Date();
        document.getElementById('ren-year').value = now.getFullYear();
        document.getElementById('ren-month').value = now.getMonth() + 1;
        document.getElementById('ren-f-inicio').value = now.toISOString().split('T')[0];
        document.getElementById('ren-qty').value = 1;

        document.getElementById('confirm-renovate').onclick = async () => {
            const yearVal = parseInt(document.getElementById('ren-year').value);
            const monthVal = parseInt(document.getElementById('ren-month').value);
            const startDateStr = document.getElementById('ren-f-inicio').value;
            const qty = parseInt(document.getElementById('ren-qty').value);

            if (isNaN(yearVal)) return alert("Año inválido");
            if (!startDateStr) return alert("Seleccione fecha de inicio");

            const startDate = new Date(startDateStr + 'T00:00:00');

            for (let i = 0; i < qty; i++) {
                const currentStart = new Date(startDate);
                currentStart.setDate(startDate.getDate() + (i * 10)); // Every 10 days
                const currentEnd = new Date(currentStart);
                currentEnd.setDate(currentStart.getDate() + 9); // 10 days duration

                await fetch('/api/renovate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        patient_id: id,
                        new_year: yearVal,
                        new_month: monthVal,
                        fecha_inicio: currentStart.toISOString().split('T')[0],
                        fecha_fin: currentEnd.toISOString().split('T')[0]
                    })
                });
            }
            document.getElementById('renovate-modal').style.display = 'none';
            loadPatients();
            alert(`Se han generado ${qty} turno(s) automáticamente.`);
        };
        document.getElementById('renovate-modal').style.display = 'block';
    };

    window.deleteHistoryEntry = async (id, pId) => {
        console.log("Deleting history entry:", id, "for patient:", pId);
        if (confirm("¿Desea eliminar este registro del historial?")) {
            try {
                const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
                if (res.ok) { await loadHistory(pId); }
                else { alert("Error al eliminar el registro."); }
            } catch (err) { console.error("Delete error:", err); }
        }
    };

    // --- Elements ---
    const mainSearch = document.getElementById('main-search');
    const neuroSearch = document.getElementById('neuro-search');
    const patientsBody = document.getElementById('patients-body');
    const registerForm = document.getElementById('register-form');
    const panelMeta = document.getElementById('panel-meta');
    const panelSummary = document.getElementById('panel-summary');
    const panelMonthlyBody = document.getElementById('panel-monthly-body');
    const panelWeeklyBody = document.getElementById('panel-weekly-body');
    const panelMethodsBody = document.getElementById('panel-methods-body');
    const panelNotes = document.getElementById('panel-notes');
    const refreshPanelBtn = document.getElementById('refresh-panel-btn');
    const top25Body = document.getElementById('top25-body');
    const top25Meta = document.getElementById('top25-meta');
    const refreshTop25Btn = document.getElementById('refresh-top25-btn');
    const top25LeaderName = document.getElementById('top25-leader-name');
    const top25LeaderDetail = document.getElementById('top25-leader-detail');
    const intersofticBody = document.getElementById('intersoftic-body');
    const intersofticContainer = document.getElementById('intersoftic-container');
    const intersofticMeta = document.getElementById('intersoftic-meta');
    const intersofticSummary = document.getElementById('intersoftic-summary');
    const refreshIntersofticBtn = document.getElementById('refresh-intersoftic-btn');
    const intersofticBranchTabs = document.getElementById('intersoftic-branch-tabs');
    const auditMeta = document.getElementById('audit-meta');
    const auditSummary = document.getElementById('audit-summary');
    const auditContainer = document.getElementById('audit-container');
    const refreshAuditBtn = document.getElementById('refresh-audit-btn');
    const auditBranchTabs = document.getElementById('audit-branch-tabs');
    const auditSearch = document.getElementById('audit-search');
    const professionalsBody = document.getElementById('professionals-body');
    const professionalsSummary = document.getElementById('professionals-summary');
    const professionalsCount = document.getElementById('professionals-count');
    const professionalsRefreshBtn = document.getElementById('professionals-refresh-btn');
    const professionalsBranchTabs = document.getElementById('professionals-branch-tabs');
    const professionalsRoleFilter = document.getElementById('professionals-role-filter');
    const professionalModal = document.getElementById('professional-modal');
    const professionalNewBtn = document.getElementById('professional-new-btn');
    const professionalSaveBtn = document.getElementById('professional-save-btn');
    const professionalClearBtn = document.getElementById('professional-clear-btn');
    const professionalDeleteBtn = document.getElementById('professional-delete-btn');
    let intersofticDataCache = null;
    let selectedIntersofticBranch = 'all';
    let auditDataCache = null;
    let selectedAuditBranch = 'all';
    let professionalsDataCache = [];
    let selectedProfessionalsBranch = "";
    const navBtns = document.querySelectorAll('.nav-btn');
    const tabs = document.querySelectorAll('.tab-content');
    const syncBtn = document.getElementById('sync-btn');
    const accessOverlay = document.getElementById('access-overlay');
    const appShell = document.getElementById('app-shell');
    const accessForm = document.getElementById('access-login-form');
    const accessError = document.getElementById('access-error');
    const logoutBtn = document.getElementById('logout-btn');
    const allowedTabs = ['intersoftic-tab', 'audit-tab'];
    const credentials = {
        CENTROSCRI: 'CENTROSCRI',
        AAZOCAR: 'ARTURO',
        crisanmiguel: 'sarmiento2283',
        crimerlo: 'rosas855',
        criituzaingo: 'soler602'
    };
    let isExistingPatient = false;

    function applyAccessMode(isLoggedIn) {
        if (!isLoggedIn) {
            if (accessOverlay) accessOverlay.style.display = 'flex';
            if (appShell) appShell.style.display = 'none';
            navBtns.forEach(btn => btn.style.display = 'none');
            if (logoutBtn) logoutBtn.style.display = 'none';
            return;
        }
        if (accessOverlay) accessOverlay.style.display = 'none';
        if (appShell) appShell.style.display = 'flex';
        navBtns.forEach(btn => {
            const tabId = btn.getAttribute('data-tab');
            btn.style.display = allowedTabs.includes(tabId) ? '' : 'none';
        });
        if (logoutBtn) logoutBtn.style.display = '';
        const allowedButton = document.querySelector('.nav-btn[data-tab="intersoftic-tab"]');
        if (allowedButton) allowedButton.click();
    }

    function checkAccess() {
        const saved = localStorage.getItem('cri-access');
        if (saved === 'ok') {
            applyAccessMode(true);
            return;
        }
        applyAccessMode(false);
    }

    if (accessForm) {
        accessForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const user = document.getElementById('access-user').value.trim();
            const pass = document.getElementById('access-pass').value.trim();
            if (credentials[user] && credentials[user] === pass) {
                localStorage.setItem('cri-access', 'ok');
                if (accessError) accessError.textContent = '';
                document.getElementById('access-user').value = '';
                document.getElementById('access-pass').value = '';
                applyAccessMode(true);
            } else {
                if (accessError) accessError.textContent = 'Usuario o contraseña incorrectos.';
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('cri-access');
            applyAccessMode(false);
            if (accessError) accessError.textContent = '';
        });
    }

    checkAccess();

    if (syncBtn) {
        syncBtn.onclick = async () => {
            const overlay = document.getElementById('sync-overlay');
            const progressBar = document.getElementById('sync-progress-bar');
            const syncMsg = document.getElementById('sync-msg');
            const syncTitle = document.getElementById('sync-title');

            overlay.style.display = 'flex';
            progressBar.style.width = '0%';
            syncMsg.innerText = 'Iniciando sincronización...';
            syncTitle.innerText = 'Sincronizando';

            try {
                const startRes = await fetch('/api/sync', { method: 'POST' });
                if (!startRes.ok) throw new Error("No se pudo iniciar");

                // Polling
                const poll = setInterval(async () => {
                    try {
                        const statusRes = await fetch('/api/sync/status');
                        const data = await statusRes.json();
                        
                        progressBar.style.width = data.progress + '%';
                        syncMsg.innerText = data.message;

                        if (data.status === 'completed') {
                            clearInterval(poll);
                            syncTitle.innerText = '¡Completado!';
                            setTimeout(() => {
                                overlay.style.display = 'none';
                                loadPatients();
                                loadPanelDashboard();
                                loadTop25Dashboard();
                            }, 1500);
                        } else if (data.status === 'error') {
                            clearInterval(poll);
                            alert("Error: " + data.message);
                            overlay.style.display = 'none';
                        }
                    } catch (e) {
                        console.error("Polling error", e);
                    }
                }, 1000);

            } catch (e) {
                alert("Error de conexión al iniciar sync");
                overlay.style.display = 'none';
            }
        };
    }

    const fetchEmailsBtn = document.getElementById('fetch-emails-btn');
    const neuroDedupeBtn = document.getElementById('neuro-dedupe-btn');
    if (fetchEmailsBtn) {
        fetchEmailsBtn.onclick = async () => {
            fetchEmailsBtn.disabled = true;
            fetchEmailsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Buscando...</span>';
            try {
                const res = await fetch('/api/fetch-emails', { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    let msg = `Sincronización Mails:\n📄 Descargados: ${data.processed}\n🔗 Vinculados: ${data.matched}`;
                    if (data.details && data.details.length > 0) {
                        msg += `\n\nDetalles:\n` + data.details.join('\n');
                    }
                    alert(msg);
                    loadNeuro();
                } else {
                    alert("Error: " + (data.detail || "Error al sincronizar correos"));
                }
            } catch (e) { alert("Error de red o conexión IMAP."); }
            finally {
                fetchEmailsBtn.disabled = false;
                fetchEmailsBtn.innerHTML = '<i class="fas fa-inbox"></i> Buscar Correos';
            }
        };
    }

    if (neuroDedupeBtn) {
        neuroDedupeBtn.onclick = async () => {
            if (!confirm("¿Desea limpiar PDFs duplicados por paciente (mismo nombre) en archivos_neuro?\nSe conservará el más nuevo y el resto se moverá a _duplicados como backup.")) return;
            neuroDedupeBtn.disabled = true;
            const previousHTML = neuroDedupeBtn.innerHTML;
            neuroDedupeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            try {
                const res = await fetch('/api/neuro/dedupe-pdfs', { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    alert("No se pudo limpiar duplicados. " + (data.detail || "Intente nuevamente."));
                    return;
                }
                let msg = `Duplicados encontrados: ${data.duplicates_found || 0}\nMovidos: ${data.moved || 0}\nActualizados en Neuro: ${data.updated_neuro || 0}`;
                if (data.backup_dir) msg += `\nBackup: ${data.backup_dir}`;
                alert(msg);
                await loadNeuroFresh();
            } catch (e) {
                alert("No se pudo limpiar duplicados. " + (e.message || ""));
            } finally {
                neuroDedupeBtn.disabled = false;
                neuroDedupeBtn.innerHTML = previousHTML;
            }
        };
    }

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            if (tabId) {
                navBtns.forEach(b => b.classList.remove('active'));
                tabs.forEach(t => t.classList.remove('active'));
                btn.classList.add('active');
                const target = document.getElementById(tabId);
                if (target) target.classList.add('active');
            }
            if (tabId === 'register-tab') {
                if (!isExistingPatient) {
                    registerForm.reset();
                    document.getElementById('reg-id').value = "";
                    document.querySelector('#register-tab h1').innerText = "Nuevo Registro";
                    updateNextHc();
                }
            } else { isExistingPatient = false; }
            if (tabId === 'neuro-tab') loadNeuro();
            if (tabId === 'agenda-tab') loadAgenda();
            if (tabId === 'hd-tab') loadHD();
            if (tabId === 'panel-tab') loadPanelDashboard({ syncOffice: false, silentSync: true });
            if (tabId === 'staff-tab') loadStaffTab({ keepStaff: false });
            if (tabId === 'top25-tab') loadTop25Dashboard();
            if (tabId === 'intersoftic-tab') loadIntersofticStats();
            if (tabId === 'audit-tab') loadIntersofticAudit();
            if (tabId === 'professionals-tab') loadProfessionals();
        });
    });

    // Auto-click initialization moved to the end of the script to avoid ReferenceError
    // with lexical declarations (const/let) used in tab loading functions.


    async function loadHistory(pId) {
        console.log("Loading history for patient:", pId);
        const res = await fetch(`/api/history/${pId}?t=${Date.now()}`);
        const data = await res.json();
        const body = document.getElementById('history-body');
        body.innerHTML = '';
        if (data.length === 0) {
            body.innerHTML = '<tr><td colspan="5" style="text-align:center; opacity:0.6;">Sin registros previos</td></tr>';
            return;
        }
        data.forEach(h => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><span class="badge badge-hc">${h.mes}/${h.anio}</span></td><td>${formatDateToES(h.fecha_inicio)}</td><td>${formatDateToES(h.fecha_fin)}</td><td>${h.hora || '-'}</td><td><button class="btn-icon delete-hist-btn" style="color: #ff3b30" onclick="deleteHistoryEntry(${h.id}, ${pId})"><i class="fas fa-trash"></i></button></td>`;
            body.appendChild(tr);
        });
    }

    const neuroMonthlyContainer = document.getElementById('neuro-monthly-container');
    const neuroMonthFilter = document.getElementById('neuro-month-filter');
    const neuroModal = document.getElementById('neuro-modal');
    const neuroForm = document.getElementById('neuro-form');
    const neuroHoraInput = document.getElementById('neuro-hora');
    const waModal = document.getElementById('wa-modal');
    let currentWaItem = null;
    const neuroHourOptions = ["08:15", "09:00", "09:45", "10:30", "11:15", "12:00", "12:45", "13:30", "14:15", "15:00", "15:45", "16:30", "17:15"];

    function ensureNeuroHourOption(value) {
        if (!neuroHoraInput || !value) return;
        const normalizedValue = String(value).slice(0, 5);
        const exists = Array.from(neuroHoraInput.options).some(option => option.value === normalizedValue);
        if (exists) return;
        const option = document.createElement('option');
        option.value = normalizedValue;
        option.textContent = normalizedValue;
        neuroHoraInput.appendChild(option);
    }

    function populateNeuroHourOptions(selectedValue = "08:15") {
        if (!neuroHoraInput) return;
        neuroHoraInput.innerHTML = "";
        neuroHourOptions.forEach(hour => {
            const option = document.createElement('option');
            option.value = hour;
            option.textContent = hour;
            neuroHoraInput.appendChild(option);
        });
        ensureNeuroHourOption(selectedValue);
        neuroHoraInput.value = String(selectedValue || "08:15").slice(0, 5);
    }

    const now = new Date();
    populateNeuroHourOptions();
    neuroMonthFilter.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    neuroMonthFilter.onchange = () => { neuroSearch.value = ""; loadNeuro(); };
    neuroSearch.oninput = (e) => { if (e.target.value.length > 2 || e.target.value.length === 0) loadNeuro(); };

    const neuroDniInput = document.getElementById('neuro-dni');
    const neuroDniStatus = document.getElementById('neuro-dni-status');
    let neuroDniDebounceTimer = null;
    let neuroDniAbortController = null;
    let neuroLastLookupDni = "";

    function setNeuroDniStatus(message = "", statusClass = "") {
        if (!neuroDniStatus) return;
        neuroDniStatus.textContent = message;
        neuroDniStatus.classList.remove('dni-loading', 'dni-found', 'dni-notfound', 'dni-error');
        if (statusClass) neuroDniStatus.classList.add(statusClass);
    }

    function normalizeDni(value) {
        return String(value || "").replace(/\D/g, "");
    }

    function applyPatientToNeuroForm(patient, { overwrite = false } = {}) {
        const mappings = [
            ['neuro-paciente', patient.apellido_nombre],
            ['neuro-fecha-nacimiento', patient.fecha_nacimiento || ""],
            ['neuro-domicilio', patient.domicilio || ""],
            ['neuro-localidad', patient.localidad || ""],
            ['neuro-tlf1', patient.telefono || ""],
            ['neuro-tlf2', patient.telefono2 || ""],
            ['neuro-beneficio', patient.num_beneficio || ""],
        ];

        mappings.forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (overwrite || !String(el.value || "").trim()) el.value = value;
        });
    }

    function resetNeuroDniLookupState() {
        neuroLastLookupDni = "";
        if (neuroDniDebounceTimer) {
            clearTimeout(neuroDniDebounceTimer);
            neuroDniDebounceTimer = null;
        }
        if (neuroDniAbortController) {
            neuroDniAbortController.abort();
            neuroDniAbortController = null;
        }
        if (neuroDniInput) neuroDniInput.style.borderColor = '';
        setNeuroDniStatus("", "");
    }

    async function lookupNeuroPatientByDni(dni, { force = false } = {}) {
        if (!neuroDniInput) return;
        if (!dni || dni.length < 7) return;
        if (!force && dni === neuroLastLookupDni) return;
        neuroLastLookupDni = dni;

        if (neuroDniAbortController) neuroDniAbortController.abort();
        neuroDniAbortController = new AbortController();

        setNeuroDniStatus("Buscando DNI...", "dni-loading");
        neuroDniInput.style.borderColor = '#f59e0b';

        try {
            const res = await fetch(`/api/patients/${dni}`, { signal: neuroDniAbortController.signal });
            if (res.ok) {
                const p = await res.json();
                const neuroIdEl = document.getElementById('neuro-id');
                const isEdit = !!String(neuroIdEl ? neuroIdEl.value : "");
                applyPatientToNeuroForm(p, { overwrite: !isEdit });
                neuroDniInput.style.borderColor = '#25d366';
                setNeuroDniStatus("Paciente encontrado. Datos autocompletados.", "dni-found");
                return;
            }
            if (res.status === 404) {
                neuroDniInput.style.borderColor = '#ef4444';
                setNeuroDniStatus("DNI no encontrado. Completá los datos manualmente.", "dni-notfound");
                return;
            }

            neuroLastLookupDni = "";
            neuroDniInput.style.borderColor = '#2563eb';
            setNeuroDniStatus("No se pudo validar el DNI. Intentá nuevamente.", "dni-error");
        } catch (err) {
            if (err && err.name === 'AbortError') return;
            neuroLastLookupDni = "";
            neuroDniInput.style.borderColor = '#2563eb';
            setNeuroDniStatus("Error de conexión al buscar el DNI.", "dni-error");
        }
    }

    function scheduleNeuroDniLookup() {
        if (!neuroDniInput) return;
        const dni = normalizeDni(neuroDniInput.value);
        if (neuroDniInput.value !== dni) neuroDniInput.value = dni;

        neuroDniInput.style.borderColor = '';
        setNeuroDniStatus("", "");

        if (neuroDniDebounceTimer) clearTimeout(neuroDniDebounceTimer);
        if (neuroDniAbortController) {
            neuroDniAbortController.abort();
            neuroDniAbortController = null;
        }

        if (!dni || dni.length < 7) {
            neuroLastLookupDni = "";
            return;
        }

        neuroDniDebounceTimer = setTimeout(() => {
            void lookupNeuroPatientByDni(dni);
        }, 450);
    }

    if (neuroDniInput) {
        neuroDniInput.addEventListener('input', scheduleNeuroDniLookup);
        neuroDniInput.addEventListener('blur', () => {
            if (neuroDniDebounceTimer) {
                clearTimeout(neuroDniDebounceTimer);
                neuroDniDebounceTimer = null;
            }
            const dni = normalizeDni(neuroDniInput.value);
            neuroDniInput.value = dni;
            void lookupNeuroPatientByDni(dni, { force: true });
        });
        neuroDniInput.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            const dni = normalizeDni(neuroDniInput.value);
            neuroDniInput.value = dni;
            void lookupNeuroPatientByDni(dni, { force: true });
        });
    }

    document.querySelectorAll('.whatsapp-option').forEach(opt => {
        opt.onclick = async () => {
            const type = opt.getAttribute('data-type');
            const fechaObj = new Date(currentWaItem.fecha + 'T00:00:00');
            const fechaLarga = fechaObj.toLocaleDateString('es-AR', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' });
            let msg = "";
            if (type === 'turno') msg = `📅 Buen día, le informamos que su turno para la evaluación de neurocognitivo fue programado para el ${fechaLarga} a las ${currentWaItem.hora} hs.\n\nLe pedimos que ese día llegue unos minutos antes.`;
            else if (type === 'informe') msg = `📄 Hola, buen día! Les enviamos el informe de la evaluación neurocognitiva correspondiente. Quedamos atentos ante cualquier novedad o indicación.\n\nSaludos cordiales.`;
            else if (type === 'orden') msg = `Le informamos que la profesional dejó para usted una orden médica para realizar un tratamiento neurocognitivo.\n\nPuede acercarse a retirarla en nuestra sede (Domingo F. Sarmiento 2283, San Miguel), de lunes a viernes de 8:00 a 16:00 hs.\n\nSaludos cordiales,\nCentro de Rehabilitación CRI`;
            const phone = currentWaItem.telefono1 ? currentWaItem.telefono1.replace(/\D/g, '') : "";
            const url = `https://wa.me/${phone.startsWith('54') ? phone : '54' + phone}?text=${encodeURIComponent(msg)}`;
            window.open(url, '_blank');
            waModal.style.display = 'none';
            currentWaItem.aviso_estado = 1; currentWaItem.aviso_tipo = 'whatsapp';
            await fetch(`/api/neuro/${currentWaItem.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(currentWaItem) });
            loadNeuro();
        };
    });

    const waInformeOption = document.querySelector('.whatsapp-option[data-type="informe"]');
    if (waInformeOption) {
        waInformeOption.onclick = async () => {
            waModal.style.display = 'none';
            const sent = await shareNeuroReportViaWhatsApp(currentWaItem);
            if (sent) {
                loadNeuro();
            }
        };
    }

    const neuroAttendanceLabels = { pendiente: 'Pendiente', asistio: 'Asistió', falto: 'Faltó' };

    function getNeuroAttendanceBadge(status) {
        const normalizedStatus = (status || 'pendiente').toLowerCase();
        const label = neuroAttendanceLabels[normalizedStatus] || neuroAttendanceLabels.pendiente;
        return `<span class="attendance-badge attendance-${normalizedStatus}">${label}</span>`;
    }

    async function loadNeuro() {
        const month = neuroMonthFilter.value;
        const query = neuroSearch.value;
        const url = query.length > 0 ? `/api/neuro/search?query=${query}` : `/api/neuro/month?month=${month}`;
        const res = await fetch(url);
        const data = await res.json();

        neuroMonthlyContainer.innerHTML = '';
        if (data.length === 0) {
            neuroMonthlyContainer.innerHTML = '<div class="glass" style="padding: 20px; text-align: center;">No se encontraron resultados.</div>';
            return;
        }

        const grouped = {};
        data.forEach(p => {
            if (!grouped[p.fecha]) grouped[p.fecha] = [];
            grouped[p.fecha].push(p);
        });

        Object.keys(grouped).sort().forEach(date => {
            const dayRecords = grouped[date];
            const dateObj = new Date(date + 'T00:00:00');
            const dateLong = dateObj.toLocaleDateString('es-AR', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' });
            const groupDiv = document.createElement('div');
            groupDiv.className = 'day-group';
            groupDiv.innerHTML = `
                <div class="day-header"><h3>${dateLong}</h3><span>${dayRecords.length} Paciente(s)</span></div>
                <div class="table-container">
                    <table class="glass-table" style="width: 100%;">
                        <thead><tr><th>Hora</th><th>Paciente</th><th>HC</th><th>Nº OP</th><th>Cápita</th><th>Asistencia</th><th>Aviso</th><th>WhatsApp</th><th>Acciones</th></tr></thead>
                        <tbody>${dayRecords.map(p => {
                const avisadoIcon = p.aviso_estado ? 'fa-check-circle estado-avisado' : 'fa-clock estado-pendiente';
                const avisoHTML = p.aviso_tipo ? `<span class="aviso-badge aviso-${p.aviso_tipo}">${p.aviso_tipo}</span>` : '-';
                const hcBadge = p.num_hc ? `<span class="badge badge-hc">${p.num_hc}</span>` : '<small style="color:#aaa">No reg.</small>';
                const attendanceHTML = getNeuroAttendanceBadge(p.asistencia);
                const itemStr = encodeURIComponent(JSON.stringify(p));
                const pdfLink = p.link_pdf ? `<a href="${p.link_pdf}" target="_blank" class="btn-icon" style="color:#ff3b30" title="Ver Informe PDF"><i class="fas fa-file-pdf"></i></a>` : '';
                const sendReportBtn = p.link_pdf ? `<button class="btn-icon" onclick="sendNeuroReport('${itemStr}')" title="Preparar envío de informe" style="color:#2563eb"><i class="fas fa-paper-plane"></i></button>` : '';
                return `<tr><td><strong>${p.hora}</strong></td><td><strong>${p.paciente}</strong><br><small>DNI: ${p.dni || '-'}</small></td><td>${hcBadge}</td><td><span class="badge badge-hc">${p.num_op || '-'}</span></td><td><small>${p.capita || '-'}</small></td><td>${attendanceHTML}</td><td>${avisoHTML} <i class="fas ${avisadoIcon}"></i></td><td><button class="btn-icon btn-whatsapp" onclick="openWaModal('${itemStr}')"><i class="fab fa-whatsapp"></i></button></td><td>${pdfLink}<button class="btn-icon" onclick="shiftNeuroEntry('${itemStr}', -1)" title="Mover 45 min antes" style="color:#475467"><i class="fas fa-arrow-up"></i></button><button class="btn-icon" onclick="shiftNeuroEntry('${itemStr}', 1)" title="Mover 45 min después" style="color:#475467"><i class="fas fa-arrow-down"></i></button><button class="btn-icon" onclick="attachReportToNeuro(${p.id})" title="Adjuntar informe" style="color:#0d6efd"><i class="fas fa-file-upload"></i></button>${sendReportBtn}<button class="btn-icon edit-neuro" onclick="editNeuroEntry('${itemStr}')" title="Editar"><i class="fas fa-edit"></i></button><button class="btn-icon delete-neuro" onclick="deleteNeuroEntry(${p.id})" style="color: #ff3b30" title="Eliminar"><i class="fas fa-trash"></i></button></td></tr>`;
            }).join('')}</tbody>
                    </table>
                </div>`;
            neuroMonthlyContainer.appendChild(groupDiv);
        });

        void autoSyncNeuroReports();
    }
    window.loadNeuro = loadNeuro;

    async function submitNeuroForm(e) {
        e.preventDefault();
        const id = document.getElementById('neuro-id').value;
        const data = {
            fecha: document.getElementById('neuro-fecha').value,
            hora: document.getElementById('neuro-hora').value,
            paciente: document.getElementById('neuro-paciente').value,
            dni: document.getElementById('neuro-dni').value,
            fecha_nacimiento: document.getElementById('neuro-fecha-nacimiento').value,
            domicilio: document.getElementById('neuro-domicilio').value,
            localidad: document.getElementById('neuro-localidad').value,
            telefono1: document.getElementById('neuro-tlf1').value,
            telefono2: document.getElementById('neuro-tlf2').value,
            beneficio: document.getElementById('neuro-beneficio').value,
            num_op: document.getElementById('neuro-op').value,
            fecha_op: document.getElementById('neuro-fecha-op').value,
            capita: document.getElementById('neuro-capita').value,
            link_pdf: document.getElementById('neuro-link').value,
            observaciones: document.getElementById('neuro-obs').value,
            asistencia: document.getElementById('neuro-asistencia').value,
            aviso_tipo: neuroForm.querySelector('input[name="aviso-tipo"]:checked')?.value || "",
            aviso_estado: document.getElementById('neuro-avisado').checked ? 1 : 0
        };

        const res = await fetch(id ? `/api/neuro/${id}` : '/api/neuro', {
            method: id ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            alert("No se pudo guardar la asistencia en Neuro. " + (errorData.detail || "Intente nuevamente."));
            return;
        }

        neuroModal.style.display = 'none';
        await loadNeuro();
    }
    neuroForm.onsubmit = submitNeuroForm;

    function fillNeuroForm(item) {
        document.getElementById('neuro-id').value = item.id;
        document.getElementById('neuro-fecha').value = item.fecha;
        populateNeuroHourOptions(item.hora || "08:15");
        document.getElementById('neuro-paciente').value = item.paciente;
        document.getElementById('neuro-dni').value = item.dni || "";
        document.getElementById('neuro-fecha-nacimiento').value = item.fecha_nacimiento || "";
        document.getElementById('neuro-domicilio').value = item.domicilio || "";
        document.getElementById('neuro-localidad').value = item.localidad || "";
        document.getElementById('neuro-tlf1').value = item.telefono1 || "";
        document.getElementById('neuro-tlf2').value = item.telefono2 || "";
        document.getElementById('neuro-beneficio').value = item.beneficio || "";
        document.getElementById('neuro-op').value = item.num_op || "";
        document.getElementById('neuro-fecha-op').value = item.fecha_op || "";
        document.getElementById('neuro-capita').value = item.capita || "";
        document.getElementById('neuro-link').value = item.link_pdf || "";
        document.getElementById('neuro-obs').value = item.observaciones || "";
        document.getElementById('neuro-asistencia').value = item.asistencia || 'pendiente';
        document.getElementById('neuro-avisado').checked = !!item.aviso_estado;
        neuroForm.querySelectorAll('input[name="aviso-tipo"]').forEach(radioBtn => { radioBtn.checked = false; });
        const radio = neuroForm.querySelector(`input[name="aviso-tipo"][value="${item.aviso_tipo}"]`);
        if (radio) radio.checked = true;
        resetNeuroDniLookupState();
        document.getElementById('neuro-modal-title').innerText = "Editar Turno Neurocognitivo";
        neuroModal.style.display = 'block';
    }
    window.editNeuroEntry = (itemStr) => {
        const item = JSON.parse(decodeURIComponent(itemStr));
        fillNeuroForm(item);
    };

    const openNeuroModal = () => {
        neuroForm.reset();
        document.getElementById('neuro-id').value = "";
        document.getElementById('neuro-fecha').value = new Date().toISOString().split('T')[0];
        populateNeuroHourOptions("08:15");
        document.getElementById('neuro-fecha-nacimiento').value = "";
        document.getElementById('neuro-domicilio').value = "";
        document.getElementById('neuro-localidad').value = "";
        resetNeuroDniLookupState();
        neuroForm.querySelectorAll('input[name="aviso-tipo"]').forEach(radioBtn => { radioBtn.checked = false; });
        document.getElementById('neuro-avisado').checked = false;
        document.getElementById('neuro-modal-title').innerText = "Nuevo Turno Neurocognitivo";
        neuroModal.style.display = 'block';
        setTimeout(() => {
            if (neuroDniInput) {
                neuroDniInput.focus();
                neuroDniInput.select();
            }
        }, 0);
    };
    document.getElementById('add-neuro-btn').onclick = openNeuroModal;

    const neuroReportFilesInput = document.getElementById('neuro-report-files');
    const neuroSingleReportFileInput = document.getElementById('neuro-single-report-file');
    let pendingNeuroReportId = null;
    let neuroAutoSyncPromise = null;
    let lastNeuroAutoSyncAt = 0;

    function setNeuroReportsButtonState(isBusy = false) {
        if (!fetchEmailsBtn) return;
        fetchEmailsBtn.disabled = isBusy;
        fetchEmailsBtn.innerHTML = isBusy
            ? '<i class="fas fa-spinner fa-spin"></i> Sincronizando...'
            : '<i class="fas fa-folder-open"></i> Sincronizar Informes';
    }

    function readFileAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = String(reader.result || "");
                const base64 = result.includes(",") ? result.split(",")[1] : result;
                resolve(base64);
            };
            reader.onerror = () => reject(new Error(`No se pudo leer ${file.name}`));
            reader.readAsDataURL(file);
        });
    }

    async function importNeuroFiles(files, neuroId = null) {
        if (!files || files.length === 0) return;

        const payloadFiles = await Promise.all(Array.from(files).map(async (file) => ({
            filename: file.name,
            content_base64: await readFileAsBase64(file),
            neuro_id: neuroId
        })));

        const res = await fetch('/api/neuro/import-reports', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: payloadFiles })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            alert("No se pudo importar el informe. " + (data.detail || "Intente nuevamente."));
            return;
        }

        let msg = `Informes procesados: ${data.processed || 0}\nVinculados: ${data.matched || 0}`;
        if (data.details && data.details.length > 0) {
            msg += `\n\nDetalles:\n${data.details.join('\n')}`;
        }
        alert(msg);
        await loadNeuro();
    }

    async function processNeuroDownloadsFolder({ force = false, silent = false } = {}) {
        if (neuroAutoSyncPromise) return neuroAutoSyncPromise;

        if (!silent) {
            setNeuroReportsButtonState(true);
        }

        neuroAutoSyncPromise = (async () => {
            const endpoint = force ? '/api/neuro/process-downloads?force=true' : '/api/neuro/process-downloads';
            const res = await fetch(endpoint, { method: 'POST' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.detail || "Intente nuevamente.");
            }
            lastNeuroAutoSyncAt = Date.now();
            return data;
        })();

        try {
            const data = await neuroAutoSyncPromise;
            if (!silent) {
                let msg = `Carpeta: ${data.folder || 'inf-neuro'}\nInformes nuevos procesados: ${data.processed || 0}\nVinculados: ${data.matched || 0}`;
                if (data.skipped) {
                    msg += `\nYa revisados antes: ${data.skipped}`;
                }
                if (data.details && data.details.length > 0) {
                    msg += `\n\nDetalles:\n${data.details.join('\n')}`;
                }
                alert(msg);
            }
            return data;
        } catch (e) {
            if (!silent) {
                alert("No se pudo sincronizar la carpeta de informes. " + (e.message || ""));
            }
            return null;
        } finally {
            neuroAutoSyncPromise = null;
            if (!silent) {
                setNeuroReportsButtonState(false);
            }
        }
    }

    async function autoSyncNeuroReports() {
        const neuroTab = document.getElementById('neuro-tab');
        if (!neuroTab || !neuroTab.classList.contains('active')) return;
        if (Date.now() - lastNeuroAutoSyncAt < 60000) return;

        const result = await processNeuroDownloadsFolder({ force: false, silent: true });
        if (result && (result.processed || 0) > 0) {
            await loadNeuro();
        }
    }

    window.attachReportToNeuro = (neuroId) => {
        pendingNeuroReportId = neuroId;
        if (neuroSingleReportFileInput) {
            neuroSingleReportFileInput.value = "";
            neuroSingleReportFileInput.click();
        }
    };

    window.sendNeuroReport = (itemStr) => {
        const item = JSON.parse(decodeURIComponent(itemStr));
        void shareNeuroReportViaWhatsApp(item).then((sent) => {
            if (sent) {
                loadNeuro();
            }
        });
    };

    function addMinutesToTime(timeStr, minutesToAdd) {
        if (!timeStr || !timeStr.includes(':')) return timeStr || "";
        const [hh, mm] = timeStr.split(':').map(Number);
        if (Number.isNaN(hh) || Number.isNaN(mm)) return timeStr;
        const total = Math.max(0, (hh * 60) + mm + minutesToAdd);
        return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
    }

    window.shiftNeuroEntry = async (itemStr, direction) => {
        const item = JSON.parse(decodeURIComponent(itemStr));
        const nextTime = addMinutesToTime(item.hora, direction * 45);
        if (!nextTime || nextTime === item.hora) return;
        const payload = { ...item, hora: nextTime };
        const res = await fetch(`/api/neuro/${item.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            alert("No se pudo mover el turno en Neuro. " + (errorData.detail || "Intente nuevamente."));
            return;
        }
        await loadNeuro();
    };

    if (fetchEmailsBtn) {
        fetchEmailsBtn.onclick = (e) => processNeuroDownloadsFolder({ force: !!e?.shiftKey, silent: false });
    }
    if (neuroReportFilesInput) {
        neuroReportFilesInput.onchange = async (e) => {
            await importNeuroFiles(e.target.files);
        };
    }
    if (neuroSingleReportFileInput) {
        neuroSingleReportFileInput.onchange = async (e) => {
            if (!pendingNeuroReportId) return;
            const targetId = pendingNeuroReportId;
            pendingNeuroReportId = null;
            await importNeuroFiles(e.target.files, targetId);
        };
    }

    setInterval(() => {
        void autoSyncNeuroReports();
    }, 120000);
    setInterval(() => {
        const top25Tab = document.getElementById('top25-tab');
        if (top25Tab && top25Tab.classList.contains('active')) {
            void loadTop25Dashboard();
        }
    }, 180000);
    setInterval(() => {
        const panelTab = document.getElementById('panel-tab');
        if (panelTab && panelTab.classList.contains('active')) {
            void loadPanelDashboard({ syncOffice: false, silentSync: true });
        }
    }, 300000);

    const regDni = document.getElementById('reg-dni'); const regAnio = document.getElementById('reg-anio'); const regMes = document.getElementById('reg-mes');
    regAnio.value = new Date().getFullYear(); regMes.value = new Date().getMonth() + 1;

    async function updateNextHc() {
        if (isExistingPatient) return;
        const yearVal = parseInt(regAnio.value); if (isNaN(yearVal)) return;
        const res = await fetch(`/api/next-hc?year=${yearVal}`);
        const data = await res.json();
        document.getElementById('reg-hc').value = data.num_hc;
    }

    regAnio.oninput = updateNextHc;
    regDni.onblur = async () => {
        if (isExistingPatient) return;
        let dni = regDni.value.replace(/\D/g, ''); regDni.value = dni; if (!dni) return;
        try {
            const res = await fetch(`/api/patients/${dni}`);
            if (res.ok) {
                const p = await res.json();
                document.getElementById('reg-id').value = p.id; document.getElementById('reg-nombre').value = p.apellido_nombre;
                document.getElementById('reg-nacimiento').value = p.fecha_nacimiento; document.getElementById('reg-domicilio').value = p.domicilio;
                document.getElementById('reg-localidad').value = p.localidad; document.getElementById('reg-telefono').value = p.telefono;
                document.getElementById('reg-beneficio').value = p.num_beneficio; document.getElementById('reg-hc').value = p.num_hc;
                regAnio.value = p.anio_vigencia; regMes.value = p.mes_renovacion;
                document.getElementById('reg-f-inicio').value = p.fecha_inicio || ""; document.getElementById('reg-f-fin').value = p.fecha_fin || "";
                isExistingPatient = true; document.querySelector('#register-tab h1').innerText = "Editar Registro (Detectado)";
            } else { isExistingPatient = false; updateNextHc(); document.querySelector('#register-tab h1').innerText = "Nuevo Registro"; }
        } catch (e) { }
    };

    const regPamiBtn = document.getElementById('reg-pami-btn');
    if (regPamiBtn) {
        regPamiBtn.onclick = async () => {
            const dni = regDni.value.replace(/\D/g, '');
            if (!dni) {
                alert("Por favor ingrese un DNI válido para buscar en PAMI.");
                return;
            }
            const origHTML = regPamiBtn.innerHTML;
            regPamiBtn.disabled = true;
            regPamiBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PAMI';
            try {
                const res = await fetch(`/api/pami/refine/${dni}`);
                const data = await res.json();
                if (res.ok && data.success && data.data) {
                    const info = data.data;
                    if (info.name) document.getElementById('reg-nombre').value = info.name;
                    if (info.beneficio) document.getElementById('reg-beneficio').value = info.beneficio;
                    if (info.fn) document.getElementById('reg-nacimiento').value = info.fn;
                    alert("Datos de PAMI obtenidos y autocompletados correctamente.");
                } else {
                    alert(data.detail || "No se encontraron datos en PAMI para este DNI.");
                }
            } catch (e) {
                alert("Error al consultar PAMI. Verifique la conexión.");
            } finally {
                regPamiBtn.disabled = false;
                regPamiBtn.innerHTML = origHTML;
            }
        };
    }

    registerForm.onsubmit = async (e) => {
        e.preventDefault();
        const yearVal = parseInt(regAnio.value); const mesVal = parseInt(regMes.value); const idVal = document.getElementById('reg-id').value;
        const data = {
            apellido_nombre: document.getElementById('reg-nombre').value, dni: regDni.value,
            fecha_nacimiento: document.getElementById('reg-nacimiento').value, domicilio: document.getElementById('reg-domicilio').value,
            localidad: document.getElementById('reg-localidad').value, telefono: document.getElementById('reg-telefono').value,
            num_beneficio: document.getElementById('reg-beneficio').value, num_hc: document.getElementById('reg-hc').value,
            anio_vigencia: yearVal || 2026, mes_renovacion: mesVal || 1,
            fecha_inicio: document.getElementById('reg-f-inicio').value, fecha_fin: document.getElementById('reg-f-fin').value
        };
        const url = idVal ? `/api/patients/${idVal}` : '/api/patients'; const method = idVal ? 'PUT' : 'POST';
        const res = await fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        if (res.ok) { alert(idVal ? "Registro Actualizado" : "Paciente Registrado"); registerForm.reset(); document.getElementById('reg-id').value = ""; isExistingPatient = false; document.querySelector('#register-tab h1').innerText = "Nuevo Registro"; updateNextHc(); loadPatients(); }
        else { const errorData = await res.json(); alert("Error: " + (errorData.detail || "No se pudo guardar.")); }
    };

    // --- Personal / Ingreso-Egreso ---
    const staffMonthInput = document.getElementById('staff-month');
    const staffYearInput = document.getElementById('staff-year');
    const staffSelect = document.getElementById('staff-select');
    const staffCargo = document.getElementById('staff-cargo');
    const staffIncludeWord = document.getElementById('staff-include-word');
    const staffDefaultIngreso = document.getElementById('staff-default-ingreso');
    const staffDefaultEgreso = document.getElementById('staff-default-egreso');
    const staffExcelPath = document.getElementById('staff-excel-path');
    const staffBaseFolder = document.getElementById('staff-base-folder');
    const staffOutputPath = document.getElementById('staff-output-path');
    const staffStatus = document.getElementById('staff-status');
    const staffTotalsBody = document.getElementById('staff-totals-body');
    const staffCalendar = document.getElementById('staff-calendar');
    const staffAttBody = document.getElementById('staff-att-body');

    const staffRefreshBtn = document.getElementById('staff-refresh-btn');
    const staffSaveDefaultBtn = document.getElementById('staff-save-default-btn');
    const staffApplyWeekdaysBtn = document.getElementById('staff-apply-weekdays-btn');
    const staffClearMonthBtn = document.getElementById('staff-clear-month-btn');
    const staffImportBtn = document.getElementById('staff-import-btn');
    const staffExportWordBtn = document.getElementById('staff-export-word-btn');

    const staffDayDate = document.getElementById('staff-day-date');
    const staffDayIngreso = document.getElementById('staff-day-ingreso');
    const staffDayEgreso = document.getElementById('staff-day-egreso');
    const staffDayObs = document.getElementById('staff-day-obs');
    const staffDayPreview = document.getElementById('staff-day-preview');
    const staffDaySaveBtn = document.getElementById('staff-day-save-btn');
    const staffDayDeleteBtn = document.getElementById('staff-day-delete-btn');

    const staffState = {
        staffList: [],
        staffById: {},
        attendanceRows: [],
        attendanceByDate: {},
        selectedDay: null,
    };

    function pad2(n) { return String(n).padStart(2, '0'); }
    function isoDate(y, m, d) { return `${y}-${pad2(m)}-${pad2(d)}`; }
    function mondayWeekdayIndex(jsDate) { return (jsDate.getDay() + 6) % 7; } // Monday=0
    function getDaysInMonth(y, m) { return new Date(y, m, 0).getDate(); } // m:1-12

    function formatHours(val) {
        const num = Number(val);
        if (!isFinite(num) || Math.abs(num) < 1e-9) return "";
        const rounded = Math.round((num + 1e-12) * 100) / 100;
        if (Math.abs(rounded - Math.round(rounded)) < 1e-9) return String(Math.round(rounded));
        let s = String(rounded);
        s = s.replace(/(\.\d*[1-9])0+$/, '$1').replace(/\.0+$/, '');
        return s;
    }

    function timeToMinutes(t) {
        if (!t) return null;
        const parts = t.split(':');
        if (parts.length < 2) return null;
        const hh = parseInt(parts[0]);
        const mm = parseInt(parts[1]);
        if (!isFinite(hh) || !isFinite(mm) || hh < 0 || hh > 23 || mm < 0 || mm > 59) return null;
        return hh * 60 + mm;
    }

    function computeHours(ingreso, egreso) {
        const i = timeToMinutes(ingreso);
        const e = timeToMinutes(egreso);
        if (i === null || e === null) return null;
        let end = e;
        if (end < i) end += 24 * 60;
        const diff = end - i;
        if (diff <= 0) return null;
        return diff / 60.0;
    }

    function setStaffStatus(msg) {
        if (staffStatus) staffStatus.innerText = msg || "";
    }

    function getStaffMonthYear() {
        const now = new Date();
        const month = staffMonthInput && staffMonthInput.value ? parseInt(staffMonthInput.value) : (now.getMonth() + 1);
        const year = staffYearInput && staffYearInput.value ? parseInt(staffYearInput.value) : now.getFullYear();
        return { month, year };
    }

    function getSelectedStaffId() {
        if (!staffSelect) return null;
        const id = parseInt(staffSelect.value);
        return isFinite(id) ? id : null;
    }

    function renderStaffTotals(totals) {
        if (!staffTotalsBody) return;
        staffTotalsBody.innerHTML = '';
        (totals || []).forEach(t => {
            const tr = document.createElement('tr');
            const includeTxt = (parseInt(t.include_in_word) === 1) ? "SI" : "NO";
            tr.innerHTML = `
                <td>${t.nombre || '-'}</td>
                <td>${t.cargo || ''}</td>
                <td><span class="badge badge-hc">${formatHours(t.total_horas)} </span></td>
                <td><span class="badge" style="background:${includeTxt==='SI' ? '#dcfce7' : '#f3f4f6'}; color:${includeTxt==='SI' ? '#166534' : '#4b5563'}">${includeTxt}</span></td>
            `;
            staffTotalsBody.appendChild(tr);
        });
        if ((totals || []).length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="4" style="text-align:center; opacity:0.6;">Sin datos</td>';
            staffTotalsBody.appendChild(tr);
        }
    }

    function renderStaffAttendanceList(rows) {
        if (!staffAttBody) return;
        staffAttBody.innerHTML = '';
        (rows || []).forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${r.fecha || '-'}</td>
                <td>${r.ingreso || ''}</td>
                <td>${r.egreso || ''}</td>
                <td><span class="badge badge-hc">${formatHours(r.horas)} </span></td>
                <td>${r.observaciones || ''}</td>
            `;
            staffAttBody.appendChild(tr);
        });
        if ((rows || []).length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="5" style="text-align:center; opacity:0.6;">Sin registros</td>';
            staffAttBody.appendChild(tr);
        }
    }

    function renderStaffCalendar() {
        if (!staffCalendar) return;
        const { month, year } = getStaffMonthYear();
        const daysInMonth = getDaysInMonth(year, month);
        const first = new Date(year, month - 1, 1);
        const startIdx = mondayWeekdayIndex(first);

        staffCalendar.innerHTML = '';
        for (let i = 0; i < 42; i++) {
            const day = i - startIdx + 1;
            const cell = document.createElement('div');
            cell.className = 'staff-cal-cell staff-cal-empty';

            if (day < 1 || day > daysInMonth) {
                cell.innerHTML = `<div class="staff-cal-num"></div><div class="staff-cal-time"></div><div class="staff-cal-hours"></div>`;
                staffCalendar.appendChild(cell);
                continue;
            }

            const dateIso = isoDate(year, month, day);
            const row = staffState.attendanceByDate[dateIso];
            const isWeekend = (i % 7) >= 5;
            if (row) cell.classList.add('staff-cal-present');
            if (isWeekend) cell.classList.add('staff-cal-weekend');
            if (staffState.selectedDay === day) cell.classList.add('staff-cal-selected');

            const timeText = row ? `${row.ingreso || ''}-${row.egreso || ''}`.replace(/^-|-$/g, '') : '-';
            const hoursText = row ? `${formatHours(row.horas)}h` : '';
            cell.innerHTML = `
                <div class="staff-cal-num">${day}</div>
                <div class="staff-cal-time">${timeText}</div>
                <div class="staff-cal-hours">${hoursText}</div>
            `;
            cell.onclick = () => selectStaffDay(day);
            staffCalendar.appendChild(cell);
        }
    }

    function updateDayPreview() {
        if (!staffDayPreview) return;
        const h = computeHours(staffDayIngreso ? staffDayIngreso.value : "", staffDayEgreso ? staffDayEgreso.value : "");
        staffDayPreview.innerText = h === null ? "" : `Horas: ${formatHours(h)}`;
    }

    function selectStaffDay(day) {
        const { month, year } = getStaffMonthYear();
        staffState.selectedDay = day;
        const dateIso = isoDate(year, month, day);
        if (staffDayDate) staffDayDate.value = dateIso;

        const row = staffState.attendanceByDate[dateIso];
        if (row) {
            if (staffDayIngreso) staffDayIngreso.value = row.ingreso || '';
            if (staffDayEgreso) staffDayEgreso.value = row.egreso || '';
            if (staffDayObs) staffDayObs.value = row.observaciones || '';
        } else {
            if (staffDayIngreso) staffDayIngreso.value = (staffDefaultIngreso && staffDefaultIngreso.value) ? staffDefaultIngreso.value : '';
            if (staffDayEgreso) staffDayEgreso.value = (staffDefaultEgreso && staffDefaultEgreso.value) ? staffDefaultEgreso.value : '';
            if (staffDayObs) staffDayObs.value = '';
        }

        updateDayPreview();
        renderStaffCalendar();
    }

    async function loadStaffTab({ keepStaff = false } = {}) {
        if (!staffMonthInput || !staffYearInput || !staffSelect) return;

        const { month, year } = getStaffMonthYear();
        if (!isFinite(month) || month < 1 || month > 12) return setStaffStatus("Mes inválido.");
        if (!isFinite(year) || year < 2000) return setStaffStatus("Año inválido.");
        staffMonthInput.value = month;
        staffYearInput.value = year;
        if (staffBaseFolder && !staffBaseFolder.value) staffBaseFolder.value = "D:\\HORAS";

        setStaffStatus("Cargando...");

        try {
            if (!keepStaff) {
                const staffRes = await fetch(`/api/staff?t=${Date.now()}`);
                const staffData = await staffRes.json();
                staffState.staffList = staffData || [];
                staffState.staffById = {};
                staffState.staffList.forEach(s => { staffState.staffById[String(s.id)] = s; });
            }

            const prevId = staffSelect.value;
            staffSelect.innerHTML = '';
            staffState.staffList.forEach(s => {
                const opt = document.createElement('option');
                opt.value = String(s.id);
                opt.textContent = `${s.nombre || '-'}${(s.cargo || '').trim() ? ' - ' + s.cargo : ''}`;
                staffSelect.appendChild(opt);
            });
            if (prevId && staffState.staffById[String(prevId)]) staffSelect.value = prevId;
            if (!staffSelect.value && staffState.staffList.length) staffSelect.value = String(staffState.staffList[0].id);

            const selectedStaffId = getSelectedStaffId();
            const selectedStaff = selectedStaffId ? staffState.staffById[String(selectedStaffId)] : null;
            if (staffCargo) staffCargo.value = selectedStaff ? (selectedStaff.cargo || '') : '';
            if (staffIncludeWord) staffIncludeWord.value = selectedStaff ? String(parseInt(selectedStaff.include_in_word) === 1 ? 1 : 0) : '1';
            if (staffDefaultIngreso) staffDefaultIngreso.value = selectedStaff ? (selectedStaff.default_ingreso || '') : '';
            if (staffDefaultEgreso) staffDefaultEgreso.value = selectedStaff ? (selectedStaff.default_egreso || '') : '';

            const totalsRes = await fetch(`/api/staff/totals?year=${year}&month=${month}&include_in_word_only=false&t=${Date.now()}`);
            const totalsData = await totalsRes.json();
            renderStaffTotals(totalsData);

            if (!selectedStaffId) {
                staffState.attendanceRows = [];
                staffState.attendanceByDate = {};
                renderStaffAttendanceList([]);
                renderStaffCalendar();
                setStaffStatus("No hay personal cargado todavía.");
                return;
            }

            const attRes = await fetch(`/api/staff/attendance?staff_id=${selectedStaffId}&year=${year}&month=${month}&t=${Date.now()}`);
            const attData = await attRes.json();
            staffState.attendanceRows = attData || [];
            staffState.attendanceByDate = {};
            staffState.attendanceRows.forEach(r => { if (r && r.fecha) staffState.attendanceByDate[r.fecha] = r; });
            renderStaffAttendanceList(staffState.attendanceRows);
            renderStaffCalendar();

            // Si no hay día seleccionado, preseleccionar hoy si corresponde al mes/año.
            const today = new Date();
            if (staffState.selectedDay === null && today.getFullYear() === year && (today.getMonth() + 1) === month) {
                selectStaffDay(today.getDate());
            }

            setStaffStatus(`OK. ${pad2(month)}/${year}`);
        } catch (e) {
            console.error(e);
            setStaffStatus("Error cargando personal/asistencia.");
        }
    }

    async function saveDefaultSchedule() {
        const staffId = getSelectedStaffId();
        if (!staffId) return alert("Seleccioná un personal.");
        const staff = staffState.staffById[String(staffId)];
        if (!staff) return alert("No encontré el personal.");

        const payload = {
            staff_key: staff.staff_key,
            nombre: staff.nombre,
            cargo: staffCargo && staffCargo.value ? staffCargo.value : (staff.cargo || ""),
            include_in_word: staffIncludeWord ? (staffIncludeWord.value === '1') : (parseInt(staff.include_in_word) === 1),
            fecha_ingreso: staff.fecha_ingreso || "",
            fecha_egreso: staff.fecha_egreso || "",
            default_ingreso: (staffDefaultIngreso && staffDefaultIngreso.value) ? staffDefaultIngreso.value : "",
            default_egreso: (staffDefaultEgreso && staffDefaultEgreso.value) ? staffDefaultEgreso.value : "",
        };

        setStaffStatus("Guardando horario...");
        const res = await fetch('/api/staff', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo guardar el horario."));
        await loadStaffTab({ keepStaff: false });
    }

    async function applyWeekdays() {
        const staffId = getSelectedStaffId();
        if (!staffId) return alert("Seleccioná un personal.");
        const { month, year } = getStaffMonthYear();
        setStaffStatus("Aplicando L-V...");
        const res = await fetch('/api/staff/apply-default-weekdays', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ staff_id: staffId, year, month })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo aplicar."));
        await loadStaffTab({ keepStaff: true });
        alert(`OK. Aplicado en ${data.inserted || 0} días.`);
    }

    async function clearMonth() {
        const staffId = getSelectedStaffId();
        if (!staffId) return alert("Seleccioná un personal.");
        if (!confirm("¿Borrar TODOS los días del mes para este personal?")) return;
        const { month, year } = getStaffMonthYear();
        setStaffStatus("Borrando mes...");
        const res = await fetch('/api/staff/attendance/clear-month', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ staff_id: staffId, year, month })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo borrar."));
        staffState.selectedDay = null;
        await loadStaffTab({ keepStaff: true });
        alert(`OK. Eliminados ${data.deleted || 0} registros.`);
    }

    async function importExcel() {
        if (!staffExcelPath || !staffExcelPath.value.trim()) return alert("Cargá la ruta del Excel.");
        setStaffStatus("Importando Excel...");
        const res = await fetch('/api/staff/import-excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ excel_path: staffExcelPath.value.trim() })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo importar."));
        if (staffMonthInput) staffMonthInput.value = String(data.month || "");
        if (staffYearInput) staffYearInput.value = String(data.year || "");
        staffState.selectedDay = null;
        await loadStaffTab({ keepStaff: false });
        alert(`OK. Importados ${data.records || 0} registros.`);
    }

    async function exportWord() {
        const { month, year } = getStaffMonthYear();
        setStaffStatus("Generando Word...");
        const payload = {
            month,
            year,
            output_path: staffOutputPath && staffOutputPath.value.trim() ? staffOutputPath.value.trim() : null,
            base_folder: staffBaseFolder && staffBaseFolder.value.trim() ? staffBaseFolder.value.trim() : null,
        };
        const res = await fetch('/api/staff/export-word', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo generar el Word."));
        setStaffStatus("OK: " + (data.output_path || "-"));
        alert("Word generado:\n" + (data.output_path || "-"));
    }

    async function saveDay() {
        const staffId = getSelectedStaffId();
        if (!staffId) return alert("Seleccioná un personal.");
        if (!staffDayDate || !staffDayDate.value) return alert("Seleccioná una fecha (clic en el calendario).");
        if (!staffDayIngreso || !staffDayIngreso.value) return alert("Cargá ingreso.");
        if (!staffDayEgreso || !staffDayEgreso.value) return alert("Cargá egreso.");

        setStaffStatus("Guardando día...");
        const payload = {
            staff_id: staffId,
            fecha: staffDayDate.value,
            ingreso: staffDayIngreso.value,
            egreso: staffDayEgreso.value,
            observaciones: staffDayObs ? (staffDayObs.value || "") : ""
        };
        const res = await fetch('/api/staff/attendance', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo guardar."));

        try {
            const d = parseInt(staffDayDate.value.split('-')[2]);
            staffState.selectedDay = isFinite(d) ? d : staffState.selectedDay;
        } catch (e) { }
        await loadStaffTab({ keepStaff: true });
    }

    async function deleteDay() {
        const staffId = getSelectedStaffId();
        if (!staffId) return alert("Seleccioná un personal.");
        if (!staffDayDate || !staffDayDate.value) return alert("Seleccioná una fecha.");
        if (!confirm("¿Eliminar el día seleccionado?")) return;
        setStaffStatus("Eliminando día...");
        const res = await fetch('/api/staff/attendance/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ staff_id: staffId, fecha: staffDayDate.value }) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return alert("Error: " + (data.detail || "No se pudo eliminar."));
        await loadStaffTab({ keepStaff: true });
    }

    // Init + listeners (solo si existe el tab en el HTML)
    if (staffMonthInput && !staffMonthInput.value) staffMonthInput.value = (new Date().getMonth() + 1).toString();
    if (staffYearInput && !staffYearInput.value) staffYearInput.value = new Date().getFullYear().toString();
    if (staffBaseFolder && !staffBaseFolder.value) staffBaseFolder.value = "D:\\HORAS";
    if (staffDayDate && !staffDayDate.value) staffDayDate.value = new Date().toISOString().split('T')[0];

    if (staffRefreshBtn) staffRefreshBtn.onclick = () => loadStaffTab({ keepStaff: true });
    if (staffSelect) staffSelect.onchange = () => { staffState.selectedDay = null; loadStaffTab({ keepStaff: true }); };
    if (staffMonthInput) staffMonthInput.onchange = () => { staffState.selectedDay = null; loadStaffTab({ keepStaff: true }); };
    if (staffYearInput) staffYearInput.onchange = () => { staffState.selectedDay = null; loadStaffTab({ keepStaff: true }); };

    if (staffSaveDefaultBtn) staffSaveDefaultBtn.onclick = () => saveDefaultSchedule();
    if (staffApplyWeekdaysBtn) staffApplyWeekdaysBtn.onclick = () => applyWeekdays();
    if (staffClearMonthBtn) staffClearMonthBtn.onclick = () => clearMonth();
    if (staffImportBtn) staffImportBtn.onclick = () => importExcel();
    if (staffExportWordBtn) staffExportWordBtn.onclick = () => exportWord();

    if (staffDayIngreso) staffDayIngreso.onchange = () => updateDayPreview();
    if (staffDayEgreso) staffDayEgreso.onchange = () => updateDayPreview();
    if (staffDayIngreso) staffDayIngreso.oninput = () => updateDayPreview();
    if (staffDayEgreso) staffDayEgreso.oninput = () => updateDayPreview();
    if (staffDaySaveBtn) staffDaySaveBtn.onclick = () => saveDay();
    if (staffDayDeleteBtn) staffDayDeleteBtn.onclick = () => deleteDay();

    function formatDateToES(iso) { if (!iso) return '-'; const [y, m, d] = iso.split('-'); return `${d}/${m}/${y}`; }

    function formatRenewalPreview(datesRaw) {
        if (!datesRaw) return '-';
        const dates = String(datesRaw)
            .split('|')
            .map(item => item.trim())
            .filter(Boolean)
            .map(formatDateToES);
        if (!dates.length) return '-';
        return dates.join(' | ');
    }

    async function loadPatients(query = '') {
        const res = await fetch(`/api/patients?query=${query}`);
        const data = await res.json();
        patientsBody.innerHTML = '';
        data.forEach(p => {
            const tr = document.createElement('tr');
            const itemStr = encodeURIComponent(JSON.stringify(p));
            tr.innerHTML = `<td><strong>${p.apellido_nombre}</strong></td><td>${p.dni}</td><td>${p.num_beneficio || '<small style="color:#ef4444;font-weight:700">SIN BENEFICIO</small>'}</td><td><span class="badge badge-hc">${p.num_hc || '-'}</span></td><td><small>${p.localidad || '-'}</small></td><td><span class="badge badge-hc">${p.anio_vigencia}</span></td><td><span class="badge badge-count">${p.renewal_count || 0}</span></td><td><button class="btn-icon" onclick="editPatient('${itemStr}')" title="Editar" style="color:var(--primary)"><i class="fas fa-user-edit"></i></button></td><td><button class="btn-icon" onclick="openHistoryModal(${p.id}, '${p.apellido_nombre.replace(/'/g, "\\'")}')" title="Ver renovaciones" style="color:#0d6efd"><i class="fas fa-clock-rotate-left"></i></button><button class="btn-icon" onclick="openRenovationModal(${p.id}, '${p.apellido_nombre.replace(/'/g, "\\'")}')" title="Renovar"><i class="fas fa-sync-alt"></i></button><button class="btn-icon" onclick="deletePatientConfirm(${p.id}, '${p.apellido_nombre.replace(/'/g, "\\'")}')" title="Eliminar definitivamente" style="color: #ff3b30"><i class="fas fa-trash-alt"></i></button></td>`;
            patientsBody.appendChild(tr);
        });

        try {
            const statRes = await fetch('/api/stats');
            const stats = await statRes.json();
            const statContainer = document.getElementById('stats-container');
            if (statContainer) {
                statContainer.innerHTML = stats
                    .filter(s => String(s.year) !== '2027')
                    .map(s => `<span class="badge" style="background: linear-gradient(135deg, #0d6efd, #0b5ed7); color: white; border: 1px solid #0a58ca; padding: 8px 15px; font-size: 14px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 20px; font-weight: 500; text-shadow: 0 1px 1px rgba(0,0,0,0.2);">Carpeta ${s.year}: <strong>${s.count}</strong> pac.</span>`).join('');
            }
        } catch (e) { }
    }

    function formatMonthLabel(monthKey) {
        if (!monthKey || !monthKey.includes('-')) return monthKey || '-';
        const [year, month] = monthKey.split('-');
        const dateObj = new Date(`${year}-${month}-01T00:00:00`);
        return dateObj.toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });
    }

    async function loadPanelDashboard() {
        if (!panelSummary) return;

        if (refreshPanelBtn) {
            refreshPanelBtn.disabled = true;
            refreshPanelBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
        }

        try {
            const res = await fetch('/api/panel');
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || 'No se pudo cargar el panel.');

            const summary = data.summary || {};
            const summaryCards = [
                { label: 'Fichas Maestras', value: summary.master_total || 0, sub: `${summary.master_with_hc || 0} con HC` },
                { label: 'Pacientes Registro', value: summary.registro_total || 0, sub: `${summary.master_with_dni || 0} con DNI en ficha maestra` },
                { label: 'PAMI Office Agenda', value: summary.pami_patients_total || 0, sub: `${summary.pami_turns_total || 0} turnos acumulados` },
                { label: 'Hospital de Día', value: summary.hd_activos || 0, sub: `${summary.hd_total || 0} registros totales` },
                { label: 'Neuro', value: summary.neuro_total || 0, sub: 'turnos neuro registrados' },
                { label: 'Datos de Contacto', value: summary.master_with_phone || 0, sub: `${summary.master_with_address || 0} con domicilio y localidad` },
            ];

            panelSummary.innerHTML = summaryCards.map(card => `
                <div class="panel-stat">
                    <span class="panel-stat-label">${card.label}</span>
                    <span class="panel-stat-value">${card.value}</span>
                    <span class="panel-stat-sub">${card.sub}</span>
                </div>
            `).join('');

            if (panelMeta) {
                const generatedAt = (data.generated_at || '').replace('T', ' ');
                panelMeta.textContent = `Cruce actual entre Registro, HD, Neuro y Office Agenda. Actualizado: ${generatedAt || '-'}`;
            }

            panelMonthlyBody.innerHTML = '';
            (data.monthly_patients || []).forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td><strong>${formatMonthLabel(item.month_key)}</strong></td><td>${item.pacientes}</td><td>${item.turnos}</td>`;
                panelMonthlyBody.appendChild(tr);
            });
            if ((data.monthly_patients || []).length === 0) {
                panelMonthlyBody.innerHTML = '<tr><td colspan="3" style="opacity:0.6;">Sin datos mensuales.</td></tr>';
            }

            panelWeeklyBody.innerHTML = '';
            (data.weekly_turns || []).forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td><strong>${item.week_label}</strong></td><td>${item.pacientes}</td><td>${item.turnos}</td>`;
                panelWeeklyBody.appendChild(tr);
            });
            if ((data.weekly_turns || []).length === 0) {
                panelWeeklyBody.innerHTML = '<tr><td colspan="3" style="opacity:0.6;">Sin datos semanales.</td></tr>';
            }

            panelMethodsBody.innerHTML = '';
            (data.methods || []).forEach(item => {
                const estado = item.estado === 'activo' ? 'Activo' : 'Pendiente de fuente';
                const badgeClass = item.estado === 'activo' ? 'badge-hc' : 'badge-count';
                const tr = document.createElement('tr');
                tr.innerHTML = `<td><strong>${item.metodo}</strong></td><td>${item.pacientes}</td><td><span class="badge ${badgeClass}">${estado}</span></td>`;
                panelMethodsBody.appendChild(tr);
            });
            if ((data.methods || []).length === 0) {
                panelMethodsBody.innerHTML = '<tr><td colspan="3" style="opacity:0.6;">Sin métodos para mostrar.</td></tr>';
            }

            panelNotes.innerHTML = (data.notes || []).map(note => `<div class="panel-note">${note}</div>`).join('');
        } catch (e) {
            if (panelMeta) panelMeta.textContent = 'No se pudo cargar el panel.';
            panelSummary.innerHTML = '<div class="panel-stat"><span class="panel-stat-label">Panel</span><span class="panel-stat-value">Error</span><span class="panel-stat-sub">No se pudieron cargar las métricas.</span></div>';
            panelMonthlyBody.innerHTML = '<tr><td colspan="3" style="color:#b42318;">No se pudieron cargar los datos.</td></tr>';
            panelWeeklyBody.innerHTML = '<tr><td colspan="3" style="color:#b42318;">No se pudieron cargar los datos.</td></tr>';
            panelMethodsBody.innerHTML = '<tr><td colspan="3" style="color:#b42318;">No se pudieron cargar los datos.</td></tr>';
            panelNotes.innerHTML = '<div class="panel-note">Todavía no pudimos leer el panel. Probá de nuevo en unos segundos.</div>';
        } finally {
            if (refreshPanelBtn) {
                refreshPanelBtn.disabled = false;
                refreshPanelBtn.innerHTML = '<i class="fas fa-rotate-right"></i> Actualizar Panel';
            }
        }
    }

    function formatDeltaLabel(delta, referenceLabel = 'día anterior') {
        const normalizedReference = referenceLabel === 'viernes_anterior'
            ? 'viernes anterior'
            : 'día anterior';
        if (delta === null || delta === undefined) {
            return normalizedReference === 'viernes anterior' ? 'Sin viernes anterior' : 'Sin día anterior';
        }
        if (!delta) return normalizedReference === 'viernes anterior' ? 'Igual que el viernes anterior' : 'Igual que el día anterior';
        return delta > 0 ? `+${delta} turnos vs ${normalizedReference}` : `${delta} turnos vs ${normalizedReference}`;
    }

    function getDeltaTone(delta) {
        if (delta === null || delta === undefined) return 'flat';
        if (delta > 0) return 'up';
        if (delta < 0) return 'down';
        return 'flat';
    }

    function renderPanelBars(items, container, labelKey = 'month_key') {
        const maxTurnos = Math.max(1, ...items.map(item => item.turnos || 0));
        container.innerHTML = items.map(item => {
            const width = Math.max(6, Math.round(((item.turnos || 0) / maxTurnos) * 100));
            const deltaTone = getDeltaTone(item.delta_turnos);
            const label = labelKey === 'month_key'
                ? formatMonthLabel(item.month_key)
                : labelKey === 'day_label'
                    ? item.day_label
                    : item.week_label;
            return `
                <div class="panel-bar-row">
                    <div class="panel-bar-head">
                        <div>
                            <div class="panel-bar-label">${label}</div>
                            <div class="panel-bar-sub">Turnos cargados</div>
                        </div>
                        <div class="panel-bar-metrics">
                            <strong>${item.turnos || 0} turnos</strong>
                            <span class="panel-delta panel-delta-${deltaTone}">${formatDeltaLabel(item.delta_turnos, item.delta_label)}</span>
                        </div>
                    </div>
                    <div class="panel-bar-track">
                        <div class="panel-bar-fill panel-bar-fill-${deltaTone}" style="width:${width}%"></div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderPanelBarSection(title, items, emptyLabel, labelKey = 'day_label') {
        if (!items || items.length === 0) {
            return `
                <div class="panel-bars-group">
                    <div class="panel-bars-group-title">${title}</div>
                    <div class="panel-empty">${emptyLabel}</div>
                </div>
            `;
        }

        const temp = document.createElement('div');
        renderPanelBars(items, temp, labelKey);
        return `
            <div class="panel-bars-group">
                <div class="panel-bars-group-title">${title}</div>
                ${temp.innerHTML}
            </div>
        `;
    }

    function renderPanelDayColumns(sections, container) {
        const allItems = sections.flatMap(section => section.items || []);
        const maxTurnos = Math.max(1, ...allItems.map(item => item.turnos || 0));
        const axisSteps = 4;
        const axisLabels = Array.from({ length: axisSteps + 1 }, (_, index) => {
            const value = Math.round((maxTurnos / axisSteps) * (axisSteps - index));
            return `<div class="panel-chart-axis-label">${value}</div>`;
        }).join('');

        const chartSections = sections.map(section => {
            const items = section.items || [];
            if (items.length === 0) {
                return `
                    <div class="panel-chart-week">
                        <div class="panel-chart-week-title">${section.title}</div>
                        <div class="panel-empty">${section.emptyLabel}</div>
                    </div>
                `;
            }

            const columns = items.map(item => {
                const height = Math.max(10, Math.round(((item.turnos || 0) / maxTurnos) * 220));
                const deltaTone = getDeltaTone(item.delta_turnos);
                return `
                    <div class="panel-chart-column">
                        <div class="panel-chart-value">${item.turnos || 0}</div>
                        <div class="panel-chart-bar-wrap">
                            <div class="panel-chart-bar panel-bar-fill panel-bar-fill-${deltaTone}" style="height:${height}px"></div>
                        </div>
                        <div class="panel-chart-day">${item.day_label || '-'}</div>
                        <div class="panel-chart-delta panel-delta panel-delta-${deltaTone}">${formatDeltaLabel(item.delta_turnos, item.delta_label)}</div>
                    </div>
                `;
            }).join('');

            return `
                <div class="panel-chart-week">
                    <div class="panel-chart-week-title">${section.title}</div>
                    <div class="panel-chart-columns">${columns}</div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="panel-chart">
                <div class="panel-chart-legend">
                    <span><i class="panel-legend-swatch panel-legend-up"></i>Sube</span>
                    <span><i class="panel-legend-swatch panel-legend-down"></i>Baja</span>
                    <span><i class="panel-legend-swatch panel-legend-flat"></i>Sin cambio</span>
                </div>
                <div class="panel-chart-body">
                    <div class="panel-chart-axis">
                        ${axisLabels}
                    </div>
                    <div class="panel-chart-grid">
                        <div class="panel-chart-guides">
                            <span></span>
                            <span></span>
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                        <div class="panel-chart-weeks">
                            ${chartSections}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    let panelSyncPromise = null;

    async function syncOfficeAgendaForPanel(silent = true) {
        if (panelSyncPromise) return panelSyncPromise;
        panelSyncPromise = (async () => {
            const res = await fetch('/api/sync', { method: 'POST', cache: 'no-store' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.detail || 'No se pudo sincronizar Office Agenda.');
            }

            const startedAt = Date.now();
            while (Date.now() - startedAt < 180000) {
                await new Promise(resolve => setTimeout(resolve, 1200));
                const statusRes = await fetch(`/api/sync/status?_=${Date.now()}`, { cache: 'no-store' });
                const statusData = await statusRes.json().catch(() => ({}));
                if (!statusRes.ok) {
                    throw new Error(statusData.detail || 'No se pudo leer el estado de sincronizacion.');
                }
                if (refreshPanelBtn && !silent) {
                    refreshPanelBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${statusData.message || 'Sincronizando...'}`;
                }
                if (statusData.status === 'completed') return statusData;
                if (statusData.status === 'error') {
                    throw new Error(statusData.message || 'Error en sincronizacion de Office Agenda.');
                }
            }
            throw new Error('La sincronizacion de Office Agenda tardo mas de lo esperado.');
        })();
        try {
            return await panelSyncPromise;
        } finally {
            panelSyncPromise = null;
        }
    }

    async function loadPanelDashboard({ syncOffice = false, silentSync = true } = {}) {
        if (!panelSummary) return;

        if (refreshPanelBtn) {
            refreshPanelBtn.disabled = true;
            refreshPanelBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${syncOffice ? 'Sincronizando...' : 'Actualizando...'}`;
        }

        try {
            if (syncOffice) {
                await syncOfficeAgendaForPanel(silentSync);
            }
            const res = await fetch(`/api/panel?_=${Date.now()}`, { cache: 'no-store' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || 'No se pudo cargar el panel.');

            const summary = data.summary || {};
            const monthTone = getDeltaTone(summary.month_delta || 0);
            const weekTone = getDeltaTone(summary.week_delta || 0);
            const currentMonthPanelLabel = summary.intersoftic_current_month_label || formatMonthLabel(summary.current_month_key);
            const summaryCards = [
                { label: `Intersoftic ${summary.current_year || ''}`, value: summary.intersoftic_ytd_total || summary.pami_turns_total || 0, sub: `Acumulado hasta ${currentMonthPanelLabel}`, tone: 'primary' },
                { label: 'Turnos Dados Esta Semana', value: summary.booking_week_turns || 0, sub: `${summary.booking_week_patients || 0} pacientes con turno cargado`, tone: 'primary' },
                { label: 'Mes Actual Intersoftic', value: summary.current_month_turns || 0, sub: `${currentMonthPanelLabel} | ${formatDeltaLabel(summary.month_delta || 0)}`, tone: monthTone },
                { label: 'Semana Actual del Mes', value: summary.current_week_turns || 0, sub: `${summary.current_week_label || '-'} | ${formatDeltaLabel(summary.week_delta || 0)}`, tone: weekTone },
                { label: 'Fichas con DNI', value: summary.master_with_dni || 0, sub: `${summary.master_with_hc || 0} con HC`, tone: 'primary' },
                { label: 'Con Teléfono', value: summary.master_with_phone || 0, sub: `${summary.master_with_address || 0} con domicilio y localidad`, tone: 'warn' },
            ];

            panelSummary.innerHTML = summaryCards.map(card => `
                <div class="panel-stat panel-stat-${card.tone}">
                    <span class="panel-stat-label">${card.label}</span>
                    <span class="panel-stat-value">${card.value}</span>
                    <span class="panel-stat-sub">${card.sub}</span>
                </div>
            `).join('');

            if (panelMeta) {
                const generatedAt = (data.generated_at || '').replace('T', ' ');
                panelMeta.textContent = `Turnos cargados por día en la semana actual y la siguiente. Actualizado: ${generatedAt || '-'}`;
            }

            const bookingSections = Array.isArray(data.booking_weeks) && data.booking_weeks.length
                ? data.booking_weeks.map((week, index) => ({
                    title: week.week_label || `Semana ${index + 1}`,
                    items: week.days || [],
                    emptyLabel: 'Sin turnos dados esta semana.',
                }))
                : [
                {
                    title: data.booking_week_label || 'Semana actual',
                    items: data.booking_days || [],
                    emptyLabel: 'Sin turnos dados esta semana.',
                },
                {
                    title: data.booking_next_week_label || 'Semana siguiente',
                    items: data.booking_days_next_week || [],
                    emptyLabel: 'Sin turnos dados la próxima semana.',
                },
                ];
            renderPanelDayColumns(bookingSections, panelMonthlyBody);

            if (panelWeeklyBody) {
                panelWeeklyBody.innerHTML = '';
            }

            panelMethodsBody.innerHTML = '';
            (data.methods || []).forEach(item => {
                const estadoMap = {
                    activo: 'Activo',
                    sin_registros: 'Sin registros',
                    pendiente_fuente: 'Pendiente de fuente'
                };
                const badgeClass = item.estado === 'activo' ? 'badge-hc' : 'badge-count';
                const tr = document.createElement('tr');
                tr.innerHTML = `<td><strong>${item.metodo}</strong></td><td>${item.pacientes}</td><td><span class="badge ${badgeClass}">${estadoMap[item.estado] || item.estado}</span></td>`;
                panelMethodsBody.appendChild(tr);
            });
            if ((data.methods || []).length === 0) {
                panelMethodsBody.innerHTML = '<tr><td colspan="3" style="opacity:0.6;">Sin métodos para mostrar.</td></tr>';
            }

            panelNotes.innerHTML = (data.notes || []).map(note => `<div class="panel-note">${note}</div>`).join('');
        } catch (e) {
            if (panelMeta) panelMeta.textContent = 'No se pudo cargar el panel.';
            panelSummary.innerHTML = '<div class="panel-stat"><span class="panel-stat-label">Panel</span><span class="panel-stat-value">Error</span><span class="panel-stat-sub">No se pudieron cargar las métricas.</span></div>';
            panelMonthlyBody.innerHTML = '<div class="panel-empty" style="color:#b42318;">No se pudieron cargar los turnos dados.</div>';
            if (panelWeeklyBody) {
                panelWeeklyBody.innerHTML = '';
            }
            panelMethodsBody.innerHTML = '<tr><td colspan="3" style="color:#b42318;">No se pudieron cargar los datos.</td></tr>';
            panelNotes.innerHTML = '<div class="panel-note">Todavía no pudimos leer el panel. Probá de nuevo en unos segundos.</div>';
            if (!silentSync) {
                alert("No se pudo actualizar el panel con Office Agenda. " + (e.message || ""));
            }
        } finally {
            if (refreshPanelBtn) {
                refreshPanelBtn.disabled = false;
                refreshPanelBtn.innerHTML = '<i class="fas fa-rotate-right"></i> Actualizar Panel';
            }
        }
    }

    async function loadTop25Dashboard() {
        if (!top25Body) return;

        if (refreshTop25Btn) {
            refreshTop25Btn.disabled = true;
            refreshTop25Btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
        }

        try {
            const res = await fetch('/api/top25');
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || 'No se pudo cargar el Top 25.');

            if (top25Meta) {
                const generatedAt = (data.generated_at || '').replace('T', ' ');
                top25Meta.textContent = `Sesiones desde 2020 hasta ${formatDateToES(data.cutoff)}. Actualizado: ${generatedAt || '-'}`;
            }

            const leader = (data.top25 || [])[0];
            if (top25LeaderName) {
                top25LeaderName.textContent = leader?.paciente || 'Sin datos';
            }
            if (top25LeaderDetail) {
                top25LeaderDetail.textContent = leader
                    ? `${leader.sesiones} sesiones | Última: ${formatDateToES(leader.ultima_sesion)}`
                    : 'Todavía no hay sesiones cargadas.';
            }

            top25Body.innerHTML = '';
            (data.top25 || []).forEach(item => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td><span class="badge badge-hc">#${item.puesto}</span></td><td><strong>${item.paciente}</strong></td><td>${item.dni || '-'}</td><td><span class="badge badge-count">${item.sesiones}</span></td><td>${formatDateToES(item.primera_sesion)}</td><td>${formatDateToES(item.ultima_sesion)}</td>`;
                top25Body.appendChild(tr);
            });

            if ((data.top25 || []).length === 0) {
                top25Body.innerHTML = '<tr><td colspan="6" style="text-align:center; opacity:0.6;">No hay datos para mostrar.</td></tr>';
            }
        } catch (e) {
            if (top25Meta) top25Meta.textContent = 'No se pudo cargar el Top 25.';
            top25Body.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#b42318;">No se pudo cargar el ranking.</td></tr>';
        } finally {
            if (refreshTop25Btn) {
                refreshTop25Btn.disabled = false;
                refreshTop25Btn.innerHTML = '<i class="fas fa-rotate-right"></i> Actualizar Ranking';
            }
        }
    }

    async function loadIntersofticStats() {
        if (!intersofticBody) return;

        if (refreshIntersofticBtn) {
            refreshIntersofticBtn.disabled = true;
            refreshIntersofticBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
        }

        intersofticBody.innerHTML = '<tr><td colspan="10" style="text-align:center; opacity:0.6;">Cargando estadística...</td></tr>';
        if (intersofticSummary) intersofticSummary.innerHTML = '';

        try {
            const res = await fetch(`/api/intersoftic-stats?t=${Date.now()}`, { cache: 'no-store' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || 'No se pudo cargar la estadistica de Intersoftic.');

            intersofticDataCache = data;
            renderIntersofticView();
        } catch (e) {
            if (intersofticMeta) intersofticMeta.textContent = 'No se pudo cargar la estadística de Intersoftic.';
            if (intersofticSummary) intersofticSummary.innerHTML = '';
            if (intersofticContainer) {
                intersofticContainer.innerHTML = '<div style="text-align:center; color:#b42318; padding:20px;">No se pudo cargar la estadística.</div>';
            } else {
                intersofticBody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:#b42318;">No se pudo cargar la estadística.</td></tr>';
            }
        } finally {
            if (refreshIntersofticBtn) {
                refreshIntersofticBtn.disabled = false;
                refreshIntersofticBtn.innerHTML = '<i class="fas fa-rotate-right"></i> Actualizar Estadística';
            }
        }
    }

    function getVisibleIntersofticBranches() {
        const data = intersofticDataCache || {};
        const branches = Array.isArray(data.branches) && data.branches.length ? data.branches : [data];
        if (selectedIntersofticBranch === 'all') return branches;
        return branches.filter(branch => branch.branch_id === selectedIntersofticBranch);
    }

    function renderIntersofticView() {
        if (!intersofticDataCache) return;
        const branches = getVisibleIntersofticBranches();
        const selectedBranch = selectedIntersofticBranch === 'all' ? null : branches[0];
        if (intersofticMeta) {
            intersofticMeta.textContent = selectedBranch
                ? `Sucursal ${selectedBranch.branch || ''} - ${intersofticDataCache.year || ''}`
                : `Todas las sucursales por separado - ${intersofticDataCache.year || ''}`;
        }
        renderIntersofticSummary(branches, intersofticDataCache.year);
        renderIntersofticBranches(branches);
    }

    function renderIntersofticBranches(branches) {
        if (!intersofticContainer) return;
        if (!branches.length) {
            intersofticContainer.innerHTML = '<div style="text-align:center; opacity:0.6; padding:20px;">No hay datos para mostrar.</div>';
            return;
        }

        intersofticContainer.innerHTML = branches.map(branch => {
            const rows = branch.rows || [];
            const totals = branch.totals || {};
            const bodyRows = rows.map(item => `
                <tr>
                    <td><strong>${item.mes || '-'}</strong></td>
                    <td>${item.mdta ?? 0}</td>
                    <td><strong>${item.capita_250101 ?? 0}</strong></td>
                    <td><strong>${item.capita_250102 ?? 0}</strong></td>
                    <td>${item.neuro ?? 0}</td>
                    <td>${item.to ?? 0}</td>
                    <td>${item.fono ?? 0}</td>
                    <td>${item.hd ?? 0}</td>
                    <td>${item.fisiatra ?? 0}</td>
                    <td>${item.domicilio ?? 0}</td>
                    <td>${item.traslado ?? 0}</td>
                    <td><strong>${item.total ?? 0}</strong></td>
                </tr>
            `).join('');
            const totalRow = `
                <tr>
                    <td><strong>TOTAL</strong></td>
                    <td><strong>${totals.mdta ?? 0}</strong></td>
                    <td><strong>${totals.capita_250101 ?? 0}</strong></td>
                    <td><strong>${totals.capita_250102 ?? 0}</strong></td>
                    <td><strong>${totals.neuro ?? 0}</strong></td>
                    <td><strong>${totals.to ?? 0}</strong></td>
                    <td><strong>${totals.fono ?? 0}</strong></td>
                    <td><strong>${totals.hd ?? 0}</strong></td>
                    <td><strong>${totals.fisiatra ?? 0}</strong></td>
                    <td><strong>${totals.domicilio ?? 0}</strong></td>
                    <td><strong>${totals.traslado ?? 0}</strong></td>
                    <td><strong>${totals.total ?? 0}</strong></td>
                </tr>
            `;

            return `
                <section class="intersoftic-branch-block">
                    <div class="intersoftic-branch-head">
                        <h2>${branch.branch || 'Sucursal'}</h2>
                        <span class="intersoftic-branch-total">Total 2026: ${totals.total ?? 0}</span>
                    </div>
                    <table class="glass-table" style="width:100%;">
                        <thead>
                            <tr>
                                <th>MES</th><th>MDTA</th><th>CAPITA 250101</th><th>CAPITA 250102</th><th>NEURO</th><th>TO</th><th>FONO</th><th>HD</th><th>FISIATRA</th><th>DOMICILIO</th><th>TRASLADO</th><th>TOTAL</th>
                            </tr>
                        </thead>
                        <tbody>${bodyRows || '<tr><td colspan="12" style="text-align:center; opacity:0.6;">Sin datos.</td></tr>'}${totalRow}</tbody>
                    </table>
                </section>
            `;
        }).join('');
    }

    function formatPercentDelta(current, previous) {
        if (!previous && !current) return { text: 'Sin movimiento', className: 'panel-delta-flat' };
        if (!previous && current) return { text: 'Nuevo mes cargado', className: 'panel-delta-up' };
        const delta = ((current - previous) / previous) * 100;
        const rounded = Math.round(delta * 10) / 10;
        if (Math.abs(rounded) < 0.1) return { text: '0%', className: 'panel-delta-flat' };
        return {
            text: `${rounded > 0 ? '+' : ''}${rounded}%`,
            className: rounded > 0 ? 'panel-delta-up' : 'panel-delta-down',
        };
    }

    function renderIntersofticSummary(branches, year) {
        if (!intersofticSummary) return;
        intersofticSummary.innerHTML = '';

        const today = new Date();
        const sameYearAsToday = Number(year) === today.getFullYear();
        const cards = (branches || []).map((branch, index) => {
            const allRows = branch.rows || [];
            const validRows = allRows.filter(row => Number(row.total || 0) > 0);
            if (!allRows.length || !validRows.length) return null;

            let current = null;
            let previous = null;
            if (sameYearAsToday) {
                const currentMonthIndex = today.getMonth();
                current = allRows[currentMonthIndex] || null;
                previous = currentMonthIndex > 0 ? (allRows[currentMonthIndex - 1] || null) : null;
            }
            if (!current) {
                current = validRows[validRows.length - 1];
                previous = validRows.length > 1 ? validRows[validRows.length - 2] : null;
            }

            return {
                label: `${branch.branch || 'Sucursal'} ${current.mes}`,
                value: current.total || 0,
                sub: previous ? `vs ${previous.mes}: ${previous.total || 0}` : 'Primer mes con datos',
                tone: index === 0 ? 'panel-stat-primary' : index === 1 ? 'panel-stat-up' : 'panel-stat-warn',
                delta: formatPercentDelta(Number(current.total || 0), Number(previous?.total || 0)),
            };
        }).filter(Boolean);

        if (!cards.length) return;

        cards.forEach(card => {
            const div = document.createElement('div');
            div.className = `panel-stat ${card.tone}`;
            div.innerHTML = `
                <span class="panel-stat-label">${card.label}</span>
                <span class="panel-stat-value">${card.value}</span>
                <span class="panel-stat-sub">${card.sub}</span>
                <span class="panel-delta ${card.delta.className}">${card.delta.text}</span>
            `;
            intersofticSummary.appendChild(div);
        });
    }

    async function loadIntersofticAudit() {
        if (!auditContainer) return;

        if (refreshAuditBtn) {
            refreshAuditBtn.disabled = true;
            refreshAuditBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ejecutando...';
        }
        if (auditMeta) auditMeta.textContent = 'Consultando Intersoftic...';
        if (auditSummary) auditSummary.innerHTML = '';
        auditContainer.innerHTML = '<div class="audit-loading"><i class="fas fa-spinner fa-spin"></i><span>Ejecutando auditoría...</span></div>';

        try {
            const res = await fetch(`/api/intersoftic-audit?t=${Date.now()}`, { cache: 'no-store' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || 'No se pudo ejecutar la auditoría.');
            auditDataCache = data;
            renderAuditView();
        } catch (e) {
            if (auditMeta) auditMeta.textContent = 'No se pudo ejecutar la auditoría.';
            if (auditSummary) auditSummary.innerHTML = '';
            auditContainer.innerHTML = `<div class="audit-error-box"><i class="fas fa-triangle-exclamation"></i>${escapeHtml(e.message || 'Error al consultar Intersoftic.')}</div>`;
        } finally {
            if (refreshAuditBtn) {
                refreshAuditBtn.disabled = false;
                refreshAuditBtn.innerHTML = '<i class="fas fa-rotate-right"></i> Ejecutar Auditoría';
            }
        }
    }

    function getVisibleAuditBranches() {
        const data = auditDataCache || {};
        const branches = Array.isArray(data.branches) ? data.branches : [];
        if (selectedAuditBranch === 'all') return branches;
        return branches.filter(branch => branch.branch_id === selectedAuditBranch);
    }

    function auditMatchesSearch(item, query) {
        if (!query) return true;
        const haystack = [
            item.fecha, item.dia_semana, item.motivo, item.paciente, item.afiliado,
            item.prestacion, item.registro_id, item.orden_id, item.mes, item.sesiones,
            item.documento, item.ugl_actual, item.esperado,
            Array.isArray(item.fechas) ? item.fechas.join(' ') : '',
            Array.isArray(item.prestaciones) ? item.prestaciones.join(' ') : ''
        ].join(' ').toLowerCase();
        return haystack.includes(query);
    }

    function renderAuditView() {
        if (!auditDataCache || !auditContainer) return;
        const branches = getVisibleAuditBranches();
        const query = (auditSearch?.value || '').trim().toLowerCase();
        const year = auditDataCache.year || '';

        if (auditMeta) {
            auditMeta.textContent = selectedAuditBranch === 'all'
                ? `Todas las sucursales - ${year}`
                : `Sucursal ${branches[0]?.branch || ''} - ${year}`;
        }

        renderAuditSummary(branches);
        renderAuditBranches(branches, query);
    }

    function renderAuditSummary(branches) {
        if (!auditSummary) return;
        const totals = (branches || []).reduce((acc, branch) => {
            const summary = branch.summary || {};
            if (branch.available === false || branch.status === 'error' || branch.sql_error) {
                acc.unavailable += 1;
            }
            acc.date += Number(summary.total_date_errors || 0);
            acc.sessions += Number(summary.total_session_errors || 0);
            acc.ugl += Number(summary.total_ugl_errors || 0);
            acc.holidays += Number(summary.feriados_count || 0);
            acc.saturdays += Number(summary.sabados_count || 0);
            acc.sundays += Number(summary.domingos_count || 0);
            return acc;
        }, { date: 0, sessions: 0, ugl: 0, holidays: 0, saturdays: 0, sundays: 0, unavailable: 0 });

        const cards = [
            { label: 'Errores de Fecha', value: totals.date, sub: `${totals.holidays} feriados | ${totals.saturdays} sábados | ${totals.sundays} domingos`, tone: totals.date ? 'audit-stat-danger' : 'audit-stat-ok' },
            { label: 'Más de 10 Sesiones', value: totals.sessions, sub: 'Por paciente y por mes', tone: totals.sessions ? 'audit-stat-warn' : 'audit-stat-ok' },
            { label: 'UGL Incorrecta', value: totals.ugl, sub: 'Según sucursal de facturación', tone: totals.ugl ? 'audit-stat-warn' : 'audit-stat-ok' },
            { label: 'Sucursales Revisadas', value: Math.max(0, branches.length - totals.unavailable), sub: totals.unavailable ? `${totals.unavailable} sin conexión SQL` : 'San Miguel, Ituzaingó y Merlo', tone: totals.unavailable ? 'audit-stat-warn' : 'panel-stat-primary' },
        ];

        auditSummary.innerHTML = cards.map(card => `
            <div class="panel-stat ${card.tone}">
                <span class="panel-stat-label">${card.label}</span>
                <span class="panel-stat-value">${card.value}</span>
                <span class="panel-stat-sub">${card.sub}</span>
            </div>
        `).join('');
    }

    function renderAuditBranches(branches, query) {
        if (!branches.length) {
            auditContainer.innerHTML = '<div class="audit-empty">No hay sucursales para mostrar.</div>';
            return;
        }

        auditContainer.innerHTML = branches.map(branch => {
            const dateErrors = (branch.date_errors || []).filter(item => auditMatchesSearch(item, query));
            const sessionErrors = (branch.session_errors || []).filter(item => auditMatchesSearch(item, query));
            const uglErrors = (branch.ugl_errors || []).filter(item => auditMatchesSearch(item, query));
            const summary = branch.summary || {};
            const hasErrors = dateErrors.length || sessionErrors.length || uglErrors.length;
            const sourceErrors = Array.isArray(branch.source_errors) ? branch.source_errors : [];
            const sqlErrorText = branch.sql_error || (sourceErrors.length ? sourceErrors.join(' | ') : '');
            const friendlySqlError = (sqlErrorText || '').replace(/\('28000'.*?\)/g, 'No se pudo autenticar en Intersoftic. Reemplazá la clave real en .env y reiniciá el servidor.');
            const sqlError = friendlySqlError ? `<div class="audit-sql-error"><i class="fas fa-database"></i>${escapeHtml(friendlySqlError)}</div>` : '';
            const isUnavailable = branch.available === false || branch.status === 'error' || Boolean(friendlySqlError);
            const statusBadge = isUnavailable
                ? '<span class="audit-badge audit-badge-alert">No ejecutada</span>'
                : hasErrors
                ? `<span class="audit-badge audit-badge-alert">${dateErrors.length + sessionErrors.length + uglErrors.length} observaciones</span>`
                : '<span class="audit-badge audit-badge-ok">Sin observaciones</span>';

            const dateRows = dateErrors.map(item => {
                const motivo = String(item.motivo || '');
                const rowClass = motivo.includes('FERIADO') ? 'audit-row-holiday' : motivo.includes('SÁBADO') || motivo.includes('DOMINGO') ? 'audit-row-weekend' : '';
                const motivoClass = motivo.includes('FERIADO') ? 'audit-motivo-feriado' : 'audit-motivo-finsemana';
                return `
                    <tr class="${rowClass}">
                        <td>${escapeHtml(item.fecha || '-')}</td>
                        <td>${escapeHtml(item.dia_semana || '-')}</td>
                        <td><span class="audit-motivo-badge ${motivoClass}">${escapeHtml(item.motivo || '-')}</span></td>
                        <td><strong>${escapeHtml(item.paciente || '-')}</strong><br><small>${escapeHtml(item.afiliado || '-')}</small></td>
                        <td><code>${escapeHtml(item.prestacion || '-')}</code></td>
                        <td>${escapeHtml(item.cantidad ?? '-')}</td>
                        <td>${escapeHtml(item.registro_id || '-')}</td>
                        <td>${escapeHtml(item.orden_id || '-')}</td>
                    </tr>
                `;
            }).join('');

            const sessionRows = sessionErrors.map(item => `
                <tr>
                    <td><strong>${escapeHtml(item.paciente || '-')}</strong><br><small>${escapeHtml(item.afiliado || '-')}</small></td>
                    <td>${escapeHtml(item.mes || '-')}</td>
                    <td><span class="audit-session-count">${escapeHtml(item.sesiones ?? '-')}</span></td>
                    <td>${escapeHtml(item.max_permitido ?? 10)}</td>
                    <td><span class="audit-excess-badge">+${Math.max(0, Number(item.sesiones || 0) - Number(item.max_permitido || 10))}</span></td>
                    <td>${escapeHtml((item.fechas || []).join(', '))}</td>
                </tr>
            `).join('');

            const uglRows = uglErrors.map(item => `
                <tr>
                    <td><strong>${escapeHtml(item.paciente || '-')}</strong><br><small>DNI: ${escapeHtml(item.documento || '-')}</small></td>
                    <td>${escapeHtml(item.afiliado || '-')}</td>
                    <td><span class="audit-motivo-badge audit-motivo-finsemana">${escapeHtml(item.ugl_actual || 'SIN UGL')}</span></td>
                    <td>${escapeHtml(item.esperado || 'UGL 8 o UGL 29')}</td>
                    <td>${escapeHtml(item.first_fecha || '-')} / ${escapeHtml(item.last_fecha || '-')}</td>
                    <td>${escapeHtml((item.prestaciones || []).join(', ') || '-')}</td>
                </tr>
            `).join('');

            const emptyBlock = !hasErrors && !isUnavailable
                ? '<div class="audit-all-ok"><i class="fas fa-circle-check"></i>No se encontraron errores para esta sucursal.</div>'
                : '';

            return `
                <section class="audit-branch-block glass">
                    <div class="audit-branch-head">
                        <h2>${escapeHtml(branch.branch || 'Sucursal')}</h2>
                        <div style="display:flex; gap:8px; flex-wrap:wrap;">
                            ${statusBadge}
                            <span class="audit-badge audit-badge-error">${summary.total_date_errors || 0} fecha</span>
                            <span class="audit-badge audit-badge-error">${summary.total_session_errors || 0} sesiones</span>
                            <span class="audit-badge audit-badge-error">${summary.total_ugl_errors || 0} UGL</span>
                        </div>
                    </div>
                    ${sqlError}
                    ${emptyBlock}
                    ${dateErrors.length ? `
                        <div class="audit-section">
                            <h4><i class="fas fa-calendar-xmark"></i> Feriados, sábados y domingos <span class="audit-count-badge">${dateErrors.length}</span></h4>
                            <div class="table-container">
                                <table class="audit-table">
                                    <thead><tr><th>Fecha</th><th>Día</th><th>Motivo</th><th>Paciente</th><th>Prestación</th><th>Cant.</th><th>ID</th><th>Orden</th></tr></thead>
                                    <tbody>${dateRows}</tbody>
                                </table>
                            </div>
                        </div>
                    ` : ''}
                    ${sessionErrors.length ? `
                        <div class="audit-section">
                            <h4><i class="fas fa-list-ol"></i> Pacientes con más de 10 sesiones mensuales <span class="audit-count-badge">${sessionErrors.length}</span></h4>
                            <div class="table-container">
                                <table class="audit-table">
                                    <thead><tr><th>Paciente</th><th>Mes</th><th>Sesiones</th><th>Máximo</th><th>Exceso</th><th>Fechas</th></tr></thead>
                                    <tbody>${sessionRows}</tbody>
                                </table>
                            </div>
                        </div>
                    ` : ''}
                    ${uglErrors.length ? `
                        <div class="audit-section">
                            <h4><i class="fas fa-id-card"></i> Pacientes con UGL incorrecta <span class="audit-count-badge">${uglErrors.length}</span></h4>
                            <div class="table-container">
                                <table class="audit-table">
                                    <thead><tr><th>Paciente</th><th>Afiliado</th><th>UGL actual</th><th>Esperado</th><th>Primer / Último turno</th><th>Prestaciones</th></tr></thead>
                                    <tbody>${uglRows}</tbody>
                                </table>
                            </div>
                        </div>
                    ` : ''}
                </section>
            `;
        }).join('');
    }

    function normalizeProfessionalBranch(value) {
        return String(value || "").trim().toUpperCase();
    }

    function getProfessionalBranch(professional) {
        return normalizeProfessionalBranch(
            professional.sucursal_detectada_2026 ||
            professional.sucursal_intersoftic ||
            professional.sucursal ||
            ""
        );
    }

    function getProfessionalRole(professional) {
        return String(professional.profesion || professional.cargo || "SIN DEFINIR").trim().toUpperCase() || "SIN DEFINIR";
    }

    function calculateAge(dateValue) {
        if (!dateValue) return "";
        const birth = new Date(`${dateValue}T00:00:00`);
        if (Number.isNaN(birth.getTime())) return "";
        const today = new Date();
        let age = today.getFullYear() - birth.getFullYear();
        const beforeBirthday = today.getMonth() < birth.getMonth() ||
            (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
        if (beforeBirthday) age -= 1;
        return age >= 0 ? `${age} años` : "";
    }

    function getVisibleProfessionals() {
        const role = String(professionalsRoleFilter?.value || "").trim().toUpperCase();
        return (professionalsDataCache || []).filter(professional => {
            const branchOk = !selectedProfessionalsBranch || getProfessionalBranch(professional) === selectedProfessionalsBranch;
            const profRole = getProfessionalRole(professional);
            const roleOk = !role || profRole === role || (!professional.profesion && role === "SIN DEFINIR");
            return branchOk && roleOk;
        });
    }

    async function loadProfessionals() {
        if (!professionalsBody) return;
        professionalsBody.innerHTML = '<tr><td colspan="11" style="text-align:center; opacity:0.6;">Cargando profesionales...</td></tr>';
        if (professionalsRefreshBtn) {
            professionalsRefreshBtn.disabled = true;
            professionalsRefreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Actualizando...';
        }

        try {
            const res = await fetch(`/api/staff/intersoftic-professionals?t=${Date.now()}`, { cache: 'no-store' });
            const data = await res.json().catch(() => []);
            if (!res.ok) throw new Error(data.detail || "No se pudieron cargar los profesionales.");
            professionalsDataCache = Array.isArray(data) ? data : [];
            renderProfessionals();
        } catch (error) {
            professionalsDataCache = [];
            professionalsBody.innerHTML = `<tr><td colspan="11" style="text-align:center; color:#b42318;">${escapeHtml(error.message || "No se pudieron cargar los profesionales.")}</td></tr>`;
            if (professionalsSummary) professionalsSummary.innerHTML = "";
            if (professionalsCount) professionalsCount.textContent = "0";
        } finally {
            if (professionalsRefreshBtn) {
                professionalsRefreshBtn.disabled = false;
                professionalsRefreshBtn.innerHTML = '<i class="fas fa-rotate-right"></i> Actualizar';
            }
        }
    }

    function renderProfessionals() {
        if (!professionalsBody) return;
        const visible = getVisibleProfessionals();
        if (professionalsCount) professionalsCount.textContent = String(visible.length);
        renderProfessionalsSummary(visible);

        if (!visible.length) {
            professionalsBody.innerHTML = '<tr><td colspan="11" style="text-align:center; opacity:0.6;">Sin profesionales para mostrar.</td></tr>';
            return;
        }

        professionalsBody.innerHTML = visible.map(professional => {
            const phone = professional.telefono || professional.movil || "";
            const mail = professional.mail || "";
            const contact = [phone, mail].filter(Boolean).map(escapeHtml).join('<br>') || '-';
            const branch = getProfessionalBranch(professional) || "-";
            const birth = professional.fecha_nacimiento || "";
            const age = calculateAge(birth);
            const birthLabel = [birth ? formatDateToES(birth) : "", age].filter(Boolean).join('<br>') || '-';
            const itemStr = encodeURIComponent(JSON.stringify(professional));
            return `
                <tr>
                    <td><strong>${escapeHtml(professional.nombre_completo || '-')}</strong><br><small>${escapeHtml(professional.origen || 'INTERSOFTIC')}</small></td>
                    <td><span class="badge badge-hc">${escapeHtml(getProfessionalRole(professional))}</span></td>
                    <td>${escapeHtml(professional.documento || '-')}</td>
                    <td>${escapeHtml(professional.matricula_1 || '-')}</td>
                    <td>${escapeHtml(professional.matricula_2 || '-')}</td>
                    <td><small>${birthLabel}</small></td>
                    <td><small>${contact}</small></td>
                    <td>${escapeHtml(professional.numero_emergencia || '-')}</td>
                    <td><small>${escapeHtml(branch)}</small></td>
                    <td><span class="badge badge-count">${Number(professional.efectores_2026 || 0)}</span></td>
                    <td><button class="btn-icon" onclick="editProfessional('${itemStr}')" title="Editar" style="color:var(--primary)"><i class="fas fa-user-edit"></i></button></td>
                </tr>
            `;
        }).join('');
    }

    function renderProfessionalsSummary(rows) {
        if (!professionalsSummary) return;
        const byRole = rows.reduce((acc, item) => {
            const role = getProfessionalRole(item);
            acc[role] = (acc[role] || 0) + 1;
            return acc;
        }, {});
        const byBranch = rows.reduce((acc, item) => {
            const branch = getProfessionalBranch(item) || "SIN SUCURSAL";
            acc[branch] = (acc[branch] || 0) + 1;
            return acc;
        }, {});
        const topRole = Object.entries(byRole).sort((a, b) => b[1] - a[1])[0];
        const topBranch = Object.entries(byBranch).sort((a, b) => b[1] - a[1])[0];
        const active = rows.filter(item => String(item.activo || "S").toUpperCase() === "S").length;
        const cards = [
            { label: "Profesionales", value: rows.length, sub: `${active} activos` },
            { label: "Profesión Principal", value: topRole ? topRole[1] : 0, sub: topRole ? topRole[0] : "-" },
            { label: "Sucursal Principal", value: topBranch ? topBranch[1] : 0, sub: topBranch ? topBranch[0] : "-" },
        ];
        professionalsSummary.innerHTML = cards.map(card => `
            <div class="panel-stat panel-stat-primary">
                <span class="panel-stat-label">${escapeHtml(card.label)}</span>
                <span class="panel-stat-value">${card.value}</span>
                <span class="panel-stat-sub">${escapeHtml(card.sub)}</span>
            </div>
        `).join('');
    }

    function clearProfessionalForm() {
        const fields = {
            id: document.getElementById('professional-id'),
            name: document.getElementById('professional-name'),
            role: document.getElementById('professional-role'),
            branch: document.getElementById('professional-branch'),
            dni: document.getElementById('professional-dni'),
            matricula: document.getElementById('professional-matricula'),
            matricula2: document.getElementById('professional-matricula-2'),
            phone: document.getElementById('professional-phone'),
            mail: document.getElementById('professional-mail'),
            birth: document.getElementById('professional-birth'),
            emergency: document.getElementById('professional-emergency'),
        };
        Object.values(fields).forEach(field => {
            if (field) field.value = "";
        });
        if (professionalDeleteBtn) professionalDeleteBtn.style.display = "none";
        const title = document.getElementById('professional-modal-title');
        if (title) title.textContent = "Nuevo profesional";
    }

    window.editProfessional = (itemStr) => {
        const professional = JSON.parse(decodeURIComponent(itemStr));
        clearProfessionalForm();
        document.getElementById('professional-id').value = professional.id || "";
        document.getElementById('professional-name').value = professional.nombre_completo || "";
        document.getElementById('professional-role').value = professional.profesion || "";
        document.getElementById('professional-branch').value = getProfessionalBranch(professional);
        document.getElementById('professional-dni').value = professional.documento || "";
        document.getElementById('professional-matricula').value = professional.matricula_1 || "";
        document.getElementById('professional-matricula-2').value = professional.matricula_2 || "";
        document.getElementById('professional-phone').value = professional.telefono || professional.movil || "";
        document.getElementById('professional-mail').value = professional.mail || "";
        document.getElementById('professional-birth').value = professional.fecha_nacimiento || "";
        document.getElementById('professional-emergency').value = professional.numero_emergencia || "";
        const title = document.getElementById('professional-modal-title');
        if (title) title.textContent = "Editar profesional";
        if (professionalDeleteBtn) professionalDeleteBtn.style.display = "";
        if (professionalModal) professionalModal.style.display = "block";
    };

    async function saveProfessional() {
        const id = document.getElementById('professional-id')?.value || "";
        const payload = {
            id: id ? Number(id) : null,
            nombre_completo: document.getElementById('professional-name')?.value || "",
            profesion: document.getElementById('professional-role')?.value || "",
            sucursal: document.getElementById('professional-branch')?.value || "",
            documento: document.getElementById('professional-dni')?.value || "",
            matricula_1: document.getElementById('professional-matricula')?.value || "",
            matricula_2: document.getElementById('professional-matricula-2')?.value || "",
            telefono: document.getElementById('professional-phone')?.value || "",
            mail: document.getElementById('professional-mail')?.value || "",
            fecha_nacimiento: document.getElementById('professional-birth')?.value || "",
            numero_emergencia: document.getElementById('professional-emergency')?.value || "",
        };
        if (!payload.nombre_completo.trim()) {
            alert("Completá el nombre del profesional.");
            return;
        }
        const res = await fetch('/api/staff/intersoftic-professionals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || "No se pudo guardar el profesional.");
            return;
        }
        if (professionalModal) professionalModal.style.display = "none";
        await loadProfessionals();
    }

    async function deleteProfessional() {
        const id = document.getElementById('professional-id')?.value || "";
        if (!id) return;
        if (!confirm("¿Eliminar este profesional?")) return;
        const res = await fetch(`/api/staff/intersoftic-professionals/${id}`, { method: 'DELETE' });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || "No se pudo eliminar el profesional.");
            return;
        }
        if (professionalModal) professionalModal.style.display = "none";
        await loadProfessionals();
    }

    mainSearch.oninput = (e) => loadPatients(e.target.value);
    if (refreshPanelBtn) refreshPanelBtn.onclick = () => loadPanelDashboard({ syncOffice: true, silentSync: false });
    if (refreshTop25Btn) refreshTop25Btn.onclick = loadTop25Dashboard;
    if (refreshIntersofticBtn) refreshIntersofticBtn.onclick = loadIntersofticStats;
    if (refreshAuditBtn) refreshAuditBtn.onclick = loadIntersofticAudit;
    if (professionalsRefreshBtn) professionalsRefreshBtn.onclick = loadProfessionals;
    if (professionalsRoleFilter) professionalsRoleFilter.onchange = renderProfessionals;
    if (professionalNewBtn) {
        professionalNewBtn.onclick = () => {
            clearProfessionalForm();
            if (professionalModal) professionalModal.style.display = "block";
        };
    }
    if (professionalSaveBtn) professionalSaveBtn.onclick = saveProfessional;
    if (professionalClearBtn) professionalClearBtn.onclick = clearProfessionalForm;
    if (professionalDeleteBtn) professionalDeleteBtn.onclick = deleteProfessional;
    document.querySelectorAll('.close-professional-modal').forEach(btn => {
        btn.onclick = () => {
            if (professionalModal) professionalModal.style.display = "none";
        };
    });
    if (intersofticBranchTabs) {
        intersofticBranchTabs.querySelectorAll('.intersoftic-branch-btn').forEach(btn => {
            btn.onclick = () => {
                selectedIntersofticBranch = btn.dataset.branch || 'all';
                intersofticBranchTabs.querySelectorAll('.intersoftic-branch-btn').forEach(item => {
                    item.classList.toggle('active', item === btn);
                });
                renderIntersofticView();
            };
        });
    }
    if (auditBranchTabs) {
        auditBranchTabs.querySelectorAll('.intersoftic-branch-btn').forEach(btn => {
            btn.onclick = () => {
                selectedAuditBranch = btn.dataset.branch || 'all';
                auditBranchTabs.querySelectorAll('.intersoftic-branch-btn').forEach(item => {
                    item.classList.toggle('active', item === btn);
                });
                renderAuditView();
            };
        });
    }
    if (auditSearch) auditSearch.oninput = renderAuditView;
    if (professionalsBranchTabs) {
        professionalsBranchTabs.querySelectorAll('.intersoftic-branch-btn').forEach(btn => {
            btn.onclick = () => {
                selectedProfessionalsBranch = normalizeProfessionalBranch(btn.dataset.branch || "");
                professionalsBranchTabs.querySelectorAll('.intersoftic-branch-btn').forEach(item => {
                    item.classList.toggle('active', item === btn);
                });
                renderProfessionals();
            };
        });
    }

    const agendaResources = ["Kine 1", "Kine 2", "Kine 3", "Kine 4", "Kine 5", "Kine 6"];

    function normalizeAgendaResource(resource) {
        const safeResource = (resource || "").toString().trim().toUpperCase();
        if (!safeResource) return "";

        const kineMatch = safeResource.match(/KINE?\s*(\d+)/);
        if (kineMatch) {
            const kineNumber = parseInt(kineMatch[1], 10);
            if (!Number.isNaN(kineNumber) && kineNumber >= 1 && kineNumber <= agendaResources.length) {
                return `Kine ${kineNumber}`;
            }
        }

        const boxMatch = safeResource.match(/BOX\s*(\d+)/);
        if (boxMatch) {
            const pairStart = parseInt(boxMatch[1], 10);
            const kineNumber = Math.floor((pairStart + 1) / 2);
            if (!Number.isNaN(kineNumber) && kineNumber >= 1 && kineNumber <= agendaResources.length) {
                return `Kine ${kineNumber}`;
            }
        }

        const numberMatch = safeResource.match(/\d+/);
        if (!numberMatch) return safeResource;

        const resourceNumber = parseInt(numberMatch[0], 10);
        if (Number.isNaN(resourceNumber) || resourceNumber < 1) return safeResource;

        if (resourceNumber <= agendaResources.length) {
            return `Kine ${resourceNumber}`;
        }

        return `Kine ${Math.floor((resourceNumber + 1) / 2)}`;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Missing variables needed for appointment modal and search
    const gridHeader = document.getElementById('grid-header');
    const gridBody = document.getElementById('grid-body');
    const appointmentModal = document.getElementById('appointment-modal');
    const appointmentForm = document.getElementById('appointment-form');
    const appPatientSearch = document.getElementById('app-patient-search');
    const appSearchResults = document.getElementById('search-results-app');
    const appPatientIdHidden = document.getElementById('app-patient-id');
    const agendaDateFilter = document.getElementById('agenda-date-filter');
    const agendaDayDisplay = document.getElementById('agenda-day-display');
    const agendaTurnCount = document.getElementById('agenda-turn-count');

    // Set today as default
    const todayISO = new Date().toISOString().split('T')[0];
    if (agendaDateFilter) {
        agendaDateFilter.value = todayISO;
        agendaDateFilter.onchange = () => loadAgenda();
        setTimeout(loadAgenda, 100); // Carga inicial
    }

    async function loadAgenda() {
        const selectedDate = agendaDateFilter.value;
        if (!selectedDate) return;

        const dObj = new Date(selectedDate + 'T00:00:00');
        agendaDayDisplay.innerText = dObj.toLocaleDateString('es-AR', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).toUpperCase();

        const res = await fetch(`/api/agenda?fecha=${selectedDate}`);
        const data = await res.json();
        const loadedAppointments = data.filter(app => {
            const patientName = (app.apellido_nombre || "").toString().trim().toUpperCase();
            return patientName !== "" && patientName !== "OCUPADO";
        }).length;

        if (agendaTurnCount) {
            agendaTurnCount.innerText = `${loadedAppointments} turno${loadedAppointments === 1 ? '' : 's'} cargado${loadedAppointments === 1 ? '' : 's'}`;
        }

        // 1. Render Header (KINE 1..6 igual que Office Agenda)
        gridHeader.innerHTML = '';
        const trHead = document.createElement('tr');
        trHead.innerHTML = '<th class="grid-time-column">Hora</th>';
        agendaResources.forEach(resource => {
            trHead.innerHTML += `<th class="grid-box-header">${resource}</th>`;
        });
        gridHeader.appendChild(trHead);

        // 2. Build Time Grid (Limited to 16:00)
        gridBody.innerHTML = '';
        const timeSlots = [];
        for (let h = 8; h <= 16; h++) { // Límite hasta las 16:00
            for (let m = 0; m < 60; m += 30) {
                if (h === 16 && m > 0) break; // No pasar de las 16:00
                timeSlots.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
            }
        }

        // Map data for fast access (hora_recurso)
        const appMap = {};
        data.forEach(app => {
            const normalizedResource = normalizeAgendaResource(app.recurso);
            const key = `${app.hora}_${normalizedResource}`;
            if (!appMap[key]) appMap[key] = [];
            appMap[key].push({ ...app, normalizedResource });
        });

        timeSlots.forEach(slot => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td class="grid-time-column">${slot}</td>`;

            agendaResources.forEach(resource => {
                const key = `${slot}_${resource}`;
                const appsInCell = appMap[key] || [];
                const cell = document.createElement('td');
                cell.className = 'grid-cell';

                if (appsInCell.length > 0) {
                    appsInCell.forEach(app => {
                        const isOcupado = (app.apellido_nombre === 'OCUPADO');
                        const observaciones = app.observaciones || '';
                        const chipClass = isOcupado ? 'chip-ocupado' : ((observaciones.includes('Sincronizado') || observaciones.includes('Importado de Office Agenda')) ? 'chip-sincronizado' : 'chip-normal');
                        const nameDisplay = isOcupado ? 'OCUPADO' : (app.apellido_nombre || 'SIN NOMBRE');

                        const chip = document.createElement('div');
                        chip.className = `appointment-chip ${chipClass}`;
                        chip.textContent = nameDisplay;
                        chip.title = `${nameDisplay}${observaciones ? ` - ${observaciones}` : ''}`;
                        chip.dataset.patientName = nameDisplay;
                        chip.dataset.boxName = app.normalizedResource || resource;
                        chip.onclick = (e) => {
                            e.stopPropagation();
                            openWaFromAgenda(encodeURIComponent(JSON.stringify(app)));
                        };
                        cell.appendChild(chip);
                    });
                }

                cell.ondblclick = () => {
                    appointmentForm.reset();
                    appPatientIdHidden.value = "";
                    document.getElementById('app-fecha').value = selectedDate;
                    document.getElementById('app-hora').value = slot;
                    document.getElementById('app-recurso').value = resource;
                    document.getElementById('app-tipo').value = "Kinesiología";
                    document.getElementById('app-patient-search').value = "";
                    appointmentModal.style.display = 'block';
                };

                tr.appendChild(cell);
            });
            gridBody.appendChild(tr);
        });
    }
    window.loadAgenda = loadAgenda;

    window.deleteAppointment = async (id) => {
        if (!confirm("¿Eliminar este turno?")) return;
        const res = await fetch(`/api/agenda/${id}`, { method: 'DELETE' });
        if (res.ok) loadAgenda();
    };

    window.openWaFromAgenda = (itemStr) => {
        const app = JSON.parse(decodeURIComponent(itemStr));
        const msg = `Buen día ${app.apellido_nombre}, le recordamos su turno de ${app.tipo_sesion} el día ${formatDateToES(app.fecha)} a las ${app.hora} hs. Saludos!`;
        const phone = app.telefono ? app.telefono.replace(/\D/g, '') : "";
        const url = `https://wa.me/${phone.startsWith('54') ? phone : '54' + phone}?text=${encodeURIComponent(msg)}`;
        window.open(url, '_blank');
    };

    document.getElementById('add-appointment-btn').onclick = () => {
        appointmentForm.reset();
        appPatientIdHidden.value = "";
        document.getElementById('app-fecha').value = agendaDateFilter.value;
        appointmentModal.style.display = 'block';
    };

    appPatientSearch.oninput = async (e) => {
        const q = e.target.value;
        if (q.length < 2) { appSearchResults.style.display = 'none'; return; }
        const res = await fetch(`/api/patients?query=${q}`);
        const data = await res.json();
        appSearchResults.innerHTML = '';
        if (data.length > 0) {
            data.forEach(p => {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                div.innerHTML = `<strong>${p.apellido_nombre}</strong> <small>(DNI: ${p.dni})</small>`;
                div.onclick = () => {
                    appPatientSearch.value = p.apellido_nombre;
                    appPatientIdHidden.value = p.id;
                    appSearchResults.style.display = 'none';
                };
                appSearchResults.appendChild(div);
            });
            appSearchResults.style.display = 'block';
        } else {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.style.background = '#e8f0fe';
            div.innerHTML = `<i class="fas fa-plus-circle"></i> <strong>Crear "${q}" como nuevo</strong>`;
            div.onclick = () => {
                // Pre-fill Name or DNI in the registration tab
                const regTabBtn = document.querySelector('[data-tab="register-tab"]');
                if (regTabBtn) regTabBtn.click();
                document.getElementById('p-nombre').value = q;
                appointmentModal.style.display = 'none';
            };
            appSearchResults.appendChild(div);
            appSearchResults.style.display = 'block';
        }
    };

    const feriados2026 = ["2026-01-01", "2026-03-24", "2026-04-02", "2026-04-03", "2026-05-01", "2026-05-25", "2026-06-20", "2026-07-09", "2026-07-10", "2026-08-17", "2026-10-12", "2026-11-23", "2026-12-08", "2026-12-25"];

    const updateCycleSummary = () => {
        const start = document.getElementById('app-fecha').value;
        const selectedDays = Array.from(document.querySelectorAll('input[name="app-days"]:checked')).map(cb => parseInt(cb.value));
        const summary = document.getElementById('cycle-summary');
        const rangeText = document.getElementById('cycle-range-text');

        if (!start || selectedDays.length === 0) {
            summary.style.display = 'none';
            return;
        }

        let dates = [start];
        let curr = new Date(start + 'T00:00:00');
        while (dates.length < 10) {
            curr.setDate(curr.getDate() + 1);
            const iso = curr.toISOString().split('T')[0];
            if (feriados2026.includes(iso)) continue;
            const jsDay = curr.getDay(); // 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri
            if (selectedDays.includes(jsDay)) {
                dates.push(iso);
            }
            if (dates.length > 50) break; // Safety
        }

        rangeText.innerText = `${formatDateToES(dates[0])} al ${formatDateToES(dates[dates.length - 1])}`;
        summary.style.display = 'block';
    };

    document.querySelectorAll('input[name="app-days"]').forEach(cb => {
        cb.addEventListener('change', updateCycleSummary);
    });
    document.getElementById('app-fecha').addEventListener('change', updateCycleSummary);

    appointmentForm.onsubmit = async (e) => {
        e.preventDefault();
        const pId = appPatientIdHidden.value;
        if (!pId) { alert("Por favor seleccione un paciente de la lista de sugerencias."); return; }

        const selectedDays = Array.from(document.querySelectorAll('input[name="app-days"]:checked')).map(cb => parseInt(cb.value));

        const data = {
            patient_id: parseInt(pId),
            fecha: document.getElementById('app-fecha').value,
            hora: document.getElementById('app-hora').value,
            recurso: document.getElementById('app-recurso').value || "Kine 1",
            tipo_sesion: document.getElementById('app-tipo').value,
            observaciones: document.getElementById('app-obs').value,
            recurring_days: selectedDays.length > 0 ? selectedDays : null
        };

        const btn = appointmentForm.querySelector('button[type="submit"]');
        const origText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';

        try {
            const res = await fetch('/api/agenda', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (res.ok) {
                const result = await res.json();
                appointmentModal.style.display = 'none';
                loadAgenda();
                if (result.inserted > 1) {
                    alert(`¡Ciclo de ${result.inserted} sesiones programado con éxito!`);
                }
            } else {
                alert("Error al guardar el turno/ciclo.");
            }
        } catch (e) {
            alert("Error de conexión al servidor.");
        } finally {
            btn.disabled = false;
            btn.innerHTML = origText;
        }
    };

    document.getElementById('refresh-agenda-btn').onclick = () => loadAgenda();

    loadPatients(); loadNeuro(); loadAgenda();
    document.querySelectorAll('.close-modal').forEach(btn => btn.onclick = () => { document.querySelectorAll('.modal').forEach(m => m.style.display = 'none'); });
    // ===== HOSPITAL DE DD?a - M?DULO COMPLETO =====

    const hdTableBody = document.getElementById("hd-table-body");
    const hdSearchInput = document.getElementById("hd-search");
    let currentHDList = [];

    const MONTH_ABBR = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
    const MONTH_NAMES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
    const OP_COLORS = ["", "op-ene", "op-feb", "op-mar", "op-abr", "op-may", "op-jun", "op-jul", "op-ago", "op-sep", "op-oct", "op-nov", "op-dic"];

    function hdFormatDate(isoStr) {
        if (!isoStr) return "";
        const [y, m, d] = isoStr.split("-");
        return `${d}/${m}/${y}`;
    }

    function hdDateFromIso(isoStr) {
        if (!isoStr) return null;
        const [y, m, d] = isoStr.split("-").map(Number);
        if (!y || !m || !d) return null;
        return new Date(y, m - 1, d);
    }

    function hdNextRequestDate(ops) {
        // Auditoria HD: el año corre desde la primera fecha de OP del ciclo.
        const withDates = (ops || [])
            .filter(o => o.fecha_val)
            .sort((a, b) => String(a.fecha_val).localeCompare(String(b.fecha_val)));
        if (!withDates.length) return null;
        const firstDate = withDates[0].fecha_val;
        const d = hdDateFromIso(firstDate);
        if (!d) return null;
        d.setFullYear(d.getFullYear() + 1);
        return d.toISOString().split("T")[0];
    }

    async function loadHD(query = "") {
        if (!hdTableBody) return;
        const res = await fetch("/api/hd?query=" + encodeURIComponent(query));
        currentHDList = await res.json();

        const today = new Date();
        const in30 = new Date(); in30.setDate(today.getDate() + 30);

        // Sort: alert rows first, then by last OP date desc, suspended last
        currentHDList.sort((a, b) => {
            const aSusp = a.estado === "Suspendido";
            const bSusp = b.estado === "Suspendido";
            if (aSusp !== bSusp) return aSusp ? 1 : -1;

            const aLast = (a.ops || []).filter(o => o.fecha_val).pop()?.fecha_val || "0000";
            const bLast = (b.ops || []).filter(o => o.fecha_val).pop()?.fecha_val || "0000";
            // Most recent last-OP goes first (they are more "active")
            return bLast.localeCompare(aLast);
        });

        // Stats
        const activos = currentHDList.filter(h => h.estado === "Activo").length;
        const suspendidos = currentHDList.filter(h => h.estado === "Suspendido").length;
        const expiring = currentHDList.filter(h => {
            if (h.estado === "Suspendido") return false;
            const nextDate = hdNextRequestDate(h.ops || []);
            if (!nextDate) return false;
            const d = hdDateFromIso(nextDate);
            return d <= in30 && d >= today;
        }).length;

        document.getElementById("hd-stat-active").innerText = activos;
        document.getElementById("hd-stat-month").innerText = currentHDList.length;
        document.getElementById("hd-stat-susp").innerText = suspendidos;
        document.getElementById("hd-stat-expiring").innerText = expiring;

        // Render grouped by month of last OP
        let html = "";
        let lastGroupMonth = null;
        let groupCounter = 0;

        currentHDList.forEach((hd, idx) => {
            const ops = hd.ops || [];
            const lastOpWithDate = ops.filter(o => o.fecha_val).pop();
            const lastOpMonth = lastOpWithDate?.fecha_val ? parseInt(lastOpWithDate.fecha_val.split("-")[1]) : 0;
            const lastOpYear = lastOpWithDate?.fecha_val ? lastOpWithDate.fecha_val.split("-")[0] : "";

            const groupKey = lastOpMonth ? `${MONTH_NAMES[lastOpMonth]} ${lastOpYear}` : "Sin OP Cargada";

            if (groupKey !== lastGroupMonth) {
                groupCounter = 0; // Reset counter for each month group
                const countInGroup = currentHDList.filter(h => {
                    const l = (h.ops || []).filter(o => o.fecha_val).pop()?.fecha_val;
                    const lm = l ? parseInt(l.split("-")[1]) : 0;
                    const ly = l ? l.split("-")[0] : "";
                    const gk = lm ? `${MONTH_NAMES[lm]} ${ly}` : "Sin OP Cargada";
                    return gk === groupKey;
                }).length;
                html += `<tr class="hd-month-hdr"><td colspan="21">${groupKey.toUpperCase()} - ${countInGroup} PACIENTE${countInGroup !== 1 ? "S" : ""}</td></tr>`;
                lastGroupMonth = groupKey;
            }

            groupCounter++; // Unique numbering per month group

            // OP cells
            let opCells = "";
            for (let i = 0; i < 5; i++) {
                const op = ops[i] || { op_number: "", fecha_val: "" };
                const m = op.fecha_val ? parseInt(op.fecha_val.split("-")[1]) : 0;
                const colorCls = m ? OP_COLORS[m] : "";
                const opVal = op.op_number || "";
                const dateVal = op.fecha_val ? hdFormatDate(op.fecha_val) : "";

                opCells += `<td class="editable ${colorCls}" onclick="hdEditCell(this,${hd.id},${hd.patient_id},${i},'op_number')">${opVal}</td>`;
                opCells += `<td class="editable ${colorCls}" onclick="hdEditCell(this,${hd.id},${hd.patient_id},${i},'fecha_val')" style="font-weight:600">${dateVal}</td>`;
            }

            // Next request date
            const nextDate = hdNextRequestDate(ops);
            let nextBadge = '<span style="opacity:0.4; font-size:0.7rem">-</span>';
            if (nextDate) {
                const nd = new Date(nextDate);
                const diff = Math.round((nd - today) / 86400000);
                let cls = "next-req-far";
                if (diff <= 0) cls = "next-req-now";
                else if (diff <= 90) cls = "next-req-soon";
                nextBadge = `<span class="next-req-badge ${cls}" title="Después del ${hdFormatDate(nextDate)}">${hdFormatDate(nextDate)}</span>`;
            }

            const isSusp = hd.estado === "Suspendido";
            const lastDate = lastOpWithDate?.fecha_val ? new Date(lastOpWithDate.fecha_val) : null;
            const isAlert = !isSusp && lastDate && lastDate <= in30 && lastDate >= today;
            const rowClass = isSusp ? "susp-row" : isAlert ? "alert-row" : "";

            html += `<tr class="${rowClass}">
                <td style="opacity:0.5; text-align:center">${groupCounter}</td>
                <td class="editable" onclick="hdEditCell(this,${hd.id},${hd.patient_id},-1,'localidad')">${hd.localidad || ""}</td>
                <td style="font-weight:700; min-width:150px">${hd.apellido_nombre || ""}</td>
                <td class="editable" style="font-size:0.72rem" onclick="hdEditPatient(this,${hd.patient_id},'dni')">${hd.dni || "-"}</td>
                <td style="font-size:0.7rem; opacity:0.7">${hd.num_hc || "-"}</td>
                <td class="editable" onclick="hdEditPatient(this,${hd.patient_id},'num_beneficio')">${hd.num_beneficio || "-"}</td>
                <td class="editable" onclick="hdEditCell(this,${hd.id},${hd.patient_id},-1,'diagnostico')">${hd.diagnostico || ""}</td>
                <td class="editable" style="font-size:0.72rem" onclick="hdEditCell(this,${hd.id},${hd.patient_id},-1,'orden_elect')">${hd.orden_elect || ""}</td>
                ${opCells}
                <td>${nextBadge}</td>
                <td>
                    <span class="badge ${isSusp ? 'bg-susp' : 'bg-active'}" style="cursor:pointer" onclick="hdToggleEstado(${hd.id})" title="Clic para cambiar estado">${hd.estado}</span>
                </td>
                <td>
                    <button onclick="deleteHD(${hd.id})" style="background:none; border:none; color:#ef4444; cursor:pointer; font-size:0.9rem;" title="Eliminar"><i class="fas fa-times-circle"></i></button>
                </td>
            </tr>`;
        });

        hdTableBody.innerHTML = html;
    }

    // Helper para convertir DD/MM/AAAA a AAAA-MM-DD
    const hdParseDate = (str) => {
        if (!str) return "";
        if (str.includes("-")) return str; // Ya es ISO
        const parts = str.split("/");
        if (parts.length === 3) {
            const d = parts[0].padStart(2, "0");
            const m = parts[1].padStart(2, "0");
            const y = parts[2];
            return `${y}-${m}-${d}`;
        }
        return str;
    };

    // Edición inline de campos del registro HD (localidad, diagnostico, orden, OPs)
    window.hdEditCell = (cell, id, patientId, opIndex, field) => {
        if (cell.querySelector("input")) return;
        const entry = currentHDList.find(h => h.id === id);
        if (!entry) return;

        const isDate = field === "fecha_val";
        let currentVal = "";

        if (opIndex >= 0) {
            if (!entry.ops[opIndex]) entry.ops[opIndex] = { op_number: "", fecha_val: "" };
            currentVal = entry.ops[opIndex][field] || "";
        } else {
            currentVal = entry[field] || "";
        }

        // Si es fecha, mostrar en formato DD/MM/AAAA para editar mejor
        const dispVal = isDate ? hdFormatDate(currentVal) : currentVal;

        cell.innerHTML = `<input type="text" class="hd-edit-input" value="${dispVal}" style="width:100%">`;
        const input = cell.querySelector("input");
        input.focus();
        input.select();

        let isSaving = false;
        const save = async () => {
            if (isSaving) return;
            isSaving = true;
            let newVal = input.value.trim();

            if (isDate) {
                newVal = hdParseDate(newVal);
            }

            if (opIndex >= 0) {
                entry.ops[opIndex][field] = newVal;
            } else {
                entry[field] = newVal;
            }

            // Actualizar fecha de pedido para que suba en el orden
            entry.fecha_pedido = new Date().toISOString().split("T")[0];

            await fetch("/api/hd", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(entry)
            });
            loadHD(hdSearchInput?.value || "");
        };

        input.onkeydown = e => {
            if (e.key === "Enter") { e.preventDefault(); save(); }
            if (e.key === "Escape") loadHD(hdSearchInput?.value || "");
        };
        input.onblur = () => {
            if (!isSaving) save();
        };
    };

    // Edición directa de campos del PACIENTE (DNI, num_beneficio) - va a la ficha del paciente
    window.hdEditPatient = (cell, patientId, field) => {
        if (cell.querySelector("input")) return;
        const oldVal = cell.innerText.trim() === "-" ? "" : cell.innerText.trim();

        cell.innerHTML = `<input type="text" class="hd-edit-input" value="${oldVal}" style="width:100%">`;
        const input = cell.querySelector("input");
        input.focus();

        const save = async () => {
            const newVal = input.value.trim();
            if (!newVal) { loadHD(hdSearchInput?.value || ""); return; }

            const res = await fetch(`/api/patients/${patientId}/fields`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ [field]: newVal })
            });

            if (res.ok) {
                // Also update the local cache so next render is immediate
                const entry = currentHDList.find(h => h.patient_id === patientId);
                if (entry) entry[field] = newVal;
                cell.innerText = newVal;
            } else {
                alert("Error al guardar. Intente nuevamente.");
                loadHD(hdSearchInput?.value || "");
            }
        };

        input.onkeydown = e => {
            if (e.key === "Enter") { e.preventDefault(); save(); }
            if (e.key === "Escape") { cell.innerText = oldVal || "-"; }
        };
        input.onblur = () => setTimeout(() => { if (cell.contains(input)) save(); }, 150);
    };

    window.hdToggleEstado = async (id) => {
        const entry = currentHDList.find(h => h.id === id);
        if (!entry) return;
        entry.estado = entry.estado === "Activo" ? "Suspendido" : "Activo";
        await fetch("/api/hd", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(entry)
        });
        loadHD(hdSearchInput?.value || "");
    };

    window.deleteHD = async (id) => {
        if (!confirm("¿Eliminar este paciente de Hospital de Día?")) return;
        const res = await fetch(`/api/hd/${id}`, { method: "DELETE" });
        if (res.ok) loadHD();
        else alert("Error al eliminar.");
    };

    // Quick-add bar
    const hqSearch = document.getElementById("hq-search");
    const hqResults = document.getElementById("hq-results");
    let hqSuggestions = [];
    let hqSelectedPatient = null;
    let hdSearchSuggestions = [];
    let hdModalInitialized = false;

    if (hqSearch) {
        hqSearch.oninput = async (e) => {
            const q = e.target.value.trim();
            hqSelectedPatient = null;
            document.getElementById("hq-patient-id").value = "";
            if (q.length < 2) { hqResults.style.display = "none"; return; }
            const res = await fetch("/api/patients?query=" + encodeURIComponent(q));
            const pats = await res.json();
            hqSuggestions = pats;
            if (!pats.length) { hqResults.style.display = "none"; return; }
            hqResults.innerHTML = pats.map((p, idx) =>
                `<div class="suggestion-item" onclick="hqSelect(${idx})">
                    <strong>${p.apellido_nombre}</strong> <span style="opacity:0.6">${p.dni || "-"}</span>
                 </div>`
            ).join("");
            hqResults.style.display = "block";
        };
        hqSearch.onkeydown = e => { if (e.key === "Escape") hqResults.style.display = "none"; };
    }

    window.hqSelect = (idx) => {
        const patient = hqSuggestions[idx];
        if (!patient) return;
        hqSelectedPatient = patient;
        document.getElementById("hq-patient-id").value = patient.id;
        hqSearch.value = patient.apellido_nombre || "";
        hqResults.style.display = "none";
        document.getElementById("hq-loc")?.focus();
    };

    window.quickAddHD = async () => {
        await window.openHDIntakeModalFromQuick();
    };


    function hdSafeText(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function hdTodayIso() {
        return new Date().toISOString().split("T")[0];
    }

    function getHDElements() {
        return {
            modal: document.getElementById("hd-modal"),
            form: document.getElementById("hd-form"),
            entryId: document.getElementById("hd-id"),
            patientId: document.getElementById("hd-patient-id"),
            patientSearch: document.getElementById("hd-patient-search"),
            patientSearchResults: document.getElementById("search-results-hd"),
            apellidoNombre: document.getElementById("hd-apellido-nombre"),
            dni: document.getElementById("hd-dni"),
            fechaNacimiento: document.getElementById("hd-fecha-nacimiento"),
            beneficio: document.getElementById("hd-beneficio"),
            numHc: document.getElementById("hd-num-hc"),
            domicilio: document.getElementById("hd-domicilio"),
            localidad: document.getElementById("hd-localidad"),
            telefono: document.getElementById("hd-telefono"),
            telefono2: document.getElementById("hd-telefono2"),
            diagnostico: document.getElementById("hd-diagnostico"),
            ordenElect: document.getElementById("hd-orden-elect"),
            fechaPedido: document.getElementById("hd-fecha-pedido"),
            estado: document.getElementById("hd-estado"),
            sesionesMax: document.getElementById("hd-sesiones-max"),
            opsContainer: document.getElementById("ops-container")
        };
    }

    async function hdFetchNextHc() {
        const yearVal = new Date().getFullYear();
        const res = await fetch(`/api/next-hc?year=${yearVal}`);
        if (!res.ok) throw new Error("No se pudo obtener el próximo HC.");
        return res.json();
    }

    function clearQuickHDSeed() {
        hqSelectedPatient = null;
        if (hqSearch) hqSearch.value = "";
        const hqPatientId = document.getElementById("hq-patient-id");
        if (hqPatientId) hqPatientId.value = "";
        const hqLoc = document.getElementById("hq-loc");
        const hqDiag = document.getElementById("hq-diag");
        const hqOrden = document.getElementById("hq-orden");
        if (hqLoc) hqLoc.value = "SM";
        if (hqDiag) hqDiag.value = "";
        if (hqOrden) hqOrden.value = "";
        if (hqResults) hqResults.style.display = "none";
    }

    window.addOPInput = (op = {}) => {
        const { opsContainer } = getHDElements();
        if (!opsContainer) return;
        const row = document.createElement("div");
        row.className = "hd-op-row";
        row.innerHTML = `
            <div class="form-group">
                <label>Nº OP</label>
                <input type="text" class="hd-op-number" value="${hdSafeText(op.op_number || "")}" />
            </div>
            <div class="form-group">
                <label>Fecha Validez</label>
                <input type="date" class="hd-op-date" value="${hdSafeText(op.fecha_val || "")}" />
            </div>
            <button type="button" class="hd-op-remove" title="Quitar OP">
                <i class="fas fa-trash-alt"></i>
            </button>
        `;
        row.querySelector(".hd-op-remove").onclick = () => row.remove();
        opsContainer.appendChild(row);
    };

    function hdCollectOps() {
        const { opsContainer } = getHDElements();
        if (!opsContainer) return [];
        return Array.from(opsContainer.querySelectorAll(".hd-op-row"))
            .map(row => ({
                op_number: row.querySelector(".hd-op-number")?.value?.trim() || "",
                fecha_val: row.querySelector(".hd-op-date")?.value || "",
                color_code: ""
            }))
            .filter(op => op.op_number || op.fecha_val);
    }

    function hdFillPatientForm(patient = {}, options = {}) {
        const els = getHDElements();
        if (!els.form) return;
        const keepLocalidad = options.keepLocalidad && els.localidad?.value.trim();
        if (els.patientId) els.patientId.value = patient.id || "";
        if (els.apellidoNombre) els.apellidoNombre.value = patient.apellido_nombre || patient.paciente || "";
        if (els.dni) els.dni.value = patient.dni || "";
        if (els.fechaNacimiento) els.fechaNacimiento.value = patient.fecha_nacimiento || "";
        if (els.beneficio) els.beneficio.value = patient.num_beneficio || patient.beneficio || "";
        if (els.numHc) els.numHc.value = patient.num_hc || "";
        if (els.domicilio) els.domicilio.value = patient.domicilio || "";
        if (els.telefono) els.telefono.value = patient.telefono || patient.telefono1 || "";
        if (els.telefono2) els.telefono2.value = patient.telefono2 || "";
        if (els.localidad && !keepLocalidad) els.localidad.value = patient.localidad || els.localidad.value || "SM";
        if (els.patientSearch) els.patientSearch.value = patient.apellido_nombre || patient.paciente || "";
        if (els.patientSearchResults) els.patientSearchResults.style.display = "none";
    }

    async function hdPrepareNewPatientNumbers() {
        const els = getHDElements();
        if (!els.form || (els.patientId && els.patientId.value)) return;
        const next = await hdFetchNextHc();
        if (els.numHc) els.numHc.value = next.num_hc || "";
    }

    function hdResetForm(seed = {}) {
        const els = getHDElements();
        if (!els.form) return;
        els.form.reset();
        if (els.entryId) els.entryId.value = "";
        if (els.patientId) els.patientId.value = "";
        if (els.numHc) els.numHc.value = "";
        if (els.fechaPedido) els.fechaPedido.value = hdTodayIso();
        if (els.estado) els.estado.value = "Activo";
        if (els.sesionesMax) els.sesionesMax.value = "24";
        if (els.localidad) els.localidad.value = seed.localidad || "SM";
        if (els.diagnostico) els.diagnostico.value = seed.diagnostico || "";
        if (els.ordenElect) els.ordenElect.value = seed.ordenElect || "";
        if (els.patientSearch) els.patientSearch.value = seed.searchText || "";
        if (els.apellidoNombre && seed.patientName) els.apellidoNombre.value = seed.patientName;
        if (els.patientSearchResults) els.patientSearchResults.style.display = "none";
        if (els.opsContainer) {
            els.opsContainer.innerHTML = "";
            window.addOPInput();
        }
    }

    function hdRenderSuggestionList(container, results, mode) {
        if (!container) return;
        if (!results.length) {
            container.style.display = "none";
            container.innerHTML = "";
            return;
        }
        container.innerHTML = results.map((p, idx) => `
            <div class="search-suggestion-item" data-index="${idx}" data-mode="${mode}">
                <strong>${hdSafeText(p.apellido_nombre || p.paciente || "")}</strong>
                <div class="search-suggestion-meta">
                    DNI ${hdSafeText(p.dni || "-")} | HC ${hdSafeText(p.num_hc || "-")}
                </div>
            </div>
        `).join("");
        container.querySelectorAll(".search-suggestion-item").forEach(item => {
            item.onclick = () => {
                const idx = parseInt(item.dataset.index || "-1", 10);
                if (item.dataset.mode === "quick") window.hqSelect(idx);
                else window.selectHDPatientSuggestion(idx);
            };
        });
        container.style.display = "block";
    }

    function hdValidatePatientAvailability(patientId, currentHdId = 0) {
        const existing = currentHDList.find(h => h.patient_id === patientId && h.id !== currentHdId);
        if (!existing) return null;
        if (existing.estado === "Activo") {
            throw new Error(`AVISO: El paciente ${existing.apellido_nombre} ya se encuentra ACTIVO en Hospital de Día.`);
        }
        const nextPossible = hdNextRequestDate(existing.ops);
        if (nextPossible) {
            const today = new Date();
            const nextDate = new Date(nextPossible);
            if (today < nextDate) {
                throw new Error(`RESTRICCION DE AUDITORIA: El paciente aun no cumple un año desde el inicio del pedido de OP.\nProximo pedido permitido: ${hdFormatDate(nextPossible)}`);
            }
        }
        return existing;
    }

    async function hdSaveOrResolvePatient() {
        const els = getHDElements();
        const apellidoNombre = (els.apellidoNombre?.value || "").trim().toUpperCase();
        const dni = (els.dni?.value || "").replace(/\D/g, "");
        if (els.apellidoNombre) els.apellidoNombre.value = apellidoNombre;
        if (els.dni) els.dni.value = dni;

        if (!apellidoNombre) throw new Error("Completá Apellido y Nombre del paciente.");
        if (!dni) throw new Error("Completá el DNI del paciente.");

        let patientId = parseInt(els.patientId?.value || "0", 10) || 0;
        const patientPayload = {
            apellido_nombre: apellidoNombre,
            dni,
            fecha_nacimiento: els.fechaNacimiento?.value || "",
            domicilio: (els.domicilio?.value || "").trim(),
            localidad: (els.localidad?.value || "").trim(),
            telefono: (els.telefono?.value || "").trim(),
            telefono2: (els.telefono2?.value || "").trim(),
            num_beneficio: (els.beneficio?.value || "").trim()
        };

        if (!patientId) {
            const existingRes = await fetch(`/api/patients/${dni}`);
            if (existingRes.ok) {
                const existingPatient = await existingRes.json();
                patientId = existingPatient.id;
                hdFillPatientForm({ ...existingPatient, ...patientPayload }, { keepLocalidad: true });
            }
        }

        if (patientId) {
            const patchPayload = {};
            Object.entries(patientPayload).forEach(([key, value]) => {
                if (String(value || "").trim()) patchPayload[key] = value;
            });
            if (Object.keys(patchPayload).length) {
                const patchRes = await fetch(`/api/patients/${patientId}/fields`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(patchPayload)
                });
                if (!patchRes.ok) {
                    const err = await patchRes.json().catch(() => ({}));
                    throw new Error(err.detail || "No se pudo actualizar la ficha del paciente.");
                }
            }
            return patientId;
        }

        const next = await hdFetchNextHc();
        const createRes = await fetch("/api/patients", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                ...patientPayload,
                num_hc: next.num_hc,
                anio_vigencia: new Date().getFullYear(),
                mes_renovacion: new Date().getMonth() + 1,
                fecha_inicio: "",
                fecha_fin: ""
            })
        });
        if (!createRes.ok) {
            const err = await createRes.json().catch(() => ({}));
            throw new Error(err.detail || "No se pudo crear el paciente.");
        }

        const lookupRes = await fetch(`/api/patients/${dni}`);
        if (!lookupRes.ok) throw new Error("El paciente se creó pero no se pudo recuperar la ficha.");
        const createdPatient = await lookupRes.json();
        hdFillPatientForm(createdPatient, { keepLocalidad: true });
        return createdPatient.id;
    }

    function closeHDIntakeModal() {
        const { modal, patientSearchResults } = getHDElements();
        if (patientSearchResults) patientSearchResults.style.display = "none";
        if (modal) modal.style.display = "none";
    }

    async function initHDIntakeModal() {
        if (hdModalInitialized) return;
        const els = getHDElements();
        if (!els.form) return;
        hdModalInitialized = true;

        if (els.patientSearch) {
            els.patientSearch.oninput = async (e) => {
                const query = e.target.value.trim();
                if (els.patientId) els.patientId.value = "";
                if (query.length < 2) {
                    hdRenderSuggestionList(els.patientSearchResults, [], "modal");
                    return;
                }
                const res = await fetch("/api/patients?query=" + encodeURIComponent(query));
                hdSearchSuggestions = await res.json();
                hdRenderSuggestionList(els.patientSearchResults, hdSearchSuggestions, "modal");
            };
            els.patientSearch.onkeydown = (e) => {
                if (e.key === "Escape" && els.patientSearchResults) els.patientSearchResults.style.display = "none";
            };
        }

        if (els.dni) {
            els.dni.onblur = async () => {
                const dni = (els.dni.value || "").replace(/\D/g, "");
                els.dni.value = dni;
                if (!dni) return;
                if (els.patientId?.value) return;
                const res = await fetch(`/api/patients/${dni}`);
                if (res.ok) {
                    const patient = await res.json();
                    hdFillPatientForm(patient, { keepLocalidad: true });
                } else {
                    await hdPrepareNewPatientNumbers();
                }
            };
        }

        els.form.onsubmit = async (e) => {
            e.preventDefault();
            try {
                const patientId = await hdSaveOrResolvePatient();
                const currentHdId = parseInt(els.entryId?.value || "0", 10) || 0;
                const existingHd = hdValidatePatientAvailability(patientId, currentHdId);
                const ops = hdCollectOps();
                const payload = {
                    id: currentHdId || existingHd?.id || undefined,
                    patient_id: patientId,
                    localidad: (els.localidad?.value || "").trim() || "SM",
                    diagnostico: (els.diagnostico?.value || "").trim() || "-",
                    orden_elect: (els.ordenElect?.value || "").trim() || "-",
                    fecha_pedido: els.fechaPedido?.value || hdTodayIso(),
                    estado: els.estado?.value || "Activo",
                    sesiones_check: existingHd?.sesiones_check || 0,
                    sesiones_max: parseInt(els.sesionesMax?.value || "24", 10) || 24,
                    num_beneficio: (els.beneficio?.value || "").trim(),
                    dni: (els.dni?.value || "").replace(/\D/g, ""),
                    ops: ops.length ? ops : (existingHd?.ops || [])
                };
                const res = await fetch("/api/hd", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    throw new Error(err.detail || "No se pudo guardar el ingreso de Hospital de Día.");
                }
                closeHDIntakeModal();
                clearQuickHDSeed();
                loadHD(hdSearchInput?.value || "");
            } catch (err) {
                alert(err.message || "No se pudo guardar el ingreso de Hospital de Día.");
            }
        };

        const closeBtn = els.modal?.querySelector(".close-hd-modal");
        if (closeBtn) closeBtn.onclick = closeHDIntakeModal;
        if (els.modal) {
            els.modal.addEventListener("click", (e) => {
                if (e.target === els.modal) closeHDIntakeModal();
            });
        }
    }

    window.selectHDPatientSuggestion = (idx) => {
        const patient = hdSearchSuggestions[idx];
        if (!patient) return;
        hdFillPatientForm(patient, { keepLocalidad: true });
    };

    window.openHDIntakeModalFromQuick = async () => {
        await initHDIntakeModal();
        const els = getHDElements();
        hdResetForm({
            localidad: document.getElementById("hq-loc")?.value.trim() || "SM",
            diagnostico: document.getElementById("hq-diag")?.value.trim() || "",
            ordenElect: document.getElementById("hq-orden")?.value.trim() || "",
            searchText: hqSelectedPatient?.apellido_nombre || "",
            patientName: !hqSelectedPatient ? (hqSearch?.value.trim() || "") : ""
        });
        if (hqSelectedPatient) {
            hdFillPatientForm(hqSelectedPatient, { keepLocalidad: true });
        } else {
            await hdPrepareNewPatientNumbers();
            if (els.apellidoNombre?.value) els.apellidoNombre.value = els.apellidoNombre.value.toUpperCase();
        }
        if (els.modal) els.modal.style.display = "block";
    };

    document.addEventListener("DOMContentLoaded", () => {
        void initHDIntakeModal();
    });

    // Search
    if (hdSearchInput) hdSearchInput.oninput = e => loadHD(e.target.value);

    loadHD();

    // Impresión de Planilla Diaria
    const printBtn = document.getElementById('print-agenda-btn');
    if (printBtn) {
        printBtn.onclick = () => {
            const selectedDate = agendaDateFilter.value;
            if (!selectedDate) return alert("Seleccione una fecha primero.");

            // Crear el contenedor de impresión si no existe
            let printArea = document.getElementById('print-area');
            if (!printArea) {
                printArea = document.createElement('div');
                printArea.id = 'print-area';
                document.body.appendChild(printArea);
            }

            const dObj = new Date(selectedDate + 'T00:00:00');
            const weekdayShort = dObj.toLocaleDateString('es-AR', { weekday: 'short' }).replace('.', '');
            const numericDate = dObj.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            const printTitle = `Mi d\u00eda : ${weekdayShort}, ${numericDate}`;

            // Obtener turnos cargados actualmente en el grid
            const rows = Array.from(gridBody.querySelectorAll('tr'));
            let tableHTML = `
                <div class="print-header print-header-excel">${escapeHtml(printTitle)}</div>
                <table class="print-table">
                    <thead>
                        <tr>
                            <th class="print-time-head">Hora</th>
                            ${agendaResources.map(resource => `<th>${escapeHtml(resource)}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
            `;

            let hasAppointments = false;
            rows.forEach((tr, slotIndex) => {
                const hour = tr.querySelector('.grid-time-column').innerText;
                const cells = Array.from(tr.querySelectorAll('.grid-cell'));
                const printRowClass = slotIndex % 2 === 0 ? 'print-row print-row-shaded' : 'print-row';
                
                cells.forEach((cell, index) => {
                    const chips = cell.querySelectorAll('.appointment-chip');
                    if (chips.length > 0) {
                        hasAppointments = true;
                        const boxName = agendaResources[index];
                        chips.forEach(chip => {
                            const name = chip.dataset.patientName || chip.innerText;
                            // Intentar extraer HC si está en el title
                            const displayBox = chip.dataset.boxName || boxName;
                            tableHTML += `
                                <tr class="${printRowClass}">
                                    <td><strong>${hour}</strong></td>
                                    <td style="font-size: 36pt; font-weight: bold; font-family: Arial, sans-serif;">${escapeHtml(name)}</td>
                                    <td style="font-size: 24pt;">${escapeHtml(displayBox)}</td>
                                    <td style="font-size: 18pt;">-</td>
                                </tr>
                            `;
                        });
                    }
                });
            });

            if (!hasAppointments) {
                alert("No hay turnos cargados para este día.");
                return;
            }

            tableHTML += `</tbody></table>`;
            printArea.innerHTML = tableHTML;

            window.print();
        };
    }

    function printAgendaAsExcelSheet() {
        const selectedDate = agendaDateFilter.value;
        if (!selectedDate) return alert("Seleccione una fecha primero.");

        const formatPrintPatientName = (fullName) => {
            const clean = String(fullName || '').replace(/\s+/g, ' ').trim();
            if (!clean) return '';
            const parts = clean.split(' ');
            if (parts.length <= 2) return clean;
            return `${parts[0]} ${parts[1]}`;
        };

        const dObj = new Date(selectedDate + 'T00:00:00');
        const weekdayShort = dObj.toLocaleDateString('es-AR', { weekday: 'short' }).replace('.', '');
        const numericDate = dObj.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const printTitle = `Mi d\u00eda : ${weekdayShort}, ${numericDate}`;
        const printTimeWidth = 140;
        const printPatientWidth = 470;
        const printRowHeight = 95;

        const rows = Array.from(gridBody.querySelectorAll('tr'));
        let tableHTML = `
            <div class="print-header print-header-excel">${escapeHtml(printTitle)}</div>
            <table class="print-table print-table-excel">
                <thead>
                    <tr>
                        <th class="print-time-head">Hora</th>
                        ${agendaResources.map(resource => `<th>${escapeHtml(resource)}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
        `;

        let hasAppointments = false;

        rows.forEach((tr, slotIndex) => {
            const hour = tr.querySelector('.grid-time-column')?.innerText || '';
            const cells = Array.from(tr.querySelectorAll('.grid-cell'));
            const slotCells = cells.map(cell => Array.from(cell.querySelectorAll('.appointment-chip')).map(chip => ({
                name: chip.dataset.patientName || chip.innerText || '',
                occupied: chip.classList.contains('chip-ocupado')
            })));
            const printRowClass = slotIndex % 2 === 0 ? 'print-row print-row-shaded' : 'print-row';

            if (slotCells.some(items => items.length > 0)) {
                hasAppointments = true;
            }

            tableHTML += `<tr class="${printRowClass}">`;
            tableHTML += `<td class="print-time-cell">${escapeHtml(hour)}</td>`;

            slotCells.forEach(items => {
                const paddedEntries = items.slice(0, 2);
                while (paddedEntries.length < 2) {
                    paddedEntries.push(null);
                }
                const linesHtml = paddedEntries.map(entry => {
                    if (!entry) return `<div class="print-patient-line">&nbsp;</div>`;
                    const extraClass = entry.occupied ? ' print-occupied' : '';
                    return `<div class="print-patient-line${extraClass}"><span class="print-patient-name">${escapeHtml(formatPrintPatientName(entry.name))}</span><span class="print-manual-number-box"></span></div>`;
                }).join('');
                tableHTML += `<td class="print-patient-cell">${linesHtml}</td>`;
            });

            tableHTML += `</tr>`;
        });

        if (!hasAppointments) {
            alert("No hay turnos cargados para este día.");
            return;
        }

        tableHTML += `</tbody></table>`;

        const MM_TO_PX = 96 / 25.4;
        const printableWidthPx = (297 - 12) * MM_TO_PX;
        const printableHeightPx = (210 - 12) * MM_TO_PX;
        const contentWidth = printTimeWidth + (agendaResources.length * printPatientWidth);

        const printWindow = window.open('', '_blank', 'width=1400,height=900');
        if (!printWindow) {
            alert("El navegador bloqueó la ventana de impresión. Permití ventanas emergentes e intentá de nuevo.");
            return;
        }

        const printHtml = `
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Impresión Agenda</title>
  <style>
    @page {
      size: A4 landscape;
      margin: 6mm;
    }
    html, body {
      margin: 0;
      padding: 0;
      background: #fff;
      color: #000;
      font-family: Arial, sans-serif;
    }
    :root {
      --print-scale: 1;
    }
    body {
      overflow: hidden;
    }
    .sheet-viewport {
      width: ${Math.floor(printableWidthPx)}px;
      height: ${Math.floor(printableHeightPx)}px;
      overflow: hidden;
    }
    .sheet {
      width: ${contentWidth}px;
      transform: scale(var(--print-scale));
      transform-origin: top left;
    }
    .print-header {
      margin: 0 0 4px 0;
      font-size: 36pt;
      font-weight: 700;
      line-height: 1;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .print-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    .print-table th,
    .print-table td {
      border: 1px solid #000;
      padding: 3px 4px;
      box-sizing: border-box;
      vertical-align: middle;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .print-table th {
      height: 50px;
      background: #fff;
      font-size: 36pt;
      font-weight: 700;
      text-align: center;
    }
    .print-time-head,
    .print-time-cell {
      width: ${printTimeWidth}px;
      text-align: center;
      font-size: 36pt;
      font-weight: 700;
      white-space: nowrap;
    }
    .print-manual-number-box {
      display: inline-block;
      flex: 0 0 auto;
      width: 48px;
      height: 34px;
      margin-left: 8px;
      border: 2px solid #000;
      background: #fff;
      box-sizing: border-box;
    }
    .print-patient-cell {
      width: ${printPatientWidth}px;
      height: ${printRowHeight}px;
      font-size: 36pt;
      font-weight: 400;
      line-height: 1;
      white-space: normal;
      overflow: hidden;
      text-overflow: clip;
      vertical-align: top;
    }
    .print-row {
      height: ${printRowHeight}px;
    }
    .print-row-shaded td {
      background: #d9d9d9;
    }
    .print-row-shaded .print-time-cell {
      background: #d9d9d9;
    }
    .print-patient-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 42px;
      max-height: 42px;
      padding: 1px 1px;
      overflow: hidden;
      line-height: 0.92;
      word-break: keep-all;
      white-space: nowrap;
    }
    .print-patient-name {
      min-width: 0;
      overflow: hidden;
      text-overflow: clip;
      white-space: nowrap;
    }
    .print-patient-line + .print-patient-line {
      margin-top: 0;
      border-top: 1px solid #9e9e9e;
      padding-top: 3px;
    }
  </style>
</head>
<body>
  <div class="sheet-viewport">
    <div class="sheet">
      ${tableHTML}
    </div>
  </div>
</body>
</html>`;

        printWindow.document.open();
        printWindow.document.write(printHtml);
        printWindow.document.close();
        printWindow.focus();
        printWindow.onload = () => {
            setTimeout(() => {
                const root = printWindow.document.documentElement;
                const sheet = printWindow.document.querySelector('.sheet');
                const printableWidth = Math.floor(printableWidthPx);
                const printableHeight = Math.floor(printableHeightPx);
                const realWidth = Math.max(sheet.scrollWidth || 0, sheet.offsetWidth || 0, 1);
                const realHeight = Math.max(sheet.scrollHeight || 0, sheet.offsetHeight || 0, 1);
                const autoScale = Math.min(printableWidth / realWidth, printableHeight / realHeight, 1) * 0.94;
                root.style.setProperty('--print-scale', autoScale.toFixed(4));
                void sheet.offsetHeight;
                printWindow.print();
                printWindow.onafterprint = () => printWindow.close();
            }, 200);
        };
    }

    if (printBtn) {
        printBtn.onclick = printAgendaAsExcelSheet;
    }

    let realtimeRefreshBusy = false;
    async function refreshActiveRealtimeTab() {
        if (realtimeRefreshBusy || document.hidden) return;
        const activeTab = document.querySelector('.tab-content.active');
        if (!activeTab) return;

        try {
            realtimeRefreshBusy = true;
            if (activeTab.id === 'intersoftic-tab') {
                await loadIntersofticStats();
            } else if (activeTab.id === 'audit-tab') {
                await loadIntersofticAudit();
            }
        } finally {
            realtimeRefreshBusy = false;
        }
    }

    window.setInterval(refreshActiveRealtimeTab, 30000);

    // Initialization
    loadPanelDashboard({ syncOffice: false, silentSync: true });
});
