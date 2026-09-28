"""Relatórios determinísticos; textos não dependem de IA."""

from __future__ import annotations

import html
import re
from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from auditoria.domain import Result, digest

FOOTER = "Relatório de conferência. Não substitui a validação do contador responsável."


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def xlsx_report(result: Result, context: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    for key, val in context.items():
        ws.append([key, safe_cell(str(val))])
    ws.append(["Motor", result.engine_version])
    ws.append(["Hash das entradas", result.input_hash])
    ws.append(["Hash das regras", result.rules_hash])
    ws.append(["Limitação", result.summary["impact_notice"]])
    ws.append(["Rodapé", FOOTER])
    ws = wb.create_sheet("Ocorrências")
    ws.append(
        [
            "Regra",
            "Severidade",
            "Produto",
            "Descrição",
            "Nota",
            "Data",
            "Item",
            "Arquivo",
            "Aba",
            "Linha",
            "Problema",
            "Como está",
            "Como deveria estar",
            "Impacto potencial R$",
            "Direção potencial",
            "Base legal",
            "Fonte",
            "ID regra",
            "ID apontamento",
            "NCM",
            "CFOP",
            "CEST",
            "ICMS CST",
            "ICMS CSOSN",
            "ICMS base",
            "ICMS alíquota %",
            "ICMS valor",
            "PIS CST",
            "PIS base",
            "PIS alíquota %",
            "PIS valor",
            "COFINS CST",
            "COFINS base",
            "COFINS alíquota %",
            "COFINS valor",
        ]
    )
    for f in result.findings:
        for ev in f.evidence:
            item, source = ev["item"], ev["item"]["source"]
            row = [
                f.code,
                f.severity,
                f.product,
                f.description,
                ev["document"],
                ev["issued"],
                item["n_item"],
                source.get("file"),
                source.get("sheet"),
                source.get("line"),
                f.message,
                str({k: item.get(k) for k in ("ncm", "cfop", "cest", "icms", "pis", "cofins")}),
                str(f.expected),
                float(f.impact) if f.impact is not None else None,
                f.direction,
                f.legal_basis,
                f.source_url,
                f.rule_id,
                f.id,
                item["ncm"],
                item["cfop"],
                item["cest"],
                item["icms"]["cst"],
                item["icms"]["csosn"],
                *[
                    float(item[t][field]) if item[t][field] is not None else None
                    for t in ("icms",)
                    for field in ("base", "rate", "value")
                ],
                item["pis"]["cst"],
                *[
                    float(item["pis"][field]) if item["pis"][field] is not None else None
                    for field in ("base", "rate", "value")
                ],
                item["cofins"]["cst"],
                *[
                    float(item["cofins"][field]) if item["cofins"][field] is not None else None
                    for field in ("base", "rate", "value")
                ],
            ]
            ws.append([safe_cell(v) for v in row])
    ws = wb.create_sheet("Não avaliadas")
    ws.append(["Regra", "Documento", "Origem", "Motivo"])
    for skip in result.skipped:
        ws.append(
            [safe_cell(str(skip.get(k, ""))) for k in ("code", "document", "source", "reason")]
        )
    for sheet in wb:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="173D35")
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                65, max(15, max(len(str(c.value or "")) for c in list(column)[:100]) + 2)
            )
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def html_report(result: Result, context: dict, branding: dict | None = None) -> str:
    def e(v):
        return html.escape(str(v if v is not None else "—"))

    branding = branding or {}
    color = branding.get("cor", "#173D35")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = "#173D35"
    logo = branding.get("logo_data_url") or ""
    logo_html = (
        f'<img alt="Logo do escritório" src="{e(logo)}" style="max-width:160px;max-height:70px">'
        if logo.startswith(("data:image/png;base64,", "data:image/jpeg;base64,"))
        else ""
    )
    groups = defaultdict(list)
    for f in result.findings:
        groups[f.product].append(f)
    sections = []
    for product, rows in sorted(groups.items()):
        lines = []
        consolidated = defaultdict(list)
        for finding in rows:
            it = finding.evidence[0]["item"]
            key = digest(
                {
                    "code": finding.code,
                    "message": finding.message,
                    "expected": finding.expected,
                    "current": {
                        **{k: it.get(k) for k in ("ncm", "cfop", "cest")},
                        **{
                            tax: {k: it[tax].get(k) for k in ("cst", "csosn", "rate")}
                            for tax in ("icms", "pis", "cofins")
                        },
                    },
                }
            )
            consolidated[key].append(finding)
        for grouped in consolidated.values():
            f = grouped[0]
            ev = f.evidence[0]
            item = ev["item"]
            lines.append(
                f"<tr><td>{e(f.code)}<br>{e(f.severity)}</td><td>{e(f.message)}"
                f"<br><small>{len(grouped)} ocorrência(s). Exemplo: nota {e(ev['document'])} · item {e(item['n_item'])}</small></td>"
                f"<td>NCM {e(item['ncm'])}<br>CFOP {e(item['cfop'])}<br>"
                f"ICMS CST {e(item['icms']['cst'])} / CSOSN {e(item['icms']['csosn'])}<br>"
                f"PIS CST {e(item['pis']['cst'])} · COFINS CST {e(item['cofins']['cst'])}<br>"
                f"CEST {e(item['cest'])} · ICMS {e(item['icms']['rate'])}%"
                f"</td><td>{e(f.expected or 'Revisão do contador')}</td></tr>"
            )
        legal = sorted({f"{f.legal_basis} | {f.source_url or ''}" for f in rows})
        sections.append(
            f"<section><h2>{e(rows[0].description)} <small>({e(product)})</small></h2>"
            f"<p>{len(rows)} apontamentos. Ocorrências detalhadas no anexo XLSX.</p>"
            "<table><thead><tr><th>Regra</th><th>Apontamento</th><th>Como está</th>"
            "<th>Revisão sugerida</th></tr></thead><tbody>"
            + "".join(lines)
            + "</tbody></table>"
            + "".join(f'<p class="legal">{e(legal_text)}</p>' for legal_text in legal)
            + "</section>"
        )
    cover = "".join(f"<p><strong>{e(k)}:</strong> {e(v)}</p>" for k, v in context.items())
    top = CounterCodes(result)
    potential = result.summary["potential_impact"]
    impacts_text = (
        f"Possível excesso documental: R$ {potential['pago_a_mais']}; "
        f"possível insuficiência documental: R$ {potential['pago_a_menos']}"
    )
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><style>
    @page {{size:A4; margin:18mm; @bottom-center {{content:"{FOOTER}";font-size:8pt}}}}
    body{{font:10pt sans-serif;color:{color}}} h1{{font-size:30pt}} h2{{font-size:15pt}}
    table{{border-collapse:collapse;width:100%;font-size:8pt}}td,th{{padding:7px;border-bottom:1px solid #ddd;text-align:left}}
    th{{background:#edf4f0}}section{{margin-top:24px}}.cover{{page-break-after:always}}.legal,small{{font-size:8pt;color:#53685f}}
    .warning{{background:#fff0d4;padding:12px}}p{{overflow-wrap:anywhere}}tr{{break-inside:avoid}}
    </style><body><div class="cover">{logo_html}<p>{e(branding.get("nome", "AUDITORIA FISCAL"))}</p>
    <h1>Conferência fiscal</h1>{cover}<p>Motor: {e(result.engine_version)}</p>
    <p class="legal">Entradas: {result.input_hash}<br>Base: {result.rules_hash}</p>
    <div class="warning">{e(result.summary["impact_notice"])}<br>
    A análise é limitada aos documentos e regras disponíveis. Checagens não avaliadas: {len(result.skipped)}.</div>
    <h2>Resumo executivo</h2><p>{len(result.findings)} apontamentos · {len(groups)} produtos</p>
    <p>Por severidade: {e(result.summary["severity"])}</p><p>Principais ocorrências: {e(top)}</p>
    <p>Impactos potenciais: {e(impacts_text)}</p>
    {"".join(f"<p>{e(x)}</p>" for x in result.summary["limitations"])}</div>
    {"".join(sections) or "<h2>Nenhuma divergência identificada nas checagens executadas.</h2>"}
    <p>{e(branding.get("rodape", ""))}</p></body></html>'''


def CounterCodes(result):
    from collections import Counter

    return ", ".join(
        f"{k}: {v}" for k, v in Counter(f.code for f in result.findings).most_common(5)
    )


def pdf_report(result: Result, context: dict, branding: dict | None = None) -> bytes:
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    # Somente imagens PNG/JPEG embutidas e validadas pelo contrato de branding.
    # Bloqueia http(s), file, FTP e redirecionamentos para recursos externos.
    fetcher = URLFetcher(allowed_protocols={"data"}, allow_redirects=False, fail_on_errors=True)
    return HTML(string=html_report(result, context, branding), url_fetcher=fetcher).write_pdf()
