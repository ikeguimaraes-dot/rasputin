from __future__ import annotations

import hashlib
from datetime import date
from uuid import uuid4

from psycopg.types.json import Jsonb

from auditoria.confirmed_report import publish
from auditoria.db import audit
from auditoria.domain import Document, Profile, Result, Rule, digest
from auditoria.engine import evaluate
from auditoria.ingestion.sheets import ingest_sheet
from auditoria.ingestion.xml import ingest_xml
from auditoria.official import document_catalog
from auditoria.reports import pdf_report, xlsx_report
from auditoria.storage import Storage


def enqueue(conn, org, user, kind, payload, key):
    return conn.execute(
        "insert into jobs(organizacao_id,criado_por,tipo,payload,dedupe_key) "
        "values(%s,%s,%s,%s,%s) on conflict(organizacao_id,dedupe_key) "
        "where dedupe_key is not null do update set dedupe_key=excluded.dedupe_key "
        "returning id",
        (org, user, kind, Jsonb(payload), key),
    ).fetchone()["id"]


def profile_data(row):
    return {k: row[k] for k in Profile.model_fields if k in row}


def persist_canonical(conn, upload, documents):
    for doc in documents:
        if doc.key:
            existing = conn.execute(
                "select id from documentos where cliente_id=%s and chave=%s",
                (upload["cliente_id"], doc.key),
            ).fetchone()
            if existing:
                continue  # Cada upload ainda preserva seu payload e sua própria proveniência.
        d = conn.execute(
            "insert into documentos(organizacao_id,cliente_id,upload_id,chave,modelo,"
            "serie,numero,data_emissao,dest_doc,dest_nome,dest_uf,dest_contribuinte,"
            "v_total,situacao) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "returning id",
            (
                upload["organizacao_id"],
                upload["cliente_id"],
                upload["id"],
                doc.key,
                doc.model,
                doc.series,
                doc.number,
                doc.issued,
                doc.recipient_doc,
                doc.recipient_name,
                doc.recipient_uf,
                doc.recipient_taxpayer,
                doc.total,
                doc.status,
            ),
        ).fetchone()["id"]
        for item in doc.items:
            i = conn.execute(
                "insert into itens(organizacao_id,documento_id,n_item,cod_produto,"
                "descricao,ncm,cest,cfop,unidade,quantidade,v_unit,v_prod,v_desc,"
                "v_frete,v_seg,v_outras) values(" + ",".join(["%s"] * 16) + ") returning id",
                (
                    upload["organizacao_id"],
                    d,
                    item.n_item,
                    item.code,
                    item.description,
                    item.ncm,
                    item.cest,
                    item.cfop,
                    item.unit,
                    item.quantity,
                    item.unit_value,
                    item.value,
                    item.discount,
                    item.freight,
                    item.insurance,
                    item.other,
                ),
            ).fetchone()["id"]
            conn.execute(
                "insert into itens_tributos(item_id,organizacao_id,icms_cst,icms_csosn,"
                "icms_bc,icms_aliq,icms_valor,icms_red_bc,st_bc,st_valor,"
                "pis_cst,pis_bc,pis_aliq,pis_valor,cofins_cst,cofins_bc,cofins_aliq,"
                "cofins_valor,ipi_cst,ipi_bc,ipi_aliq,ipi_valor,ibs_cbs) values("
                + ",".join(["%s"] * 23)
                + ")",
                (
                    i,
                    upload["organizacao_id"],
                    item.icms.cst,
                    item.icms.csosn,
                    item.icms.base,
                    item.icms.rate,
                    item.icms.value,
                    item.icms.reduction,
                    item.st.base,
                    item.st.value,
                    item.pis.cst,
                    item.pis.base,
                    item.pis.rate,
                    item.pis.value,
                    item.cofins.cst,
                    item.cofins.base,
                    item.cofins.rate,
                    item.cofins.value,
                    item.ipi.cst,
                    item.ipi.base,
                    item.ipi.rate,
                    item.ipi.value,
                    Jsonb(item.ibs_cbs),
                ),
            )
            conn.execute(
                "insert into origem_linha(item_id,organizacao_id,arquivo,linha,chave,n_item) "
                "values(%s,%s,%s,%s,%s,%s)",
                (
                    i,
                    upload["organizacao_id"],
                    item.source.get("file"),
                    item.source.get("line"),
                    doc.key,
                    item.n_item,
                ),
            )


