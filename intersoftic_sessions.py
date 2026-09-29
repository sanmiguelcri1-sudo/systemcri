# -*- coding: utf-8 -*-
"""
Control de sesiones anuales por paciente de Intersoftic.
"""
import calendar
import datetime
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from intersoftic_stats import (
    BRANCHES,
    TARGET_YEAR,
    connect_intersoftic_sql,
    SQL_OBRA_SOCIAL_ID,
    SQL_TIPO_PRESTACION_ID,
    SQL_OBRA_SOCIAL_DELEGACION_ID,
    STAT_CODES,
    find_tracked_practice_code,
    normalize_practice_code,
)

# MDCS/MDTA (límite anual 50) y Hospital de Día.
MDTA_CODES = set(STAT_CODES["mdta"]) | {"123007", "123008"}
HD_CODES = set(STAT_CODES["hd"])
ANNUAL_LIMIT = 50

def _connect_sql():
    return connect_intersoftic_sql()

def _fetch_detail_rows(conn, sucursal_id: int, date_from: str, date_to: str) -> list:
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
        except Exception as exc:
            last_exc = exc
            if "1205" not in str(exc) or attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last_exc

def _parse_fecha(fecha_raw) -> str:
    if isinstance(fecha_raw, datetime.datetime):
        return fecha_raw.strftime("%Y-%m-%d")
    if isinstance(fecha_raw, datetime.date):
        return fecha_raw.isoformat()
    fecha_str = str(fecha_raw or "").strip()[:10]
    datetime.date.fromisoformat(fecha_str)
    return fecha_str


def build_sessions_for_branch(branch_cfg: dict) -> dict:
    conn = _connect_sql()

    # {(paciente, afiliado): {"regulares_dates": set(), "hd_dates": set()}}
    patients_data = defaultdict(lambda: {"regulares_dates": set(), "hd_dates": set()})
    month_errors = []

    try:
        for month_num in range(1, 13):
            last_day = calendar.monthrange(int(TARGET_YEAR), month_num)[1]
            date_from = f"{TARGET_YEAR}-{month_num:02d}-01"
            date_to = f"{TARGET_YEAR}-{month_num:02d}-{last_day:02d}"

            try:
                rows = _fetch_detail_rows(conn, branch_cfg["sql_sucursal_id"], date_from, date_to)
            except Exception as exc:
                month_errors.append(f"{date_from[:7]}: {exc}")
                continue

            for row in rows:
                try:
                    fecha_raw = row[9] if len(row) > 9 and row[9] else (row[2] if len(row) > 2 else row[0])
                    paciente = str(row[12] or "").strip() if len(row) > 12 else ""
                    afiliado = str(row[3] or "").strip() if len(row) > 3 else ""
                    codigo = find_tracked_practice_code(row, row[8] if len(row) > 8 else "")
                    if codigo not in MDTA_CODES and codigo not in HD_CODES:
                        codigo = normalize_practice_code(row[8] if len(row) > 8 else "")

                    if not paciente or not afiliado or not codigo:
                        continue

                    fecha_str = _parse_fecha(fecha_raw)
                    pac_key = (paciente.upper(), afiliado.upper())

                    if codigo in HD_CODES:
                        patients_data[pac_key]["hd_dates"].add(fecha_str)
                    elif codigo in MDTA_CODES:
                        patients_data[pac_key]["regulares_dates"].add(fecha_str)
                except Exception:
                    continue
    finally:
        conn.close()

    session_rows = []
    
    for (paciente, afiliado), data in patients_data.items():
        sesiones_regulares = len(data["regulares_dates"])
        sesiones_hd = len(data["hd_dates"])
        
        # Mostrar todos los pacientes (aún si tienen < 50) para que la tabla no esté vacía.
        if sesiones_regulares == 0 and sesiones_hd == 0:
            continue
            
        tiene_hd = sesiones_hd > 0
        
        # La vista anual se limita a pacientes que están dentro del rango
        # operativo solicitado: hasta 50 sesiones regulares inclusive.
        if sesiones_regulares > ANNUAL_LIMIT:
            continue

        if tiene_hd:
            estado = "hd_activo"
        elif sesiones_regulares == ANNUAL_LIMIT:
            estado = "limite"
        elif sesiones_regulares >= 40:
            estado = "alerta"
        else:
            estado = "ok"

        session_rows.append({
            "paciente": paciente,
            "afiliado": afiliado,
            "sucursal": branch_cfg["name"],
            "branch_id": branch_cfg["id"],
            "sesiones_regulares": sesiones_regulares,
            "sesiones_hd": sesiones_hd,
            "total_sesiones": sesiones_regulares + sesiones_hd,
            "tiene_hd": tiene_hd,
            "estado": estado
        })

    session_rows.sort(key=lambda x: (-x["sesiones_regulares"], x["paciente"]))
    
    summary = {
        "total_pacientes": len(session_rows),
        "total_alerta": sum(1 for row in session_rows if row["estado"] == "alerta"),
        "total_limite": sum(1 for row in session_rows if row["estado"] == "limite"),
        "total_hd": sum(1 for row in session_rows if row["estado"] == "hd_activo"),
    }

    result = {
        "branch": branch_cfg["name"],
        "branch_id": branch_cfg["id"],
        "rows": session_rows,
        "summary": summary,
    }
    if month_errors:
        result["errors"] = month_errors
    return result

def build_sessions_all_branches() -> dict:
    branches = []
    all_rows = []
    errors = []
    empty_branch = {
        "rows": [],
        "summary": {
            "total_pacientes": 0,
            "total_alerta": 0,
            "total_limite": 0,
            "total_hd": 0,
        },
        "status": "error",
    }

    with ThreadPoolExecutor(max_workers=len(BRANCHES) or 1) as pool:
        futures = {pool.submit(build_sessions_for_branch, cfg): cfg for cfg in BRANCHES}
        for fut in as_completed(futures):
            branch_cfg = futures[fut]
            try:
                result = fut.result()
                branches.append(result)
                all_rows.extend(result["rows"])
                for month_error in result.get("errors") or []:
                    errors.append({
                        "branch": branch_cfg["name"],
                        "branch_id": branch_cfg["id"],
                        "error": month_error,
                    })
            except Exception as exc:
                errors.append({
                    "branch": branch_cfg["name"],
                    "branch_id": branch_cfg["id"],
                    "error": str(exc),
                })
                branches.append({
                    "branch": branch_cfg["name"],
                    "branch_id": branch_cfg["id"],
                    **empty_branch,
                })

    branches.sort(key=lambda item: item.get("branch") or "")

    # Sort all rows
    all_rows.sort(key=lambda x: (-x["sesiones_regulares"], x["paciente"]))
    
    grand_summary = {
        "total_pacientes": len(all_rows),
        "total_alerta": sum(1 for row in all_rows if row["estado"] == "alerta"),
        "total_limite": sum(1 for row in all_rows if row["estado"] == "limite"),
        "total_hd": sum(1 for row in all_rows if row["estado"] == "hd_activo"),
    }

    return {
        "year": int(TARGET_YEAR),
        "branches": branches,
        "all_rows": all_rows,
        "summary": grand_summary,
        "errors": errors
    }
