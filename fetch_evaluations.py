import os
import re
import datetime
import base64
import uuid
import hashlib
import difflib
import shutil
import tempfile
import zipfile
from typing import Dict, Optional
from dotenv import load_dotenv
from imap_tools import MailBox, AND
from docx2pdf import convert
import database

load_dotenv()

EMAIL = os.getenv("HOTMAIL_EMAIL")
PASS = os.getenv("HOTMAIL_PASS")
SENDER = os.getenv("ALLOWED_SENDER", "rox31080@gmail.com")

ARCHIVOS_DIR = os.path.join(os.path.dirname(__file__), "archivos_neuro")
DOWNLOADS_REPORTS_DIR = os.getenv("NEURO_REPORTS_DIR", r"C:\Users\Usuario\Downloads\inf-neuro")
SUPPORTED_REPORT_EXTENSIONS = {".pdf", ".docx", ".doc"}
_PDF_HASH_INDEX: Optional[Dict[str, str]] = None

def format_imap_error(error: Exception) -> str:
    message = str(error)
    upper_message = message.upper()

    if "BASICAUTHBLOCKED" in upper_message or "AUTHFAILED:LOGONDENIED-BASICAUTHBLOCKED" in upper_message:
        return (
            "Hotmail/Outlook bloqueó el ingreso por IMAP porque esta cuenta usa autenticación básica, "
            "y Microsoft ya no la permite para este acceso. "
            "Para que 'Buscar Correos' funcione hay que cambiar este módulo a autenticación moderna "
            "(OAuth) o usar otra casilla que sí permita IMAP."
        )

    if "AUTHENTICATE FAILED" in upper_message or "INVALIDCREDENTIALS" in upper_message:
        return "No se pudo iniciar sesión en el correo. Revisá usuario, clave y permisos IMAP de la cuenta."

    return f"Error de conexión IMAP: {message}"

def sync_reports() -> dict:
    if not os.path.exists(ARCHIVOS_DIR):
        os.makedirs(ARCHIVOS_DIR)

    if not EMAIL or not PASS:
        return {"status": "error", "message": "Credenciales de correo no encontradas en el archivo .env"}

    processed_count = 0
    matched_count = 0
    messages = []
    
    try:
        # Connecting to Outlook IMAP
        with MailBox('outlook.office365.com').login(EMAIL, PASS) as mailbox:
            # Fetch unread emails from the specific sender
            # Using basic AND criterion
            emails = mailbox.fetch(AND(from_=SENDER, unseen=True))
            
            for msg in emails:
                subject = msg.subject.upper()
                if "INFORME" not in subject:
                    continue # Skip if it doesn't look like a report email
                
                # Try to parse date from subject "INFORME 16/3"
                date_match = re.search(r'INFORME.*?(\d{1,2})\s*[/-]\s*(\d{1,2})', subject)
                target_date = None
                if date_match:
                    day = int(date_match.group(1))
                    month = int(date_match.group(2))
                    year = datetime.datetime.now().year
                    try:
                        target_date = datetime.date(year, month, day)
                    except ValueError:
                        pass

                # Look for DOCX attachments
                for att in msg.attachments:
                    if att.filename.lower().endswith(".docx"):
                        processed_count += 1
                        surname = os.path.splitext(att.filename)[0].strip()
                        
                        # Save docx temporarily
                        docx_path = os.path.join(ARCHIVOS_DIR, att.filename)
                        with open(docx_path, 'wb') as f:
                            f.write(att.payload)
                        
                        pdf_filename = f"{surname}_{msg.uid}.pdf" # Unique
                        pdf_path = os.path.join(ARCHIVOS_DIR, pdf_filename)
                        
                        try:
                            # Convert to PDF
                            convert(docx_path, pdf_path)
                            os.remove(docx_path) # Clean up docx
                        except Exception as e:
                            messages.append(f"Error al convertir {att.filename}: {str(e)}")
                            continue
                            
                        # Try to match in database
                        matched = attempt_match_and_update(surname, target_date, pdf_filename)
                        if matched:
                            matched_count += 1
                            messages.append(f"Asignado ✓ {surname} ({target_date})")
                        else:
                            messages.append(f"⚠️ PDF descargado ({surname}) pero no se encontró un turno coincidente.")
                            
    except Exception as e:
        return {"status": "error", "message": format_imap_error(e)}
        
    return {
        "status": "success", 
        "processed": processed_count, 
        "matched": matched_count,
        "details": messages
    }

