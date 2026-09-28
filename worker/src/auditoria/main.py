"""API autenticada e consumidor da fila. /health testa processo; /ready testa banco."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from auditoria.api import router
from auditoria.assessment_api import router as assessment_router
from auditoria.config import Settings
from auditoria.db import connect
from auditoria.queue import consume


def create_app(settings: Settings | None = None, run_queue: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings or Settings.from_env()
        stop = threading.Event()
        thread = None
        if run_queue:
            thread = threading.Thread(target=consume, args=(app.state.settings, stop), daemon=True)
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=2)

    app = FastAPI(title="Auditoria Fiscal", docs_url=None, redoc_url=None, lifespan=lifespan)
    if settings:
        app.state.settings = settings
    import os

    origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins],
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id"],
    )
    app.include_router(router)
    app.include_router(assessment_router)

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)[:700]})

    @app.exception_handler(ValidationError)
    async def invalid_model(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422, content={"detail": "Dados inválidos: " + str(exc)[:700]}
        )

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Request, exc: psycopg.Error):
        logging.getLogger(__name__).warning("database_error kind=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Banco indisponível ou operação incompatível com os dados. "
                    "Confira configuração e vigências."
                )
            },
        )

    @app.get("/health")
    def health():
        return {"success": True, "data": {"status": "ok"}, "error": None}

    @app.get("/ready")
    def ready(request: Request):
        with connect(request.app.state.settings) as conn:
            conn.execute("select 1 from rule_sets limit 1")
        return {"ready": True}

    return app


app = create_app()
