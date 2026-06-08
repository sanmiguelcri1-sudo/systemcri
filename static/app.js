(function () {
  const state = {
    stats: null,
    audit: null,
    statsBranch: "all",
    auditBranch: "all",
    auditSearch: "",
  };

  const $ = (id) => document.getElementById(id);
  const fmt = (value) => Number(value || 0).toLocaleString("es-AR");

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function statCard(label, value, sub = "", extraClass = "") {
    return `
      <div class="panel-stat ${extraClass}">
        <span class="panel-stat-label">${escapeHtml(label)}</span>
        <span class="panel-stat-value">${fmt(value)}</span>
        ${sub ? `<span class="panel-stat-sub">${escapeHtml(sub)}</span>` : ""}
      </div>
    `;
  }

  function setActiveTab(tabId) {
    document.querySelectorAll(".nav-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    });
    document.querySelectorAll(".tab-content").forEach((section) => {
      section.classList.toggle("active", section.id === tabId);
    });
    if (tabId === "intersoftic-tab" && !state.stats) loadIntersofticStats();
    if (tabId === "audit-tab" && !state.audit) loadIntersofticAudit();
  }

  function setBranch(groupId, branchId, key, render) {
    state[key] = branchId;
    document.querySelectorAll(`#${groupId} .branch-btn`).forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.branch === branchId);
    });
    render();
  }

  function selectedStatsBranches() {
    const branches = (state.stats && state.stats.branches) || [];
    if (state.statsBranch === "all") return branches;
    return branches.filter((branch) => branch.branch_id === state.statsBranch);
  }

  function sumTotals(branches) {
    const keys = [
      "mdta",
      "capita_250101",
      "capita_250102",
      "neuro",
      "to",
      "fono",
      "hd",
      "fisiatra",
      "domicilio",
      "traslado",
      "total",
    ];
    const totals = Object.fromEntries(keys.map((key) => [key, 0]));
    branches.forEach((branch) => {
      keys.forEach((key) => {
        totals[key] += Number((branch.totals || {})[key] || 0);
      });
    });
    return totals;
  }

  function renderStats() {
    const body = $("intersoftic-body");
    const summary = $("intersoftic-summary");
    if (!body || !summary) return;

    const branches = selectedStatsBranches();
    const totals = sumTotals(branches);
    summary.innerHTML = [
      statCard("Total general", totals.total, state.statsBranch === "all" ? "Todas las sucursales" : branches[0]?.branch || ""),
      statCard("MDTA", totals.mdta),
      statCard("Cápita", totals.capita_250101 + totals.capita_250102, "250101 + 250102"),
      statCard("Neuro", totals.neuro),
      statCard("Fono / TO", totals.fono + totals.to),
      statCard("Hospital de Día", totals.hd),
    ].join("");

    if (!branches.length) {
      body.innerHTML = `<tr><td colspan="12">No hay datos para esta sucursal.</td></tr>`;
      return;
    }

    body.innerHTML = branches
      .map((branch) => {
        const rows = (branch.rows || [])
          .map(
            (row) => `
              <tr>
                <td>${escapeHtml(row.mes)}</td>
                <td>${fmt(row.mdta)}</td>
                <td>${fmt(row.capita_250101)}</td>
                <td>${fmt(row.capita_250102)}</td>
                <td>${fmt(row.neuro)}</td>
                <td>${fmt(row.to)}</td>
                <td>${fmt(row.fono)}</td>
                <td>${fmt(row.hd)}</td>
                <td>${fmt(row.fisiatra)}</td>
                <td>${fmt(row.domicilio)}</td>
                <td>${fmt(row.traslado)}</td>
                <td><strong>${fmt(row.total)}</strong></td>
              </tr>
            `
          )
          .join("");
        const t = branch.totals || {};
        return `
          <tr class="total-row">
            <td>${escapeHtml(branch.branch)}</td>
            <td>${fmt(t.mdta)}</td>
            <td>${fmt(t.capita_250101)}</td>
            <td>${fmt(t.capita_250102)}</td>
            <td>${fmt(t.neuro)}</td>
            <td>${fmt(t.to)}</td>
            <td>${fmt(t.fono)}</td>
            <td>${fmt(t.hd)}</td>
            <td>${fmt(t.fisiatra)}</td>
            <td>${fmt(t.domicilio)}</td>
            <td>${fmt(t.traslado)}</td>
            <td>${fmt(t.total)}</td>
          </tr>
          ${rows}
        `;
      })
      .join("");
  }

  async function loadIntersofticStats() {
    const btn = $("refresh-intersoftic-btn");
    const meta = $("intersoftic-meta");
    const body = $("intersoftic-body");
    if (btn) btn.disabled = true;
    if (meta) meta.textContent = "Actualizando datos desde Intersoftic...";
    if (body) body.innerHTML = `<tr><td colspan="12" class="loading">Consultando Intersoftic...</td></tr>`;

    try {
      const res = await fetch(`/api/intersoftic-stats?t=${Date.now()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "No se pudo cargar estadística.");
      state.stats = data;
      if (meta) meta.textContent = `Año ${data.year || "2026"} · Actualizado ${new Date().toLocaleString("es-AR")}`;
      renderStats();
    } catch (error) {
      if (meta) meta.textContent = "Error al actualizar.";
      if (body) body.innerHTML = `<tr><td colspan="12">${escapeHtml(error.message)}</td></tr>`;
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function selectedAuditBranches() {
    const branches = (state.audit && state.audit.branches) || [];
    if (state.auditBranch === "all") return branches;
    return branches.filter((branch) => branch.branch_id === state.auditBranch);
  }

  function auditMatchesSearch(item) {
    const q = state.auditSearch.trim().toLowerCase();
    if (!q) return true;
    return JSON.stringify(item || {}).toLowerCase().includes(q);
  }

  function renderAuditTable(headers, rows, columns, emptyText) {
    const filtered = rows.filter(auditMatchesSearch);
    if (!filtered.length) return `<div class="audit-empty">${escapeHtml(emptyText)}</div>`;
    return `
      <div class="table-container">
        <table class="audit-table">
          <thead>
            <tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${filtered
              .map(
                (row) => `
                  <tr>
                    ${columns.map((column) => `<td>${column(row)}</td>`).join("")}
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderAuditBranch(branch) {
    const summary = branch.summary || {};
    const alertCount =
      Number(summary.total_date_errors || 0) +
      Number(summary.total_session_errors || 0) +
      Number(summary.total_ugl_errors || 0);
    const badge = branch.available === false
      ? `<span class="audit-badge audit-badge-error">Sin conexión</span>`
      : alertCount
        ? `<span class="audit-badge audit-badge-alert">${fmt(alertCount)} alertas</span>`
        : `<span class="audit-badge audit-badge-ok">Sin alertas</span>`;

    const rawSourceErrors = branch.source_errors || (branch.sql_error ? [branch.sql_error] : []);
    const sourceErrors = rawSourceErrors
      .filter(Boolean)
      .map((error) => `<div class="audit-sql-error"><i class="fas fa-circle-info"></i>${escapeHtml(error)}</div>`)
      .join("");

    const dateTable = renderAuditTable(
      ["Fecha", "Día", "Motivo", "Paciente", "Afiliado", "Prestación", "Cantidad", "Registro", "Orden"],
      branch.date_errors || [],
      [
        (row) => escapeHtml(row.fecha),
        (row) => escapeHtml(row.dia_semana),
        (row) => `<span class="audit-motivo-badge ${String(row.motivo || "").includes("FERIADO") ? "audit-motivo-feriado" : "audit-motivo-finsemana"}">${escapeHtml(row.motivo)}</span>`,
        (row) => escapeHtml(row.paciente),
        (row) => escapeHtml(row.afiliado),
        (row) => `<code>${escapeHtml(row.prestacion)}</code>`,
        (row) => fmt(row.cantidad),
        (row) => escapeHtml(row.registro_id || ""),
        (row) => escapeHtml(row.orden_id || ""),
      ],
      "No hay errores de fecha para mostrar."
    );

    const sessionTable = renderAuditTable(
      ["Paciente", "Afiliado", "Mes", "Sesiones", "Exceso", "Fechas"],
      branch.session_errors || [],
      [
        (row) => escapeHtml(row.paciente),
        (row) => escapeHtml(row.afiliado),
        (row) => escapeHtml(row.mes),
        (row) => `<span class="audit-session-count">${fmt(row.sesiones)}</span>`,
        (row) => `<span class="audit-excess-badge">+${fmt(Number(row.sesiones || 0) - Number(row.max_permitido || 10))}</span>`,
        (row) => escapeHtml((row.fechas || []).join(", ")),
      ],
      "No hay pacientes con más de 10 sesiones mensuales."
    );

    const uglTable = renderAuditTable(
      ["Paciente", "DNI", "Afiliado", "UGL actual", "Esperado", "Prestaciones"],
      branch.ugl_errors || [],
      [
        (row) => escapeHtml(row.paciente),
        (row) => escapeHtml(row.documento),
        (row) => escapeHtml(row.afiliado),
        (row) => escapeHtml(row.ugl_actual),
        (row) => escapeHtml(row.esperado),
        (row) => escapeHtml((row.prestaciones || []).join(", ")),
      ],
      "No hay diferencias de UGL para mostrar."
    );

    return `
      <article class="audit-branch-block">
        <div class="audit-branch-head">
          <h2>${escapeHtml(branch.branch)}</h2>
          ${badge}
        </div>
        ${sourceErrors}
        <div class="audit-section">
          <h3>Fechas cargadas en feriados o fines de semana <span class="audit-count-badge">${fmt(summary.total_date_errors)}</span></h3>
          ${dateTable}
        </div>
        <div class="audit-section">
          <h3>Pacientes con más de 10 sesiones mensuales <span class="audit-count-badge">${fmt(summary.total_session_errors)}</span></h3>
          ${sessionTable}
        </div>
        <div class="audit-section">
          <h3>UGL incorrecta por sucursal <span class="audit-count-badge">${fmt(summary.total_ugl_errors)}</span></h3>
          ${uglTable}
        </div>
      </article>
    `;
  }

  function renderAudit() {
    const summaryEl = $("audit-summary");
    const container = $("audit-container");
    if (!summaryEl || !container) return;

    const branches = selectedAuditBranches();
    const summary = branches.reduce(
      (acc, branch) => {
        const s = branch.summary || {};
        acc.total_date_errors += Number(s.total_date_errors || 0);
        acc.total_session_errors += Number(s.total_session_errors || 0);
        acc.total_ugl_errors += Number(s.total_ugl_errors || 0);
        acc.feriados_count += Number(s.feriados_count || 0);
        acc.sabados_count += Number(s.sabados_count || 0);
        acc.domingos_count += Number(s.domingos_count || 0);
        return acc;
      },
      {
        total_date_errors: 0,
        total_session_errors: 0,
        total_ugl_errors: 0,
        feriados_count: 0,
        sabados_count: 0,
        domingos_count: 0,
      }
    );

    summaryEl.innerHTML = [
      statCard("Errores de fecha", summary.total_date_errors, "Feriados y fines de semana", summary.total_date_errors ? "stat-danger" : "stat-ok"),
      statCard("Exceso de sesiones", summary.total_session_errors, "Más de 10 por mes", summary.total_session_errors ? "stat-danger" : "stat-ok"),
      statCard("UGL incorrecta", summary.total_ugl_errors, "Según sucursal", summary.total_ugl_errors ? "stat-warn" : "stat-ok"),
      statCard("Feriados", summary.feriados_count),
      statCard("Sábados", summary.sabados_count),
      statCard("Domingos", summary.domingos_count),
    ].join("");

    if (!branches.length) {
      container.innerHTML = `<div class="message-box">No hay datos de auditoría para esta sucursal.</div>`;
      return;
    }

    container.innerHTML = branches.map(renderAuditBranch).join("");
  }

  async function loadIntersofticAudit() {
    const btn = $("refresh-audit-btn");
    const meta = $("audit-meta");
    const container = $("audit-container");
    if (btn) btn.disabled = true;
    if (meta) meta.textContent = "Actualizando auditoría desde Intersoftic...";
    if (container) container.innerHTML = `<div class="loading">Consultando auditoría...</div>`;

    try {
      const res = await fetch(`/api/intersoftic-audit?t=${Date.now()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "No se pudo cargar auditoría.");
      state.audit = data;
      if (meta) meta.textContent = `Año ${data.year || "2026"} · Actualizado ${new Date().toLocaleString("es-AR")}`;
      renderAudit();
    } catch (error) {
      if (meta) meta.textContent = "Error al actualizar.";
      if (container) container.innerHTML = `<div class="message-box">${escapeHtml(error.message)}</div>`;
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
    });

    document.querySelectorAll("#intersoftic-branch-tabs .branch-btn").forEach((btn) => {
      btn.addEventListener("click", () => setBranch("intersoftic-branch-tabs", btn.dataset.branch, "statsBranch", renderStats));
    });

    document.querySelectorAll("#audit-branch-tabs .branch-btn").forEach((btn) => {
      btn.addEventListener("click", () => setBranch("audit-branch-tabs", btn.dataset.branch, "auditBranch", renderAudit));
    });

    $("refresh-intersoftic-btn")?.addEventListener("click", loadIntersofticStats);
    $("refresh-audit-btn")?.addEventListener("click", loadIntersofticAudit);
    $("audit-search")?.addEventListener("input", (event) => {
      state.auditSearch = event.target.value || "";
      renderAudit();
    });

    loadIntersofticStats();
  });
})();