def sanitize_stem(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or "informe"))[0].strip()
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", stem).strip().replace(" ", "_")
    return safe or "informe"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def get_pdf_hash_index() -> Dict[str, str]:
    global _PDF_HASH_INDEX
    if _PDF_HASH_INDEX is not None:
        return _PDF_HASH_INDEX

    index: Dict[str, str] = {}
    if os.path.exists(ARCHIVOS_DIR):
        for entry_name in os.listdir(ARCHIVOS_DIR):
            entry_path = os.path.join(ARCHIVOS_DIR, entry_name)
            if not os.path.isfile(entry_path):
                continue
            if not entry_name.lower().endswith(".pdf"):
                continue

            try:
                digest = sha256_file(entry_path)
            except OSError:
                continue

            existing_name = index.get(digest)
            if not existing_name:
                index[digest] = entry_name
                continue

            try:
                existing_path = os.path.join(ARCHIVOS_DIR, existing_name)
                if os.path.getmtime(entry_path) < os.path.getmtime(existing_path):
                    index[digest] = entry_name
            except OSError:
                pass

    _PDF_HASH_INDEX = index
    return index

def extract_report_date(source_name: str) -> Optional[datetime.date]:
    base_name = os.path.splitext(os.path.basename(source_name or ""))[0]
    date_match = re.search(r'(\d{1,2})\s*[_\-/ ]\s*(\d{1,2})(?:\s*[_\-/ ]\s*(\d{2,4}))?', base_name)
    if not date_match:
        return None

    day = int(date_match.group(1))
    month = int(date_match.group(2))
    year_raw = date_match.group(3)
    if year_raw:
        year = int(year_raw)
        if year < 100:
            year += 2000
    else:
        year = datetime.date.today().year

    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None

def convert_with_word_com(source_path: str, target_pdf: str) -> None:
    import pythoncom
    from win32com.client import DispatchEx

    pythoncom.CoInitialize()
    word = DispatchEx("Word.Application")
    word.Visible = False
    document = None
    try:
        document = word.Documents.Open(os.path.abspath(source_path), ReadOnly=True)
        document.SaveAs(os.path.abspath(target_pdf), FileFormat=17)
    finally:
        if document is not None:
            document.Close(False)
        word.Quit()
        pythoncom.CoUninitialize()

def build_file_source_key(file_path: str, file_size: int, file_mtime: float) -> str:
    normalized_path = os.path.abspath(file_path).lower()
    return f"file|{normalized_path}|{file_size}|{int(file_mtime)}"

def build_zip_source_key(zip_path: str, zip_size: int, zip_mtime: float, info: zipfile.ZipInfo) -> str:
    normalized_path = os.path.abspath(zip_path).lower()
    inner_name = info.filename.replace("\\", "/").lower()
    return f"zip|{normalized_path}|{zip_size}|{int(zip_mtime)}|{inner_name}|{info.file_size}|{info.CRC}"

def save_pdf_content(stem: str, pdf_bytes: bytes) -> str:
    if not os.path.exists(ARCHIVOS_DIR):
        os.makedirs(ARCHIVOS_DIR)

    digest = sha256_bytes(pdf_bytes)
    index = get_pdf_hash_index()

    existing_name = index.get(digest)
    if existing_name:
        existing_path = os.path.join(ARCHIVOS_DIR, existing_name)
        if os.path.exists(existing_path):
            return existing_name
        index.pop(digest, None)

    safe_stem = sanitize_stem(stem)
    pdf_filename = f"{safe_stem}_{digest[:10]}.pdf"
    pdf_path = os.path.join(ARCHIVOS_DIR, pdf_filename)

    if os.path.exists(pdf_path):
        try:
            if sha256_file(pdf_path) == digest:
                index[digest] = pdf_filename
                return pdf_filename
        except OSError:
            pass
        pdf_filename = f"{safe_stem}_{digest[:10]}_{uuid.uuid4().hex[:4]}.pdf"
        pdf_path = os.path.join(ARCHIVOS_DIR, pdf_filename)

    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    index[digest] = pdf_filename
    return pdf_filename

