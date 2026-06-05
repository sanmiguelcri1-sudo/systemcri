import sqlite3
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from db.base import create_connection

def upsert_staff(
    *,
    staff_key: str,
    nombre: str,
    cargo: str = "",
    include_in_word: bool = True,
    fecha_ingreso: str = "",
    fecha_egreso: str = "",
    default_ingreso: str = "",
    default_egreso: str = "",
) -> int:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO staff (staff_key, nombre, cargo, include_in_word, fecha_ingreso, fecha_egreso, default_ingreso, default_egreso, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(staff_key) DO UPDATE SET
            nombre = excluded.nombre,
            cargo = excluded.cargo,
            include_in_word = excluded.include_in_word,
            fecha_ingreso = excluded.fecha_ingreso,
            fecha_egreso = excluded.fecha_egreso,
            default_ingreso = excluded.default_ingreso,
            default_egreso = excluded.default_egreso,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (staff_key, nombre, cargo or "", 1 if include_in_word else 0, fecha_ingreso or "", fecha_egreso or "", default_ingreso or "", default_egreso or ""),
    )
    conn.commit()
    cursor.execute("SELECT id FROM staff WHERE staff_key = ?", (staff_key,))
    row = cursor.fetchone()
    conn.close()
    return int(row["id"]) if row else 0

