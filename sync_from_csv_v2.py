import csv
import sqlite3
import re
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB = os.path.join(BASE_DIR, 'hc_archive.db')

def clean_digits(value):
    return re.sub(r'\D+', '', str(value or ''))

def pick_hc_number(_mdb_patient_id, used_hc_numbers, next_hc):
    """Asigna el próximo num_hc local sin pisar la numeración manual."""
    while str(next_hc) in used_hc_numbers:
        next_hc += 1
    hc = str(next_hc)
    used_hc_numbers.add(hc)
    return hc, next_hc + 1

def resolve_patient_id(cursor, pat_id, patient_db_id_map, patient_hc_id_map):
    hc_from_office = clean_digits(pat_id)
    sqlite_id = patient_db_id_map.get(pat_id) or patient_hc_id_map.get(hc_from_office)
    if sqlite_id:
        patient_db_id_map[pat_id] = sqlite_id
        cursor.execute(
            "UPDATE patients SET mdb_id = COALESCE(NULLIF(mdb_id, ''), ?) WHERE id = ?",
            (pat_id, sqlite_id)
        )
    return sqlite_id

def run_sync():
    print("Iniciando sincronización desde 2020...")

    existing_agenda_created = {}
    preserve_existing_created = False
    try:
        previous_conn = sqlite3.connect(SQLITE_DB)
        previous_conn.row_factory = sqlite3.Row
        previous_cursor = previous_conn.cursor()
        previous_cursor.execute('''
            SELECT p.mdb_id, a.fecha, a.hora, a.recurso, a.fecha_carga
            FROM agenda_general a
            JOIN patients p ON p.id = a.patient_id
            WHERE COALESCE(a.observaciones, '') LIKE 'Importado de Office Agenda%'
              AND COALESCE(p.mdb_id, '') <> ''
        ''')
        for row in previous_cursor.fetchall():
            key = f"{row['mdb_id']}_{row['fecha']}_{row['hora']}_{row['recurso']}"
            existing_agenda_created[key] = row["fecha_carga"]
        previous_conn.close()
        preserve_existing_created = True
    except Exception:
        existing_agenda_created = {}
        preserve_existing_created = False

    # 1. Cargar pacientes: PatId -> Nombre
    agenda_patients = {}
    with open('scratch/exp_pat.csv', 'r', encoding='latin1') as f:
        reader = csv.reader(f)
        try: next(reader) # skip header
        except: pass
        for row in reader:
            if len(row) < 4: continue
            kennummer = row[0].strip()
            last = row[1].strip()
            first = row[2].strip()
            dni_raw = row[3].strip() if len(row) > 3 else ""
            if last.isdigit() and not first and not dni_raw:
                continue

            full_name = f"{last} {first}".strip().upper()
            full_name = re.sub(r'\s+', ' ', full_name)
            if kennummer:
                agenda_patients[kennummer] = {"name": full_name, "dni_raw": dni_raw, "dates": [], "all_appointments": []}

    # 2. Cargar fechas de turnos
    with open('scratch/exp_ter.csv', 'r', encoding='latin1') as f:
        reader = csv.reader(f)
        try: next(reader) # skip header
        except: pass
        for row in reader:
            if len(row) < 2: continue
            pat_id = row[0].strip()
            dt_str = row[1].strip()
            if pat_id in agenda_patients and dt_str:
                try:
                    parts = dt_str.split(' ')
                    dt_part = parts[0]
                    tm_part = parts[1] if len(parts) > 1 else "00:00:00"

                    d, m, y = dt_part.split('/')
                    # Ignore anything before 2020 for history
                    if int(y) >= 2020:
                        iso_dt = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                        agenda_patients[pat_id]["dates"].append(iso_dt)

                        # Store for agenda_general if it's recent (2026+)
                        if int(y) >= 2026:
                            res_str = row[2].strip() if len(row) > 2 else "D1;"
                            match = re.search(r'D(\d+)', res_str)
                            raum_id = match.group(1) if match else "1"

                            h, m_orig = tm_part[:2], tm_part[3:5]
                            m_rounded = "00" if int(m_orig) < 30 else "30"
                            rounded_time = f"{h}:{m_rounded}"
                            box_name = f"Kine {raum_id}"

                            # Evitar duplicados exactos (mismo paciente, mismo dia, mismo box, misma hora redondeada)
                            dup_key = f"{pat_id}_{iso_dt}_{rounded_time}_{box_name}"
                            if "added_keys" not in agenda_patients[pat_id]:
                                agenda_patients[pat_id]["added_keys"] = set()

                            if dup_key not in agenda_patients[pat_id]["added_keys"]:
                                agenda_patients[pat_id]["all_appointments"].append({
                                    "fecha": iso_dt,
                                    "hora": rounded_time,
                                    "recurso": box_name
                                })
                                agenda_patients[pat_id]["added_keys"].add(dup_key)
                except:
                    pass

    # 3. Crear ciclos (Máximo 10 sesiones, o corte por inactividad)
    all_cycles = []
    for pat_id, data in agenda_patients.items():
        dates = sorted(list(set(data["dates"])))
        if not dates: continue

        cycles_for_patient = []
        current_cycle = []

        for d_str in dates:
            d_obj = datetime.strptime(d_str, "%Y-%m-%d")
            if not current_cycle:
                current_cycle.append(d_obj)
                continue

            start_obj = current_cycle[0]
            prev_obj = current_cycle[-1]

            gap_days = (d_obj - prev_obj).days
            total_duration = (d_obj - start_obj).days

            # Cortar ciclo si:
            # - llega a 10 sesiones
            # - pasaron más de 30 días sin venir (abandono visible)
            # - el ciclo en total ya dura más de 65 días (15 días extra por pre-feriados)
            if len(current_cycle) == 10 or gap_days > 30 or total_duration > 65:
                cycles_for_patient.append(current_cycle)
                current_cycle = [d_obj]
            else:
                current_cycle.append(d_obj)

        if current_cycle:
            cycles_for_patient.append(current_cycle)

        for chunk in cycles_for_patient:
            start_date = chunk[0].strftime("%Y-%m-%d")
            end_date = chunk[-1].strftime("%Y-%m-%d")
            y = int(end_date[:4])
            m = int(end_date[5:7])
            all_cycles.append({
                "pat_id": pat_id,
                "name": data["name"],
                "dni_raw": data.get("dni_raw", ""),
                "start": start_date,
                "end": end_date,
                "y": y,
                "m": m
            })

    # Ordenar todos los ciclos cronológicamente para asignar HC a los más antiguos primero
    all_cycles.sort(key=lambda x: x["start"])

    # 4. Reconstruir BD (No destructivo)
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 4.1. Mapear pacientes existentes por mdb_id, num_hc y DNI
    cursor.execute("SELECT id, dni, mdb_id, num_hc FROM patients")
    existing_patients = cursor.fetchall()
    patient_db_id_map = {row['mdb_id']: row['id'] for row in existing_patients if row['mdb_id']}
    patient_hc_id_map = {clean_digits(row['num_hc']): row['id'] for row in existing_patients if clean_digits(row['num_hc'])}
    used_dnis = {row['dni'] for row in existing_patients if row['dni']}
    used_hc_numbers = {clean_digits(row['num_hc']) for row in existing_patients if clean_digits(row['num_hc'])}

    # Determinar el siguiente número de HC real
    next_hc = 1
    hc_nums = [int(num) for num in used_hc_numbers if num.isdigit()]
    if hc_nums:
        next_hc = max(hc_nums) + 1

    # 4.2. Limpiar solo tablas derivadas de Office Agenda (no tocar manuales)
    cursor.execute("DELETE FROM agenda_general WHERE COALESCE(observaciones, '') LIKE 'Importado de Office Agenda%'")
    cursor.execute("DELETE FROM renewals WHERE patient_id IN (SELECT id FROM patients WHERE mdb_id IS NOT NULL)")

    stats_patients_new = 0
    stats_patients_updated = 0
    stats_patients = 0
    stats_cycles = 0

    # 4.3. Procesar ciclos e Insertar/Actualizar pacientes
    for cycle in all_cycles:
        pat_id = cycle["pat_id"]
        sqlite_id = resolve_patient_id(cursor, pat_id, patient_db_id_map, patient_hc_id_map)

        if not sqlite_id:
            # First time seeing this patient, create their record
            raw_d = cycle.get("dni_raw", "").strip()
            if not raw_d or raw_d in used_dnis or len(raw_d) < 5:
                dni_final = "TEMP_" + str(next_hc)
            else:
                dni_final = raw_d
            used_dnis.add(dni_final)
            hc_final, next_hc = pick_hc_number(pat_id, used_hc_numbers, next_hc)

            cursor.execute('''
                INSERT INTO patients (
                    apellido_nombre, dni, num_hc, anio_vigencia, mes_renovacion,
                    fecha_inicio, fecha_fin, mdb_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                cycle["name"], dni_final, hc_final,
                cycle["y"], cycle["m"], cycle["start"], cycle["end"], pat_id
            ))
            patient_db_id_map[pat_id] = cursor.lastrowid
            patient_hc_id_map[hc_final] = cursor.lastrowid
            stats_patients += 1
        else:
            cursor.execute('''
                UPDATE patients SET anio_vigencia=?, mes_renovacion=?, fecha_inicio=?, fecha_fin=?
                WHERE id=?
            ''', (cycle["y"], cycle["m"], cycle["start"], cycle["end"], sqlite_id))

        sqlite_id = patient_db_id_map[pat_id]
        cursor.execute('''
            INSERT INTO renewals (patient_id, anio, mes, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?, ?)
        ''', (sqlite_id, cycle["y"], cycle["m"], cycle["start"], cycle["end"]))
        stats_cycles += 1

    # Insert patients from agenda (only those without cycles)
    for pat_id, data in agenda_patients.items():
        sqlite_id = resolve_patient_id(cursor, pat_id, patient_db_id_map, patient_hc_id_map)
        if not sqlite_id:
            raw_d = data.get("dni_raw", "").strip()
            if not raw_d or raw_d in used_dnis or len(raw_d) < 5:
                dni_final = "TEMP_" + str(next_hc)
            else:
                dni_final = raw_d
            used_dnis.add(dni_final)
            hc_final, next_hc = pick_hc_number(pat_id, used_hc_numbers, next_hc)

            cursor.execute('''
                INSERT INTO patients (
                    apellido_nombre, dni, num_hc, anio_vigencia, mes_renovacion, mdb_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (data["name"], dni_final, hc_final, 2026, 1, pat_id))
            patient_db_id_map[pat_id] = cursor.lastrowid
            patient_hc_id_map[hc_final] = cursor.lastrowid
            used_dnis.add(dni_final)
            stats_patients_new += 1

    # 5. Poblar Agenda General (solo turnos 2026+)
    stats_appointments = 0
    imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for pat_id, data in agenda_patients.items():
        if pat_id in patient_db_id_map:
            sqlite_id = patient_db_id_map[pat_id]
            for appo in data["all_appointments"]:
                fecha_carga = existing_agenda_created.get(
                    f"{pat_id}_{appo['fecha']}_{appo['hora']}_{appo['recurso']}",
                    imported_at if preserve_existing_created else appo["fecha"]
                )
                cursor.execute('''
                    INSERT INTO agenda_general (patient_id, fecha, hora, recurso, tipo_sesion, observaciones, fecha_carga)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (sqlite_id, appo["fecha"], appo["hora"], appo["recurso"], "Sincronizado", "Importado de Office Agenda", fecha_carga))
                stats_appointments += 1

    conn.commit()
    conn.close()

    # 6. Refrescar Ficha Maestra
    print("Sincronización de registros completada. Refrescando ficha maestra...")
    from db.patients import rebuild_patient_master
    rebuild_patient_master()

    print(f"Sincronización FINALIZADA (Modo No Destructivo).")
    print(f"Pacientes nuevos: {stats_patients_new}")
    print(f"Pacientes actualizados: {stats_patients_updated}")
    print(f"Ciclos históricos registrados: {stats_cycles}")
    print(f"Turnos cargados en Agenda (2026): {stats_appointments}")

if __name__ == "__main__":
    run_sync()
