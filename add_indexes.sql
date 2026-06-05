-- =============================================================================
-- HC: Índices de Performance
-- Generado: 2026-05-04
-- Aplicar con: sqlite3 hc_archive.db < add_indexes.sql
-- Todos los CREATE son IF NOT EXISTS → seguro re-ejecutar.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- PATIENTS
-- Impacto principal: find_patient() en load_hd_data.py y sync_neuro_dni_from_office.py
-- se ejecuta por cada paciente en cada sync (potencialmente 500+ veces).
-- -----------------------------------------------------------------------------

-- Búsqueda por nombre exacto (find_patient → WHERE apellido_nombre = ?)
CREATE INDEX IF NOT EXISTS idx_patients_apellido_nombre
    ON patients (apellido_nombre);

-- Búsqueda por DNI (sync_pac_csv, rebuild_patient_master, pami_refiner)
-- WHERE dni = ? / WHERE STARTS WITH 'TEMP_'
CREATE INDEX IF NOT EXISTS idx_patients_dni
    ON patients (dni);

-- Búsqueda por num_beneficio (load_hd_data find_patient paso 4, pami_refiner)
CREATE INDEX IF NOT EXISTS idx_patients_num_beneficio
    ON patients (num_beneficio);

-- Búsqueda por mdb_id (sync_from_csv_v2 → patient_db_id_map lookup en restore)
CREATE INDEX IF NOT EXISTS idx_patients_mdb_id
    ON patients (mdb_id);

-- Filtro por vigencia (dashboard, renovaciones vencidas)
-- WHERE anio_vigencia = ? AND mes_renovacion = ?
CREATE INDEX IF NOT EXISTS idx_patients_vigencia
    ON patients (anio_vigencia, mes_renovacion);

-- -----------------------------------------------------------------------------
-- AGENDA_GENERAL
-- Impacto: sync_from_csv_v2 inserta 26K+ filas. La UI filtra por fecha y recurso.
-- -----------------------------------------------------------------------------

-- Filtro principal de agenda (vista por día/semana)
-- WHERE fecha = ? / WHERE fecha BETWEEN ? AND ?
CREATE INDEX IF NOT EXISTS idx_agenda_fecha
    ON agenda_general (fecha);

-- Filtro por paciente (historial de turnos)
CREATE INDEX IF NOT EXISTS idx_agenda_patient_id
    ON agenda_general (patient_id);

-- Filtro combinado fecha + recurso (vista por box/sala)
CREATE INDEX IF NOT EXISTS idx_agenda_fecha_recurso
    ON agenda_general (fecha, recurso);

-- Deduplicación en sync (fecha + hora + recurso + patient_id)
-- El sync actual hace INSERT sin check → este índice ayuda a detectar duplicados
CREATE INDEX IF NOT EXISTS idx_agenda_dedup
    ON agenda_general (patient_id, fecha, hora, recurso);

-- Filtro por fecha_carga (preserve_existing_created en sync_from_csv_v2)
CREATE INDEX IF NOT EXISTS idx_agenda_fecha_carga
    ON agenda_general (fecha_carga);

-- -----------------------------------------------------------------------------
-- NEURO_PATIENTS
-- Impacto: sync_neuro_google_sheet hace SELECT por fecha+hora en cada upsert.
-- Con ~500 registros hoy, pero crece mensualmente.
-- -----------------------------------------------------------------------------

-- Lookup principal del upsert (WHERE fecha = ? AND hora = ?)
CREATE INDEX IF NOT EXISTS idx_neuro_fecha_hora
    ON neuro_patients (fecha, hora);

-- Búsqueda por DNI (sync_pac_csv, sync_neuro_dni_from_office)
CREATE INDEX IF NOT EXISTS idx_neuro_dni
    ON neuro_patients (dni);

-- Filtro de pacientes sin DNI (sync_neuro_dni_from_office → WHERE dni IS NULL OR dni = '')
-- SQLite puede usar índice parcial con expresión
CREATE INDEX IF NOT EXISTS idx_neuro_sin_dni
    ON neuro_patients (id)
    WHERE dni IS NULL OR TRIM(dni) = '';

-- -----------------------------------------------------------------------------
-- HOSPITAL_DIA
-- Impacto: load_hd_data hace DELETE + INSERT completo. La UI filtra por estado.
-- -----------------------------------------------------------------------------

-- Lookup por patient_id (JOIN en load_hd_data, UI de detalle)
CREATE INDEX IF NOT EXISTS idx_hd_patient_id
    ON hospital_dia (patient_id);

-- Filtro por estado (Activo / Suspendido) — usado en dashboard
CREATE INDEX IF NOT EXISTS idx_hd_estado
    ON hospital_dia (estado);

-- -----------------------------------------------------------------------------
-- HD_OPS
-- Impacto: carga masiva en load_hd_data (~80 ops). Subquery de conteo en UI.
-- (SELECT COUNT(*) FROM hd_ops WHERE hd_id = hd.id) — se ejecuta por cada fila HD
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_hd_ops_hd_id
    ON hd_ops (hd_id);

-- -----------------------------------------------------------------------------
-- RENEWALS
-- Impacto: historial de ciclos, filtros por año/mes en estadísticas
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_renewals_patient_id
    ON renewals (patient_id);

CREATE INDEX IF NOT EXISTS idx_renewals_anio_mes
    ON renewals (anio, mes);

-- -----------------------------------------------------------------------------
-- PATIENT_MASTER (si existe)
-- Impacto: sync_pac_csv hace full scan de patient_master en cada sync
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_patient_master_patient_id
    ON patient_master (patient_id);

CREATE INDEX IF NOT EXISTS idx_patient_master_dni
    ON patient_master (dni);

CREATE INDEX IF NOT EXISTS idx_patient_master_num_beneficio
    ON patient_master (num_beneficio);

-- =============================================================================
-- VERIFICACIÓN (ejecutar después para confirmar)
-- =============================================================================
-- sqlite3 hc_archive.db ".indexes"
-- sqlite3 hc_archive.db "EXPLAIN QUERY PLAN SELECT * FROM agenda_general WHERE fecha = '2026-05-04'"
-- =============================================================================
