import csv
import datetime
import glob
import json
import os
import calendar
import time
import re
from collections import defaultdict
from pathlib import Path

try:
    import pyodbc
except Exception:
    pyodbc = None

try:
    import pymssql
except Exception:
    pymssql = None

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"), override=False)
except Exception:
    pass


EXPORT_GLOB = r"C:\Intersoftic\DLL\Exportado_*.csv"
OUTPUT_CSV = os.path.join("scratch", "intersoftic_stats_2026.csv")
MANUAL_JSON = os.path.join(os.path.dirname(__file__), "intersoftic_manual_2026.json")
MANUAL_BY_BRANCH_JSON = os.path.join(os.path.dirname(__file__), "intersoftic_manual_2026_by_branch.json")
TARGET_BRANCH = "SAN MIGUEL"
TARGET_YEAR = "2026"
SQL_SERVER = os.environ.get("INTERSOFTIC_SQL_SERVER", "")
SQL_DATABASE = os.environ.get("INTERSOFTIC_SQL_DATABASE", "")
SQL_USER = os.environ.get("INTERSOFTIC_SQL_USER", "")
SQL_PASSWORD = os.environ.get("INTERSOFTIC_SQL_PASSWORD", "")
SQL_OBRA_SOCIAL_ID = int(os.environ.get("INTERSOFTIC_OBRA_SOCIAL_ID", "8"))
SQL_TIPO_PRESTACION_ID = int(os.environ.get("INTERSOFTIC_TIPO_PRESTACION_ID", "0"))
SQL_OBRA_SOCIAL_DELEGACION_ID = int(os.environ.get("INTERSOFTIC_OBRA_SOCIAL_DELEGACION_ID", "0"))


class _PymssqlCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, *params):
        self._cursor.execute(query.replace("?", "%s"), params)
        return self

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def description(self):
        return self._cursor.description


class _PymssqlConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return _PymssqlCursor(self._connection.cursor())

    def close(self):
        self._connection.close()


def _split_sql_server(value):
    server = str(value or "").strip()
    if "," not in server:
        return server, None
    host, port = server.rsplit(",", 1)
    try:
        return host.strip(), int(port.strip())
    except ValueError:
        return server, None


def connect_intersoftic_sql():
    if not all([SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD]):
        raise RuntimeError("Falta configurar Intersoftic en .env: servidor, base, usuario y clave.")

    last_error = None

    if pyodbc is not None:
        conn_str = (
            "DRIVER={SQL Server};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={SQL_DATABASE};"
            f"UID={SQL_USER};"
            f"PWD={SQL_PASSWORD};"
            "TrustServerCertificate=yes;"
            "Connection Timeout=8;"
        )
        try:
            return pyodbc.connect(conn_str, timeout=8)
        except Exception as exc:
            last_error = exc

    if pymssql is not None:
        server, port = _split_sql_server(SQL_SERVER)
        kwargs = {
            "server": server,
            "user": SQL_USER,
            "password": SQL_PASSWORD,
            "database": SQL_DATABASE,
            "login_timeout": 8,
            "timeout": 30,
        }
        if port is not None:
            kwargs["port"] = port
        try:
            return _PymssqlConnection(pymssql.connect(**kwargs))
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise RuntimeError("Intersoftic SQL no está disponible en este host (ODBC no instalado y pymssql no disponible).")

STAT_CODES = {
    "mdta": ("123008",),
    "capita_250101": ("250101",),
    "capita_250102": ("250102",),
    "neuro": ("125001",),
    "to": ("123004",),
    "fono": ("123005",),
    "hd": ("140010",),
    "fisiatra": ("123001",),
    "domicilio": ("250121",),
    "traslado": ("990212", "990213"),
}

TRACKED_CODES = {code for codes in STAT_CODES.values() for code in codes}

BRANCHES = [
    {"id": "san_miguel", "name": "SAN MIGUEL", "sql_sucursal_id": 3},
    {"id": "ituzaingo", "name": "ITUZAINGO", "sql_sucursal_id": 2},
    {"id": "merlo", "name": "MERLO", "sql_sucursal_id": 1},
]

MONTH_NAMES = {
    "01": "ENERO",
    "02": "FEBRERO",
    "03": "MARZO",
    "04": "ABRIL",
    "05": "MAYO",
    "06": "JUNIO",
    "07": "JULIO",
    "08": "AGOSTO",
    "09": "SEPTIEMBRE",
    "10": "OCTUBRE",
    "11": "NOVIEMBRE",
    "12": "DICIEMBRE",
}