def ingest(conn, settings, job):
    org, payload = job["organizacao_id"], job["payload"]
    upload = conn.execute(
        "select u.*,c.cnpj from uploads u join clientes c on c.id=u.cliente_id "
        "where u.id=%s and u.organizacao_id=%s for update",
        (payload["upload_id"], org),
    ).fetchone()
    if not upload:
        raise ValueError("Upload não pertence à organização da tarefa")
    if upload["status"] == "processado":
        return
    storage = Storage(settings)
    content = storage.get(settings.storage_bucket_uploads, upload["storage_path"])
    if hashlib.sha256(content).hexdigest() != upload["sha256"]:
        raise ValueError("Hash do arquivo divergente; ingestão interrompida")
    if upload["tipo"] in ("xml", "zip"):
        result = ingest_xml(content, upload["nome"], upload["cnpj"])
    else:
        mapping = upload["mapping_snapshot"] or {}
        result = ingest_sheet(
            content,
            upload["nome"],
            mapping.get("mapping", {}),
            mapping.get("sheet"),
            mapping.get("header_rows", 1),
        )
    if not result.documents:
        raise ValueError("Nenhum documento válido. " + str(result.errors[:3]))
    persist_canonical(conn, upload, result.documents)
    report = result.model_dump(mode="json", exclude={"documents"})
    dates = sorted({d.issued for d in result.documents})
    report.update(
        {
            "period_start": str(dates[0]),
            "period_end": str(dates[-1]),
            "dates_present": [str(d) for d in dates],
        }
    )
    conn.execute(
        "update uploads set status=%s,canonical_payload=%s,ingestion_report=%s,"
        "parcial=%s,parser_version=%s where id=%s and organizacao_id=%s",
        (
            "processado",
            Jsonb([d.model_dump(mode="json") for d in result.documents]),
            Jsonb(report),
            result.partial,
            result.parser_version,
            upload["id"],
            org,
        ),
    )
    audit(conn, org, job["criado_por"], "ingestao_concluida", "uploads", upload["id"], report)