def update_staff_intersoftic_details(
    *,
    staff_key: str,
    intersoftic_profesional_id: int,
    intersoftic_activo: str = "",
    tipo_documento: str = "",
    documento: str = "",
    matricula_1: str = "",
    matricula_2: str = "",
    telefono: str = "",
    movil: str = "",
    mail: str = "",
    sucursal_intersoftic_id: int = 0,
    sucursal_intersoftic: str = "",
    sucursal_detectada_2026: str = "",
    efectores_2026: int = 0,
    especialidades_detectadas: str = "",
    domicilio_laboral: str = "",
    color_localizacion: str = "",
    motivo_baja: str = "",
    observaciones_intersoftic: str = "",
) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        UPDATE staff SET
            intersoftic_profesional_id = ?,
            intersoftic_activo = ?,
            tipo_documento = ?,
            documento = ?,
            matricula_1 = ?,
            matricula_2 = ?,
            telefono = ?,
            movil = ?,
            mail = ?,
            sucursal_intersoftic_id = ?,
            sucursal_intersoftic = ?,
            sucursal_detectada_2026 = ?,
            efectores_2026 = ?,
            especialidades_detectadas = ?,
            domicilio_laboral = ?,
            color_localizacion = ?,
            motivo_baja = ?,
            observaciones_intersoftic = ?,
            intersoftic_synced_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE staff_key = ?
        ''',
        (
            int(intersoftic_profesional_id or 0),
            str(intersoftic_activo or ""),
            str(tipo_documento or ""),
            str(documento or ""),
            str(matricula_1 or ""),
            str(matricula_2 or ""),
            str(telefono or ""),
            str(movil or ""),
            str(mail or ""),
            int(sucursal_intersoftic_id or 0),
            str(sucursal_intersoftic or ""),
            str(sucursal_detectada_2026 or ""),
            int(efectores_2026 or 0),
            str(especialidades_detectadas or ""),
            str(domicilio_laboral or ""),
            str(color_localizacion or ""),
            str(motivo_baja or ""),
            str(observaciones_intersoftic or ""),
            str(staff_key),
        ),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def list_staff(*, include_inactive: bool = True) -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    if include_inactive:
        cursor.execute("SELECT * FROM staff ORDER BY nombre")
    else:
        cursor.execute("SELECT * FROM staff WHERE (fecha_egreso IS NULL OR fecha_egreso = '') ORDER BY nombre")
    rows = cursor.fetchall()
    conn.close()
    return rows

def list_intersoftic_professionals() -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT *
        FROM intersoftic_professionals
        ORDER BY nombre_completo
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def upsert_intersoftic_professional(data: Dict[str, Any]) -> int:
    conn = create_connection()
    cursor = conn.cursor()
    prof_id = int(data.get("id") or 0)
    fields = {
        "nombre_completo": str(data.get("nombre_completo") or "").strip().upper(),
        "documento": str(data.get("documento") or "").strip().upper(),
        "matricula_1": str(data.get("matricula_1") or "").strip().upper(),
        "matricula_2": str(data.get("matricula_2") or "").strip().upper(),
        "telefono": str(data.get("telefono") or "").strip().upper(),
        "movil": str(data.get("movil") or "").strip().upper(),
        "mail": str(data.get("mail") or "").strip(),
        "fecha_nacimiento": str(data.get("fecha_nacimiento") or "").strip(),
        "numero_emergencia": str(data.get("numero_emergencia") or "").strip().upper(),
        "profesion": str(data.get("profesion") or "").strip().upper(),
        "sucursal_intersoftic": str(data.get("sucursal_intersoftic") or data.get("sucursal") or "").strip().upper(),
        "sucursal_detectada_2026": str(data.get("sucursal_detectada_2026") or data.get("sucursal") or "").strip().upper(),
        "efectores_2026": int(data.get("efectores_2026") or 0),
    }
    if prof_id:
        cursor.execute(
            '''
            UPDATE intersoftic_professionals SET
                nombre_completo=?, documento=?, matricula_1=?, matricula_2=?, telefono=?, movil=?, mail=?,
                fecha_nacimiento=?, numero_emergencia=?, profesion=?, sucursal_intersoftic=?,
                sucursal_detectada_2026=?, efectores_2026=?, synced_at=CURRENT_TIMESTAMP
            WHERE id=?
            ''',
            (
                fields["nombre_completo"], fields["documento"], fields["matricula_1"], fields["matricula_2"],
                fields["telefono"], fields["movil"], fields["mail"], fields["fecha_nacimiento"],
                fields["numero_emergencia"], fields["profesion"], fields["sucursal_intersoftic"],
                fields["sucursal_detectada_2026"], fields["efectores_2026"], prof_id,
            ),
        )
    else:
        next_intersoftic_id = cursor.execute(
            "SELECT COALESCE(MIN(intersoftic_profesional_id), 0) - 1 FROM intersoftic_professionals WHERE intersoftic_profesional_id < 0"
        ).fetchone()[0]
        cursor.execute(
            '''
            INSERT INTO intersoftic_professionals (
                intersoftic_profesional_id, activo, nombre_completo, documento, matricula_1, matricula_2,
                telefono, movil, mail, fecha_nacimiento, numero_emergencia, profesion,
                sucursal_intersoftic, sucursal_detectada_2026, efectores_2026, origen, synced_at
            )
            VALUES (?, 'S', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'MANUAL', CURRENT_TIMESTAMP)
            ''',
            (
                int(next_intersoftic_id or -1), fields["nombre_completo"], fields["documento"],
                fields["matricula_1"], fields["matricula_2"], fields["telefono"], fields["movil"],
                fields["mail"], fields["fecha_nacimiento"], fields["numero_emergencia"], fields["profesion"],
                fields["sucursal_intersoftic"], fields["sucursal_detectada_2026"], fields["efectores_2026"],
            ),
        )
        prof_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return prof_id

def delete_intersoftic_professional(professional_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM intersoftic_professionals WHERE id = ?", (int(professional_id),))
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def get_staff_by_key(staff_key: str) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff WHERE staff_key = ? LIMIT 1", (staff_key,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_staff_by_id(staff_id: int) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff WHERE id = ? LIMIT 1", (int(staff_id),))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_staff(staff_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM staff_attendance WHERE staff_id = ?", (int(staff_id),))
    cursor.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def upsert_staff_attendance(
    *,
    staff_id: int,
    fecha: str,
    ingreso: str = "",
    egreso: str = "",
    horas: float = 0.0,
    observaciones: str = "",
) -> int:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO staff_attendance (staff_id, fecha, ingreso, egreso, horas, observaciones, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(staff_id, fecha) DO UPDATE SET
            ingreso = excluded.ingreso,
            egreso = excluded.egreso,
            horas = excluded.horas,
            observaciones = excluded.observaciones,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (int(staff_id), str(fecha), str(ingreso or ""), str(egreso or ""), float(horas or 0.0), str(observaciones or "")),
    )
    conn.commit()
    cursor.execute("SELECT id FROM staff_attendance WHERE staff_id = ? AND fecha = ?", (int(staff_id), str(fecha)))
    row = cursor.fetchone()
    conn.close()
    return int(row["id"]) if row else 0

def get_staff_attendance(*, staff_id: int, fecha: str) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staff_attendance WHERE staff_id = ? AND fecha = ? LIMIT 1", (int(staff_id), str(fecha)))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_staff_attendance(attendance_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM staff_attendance WHERE id = ?", (int(attendance_id),))
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def delete_staff_attendance_for_staff_date(*, staff_id: int, fecha: str) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM staff_attendance WHERE staff_id = ? AND fecha = ?", (int(staff_id), str(fecha)))
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def list_staff_attendance_by_month(*, year: int, month: int) -> List[sqlite3.Row]:
    month, year = int(month), int(year)
    start = f"{year:04d}-{month:02d}-01"
    end_dt = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.nombre, s.cargo, s.staff_key
        FROM staff_attendance a
        JOIN staff s ON s.id = a.staff_id
        WHERE a.fecha BETWEEN ? AND ?
        ORDER BY a.fecha, s.nombre
    ''', (start, end))
    rows = cursor.fetchall()
    conn.close()
    return rows