def load_manual_rows():
    if not os.path.exists(MANUAL_JSON):
        return {}

    with open(MANUAL_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    manual_rows = {}
    for month_name, values in data.items():
        normalized_month = str(month_name or "").strip().upper()
        manual_rows[normalized_month] = {
            "mdta": int(values.get("mdta") or 0),
            "capita_250101": int(values.get("capita_250101") or values.get("capita") or 0),
            "capita_250102": int(values.get("capita_250102") or 0),
            "neuro": int(values.get("neuro") or 0),
            "to": int(values.get("to") or 0),
            "fono": int(values.get("fono") or 0),
            "hd": int(values.get("hd") or 0),
            "fisiatra": int(values.get("fisiatra") or 0),
            "domicilio": int(values.get("domicilio") or 0),
            "traslado": int(values.get("traslado") or 0),
        }
    return manual_rows


def normalize_branch_id(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def load_manual_rows_for_branch(branch_cfg=None):
    branch_id = normalize_branch_id((branch_cfg or {}).get("id"))
    if os.path.exists(MANUAL_BY_BRANCH_JSON):
        with open(MANUAL_BY_BRANCH_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        branch_rows = data.get(branch_id) or {}
        if branch_rows:
            return {
                str(month_name or "").strip().upper(): {
                    "mdta": int(values.get("mdta") or 0),
                    "capita_250101": int(values.get("capita_250101") or values.get("capita") or 0),
                    "capita_250102": int(values.get("capita_250102") or 0),
                    "neuro": int(values.get("neuro") or 0),
                    "to": int(values.get("to") or 0),
                    "fono": int(values.get("fono") or 0),
                    "hd": int(values.get("hd") or 0),
                    "fisiatra": int(values.get("fisiatra") or 0),
                    "domicilio": int(values.get("domicilio") or 0),
                    "traslado": int(values.get("traslado") or 0),
                }
                for month_name, values in branch_rows.items()
            }
    if branch_id == "san_miguel":
        return load_manual_rows()
    return {}


def parse_export_rows(path):
    rows = []
    with open(path, "r", encoding="latin1", errors="ignore") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)
        for row in reader:
            if len(row) > 5 and row[0].count("/") == 2:
                rows.append(row)
    return rows


def normalize_practice_code(value) -> str:
    match = re.search(r"\d{6}", str(value or ""))
    return match.group(0) if match else str(value or "").strip()


def find_tracked_practice_code(row, preferred_value=None) -> str:
    preferred = normalize_practice_code(preferred_value)
    if preferred in TRACKED_CODES:
        return preferred
    for value in row:
        code = normalize_practice_code(value)
        if code in TRACKED_CODES:
            return code
    return preferred


def qty_for_codes(item, category: str) -> float:
    if not item:
        return 0.0
    return sum(item["qty_by_code"][code] for code in STAT_CODES[category])


def latest_file_per_month():
    month_files = {}
    export_paths = sorted(glob.glob(EXPORT_GLOB), key=lambda path: (os.path.getmtime(path), path))
    for path in export_paths:
        rows = parse_export_rows(path)
        if not rows:
            continue
        months = {row[0][3:10] for row in rows if len(row) > 3 and (row[3] or "").strip().upper() == TARGET_BRANCH}
        for month_key in months:
            month_files[month_key] = path
    return month_files


def build_stats():
    stats = defaultdict(
        lambda: {
            "qty_by_code": defaultdict(float),
            "other_codes": defaultdict(int),
        }
    )

    for month_key, path in sorted(latest_file_per_month().items()):
        for row in parse_export_rows(path):
            fecha, paciente, afiliado, sucursal, orden, code = row[:6]
            code = normalize_practice_code(code)
            if (sucursal or "").strip().upper() != TARGET_BRANCH:
                continue
            month = fecha[3:10]
            if month != month_key:
                continue
            qty_raw = row[7] if len(row) > 7 else "0"
            try:
                qty = float((qty_raw or "0").replace(",", "."))
            except ValueError:
                qty = 0.0

            if code in TRACKED_CODES:
                stats[month]["qty_by_code"][code] += qty
            else:
                stats[month]["other_codes"][code] += 1

    return stats


def build_live_sql_stats(sql_sucursal_id=None):
    stats = defaultdict(
        lambda: {
            "qty_by_code": defaultdict(float),
            "other_codes": defaultdict(int),
        }
    )

    conn = connect_intersoftic_sql()
    try:
        cursor = conn.cursor()
        for month_num in range(1, 13):
            month_key = f"{month_num:02d}/{TARGET_YEAR}"
            last_day = calendar.monthrange(int(TARGET_YEAR), month_num)[1]
            date_from = f"{TARGET_YEAR}-{month_num:02d}-01"
            date_to = f"{TARGET_YEAR}-{month_num:02d}-{last_day:02d}"
            last_exc = None
            for attempt in range(3):
                try:
                    rows = cursor.execute(
                        "EXEC dbo.spp_Efectores_AMB_Resumen ?, ?, ?, ?, ?, ?",
                        date_from,
                        date_to,
                        sql_sucursal_id if sql_sucursal_id is not None else 3,
                        SQL_OBRA_SOCIAL_ID,
                        SQL_TIPO_PRESTACION_ID,
                        SQL_OBRA_SOCIAL_DELEGACION_ID,
                    ).fetchall()
                    break
                except Exception as exc:
                    last_exc = exc
                    if "1205" not in str(exc) or attempt == 2:
                        raise
                    time.sleep(1.5 * (attempt + 1))
            else:
                raise last_exc

            for row in rows:
                code = find_tracked_practice_code(row, row[0])
                try:
                    qty = float(row[2] or 0)
                except (TypeError, ValueError):
                    qty = 0.0

                if code in TRACKED_CODES:
                    stats[month_key]["qty_by_code"][code] += qty
                elif code:
                    stats[month_key]["other_codes"][code] += 1
    finally:
        conn.close()

    return stats


def write_csv(stats):
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "MES",
                "COD_123008",
                "COD_250101",
                "COD_250102",
                "COD_125001",
                "COD_123005",
                "COD_140010",
                "COD_123001",
                "COD_250121",
                "COD_990212_990213",
                "OTROS",
                "TOTAL",
            ]
        )

        totals = {
            "123008": 0.0,
            "250101": 0.0,
            "250102": 0.0,
            "125001": 0.0,
            "123005": 0.0,
            "140010": 0.0,
            "123001": 0.0,
            "250121": 0.0,
            "990212_990213": 0.0,
            "otros": 0,
            "total": 0.0,
        }

        for month_num in [f"{n:02d}" for n in range(1, 13)]:
            month_key = f"{month_num}/{TARGET_YEAR}"
            item = stats.get(month_key)
            code_123008 = item["qty_by_code"]["123008"] if item else 0
            code_250101 = qty_for_codes(item, "capita_250101")
            code_250102 = qty_for_codes(item, "capita_250102")
            code_125001 = item["qty_by_code"]["125001"] if item else 0
            code_123005 = item["qty_by_code"]["123005"] if item else 0
            code_140010 = item["qty_by_code"]["140010"] if item else 0
            code_123001 = item["qty_by_code"]["123001"] if item else 0
            code_250121 = item["qty_by_code"]["250121"] if item else 0
            code_990 = qty_for_codes(item, "traslado")
            otros = sum(item["other_codes"].values()) if item else 0
            total = code_123008 + code_250101 + code_250102 + code_125001 + code_123005 + code_140010 + code_123001 + code_250121 + code_990 + otros

            writer.writerow(
                [
                    MONTH_NAMES[month_num],
                    int(code_123008),
                    int(code_250101),
                    int(code_250102),
                    int(code_125001),
                    int(code_123005),
                    int(code_140010),
                    int(code_123001),
                    int(code_250121),
                    int(code_990),
                    otros,
                    int(total),
                ]
            )

            totals["123008"] += code_123008
            totals["250101"] += code_250101
            totals["250102"] += code_250102
            totals["125001"] += code_125001
            totals["123005"] += code_123005
            totals["140010"] += code_140010
            totals["123001"] += code_123001
            totals["250121"] += code_250121
            totals["990212_990213"] += code_990
            totals["otros"] += otros
            totals["total"] += total

        writer.writerow(
            [
                "TOTAL",
                totals["123008"],
                totals["250101"],
                totals["250102"],
                totals["125001"],
                totals["123005"],
                totals["140010"],
                totals["123001"],
                totals["250121"],
                totals["990212_990213"],
                totals["otros"],
                totals["total"],
            ]
        )


