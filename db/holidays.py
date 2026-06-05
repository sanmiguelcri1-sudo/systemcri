import sqlite3
from typing import List, Dict, Optional
from db.base import create_connection

def get_holidays() -> List[str]:
    """Retorna una lista de strings con las fechas de los feriados (YYYY-MM-DD)."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fecha FROM holidays ORDER BY fecha ASC")
    res = [row["fecha"] for row in cursor.fetchall()]
    conn.close()
    return res

def add_holiday(fecha: str, descripcion: str = "") -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO holidays (fecha, descripcion) VALUES (?, ?)", (fecha, descripcion))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def delete_holiday(fecha: str) -> bool:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM holidays WHERE fecha = ?", (fecha,))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success

def init_default_holidays():
    """Poblar con los feriados de 2026 por defecto si la tabla está vacía."""
    existing = get_holidays()
    if not existing:
        defaults = [
            ("2026-01-01", "Año Nuevo"),
            ("2026-03-24", "Memoria, Verdad y Justicia"),
            ("2026-04-02", "Malvinas"),
            ("2026-04-03", "Viernes Santo"),
            ("2026-05-01", "Día del Trabajador"),
            ("2026-05-25", "Revolución de Mayo"),
            ("2026-06-20", "Paso a la Inmortalidad del Gral. Belgrano"),
            ("2026-07-09", "Día de la Independencia"),
            ("2026-07-10", "Feriado Puente"),
            ("2026-08-17", "Gral. San Martín"),
            ("2026-10-12", "Diversidad Cultural"),
            ("2026-11-23", "Soberanía Nacional"),
            ("2026-12-08", "Inmaculada Concepción"),
            ("2026-12-25", "Navidad")
        ]
        for f, d in defaults:
            add_holiday(f, d)
