import sqlite3
from typing import List, Dict, Optional, Any
from db.base import create_connection
from utils.text import normalize_name

# Configuración de slots para neuro
NEURO_DAY_CAPACITY = 13
NEURO_SLOT_MINUTES = 45
NEURO_DEFAULT_SLOTS = ["08:15", "09:00", "09:45", "10:30", "11:15", "12:00", "12:45", "13:30", "14:15", "15:00", "15:45", "16:30", "17:15"]

from db.matching import find_patient_master_data, upsert_patient_master

def enrich_neuro_results(rows: List[Dict]) -> List[Dict]:
    enriched = []
    for row in rows:
        match = find_patient_master_data(row)
        if match:
            row["dni"] = row.get("dni") or match.get("dni", "")
            row["beneficio"] = row.get("beneficio") or match.get("num_beneficio", "")
            row["telefono1"] = row.get("telefono1") or match.get("telefono1", "")
            row["telefono2"] = row.get("telefono2") or match.get("telefono2", "")
            row["num_hc"] = row.get("num_hc") or match.get("num_hc", "")
            row["fecha_nacimiento"] = match.get("fecha_nacimiento", "")
            row["domicilio"] = match.get("domicilio", "")
            row["localidad"] = match.get("localidad", "")
        enriched.append(row)
    return enriched

def sync_patient_master_from_neuro_id(n_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM neuro_patients WHERE id = ?", (n_id,))
        row = cursor.fetchone()
        if not row: return False
        upsert_patient_master(dict(row), "neuro")
        return True
    except: return False
    finally: conn.close()

def get_neuro_patients(fecha: str) -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT n.*, p.num_hc
        FROM neuro_patients n
        LEFT JOIN patients p ON n.dni = p.dni
        WHERE n.fecha = ?
        ORDER BY n.hora ASC
    ''', (fecha,))
    res = cursor.fetchall()
    conn.close()
    return res

def get_neuro_patients_by_month(year_month: str) -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT n.*, p.num_hc
        FROM neuro_patients n
        LEFT JOIN patients p ON n.dni = p.dni
        WHERE n.fecha LIKE ? 
        ORDER BY n.fecha ASC, n.hora ASC
    ''', (f"{year_month}-%",))
    res = cursor.fetchall()
    conn.close()
    return res

def search_neuro_patients(query: str, asistencia: Optional[str] = None, aviso_estado: Optional[int] = None) -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    
    sql = '''
        SELECT n.*, p.num_hc
        FROM neuro_patients n
        LEFT JOIN patients p ON n.dni = p.dni
        WHERE (n.paciente LIKE ? OR n.dni LIKE ?)
    '''
    params = [f"%{query}%", f"%{query}%"]
    
    if asistencia:
        sql += " AND n.asistencia = ?"
        params.append(asistencia)
    
    if aviso_estado is not None:
        sql += " AND n.aviso_estado = ?"
        params.append(aviso_estado)
        
    sql += " ORDER BY n.fecha DESC, n.hora ASC"
    
    cursor.execute(sql, params)
    res = cursor.fetchall()
    conn.close()
    return res