def main():
    stats = build_stats()
    write_csv(stats)
    print(f"Archivo generado: {OUTPUT_CSV}")
    for month in sorted(stats.keys(), key=lambda s: (int(s[3:]), int(s[:2]))):
        item = stats[month]
        print(
            month,
            {
                "123008": item["qty_by_code"]["123008"],
                "250101_qty": item["qty_by_code"]["250101"],
                "250102_qty": item["qty_by_code"]["250102"],
                "250121": item["qty_by_code"]["250121"],
                "990212": item["qty_by_code"]["990212"],
                "990213": item["qty_by_code"]["990213"],
                "125001": item["qty_by_code"]["125001"],
                "123004": item["qty_by_code"]["123004"],
                "140010": item["qty_by_code"]["140010"],
                "123001": item["qty_by_code"]["123001"],
                "otros": dict(item["other_codes"]),
            },
        )


if __name__ == "__main__":
    main()


def _empty_totals():
    return {
        "mdta": 0,
        "capita_250101": 0,
        "capita_250102": 0,
        "neuro": 0,
        "to": 0,
        "fono": 0,
        "hd": 0,
        "fisiatra": 0,
        "domicilio": 0,
        "traslado": 0,
        "total": 0,
    }


def build_intersoftic_table_rows(branch=None):
    branch_cfg = branch or BRANCHES[0]
    source = "detalle_practica_sql_live"
    source_error = ""
    month_files = {}
    manual_rows = load_manual_rows_for_branch(branch_cfg)
    today = datetime.date.today()

    try:
        stats = build_live_sql_stats(branch_cfg["sql_sucursal_id"])
    except Exception as exc:
        source_error = str(exc)
        if branch_cfg["name"] == TARGET_BRANCH:
            source = "csv_fallback"
            stats = build_stats()
            month_files = latest_file_per_month()
        else:
            source = "excel_manual" if manual_rows else "sql_error"
            stats = defaultdict(
                lambda: {
                    "qty_by_code": defaultdict(float),
                    "other_codes": defaultdict(int),
                }
            )

    rows = []
    totals = _empty_totals()

    for month_num in [f"{n:02d}" for n in range(1, 13)]:
        month_key = f"{month_num}/{TARGET_YEAR}"
        month_name = MONTH_NAMES[month_num]
        item = stats.get(month_key)
        manual = None
        if manual_rows:
            manual = manual_rows.get(month_name)
        if manual is not None:
            row = {"mes": month_name, **manual, "source": "manual"}
        else:
            row = {
                "mes": month_name,
                "mdta": int(item["qty_by_code"]["123008"]) if item else 0,
                "capita_250101": int(qty_for_codes(item, "capita_250101")),
                "capita_250102": int(qty_for_codes(item, "capita_250102")),
                "neuro": int(item["qty_by_code"]["125001"]) if item else 0,
                "to": int(item["qty_by_code"]["123004"]) if item else 0,
                "fono": int(item["qty_by_code"]["123005"]) if item else 0,
                "hd": int(item["qty_by_code"]["140010"]) if item else 0,
                "fisiatra": int(item["qty_by_code"]["123001"]) if item else 0,
                "domicilio": int(item["qty_by_code"]["250121"]) if item else 0,
                "traslado": int(qty_for_codes(item, "traslado")),
                "source": "sql_live" if source == "detalle_practica_sql_live" else "csv",
            }
        row["total"] = (
            row["mdta"] + row["capita_250101"] + row["capita_250102"] + row["neuro"] + row["to"] +
            row["fono"] + row["hd"] + row["fisiatra"] + row["domicilio"] + row["traslado"]
        )
        rows.append(row)
        for key in totals:
            totals[key] += row[key]

    return {
        "branch": branch_cfg["name"],
        "branch_id": branch_cfg["id"],
        "sql_sucursal_id": branch_cfg["sql_sucursal_id"],
        "year": int(TARGET_YEAR),
        "source": source,
        "source_error": source_error,
        "manual_file": MANUAL_BY_BRANCH_JSON if manual_rows else "",
        "month_files": month_files,
        "rows": rows,
        "totals": totals,
        "generated_csv": OUTPUT_CSV,
    }


def build_intersoftic_all_branches():
    branches = [build_intersoftic_table_rows(branch_cfg) for branch_cfg in BRANCHES]
    grand_totals = _empty_totals()
    for branch in branches:
        for key in grand_totals:
            grand_totals[key] += int((branch.get("totals") or {}).get(key) or 0)

    return {
        "branch": "TODAS",
        "year": int(TARGET_YEAR),
        "source": "detalle_practica_sql_live",
        "branches": branches,
        "totals": grand_totals,
    }
