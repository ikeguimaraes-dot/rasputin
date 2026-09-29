"""Company-scoped, append-only product and service classifications."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from auditoria.auth import Actor, identity, require_org
from auditoria.db import audit, connect
from auditoria.domain import Model, digest

router = APIRouter(prefix="/api/product-catalog")


class ProductDefinition(Model):
    code: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=2, max_length=500)
    kind: Literal["produto", "servico"] = "produto"
    ncm: str | None = Field(default=None, pattern=r"^\d{8}$")
    cest: str | None = Field(default=None, pattern=r"^\d{7}$")
    service_code: str | None = Field(default=None, max_length=40)
    municipality: str | None = Field(default=None, pattern=r"^\d{7}$")
    status: Literal["proposta", "validada", "inativa"] = "proposta"
    valid_from: date
    valid_to: date | None = None
    basis: str = Field(default="", max_length=3000)
    source_url: str | None = Field(default=None, pattern=r"^https://", max_length=1000)

    @model_validator(mode="after")
    def check_definition(self):
        self.code = self.code.strip()
        self.description = self.description.strip()
        if not self.code or len(self.description) < 2:
            raise ValueError("Informe código e descrição")
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Vigência final anterior à inicial")
        if self.status == "validada":
            if len(self.basis.strip()) < 10:
                raise ValueError("Registre o fundamento da classificação validada")
            if self.kind == "produto" and not self.ncm:
                raise ValueError("Informe o NCM do produto validado")
            if self.kind == "servico" and (not self.service_code or not self.municipality):
                raise ValueError("Informe código do serviço e município IBGE")
        return self


class ProductInput(Model):
    client_id: UUID
    definition: ProductDefinition


def owned(conn, actor, client):
    if not conn.execute(
        "select id from clientes where id=%s and organizacao_id=%s", (client, actor.org)
    ).fetchone():
        raise HTTPException(404, "Cliente não encontrado")


@router.get("")
def list_products(request: Request, client_id: UUID, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        owned(conn, actor, client_id)
        return conn.execute(
            "select distinct on(code) * from product_catalog_versions "
            "where organizacao_id=%s and cliente_id=%s order by code,criado_em desc,id desc",
            (actor.org, client_id),
        ).fetchall()


@router.get("/history")
def history(request: Request, client_id: UUID, code: str, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        owned(conn, actor, client_id)
        return conn.execute(
            "select * from product_catalog_versions where organizacao_id=%s and cliente_id=%s "
            "and code=%s order by criado_em desc,id desc",
            (actor.org, client_id, code),
        ).fetchall()


@router.post("")
def save(body: ProductInput, request: Request, actor: Actor = Depends(identity)):
    require_org(actor, admin=True)
    definition = body.definition.model_dump(mode="json")
    with connect(request.app.state.settings) as conn:
        owned(conn, actor, body.client_id)
        # Always append, including a deliberate return to an older classification.
        # A retry of the current version remains idempotent.
        conn.execute(
            "select pg_advisory_xact_lock(hashtext(%s))",
            (f"{actor.org}:{body.client_id}:{body.definition.code}",),
        )
        prior = conn.execute(
            "select * from product_catalog_versions where organizacao_id=%s and cliente_id=%s "
            "and code=%s order by criado_em desc,id desc limit 1",
            (actor.org, body.client_id, body.definition.code),
        ).fetchone()
        if prior and prior["definition"] == definition:
            return prior
        sha = digest({"definition": definition, "previous": str(prior["id"]) if prior else None})
        row = conn.execute(
            "insert into product_catalog_versions"
            "(organizacao_id,cliente_id,code,definition,sha256,criado_por) "
            "values(%s,%s,%s,%s,%s,%s) returning *",
            (actor.org, body.client_id, body.definition.code, Jsonb(definition), sha, actor.user),
        ).fetchone()
        audit(
            conn,
            actor.org,
            actor.user,
            "classificacao_produto_registrada",
            "product_catalog_versions",
            row["id"],
            {"status": body.definition.status},
        )
        return row


@router.get("/observed")
def observed(request: Request, client_id: UUID, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        owned(conn, actor, client_id)
        rows = conn.execute(
            "select canonical_payload from uploads where organizacao_id=%s and cliente_id=%s "
            "and status='processado' order by criado_em",
            (actor.org, client_id),
        ).fetchall()
    products = {}
    for row in rows:
        for doc in row["canonical_payload"] or []:
            for item in doc.get("items", []):
                key = (item.get("code"), item.get("description"), item.get("ncm"), item.get("cest"))
                products.setdefault(key, set())
                if item.get("cfop"):
                    products[key].add(item["cfop"])
    return [
        {"code": k[0], "description": k[1], "ncm": k[2], "cest": k[3], "cfops": sorted(v)}
        for k, v in products.items()
    ]
