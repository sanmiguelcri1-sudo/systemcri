import json

import pyodbc

import database
import ingreso_egreso
import intersoftic_stats


def _clean(value) -> str:
    return str(value or "").strip()


def _date(value) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


def _cargo_from_specialties(specialties: set[str]) -> str:
    joined = " ".join(specialties).upper()
    if "FONO" in joined:
        return "FONOAUDIOLOGIA"
    if "OCUPACIONAL" in joined or "250103" in joined:
        return "TERAPIA OCUPACIONAL"
    if "FISIO" in joined or "KINES" in joined or "250101" in joined or "250102" in joined:
        return "KINESIOLOGIA"
    if "MEDICA" in joined or "CONSULTA" in joined:
        return "MEDICO"
    return ""


def _upsert_raw_intersoftic_profile(row: dict) -> None:
    conn = database.create_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO intersoftic_professionals (
            intersoftic_profesional_id, staff_id, staff_key, activo, apellido, nombre, nombre_completo,
            tipo_documento, documento, matricula_1, matricula_2, telefono, movil, mail, fecha_ingreso,
            sucursal_intersoftic_id, sucursal_intersoftic, sucursal_detectada_2026, efectores_2026,
            especialidades_detectadas, domicilio_laboral, color_localizacion, motivo_baja,
            observaciones_intersoftic, raw_json, synced_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(intersoftic_profesional_id) DO UPDATE SET
            staff_id = excluded.staff_id,
            staff_key = excluded.staff_key,
            activo = excluded.activo,
            apellido = excluded.apellido,
            nombre = excluded.nombre,
            nombre_completo = excluded.nombre_completo,
            tipo_documento = excluded.tipo_documento,
            documento = excluded.documento,
            matricula_1 = excluded.matricula_1,
            matricula_2 = excluded.matricula_2,
            telefono = excluded.telefono,
            movil = excluded.movil,
            mail = excluded.mail,
            fecha_ingreso = excluded.fecha_ingreso,
            sucursal_intersoftic_id = excluded.sucursal_intersoftic_id,
            sucursal_intersoftic = excluded.sucursal_intersoftic,
            sucursal_detectada_2026 = excluded.sucursal_detectada_2026,
            efectores_2026 = excluded.efectores_2026,
            especialidades_detectadas = excluded.especialidades_detectadas,
            domicilio_laboral = excluded.domicilio_laboral,
            color_localizacion = excluded.color_localizacion,
            motivo_baja = excluded.motivo_baja,
            observaciones_intersoftic = excluded.observaciones_intersoftic,
            raw_json = excluded.raw_json,
            synced_at = CURRENT_TIMESTAMP
        ''',
        (
            row["intersoftic_profesional_id"],
            row["staff_id"],
            row["staff_key"],
            row["activo"],
            row["apellido"],
            row["nombre"],
            row["nombre_completo"],
            row["tipo_documento"],
            row["documento"],
            row["matricula_1"],
            row["matricula_2"],
            row["telefono"],
            row["movil"],
            row["mail"],
            row["fecha_ingreso"],
            row["sucursal_intersoftic_id"],
            row["sucursal_intersoftic"],
            row["sucursal_detectada_2026"],
            row["efectores_2026"],
            row["especialidades_detectadas"],
            row["domicilio_laboral"],
            row["color_localizacion"],
            row["motivo_baja"],
            row["observaciones_intersoftic"],
            row["raw_json"],
        ),
    )
    conn.commit()
    conn.close()


def import_professionals() -> dict[str, int]:
    database.init_db()
    conn_str = (
        "DRIVER={SQL Server};"
        f"SERVER={intersoftic_stats.SQL_SERVER};"
        f"DATABASE={intersoftic_stats.SQL_DATABASE};"
        f"UID={intersoftic_stats.SQL_USER};"
        f"PWD={intersoftic_stats.SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=8;"
    )
    conn = pyodbc.connect(conn_str, timeout=8)
    try:
        cursor = conn.cursor()
        sucursales = {
            int(row.SucursalID): _clean(row.Descripcion)
            for row in cursor.execute("SELECT SucursalID, Descripcion FROM dbo.Sucursales")
        }

        usage_by_prof: dict[int, dict[int, int]] = {}
        for row in cursor.execute(
            """
            SELECT ep.ProfesionalID, ef.SucursalID, COUNT(*) AS Cantidad
            FROM dbo.Efectores_Profesionales ep
            INNER JOIN dbo.Efectores ef ON ef.EfectorID = ep.EfectorID
            WHERE ep.ProfesionalID IS NOT NULL AND ep.ProfesionalID <> 0
              AND ef.Fecha >= '2026-01-01' AND ef.Fecha < '2027-01-01'
            GROUP BY ep.ProfesionalID, ef.SucursalID
            """
        ):
            usage_by_prof.setdefault(int(row.ProfesionalID), {})[int(row.SucursalID or 0)] = int(row.Cantidad or 0)

        specialties_by_prof: dict[int, set[str]] = {}
        for row in cursor.execute(
            """
            SELECT DISTINCT em.ProfesionalID, e.Descripcion
            FROM dbo.Efectores_Modulos em
            LEFT JOIN dbo.Especialidades e ON e.EspecialidadID = em.EspecialidadID
            WHERE em.ProfesionalID IS NOT NULL AND em.ProfesionalID <> 0
            """
        ):
            if row.Descripcion:
                specialties_by_prof.setdefault(int(row.ProfesionalID), set()).add(_clean(row.Descripcion))

        inserted = 0
        updated = 0
        professionals = cursor.execute(
            """
            SELECT ProfesionalID, Apellido, Nombre, Activo, TipoDocumento, NumeorDocumento, NMatricula, NMatricula2,
                   Telefono, Movil, Mail, FechaIngreso, MotivoDeBaja, Observaciones, SucursalID,
                   DomicilioLaboral, ColorLocalizacion
            FROM dbo.Profesionales
            WHERE ProfesionalID <> 0 AND COALESCE(Activo, '') = 'S'
            ORDER BY Apellido, Nombre
            """
        ).fetchall()

        for prof in professionals:
            pid = int(prof.ProfesionalID)
            apellido = _clean(prof.Apellido)
            nombre = _clean(prof.Nombre)
            full_name = f"{apellido}, {nombre}".strip(", ")
            staff_key = ingreso_egreso.normalize_key(f"{apellido} {nombre}") or f"INTERSOFTIC{pid}"
            existing = database.get_staff_by_key(staff_key)
            specialties = specialties_by_prof.get(pid, set())
            usage = usage_by_prof.get(pid, {})
            total_usage = sum(usage.values())
            main_usage_sucursal_id = max(usage, key=usage.get) if usage else int(prof.SucursalID or 0)
            intersoftic_sucursal_id = int(prof.SucursalID or 0)

            if existing is None:
                database.upsert_staff(
                    staff_key=staff_key,
                    nombre=full_name,
                    cargo=_cargo_from_specialties(specialties),
                    include_in_word=True,
                    fecha_ingreso=_date(prof.FechaIngreso),
                    fecha_egreso="",
                    default_ingreso="",
                    default_egreso="",
                )
                inserted += 1
            else:
                database.upsert_staff(
                    staff_key=staff_key,
                    nombre=str(existing["nombre"] or full_name),
                    cargo=str(existing["cargo"] or _cargo_from_specialties(specialties)),
                    include_in_word=bool(int(existing["include_in_word"] or 0)),
                    fecha_ingreso=str(existing["fecha_ingreso"] or _date(prof.FechaIngreso)),
                    fecha_egreso=str(existing["fecha_egreso"] or ""),
                    default_ingreso=str(existing["default_ingreso"] or ""),
                    default_egreso=str(existing["default_egreso"] or ""),
                )
                updated += 1

            detected = ", ".join(
                f"{sucursales.get(sid, 'SIN SUCURSAL')} ({count})"
                for sid, count in sorted(usage.items(), key=lambda item: item[1], reverse=True)
            )
            database.update_staff_intersoftic_details(
                staff_key=staff_key,
                intersoftic_profesional_id=pid,
                intersoftic_activo=_clean(prof.Activo),
                tipo_documento=_clean(prof.TipoDocumento),
                documento=_clean(prof.NumeorDocumento),
                matricula_1=_clean(prof.NMatricula),
                matricula_2=_clean(prof.NMatricula2),
                telefono=_clean(prof.Telefono),
                movil=_clean(prof.Movil),
                mail=_clean(prof.Mail),
                sucursal_intersoftic_id=intersoftic_sucursal_id,
                sucursal_intersoftic=sucursales.get(intersoftic_sucursal_id, "SIN SUCURSAL"),
                sucursal_detectada_2026=detected or sucursales.get(main_usage_sucursal_id, "SIN SUCURSAL"),
                efectores_2026=total_usage,
                especialidades_detectadas=", ".join(sorted(specialties)),
                domicilio_laboral=_clean(prof.DomicilioLaboral),
                color_localizacion=_clean(prof.ColorLocalizacion),
                motivo_baja=_clean(prof.MotivoDeBaja),
                observaciones_intersoftic=_clean(prof.Observaciones),
            )
            staff_row = database.get_staff_by_key(staff_key)
            raw_payload = {
                "ProfesionalID": pid,
                "Apellido": apellido,
                "Nombre": nombre,
                "Activo": _clean(prof.Activo),
                "TipoDocumento": _clean(prof.TipoDocumento),
                "NumeorDocumento": _clean(prof.NumeorDocumento),
                "NMatricula": _clean(prof.NMatricula),
                "NMatricula2": _clean(prof.NMatricula2),
                "Telefono": _clean(prof.Telefono),
                "Movil": _clean(prof.Movil),
                "Mail": _clean(prof.Mail),
                "FechaIngreso": _date(prof.FechaIngreso),
                "SucursalID": intersoftic_sucursal_id,
                "DomicilioLaboral": _clean(prof.DomicilioLaboral),
                "ColorLocalizacion": _clean(prof.ColorLocalizacion),
                "MotivoDeBaja": _clean(prof.MotivoDeBaja),
                "Observaciones": _clean(prof.Observaciones),
            }
            _upsert_raw_intersoftic_profile(
                {
                    "intersoftic_profesional_id": pid,
                    "staff_id": int(staff_row["id"]) if staff_row else None,
                    "staff_key": staff_key,
                    "activo": _clean(prof.Activo),
                    "apellido": apellido,
                    "nombre": nombre,
                    "nombre_completo": full_name,
                    "tipo_documento": _clean(prof.TipoDocumento),
                    "documento": _clean(prof.NumeorDocumento),
                    "matricula_1": _clean(prof.NMatricula),
                    "matricula_2": _clean(prof.NMatricula2),
                    "telefono": _clean(prof.Telefono),
                    "movil": _clean(prof.Movil),
                    "mail": _clean(prof.Mail),
                    "fecha_ingreso": _date(prof.FechaIngreso),
                    "sucursal_intersoftic_id": intersoftic_sucursal_id,
                    "sucursal_intersoftic": sucursales.get(intersoftic_sucursal_id, "SIN SUCURSAL"),
                    "sucursal_detectada_2026": detected or sucursales.get(main_usage_sucursal_id, "SIN SUCURSAL"),
                    "efectores_2026": total_usage,
                    "especialidades_detectadas": ", ".join(sorted(specialties)),
                    "domicilio_laboral": _clean(prof.DomicilioLaboral),
                    "color_localizacion": _clean(prof.ColorLocalizacion),
                    "motivo_baja": _clean(prof.MotivoDeBaja),
                    "observaciones_intersoftic": _clean(prof.Observaciones),
                    "raw_json": json.dumps(raw_payload, ensure_ascii=False),
                }
            )

        return {"inserted": inserted, "updated": updated, "total": len(professionals)}
    finally:
        conn.close()


if __name__ == "__main__":
    result = import_professionals()
    print(result)
