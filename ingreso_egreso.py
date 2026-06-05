import datetime as _dt
import os
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional
from utils.text import strip_accents as _strip_accents, clean_text_keep_letters as _clean_text_keep_letters, normalize_key


MONTHS_ES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}

MONTH_ALIASES = {
    1: {"ENERO"},
    2: {"FEBRERO"},
    3: {"MARZO"},
    4: {"ABRIL"},
    5: {"MAYO"},
    6: {"JUNIO"},
    7: {"JULIO"},
    8: {"AGOSTO"},
    9: {"SEPTIEMBRE", "SETIEMBRE"},
    10: {"OCTUBRE"},
    11: {"NOVIEMBRE"},
    12: {"DICIEMBRE", "DICEIMBRE"},
}


DEFAULT_FACILITY = "CRI SAN MIGUEL"
DEFAULT_DOC_PREFIX = "LIstado SAN MIGUEL"

# Estos patrones NO van en el Word (se pueden cambiar desde ABM personal).
DEFAULT_EXCLUDE_IN_WORD_PATTERNS = ["AZOCAR", "KALAFA", "LEGUIZAMON", "MARIANI"]


@dataclass(frozen=True)
class AttendanceRecord:
    staff_key: str
    staff_name: str
    date: str  # YYYY-MM-DD
    ingreso: str  # HH:MM
    egreso: str  # HH:MM
    hours: float


@dataclass(frozen=True)
class WordRow:
    name: str
    cargo: str
    hours: str




def infer_month_year_from_path(path: str) -> tuple[Optional[int], Optional[int]]:
    haystack = _strip_accents(str(path or "")).upper()
    year_match = re.search(r"(20\d{2})", haystack)
    year = int(year_match.group(1)) if year_match else None

    month = None
    for m, aliases in MONTH_ALIASES.items():
        if any(alias in haystack for alias in aliases):
            month = m
            break
    return month, year


def parse_month_arg(raw: str) -> int:
    if raw is None:
        raise ValueError("Mes vacío.")
    raw = raw.strip()
    if not raw:
        raise ValueError("Mes vacío.")
    if raw.isdigit():
        m = int(raw)
        if 1 <= m <= 12:
            return m
        raise ValueError("El mes debe estar entre 1 y 12.")

    raw_norm = _strip_accents(raw).upper()
    for m, aliases in MONTH_ALIASES.items():
        if raw_norm in aliases:
            return m
    raise ValueError(f"Mes inválido: {raw!r}")


def format_hours(value: Any) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
    except Exception:
        s = str(value).strip()
        return s

    if abs(v) < 1e-9:
        return ""
    v = round(v + 1e-12, 2)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _excel_time_to_minutes(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Excel: fracción del día
        v = float(value)
        if abs(v) < 1e-12:
            return None
        minutes = int(round(v * 24.0 * 60.0))
        minutes = max(0, minutes)
        return minutes
    s = str(value).strip()
    if not s:
        return None
    return parse_hhmm_to_minutes(s)


def minutes_to_hhmm(minutes: int) -> str:
    minutes = int(minutes) % (24 * 60)
    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


def parse_hhmm_to_minutes(raw: str) -> Optional[int]:
    s = str(raw or "").strip()
    if not s:
        return None
    s = s.replace(".", ":")
    m = re.match(r"^(\d{1,2})(?::(\d{1,2}))?$", s)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2) or "0")
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return hh * 60 + mm


def compute_hours_from_minutes(ingreso_min: int, egreso_min: int) -> float:
    if ingreso_min is None or egreso_min is None:
        return 0.0
    start = int(ingreso_min)
    end = int(egreso_min)
    if end < start:
        # Si cruza medianoche, asumir egreso al día siguiente.
        end += 24 * 60
    diff_min = end - start
    if diff_min <= 0:
        return 0.0
    return float(Decimal(diff_min) / Decimal(60))


def should_exclude_in_word(staff_key: str) -> bool:
    key_upper = (staff_key or "").upper()
    for pat in DEFAULT_EXCLUDE_IN_WORD_PATTERNS:
        pat_norm = normalize_key(pat)
        if pat_norm and pat_norm in key_upper:
            return True
    return False


