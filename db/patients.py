import sqlite3
import calendar
import csv
import os
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from db.base import create_connection
from utils.text import normalize_text, normalize_name, normalize_digits, is_blank

from db.matching import upsert_patient_master, row_to_dict

_OFFICE_APPOINTMENTS_CACHE = {"mtime": None, "items": {}}

def sync_patient_master_from_patient_id(p_id: int) -> bool:
    """Sincroniza los datos de un paciente específico hacia la tabla maestra."""
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM patients WHERE id = ?", (p_id,))
        p = cursor.fetchone()
        if not p: return False
        upsert_patient_master(row_to_dict(p), "patient")
        return True
    except: return False
    finally: conn.close()

def insert_patient(data: Dict) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        # Check if exists (UPPER+TRIM comparison or ID if provided)
        p_id = data.get('id')
        row = None
        if p_id:
            cursor.execute("SELECT id FROM patients WHERE id = ?", (p_id,))
            row = cursor.fetchone()
        else:
            cursor.execute("SELECT id FROM patients WHERE UPPER(TRIM(apellido_nombre)) = ? AND (dni = ? OR num_beneficio = ?)",
                           (data['apellido_nombre'].upper(), data['dni'], data['num_beneficio']))
            row = cursor.fetchone()

        if row:
            # UPDATE
            cursor.execute('''
                UPDATE patients SET
                    apellido_nombre=?, dni=?, fecha_nacimiento=?, domicilio=?, localidad=?,
                    telefono=?, telefono2=?, num_beneficio=?, num_hc=?, anio_vigencia=?, mes_renovacion=?,
                    fecha_inicio=?, fecha_fin=?
                WHERE id=?
            ''', (
                data['apellido_nombre'], data['dni'], data.get('fecha_nacimiento', ''),
                data.get('domicilio', ''), data.get('localidad', ''), data.get('telefono', ''),
                data.get('telefono2', ''), data.get('num_beneficio', ''),
                data['num_hc'], data['anio_vigencia'], data['mes_renovacion'],
                data.get('fecha_inicio'), data.get('fecha_fin'),
                row['id']
            ))
            p_id = row['id']
        else:
            # INSERT
            cursor.execute('''
                INSERT INTO patients (
                    apellido_nombre, dni, fecha_nacimiento, domicilio, localidad,
                    telefono, telefono2, num_beneficio, num_hc, anio_vigencia, mes_renovacion,
                    fecha_inicio, fecha_fin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['apellido_nombre'], data['dni'], data.get('fecha_nacimiento', ''),
                data.get('domicilio', ''), data.get('localidad', ''), data.get('telefono', ''),
                data.get('telefono2', ''), data.get('num_beneficio', ''), data['num_hc'],
                data['anio_vigencia'], data['mes_renovacion'],
                data.get('fecha_inicio'), data.get('fecha_fin')
            ))
            p_id = cursor.lastrowid

        # AUTOMATICALLY record in history (renewals)
        cursor.execute('SELECT id FROM renewals WHERE patient_id = ? AND anio = ? AND mes = ?',
                       (p_id, data['anio_vigencia'], data['mes_renovacion']))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO renewals (patient_id, anio, mes, fecha_inicio, fecha_fin)
                VALUES (?, ?, ?, ?, ?)
            ''', (p_id, data['anio_vigencia'], data['mes_renovacion'], data.get('fecha_inicio'), data.get('fecha_fin')))

        conn.commit()
        sync_patient_master_from_patient_id(p_id)
        return True
    except sqlite3.Error as e:
        print(f"Error DB Insert/Update: {e}")
        return False
    finally:
        conn.close()

def get_patient_by_id(p_id: int) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients WHERE id = ?', (p_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def delete_patient(p_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM renewals WHERE patient_id = ?', (p_id,))
        cursor.execute('DELETE FROM agenda_general WHERE patient_id = ?', (p_id,))
        cursor.execute('DELETE FROM patients WHERE id = ?', (p_id,))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def search_patients(query: str, hc_query: str = "") -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    query = (query or "").strip()
    hc_query = (hc_query or "").strip()
    q = f"%{query}%"
    norm_dig = normalize_digits(query)
    if hc_query:
        where_clause = "CAST(p.num_hc AS INTEGER) = ?"
        params = (int(normalize_digits(hc_query) or "0"),)
    else:
        if norm_dig:
            digits_q = f"%{norm_dig}%"
            where_clause = """
                p.apellido_nombre LIKE ?
                OR p.dni LIKE ?
                OR p.num_beneficio LIKE ?
                OR p.dni LIKE ?
                OR p.num_beneficio LIKE ?
            """
            params = (q, q, q, digits_q, digits_q)
        else:
            where_clause = """
                p.apellido_nombre LIKE ?
                OR p.dni LIKE ?
                OR p.num_beneficio LIKE ?
            """
            params = (q, q, q)
    cursor.execute('''
        SELECT
            p.*,
            (SELECT COUNT(*) FROM renewals r WHERE r.patient_id = p.id) AS renewal_count,
            (SELECT GROUP_CONCAT(item.fecha_ref, '|') FROM (
                SELECT COALESCE(NULLIF(r.fecha_inicio, ''), printf('%04d-%02d-01', r.anio, r.mes)) AS fecha_ref
                FROM renewals r
                WHERE r.patient_id = p.id
                ORDER BY fecha_ref DESC
            ) AS item) AS renewal_dates
        FROM patients p
        WHERE
            ''' + where_clause + '''
        ORDER BY p.apellido_nombre ASC
    ''', params)
    res = cursor.fetchall()
    conn.close()
    return res