def convert_upload_to_pdf(filename: str, content_bytes: bytes) -> str:
    if not os.path.exists(ARCHIVOS_DIR):
        os.makedirs(ARCHIVOS_DIR)

    ext = os.path.splitext(filename or "")[1].lower()
    stem = sanitize_stem(filename)

    if ext == ".pdf":
        return save_pdf_content(stem, content_bytes)

    if ext not in {".docx", ".doc"}:
        raise ValueError("Solo se pueden importar archivos .doc, .docx o .pdf")

    temp_source = os.path.join(ARCHIVOS_DIR, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
    temp_pdf = os.path.splitext(temp_source)[0] + ".pdf"
    with open(temp_source, "wb") as f:
        f.write(content_bytes)

    try:
        convert(temp_source, temp_pdf)
        with open(temp_pdf, "rb") as f:
            pdf_bytes = f.read()
        return save_pdf_content(stem, pdf_bytes)
    except Exception as e:
        try:
            convert_with_word_com(temp_source, temp_pdf)
            with open(temp_pdf, "rb") as f:
                pdf_bytes = f.read()
            return save_pdf_content(stem, pdf_bytes)
        except Exception as com_error:
            detail = str(com_error).strip() or str(e).strip() or "el convertidor no devolvió detalle"
            raise ValueError(f"No se pudo convertir {filename} a PDF. Revisá que Microsoft Word esté instalado. Detalle: {detail}")
    finally:
        if os.path.exists(temp_source):
            os.remove(temp_source)
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

def attach_pdf_to_neuro(neuro_id: int, pdf_filename: str) -> bool:
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE neuro_patients SET link_pdf = ?, aviso_estado = 0 WHERE id = ?", (f"/archivos_neuro/{pdf_filename}", neuro_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def import_uploaded_report(
    filename: str,
    content_bytes: bytes,
    neuro_id: int | None = None,
    target_date: Optional[datetime.date] = None
) -> Dict:
    pdf_filename = convert_upload_to_pdf(filename, content_bytes)

    if neuro_id is not None:
        if not attach_pdf_to_neuro(neuro_id, pdf_filename):
            return {"matched": False, "message": f"No se encontró el turno Neuro #{neuro_id}."}
        return {"matched": True, "message": f"Informe vinculado al turno #{neuro_id}.", "pdf_link": f"/archivos_neuro/{pdf_filename}"}

    surname = sanitize_stem(filename).replace("_", " ")
    matched = attempt_match_and_update(surname, target_date, pdf_filename)
    if matched:
        return {"matched": True, "message": f"Asignado OK: {surname}.", "pdf_link": f"/archivos_neuro/{pdf_filename}"}
    return {"matched": False, "message": f"PDF generado para {surname}, pero no se encontró un turno coincidente.", "pdf_link": f"/archivos_neuro/{pdf_filename}"}

def import_uploaded_reports(files: list[dict]) -> dict:
    processed_count = 0
    matched_count = 0
    messages = []

    for item in files:
        filename = item.get("filename", "")
        content_base64 = item.get("content_base64", "")
        neuro_id = item.get("neuro_id")
        if not filename or not content_base64:
            messages.append("Archivo omitido: faltan datos.")
            continue
        try:
            content_bytes = base64.b64decode(content_base64)
            result = import_uploaded_report(filename, content_bytes, neuro_id)
            processed_count += 1
            if result.get("matched"):
                matched_count += 1
            messages.append(result.get("message", filename))
        except Exception as e:
            messages.append(f"Error al procesar {filename}: {str(e)}")

    return {
        "status": "success",
        "processed": processed_count,
        "matched": matched_count,
        "details": messages,
    }

def import_local_report(
    file_path: str,
    neuro_id: int | None = None,
    target_date: Optional[datetime.date] = None,
    original_filename: Optional[str] = None
) -> Dict:
    with open(file_path, "rb") as f:
        content_bytes = f.read()
    effective_name = original_filename or os.path.basename(file_path)
    effective_date = target_date or extract_report_date(effective_name) or extract_report_date(file_path)
    return import_uploaded_report(effective_name, content_bytes, neuro_id, effective_date)

