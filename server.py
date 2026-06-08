# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel
import threading
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from urllib.parse import quote

try:
    from runtime_paths import bundled_path, configure_exe_environment, external_path, is_frozen
    configure_exe_environment()
except Exception:
    def bundled_path(*parts):
        return Path(__file__).resolve().parent.joinpath(*parts)

    def external_path(*parts):
        return Path(__file__).resolve().parent.joinpath(*parts)

    def is_frozen():
        return False

import database
import fetch_evaluations
import top25_stats
import ingreso_egreso
import intersoftic_stats
import intersoftic_audit
from utils.status import set_status, get_status
from utils.text import validate_utf8_text

app = FastAPI(title="HC API", default_response_class=JSONResponse)


def build_whatsapp_message(patient_name: Optional[str] = None) -> str:
    patient_name = validate_utf8_text(patient_name).strip()
    greeting = f"Hola {patient_name}," if patient_name else "Hola,"
    return (
        "📩 "
        f"{greeting} les enviamos el informe de la evaluación neurocognitiva correspondiente. "
        "Quedamos atentos ante cualquier novedad o indicación. Saludos cordiales."
    )

# Inicializar DB
database.init_db()

staff_com_lock = threading.Lock()

# Modelos
class Patient(BaseModel):
    apellido_nombre: str
    dni: str
    fecha_nacimiento: Optional[str] = ""
    domicilio: Optional[str] = ""
    localidad: Optional[str] = ""
    telefono: Optional[str] = ""
    telefono2: Optional[str] = ""
    num_beneficio: Optional[str] = ""
    num_hc: str
    anio_vigencia: Optional[int] = 2026
    mes_renovacion: Optional[int] = 1
    fecha_inicio: Optional[str] = ""
    fecha_fin: Optional[str] = ""

class Renovation(BaseModel):
    patient_id: int
    new_year: int
    new_month: int
    fecha_inicio: Optional[str] = ""
    fecha_fin: Optional[str] = ""

class RenewalUpdate(BaseModel):
    anio: int
    mes: int
    fecha_inicio: str = ""
    fecha_fin: str = ""

class NeuroPatient(BaseModel):
    fecha: str
    hora: str
    paciente: str
    dni: Optional[str] = ""
    fecha_nacimiento: Optional[str] = ""
    domicilio: Optional[str] = ""
    localidad: Optional[str] = ""
    telefono1: Optional[str] = ""
    telefono2: Optional[str] = ""
    beneficio: Optional[str] = ""
    num_op: Optional[str] = ""
    fecha_op: Optional[str] = ""
    capita: Optional[str] = ""
    link_pdf: Optional[str] = ""
    observaciones: Optional[str] = ""
    asistencia: Optional[str] = "pendiente"
    aviso_tipo: Optional[str] = ""
    aviso_estado: Optional[int] = 0

class NeuroReportFile(BaseModel):
    filename: str
    content_base64: str
    neuro_id: Optional[int] = None

class NeuroReportBatch(BaseModel):
    files: List[NeuroReportFile]

class Appointment(BaseModel):
    patient_id: int
    fecha: str
    hora: Optional[str] = ""
    recurso: Optional[str] = "Kine 1"
    tipo_sesion: Optional[str] = "Kinesiología"
    observaciones: Optional[str] = ""
    recurring_days: Optional[List[int]] = None

class HDOp(BaseModel):
    op_number: str
    fecha_val: str
    color_code: Optional[str] = ""

class HDEntry(BaseModel):
    id: Optional[int] = None
    patient_id: int
    localidad: str
    diagnostico: str
    orden_elect: str
    estado: Optional[str] = "Activo"
    fecha_pedido: Optional[str] = ""
    sesiones_check: Optional[int] = 0
    sesiones_max: Optional[int] = 24
    num_beneficio: Optional[str] = None
    dni: Optional[str] = None
    ops: List[HDOp] = []

class StaffPayload(BaseModel):
    staff_key: Optional[str] = None
    nombre: str
    cargo: Optional[str] = ""
    include_in_word: Optional[bool] = True
    fecha_ingreso: Optional[str] = ""
    fecha_egreso: Optional[str] = ""
    default_ingreso: Optional[str] = ""
    default_egreso: Optional[str] = ""

