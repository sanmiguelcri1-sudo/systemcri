"""
Auditoría Intersoftic: detección de errores de carga.
- Sesiones cargadas en feriados argentinos, sábados o domingos.
- Pacientes con más de 10 sesiones mensuales.
Separado por sucursal (San Miguel, Merlo, Ituzaingó).
"""

import calendar
import datetime
import re
import time
from collections import defaultdict
from typing import Optional

import pyodbc

from intersoftic_stats import (
    BRANCHES,
    MONTH_NAMES,
    SQL_DATABASE,
    SQL_OBRA_SOCIAL_DELEGACION_ID,
    SQL_OBRA_SOCIAL_ID,
    SQL_PASSWORD,
    SQL_SERVER,
    SQL_TIPO_PRESTACION_ID,
    SQL_USER,
    TARGET_YEAR,
)

# ──────────────────────────────────────────────────────────────
# Feriados Argentina 2026 (nacionales inamovibles + trasladables)
# ──────────────────────────────────────────────────────────────
FERIADOS_ARGENTINA_2026 = {
    "2026-01-01": "Año Nuevo",
    "2026-02-16": "Carnaval",
    "2026-02-17": "Carnaval",
    "2026-03-24": "Día Nacional de la Memoria por la Verdad y la Justicia",
    "2026-04-02": "Día del Veterano y de los Caídos en la Guerra de Malvinas",
    "2026-04-03": "Viernes Santo",
    "2026-05-01": "Día del Trabajador",
    "2026-05-25": "Día de la Revolución de Mayo",
    "2026-06-15": "Paso a la Inmortalidad del Gral. Güemes (trasladado)",
    "2026-06-20": "Paso a la Inmortalidad del Gral. Manuel Belgrano",
    "2026-07-09": "Día de la Independencia",
    "2026-07-10": "Feriado Puente Turístico",
    "2026-08-17": "Paso a la Inmortalidad del Gral. José de San Martín",
    "2026-09-21": "Día de la Sanidad",
    "2026-10-12": "Día del Respeto a la Diversidad Cultural",
    "2026-11-23": "Día de la Soberanía Nacional",
    "2026-11-27": "Feriado Puente Turístico",
    "2026-12-07": "Feriado Puente Turístico",
    "2026-12-08": "Inmaculada Concepción de María",
    "2026-12-24": "Nochebuena",
    "2026-12-25": "Navidad",
    "2026-12-31": "Fin de Año",
}

# Excepciones aceptadas por auditoria: casos que no se pueden corregir manualmente
# en Intersoftic y no deben aparecer como error operativo.
SESSION_ERROR_EXCLUSIONS = {
    ("150231771501", "2026-02"),
}

EXPECTED_UGL_BY_BRANCH = {
    "san_miguel": {"ids": {2}, "label": "UGL 8"},
    "ituzaingo": {"ids": {1}, "label": "UGL 29"},
    "merlo": {"ids": {1}, "label": "UGL 29"},
}
_UGL_STATUS_CACHE = None


def _connect_sql():
    """Conexión al SQL Server de Intersoftic."""
    if not all([SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD]):
        raise RuntimeError("Falta configurar Intersoftic en .env: servidor, base, usuario y clave.")

    conn_str = (
        "DRIVER={SQL Server};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=8;"
    )
    return pyodbc.connect(conn_str, timeout=8)


def _fetch_detail_rows(conn, sucursal_id: int, date_from: str, date_to: str) -> list:
    """
    Ejecuta el SP de detalle de prestaciones ambulatorias para obtener
    datos a nivel paciente/fecha/prestación.
    Retorna lista de tuplas tal cual el SP.
    """
    cursor = conn.cursor()
    last_exc = None
    for attempt in range(3):
        try:
            rows = cursor.execute(
                "EXEC dbo.spp_Efectores_AMB_Detalle ?, ?, ?, ?, ?, ?",
                date_from,
                date_to,
                sucursal_id,
                SQL_OBRA_SOCIAL_ID,
                SQL_TIPO_PRESTACION_ID,
                SQL_OBRA_SOCIAL_DELEGACION_ID,
            ).fetchall()
            return rows
        except pyodbc.Error as exc:
            last_exc = exc
            # Deadlock retry
            if "1205" not in str(exc) or attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_exc


