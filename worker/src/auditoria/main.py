"""Ponto de entrada HTTP interno do worker (o loop da fila entra na M1)."""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Auditoria Fiscal - Worker", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return {"success": True, "data": {"status": "ok"}, "error": None}

    return app


app = create_app()
