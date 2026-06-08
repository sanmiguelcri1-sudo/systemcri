import sqlite3
import os
import shutil
from pathlib import Path

from runtime_paths import bundled_path, external_path, is_frozen, load_local_env

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED_DB_NAME = str(bundled_path("hc_archive.db"))

load_local_env()


def _resolve_db_name():
    configured_db = os.environ.get("SQLITE_DB_PATH", "").strip()
    if configured_db:
        return configured_db

    if is_frozen():
        runtime_db = external_path("hc_archive.db")
        if not runtime_db.exists() and Path(BUNDLED_DB_NAME).exists():
            shutil.copy2(BUNDLED_DB_NAME, runtime_db)
        return str(runtime_db)

    return BUNDLED_DB_NAME


DB_NAME = _resolve_db_name()

def create_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = create_connection()
    cursor = conn.cursor()
    
    # 1. TABLAS
    
    # Patients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apellido_nombre TEXT NOT NULL,
            num_beneficio TEXT,
            num_hc TEXT,
            anio_vigencia INTEGER,
            mes_renovacion INTEGER,
            dni TEXT,
            localidad TEXT,
            domicilio TEXT,
            telefono TEXT,
            telefono2 TEXT,
            fecha_nacimiento TEXT,
            mdb_id TEXT,
            fecha_inicio TEXT,
            fecha_fin TEXT
        )
    ''')

    # Renewals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS renewals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            anio INTEGER,
            mes INTEGER,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        )
    ''')

    # Agenda table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agenda_general (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            fecha TEXT,
            hora TEXT,
            recurso TEXT,
            tipo_sesion TEXT,
            observaciones TEXT,
            fecha_carga TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        )
    ''')

    # Hospital de Día table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hospital_dia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            localidad TEXT,
            diagnostico TEXT,
            orden_elect TEXT,
            estado TEXT DEFAULT 'Activo',
            fecha_pedido TEXT,
            sesiones_check INTEGER DEFAULT 0,
            sesiones_max INTEGER DEFAULT 24,
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        )
    ''')

    # Hospital de Día OPs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hd_ops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hd_id INTEGER,
            op_number TEXT,
            fecha_val TEXT,
            color_code TEXT,
            FOREIGN KEY(hd_id) REFERENCES hospital_dia(id)
        )
    ''')

    # Neuro Patients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS neuro_patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            hora TEXT,
            paciente TEXT,
            dni TEXT,
            telefono1 TEXT,
            telefono2 TEXT,
            beneficio TEXT,
            num_op TEXT,
            fecha_op TEXT,
            capita TEXT,
            link_pdf TEXT,
            observaciones TEXT,
            asistencia TEXT DEFAULT 'pendiente',
            aviso_tipo TEXT,
            aviso_estado INTEGER DEFAULT 0,
            fecha_nacimiento TEXT,
            domicilio TEXT,
            localidad TEXT
        )
    ''')

    # Patient Master table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            apellido_nombre TEXT,
            dni TEXT,
            num_beneficio TEXT,
            num_hc TEXT,
            telefono1 TEXT,
            telefono2 TEXT,
            domicilio TEXT,
            localidad TEXT,
            fecha_nacimiento TEXT,
            origen TEXT,
            last_sync TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mdb_id TEXT
        )
    ''')

    # Staff table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_key TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            cargo TEXT DEFAULT '',
            include_in_word INTEGER DEFAULT 1,
            fecha_ingreso TEXT DEFAULT '',
            fecha_egreso TEXT DEFAULT '',
            default_ingreso TEXT NOT NULL DEFAULT '',
            default_egreso TEXT NOT NULL DEFAULT '',
            intersoftic_profesional_id INTEGER,
            intersoftic_activo TEXT DEFAULT '',
            tipo_documento TEXT DEFAULT '',
            documento TEXT DEFAULT '',
            matricula_1 TEXT DEFAULT '',
            matricula_2 TEXT DEFAULT '',
            telefono TEXT DEFAULT '',
            movil TEXT DEFAULT '',
            mail TEXT DEFAULT '',
            sucursal_intersoftic_id INTEGER,
            sucursal_intersoftic TEXT DEFAULT '',
            sucursal_detectada_2026 TEXT DEFAULT '',
            efectores_2026 INTEGER DEFAULT 0,
            especialidades_detectadas TEXT DEFAULT '',
            domicilio_laboral TEXT DEFAULT '',
            color_localizacion TEXT DEFAULT '',
            motivo_baja TEXT DEFAULT '',
            observaciones_intersoftic TEXT DEFAULT '',
            intersoftic_synced_at TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    _ensure_columns(cursor, "staff", {
        "intersoftic_profesional_id": "INTEGER",
        "intersoftic_activo": "TEXT DEFAULT ''",
        "tipo_documento": "TEXT DEFAULT ''",
        "documento": "TEXT DEFAULT ''",
        "matricula_1": "TEXT DEFAULT ''",
        "matricula_2": "TEXT DEFAULT ''",
        "telefono": "TEXT DEFAULT ''",
        "movil": "TEXT DEFAULT ''",
        "mail": "TEXT DEFAULT ''",
        "sucursal_intersoftic_id": "INTEGER",
        "sucursal_intersoftic": "TEXT DEFAULT ''",
        "sucursal_detectada_2026": "TEXT DEFAULT ''",
        "efectores_2026": "INTEGER DEFAULT 0",
        "especialidades_detectadas": "TEXT DEFAULT ''",
        "domicilio_laboral": "TEXT DEFAULT ''",
        "color_localizacion": "TEXT DEFAULT ''",
        "motivo_baja": "TEXT DEFAULT ''",
        "observaciones_intersoftic": "TEXT DEFAULT ''",
        "intersoftic_synced_at": "TEXT DEFAULT ''",
    })

    # Staff Attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            ingreso TEXT DEFAULT '',
            egreso TEXT DEFAULT '',
            horas REAL NOT NULL DEFAULT 0,
            observaciones TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (staff_id, fecha),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intersoftic_professionals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersoftic_profesional_id INTEGER UNIQUE NOT NULL,
            staff_id INTEGER,
            staff_key TEXT DEFAULT '',
            activo TEXT DEFAULT '',
            apellido TEXT DEFAULT '',
            nombre TEXT DEFAULT '',
            nombre_completo TEXT DEFAULT '',
            tipo_documento TEXT DEFAULT '',
            documento TEXT DEFAULT '',
            matricula_1 TEXT DEFAULT '',
            matricula_2 TEXT DEFAULT '',
            telefono TEXT DEFAULT '',
            movil TEXT DEFAULT '',
            mail TEXT DEFAULT '',
            fecha_ingreso TEXT DEFAULT '',
            sucursal_intersoftic_id INTEGER,
            sucursal_intersoftic TEXT DEFAULT '',
            sucursal_detectada_2026 TEXT DEFAULT '',
            efectores_2026 INTEGER DEFAULT 0,
            especialidades_detectadas TEXT DEFAULT '',
            domicilio_laboral TEXT DEFAULT '',
            color_localizacion TEXT DEFAULT '',
            motivo_baja TEXT DEFAULT '',
            observaciones_intersoftic TEXT DEFAULT '',
            profesion TEXT DEFAULT '',
            fecha_nacimiento TEXT DEFAULT '',
            numero_emergencia TEXT DEFAULT '',
            origen TEXT DEFAULT 'INTERSOFTIC',
            raw_json TEXT DEFAULT '',
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    ''')
    _ensure_columns(cursor, "intersoftic_professionals", {
        "profesion": "TEXT DEFAULT ''",
        "fecha_nacimiento": "TEXT DEFAULT ''",
        "numero_emergencia": "TEXT DEFAULT ''",
        "origen": "TEXT DEFAULT 'INTERSOFTIC'",
    })

    # Report Sources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_report_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT UNIQUE NOT NULL,
            source_path TEXT,
            archive_name TEXT,
            inner_name TEXT,
            file_size INTEGER,
            file_mtime REAL,
            neuro_id INTEGER,
            pdf_link TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Holidays table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. ÍNDICES DE PERFORMANCE
    
    # Patients
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_dni ON patients(dni)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_beneficio ON patients(num_beneficio)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_hc ON patients(num_hc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_nombre ON patients(apellido_nombre)")
    
    # Agenda
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agenda_fecha ON agenda_general(fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agenda_patient ON agenda_general(patient_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agenda_dedup ON agenda_general(fecha, hora, patient_id)")
    
    # Neuro
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_neuro_fecha ON neuro_patients(fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_neuro_dni ON neuro_patients(dni)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_neuro_paciente ON neuro_patients(paciente)")
    
    # Hospital de Día
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hd_patient ON hospital_dia(patient_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hd_ops_hd ON hd_ops(hd_id)")
    
    # Patient Master
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_dni ON patient_master(dni)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_beneficio ON patient_master(num_beneficio)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_hc ON patient_master(num_hc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_master_nombre ON patient_master(apellido_nombre)")
    
    # Renewals
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_renewals_patient ON renewals(patient_id)")
    
    # Staff & Attendance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_attendance_fecha ON staff_attendance(fecha)")
    
    # Report Sources
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_neuro_id ON processed_report_sources(neuro_id)")
    
    # Holidays
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_holidays_fecha ON holidays(fecha)")

    conn.commit()
    conn.close()

def _ensure_columns(cursor: sqlite3.Cursor, table_name: str, columns: dict[str, str]) -> None:
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {str(row[1]) for row in cursor.fetchall()}
    for column_name, column_type in columns.items():
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

if __name__ == "__main__":
    init_db()