def _is_weekend(date_str: str) -> Optional[str]:
    """Devuelve 'SÁBADO' o 'DOMINGO' si la fecha cae en fin de semana, else None."""
    try:
        dt = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
    if dt.weekday() == 5:
        return "SÁBADO"
    if dt.weekday() == 6:
        return "DOMINGO"
    return None


def _is_holiday(date_str: str) -> Optional[str]:
    """Devuelve el nombre del feriado si la fecha es un feriado, else None."""
    return FERIADOS_ARGENTINA_2026.get(date_str)


def _clean_digits(value: str) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _fetch_ugl_status_by_affiliate(conn, affiliate_numbers: set[str]) -> dict:
    """Devuelve estado de UGL por numero de afiliado base de PAMI."""
    clean_affiliates = {_clean_digits(value) for value in affiliate_numbers if _clean_digits(value)}
    if not clean_affiliates:
        return {}

    result = {}
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT
            p.PacienteID,
            LTRIM(RTRIM(COALESCE(p.Apellido, '') + ' ' + COALESCE(p.Nombre, ''))) AS paciente,
            p.Documento,
            p.NumeroSocio,
            p.OBRASOCIAL_DELEGACIONID,
            COALESCE(d.descripcion, d.descripcion_delegacion, '') AS ugl
        FROM dbo.Pacientes p
        LEFT JOIN dbo.obrassociales_delegaciones d
            ON d.id = p.OBRASOCIAL_DELEGACIONID
        WHERE p.ObraSocialID = ?
    """, SQL_OBRA_SOCIAL_ID).fetchall()

    for row in rows:
        raw_affiliate = str(row.NumeroSocio or "").strip()
        key = _clean_digits(raw_affiliate.split("/")[0])
        if not key:
            continue
        result[key] = {
            "paciente_id": row.PacienteID,
            "paciente": str(row.paciente or "").strip(),
            "documento": str(row.Documento or "").strip(),
            "afiliado": raw_affiliate,
            "delegacion_id": int(row.OBRASOCIAL_DELEGACIONID or 0),
            "ugl": str(row.ugl or "").strip(),
        }

    return {key: value for key, value in result.items() if key in clean_affiliates}


def _friendly_sql_error(exc: Exception) -> str:
    text = str(exc)
    if "Login failed for user" in text or "Atributo de cadena de conexión no válido" in text:
        return "No se pudo autenticar en Intersoftic. Reemplazá la clave actual en .env por la contraseña real y reiniciá el servidor."
    return text


def build_audit_for_branch(branch_cfg: dict) -> dict:
    """
    Construye el reporte de auditoría para una sucursal.
    Retorna:
    {
        "branch": "SAN MIGUEL",
        "branch_id": "san_miguel",
        "year": 2026,
        "date_errors": [
            {
                "fecha": "2026-01-01",
                "dia_semana": "JUEVES",
                "motivo": "FERIADO: Año Nuevo",
                "paciente": "GOMEZ JUAN",
                "afiliado": "...",
                "prestacion": "123008",
                "cantidad": 1
            }
        ],
        "session_errors": [
            {
                "paciente": "GOMEZ JUAN",
                "afiliado": "...",
                "mes": "ENERO",
                "sesiones": 12,
                "max_permitido": 10
            }
        ],
        "summary": {
            "total_date_errors": X,
            "total_session_errors": X,
            "feriados_count": X,
            "sabados_count": X,
            "domingos_count": X
        }
    }
    """
    date_errors = []
    ugl_errors_by_affiliate = {}
    source_errors = []
    # patient_month_counts: key = (paciente_normalizado, afiliado, mes_num) -> fechas unicas
    patient_month_counts = defaultdict(
        lambda: {"dates": set(), "paciente": "", "afiliado": "", "total_practicas": 0}
    )

    conn = _connect_sql()
    try:
        for month_num in range(1, 13):
            last_day = calendar.monthrange(int(TARGET_YEAR), month_num)[1]
            date_from = f"{TARGET_YEAR}-{month_num:02d}-01"
            date_to = f"{TARGET_YEAR}-{month_num:02d}-{last_day:02d}"

            try:
                rows = _fetch_detail_rows(conn, branch_cfg["sql_sucursal_id"], date_from, date_to)
            except Exception as exc:
                # Si falla el SP de detalle, intentamos con el de resumen
                # pero ese no tiene detalle por paciente, así que lo registramos y lo saltamos.
                source_errors.append(f"{MONTH_NAMES.get(f'{month_num:02d}', month_num)}: {exc}")
                continue

            for row in rows:
                # El SP de detalle retorna:
                # 2: FechaAtencion, 3: Beneficio, 8: Practica, 9: FechaPractica, 10: Cantidad, 12: Paciente
                try:
                    fecha_raw = row[9] if len(row) > 9 and row[9] else (row[2] if len(row) > 2 else row[0])
                    paciente = str(row[12] or "").strip() if len(row) > 12 else ""
                    afiliado = str(row[3] or "").strip() if len(row) > 3 else ""
                    codigo = str(row[8] or "").strip() if len(row) > 8 else ""
                    registro_id = str(row[0] or "").strip() if len(row) > 0 else ""
                    orden_id = str(row[11] or "").strip() if len(row) > 11 else ""
                    cantidad_raw = row[10] if len(row) > 10 else 1
                    try:
                        cantidad = int(float(cantidad_raw or 1))
                    except (TypeError, ValueError):
                        cantidad = 1

                    # Normalizar fecha
                    if isinstance(fecha_raw, datetime.datetime):
                        fecha_str = fecha_raw.strftime("%Y-%m-%d")
                        dia_semana_num = fecha_raw.weekday()
                    elif isinstance(fecha_raw, datetime.date):
                        fecha_str = fecha_raw.isoformat()
                        dia_semana_num = fecha_raw.weekday()
                    else:
                        fecha_str = str(fecha_raw).strip()[:10]
                        try:
                            dt = datetime.date.fromisoformat(fecha_str)
                            dia_semana_num = dt.weekday()
                        except ValueError:
                            continue

                    dias_semana = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
                    dia_semana = dias_semana[dia_semana_num] if 0 <= dia_semana_num <= 6 else ""

                    # Check date errors
                    weekend = _is_weekend(fecha_str)
                    holiday = _is_holiday(fecha_str)

                    if weekend or holiday:
                        motivo = ""
                        if holiday:
                            motivo = f"FERIADO: {holiday}"
                        if weekend:
                            motivo = f"{weekend}" if not motivo else f"{motivo} / {weekend}"

                        date_errors.append({
                            "fecha": fecha_str,
                            "dia_semana": dia_semana,
                            "motivo": motivo,
                            "paciente": paciente,
                            "afiliado": afiliado,
                            "prestacion": codigo,
                            "cantidad": cantidad,
                            "registro_id": registro_id,
                            "orden_id": orden_id,
                        })

                    # Count unique session dates per patient per month.
                    # Intersoftic can return multiple practices for the same patient/day
                    # (for example 250101 + 250102), but audit rule is sessions/month.
                    month_key = fecha_str[:7]  # YYYY-MM
                    pac_key = (paciente.upper(), afiliado.upper(), month_key)
                    patient_month_counts[pac_key]["dates"].add(fecha_str)
                    patient_month_counts[pac_key]["total_practicas"] += cantidad
                    patient_month_counts[pac_key]["paciente"] = paciente
                    patient_month_counts[pac_key]["afiliado"] = afiliado
                    clean_affiliate = _clean_digits(afiliado)
                    if clean_affiliate:
                        ugl_errors_by_affiliate.setdefault(clean_affiliate, {
                            "paciente": paciente,
                            "afiliado": afiliado,
                            "first_fecha": fecha_str,
                            "last_fecha": fecha_str,
                            "prestaciones": set(),
                        })
                        ugl_info = ugl_errors_by_affiliate[clean_affiliate]
                        ugl_info["first_fecha"] = min(ugl_info["first_fecha"], fecha_str)
                        ugl_info["last_fecha"] = max(ugl_info["last_fecha"], fecha_str)
                        ugl_info["prestaciones"].add(codigo)
                except Exception:
                    continue

        ugl_status = _fetch_ugl_status_by_affiliate(conn, set(ugl_errors_by_affiliate.keys()))
    finally:
        conn.close()

    # Build session errors (> 10 per month)
    session_errors = []
    for (pac_upper, afil_upper, month_key), info in sorted(
        patient_month_counts.items(), key=lambda item: (-len(item[1]["dates"]), item[0])
    ):
        if (afil_upper, month_key) in SESSION_ERROR_EXCLUSIONS:
            continue

        session_count = len(info["dates"])
        if session_count > 10:
            # Parse month name
            month_num_str = month_key.split("-")[1]
            mes_name = MONTH_NAMES.get(month_num_str, month_key)
            session_errors.append({
                "paciente": info["paciente"],
                "afiliado": info["afiliado"],
                "mes": mes_name,
                "mes_num": int(month_num_str),
                "sesiones": session_count,
                "max_permitido": 10,
                "fechas": sorted(info["dates"]),
                "total_practicas": info["total_practicas"],
            })

    ugl_errors = []
    expected_ugl = EXPECTED_UGL_BY_BRANCH.get(branch_cfg["id"], {"ids": {1, 2}, "label": "UGL 8 o UGL 29"})
    for affiliate_key, info in ugl_errors_by_affiliate.items():
        status = ugl_status.get(affiliate_key)
        if not status:
            continue
        if int(status.get("delegacion_id") or 0) in expected_ugl["ids"]:
            continue
        current_ugl = status.get("ugl") or "SIN UGL"
        ugl_errors.append({
            "paciente": status.get("paciente") or info["paciente"],
            "documento": status.get("documento") or "",
            "afiliado": status.get("afiliado") or info["afiliado"],
            "ugl_actual": current_ugl,
            "delegacion_id": status.get("delegacion_id") or 0,
            "esperado": expected_ugl["label"],
            "first_fecha": info["first_fecha"],
            "last_fecha": info["last_fecha"],
            "prestaciones": sorted(code for code in info["prestaciones"] if code),
        })

    # Build summary
    feriados_count = sum(1 for e in date_errors if "FERIADO" in e["motivo"])
    sabados_count = sum(1 for e in date_errors if "SÁBADO" in e["motivo"])
    domingos_count = sum(1 for e in date_errors if "DOMINGO" in e["motivo"])

    # Sort newest first so a freshly loaded test error is visible immediately.
    date_errors.sort(key=lambda e: (e["fecha"], e["paciente"], e["prestacion"]), reverse=True)
    session_errors.sort(key=lambda e: (e["mes_num"], e["sesiones"], e["paciente"]), reverse=True)
    ugl_errors.sort(key=lambda e: (e["paciente"], e["afiliado"]))

    return {
        "branch": branch_cfg["name"],
        "branch_id": branch_cfg["id"],
        "year": int(TARGET_YEAR),
        "date_errors": date_errors,
        "session_errors": session_errors,
        "ugl_errors": ugl_errors,
        "summary": {
            "total_date_errors": len(date_errors),
            "total_session_errors": len(session_errors),
            "total_ugl_errors": len(ugl_errors),
            "feriados_count": feriados_count,
            "sabados_count": sabados_count,
            "domingos_count": domingos_count,
        },
        "source_errors": source_errors,
    }


def build_audit_all_branches() -> dict:
    """Ejecuta la auditoría para todas las sucursales."""
    results = []
    errors = []

    for branch_cfg in BRANCHES:
        try:
            result = build_audit_for_branch(branch_cfg)
            results.append(result)
        except Exception as exc:
            friendly = _friendly_sql_error(exc)
            errors.append({
                "branch": branch_cfg["name"],
                "branch_id": branch_cfg["id"],
                "error": friendly,
            })
            # Aún así agregamos un resultado vacío para que el frontend lo muestre
            results.append({
                "branch": branch_cfg["name"],
                "branch_id": branch_cfg["id"],
                "year": int(TARGET_YEAR),
                "date_errors": [],
                "session_errors": [],
                "ugl_errors": [],
                "summary": {
                    "total_date_errors": 0,
                    "total_session_errors": 0,
                    "total_ugl_errors": 0,
                    "feriados_count": 0,
                    "sabados_count": 0,
                    "domingos_count": 0,
                },
                "sql_error": friendly,
                "source_errors": [friendly],
            })

    # Grand summary
    grand_summary = {
        "total_date_errors": sum(r["summary"]["total_date_errors"] for r in results),
        "total_session_errors": sum(r["summary"]["total_session_errors"] for r in results),
        "total_ugl_errors": sum(r["summary"].get("total_ugl_errors", 0) for r in results),
        "feriados_count": sum(r["summary"]["feriados_count"] for r in results),
        "sabados_count": sum(r["summary"]["sabados_count"] for r in results),
        "domingos_count": sum(r["summary"]["domingos_count"] for r in results),
    }

    return {
        "year": int(TARGET_YEAR),
        "feriados": FERIADOS_ARGENTINA_2026,
        "branches": results,
        "errors": errors,
        "summary": grand_summary,
    }
