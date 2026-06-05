from datetime import datetime
from typing import Optional

def normalize_date_es(d_str: Optional[str]) -> str:
    """Parsea fechas en formato D/M/YYYY o D/M/YY a YYYY-MM-DD."""
    if not d_str or not str(d_str).strip():
        return ""
    d_str = str(d_str).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(d_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""

def format_date_to_es(iso_date: Optional[str]) -> str:
    """Convierte YYYY-MM-DD a DD/MM/YYYY."""
    if not iso_date:
        return ""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date
