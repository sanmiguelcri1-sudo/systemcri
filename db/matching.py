import sqlite3
from typing import List, Dict, Optional, Any
from utils.text import normalize_text, normalize_name, normalize_digits
from db.base import create_connection

def choose_value(current: Optional[str], incoming: Optional[str], *, prefer_incoming: bool = False, prefer_longer: bool = False) -> str:
    c = normalize_text(current)
    i = normalize_text(incoming)
    if not i: return c
    if not c: return i
    if prefer_incoming: return i
    if prefer_longer: return i if len(i) >= len(c) else c
    return c

def merge_phones(current1: Optional[str], current2: Optional[str], incoming1: Optional[str], incoming2: Optional[str]) -> tuple[str, str]:
    phones = {normalize_digits(p) for p in [current1, current2, incoming1, incoming2]}
    phones.discard("")
    sorted_phones = sorted(list(phones))
    p1 = sorted_phones[0] if len(sorted_phones) > 0 else ""
    p2 = sorted_phones[1] if len(sorted_phones) > 1 else ""
    return p1, p2

def row_to_dict(row: Optional[sqlite3.Row]) -> Dict:
    return dict(row) if row else {}

def build_master_payload(source_data: Dict, patient_row: Optional[sqlite3.Row] = None) -> Dict:
    patient = row_to_dict(patient_row)
    return {
        "patient_id": patient.get("id") or source_data.get("patient_id"),
        "apellido_nombre": source_data.get("apellido_nombre") or source_data.get("paciente") or patient.get("apellido_nombre"),
        "fecha_nacimiento": source_data.get("fecha_nacimiento") or patient.get("fecha_nacimiento"),
        "dni": source_data.get("dni") or patient.get("dni"),
        "num_beneficio": source_data.get("num_beneficio") or source_data.get("beneficio") or patient.get("num_beneficio"),
        "domicilio": source_data.get("domicilio") or patient.get("domicilio"),
        "localidad": source_data.get("localidad") or patient.get("localidad"),
        "telefono1": source_data.get("telefono1") or source_data.get("telefono") or patient.get("telefono"),
        "telefono2": source_data.get("telefono2") or patient.get("telefono2"),
        "num_hc": source_data.get("num_hc") or patient.get("num_hc"),
    }

def find_patient_match(cursor: sqlite3.Cursor, source_data: Dict) -> Optional[sqlite3.Row]:
    """Busca un paciente en la tabla 'patients' usando una jerarquía de criterios optimizada."""
    p_id = source_data.get("patient_id")
    if p_id:
        cursor.execute("SELECT * FROM patients WHERE id = ?", (p_id,))
        row = cursor.fetchone()
        if row: return row

    dni = normalize_digits(source_data.get("dni"))
    num_hc = normalize_text(source_data.get("num_hc"))
    beneficio = normalize_text(source_data.get("num_beneficio") or source_data.get("beneficio"))

    # Intento 1: DNI, HC o Beneficio (Campos únicos/indexados)
    # UNION ALL permite que SQLite use los índices de cada tabla de forma independiente
    queries = []
    params = []
    if dni:
        queries.append("SELECT * FROM patients WHERE dni = ?")
        params.append(dni)
    if num_hc:
        queries.append("SELECT * FROM patients WHERE num_hc = ?")
        params.append(num_hc)
    if beneficio:
        queries.append("SELECT * FROM patients WHERE num_beneficio = ?")
        params.append(beneficio)

    if queries:
        cursor.execute(" UNION ALL ".join(queries) + " LIMIT 1", params)
        row = cursor.fetchone()
        if row: return row

    # Intento 2: Nombre + Teléfono
    target_name = normalize_name(source_data.get("apellido_nombre") or source_data.get("paciente"))
    if target_name:
        cursor.execute("SELECT * FROM patients WHERE UPPER(TRIM(apellido_nombre)) = ?", (target_name,))
        candidates = cursor.fetchall()
        if candidates:
            if len(candidates) == 1: return candidates[0]

            # Si hay varios con el mismo nombre, desempatar por teléfono
            in_phones = {normalize_digits(source_data.get(k)) for k in ["telefono1", "telefono2", "telefono"]}
            in_phones.discard("")
            if not in_phones: return candidates[0] # Tomar el primero si no hay con qué comparar

            for cand in candidates:
                c_phones = {normalize_digits(cand["telefono"]), normalize_digits(cand["telefono2"])}
                if in_phones.intersection(c_phones): return cand

            return candidates[0]

    return None

