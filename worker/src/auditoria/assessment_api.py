from __future__ import annotations

from calendar import monthrange
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from auditoria.assessment import MODULES, calculate, catalog
from auditoria.assessment_documents import consolidate, period_bounds
from auditoria.auth import Actor, identity, require_org
from auditoria.db import audit, connect
from auditoria.domain import Model, Profile, digest
from auditoria.service import profile_data
from auditoria.storage import Storage

router = APIRouter(prefix="/api")


class AssessmentInput(Model):
    client_id: UUID
    module: str = Field(max_length=40)
    period: date
    values: dict = Field(default_factory=dict, max_length=80)
    upload_ids: list[UUID] = Field(default_factory=list, max_length=200)
    evidence_hash: str | None = Field(default=None, max_length=64)
    documents_complete: bool = False
    draft: bool = False


def document_evidence(conn, actor, body, profile):
    rows = conn.execute(
        "select id,nome,sha256,parcial,status,canonical_payload from uploads "
        "where organizacao_id=%s and cliente_id=%s and id=any(%s::uuid[]) order by id",
        (actor.org, body.client_id, body.upload_ids),
    ).fetchall()
    if not rows or len(rows) != len(set(body.upload_ids)):
        raise ValueError("Selecione arquivos deste cliente e organização")
    if any(r["status"] != "processado" for r in rows):
        raise ValueError("Aguarde o processamento dos arquivos")
    return consolidate(rows, body.module, body.period, profile)


@router.post("/assessments/documents")
def documents(body: AssessmentInput, request: Request, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        owned = conn.execute(
            "select id from clientes where id=%s and organizacao_id=%s",
            (body.client_id, actor.org),
        ).fetchone()
        if not owned:
            raise HTTPException(404, "Cliente não encontrado")
        start, end = period_bounds(body.module, body.period)
        profiles = conn.execute(
            "select * from perfil_fiscal where cliente_id=%s and organizacao_id=%s "
            "and valid_from<=%s and (valid_to is null or valid_to>=%s)",
            (body.client_id, actor.org, start, end),
        ).fetchall()
        profile = Profile(**profile_data(profiles[0])) if len(profiles) == 1 else None
        evidence = document_evidence(conn, actor, body, profile)
        if profile is None:
            evidence["warnings"].append(
                "Cadastre um perfil válido durante todo o período para calcular bases."
            )
        return evidence


@router.get("/fiscal-catalog")
def fiscal_catalog(actor: Actor = Depends(identity)):
    require_org(actor)
    return catalog()


def prepare(conn, actor, body):
    if body.module not in MODULES:
        raise ValueError("Módulo desconhecido")
    client = conn.execute(
        "select id,cnpj,razao_social from clientes where id=%s and organizacao_id=%s",
        (body.client_id, actor.org),
    ).fetchone()
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    start = body.period
    if MODULES[body.module]["period"] == "trimestral":
        start = start.replace(month=((start.month - 1) // 3) * 3 + 1)
    elif MODULES[body.module]["period"] == "anual_acumulado":
        start = start.replace(month=1)
    end = body.period.replace(day=monthrange(body.period.year, body.period.month)[1])
    rows = conn.execute(
        "select * from perfil_fiscal where cliente_id=%s and organizacao_id=%s "
        "and valid_from<=%s and (valid_to is null or valid_to>=%s)",
        (body.client_id, actor.org, start, end),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("Cadastre um perfil fiscal vigente durante todo o período da apuração")
    profile = Profile(**profile_data(rows[0]))
    result = calculate(body.module, body.period, body.values, profile)
    evidence = None
    if body.upload_ids:
        evidence = document_evidence(conn, actor, body, profile)
        if body.evidence_hash != evidence["hash"]:
            raise ValueError("Os documentos ou o perfil mudaram. Consolide os arquivos novamente.")
        result["memory"]["documents"] = evidence
        result["warnings"].extend(evidence["warnings"])
        blockers = list(evidence["blockers"])
        if not body.documents_complete:
            blockers.append(
                "Confirme que as fontes cobrem todo o período e que as bases foram conciliadas."
            )
        if blockers:
            result["status"] = "incompleta"
            result["missing"].extend({"field": "documentos", "label": b} for b in blockers)
            result.pop("total_due", None)
            result["lines"] = []
        result.setdefault("notice", "Consolidação documental vinculada à versão salva.")
    snapshot = {
        **body.model_dump(mode="json"),
        "client": {k: str(v) for k, v in client.items()},
        "profile": profile.model_dump(mode="json"),
    }
    if evidence:
        snapshot["document_evidence"] = evidence
    return snapshot, result


@router.post("/assessments/preview")
def preview(body: AssessmentInput, request: Request, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        _, result = prepare(conn, actor, body)
    return result


@router.post("/assessments")
def save(body: AssessmentInput, request: Request, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        snapshot, result = prepare(conn, actor, body)
        if result["status"] != "calculada" and not body.draft:
            raise HTTPException(422, "Preencha os dados indicados antes de salvar a apuração")
        if body.draft:
            result["status"] = "rascunho"
            result["notice"] = (
                "Prévia de trabalho. Não representa fechamento nem autorização de recolhimento."
            )
        rules = catalog()
        sha = digest({"input": snapshot, "catalog": rules, "result": result})
        row = conn.execute(
            "insert into fiscal_assessments(organizacao_id,cliente_id,module,period,"
            "input_snapshot,catalog_snapshot,result_payload,sha256,criado_por) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(organizacao_id,sha256) "
            "do nothing returning *",
            (
                actor.org,
                body.client_id,
                body.module,
                body.period,
                Jsonb(snapshot),
                Jsonb(rules),
                Jsonb(result),
                sha,
                actor.user,
            ),
        ).fetchone()
        if not row:
            row = conn.execute(
                "select * from fiscal_assessments where organizacao_id=%s and sha256=%s",
                (actor.org, sha),
            ).fetchone()
        audit(conn, actor.org, actor.user, "apuracao_salva", "fiscal_assessments", row["id"])
    return row


@router.get("/assessments")
def history(request: Request, client_id: UUID, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        return conn.execute(
            "select id,module,period,sha256,result_payload,criado_em from fiscal_assessments "
            "where organizacao_id=%s and cliente_id=%s order by criado_em desc limit 100",
            (actor.org, client_id),
        ).fetchall()


@router.get("/assessments/{ident}")
def detail(ident: UUID, request: Request, actor: Actor = Depends(identity)):
    require_org(actor)
    with connect(request.app.state.settings) as conn:
        row = conn.execute(
            "select * from fiscal_assessments where id=%s and organizacao_id=%s", (ident, actor.org)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Apuração não encontrada")
    return row


@router.get("/assessments/{ident}/download/{kind}")
def download(ident: UUID, kind: str, request: Request, actor: Actor = Depends(identity)):
    from auditoria.assessment_reports import export

    if kind not in ("pdf", "xlsx"):
        raise HTTPException(404, "Formato não encontrado")
    row = detail(ident, request, actor)
    content, mime = export(row, kind)
    settings = request.app.state.settings
    storage = Storage(settings)
    path = f"{actor.org}/{row['cliente_id']}/apuracoes/{ident}/{row['sha256']}.{kind}"
    storage.put(settings.storage_bucket_reports, path, content, mime)
    url = storage.sign(settings.storage_bucket_reports, path)
    with connect(settings) as conn:
        audit(
            conn,
            actor.org,
            actor.user,
            "download_apuracao",
            "fiscal_assessments",
            ident,
            {"format": kind},
        )
    return {"url": url, "expires_in": 120}
