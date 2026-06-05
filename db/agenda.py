import sqlite3
from typing import List, Dict, Optional, Any
from datetime import datetime
from db.base import create_connection

def get_agenda(fecha: str) -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, p.apellido_nombre, p.dni, p.telefono, p.mdb_id
        FROM agenda_general a
        LEFT JOIN patients p ON a.patient_id = p.id
        WHERE a.fecha = ?
        ORDER BY a.hora ASC
    ''', (fecha,))
    res = cursor.fetchall()
    conn.close()
    return res

def get_agenda_week(start_date: str, end_date: str) -> List[sqlite3.Row]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, p.apellido_nombre, p.dni, p.telefono, p.mdb_id
        FROM agenda_general a
        LEFT JOIN patients p ON a.patient_id = p.id
        WHERE a.fecha >= ? AND a.fecha <= ?
        ORDER BY a.fecha ASC, a.hora ASC
    ''', (start_date, end_date))
    res = cursor.fetchall()
    conn.close()
    return res

def insert_appointment(data: Dict) -> int:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        fecha_carga = data.get('fecha_carga') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO agenda_general (patient_id, fecha, hora, recurso, tipo_sesion, observaciones, fecha_carga)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['patient_id'], data['fecha'], data.get('hora'), data.get('recurso', 'Kine 1'), data.get('tipo_sesion'), data.get('observaciones'), fecha_carga))
        new_id = cursor.lastrowid
        conn.commit()
        return new_id
    except: return 0
    finally: conn.close()

def delete_appointment(a_id: int) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM agenda_general WHERE id = ?', (a_id,))
        conn.commit()
        return True
    except: return False
    finally: conn.close()
