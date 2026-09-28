from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import httpx
from fastapi import Header, HTTPException, Request

from auditoria.db import connect


@dataclass
class Actor:
    user: str
    org: str
    role: str


def identity(
    request: Request,
    authorization: str = Header(default=""),
    x_organization_id: str | None = Header(default=None),
) -> Actor:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Entre na sua conta para continuar.")
    settings = request.app.state.settings
    try:
        response = httpx.get(
            settings.supabase_url.rstrip("/") + "/auth/v1/user",
            headers={"apikey": settings.supabase_service_role_key, "Authorization": authorization},
            timeout=10,
        )
        if response.status_code != 200:
            raise HTTPException(401, "Sessão inválida ou expirada.")
        user = str(UUID(response.json()["id"]))
        org = str(UUID(x_organization_id)) if x_organization_id else None
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Não foi possível validar a sessão.") from exc
    with connect(settings) as conn:
        rows = conn.execute(
            "select organizacao_id,papel from membros where user_id=%s order by criado_em", (user,)
        ).fetchall()
    if org:
        rows = [r for r in rows if str(r["organizacao_id"]) == org]
    if not rows:
        return Actor(user, "", "sem_organizacao")
    if len(rows) > 1 and not org:
        raise HTTPException(400, "Selecione a organização no cabeçalho X-Organization-Id.")
    return Actor(user, str(rows[0]["organizacao_id"]), rows[0]["papel"])


def require_org(actor: Actor, admin=False):
    if not actor.org:
        raise HTTPException(403, "Crie ou selecione uma organização.")
    if admin and actor.role != "admin":
        raise HTTPException(403, "Ação reservada ao administrador da organização.")