def process_zip_report(zip_path: str, *, force: bool = False) -> dict:
    processed_count = 0
    matched_count = 0
    skipped_count = 0
    messages = []
    archive_name = os.path.basename(zip_path)
    archive_date = extract_report_date(archive_name)
    zip_stat = os.stat(zip_path)

    if not zipfile.is_zipfile(zip_path):
        return {
            "status": "error",
            "processed": 0,
            "matched": 0,
            "skipped": 0,
            "details": [f"{archive_name}: el archivo no es un ZIP válido."]
        }

    with tempfile.TemporaryDirectory(prefix="neuro_zip_") as temp_dir:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            for info in zip_file.infolist():
                if info.is_dir():
                    continue

                inner_name = os.path.basename(info.filename)
                ext = os.path.splitext(inner_name)[1].lower()
                if ext not in SUPPORTED_REPORT_EXTENSIONS:
                    continue

                source_key = build_zip_source_key(zip_path, zip_stat.st_size, zip_stat.st_mtime, info)
                existing_source = database.get_report_source(source_key)
                if existing_source and not force:
                    skipped_count += 1
                    continue

                if existing_source and force:
                    existing_link = existing_source["pdf_link"] or ""
                    existing_filename = os.path.basename(existing_link) if existing_link else ""
                    existing_path = os.path.join(ARCHIVOS_DIR, existing_filename) if existing_filename else ""
                    if existing_filename and os.path.exists(existing_path):
                        target_date = extract_report_date(inner_name) or archive_date
                        surname = sanitize_stem(inner_name).replace("_", " ")
                        matched = attempt_match_and_update(surname, target_date, existing_filename)
                        processed_count += 1
                        if matched:
                            matched_count += 1
                        messages.append(f"{archive_name} > Reprocesado (sin duplicar) {inner_name}")
                        database.mark_report_source_processed(
                            source_key,
                            source_path=zip_path,
                            archive_name=archive_name,
                            inner_name=inner_name,
                            file_size=info.file_size,
                            file_mtime=zip_stat.st_mtime,
                            pdf_link=existing_link,
                        )
                        continue

                extracted_name = f"{uuid.uuid4().hex[:8]}_{sanitize_stem(inner_name)}{ext}"
                extracted_path = os.path.join(temp_dir, extracted_name)
                with zip_file.open(info, "r") as source, open(extracted_path, "wb") as target:
                    shutil.copyfileobj(source, target)

                try:
                    result = import_local_report(
                        extracted_path,
                        target_date=extract_report_date(inner_name) or archive_date,
                        original_filename=inner_name
                    )
                    processed_count += 1
                    if result.get("matched"):
                        matched_count += 1
                    messages.append(f"{archive_name} > {result.get('message', inner_name)}")
                    database.mark_report_source_processed(
                        source_key,
                        source_path=zip_path,
                        archive_name=archive_name,
                        inner_name=inner_name,
                        file_size=info.file_size,
                        file_mtime=zip_stat.st_mtime,
                        pdf_link=result.get("pdf_link", "")
                    )
                except Exception as e:
                    messages.append(f"{archive_name} > Error con {inner_name}: {str(e)}")
                    database.mark_report_source_processed(
                        source_key,
                        source_path=zip_path,
                        archive_name=archive_name,
                        inner_name=inner_name,
                        file_size=info.file_size,
                        file_mtime=zip_stat.st_mtime
                    )

    return {
        "status": "success",
        "processed": processed_count,
        "matched": matched_count,
        "skipped": skipped_count,
        "details": messages,
    }

