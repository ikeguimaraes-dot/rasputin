from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from auditoria.config import Settings


def connect(settings: Settings):
    return psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=10)


def audit(conn, org, user, action, entity=None, ident=None, details=None):
    conn.execute(
        "insert into audit_log(organizacao_id,user_id,acao,entidade,entidade_id,detalhe) "
        "values(%s,%s,%s,%s,%s,%s)",
        (org, user, action, entity, str(ident) if ident else None, Jsonb(details or {})),
    )