def get_patient_by_dni(dni: str) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients WHERE dni = ?', (dni,))
    res = cursor.fetchone()
    conn.close()
    return res

def get_next_hc(year: Optional[int] = None) -> Dict[str, str]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(CAST(num_hc AS INTEGER)) FROM patients")
    row = cursor.fetchone()
    next_hc = 1
    if row and row[0]: next_hc = int(row[0]) + 1
    conn.close()
    return {"num_hc": str(next_hc)}

def update_renovation(patient_id: int, new_year: int, new_month: int, f_ini: str = "", f_fin: str = "") -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE patients SET anio_vigencia=?, mes_renovacion=?, fecha_inicio=?, fecha_fin=? WHERE id=?', (new_year, new_month, f_ini, f_fin, patient_id))
        cursor.execute('INSERT INTO renewals (patient_id, anio, mes, fecha_inicio, fecha_fin) VALUES (?,?,?,?,?)', (patient_id, new_year, new_month, f_ini, f_fin))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def _floor_agenda_time(value: str) -> str:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})", str(value or ""))
    if not match:
        return ""
    hour = int(match.group(1))
    minute = int(match.group(2))
    rounded_minute = 0 if minute < 30 else 30
    return f"{hour:02d}:{rounded_minute:02d}"

def _parse_office_datetime(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""
    parts = text.split()
    if not parts:
        return "", ""
    date_parts = parts[0].split("/")
    if len(date_parts) != 3:
        return "", ""
    day, month, year = date_parts
    iso_date = f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
    raw_time = parts[1] if len(parts) > 1 else ""
    return iso_date, _floor_agenda_time(raw_time)

def _load_office_appointments_by_patient() -> Dict[str, list[tuple[str, str]]]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "scratch", "exp_ter.csv")
    if not os.path.exists(csv_path):
        return {}

    mtime = os.path.getmtime(csv_path)
    if _OFFICE_APPOINTMENTS_CACHE["mtime"] == mtime:
        return _OFFICE_APPOINTMENTS_CACHE["items"]

    items: Dict[str, list[tuple[str, str]]] = {}
    with open(csv_path, "r", encoding="latin1", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_key = str(row.get("Patient_Id") or "").strip().strip('"')
            date_value, time_value = _parse_office_datetime(row.get("Datum_Beginn"))
            if not patient_key or not date_value or not time_value:
                continue
            items.setdefault(patient_key, []).append((date_value, time_value))

    _OFFICE_APPOINTMENTS_CACHE["mtime"] = mtime
    _OFFICE_APPOINTMENTS_CACHE["items"] = items
    return items

def _renewal_date_range(row: sqlite3.Row) -> tuple[str, str]:
    start = str(row["fecha_inicio"] or "").strip()
    end = str(row["fecha_fin"] or "").strip()
    year = int(row["anio"] or datetime.now().year)
    month = int(row["mes"] or 1)
    if not start:
        start = f"{year:04d}-{month:02d}-01"
    if not end:
        last_day = calendar.monthrange(year, month)[1]
        end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return start, end

def _get_renewal_agenda_time(cursor: sqlite3.Cursor, patient_id: int, row: sqlite3.Row) -> str:
    start, end = _renewal_date_range(row)
    cursor.execute('''
        SELECT hora
        FROM agenda_general
        WHERE patient_id = ?
          AND fecha = ?
          AND COALESCE(hora, '') <> ''
        ORDER BY hora ASC
        LIMIT 1
    ''', (patient_id, start))
    start_row = cursor.fetchone()
    if start_row:
        rounded = _floor_agenda_time(start_row["hora"])
        if rounded:
            return rounded

    cursor.execute("SELECT mdb_id, num_hc FROM patients WHERE id = ?", (patient_id,))
    patient = cursor.fetchone()
    patient_keys = []
    if patient:
        patient_keys = [
            str(patient["mdb_id"] or "").strip(),
            str(patient["num_hc"] or "").strip(),
        ]

    office_items = _load_office_appointments_by_patient()
    for patient_key in patient_keys:
        if not patient_key:
            continue
        start_matches = [
            time_value
            for date_value, time_value in office_items.get(patient_key, [])
            if date_value == start and time_value
        ]
        if start_matches:
            return sorted(start_matches)[0]

    cursor.execute('''
        SELECT fecha, hora
        FROM agenda_general
        WHERE patient_id = ?
          AND fecha >= ?
          AND fecha <= ?
          AND COALESCE(hora, '') <> ''
        ORDER BY fecha ASC, hora ASC
    ''', (patient_id, start, end))
    counts = {}
    first_seen = {}
    for agenda_row in cursor.fetchall():
        rounded = _floor_agenda_time(agenda_row["hora"])
        if not rounded:
            continue
        counts[rounded] = counts.get(rounded, 0) + 1
        first_seen.setdefault(rounded, (agenda_row["fecha"], agenda_row["hora"]))
    if not counts:
        for patient_key in patient_keys:
            if not patient_key:
                continue
            for date_value, time_value in office_items.get(patient_key, []):
                if start <= date_value <= end:
                    counts[time_value] = counts.get(time_value, 0) + 1
                    first_seen.setdefault(time_value, (date_value, time_value))

    if not counts:
        return ""
    return sorted(counts, key=lambda hour: (-counts[hour], first_seen[hour]))[0]

def get_renovation_history(patient_id: int) -> List[Dict[str, Any]]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM renewals
        WHERE patient_id = ?
        ORDER BY COALESCE(NULLIF(fecha_inicio, ''), printf('%04d-%02d-01', anio, mes)) DESC
    ''', (patient_id,))
    rows = cursor.fetchall()
    res = []
    for row in rows:
        item = dict(row)
        item["hora"] = _get_renewal_agenda_time(cursor, patient_id, row)
        res.append(item)
    conn.close()
    return res

def delete_renewal_entry(r_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM renewals WHERE id = ?', (r_id,))
    conn.commit()
    conn.close()
    return True

def update_renewal_entry(r_id: int, anio: int, mes: int, f_ini: str = "", f_fin: str = "") -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE renewals SET anio=?, mes=?, fecha_inicio=?, fecha_fin=? WHERE id=?', (anio, mes, f_ini, f_fin, r_id))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def update_patient_fields(patient_id: int, fields: Dict) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        allowed = {'num_beneficio', 'dni', 'apellido_nombre', 'num_hc', 'localidad', 'domicilio', 'telefono', 'telefono2', 'fecha_nacimiento'}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates: return False
        set_clause = ', '.join([f"{k}=?" for k in updates])
        values = list(updates.values()) + [patient_id]
        cursor.execute(f"UPDATE patients SET {set_clause} WHERE id=?", values)
        conn.commit()
        sync_patient_master_from_patient_id(patient_id)
        return True
    except: return False
    finally: conn.close()

def rebuild_patient_master() -> Dict[str, int]:
    """Reconstruye la tabla patient_master consolidando datos de todas las fuentes de forma eficiente."""
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM patient_master")

        # 1. Sincronizar desde Patients (Bulk)
        cursor.execute('SELECT * FROM patients')
        patients = cursor.fetchall()
        for p in patients:
            upsert_patient_master(row_to_dict(p), "patient", conn=conn)

        # 2. Sincronizar desde Neuro
        import datetime
        now = datetime.datetime.now()
        for i in range(3):
            m = now - datetime.timedelta(days=30*i)
            month_str = m.strftime("%Y-%m")
            # Query directly instead of calling get_neuro_patients_by_month
            cursor.execute("SELECT * FROM neuro_patients WHERE fecha LIKE ?", (f"{month_str}%",))
            n_patients = cursor.fetchall()
            for np in n_patients:
                upsert_patient_master(row_to_dict(np), "neuro", conn=conn)

        # 3. Sincronizar desde HD
        cursor.execute('''
            SELECT hd.*, p.apellido_nombre, p.dni, p.num_beneficio, p.num_hc
            FROM hospital_dia hd
            JOIN patients p ON hd.patient_id = p.id
        ''')
        hds = cursor.fetchall()
        for hd in hds:
            upsert_patient_master(dict(hd), "hd", conn=conn)

        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM patient_master")
        total = cursor.fetchone()[0]
        return {"total_master": total}
    except Exception as e:
        conn.rollback()
        print(f"Error rebuilding master: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


def get_patients_all() -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients ORDER BY apellido_nombre ASC')
    res = cursor.fetchall()
    conn.close()
    return res
