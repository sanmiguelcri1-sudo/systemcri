# -*- coding: utf-8 -*-
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
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


app = FastAPI(title="SYSTEMCRI Intersoftic", default_response_class=JSONResponse)


def _no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


@app.get("/api/health")
def get_health():
    return {"status": "ok", "app": "SYSTEMCRI Intersoftic"}


@app.get("/api/intersoftic-stats")
def get_intersoftic_stats(response: Response):
    try:
        _no_cache(response)
        return intersoftic_stats.build_intersoftic_all_branches()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/intersoftic-audit")
def get_intersoftic_audit(response: Response):
    try:
        _no_cache(response)
        return intersoftic_audit.build_audit_all_branches()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


app.mount("/", StaticFiles(directory=str(bundled_path("static")), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8010"))
    uvicorn.run(app, host="127.0.0.1", port=port)