class ProfessionalPayload(BaseModel):
    id: Optional[int] = None
    nombre_completo: str
    documento: Optional[str] = ""
    matricula_1: Optional[str] = ""
    matricula_2: Optional[str] = ""
    telefono: Optional[str] = ""
    movil: Optional[str] = ""
    mail: Optional[str] = ""
    fecha_nacimiento: Optional[str] = ""
    numero_emergencia: Optional[str] = ""
    profesion: Optional[str] = ""
    sucursal: Optional[str] = ""
    sucursal_intersoftic: Optional[str] = ""
    sucursal_detectada_2026: Optional[str] = ""
    efectores_2026: Optional[int] = 0

class StaffMonthPayload(BaseModel):
    staff_id: int
    year: int
    month: int

class AttendancePayload(BaseModel):
    staff_id: int
    fecha: str  # YYYY-MM-DD
    ingreso: str  # HH:MM
    egreso: str  # HH:MM
    observaciones: Optional[str] = ""

class DeleteAttendancePayload(BaseModel):
    staff_id: int
    fecha: str

class ImportExcelPayload(BaseModel):
    excel_path: str
    month: Optional[int] = None
    year: Optional[int] = None

class ExportWordPayload(BaseModel):
    year: int
    month: int
    output_path: Optional[str] = None
    base_folder: Optional[str] = r"D:\HORAS"
    facility: Optional[str] = ingreso_egreso.DEFAULT_FACILITY
    doc_prefix: Optional[str] = ingreso_egreso.DEFAULT_DOC_PREFIX

# Endpoints

@app.get("/api/patients/missing")
def get_patients_missing():
    """
    Return patients that have missing critical data: birthdate, benefit number, phone, address, or incomplete name.
    """
    conn = database.create_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM patients
        WHERE
            fecha_nacimiento IS NULL OR fecha_nacimiento = '' OR
            num_beneficio IS NULL OR num_beneficio = '' OR
            telefono IS NULL OR telefono = '' OR
            domicilio IS NULL OR domicilio = '' OR
            (apellido_nombre NOT LIKE '%, %' AND apellido_nombre NOT LIKE ' % %')
        ORDER BY apellido_nombre
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/pami/refine/{dni}")
def get_pami_refine(dni: str):
    """
    Refine patient details using PAMI web scraper.
    """
    try:
        import pami_refiner
        data = pami_refiner.solve_pami_dni(dni)
        if data:
            return {"success": True, "data": data}
        else:
            raise HTTPException(status_code=404, detail="No se encontraron datos en PAMI para el DNI provisto.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar PAMI: {str(e)}")

@app.get("/api/patients")
def get_patients(query: str = "", hc_query: str = ""):
    results = database.search_patients(query, hc_query)
    return [dict(r) for r in results]

@app.get("/api/patients/{dni}")
def get_patient_by_dni(dni: str):
    patient = database.get_patient_by_dni(dni)
    if patient:
        return dict(patient)
    raise HTTPException(status_code=404, detail="Patient not found")

@app.get("/api/next-hc")
def get_next(year: Optional[int] = None):
    return database.get_next_hc(year)

@app.post("/api/patients")
def create_patient(patient: Patient):
    data = patient.model_dump()
    success = database.insert_patient(data)
    if success:
        # Sincronizar creación con MDB
        try:
            import os, subprocess
            vbs_path = os.path.join(os.path.dirname(__file__), "scratch", "insert_paciente_mdb.vbs")
            # Argumentos: Kennummer (num_hc), Nachname (apellido), Vorname (nombre), DNI
            parts = data['apellido_nombre'].split(' ', 1)
            last = parts[0].replace('"', '')
            first = parts[1].replace('"', '') if len(parts) > 1 else ""
            cmd = f'C:\\Windows\\SysWOW64\\cscript.exe //Nologo "{vbs_path}" "{data["num_hc"]}" "{last}" "{first}" "{data["dni"]}"'
            subprocess.Popen(cmd, shell=True)
        except: pass
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error creating/updating patient. DNI or HC might be duplicate.")

