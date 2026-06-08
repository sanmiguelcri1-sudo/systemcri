import os
import socket
import sys
import time
import urllib.error
import urllib.request
from multiprocessing import freeze_support

import uvicorn

from runtime_paths import configure_exe_environment


def _ensure_stdio() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_server(host: str, port: int, timeout_seconds: int = 20) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _port_is_open(host, port):
            return True
        time.sleep(0.25)
    return False


def _is_systemcri_server(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _find_free_port(host: str, preferred_port: int) -> int:
    if not _port_is_open(host, preferred_port):
        return preferred_port
    for port in range(preferred_port + 1, preferred_port + 30):
        if not _port_is_open(host, port):
            return port
    raise RuntimeError("No hay puertos locales disponibles para iniciar SYSTEMCRI.")


def main() -> int:
    freeze_support()
    _ensure_stdio()
    configure_exe_environment()

    host = "127.0.0.1"
    requested_port = int(os.environ.get("PORT", "8010"))
    port = requested_port
    url = f"http://{host}:{port}/"

    if _port_is_open(host, port):
        if _is_systemcri_server(host, port):
            print(f"SYSTEMCRI ya esta iniciado en {url}")
            return 0
        port = _find_free_port(host, requested_port)
        os.environ["PORT"] = str(port)
        url = f"http://{host}:{port}/"
        print(f"El puerto {requested_port} esta ocupado. Usando {port}.")

    print("Iniciando SYSTEMCRI local...")
    print(f"SYSTEMCRI queda disponible solo en esta maquina: {url}")
    print("Abriendo ventana local de SYSTEMCRI.")

    import server

    config = uvicorn.Config(
        server.app,
        host=host,
        port=port,
        log_level=os.environ.get("SYSTEMCRI_LOG_LEVEL", "info"),
        log_config=None,
        access_log=False,
    )
    uvicorn_server = uvicorn.Server(config)

    import threading

    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()

    if not _wait_for_server(host, port):
        print("No se pudo iniciar el servidor local. Revise la configuracion y vuelva a intentar.")
        return 1

    print("SYSTEMCRI iniciado correctamente.")

    try:
        try:
            import webview

            webview.create_window(
                "SYSTEMCRI",
                url,
                width=1280,
                height=820,
                min_size=(1024, 680),
            )
            webview.start()
            uvicorn_server.should_exit = True
        except Exception as exc:
            print("No se pudo abrir la ventana local de SYSTEMCRI.")
            print(f"Detalle: {exc}")
            print(f"Puede abrir manualmente esta direccion local: {url}")
            while thread.is_alive():
                time.sleep(0.5)
    except KeyboardInterrupt:
        uvicorn_server.should_exit = True

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