def process_downloads_folder(folder_path: Optional[str] = None, *, force: bool = False) -> dict:
    target_folder = folder_path or DOWNLOADS_REPORTS_DIR
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    processed_count = 0
    matched_count = 0
    skipped_count = 0
    messages = []
    found_any = False

    for entry_name in sorted(os.listdir(target_folder)):
        entry_path = os.path.join(target_folder, entry_name)
        if not os.path.isfile(entry_path):
            continue

        ext = os.path.splitext(entry_name)[1].lower()
        if ext == ".zip":
            found_any = True
            result = process_zip_report(entry_path, force=force)
            processed_count += result.get("processed", 0)
            matched_count += result.get("matched", 0)
            skipped_count += result.get("skipped", 0)
            messages.extend(result.get("details", []))
            continue

        if ext not in SUPPORTED_REPORT_EXTENSIONS:
            continue

        found_any = True
        entry_stat = os.stat(entry_path)
        source_key = build_file_source_key(entry_path, entry_stat.st_size, entry_stat.st_mtime)
        existing_source = database.get_report_source(source_key)
        if existing_source and not force:
            skipped_count += 1
            continue

        if existing_source and force:
            existing_link = existing_source["pdf_link"] or ""
            existing_filename = os.path.basename(existing_link) if existing_link else ""
            existing_path = os.path.join(ARCHIVOS_DIR, existing_filename) if existing_filename else ""
            if existing_filename and os.path.exists(existing_path):
                target_date = extract_report_date(entry_name) or extract_report_date(entry_path)
                surname = sanitize_stem(entry_name).replace("_", " ")
                matched = attempt_match_and_update(surname, target_date, existing_filename)
                processed_count += 1
                if matched:
                    matched_count += 1
                messages.append(f"{entry_name} > Reprocesado (sin duplicar)")
                database.mark_report_source_processed(
                    source_key,
                    source_path=entry_path,
                    inner_name=entry_name,
                    file_size=entry_stat.st_size,
                    file_mtime=entry_stat.st_mtime,
                    pdf_link=existing_link,
                )
                continue
        try:
            result = import_local_report(entry_path)
            processed_count += 1
            if result.get("matched"):
                matched_count += 1
            messages.append(f"{entry_name} > {result.get('message', entry_name)}")
            database.mark_report_source_processed(
                source_key,
                source_path=entry_path,
                inner_name=entry_name,
                file_size=entry_stat.st_size,
                file_mtime=entry_stat.st_mtime,
                pdf_link=result.get("pdf_link", "")
            )
        except Exception as e:
            messages.append(f"{entry_name} > Error: {str(e)}")
            database.mark_report_source_processed(
                source_key,
                source_path=entry_path,
                inner_name=entry_name,
                file_size=entry_stat.st_size,
                file_mtime=entry_stat.st_mtime
            )

    if not found_any:
        messages.append(f"No se encontraron archivos .zip, .doc, .docx o .pdf en {target_folder}.")

    return {
        "status": "success",
        "folder": target_folder,
        "processed": processed_count,
        "matched": matched_count,
        "skipped": skipped_count,
        "details": messages,
    }

def is_fuzzy_token_match(target_token: str, patient_tokens: list[str]) -> bool:
    if len(target_token) < 5:
        return False
    for patient_token in patient_tokens:
        if len(patient_token) < 5:
            continue
        similarity = difflib.SequenceMatcher(None, target_token, patient_token).ratio()
        if similarity >= 0.88:
            return True
    return False

def attempt_match_and_update(surname: str, target_date: Optional[datetime.date], pdf_filename: str) -> bool:
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, fecha, paciente FROM neuro_patients')
    candidates = cursor.fetchall()

    normalized_target = database.normalize_name(surname or "")
    tokens = [token for token in normalized_target.split() if len(token) >= 3]
    best_match_id = None

    best_score = -1
    tied_best = False

    for cand in candidates:
        normalized_patient = database.normalize_name(cand['paciente'] or "")
        patient_tokens = [token for token in normalized_patient.split() if len(token) >= 3]
        base_score = -1

        if normalized_target and normalized_target in normalized_patient:
            base_score = 100
        elif tokens and all(token in normalized_patient for token in tokens):
            base_score = 80 + len(tokens)
        elif tokens and all(token in normalized_patient or is_fuzzy_token_match(token, patient_tokens) for token in tokens):
            base_score = 62 + len(tokens)
        elif normalized_target and normalized_patient.startswith(normalized_target):
            base_score = 70
        elif tokens and tokens[0] in normalized_patient:
            base_score = 45
        elif tokens and is_fuzzy_token_match(tokens[0], patient_tokens):
            base_score = 48

        if base_score < 0:
            continue

        score = base_score
        if target_date:
            try:
                c_date = datetime.datetime.strptime(cand['fecha'], "%Y-%m-%d").date()
                diff = abs((c_date - target_date).days)
                if diff <= 1:
                    score += 30
                elif diff <= 3:
                    score += 20
                elif diff <= 7:
                    score += 10
                else:
                    score -= min(diff, 15)
            except ValueError:
                pass

        if score > best_score:
            best_score = score
            best_match_id = cand['id']
            tied_best = False
        elif score == best_score:
            tied_best = True

    if best_match_id and best_score >= 45 and not tied_best:
        # Ensure we construct a relative link for the web
        link = f"/archivos_neuro/{pdf_filename}"
        cursor.execute("UPDATE neuro_patients SET link_pdf = ?, aviso_estado = 0 WHERE id = ?", (link, best_match_id))
        conn.commit()
        conn.close()
        return True
        
    conn.close()
    return False