def get_neuro_patient_by_id(p_id: int) -> Optional[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM neuro_patients WHERE id = ?", (p_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def _time_to_minutes(time_str: str) -> Optional[int]:
    try:
        hh, mm = str(time_str or "").split(":")[:2]
        return int(hh) * 60 + int(mm)
    except: return None

def _minutes_to_time(total_minutes: int) -> str:
    hours = max(0, total_minutes) // 60
    minutes = max(0, total_minutes) % 60
    return f"{hours:02d}:{minutes:02d}"

def _normalize_neuro_day(cursor: sqlite3.Cursor, fecha: str, moved_id: Optional[int] = None, moved_after_equal: bool = False) -> None:
    rows = cursor.execute("SELECT id, hora FROM neuro_patients WHERE fecha = ? ORDER BY hora ASC, id ASC", (fecha,)).fetchall()
    items = [{"id": row["id"], "hora": row["hora"]} for row in rows]
    if len(items) <= 1: return

    if moved_id is not None:
        moved_index = next((index for index, item in enumerate(items) if item["id"] == moved_id), None)
        if moved_index is not None:
            moved_item = items.pop(moved_index)
            moved_minutes = _time_to_minutes(moved_item["hora"])
            if moved_minutes is not None:
                insert_at = 0
                while insert_at < len(items):
                    cur_min = _time_to_minutes(items[insert_at]["hora"])
                    if cur_min is None: break
                    if moved_after_equal:
                        if cur_min > moved_minutes: break
                    elif cur_min >= moved_minutes: break
                    insert_at += 1
                items.insert(insert_at, moved_item)
            else:
                items.insert(moved_index, moved_item)

    minute_values = [v for v in [_time_to_minutes(it["hora"]) for it in items] if v is not None]
    if not minute_values: return
    next_minutes = min(minute_values)
    for item in items:
        norm_time = _minutes_to_time(next_minutes)
        if item["hora"] != norm_time:
            cursor.execute("UPDATE neuro_patients SET hora = ? WHERE id = ?", (norm_time, item["id"]))
        next_minutes += NEURO_SLOT_MINUTES

def _rebalance_neuro_schedule_from(cursor: sqlite3.Cursor, start_date: str, original_dates: List[str]) -> None:
    current_rows = cursor.execute("SELECT id, fecha, hora FROM neuro_patients WHERE fecha >= ? ORDER BY fecha ASC, hora ASC, id ASC", (start_date,)).fetchall()
    if not current_rows: return
    current_dates = [r["fecha"] for r in cursor.execute("SELECT DISTINCT fecha FROM neuro_patients WHERE fecha >= ? ORDER BY fecha ASC", (start_date,)).fetchall()]
    dates = sorted({*(original_dates or []), *current_dates})
    if not dates: return
    items = [{"id": r["id"]} for r in current_rows]
    req_cap = len(items)
    if (len(dates) * NEURO_DAY_CAPACITY) < req_cap: return
    slot_plan = []
    for f in dates:
        for h in NEURO_DEFAULT_SLOTS:
            slot_plan.append((f, h))
            if len(slot_plan) >= req_cap: break
        if len(slot_plan) >= req_cap: break
    for item, (f_slot, h_slot) in zip(items, slot_plan):
        row = cursor.execute("SELECT fecha, hora FROM neuro_patients WHERE id = ?", (item["id"],)).fetchone()
        if row and (row["fecha"] != f_slot or row["hora"] != h_slot):
            cursor.execute("UPDATE neuro_patients SET fecha = ?, hora = ? WHERE id = ?", (f_slot, h_slot, item["id"]))

def insert_neuro_patient(data: Dict) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO neuro_patients (fecha, hora, paciente, dni, fecha_nacimiento, domicilio, localidad, telefono1, telefono2, beneficio, num_op, fecha_op, capita, link_pdf, observaciones, asistencia, aviso_tipo, aviso_estado)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (data['fecha'], data['hora'], data['paciente'], data.get('dni'), data.get('fecha_nacimiento'), data.get('domicilio'), data.get('localidad'), data.get('telefono1'), data.get('telefono2'), data.get('beneficio'), data.get('num_op'), data.get('fecha_op'), data.get('capita'), data.get('link_pdf'), data.get('observaciones'), data.get('asistencia', 'pendiente'), data.get('aviso_tipo'), data.get('aviso_estado', 0)))
        n_id = cursor.lastrowid
        conn.commit()
        sync_patient_master_from_neuro_id(n_id)
        return True
    except: return False
    finally: conn.close()

def update_neuro_patient(p_id: int, data: Dict) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        previous = cursor.execute("SELECT fecha, hora FROM neuro_patients WHERE id = ?", (p_id,)).fetchone()
        cursor.execute('''
            UPDATE neuro_patients SET fecha=?, hora=?, paciente=?, dni=?, fecha_nacimiento=?, domicilio=?, localidad=?, telefono1=?, telefono2=?, beneficio=?, num_op=?, fecha_op=?, capita=?, link_pdf=?, observaciones=?, asistencia=?, aviso_tipo=?, aviso_estado=?
            WHERE id=?
        ''', (data['fecha'], data['hora'], data['paciente'], data.get('dni'), data.get('fecha_nacimiento'), data.get('domicilio'), data.get('localidad'), data.get('telefono1'), data.get('telefono2'), data.get('beneficio'), data.get('num_op'), data.get('fecha_op'), data.get('capita'), data.get('link_pdf'), data.get('observaciones'), data.get('asistencia', 'pendiente'), data.get('aviso_tipo'), data.get('aviso_estado'), p_id))
        old_f, old_h = (previous["fecha"], previous["hora"]) if previous else (None, None)
        new_f, new_h = data["fecha"], data["hora"]
        if old_f and (old_f != new_f or old_h != new_h):
            if old_f != new_f:
                _normalize_neuro_day(cursor, old_f)
                _normalize_neuro_day(cursor, new_f, moved_id=p_id)
            else:
                moved_after_eq = old_f == new_f and _time_to_minutes(old_h) is not None and _time_to_minutes(new_h) is not None and _time_to_minutes(new_h) > _time_to_minutes(old_h)
                _normalize_neuro_day(cursor, new_f, moved_id=p_id, moved_after_equal=moved_after_eq)
        conn.commit()
        sync_patient_master_from_neuro_id(p_id)
        return True
    except: return False
    finally: conn.close()

def delete_neuro_patient(p_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM neuro_patients WHERE id = ?', (p_id,))
    conn.commit()
    conn.close()
    return True

def mark_neuro_whatsapp_sent(p_id: int, aviso_tipo: str = "whatsapp") -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE neuro_patients SET aviso_tipo = ?, aviso_estado = 1 WHERE id = ?", (aviso_tipo, p_id))
        conn.commit()
        return cursor.rowcount > 0
    except: return False
    finally: conn.close()
