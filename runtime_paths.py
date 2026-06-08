import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return Path(__file__).resolve().parent


def external_path(*parts: str) -> Path:
    return app_dir().joinpath(*parts)


def bundled_path(*parts: str) -> Path:
    return bundled_dir().joinpath(*parts)


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    env_path = external_path(".env")
    if env_path.exists():
        load_dotenv(env_path, override=False)


def configure_exe_environment() -> None:
    load_local_env()
    if not is_frozen():
        os.environ.setdefault("SQLITE_DB_PATH", str(external_path("hc_archive.db")))
