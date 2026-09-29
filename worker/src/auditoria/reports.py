"""Relatórios determinísticos; textos não dependem de IA."""

from __future__ import annotations

import html
import re
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from auditoria.confirmed_report import brl, example, publish
from auditoria.domain import Result

FOOTER = "Relatório de conferência. Não substitui a validação do contador responsável."


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def xlsx_report(result: Result, context: dict) -> bytes:
    result = publish(result)
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
    base = result.summary.get("base_review")
    if base:
        ws.append(["Linhas sem descontar o ICMS da base", base["missing_icms"]])
        ws.append(["Linhas com outra divergência na composição da base", base["other_difference"]])
        ws.append(["Linhas compatíveis com a fórmula", base["compatible"]])
        if base["rows"]:
            ws.append(["Exemplo", safe_cell(example(base["rows"][0]))])
        ws = wb.create_sheet("Bases PIS COFINS")
        ws.append(
            [
                "Nota",
                "Linha",
                "Produto",
                "CFOP",
                "Resultado",
                "Valor da operação R$",
                "ICMS R$",
                "Base esperada R$",
                "Base PIS R$",
                "Base COFINS R$",
                "CST PIS",
                "CST COFINS",
                "Arquivo",
                "Aba",
            ]
        )
        for row in base["rows"]:
            ws.append(
                [
                    safe_cell(row["document"]),
                    row["source"].get("line"),
                    safe_cell(row["description"]),
                    row["cfop"],
                    "ICMS não descontado"
                    if row["kind"] == "missing_icms"
                    else "Outra divergência de composição",
                ]
                + [
                    float(row[k]) if row[k] is not None else None
                    for k in ("operation_value", "icms", "expected_base", "pis_base", "cofins_base")
                ]
                + [
                    row["pis_cst"],
                    row["cofins_cst"],
                    safe_cell(row["source"].get("file")),
                    safe_cell(row["source"].get("sheet")),
                ]
            )
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
        if base and f.code == "C09":
            continue
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
    ws = wb.create_sheet("Por CFOP e categoria")
    ws.append(
        [
            "CFOP",
            "Natureza",
            "Categoria declarada",
            "ICMS alíquota %",
            "Itens",
            "Valor dos itens R$",
            "ICMS informado R$",
        ]
    )
    for row in result.summary.get("operations", []):
        ws.append(
            [safe_cell(row.get(k)) for k in ("cfop", "nature", "category")]
            + [
                float(row["icms_rate"]) if row["icms_rate"] is not None else None,
                row["items"],
                float(row["value"]) if row["value"] is not None else None,
                float(row["icms_value"]) if row["icms_value"] is not None else None,
            ]
        )
    ws = wb.create_sheet("Itens conferidos")
    keys = (
        "document",
        "issued",
        "code",
        "description",
        "ncm",
        "cfop",
        "nature",
        "category",
        "icms_cst",
        "pis_cst",
        "cofins_cst",
        "icms_rate",
        "value",
        "icms_value",
    )
    ws.append(
        [
            "Nota",
            "Data",
            "Código",
            "Descrição",
            "NCM",
            "CFOP",
            "Natureza",
            "Categoria declarada",
            "CST ICMS",
            "CST PIS",
            "CST COFINS",
            "ICMS alíquota %",
            "Valor do item R$",
            "ICMS informado R$",
            "Arquivo",
            "Aba",
            "Linha",
        ]
    )
    for row in result.summary.get("review_rows", []):
        ws.append(
            [
                safe_cell(row.get(k))
                if k not in ("icms_rate", "value", "icms_value")
                else (float(row[k]) if row.get(k) is not None else None)
                for k in keys
            ]
            + [safe_cell(row["source"].get(k)) for k in ("file", "sheet", "line")]
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
    result = publish(result)

    def e(v):
        return html.escape(str(v if v is not None else "—"))

    branding = branding or {}
    color = branding.get("cor", "#173D35")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = "#173D35"
    logo = branding.get("logo_data_url") or ""
    logo_html = (
        f'<img alt="Logo" src="{e(logo)}" style="max-width:160px;max-height:70px">'
        if logo.startswith(("data:image/png;base64,", "data:image/jpeg;base64,"))
        else ""
    )
    cover = "".join(f"<p><strong>{e(k)}:</strong> {e(v)}</p>" for k, v in context.items())
    base = result.summary.get("base_review")
    sections = []
    if base:
        sections.append(
            f"<h2>Base de PIS e COFINS — CST 01 e 02</h2><ul><li>{base['missing_icms']} linhas sem descontar o ICMS da base.</li><li>{base['other_difference']} linha(s) com outra divergência na composição da base.</li><li>{base['compatible']} linhas compatíveis com a fórmula.</li></ul>"
        )
        sections.append(
            "<p>Fórmula conforme o método cadastrado. Valor da operação = valor do item − desconto + frete + seguro + outras despesas. Cada linha é contada uma vez.</p>"
        )
        if base["unassessed"]:
            sections.append(
                f"<p>{base['unassessed']} linha(s) sem comparação completa; não contabilizadas como compatíveis ou como erro.</p>"
            )
        if base["rows"]:
            sections.append(f"<p><strong>Exemplo:</strong> {e(example(base['rows'][0]))}</p>")
            sections.append(
                "<h2>Linhas com divergência na base</h2><table><thead><tr><th>Nota / linha</th><th>Produto</th><th>Operação / ICMS</th><th>Base esperada</th><th>Base PIS / COFINS</th><th>Diferença</th></tr></thead><tbody>"
            )
            for row in base["rows"]:
                sections.append(
                    f"<tr><td>{e(row['document'])} / {e(row['source'].get('line'))}</td><td>{e(row['description'])}</td><td>{brl(row['operation_value'])}<br>{brl(row['icms'])}</td><td>{brl(row['expected_base'])}</td><td>{brl(row['pis_base'])}<br>{brl(row['cofins_base'])}</td><td>{'ICMS não descontado' if row['kind'] == 'missing_icms' else 'Composição da base'}</td></tr>"
                )
            sections.append("</tbody></table>")
    others = [f for f in result.findings if not base or f.code != "C09"]
    if others:
        sections.append("<h2>Outras divergências documentais</h2>")
        for f in others:
            for ev in f.evidence:
                sections.append(
                    f"<p><strong>Nota {e(ev['document'])}, linha {e(ev['item']['source'].get('line'))} — {e(f.description)}</strong><br>{e(f.message)}<br>ICMS informado: {brl(ev['item']['icms']['value'])}. {e(f.expected) if f.expected else ''}</p>"
                )
    if not result.findings:
        sections.append(
            "<p>Nenhuma divergência documental identificada nas comparações realizadas.</p>"
        )
    limitations = "".join(
        f"<p>{e(x)}</p>"
        for x in result.summary.get("limitations", [])
        if "arquivo" in x.lower() or "trunc" in x.lower() or "descart" in x.lower()
    )
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><style>
    @page {{size:A4; margin:15mm; @bottom-center {{content:"{FOOTER}";font-size:8pt}}}}
    body{{font:10pt sans-serif;color:{color}}} h1{{font-size:24pt}} h2{{font-size:14pt}}
    table{{border-collapse:collapse;width:100%;font-size:8pt}}td,th{{padding:6px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#edf4f0}}tr{{break-inside:avoid}}p{{overflow-wrap:anywhere}}small{{font-size:7pt}}
    </style><body>{logo_html}<h1>Conferência fiscal</h1>{cover}{"".join(sections)}
    <p>A conferência mostra diferenças verificáveis nos dados e na fórmula cadastrada. A classificação fiscal dos demais produtos não foi concluída.</p>{limitations}
    <small>Motor: {e(result.engine_version)}<br>Entradas: {e(result.input_hash)}<br>Regras: {e(result.rules_hash)}</small><p>{e(branding.get("rodape", ""))}</p></body></html>'''


def pdf_report(result: Result, context: dict, branding: dict | None = None) -> bytes:
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    # Somente imagens PNG/JPEG embutidas e validadas pelo contrato de branding.
    # Bloqueia http(s), file, FTP e redirecionamentos para recursos externos.
    fetcher = URLFetcher(allowed_protocols={"data"}, allow_redirects=False, fail_on_errors=True)
    return HTML(string=html_report(result, context, branding), url_fetcher=fetcher).write_pdf()