def find_master_match(cursor: sqlite3.Cursor, source_data: Dict) -> Optional[sqlite3.Row]:
    """Busca un paciente en 'patient_master' de forma eficiente."""
    p_id = source_data.get("patient_id")
    if p_id:
        cursor.execute("SELECT * FROM patient_master WHERE patient_id = ?", (p_id,))
        row = cursor.fetchone()
        if row: return row

    dni = normalize_digits(source_data.get("dni"))
    beneficio = normalize_text(source_data.get("num_beneficio") or source_data.get("beneficio"))
    num_hc = normalize_text(source_data.get("num_hc"))

    queries = []
    params = []
    if dni:
        queries.append("SELECT * FROM patient_master WHERE dni = ?")
        params.append(dni)
    if beneficio:
        queries.append("SELECT * FROM patient_master WHERE num_beneficio = ?")
        params.append(beneficio)
    if num_hc:
        queries.append("SELECT * FROM patient_master WHERE num_hc = ?")
        params.append(num_hc)

    if queries:
        cursor.execute(" UNION ALL ".join(queries) + " LIMIT 1", params)
        row = cursor.fetchone()
        if row: return row

    # Fallback por nombre
    target_name = normalize_name(source_data.get("apellido_nombre") or source_data.get("paciente"))
    if target_name:
        cursor.execute("SELECT * FROM patient_master WHERE UPPER(TRIM(apellido_nombre)) = ? LIMIT 1", (target_name,))
        return cursor.fetchone()

    return None

def upsert_patient_master(source_data: Dict, source: str = "", conn: Optional[sqlite3.Connection] = None) -> int:
    _conn = conn or create_connection()
    cursor = _conn.cursor()
    try:
        patient_row = find_patient_match(cursor, source_data)
        payload = build_master_payload(source_data, patient_row)
        existing = find_master_match(cursor, payload)
        existing_data = row_to_dict(existing)
        authoritative = (source == "patient")

        payload["apellido_nombre"] = choose_value(existing_data.get("apellido_nombre"), payload.get("apellido_nombre"), prefer_incoming=authoritative, prefer_longer=True)
        payload["fecha_nacimiento"] = choose_value(existing_data.get("fecha_nacimiento"), payload.get("fecha_nacimiento"), prefer_incoming=authoritative)
        payload["dni"] = choose_value(existing_data.get("dni"), payload.get("dni"), prefer_incoming=authoritative)
        payload["num_beneficio"] = choose_value(existing_data.get("num_beneficio"), payload.get("num_beneficio"), prefer_incoming=authoritative)
        payload["domicilio"] = choose_value(existing_data.get("domicilio"), payload.get("domicilio"), prefer_incoming=authoritative)
        payload["localidad"] = choose_value(existing_data.get("localidad"), payload.get("localidad"), prefer_incoming=authoritative)
        payload["num_hc"] = choose_value(existing_data.get("num_hc"), payload.get("num_hc"), prefer_incoming=authoritative)
        payload["telefono1"], payload["telefono2"] = merge_phones(existing_data.get("telefono1"), existing_data.get("telefono2"), payload.get("telefono1"), payload.get("telefono2"))
        payload["patient_id"] = payload.get("patient_id") or existing_data.get("patient_id")

        if existing:
            cursor.execute('''
                UPDATE patient_master SET
                    patient_id=?, apellido_nombre=?, dni=?, num_beneficio=?, num_hc=?,
                    telefono1=?, telefono2=?, domicilio=?, localidad=?, fecha_nacimiento=?,
                    origen=?, updated_at=CURRENT_TIMESTAMP, mdb_id=?
                WHERE id=?
            ''', (
                payload["patient_id"], payload["apellido_nombre"], payload["dni"], payload["num_beneficio"],
                payload["num_hc"], payload["telefono1"], payload["telefono2"],
                payload["domicilio"], payload["localidad"], payload["fecha_nacimiento"],
                source or existing_data.get("origen"),
                patient_row["mdb_id"] if patient_row and "mdb_id" in patient_row.keys() else existing_data.get("mdb_id"),
                existing["id"]
            ))
            res_id = existing["id"]
        else:
            cursor.execute('''
                INSERT INTO patient_master (
                    patient_id, apellido_nombre, dni, num_beneficio, num_hc,
                    telefono1, telefono2, domicilio, localidad, fecha_nacimiento, origen, mdb_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payload["patient_id"], payload["apellido_nombre"], payload["dni"], payload["num_beneficio"],
                payload["num_hc"], payload["telefono1"], payload["telefono2"],
                payload["domicilio"], payload["localidad"], payload["fecha_nacimiento"], source,
                patient_row["mdb_id"] if patient_row and "mdb_id" in patient_row.keys() else None
            ))
            res_id = cursor.lastrowid

        if not conn:
            _conn.commit()
        return res_id
    except Exception as e:
        if not conn:
            _conn.rollback()
        raise e
    finally:
        if not conn:
            _conn.close()

def find_patient_master_data(source_data: Dict) -> Dict:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        patient_row = find_patient_match(cursor, source_data)
        if patient_row: return build_master_payload(dict(patient_row), patient_row)
        master_row = find_master_match(cursor, source_data)
        return row_to_dict(master_row)
    finally: conn.close()
