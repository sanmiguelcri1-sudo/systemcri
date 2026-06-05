import csv
import datetime as dt
from collections import Counter
from typing import Dict, List

import database

OFFICE_PATIENTS_CSV = "scratch/exp_pat.csv"
OFFICE_APPOINTMENTS_CSV = "scratch/exp_ter.csv"
INVALID_PATIENT_NAMES = {"", "-", "OCUPADO", "LIBRE"}


def load_office_patients() -> Dict[str, Dict[str, str]]:
    patients: Dict[str, Dict[str, str]] = {}
    with open(OFFICE_PATIENTS_CSV, "r", encoding="latin1", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            pat_id = row[0].strip()
            if not pat_id:
                continue
            full_name = f"{row[1].strip()} {row[2].strip()}".strip().upper()
            patients[pat_id] = {
                "paciente": full_name,
                "dni": row[3].strip(),
            }
    return patients


def build_top25(limit: int = 25) -> Dict[str, object]:
    cutoff = dt.date.today()
    patients = load_office_patients()
    counts: Counter[str] = Counter()
    first_session: Dict[str, str] = {}
    last_session: Dict[str, str] = {}

    with open(OFFICE_APPOINTMENTS_CSV, "r", encoding="latin1", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue

            pat_id = row[0].strip()
            patient = patients.get(pat_id)
            if not patient or pat_id == "-1" or patient["paciente"] in INVALID_PATIENT_NAMES:
                continue

            raw_dt = row[1].strip()
            if not raw_dt:
                continue

            try:
                d, m, y = raw_dt.split(" ")[0].split("/")
                session_date = dt.date(int(y), int(m), int(d))
            except ValueError:
                continue

            if session_date < dt.date(2020, 1, 1) or session_date > cutoff:
                continue

            iso_date = session_date.isoformat()
            counts[pat_id] += 1

            if pat_id not in first_session or iso_date < first_session[pat_id]:
                first_session[pat_id] = iso_date
            if pat_id not in last_session or iso_date > last_session[pat_id]:
                last_session[pat_id] = iso_date

    top25: List[Dict[str, object]] = []
    for position, (pat_id, total) in enumerate(counts.most_common(limit), start=1):
        patient = patients.get(pat_id, {})
        top25.append(
            {
                "puesto": position,
                "pat_id": pat_id,
                "paciente": patient.get("paciente", ""),
                "dni": patient.get("dni", ""),
                "sesiones": total,
                "primera_sesion": first_session.get(pat_id, ""),
                "ultima_sesion": last_session.get(pat_id, ""),
            }
        )

    conn = database.create_connection()
    cursor = conn.cursor()
    first_history = cursor.execute(
        """
        SELECT id, apellido_nombre, dni, num_hc, anio_vigencia, mes_renovacion, fecha_inicio, fecha_fin
        FROM patients
        WHERE num_hc = '1'
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    return {
        "cutoff": cutoff.isoformat(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "top25": top25,
        "history_one": dict(first_history) if first_history else None,
    }


if __name__ == "__main__":
    print(build_top25())