def parse_excel_timesheet(excel_path: str, *, month: Optional[int] = None, year: Optional[int] = None) -> tuple[int, int, list[AttendanceRecord]]:
    """
    Parsea un Excel como el de ABRIL 2026 (filas: personal, columnas: días con ENTER/OUT/TOTAL).
    Devuelve (month, year, records).
    """
    import pythoncom
    from win32com.client import DispatchEx

    excel_path_abs = os.path.abspath(excel_path)
    if month is None or year is None:
        m2, y2 = infer_month_year_from_path(excel_path_abs)
        month = month or m2
        year = year or y2
    if month is None or year is None:
        raise ValueError("No pude inferir mes/año del Excel. Indicá mes y año.")

    pythoncom.CoInitialize()
    xl = DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    wb = None
    try:
        wb = xl.Workbooks.Open(excel_path_abs, ReadOnly=True)
        sheet = wb.Sheets(1)

        used = sheet.UsedRange
        used_rows = int(used.Rows.Count)
        used_cols = int(used.Columns.Count)

        # Buscar fila con "PROF" en columna A.
        prof_row = None
        for r in range(1, min(used_rows, 20) + 1):
            v = sheet.Cells(r, 1).Value
            if v is None:
                continue
            if _strip_accents(str(v)).strip().upper() == "PROF":
                prof_row = r
                break
        if prof_row is None:
            raise ValueError("No encontré la fila de encabezado 'PROF'.")

        day_header_row = prof_row
        label_row = prof_row + 1
        start_row = prof_row + 2

        # Identificar grupos por día: columna con número de día y etiqueta ENTER.
        day_groups: list[tuple[int, int, int, int]] = []
        # (day, enter_col, out_col, total_col)
        c = 2
        while c <= used_cols:
            day_val = sheet.Cells(day_header_row, c).Value
            label_val = sheet.Cells(label_row, c).Value
            label_txt = _strip_accents(str(label_val or "")).upper().strip()
            day_num = None
            try:
                if day_val is not None and str(day_val).strip() != "":
                    day_num = int(float(day_val))
            except Exception:
                day_num = None

            if day_num and 1 <= day_num <= 31 and "ENTER" in label_txt:
                enter_col = c
                out_col = c + 1
                total_col = c + 2
                day_groups.append((day_num, enter_col, out_col, total_col))
                c += 3
                continue
            c += 1

        if not day_groups:
            raise ValueError("No encontré columnas de días (ENTER/OUT/TOTAL).")

        records: list[AttendanceRecord] = []
        for r in range(start_row, used_rows + 1):
            raw_name = sheet.Cells(r, 1).Value
            if raw_name is None or str(raw_name).strip() == "":
                continue
            staff_name = _clean_text_keep_letters(str(raw_name)).strip()
            staff_key = normalize_key(staff_name)
            if not staff_key:
                continue

            for day_num, enter_col, out_col, total_col in day_groups:
                enter_val = sheet.Cells(r, enter_col).Value
                out_val = sheet.Cells(r, out_col).Value
                total_val = sheet.Cells(r, total_col).Value

                enter_min = _excel_time_to_minutes(enter_val)
                out_min = _excel_time_to_minutes(out_val)

                hours = 0.0
                if total_val is not None and str(total_val).strip() != "":
                    try:
                        tv = float(total_val)
                        # Si TOTAL está como fracción del día, pasarlo a horas.
                        if 0 < tv <= 1 and enter_min is not None and out_min is not None:
                            hours = compute_hours_from_minutes(enter_min, out_min)
                        else:
                            hours = tv
                    except Exception:
                        hours = 0.0
                elif enter_min is not None and out_min is not None:
                    hours = compute_hours_from_minutes(enter_min, out_min)

                if hours <= 1e-9:
                    continue

                date_iso = f"{int(year):04d}-{int(month):02d}-{int(day_num):02d}"
                ingreso = minutes_to_hhmm(enter_min) if enter_min is not None else ""
                egreso = minutes_to_hhmm(out_min) if out_min is not None else ""
                records.append(
                    AttendanceRecord(
                        staff_key=staff_key,
                        staff_name=staff_name,
                        date=date_iso,
                        ingreso=ingreso,
                        egreso=egreso,
                        hours=float(hours),
                    )
                )

        return int(month), int(year), records
    finally:
        try:
            if wb is not None:
                wb.Close(False)
        finally:
            xl.Quit()
            pythoncom.CoUninitialize()


def backup_if_exists(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))
    backup_name = f"{stem}.bak_{ts}{ext}"
    backup_path = os.path.join(folder, backup_name)
    os.replace(path, backup_path)
    return backup_path


def write_word_doc(
    *,
    output_path: str,
    facility: str,
    month_name: str,
    year: int,
    rows: list[WordRow],
) -> None:
    import pythoncom
    from win32com.client import DispatchEx

    output_path_abs = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path_abs), exist_ok=True)

    pythoncom.CoInitialize()
    word = DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0

    doc = None
    try:
        doc = word.Documents.Add()
        table_rows = 2 + len(rows)
        table = doc.Tables.Add(doc.Range(0, 0), NumRows=table_rows, NumColumns=3)
        try:
            table.Borders.Enable = True
        except Exception:
            pass

        table.Cell(1, 1).Range.Text = facility
        table.Cell(1, 2).Range.Text = f"MES: {month_name} {year}"
        table.Cell(1, 3).Range.Text = ""

        table.Cell(2, 1).Range.Text = "NOMBRE"
        table.Cell(2, 2).Range.Text = "CARGO"
        table.Cell(2, 3).Range.Text = "HORAS"

        r = 3
        for row in rows:
            table.Cell(r, 1).Range.Text = row.name
            table.Cell(r, 2).Range.Text = row.cargo
            table.Cell(r, 3).Range.Text = row.hours
            r += 1

        doc.Range(doc.Content.End - 1, doc.Content.End - 1).InsertAfter("\r\n\r\nObservaciones:\r\n")
        doc.SaveAs2(output_path_abs, FileFormat=16)
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        finally:
            word.Quit()
            pythoncom.CoUninitialize()