@app.put("/api/patients/{p_id}")
def update_patient(p_id: int, patient: Patient):
    success = database.update_patient(p_id, patient.model_dump())
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error updating patient. HC Number might be duplicate.")

@app.post("/api/patients/{p_id}/delete")
def delete_patient_post(p_id: int):
    success = database.delete_patient(p_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error deleting patient.")

@app.post("/api/renovate")
def renovate(ren: Renovation):
    success = database.update_renovation(ren.patient_id, ren.new_year, ren.new_month, ren.fecha_inicio, ren.fecha_fin)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error updating renovation.")

@app.get("/api/history/{patient_id}")
def get_history(patient_id: int):
    results = database.get_renovation_history(patient_id)
    return [dict(r) for r in results]

@app.put("/api/history/{renewal_id}")
def update_history(renewal_id: int, ren: RenewalUpdate):
    success = database.update_renewal_entry(renewal_id, ren.anio, ren.mes, ren.fecha_inicio, ren.fecha_fin)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error updating renewal entry.")

@app.delete("/api/history/{renewal_id}")
def delete_history(renewal_id: int):
    success = database.delete_renewal_entry(renewal_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error deleting renewal entry.")

# --- Neurocognitivo Endpoints ---
@app.get("/api/neuro")
def get_neuro(fecha: str):
    results = database.get_neuro_patients(fecha)
    return database.enrich_neuro_results([dict(r) for r in results])

@app.get("/api/neuro/month")
def get_neuro_month(month: str):
    results = database.get_neuro_patients_by_month(month)
    return database.enrich_neuro_results([dict(r) for r in results])

@app.get("/api/neuro/search")
def search_neuro(query: str, asistencia: Optional[str] = None, aviso_estado: Optional[int] = None):
    results = database.search_neuro_patients(query, asistencia, aviso_estado)
    return database.enrich_neuro_results([dict(r) for r in results])

@app.get("/api/health")
def get_health():
    return {"status": "ok", "app": "SYSTEMCRI"}


@app.post("/api/neuro")
def create_neuro(p: NeuroPatient):
    success = database.insert_neuro_patient(p.dict())
    if success: return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error creating neuro patient.")

@app.put("/api/neuro/{p_id}")
def update_neuro(p_id: int, p: NeuroPatient):
    success = database.update_neuro_patient(p_id, p.dict())
    if success: return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error updating neuro patient.")

@app.delete("/api/neuro/{p_id}")
def delete_neuro(p_id: int):
    success = database.delete_neuro_patient(p_id)
    if success: return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error deleting neuro patient.")

@app.post("/api/neuro/{p_id}/mark-whatsapp-sent")
def mark_neuro_whatsapp_sent(p_id: int):
    success = database.mark_neuro_whatsapp_sent(p_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="No se pudo marcar el informe como enviado.")

@app.post("/api/neuro/{p_id}/send-report-whatsapp")
def send_neuro_report_whatsapp(p_id: int):
    row = database.get_neuro_patient_by_id(p_id)
    if not row:
        raise HTTPException(status_code=404, detail="Paciente neurocognitivo no encontrado.")

    record = dict(row)
    phone = "".join(ch for ch in (record.get("telefono1") or "") if ch.isdigit())
    if not phone:
        raise HTTPException(status_code=400, detail="Este paciente no tiene telefono cargado.")

    pdf_link = record.get("link_pdf") or ""
    if not pdf_link.startswith("/archivos_neuro/"):
        raise HTTPException(status_code=400, detail="Primero hay que vincular un informe PDF a este paciente.")

    file_name = pdf_link.split("/archivos_neuro/", 1)[1]
    archivos_root = Path(__file__).resolve().parent / "archivos_neuro"
    pdf_path = (archivos_root / file_name).resolve()
    if archivos_root not in pdf_path.parents or not pdf_path.exists():
        raise HTTPException(status_code=400, detail="No se encontro el PDF del informe.")

    full_phone = phone if phone.startswith("54") else f"54{phone}"
    patient_name = record.get("paciente") or record.get("apellido_nombre") or ""
    message = build_whatsapp_message(patient_name)
    whatsapp_uri = f"whatsapp://send?phone={full_phone}&text={quote(message, safe='', encoding='utf-8')}"

    ps_whatsapp_uri = whatsapp_uri.replace("'", "''")
    ps_pdf_path = str(pdf_path).replace("'", "''")
    powershell_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$ErrorActionPreference = 'Stop'
Start-Process '{ps_whatsapp_uri}'
Start-Sleep -Seconds 4
[System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
Start-Sleep -Milliseconds 900
Set-Clipboard -Path '{ps_pdf_path}'
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Seconds 2
[System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
"""

    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script,
            ],
            cwd=os.path.dirname(__file__),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo iniciar WhatsApp Desktop: {exc}")

    if not database.mark_neuro_whatsapp_sent(p_id):
        raise HTTPException(status_code=500, detail="WhatsApp se abrio, pero no pude marcar el informe como enviado.")

    return {"status": "success", "mode": "desktop_automation"}

@app.get("/api/sync/status")
def get_sync_status():
    return get_status()

def run_sync_task():
    script_path = os.path.join(os.path.dirname(__file__), "sync_office_agenda.py")
    subprocess.run(["python", script_path])

@app.post("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    current_status = get_status()
    if current_status.get("status") == "running":
        return {"status": "running"}
    set_status(0, "Iniciando proceso...")
    background_tasks.add_task(run_sync_task)
    return {"status": "started"}

@app.post("/api/fetch-emails")
def trigger_fetch_emails():
    try:
        result = fetch_evaluations.sync_reports()
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/neuro/import-reports")
def import_neuro_reports(payload: NeuroReportBatch):
    result = fetch_evaluations.import_uploaded_reports([item.model_dump() for item in payload.files])
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Error importing reports."))
    return result

@app.post("/api/neuro/process-downloads")
def process_neuro_downloads(force: bool = False):
    try:
        result = fetch_evaluations.process_downloads_folder(force=force)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Error processing reports folder."))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en process_downloads: {str(e)}")

@app.post("/api/neuro/dedupe-pdfs")
def dedupe_neuro_pdfs():
    result = fetch_evaluations.dedupe_archivos_neuro(move_to_subfolder=True)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "Error deduplicating PDFs."))
    return result

@app.post("/api/neuro/{p_id}/report")
def upload_neuro_report(p_id: int, payload: NeuroReportFile):
    try:
        content_bytes = __import__("base64").b64decode(payload.content_base64)
        result = fetch_evaluations.import_uploaded_report(payload.filename, content_bytes, p_id)
        if not result.get("matched"):
            raise HTTPException(status_code=400, detail=result.get("message", "No se pudo vincular el informe."))
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/stats")
def get_stats():
    return database.get_folder_stats()

@app.get("/api/top25")
def get_top25():
    try:
        return top25_stats.build_top25()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/intersoftic-stats")
def get_intersoftic_stats(response: Response):
    try:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return intersoftic_stats.build_intersoftic_all_branches()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/intersoftic-audit")
def get_intersoftic_audit(response: Response):
    try:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return intersoftic_audit.build_audit_all_branches()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/panel")
def get_panel(response: Response):
    try:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return database.get_panel_dashboard()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Holidays Endpoints ---
@app.get("/api/holidays")
def list_holidays():
    return database.get_holidays()

@app.post("/api/holidays")
def add_holiday(fecha: str, descripcion: str = ""):
    if database.add_holiday(fecha, descripcion):
        return {"status": "ok"}
    raise HTTPException(status_code=400, detail="Error adding holiday")

@app.delete("/api/holidays/{fecha}")
def delete_holiday(fecha: str):
    if database.delete_holiday(fecha):
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Holiday not found")

# --- Agenda General Endpoints ---
@app.get("/api/agenda")
def get_agenda(fecha: str):
    results = database.get_agenda(fecha)
    return [dict(r) for r in results]

@app.get("/api/agenda/week")
def get_agenda_week(start: str, end: str):
    results = database.get_agenda_week(start, end)
    return [dict(r) for r in results]

@app.post("/api/agenda")
def create_appointment(appo: Appointment):
    from datetime import datetime, timedelta
    import re
    import os
    import subprocess
    
    # 1. Determinar fechas (una sola o ciclo de 10)
    feriados = database.get_holidays()
    
    dates_to_insert = [appo.fecha]
    if appo.recurring_days and len(appo.recurring_days) > 0:
        base_date = datetime.strptime(appo.fecha, "%Y-%m-%d")
        current_date = base_date
        while len(dates_to_insert) < 10:
            current_date += timedelta(days=1)
            f_str = current_date.strftime("%Y-%m-%d")
            # Skip feriados
            if f_str in feriados: continue
            # weekday() 0=Mon...6=Sun. Nuestra entrada 1=Mon...5=Fri (UI)
            if (current_date.weekday() + 1) in appo.recurring_days:
                dates_to_insert.append(f_str)

    # 2. Obtener datos del paciente para MDB
    patient = database.get_patient_by_id(appo.patient_id)
    mdb_id = patient["num_hc"] if patient and "num_hc" in patient.keys() else "-1"
    
    # Asegurar que el paciente existe en MDB antes de agendar
    if patient:
        try:
            parts = patient['apellido_nombre'].split(' ', 1)
            last = parts[0].replace('"', '')
            first = parts[1].replace('"', '') if len(parts) > 1 else ""
            vbs_p_path = os.path.join(os.path.dirname(__file__), "scratch", "insert_paciente_mdb.vbs")
            cmd_p = f'C:\\Windows\\SysWOW64\\cscript.exe //Nologo "{vbs_p_path}" "{patient["num_hc"]}" "{last}" "{first}" "{patient["dni"]}"'
            subprocess.Popen(cmd_p, shell=True)
        except: pass

    inserted_count = 0
    for f in dates_to_insert:
        # Guardar en DB local
        data = appo.model_dump()
        data['fecha'] = f
        new_id = database.insert_appointment(data)
        
        if new_id:
            inserted_count += 1
            # 3. Sincronizar con Office Agenda (MDB) si tenemos mdb_id
            if mdb_id != "-1":
                try:
                    # MDB format date: DD/MM/YYYY
                    y, m, d = f.split('-')
                    mdb_date = f"{d}/{m}/{y}"
                    hora = appo.hora if appo.hora else "08:00"
                    
                    match = re.search(r'(\d+)', appo.recurso)
                    box_num = match.group(1) if match else "1"
                    
                    vbs_path = os.path.join(os.path.dirname(__file__), "scratch", "insert_turno.vbs")
                    cmd = f'C:\\Windows\\SysWOW64\\cscript.exe //Nologo "{vbs_path}" "{mdb_id}" "{mdb_date}" "{hora}" "{box_num}"'
                    subprocess.Popen(cmd, shell=True)
                except Exception as e:
                    print(f"Error syncing to MDB for date {f}: {e}")
    
    if inserted_count == 0:
        raise HTTPException(status_code=400, detail="Error al crear los turnos.")
    
    return {"status": "success", "inserted": inserted_count}

# --- Hospital de Dia Endpoints ---
@app.get("/api/hd")
def get_hd(query: str = ""):
    return database.get_hospital_dia(query)

@app.post("/api/hd")
def save_hd(entry: HDEntry):
    try:
        res_id = database.save_hd_entry(entry.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if res_id: return {"status": "success", "id": res_id}
    raise HTTPException(status_code=400, detail="Error saving HD record.")

@app.delete("/api/hd/{hd_id}")
def delete_hd(hd_id: int):
    if database.delete_hd_entry(hd_id):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Error al eliminar")

@app.get("/api/hd/validate-op")
def validate_op(op: str, exclude_hd_id: Optional[int] = None):
    return database.check_op_duplicate(op, exclude_hd_id)

@app.patch("/api/patients/{p_id}/fields")
def patch_patient_fields(p_id: int, fields: dict):
    """Actualiza campos de un paciente directamente (beneficio, dni, etc.)"""
    success = database.update_patient_fields(p_id, fields)
    if success: return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error updating patient fields.")

@app.post("/api/master/rebuild")
def rebuild_master():
    return {"status": "success", **database.rebuild_patient_master()}

@app.delete("/api/agenda/{a_id}")
def delete_appointment(a_id: int):
    success = database.delete_appointment(a_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Error al eliminar el turno")

# --- Personal / Ingreso-Egreso ---
@app.get("/api/staff")
def api_list_staff():
    return [dict(r) for r in database.list_staff(include_inactive=True)]

@app.get("/api/staff/intersoftic-professionals")
def api_list_intersoftic_professionals():
    return [dict(r) for r in database.list_intersoftic_professionals()]

@app.post("/api/staff/intersoftic-professionals")
def api_upsert_intersoftic_professional(payload: ProfessionalPayload):
    nombre = (payload.nombre_completo or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta nombre del profesional.")
    professional_id = database.upsert_intersoftic_professional(payload.model_dump())
    return {"status": "success", "id": professional_id}

@app.delete("/api/staff/intersoftic-professionals/{professional_id}")
def api_delete_intersoftic_professional(professional_id: int):
    ok = database.delete_intersoftic_professional(int(professional_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Profesional no encontrado.")
    return {"status": "success"}

@app.post("/api/staff")
def api_upsert_staff(payload: StaffPayload):
    nombre = (payload.nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta nombre.")

    staff_key = (payload.staff_key or "").strip()
    if not staff_key:
        staff_key = ingreso_egreso.normalize_key(nombre)
    if not staff_key:
        raise HTTPException(status_code=400, detail="No pude generar staff_key.")

    def_ing = (payload.default_ingreso or "").strip()
    def_egr = (payload.default_egreso or "").strip()
    if (def_ing and not def_egr) or (def_egr and not def_ing):
        raise HTTPException(status_code=400, detail="Completá default_ingreso y default_egreso.")
    if def_ing and ingreso_egreso.parse_hhmm_to_minutes(def_ing) is None:
        raise HTTPException(status_code=400, detail="default_ingreso inválido (usar HH:MM).")
    if def_egr and ingreso_egreso.parse_hhmm_to_minutes(def_egr) is None:
        raise HTTPException(status_code=400, detail="default_egreso inválido (usar HH:MM).")

    staff_id = database.upsert_staff(
        staff_key=staff_key,
        nombre=nombre,
        cargo=(payload.cargo or "").strip(),
        include_in_word=bool(payload.include_in_word) if payload.include_in_word is not None else True,
        fecha_ingreso=(payload.fecha_ingreso or "").strip(),
        fecha_egreso=(payload.fecha_egreso or "").strip(),
        default_ingreso=def_ing,
        default_egreso=def_egr,
    )
    return {"status": "success", "staff_id": staff_id}

@app.delete("/api/staff/{staff_id}")
def api_delete_staff(staff_id: int):
    ok = database.delete_staff(int(staff_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Personal no encontrado.")
    return {"status": "success"}

@app.get("/api/staff/totals")
def api_staff_month_totals(year: int, month: int, include_in_word_only: bool = False):
    rows = database.get_staff_month_totals(year=int(year), month=int(month), include_in_word_only=bool(include_in_word_only))
    return [dict(r) for r in rows]

@app.get("/api/staff/attendance")
def api_staff_attendance(staff_id: int, year: int, month: int):
    rows = database.list_staff_attendance_for_staff_by_month(staff_id=int(staff_id), year=int(year), month=int(month))
    return [dict(r) for r in rows]

@app.post("/api/staff/attendance")
def api_upsert_attendance(payload: AttendancePayload):
    staff_id = int(payload.staff_id)
    fecha = (payload.fecha or "").strip()
    if not fecha:
        raise HTTPException(status_code=400, detail="Falta fecha.")

    ing_min = ingreso_egreso.parse_hhmm_to_minutes(payload.ingreso)
    egr_min = ingreso_egreso.parse_hhmm_to_minutes(payload.egreso)
    if ing_min is None or egr_min is None:
        raise HTTPException(status_code=400, detail="Ingreso/Egreso inválido (usar HH:MM).")
    horas = ingreso_egreso.compute_hours_from_minutes(ing_min, egr_min)
    if horas <= 0:
        raise HTTPException(status_code=400, detail="Las horas calculadas dan 0. Revisá ingreso/egreso.")

    att_id = database.upsert_staff_attendance(
        staff_id=staff_id,
        fecha=fecha,
        ingreso=ingreso_egreso.minutes_to_hhmm(ing_min),
        egreso=ingreso_egreso.minutes_to_hhmm(egr_min),
        horas=float(horas),
        observaciones=(payload.observaciones or "").strip(),
    )
    return {"status": "success", "id": att_id, "horas": float(horas)}

@app.post("/api/staff/attendance/delete")
def api_delete_attendance(payload: DeleteAttendancePayload):
    ok = database.delete_staff_attendance_for_staff_date(staff_id=int(payload.staff_id), fecha=str(payload.fecha))
    return {"status": "success", "deleted": bool(ok)}

@app.post("/api/staff/attendance/clear-month")
def api_clear_attendance_month(payload: StaffMonthPayload):
    deleted = database.delete_staff_attendance_for_staff_month(staff_id=int(payload.staff_id), year=int(payload.year), month=int(payload.month))
    return {"status": "success", "deleted": int(deleted)}

@app.post("/api/staff/apply-default-weekdays")
def api_apply_default_weekdays(payload: StaffMonthPayload):
    staff_row = database.get_staff_by_id(int(payload.staff_id))
    if staff_row is None:
        raise HTTPException(status_code=404, detail="Personal no encontrado.")
    def_ing = (staff_row["default_ingreso"] or "").strip()
    def_egr = (staff_row["default_egreso"] or "").strip()
    if not def_ing or not def_egr:
        raise HTTPException(status_code=400, detail="Falta horario habitual (default_ingreso/default_egreso).")

    ing_min = ingreso_egreso.parse_hhmm_to_minutes(def_ing)
    egr_min = ingreso_egreso.parse_hhmm_to_minutes(def_egr)
    if ing_min is None or egr_min is None:
        raise HTTPException(status_code=400, detail="Horario habitual inválido.")

    existing = database.list_staff_attendance_for_staff_by_month(staff_id=int(payload.staff_id), year=int(payload.year), month=int(payload.month))
    existing_dates = {str(r["fecha"]) for r in existing}

    inserted = 0
    days_in_month = __import__("calendar").monthrange(int(payload.year), int(payload.month))[1]
    for d in range(1, days_in_month + 1):
        dt = datetime(int(payload.year), int(payload.month), int(d))
        if dt.weekday() > 4:
            continue
        fecha = dt.strftime("%Y-%m-%d")
        if fecha in existing_dates:
            continue
        horas = ingreso_egreso.compute_hours_from_minutes(ing_min, egr_min)
        if horas <= 0:
            continue
        database.upsert_staff_attendance(
            staff_id=int(payload.staff_id),
            fecha=fecha,
            ingreso=ingreso_egreso.minutes_to_hhmm(ing_min),
            egreso=ingreso_egreso.minutes_to_hhmm(egr_min),
            horas=float(horas),
            observaciones="",
        )
        inserted += 1

    return {"status": "success", "inserted": int(inserted)}

@app.post("/api/staff/import-excel")
def api_import_staff_from_excel(payload: ImportExcelPayload):
    excel_path = (payload.excel_path or "").strip()
    if not excel_path:
        raise HTTPException(status_code=400, detail="Falta excel_path.")

    with staff_com_lock:
        month, year, records = ingreso_egreso.parse_excel_timesheet(excel_path, month=payload.month, year=payload.year)

        staff_cache: dict[str, int] = {}
        for rec in records:
            staff_id = staff_cache.get(rec.staff_key)
            if not staff_id:
                staff_row = database.get_staff_by_key(rec.staff_key)
                if staff_row is None:
                    include_default = not ingreso_egreso.should_exclude_in_word(rec.staff_key)
                    staff_id = database.upsert_staff(
                        staff_key=rec.staff_key,
                        nombre=rec.staff_name.title(),
                        cargo="",
                        include_in_word=include_default,
                        fecha_ingreso="",
                        fecha_egreso="",
                        default_ingreso="",
                        default_egreso="",
                    )
                else:
                    staff_id = int(staff_row["id"])
                staff_cache[rec.staff_key] = staff_id

            database.upsert_staff_attendance(
                staff_id=int(staff_id),
                fecha=rec.date,
                ingreso=rec.ingreso,
                egreso=rec.egreso,
                horas=float(rec.hours),
                observaciones="",
            )

    return {"status": "success", "month": month, "year": year, "records": len(records), "staff": len(staff_cache)}

@app.post("/api/staff/export-word")
def api_export_staff_word(payload: ExportWordPayload):
    month = int(payload.month)
    year = int(payload.year)
    month_name = ingreso_egreso.MONTHS_ES.get(month)
    if not month_name:
        raise HTTPException(status_code=400, detail="Mes inválido.")

    rows_db = database.get_staff_month_totals(year=year, month=month, include_in_word_only=True)
    rows: list[ingreso_egreso.WordRow] = []
    for r in rows_db:
        total_h = float(r["total_horas"] or 0)
        if total_h <= 1e-9:
            continue
        rows.append(
            ingreso_egreso.WordRow(
                name=str(r["nombre"]),
                cargo=str(r["cargo"] or ""),
                hours=ingreso_egreso.format_hours(total_h),
            )
        )

    if not rows:
        raise HTTPException(status_code=400, detail="No hay horas para exportar en ese mes.")

    facility = (payload.facility or ingreso_egreso.DEFAULT_FACILITY).strip()
    prefix = (payload.doc_prefix or ingreso_egreso.DEFAULT_DOC_PREFIX).strip()
    default_filename = f"{prefix} {month_name} {year}.docx"

    output_raw = (payload.output_path or "").strip()
    base_folder = (payload.base_folder or r"D:\HORAS").strip()

    def pick_month_folder() -> str:
        if not base_folder:
            raise HTTPException(status_code=400, detail="Falta base_folder.")
        year_dir = __import__("os").path.join(base_folder, str(int(year)))
        __import__("os").makedirs(year_dir, exist_ok=True)
        month_norm = ingreso_egreso._strip_accents(month_name).upper()
        year_txt = str(int(year))
        for name in __import__("os").listdir(year_dir):
            p = __import__("os").path.join(year_dir, name)
            if not __import__("os").path.isdir(p):
                continue
            name_norm = ingreso_egreso._strip_accents(name).upper()
            if month_norm in name_norm and year_txt in name_norm:
                return p
        p = __import__("os").path.join(year_dir, f"{int(month)}-{month_name} {int(year)}")
        __import__("os").makedirs(p, exist_ok=True)
        return p

    if output_raw:
        if output_raw.lower().endswith(".docx"):
            output_path_final = output_raw
        elif __import__("os").path.isdir(output_raw) or output_raw.endswith(("/", "\\")):
            output_path_final = __import__("os").path.join(output_raw, default_filename)
        else:
            output_path_final = __import__("os").path.join(output_raw, default_filename)
    else:
        output_path_final = __import__("os").path.join(pick_month_folder(), default_filename)

    with staff_com_lock:
        backup_path = ingreso_egreso.backup_if_exists(output_path_final)
        ingreso_egreso.write_word_doc(
            output_path=output_path_final,
            facility=facility,
            month_name=month_name,
            year=year,
            rows=rows,
        )

    return {"status": "success", "output_path": output_path_final, "backup_path": backup_path}

# Asegurar la creación de la carpeta de archivos y montarla solo si existe en un FS escribible.
APP_DIR = Path(__file__).resolve().parent
runtime_base_dir = Path(database.DB_NAME).resolve().parent if is_frozen() else APP_DIR
archivos_dir = runtime_base_dir / "archivos_neuro"
try:
    archivos_dir.mkdir(parents=True, exist_ok=True)
    if archivos_dir.is_dir():
        app.mount("/archivos_neuro", StaticFiles(directory=str(archivos_dir)), name="archivos_neuro")
except OSError:
    pass

# Static files
app.mount("/", StaticFiles(directory=str(bundled_path("static")), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8010"))
    uvicorn.run(app, host="127.0.0.1", port=port)
