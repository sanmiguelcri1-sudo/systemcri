import json
import os
import time

STATUS_FILE = "sync_status.json"

def set_status(progress: int, message: str, status: str = "running"):
    data = {
        "progress": progress,
        "message": message,
        "status": status,
        "last_update": time.time()
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def get_status():
    if not os.path.exists(STATUS_FILE):
        return {"progress": 0, "message": "Esperando...", "status": "idle"}
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"progress": 0, "message": "Error leyendo estado", "status": "error"}

def clear_status():
    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)
