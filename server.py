# -*- coding: utf-8 -*-
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

try:
    from runtime_paths import bundled_path, configure_exe_environment

    configure_exe_environment()
except Exception:
    def bundled_path(*parts):
        return Path(__file__).resolve().parent.joinpath(*parts)

import intersoftic_audit
import intersoftic_stats
import intersoftic_sessions

app = FastAPI(title="SYSTEMCRI Intersoftic", default_response_class=JSONResponse)
_CACHE = {}
_CACHE_SECONDS = int(os.environ.get("SYSTEMCRI_CACHE_SECONDS", "300"))


def _no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _cached(key, builder, force_refresh=False):
    now = time.time()
    item = _CACHE.get(key)
    if not force_refresh and item and now - item["created_at"] < _CACHE_SECONDS:
        return item["data"]

    data = builder()
    _CACHE[key] = {
        "created_at": now,
        "data": data,
    }
    return data


@app.get("/api/health")
def get_health():
    return {"status": "ok", "app": "SYSTEMCRI Intersoftic"}


@app.get("/api/intersoftic-stats")
def get_intersoftic_stats(response: Response, refresh: bool = False):
    try:
        _no_cache(response)
        return _cached("intersoftic_stats", intersoftic_stats.build_intersoftic_all_branches, refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/intersoftic-audit")
def get_intersoftic_audit(response: Response, refresh: bool = False):
    try:
        _no_cache(response)
        return _cached("intersoftic_audit", intersoftic_audit.build_audit_all_branches, refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/intersoftic-sessions")
def get_intersoftic_sessions(response: Response, refresh: bool = False):
    try:
        _no_cache(response)
        return _cached("intersoftic_sessions", intersoftic_sessions.build_sessions_all_branches, refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/feriados")
def get_feriados():
    try:
        return intersoftic_audit.get_feriados()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/feriados")
async def update_feriados(request: Request):
    try:
        data = await request.json()
        intersoftic_audit.save_feriados(data)
        _CACHE.pop("intersoftic_audit", None)
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

app.mount("/", StaticFiles(directory=str(bundled_path("static")), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8010"))
    uvicorn.run(app, host="127.0.0.1", port=port)