def create_analysis(conn, org, user, client, upload_ids, start: date, end: date):
    uploads = conn.execute(
        "select * from uploads where id=any(%s::uuid[]) and organizacao_id=%s "
        "and cliente_id=%s order by criado_em,id",
        (upload_ids, org, client),
    ).fetchall()
    if len(uploads) != len(set(upload_ids)) or not uploads:
        raise ValueError("Selecione uploads do mesmo cliente e organização")
    if any(u["status"] != "processado" for u in uploads):
        raise ValueError("Aguarde a conclusão da ingestão de todos os uploads")
    profiles = [
        Profile(**profile_data(r)).model_dump(mode="json")
        for r in conn.execute(
            "select * from perfil_fiscal where cliente_id=%s and "
            "organizacao_id=%s order by valid_from",
            (client, org),
        ).fetchall()
    ]
    rules = [
        Rule(**r["definition"]).model_dump(mode="json")
        for r in conn.execute(
            "select definition from fiscal_rules where organizacao_id=%s "
            "and status='aprovada' order by id",
            (org,),
        ).fetchall()
    ]
    rules_hash = digest(rules)
    rule_set = conn.execute(
        "insert into rule_sets(organizacao_id,sha256,rules) values(%s,%s,%s) "
        "on conflict(organizacao_id,sha256) do nothing returning id",
        (org, rules_hash, Jsonb(rules)),
    ).fetchone()
    if not rule_set:
        rule_set = conn.execute(
            "select id from rule_sets where organizacao_id=%s and sha256=%s", (org, rules_hash)
        ).fetchone()
    docs, seen, notices = [], {}, []
    for u in uploads:
        for raw in u["canonical_payload"]:
            d = Document(**raw)
            if not start <= d.issued <= end:
                continue
            if d.key and d.key in seen:
                clean = d.model_dump(mode="json")
                for i in clean["items"]:
                    i["source"] = {}
                if digest(clean) != seen[d.key]:
                    raise ValueError(
                        "Mesma chave com conteúdo divergente entre uploads; selecione uma origem"
                    )
                notices.append("Nota duplicada deduplicada: " + d.key)
                continue
            clean = d.model_dump(mode="json")
            for i in clean["items"]:
                i["source"] = {}
            if d.key:
                seen[d.key] = digest(clean)
            docs.append(raw)
    if not docs:
        raise ValueError("Nenhum documento no período selecionado")
    customer = conn.execute(
        "select razao_social,cnpj from clientes where id=%s and organizacao_id=%s", (client, org)
    ).fetchone()
    branding = conn.execute("select branding from organizacoes where id=%s", (org,)).fetchone()[
        "branding"
    ]
    snapshot = {
        "customer": customer,
        "branding": branding,
        "documents": docs,
        "profiles": profiles,
        "uploads": [
            {
                "id": str(u["id"]),
                "name": u["nome"],
                "sha256": u["sha256"],
                "parser_version": u["parser_version"],
                "mapping": u["mapping_snapshot"],
                "ingestion_report": u["ingestion_report"],
            }
            for u in uploads
        ],
        "notices": notices,
        "official_catalog": document_catalog(docs),
    }
    row = conn.execute(
        "insert into analises(organizacao_id,cliente_id,periodo_ini,periodo_fim,"
        "rule_set_id,input_snapshot,input_hash,parcial,criado_por) "
        "values(%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id",
        (
            org,
            client,
            start,
            end,
            rule_set["id"],
            Jsonb(snapshot),
            digest(snapshot),
            any(u["parcial"] for u in uploads),
            user,
        ),
    ).fetchone()
    for u in uploads:
        conn.execute(
            "insert into analise_uploads(analise_id,upload_id,organizacao_id,cliente_id) "
            "values(%s,%s,%s,%s)",
            (row["id"], u["id"], org, client),
        )
    enqueue(
        conn,
        org,
        user,
        "run_analysis",
        {"analysis_id": str(row["id"])},
        "analysis:" + str(row["id"]),
    )
    audit(conn, org, user, "analise_solicitada", "analises", row["id"])
    return row


