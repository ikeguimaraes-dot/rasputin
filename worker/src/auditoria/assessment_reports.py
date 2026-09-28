"""Exporta exclusivamente o snapshot salvo, sem recalcular com regras novas."""

import html
import json
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

from auditoria.reports import safe_cell


def export(row, kind):
    result = row["result_payload"]
    source = row["input_snapshot"]
    fields = row["catalog_snapshot"]["modules"][row["module"]]["fields"]
    labels = {f["key"]: f["label"] for f in fields}
    headers = [
        "Tributo",
        "Base R$",
        "Débito R$",
        "Deduções R$",
        "Saldo a recolher R$",
        "Excedente R$",
    ]
    values = [
        [
            (x[k] if x[k] is not None else "—")
            for k in ("tax", "base", "gross", "deductions", "due", "remaining")
        ]
        for x in result["lines"]
    ]
    context = [
        ["Cliente", source["client"]["razao_social"]],
        ["CNPJ", source["client"]["cnpj"]],
        ["Competência", str(row["period"])],
        ["Periodicidade", result["period_type"]],
        ["Versão", result["catalog_version"]],
        ["Hash da apuração", row["sha256"]],
        ["Hash das regras", result["catalog_hash"]],
        ["Escopo", result["scope"]],
    ]
    inputs = [[labels.get(k, k), str(v)] for k, v in source["values"].items()]
    sources = [
        [s["title"], s["url"], s["sha256"], s.get("capture_kind", "")] for s in result["sources"]
    ]
    notes = [result["notice"], *result["warnings"]]
    if kind == "xlsx":
        wb = Workbook()
        wb.remove(wb.active)
        for name, rows in [
            ("Apuração", context + [headers] + values),
            ("Dados declarados", inputs),
            ("Fontes", [["Norma", "URL", "Hash da captura", "Tipo da captura"]] + sources),
            (
                "Memória",
                [[k, json.dumps(v, ensure_ascii=False)] for k, v in result["memory"].items()],
            ),
            ("Observações", [[x] for x in notes]),
        ]:
            ws = wb.create_sheet(name)
            for r in rows:
                ws.append([safe_cell(x) for x in r])
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for c in ws[1]:
                c.font = Font(bold=True)
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(
                    65, max(20, max(len(str(c.value or "")) for c in col) + 2)
                )
        out = BytesIO()
        wb.save(out)
        return out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    from weasyprint import HTML
    from weasyprint.urls import URLFetcher

    def e(x):
        return html.escape(str(x))

    def table(rows):
        return (
            "<table>"
            + "".join("<tr>" + "".join("<td>" + e(x) + "</td>" for x in r) + "</tr>" for r in rows)
            + "</table>"
        )

    body = (
        '<html lang="pt-BR"><meta charset="utf-8"><style>@page{size:A4;margin:18mm}'
        "body{font:10pt "
        "sans-serif;color:#173d35}table{width:100%;border-collapse:collapse;margin:12px 0}"
        "td{border:1px solid "
        "#ddd;padding:6px;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "h1{font-size:20pt}</style><h1>"
        + e(result["title"])
        + "</h1>"
        + table(context)
        + table([headers] + values)
        + "<h2>Dados declarados</h2>"
        + table(inputs)
        + "<h2>Memória de cálculo</h2><pre>"
        + e(json.dumps(result["memory"], ensure_ascii=False, indent=2))
        + "</pre><h2>Fontes</h2>"
        + table(sources)
        + "".join("<p>" + e(x) + "</p>" for x in notes)
        + "</html>"
    )
    fetcher = URLFetcher(allowed_protocols={"data"}, allow_redirects=False, fail_on_errors=True)
    return HTML(string=body, url_fetcher=fetcher).write_pdf(), "application/pdf"