def report_group_key(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or ""))[0].strip()
    if not stem:
        return ""

    match = re.match(r"^(.*)_([A-Fa-f0-9]{8}|[A-Fa-f0-9]{10})(?:_[A-Fa-f0-9]{4})?$", stem)
    if match:
        return match.group(1).strip()
    return stem

def dedupe_archivos_neuro(*, move_to_subfolder: bool = True) -> dict:
    if not os.path.exists(ARCHIVOS_DIR):
        return {"status": "success", "duplicates_found": 0, "moved": 0, "updated_neuro": 0, "updated_sources": 0}

    pdf_files: list[str] = []
    for entry_name in os.listdir(ARCHIVOS_DIR):
        entry_path = os.path.join(ARCHIVOS_DIR, entry_name)
        if not os.path.isfile(entry_path):
            continue
        if entry_name.lower().endswith(".pdf"):
            pdf_files.append(entry_name)

    grouped: Dict[str, list[str]] = {}
    for name in pdf_files:
        key = report_group_key(name)
        if not key:
            continue
        grouped.setdefault(key.lower(), []).append(name)

    duplicates = {key: names for key, names in grouped.items() if len(names) > 1}
    if not duplicates:
        return {"status": "success", "duplicates_found": 0, "moved": 0, "updated_neuro": 0, "updated_sources": 0}

    backup_dir = ""
    if move_to_subfolder:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(ARCHIVOS_DIR, "_duplicados", ts)
        os.makedirs(backup_dir, exist_ok=True)

    rewrites: Dict[str, str] = {}
    moved = 0

    for key, names in duplicates.items():
        def sort_key(filename: str):
            path = os.path.join(ARCHIVOS_DIR, filename)
            try:
                # Keep the newest as canonical.
                return (-os.path.getmtime(path), filename.lower())
            except OSError:
                return (float("inf"), filename.lower())

        ordered = sorted(names, key=sort_key)
        keep_name = ordered[0]
        for dup_name in ordered[1:]:
            rewrites[dup_name] = keep_name
            src = os.path.join(ARCHIVOS_DIR, dup_name)
            try:
                if move_to_subfolder:
                    shutil.move(src, os.path.join(backup_dir, dup_name))
                else:
                    os.remove(src)
                moved += 1
            except OSError:
                continue

    updated_neuro = 0
    updated_sources = 0
    conn = database.create_connection()
    cursor = conn.cursor()
    for old_name, new_name in rewrites.items():
        old_link = f"/archivos_neuro/{old_name}"
        new_link = f"/archivos_neuro/{new_name}"
        cursor.execute("UPDATE neuro_patients SET link_pdf = ? WHERE link_pdf = ?", (new_link, old_link))
        updated_neuro += cursor.rowcount
        cursor.execute("UPDATE processed_report_sources SET pdf_link = ? WHERE pdf_link = ?", (new_link, old_link))
        updated_sources += cursor.rowcount
    conn.commit()
    conn.close()

    global _PDF_HASH_INDEX
    _PDF_HASH_INDEX = None

    return {
        "status": "success",
        "duplicates_found": sum(len(v) - 1 for v in duplicates.values()),
        "moved": moved,
        "backup_dir": backup_dir,
        "updated_neuro": updated_neuro,
        "updated_sources": updated_sources,
    }

if __name__ == "__main__":
    result = sync_reports()
    print(result)