def run_analysis(conn, settings, job):
    org, ident = job["organizacao_id"], job["payload"]["analysis_id"]
    analysis = conn.execute(
        "select a.*,r.rules,c.razao_social,c.cnpj,o.branding from analises a "
        "join rule_sets r on r.id=a.rule_set_id "
        "join clientes c on c.id=a.cliente_id join organizacoes o on o.id=a.organizacao_id "
        "where a.id=%s and a.organizacao_id=%s for update of a",
        (ident, org),
    ).fetchone()
    if not analysis:
        raise ValueError("Análise não pertence à organização da tarefa")
    if analysis["status"] == "concluida":
        return
    snapshot = analysis["input_snapshot"]
    result = evaluate(
        [Document(**d) for d in snapshot["documents"]],
        [Profile(**p) for p in snapshot["profiles"]],
        [Rule(**r) for r in analysis["rules"]],
        snapshot.get("official_catalog"),
    )
    result = publish(result, snapshot)
    # Preserve ingestion limitations in every downloadable report, not only the upload screen.
    for upload in snapshot["uploads"]:
        report = upload.get("ingestion_report") or {}
        for warning in report.get("warnings", []):
            notice = f"{upload['name']}: {warning}"
            if notice not in result.summary["limitations"]:
                result.summary["limitations"].append(notice)
        if report.get("discarded"):
            result.summary["limitations"].append(
                f"{upload['name']}: {report['discarded']} linha(s) descartada(s); "
                "consulte o relatório de ingestão para localizar os dados incompletos."
            )
    partial = analysis["parcial"] or bool(result.skipped)
    context = {
        "Cliente": snapshot["customer"]["razao_social"],
        "CNPJ": snapshot["customer"]["cnpj"],
        "Período": f"{analysis['periodo_ini']} a {analysis['periodo_fim']}",
        "Análise": str(analysis["id"]),
        "Gerada em": str(analysis["criado_em"]),
        "Cobertura": "Parcial / limitada" if partial else "Checagens disponíveis executadas",
        "Arquivos": ", ".join(u["name"] for u in snapshot["uploads"]),
        "Versão da base": str(analysis["rule_set_id"]),
    }
    pdf, xlsx = pdf_report(result, context, snapshot["branding"]), xlsx_report(result, context)
    path = f"{org}/{analysis['cliente_id']}/{ident}"
    storage = Storage(settings)
    storage.put(settings.storage_bucket_reports, path + "/relatorio.pdf", pdf, "application/pdf")
    storage.put(
        settings.storage_bucket_reports,
        path + "/ocorrencias.xlsx",
        xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    for f in result.findings:
        conn.execute(
            "insert into findings(organizacao_id,analise_id,regra_codigo,severidade,"
            "direcao_impacto,impacto_brl,produto_cod,evidencia,correcao_sugerida,base_legal,"
            "fonte_url,rule_ref,fiscal_rule_id) values(" + ",".join(["%s"] * 13) + ")",
            (
                org,
                ident,
                f.code,
                f.severity,
                f.direction,
                f.impact,
                f.product,
                Jsonb(f.evidence),
                Jsonb(f.expected),
                f.legal_basis,
                f.source_url,
                Jsonb({"id": f.rule_id, "hash": f.id}),
                f.rule_id,
            ),
        )
    conn.execute(
        "insert into relatorios(organizacao_id,analise_id,pdf_path,xlsx_path) "
        "values(%s,%s,%s,%s) on conflict(analise_id) do update set "
        "pdf_path=excluded.pdf_path,xlsx_path=excluded.xlsx_path",
        (org, ident, path + "/relatorio.pdf", path + "/ocorrencias.xlsx"),
    )
    conn.execute(
        "update analises set "
        "result_payload=%s,resumo=%s,engine_version=%s,parcial=%s,report_context=%s,"
        "status='concluida',erro=null where id=%s and organizacao_id=%s",
        (
            Jsonb(result.model_dump(mode="json")),
            Jsonb(result.summary),
            result.engine_version,
            partial,
            Jsonb(context),
            ident,
            org,
        ),
    )
    audit(
        conn,
        org,
        job["criado_por"],
        "analise_concluida",
        "analises",
        ident,
        {"findings": len(result.findings)},
    )


def reissue(conn, settings, org, user, ident):
    row = conn.execute(
        "select a.*,c.razao_social,c.cnpj,o.branding from analises a "
        "join clientes c on c.id=a.cliente_id join organizacoes o on o.id=a.organizacao_id "
        "where a.id=%s and a.organizacao_id=%s and a.status='concluida'",
        (ident, org),
    ).fetchone()
    if not row:
        raise ValueError("Análise concluída não encontrada")
    result = publish(Result(**row["result_payload"]), row["input_snapshot"])
    # Reemissão usa findings preservados, nunca reavalia regras atuais.
    context = row["report_context"]
    storage = Storage(settings)
    path = f"{org}/{row['cliente_id']}/{ident}"
    storage.put(
        settings.storage_bucket_reports,
        path + "/relatorio.pdf",
        pdf_report(result, context, row["input_snapshot"]["branding"]),
        "application/pdf",
    )
    storage.put(
        settings.storage_bucket_reports,
        path + "/ocorrencias.xlsx",
        xlsx_report(result, context),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    audit(conn, org, user, "relatorio_reemitido", "analises", ident)


def new_rule(raw, org):
    raw = dict(raw)
    raw.update(id=str(uuid4()), status="proposta", approved_by=None, approved_at=None)
    return Rule(**raw)
