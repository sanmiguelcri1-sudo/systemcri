import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Set, Any
from db.base import create_connection
from utils.text import normalize_text
import intersoftic_stats


def get_folder_stats() -> List[Dict]:
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT anio_vigencia, COUNT(id) AS count
        FROM patients
        WHERE anio_vigencia IS NOT NULL
        GROUP BY anio_vigencia
        ORDER BY anio_vigencia DESC
    """)
    res = cursor.fetchall()
    conn.close()
    return [{"year": r["anio_vigencia"], "count": r["count"]} for r in res]


def get_panel_dashboard() -> Dict:
    conn = create_connection()
    cursor = conn.cursor()

    now = datetime.now()
    today = now.date()
    year_start_iso = today.replace(month=1, day=1).isoformat()
    year_end_iso = today.replace(month=12, day=31).isoformat()
    generated_at = now.isoformat(timespec="seconds")
    current_month_key = today.strftime("%Y-%m")
    current_week_monday = today - timedelta(days=today.weekday())
    previous_week_monday = current_week_monday - timedelta(days=7)

    _f_obs = "COALESCE(a.observaciones, '') LIKE 'Importado de Office Agenda%'"
    _f_real = (
        "COALESCE(p.mdb_id, '') <> '' "
        "AND COALESCE(TRIM(p.apellido_nombre), '') <> '' "
        "AND UPPER(TRIM(p.apellido_nombre)) <> 'OCUPADO'"
    )
    imported_scope = f"{_f_obs} AND {_f_real} AND a.fecha >= ? AND a.fecha <= ?"
    imported_params = (year_start_iso, year_end_iso)

    # Q1: Todos los COUNT(*) estructurales en una sola query (Optimización Agresiva)
    base = cursor.execute("""
        SELECT
            (SELECT COUNT(*) FROM patient_master) AS master_total,
            (SELECT SUM(CASE WHEN COALESCE(TRIM(dni),'') <> '' THEN 1 ELSE 0 END) FROM patient_master) AS master_with_dni,
            (SELECT SUM(CASE WHEN COALESCE(TRIM(telefono1),'') <> '' OR COALESCE(TRIM(telefono2),'') <> '' THEN 1 ELSE 0 END) FROM patient_master) AS master_with_phone,
            (SELECT SUM(CASE WHEN COALESCE(TRIM(domicilio),'') <> '' AND COALESCE(TRIM(localidad),'') <> '' THEN 1 ELSE 0 END) FROM patient_master) AS master_with_address,
            (SELECT SUM(CASE WHEN COALESCE(TRIM(num_hc),'') <> '' THEN 1 ELSE 0 END) FROM patient_master) AS master_with_hc,
            (SELECT COUNT(*) FROM patients) AS registro_total,
            (SELECT COUNT(*) FROM neuro_patients) AS neuro_total,
            (SELECT COUNT(*) FROM hospital_dia) AS hd_total,
            (SELECT COUNT(*) FROM hospital_dia WHERE COALESCE(estado,'Activo') = 'Activo') AS hd_activos,
            (SELECT COUNT(DISTINCT patient_id) FROM hospital_dia WHERE COALESCE(estado,'Activo') = 'Activo') AS hd_people
    """).fetchone()

    hd_people = base["hd_people"] or 0
    summary: Dict = {
        "master_total":        base["master_total"]        or 0,
        "master_with_dni":     base["master_with_dni"]     or 0,
        "master_with_phone":   base["master_with_phone"]   or 0,
        "master_with_address": base["master_with_address"] or 0,
        "master_with_hc":      base["master_with_hc"]      or 0,
        "registro_total":      base["registro_total"]      or 0,
        "neuro_total":         base["neuro_total"]         or 0,
        "hd_total":            base["hd_total"]            or 0,
        "hd_activos":          base["hd_activos"]          or 0,
    }

    # Q2: Una sola lectura de agenda_general para todas las series temporales
    agenda_rows = cursor.execute(f"""
        SELECT a.fecha, a.patient_id
        FROM agenda_general a
        JOIN patients p ON p.id = a.patient_id
        WHERE {imported_scope}
        ORDER BY a.fecha ASC
    """, imported_params).fetchall()

    pami_pids:   Set[int] = set()
    monthly_map: Dict[str, Dict] = {}
    weekly_map:  Dict[str, Dict] = {}

    for row in agenda_rows:
        pid   = row["patient_id"]
        fecha = row["fecha"] or ""
        if not fecha:
            continue
        if pid:
            pami_pids.add(pid)
        # Mensual
        mk = fecha[:7]
        mb = monthly_map.setdefault(mk, {"turnos": 0, "patient_ids": set()})
        mb["turnos"] += 1
        if pid:
            mb["patient_ids"].add(pid)
        # Semanal
        try:
            d_obj  = datetime.strptime(fecha, "%Y-%m-%d").date()
            monday = d_obj - timedelta(days=d_obj.weekday())
            wk     = monday.isoformat()
            wb = weekly_map.setdefault(wk, {
                "monday":      monday,
                "week_label":  f"{monday.strftime('%d/%m')} al {(monday + timedelta(days=6)).strftime('%d/%m')}",
                "turnos":      0,
                "patient_ids": set(),
            })
            wb["turnos"] += 1
            if pid:
                wb["patient_ids"].add(pid)
        except Exception:
            pass

    summary.update({
        "pami_patients_total": len(pami_pids),
        "pami_turns_total":    len(agenda_rows),
    })

    # Intersoftic (Estadísticas externas)
    try:
        idata = intersoftic_stats.build_intersoftic_table_rows()
        irows = idata.get("rows", [])
        if idata.get("year") == today.year and len(irows) >= today.month:
            ci  = irows[today.month - 1]
            pi  = irows[today.month - 2] if today.month > 1 else None
            ytd = sum(int((r or {}).get("total") or 0) for r in irows[:today.month])
            summary.update({
                "intersoftic_ytd_total":            ytd,
                "intersoftic_current_month_label":  ci.get("mes", ""),
                "intersoftic_previous_month_label": (pi or {}).get("mes", ""),
                "current_month_turns":  int(ci.get("total") or 0),
                "previous_month_turns": int((pi or {}).get("total") or 0),
                "month_delta":          int(ci.get("total") or 0) - int((pi or {}).get("total") or 0),
            })
    except Exception:
        pass

    # Generar series mensuales sin queries adicionales
    monthly_patients: List[Dict] = []
    prev_mt = None
    for m_num in range(1, today.month + 1):
        mk  = f"{today.year}-{m_num:02d}"
        bkt = monthly_map.get(mk, {"turnos": 0, "patient_ids": set()})
        monthly_patients.append({
            "month_key":    mk,
            "pacientes":    len(bkt["patient_ids"]),
            "turnos":       bkt["turnos"],
            "delta_turnos": None if prev_mt is None else bkt["turnos"] - prev_mt,
        })
        prev_mt = bkt["turnos"]

    # Generar series semanales sin queries adicionales
    weekly_turns: List[Dict] = []
    curr_m_start  = today.replace(day=1)
    first_monday  = curr_m_start - timedelta(days=curr_m_start.weekday())
    cur_mon       = first_monday
    prev_wt       = None
    while cur_mon <= current_week_monday:
        wk   = cur_mon.isoformat()
        buck = weekly_map.get(wk, {
            "week_label":  f"{cur_mon.strftime('%d/%m')} al {(cur_mon + timedelta(days=6)).strftime('%d/%m')}",
            "turnos":      0,
            "patient_ids": set(),
        })
        weekly_turns.append({
            "week_key":     wk,
            "week_label":   buck["week_label"],
            "turnos":       buck["turnos"],
            "pacientes":    len(buck["patient_ids"]),
            "delta_turnos": None if prev_wt is None else buck["turnos"] - prev_wt,
        })
        prev_wt = buck["turnos"]
        cur_mon += timedelta(days=7)

    cur_m  = next((x for x in monthly_patients if x["month_key"] == current_month_key), {"turnos": 0, "pacientes": 0})
    prev_m = monthly_patients[-2] if len(monthly_patients) > 1 else {"turnos": 0, "pacientes": 0}
    cur_w  = next((x for x in weekly_turns if x["week_key"] == current_week_monday.isoformat()), {"turnos": 0, "pacientes": 0, "week_label": ""})
    prev_w = next((x for x in weekly_turns if x["week_key"] == previous_week_monday.isoformat()), {"turnos": 0, "pacientes": 0, "week_label": ""})

    summary.update({
        "current_year":           today.year,
        "current_month_key":      current_month_key,
        "current_month_turns":    cur_m["turnos"],
        "current_month_patients": cur_m["pacientes"],
        "previous_month_turns":   prev_m["turnos"],
        "month_delta":            cur_m["turnos"] - prev_m["turnos"],
        "current_week_label":     cur_w["week_label"],
        "current_week_turns":     cur_w["turnos"],
        "current_week_patients":  cur_w["pacientes"],
        "previous_week_turns":    prev_w["turnos"],
        "week_delta":             cur_w["turnos"] - prev_w["turnos"],
    })

    # Q3: Booking consolidado de 4 semanas para ver cómo viene la agenda
    prev_fri = current_week_monday - timedelta(days=3)
    last_fri = current_week_monday + timedelta(days=25)

    booking_rows = cursor.execute(f"""
        SELECT a.fecha, a.patient_id
        FROM agenda_general a
        JOIN patients p ON p.id = a.patient_id
        WHERE {_f_obs} AND {_f_real}
          AND a.fecha >= ? AND a.fecha <= ?
        ORDER BY a.fecha ASC
    """, (prev_fri.isoformat(), last_fri.isoformat())).fetchall()

    def _agg_booking(rows, week_monday):
        pf = week_monday - timedelta(days=3)
        bmap: Dict[str, Dict] = {}
        for r in rows:
            dk = r["fecha"]
            if not dk:
                continue
            b = bmap.setdefault(dk, {"turnos": 0, "patient_ids": set()})
            b["turnos"] += 1
            if r["patient_id"]:
                b["patient_ids"].add(r["patient_id"])
        
        prev_dt_entry = bmap.get(pf.isoformat())
        prev_dt = prev_dt_entry["turnos"] if prev_dt_entry else 0
        
        days, b_turns, b_pats = [], 0, set()
        for offset in range(5):
            day  = week_monday + timedelta(days=offset)
            dk   = day.isoformat()
            buck = bmap.get(dk, {"turnos": 0, "patient_ids": set()})
            days.append({
                "day_key":      dk,
                "day_label":    day.strftime("%d/%m"),
                "turnos":       buck["turnos"],
                "pacientes":    len(buck["patient_ids"]),
                "delta_turnos": buck["turnos"] - prev_dt,
                "delta_label":  "viernes_anterior" if offset == 0 else "dia_anterior",
            })
            b_turns += buck["turnos"]
            b_pats.update(buck["patient_ids"])
            prev_dt = buck["turnos"]
        
        we = week_monday + timedelta(days=4)
        return {
            "week_label": f"{week_monday.strftime('%d/%m')} al {we.strftime('%d/%m')}",
            "days": days, "turnos": b_turns, "pacientes": len(b_pats),
        }

    booking_weeks = [
        _agg_booking(booking_rows, current_week_monday + timedelta(days=7 * idx))
        for idx in range(4)
    ]
    cur_booking = booking_weeks[0]
    next_booking = booking_weeks[1]
    summary.update({"booking_week_turns": cur_booking["turnos"], "booking_week_patients": cur_booking["pacientes"]})

    # Q4: Métricas por Especialidad (Agregadas en una query)
    specialties = cursor.execute("""
        SELECT
            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(tipo_sesion,'')) LIKE '%fono%'         THEN patient_id END) AS fono,
            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(tipo_sesion,'')) LIKE '%terapia ocup%' THEN patient_id END) AS to_people,
            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(tipo_sesion,'')) LIKE '%to + k%'
                               OR LOWER(COALESCE(observaciones,'')) LIKE '%to + k%'        THEN patient_id END) AS to_k,
            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(tipo_sesion,'')) LIKE '%fisiatra%'
                               OR LOWER(COALESCE(observaciones,'')) LIKE '%fisiatra%'      THEN patient_id END) AS fisiatra,
            COUNT(DISTINCT CASE WHEN LOWER(COALESCE(tipo_sesion,'')) LIKE '%test neuro%'
                               OR LOWER(COALESCE(observaciones,'')) LIKE '%test neuro%'    THEN patient_id END) AS test_neuro
        FROM agenda_general WHERE fecha >= ? AND fecha <= ?
    """, imported_params).fetchone()

    # Q5: Pacientes únicos Neuro (Tabla separada)
    neuro_people = cursor.execute("""
        SELECT COUNT(DISTINCT CASE WHEN COALESCE(TRIM(dni),'') <> '' THEN TRIM(dni) ELSE UPPER(TRIM(paciente)) END)
        FROM neuro_patients WHERE fecha >= ? AND fecha <= ?
    """, imported_params).fetchone()[0]

    def _estado(v):
        return "activo" if (v or 0) > 0 else "sin_registros"

    methods = [
        {"metodo": "ING PAMI",    "pacientes": summary["pami_patients_total"],      "estado": "activo"},
        {"metodo": "H.D",         "pacientes": hd_people,                           "estado": "activo"},
        {"metodo": "EVAL. NEURO", "pacientes": neuro_people or 0,                   "estado": "activo"},
        {"metodo": "FONO",        "pacientes": specialties["fono"]       or 0,      "estado": _estado(specialties["fono"])},
        {"metodo": "T.O",         "pacientes": specialties["to_people"]  or 0,      "estado": _estado(specialties["to_people"])},
        {"metodo": "TO + K",      "pacientes": specialties["to_k"]       or 0,      "estado": _estado(specialties["to_k"])},
        {"metodo": "FISIATRA",    "pacientes": specialties["fisiatra"]   or 0,      "estado": _estado(specialties["fisiatra"])},
        {"metodo": "TEST NEURO",  "pacientes": specialties["test_neuro"] or 0,      "estado": _estado(specialties["test_neuro"])},
    ]

    conn.close()
    return {
        "generated_at":            generated_at,
        "summary":                 summary,
        "methods":                 methods,
        "monthly_patients":        monthly_patients,
        "weekly_turns":            weekly_turns,
        "booking_days":            cur_booking["days"],
        "booking_days_next_week":  next_booking["days"],
        "booking_weeks":           booking_weeks,
        "booking_week_label":      cur_booking["week_label"],
        "booking_next_week_label": next_booking["week_label"],
        "notes": [
            f"El panel toma sólo {today.year} desde el 01/01 hasta el 31/12 con toda la agenda cargada.",
            "Office Agenda hoy entra con paciente, fecha y recurso. Los métodos específicos todavía no salen desde esa exportación.",
            "Fono quedó preparado para empezar a medirse en cuanto entren turnos con esa especialidad.",
        ],
    }
