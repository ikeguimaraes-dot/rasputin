from __future__ import annotations

import logging
import threading
from uuid import uuid4

from auditoria.db import connect
from auditoria.service import ingest, run_analysis

logger = logging.getLogger(__name__)


def tick(settings):
    with connect(settings) as conn:
        row = conn.execute(
            "select * from jobs where (status='pendente' and run_after<=now()) "
            "or (status='executando' and locked_at<now()-interval '30 minutes') "
            "order by criado_em limit 1 for update skip locked"
        ).fetchone()
        if not row:
            return False
        ident, token = row["id"], uuid4()
        locked = conn.execute(
            "select pg_try_advisory_lock(hashtextextended(%s,0)) as ok", (str(ident),)
        ).fetchone()["ok"]
        if not locked:
            return False
        try:
            conn.execute(
                "update jobs set status='executando',locked_at=now(),lock_token=%s,"
                "tentativas=tentativas+1,atualizado_em=now() where id=%s",
                (token, ident),
            )
            conn.commit()
            try:
                handler = {"ingest_upload": ingest, "run_analysis": run_analysis}.get(row["tipo"])
                if not handler:
                    raise ValueError("Tipo de tarefa não suportado")
                handler(conn, settings, row)
                conn.execute(
                    "update jobs set status='concluido',erro=null,atualizado_em=now() "
                    "where id=%s and lock_token=%s",
                    (ident, token),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                # Não persistir stacktrace/URLs/chaves em mensagens de erro públicas.
                message = (
                    str(exc)[:500]
                    if isinstance(exc, ValueError)
                    else f"Falha no processamento ({type(exc).__name__}); consulte o operador."
                )
                terminal = row["tentativas"] + 1 >= settings.job_max_attempts or isinstance(
                    exc, ValueError
                )
                conn.execute(
                    "update jobs set status=%s,erro=%s,run_after=now()+interval '30 seconds',"
                    "atualizado_em=now() where id=%s and lock_token=%s",
                    ("erro" if terminal else "pendente", message, ident, token),
                )
                if terminal and row["tipo"] == "ingest_upload":
                    conn.execute(
                        "update uploads set status='erro',ingestion_report=%s::jsonb "
                        "where id=%s and organizacao_id=%s",
                        (
                            __import__("json").dumps({"errors": [message]}),
                            row["payload"]["upload_id"],
                            row["organizacao_id"],
                        ),
                    )
                if terminal and row["tipo"] == "run_analysis":
                    conn.execute(
                        "update analises set status='erro',erro=%s where "
                        "id=%s and organizacao_id=%s",
                        (message, row["payload"]["analysis_id"], row["organizacao_id"]),
                    )
                conn.commit()
                logger.warning("job_failed job=%s kind=%s", ident, type(exc).__name__)
        finally:
            conn.execute("select pg_advisory_unlock(hashtextextended(%s,0))", (str(ident),))
            conn.commit()
    return True


def consume(settings, stop: threading.Event):
    while not stop.is_set():
        try:
            worked = tick(settings)
        except Exception as exc:
            logger.warning("queue_unavailable kind=%s", type(exc).__name__)
            worked = False
        stop.wait(0.1 if worked else settings.poll_interval_seconds)