def list_staff_attendance_for_staff_by_month(*, staff_id: int, year: int, month: int) -> List[sqlite3.Row]:
    month, year = int(month), int(year)
    start = f"{year:04d}-{month:02d}-01"
    end_dt = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.nombre, s.cargo, s.staff_key
        FROM staff_attendance a
        JOIN staff s ON s.id = a.staff_id
        WHERE a.staff_id = ? AND a.fecha BETWEEN ? AND ?
        ORDER BY a.fecha
    ''', (int(staff_id), start, end))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_staff_attendance_for_staff_month(*, staff_id: int, year: int, month: int) -> int:
    month, year = int(month), int(year)
    start = f"{year:04d}-{month:02d}-01"
    end_dt = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM staff_attendance WHERE staff_id = ? AND fecha BETWEEN ? AND ?", (int(staff_id), start, end))
    conn.commit()
    deleted = int(cursor.rowcount or 0)
    conn.close()
    return deleted

def get_staff_month_totals(*, year: int, month: int, include_in_word_only: bool = False) -> List[sqlite3.Row]:
    month, year = int(month), int(year)
    start = f"{year:04d}-{month:02d}-01"
    end_dt = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")
    conn = create_connection()
    cursor = conn.cursor()
    where = [
        "(s.fecha_ingreso IS NULL OR s.fecha_ingreso = '' OR s.fecha_ingreso <= ?)",
        "(s.fecha_egreso IS NULL OR s.fecha_egreso = '' OR s.fecha_egreso >= ?)"
    ]
    params = [end, start, start, end]
    if include_in_word_only: where.append("s.include_in_word = 1")
    cursor.execute(f'''
        SELECT s.id AS staff_id, s.staff_key, s.nombre, s.cargo, s.include_in_word, s.fecha_ingreso, s.fecha_egreso, COALESCE(SUM(a.horas), 0) AS total_horas
        FROM staff s
        LEFT JOIN staff_attendance a ON a.staff_id = s.id AND a.fecha BETWEEN ? AND ?
        WHERE {" AND ".join(where)}
        GROUP BY s.id ORDER BY s.nombre
    ''', params)
    rows = cursor.fetchall()
    conn.close()
    return rows
