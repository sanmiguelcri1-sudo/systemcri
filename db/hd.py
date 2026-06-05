import sqlite3
from datetime import date, datetime
from typing import List, Dict, Optional, Any
from db.base import create_connection

from db.matching import upsert_patient_master

def sync_patient_master_from_hd_data(data: Dict) -> bool:
    try:
        upsert_patient_master(data, "hd")
        return True
    except: return False


def _parse_iso_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(str(value or ""), "%Y-%m-%d").date()
    except Exception:
        return None


def _add_one_year(value: date) -> date:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def _format_date_es(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _next_hd_request_date_for_patient(cursor: sqlite3.Cursor, patient_id: int, exclude_hd_id: int = 0) -> Optional[date]:
    rows = cursor.execute(
        """
        SELECT hd.id, hd.estado, o.fecha_val
        FROM hospital_dia hd
        LEFT JOIN hd_ops o ON o.hd_id = hd.id
        WHERE hd.patient_id = ?
          AND (? = 0 OR hd.id <> ?)
        ORDER BY hd.id ASC, o.fecha_val ASC
        """,
        (patient_id, exclude_hd_id or 0, exclude_hd_id or 0),
    ).fetchall()
    if not rows:
        return None

    for row in rows:
        if (row["estado"] or "Activo") == "Activo":
            raise ValueError("AVISO: El paciente ya se encuentra ACTIVO en Hospital de Dia.")

    first_dates_by_hd = {}
    for row in rows:
        parsed = _parse_iso_date(row["fecha_val"])
        if not parsed:
            continue
        hd_id = row["id"]
        if hd_id not in first_dates_by_hd or parsed < first_dates_by_hd[hd_id]:
            first_dates_by_hd[hd_id] = parsed

    if not first_dates_by_hd:
        return None
    latest_cycle_start = max(first_dates_by_hd.values())
    return _add_one_year(latest_cycle_start)


def validate_hd_patient_request_window(cursor: sqlite3.Cursor, patient_id: int, exclude_hd_id: int = 0) -> None:
    next_allowed = _next_hd_request_date_for_patient(cursor, patient_id, exclude_hd_id)
    if next_allowed and date.today() < next_allowed:
        raise ValueError(
            "RESTRICCION DE AUDITORIA: El paciente aun no cumple un año desde el inicio del pedido de OP. "
            f"Proximo pedido permitido: {_format_date_es(next_allowed)}"
        )

def get_hospital_dia(query: str = "") -> List[Dict]:
    conn = create_connection()
    cursor = conn.cursor()
    sql = '''
        SELECT hd.*, p.apellido_nombre, p.dni, p.num_beneficio, p.num_hc
        FROM hospital_dia hd
        JOIN patients p ON hd.patient_id = p.id
    '''
    if query:
        sql += " WHERE p.apellido_nombre LIKE ? OR p.dni LIKE ?"
        cursor.execute(sql, (f"%{query}%", f"%{query}%"))
    else:
        cursor.execute(sql)
    hds = [dict(row) for row in cursor.fetchall()]
    
    if not hds:
        conn.close()
        return []

    # Batch fetch all OPs
    hd_ids = [hd['id'] for hd in hds]
    placeholders = ','.join(['?'] * len(hd_ids))
    cursor.execute(f'SELECT * FROM hd_ops WHERE hd_id IN ({placeholders}) ORDER BY id ASC', hd_ids)
    all_ops = [dict(row) for row in cursor.fetchall()]
    
    ops_by_hd = {}
    for op in all_ops:
        hd_id = op['hd_id']
        if hd_id not in ops_by_hd: ops_by_hd[hd_id] = []
        ops_by_hd[hd_id].append(op)
        
    for hd in hds:
        hd['ops'] = ops_by_hd.get(hd['id'], [])
        
    conn.close()
    return hds

def save_hd_entry(data: Dict) -> int:
    import logging
    conn = create_connection()
    cursor = conn.cursor()
    try:
        p_id = data.get('patient_id')
        if p_id:
            validate_hd_patient_request_window(cursor, int(p_id), int(data.get('id') or 0))

        if 'id' in data and data['id']:
            cursor.execute('''
                UPDATE hospital_dia SET localidad=?, diagnostico=?, orden_elect=?, estado=?, fecha_pedido=?, sesiones_check=?, sesiones_max=? WHERE id=?
            ''', (data.get('localidad',''), data.get('diagnostico',''), data.get('orden_elect',''), data.get('estado', 'Activo'), data.get('fecha_pedido'), data.get('sesiones_check', 0), data.get('sesiones_max', 24), data['id']))
            hd_id = data['id']
            if not data.get('patient_id'):
                cursor.execute("SELECT patient_id FROM hospital_dia WHERE id=?", (hd_id,))
                row = cursor.fetchone()
                if row: data['patient_id'] = row[0]
        else:
            cursor.execute('''
                INSERT INTO hospital_dia (patient_id, localidad, diagnostico, orden_elect, estado, fecha_pedido, sesiones_check, sesiones_max)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['patient_id'], data.get('localidad',''), data.get('diagnostico',''), data.get('orden_elect',''), data.get('estado', 'Activo'), data.get('fecha_pedido'), data.get('sesiones_check', 0), data.get('sesiones_max', 24)))
            hd_id = cursor.lastrowid

        p_id = data.get('patient_id')
        if p_id:
            if data.get('num_beneficio') and str(data['num_beneficio']).strip() not in ('', '-', '—'):
                cursor.execute("UPDATE patients SET num_beneficio = ? WHERE id = ?", (str(data['num_beneficio']).strip(), p_id))
            if data.get('dni') and str(data['dni']).strip() not in ('', '-', '—'):
                cursor.execute("UPDATE patients SET dni = ? WHERE id = ?", (str(data['dni']).strip(), p_id))
            if data.get('localidad') and str(data['localidad']).strip() not in ('', '-', '—'):
                cursor.execute("UPDATE patients SET localidad = CASE WHEN localidad IS NULL OR localidad = '' THEN ? ELSE localidad END WHERE id = ?", (str(data['localidad']).strip(), p_id))

        if 'ops' in data:
            cursor.execute('DELETE FROM hd_ops WHERE hd_id = ?', (hd_id,))
            for op in data['ops']:
                if op.get('op_number') or op.get('fecha_val'):
                    cursor.execute('INSERT INTO hd_ops (hd_id, op_number, fecha_val, color_code) VALUES (?, ?, ?, ?)', (hd_id, op.get('op_number',''), op.get('fecha_val',''), op.get('color_code', '')))

        conn.commit()
        sync_patient_master_from_hd_data(data)
        return hd_id
    except ValueError:
        conn.rollback()
        raise
    except Exception as e:
        logging.error(f"Error saving HD entry: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()

def delete_hd_entry(hd_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM hd_ops WHERE hd_id = ?', (hd_id,))
        cursor.execute('DELETE FROM hospital_dia WHERE id = ?', (hd_id,))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def check_op_duplicate(op_number: str, exclude_hd_id: Optional[int] = None) -> List[Dict]:
    """Busca si un número de OP ya está siendo usado por otro paciente en HD."""
    if not op_number or len(op_number) < 5: return []
    conn = create_connection()
    cursor = conn.cursor()
    sql = '''
        SELECT p.apellido_nombre, p.dni, o.op_number, o.fecha_val
        FROM hd_ops o
        JOIN hospital_dia hd ON o.hd_id = hd.id
        JOIN patients p ON hd.patient_id = p.id
        WHERE o.op_number = ?
    '''
    params = [op_number]
    if exclude_hd_id:
        sql += " AND hd.id <> ?"
        params.append(exclude_hd_id)
    
    cursor.execute(sql, params)
    res = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return res
