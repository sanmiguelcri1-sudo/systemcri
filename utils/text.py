import re
import unicodedata
from typing import Optional

def strip_accents(text: str) -> str:
    """Remueve acentos y tildes de un texto."""
    if not text:
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))

def clean_text_keep_letters(text: str) -> str:
    """Limpia el texto manteniendo letras, números, espacios y puntuación básica.
    Remueve Variation Selectors y otros caracteres no imprimibles.
    """
    if text is None:
        return ""
    text = str(text).replace("\u00a0", " ")
    kept: list[str] = []
    for ch in text:
        code = ord(ch)
        if 0xFE00 <= code <= 0xFE0F:
            continue
        cat = unicodedata.category(ch)
        if not cat:
            continue
        if cat[0] in {"L", "M", "N", "Z", "P"}:
            kept.append(ch)
    cleaned = "".join(kept)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def normalize_text(value: Optional[str]) -> str:
    """Normaliza espacios: quita duplicados y recorta extremos."""
    return re.sub(r"\s+", " ", str(value or "")).strip()

def normalize_name(value: Optional[str]) -> str:
    """Normaliza texto y lo pasa a MAYÚSCULAS."""
    return normalize_text(value).upper()

def normalize_digits(value: Optional[str]) -> str:
    """Mantiene solo los dígitos de una cadena."""
    return re.sub(r"\D", "", str(value or ""))

def normalize_key(name: str) -> str:
    """Genera una clave única para comparación (ej: personal).
    Limpia texto, quita acentos, a mayúsculas y quita todo lo que no sea A-Z0-9.
    """
    cleaned = clean_text_keep_letters(name)
    cleaned = strip_accents(cleaned).upper()
    cleaned = re.sub(r"[^A-Z0-9]+", "", cleaned)
    return cleaned

def normalize_numeric_text(raw_value: str) -> str:
    """Maneja casos de notación científica de Excel o .0 redundantes."""
    value = (raw_value or "").strip()
    if not value:
        return ""
    compact = value.replace(" ", "")
    if re.fullmatch(r"\d+(?:\.\d+)?[Ee][+-]?\d+", compact):
        try:
            return str(int(float(compact)))
        except:
            return value
    if re.fullmatch(r"\d+\.0+", compact):
        try:
            return str(int(float(compact)))
        except:
            return value
    return value

def validate_utf8_text(value: Optional[str]) -> str:
    """Asegura que el valor sea texto Unicode válido en UTF-8."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    try:
        text = str(value)
        text.encode("utf-8")
        return text
    except Exception:
        return str(value).encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def is_blank(value: Optional[str]) -> bool:
    """Verifica si una cadena está vacía tras normalizarla."""
    return normalize_text(value) == ""
