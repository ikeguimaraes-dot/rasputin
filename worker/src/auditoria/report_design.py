"""Apresentação editorial do relatório ao cliente. Não altera conclusões ou valores."""

import re
from base64 import b64encode
from functools import lru_cache
from html import escape
from pathlib import Path

from auditoria.confirmed_report import brl, example, line_key


def e(value):
    return escape(str(value if value is not None else "Não informado"))


@lru_cache(maxsize=1)
def mascot():
    data = Path(__file__).with_name("assets").joinpath("rasputin-mascot.png").read_bytes()
    return "data:image/png;base64," + b64encode(data).decode("ascii")


def client_html(result, context, branding, footer):
    branding = branding or {}
    color = branding.get("cor", "#193b32")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = "#193b32"
    logo = branding.get("logo_data_url") or ""
    logo_html = (
        f'<img class="office-logo" src="{e(logo)}" alt="Logo do escritório">'
        if logo.startswith(("data:image/png;base64,", "data:image/jpeg;base64,"))
        else ""
    )
    cnpj = str(context.get("CNPJ", "Não informado"))
    if re.fullmatch(r"\d{14}", cnpj):
        cnpj = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    period = re.sub(
        r"(\d{4})-(\d{2})-(\d{2})", r"\3/\2/\1", str(context.get("Período", "Não informado"))
    )
    base = result.summary.get("base_review")
    overview, details = [], []
    if base:
        total = base["compatible"] + base["missing_icms"] + base["other_difference"]
        percent = base["compatible"] / total * 100 if total else 0
        overview.append(
            f"<h2>01 <span>O resultado, em números</span></h2><p>Foram comparadas <strong>{total} linhas</strong> com CST 01 ou 02 de PIS/COFINS e dados suficientes. Cada item é contado uma única vez, mesmo quando a diferença aparece nos dois tributos.</p>"
        )
        overview.append(
            '<div class="metrics">'
            + "".join(
                f'<div class="metric"><strong>{base[key]}</strong><span>{label}</span></div>'
                for key, label in [
                    (
                        "missing_icms",
                        ("linha" if base["missing_icms"] == 1 else "linhas")
                        + " sem descontar o ICMS da base",
                    ),
                    (
                        "other_difference",
                        ("linha" if base["other_difference"] == 1 else "linhas")
                        + " com outra divergência na composição da base",
                    ),
                    (
                        "compatible",
                        ("linha compatível" if base["compatible"] == 1 else "linhas compatíveis")
                        + " com a fórmula",
                    ),
                ]
            )
            + "</div>"
        )
        if total:
            overview.append(
                '<div class="bar">'
                + "".join(
                    f'<span style="width:{base[key] / total * 100:.5f}%;background:{tone}"></span>'
                    for key, tone in [
                        ("compatible", "#1a493b"),
                        ("missing_icms", "#a9c943"),
                        ("other_difference", "#bd744d"),
                    ]
                )
                + "</div>"
            )
            overview.append(
                f'<p class="caption">{percent:.1f}% das bases comparadas são compatíveis com a fórmula. O indicador se refere à composição da base; não representa conformidade fiscal geral.</p>'.replace(
                    f"{percent:.1f}%", f"{percent:.1f}%".replace(".", ",")
                )
            )
        if base["unassessed"]:
            overview.append(
                f'<p class="caption">{base["unassessed"]} linha(s) sem comparação completa, excluídas do indicador. A falta de informação não foi tratada como erro ou aprovação.</p>'
            )
        if base["rows"]:
            overview.append(
                f'<div class="callout"><h3>Uma diferença, explicada</h3><p>{e(example(base["rows"][0]))}</p></div>'
            )
        overview.append(
            "<h3>O que este resultado significa</h3><p>A conferência compara a base informada com a fórmula do método cadastrado, considerando valor do item, descontos, frete, seguro, outras despesas e, quando aplicável, a exclusão do ICMS destacado. Os apontamentos identificam diferenças nos dados; não calculam, por si só, imposto devido ou recolhido.</p>"
        )
        if base["rows"]:
            for start in range(0, len(base["rows"]), 12):
                chunk = base["rows"][start : start + 12]
                details.append('<section class="item-page">')
                details.append(
                    "<h2>02 <span>Itens que precisam de revisão</span></h2><p>Localize cada ocorrência pela nota e pela linha do arquivo. A base esperada corresponde ao método informado para a empresa. As colunas de PIS e COFINS reproduzem as bases da planilha.</p><table><thead><tr><th>Nota / linha</th><th>Produto / CFOP</th><th>Operação<br>ICMS</th><th>Base<br>esperada</th><th>Base PIS<br>Base COFINS</th><th>Apontamento</th></tr></thead><tbody>"
                )
                for row in chunk:
                    label = (
                        "ICMS não descontado"
                        if row["kind"] == "missing_icms"
                        else "Outra composição"
                    )
                    details.append(
                        f'<tr><td><b>{e(row["document"])}</b><br>Linha {e(row["source"].get("line"))}</td><td>{e(row["description"])}<br><small>CFOP {e(row["cfop"])}</small></td><td class="amount">{brl(row["operation_value"])}<br>{brl(row["icms"])}</td><td class="amount"><b>{brl(row["expected_base"])}</b></td><td class="amount">{brl(row["pis_base"])}<br>{brl(row["cofins_base"])}</td><td>{label}</td></tr>'
                    )
                details.append(
                    '</tbody></table><p class="caption">Valor da operação = valor do item - desconto + frete + seguro + outras despesas. A mesma base esperada só se aplica aos tributos com CST 01/02; outros CSTs não entram nessa comparação.</p>'
                )
                details.append("</section>")
            for row in base["rows"]:
                if row["kind"] == "other_difference":
                    details.append(
                        f'<div class="callout"><h3>Composição da base: revisão específica</h3><p>{e(example(row))}</p><p>Neste item, a diferença não corresponde apenas à ausência de desconto do ICMS. Confira os componentes da operação e eventuais exclusões documentadas antes de ajustar a escrituração.</p></div>'
                    )
    others = [f for f in result.findings if not base or f.code != "C09"]
    if others:
        count = len({line_key(ev) for f in others for ev in f.evidence})
        overview.append(
            f'<p class="caption">Além da composição da base, {count} linha(s) apresentam outras divergências documentais, detalhadas na seção 03.</p>'
        )
        details.append(
            '<section class="other-section"><h2>03 <span>Outras divergências documentais</span></h2>'
        )
        for f in others:
            for ev in f.evidence:
                item = ev["item"]
                explanation = (
                    f"O item informa CST {e(item['icms']['cst'])} e, ao mesmo tempo, ICMS de {brl(item['icms']['value'])}. Há uma contradição entre a situação tributária declarada e o destaque do imposto. Verifique a nota de origem para confirmar qual informação precisa ser corrigida."
                    if f.code == "C03"
                    else e(f.message)
                )
                details.append(
                    f'<div class="finding"><h3>Nota {e(ev["document"])}, linha {e(item["source"].get("line"))}</h3><p class="product">{e(f.description)}</p><p>{explanation}</p>'
                )
                if f.code != "C03":
                    details.append(
                        "<p>"
                        + "; ".join(
                            f"{e(k.replace('_', ' '))}: {e(v)}" for k, v in f.expected.items()
                        )
                        + "</p>"
                    )
                details.append("</div>")
        details.append("</section>")
    if not result.findings:
        overview.append(
            '<div class="callout"><h3>Comparações concluídas</h3><p>Nenhuma divergência documental identificada nas comparações realizadas. O resultado se limita aos dados e às regras disponíveis.</p></div>'
        )
    next_step = (
        "Revise os itens relacionados neste relatório junto aos documentos de origem. Confirme os valores de ICMS e os componentes da operação; quando a diferença for confirmada, ajuste a base no sistema fiscal. Preserve a evidência da revisão para a próxima conferência."
        if result.findings
        else "Mantenha os documentos de origem e o relatório arquivados para acompanhamento. Novos documentos ou informações complementares podem ser avaliados em uma nova conferência."
    )
    conclusion = (
        f'<div class="next"><h3>Encaminhamento ao responsável fiscal</h3><p>{next_step}</p></div>'
    )
    limitations = "".join(
        f"<p>{e(x)}</p>"
        for x in result.summary.get("limitations", [])
        if any(word in x.lower() for word in ("arquivo", "trunc", "descart"))
    )
    metadata = "".join(
        f"<p><b>{e(k)}</b> {e(v)}</p>"
        for k, v in context.items()
        if k not in ("Cliente", "CNPJ", "Período")
    )
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Relatório de conferência fiscal</title><style>
    @page {{size:A4; margin:16mm 15mm 19mm; @bottom-left {{content:"RASPUTIN  /  CONFERÊNCIA DOCUMENTAL";font:7pt sans-serif;color:#617367}} @bottom-right {{content:counter(page) " / " counter(pages);font:8pt sans-serif;color:#193b32}}}}
    *{{box-sizing:border-box}}body{{font:9pt/1.65 sans-serif;color:{color};margin:0}}h1,h2,h3,p{{margin:0}}p{{margin:7px 0;overflow-wrap:anywhere}}h1{{font-size:29pt;font-weight:500;line-height:1.12;letter-spacing:-1px;margin:14px 0}}h2{{font-size:11pt;color:#729049;margin:22px 0 10px;break-after:avoid}}h2 span{{color:{color};font-size:15pt;margin-left:10px}}h3{{font-size:10pt;margin-bottom:6px;break-after:avoid}}.masthead{{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}}.wordmark{{font-size:21pt;font-weight:bold;letter-spacing:-1px}}.office-logo{{max-width:110px;max-height:40px}}.office{{font-size:8pt;text-align:right;color:#617367;max-width:240px}}.hero{{background:#193f33;color:white;border-radius:14px;padding:24px 28px;position:relative;min-height:162px;overflow:hidden}}.hero p{{color:#d0dfc8;font-size:9pt;max-width:370px}}.hero .eyebrow{{color:#d8f078;letter-spacing:1.6px;font-size:7pt}}.mascot{{position:absolute;right:15px;bottom:-3px;width:111px;height:165px;object-fit:contain}}.identity{{padding:14px 0;border-bottom:1px solid #e1e6df}}.identity strong{{font-size:11pt}}.identity p{{margin:3px 0;font-size:8pt;color:#617367}}.metrics{{display:flex;gap:12px;margin:15px 0 13px}}.metric{{flex:1;padding:13px;background:#f3f6eb;border-radius:9px}}.metric strong{{display:block;font-size:25pt;font-weight:500;line-height:1.25}}.metric span{{display:block;font-size:8pt;line-height:1.5;margin-top:6px}}.bar{{display:flex;height:7px;background:#edf0e9;border-radius:4px;overflow:hidden}}.bar span{{display:block;height:7px}}.caption{{font-size:7.5pt;color:#617367;line-height:1.5}}.callout{{background:#f1f6e2;border-left:3px solid #a9c943;border-radius:0 8px 8px 0;padding:15px 18px;margin:17px 0;break-inside:avoid}}.next{{border:1px solid #dce5d4;border-radius:9px;padding:14px 18px;margin-top:15px;break-inside:avoid}}.cover{{break-after:page}}.details>h2:first-child{{margin-top:0}}table{{border-collapse:collapse;width:100%;font-size:7.3pt;table-layout:fixed;margin-top:16px}}thead{{display:table-header-group}}th{{background:#193f33;color:white;padding:9px 6px;text-align:left;font-weight:500;font-size:7pt}}td{{padding:10px 6px;vertical-align:top;border-bottom:1px solid #dfe7d9;overflow-wrap:anywhere;line-height:1.5}}th:nth-child(1){{width:13%}}th:nth-child(2){{width:24%}}th:nth-child(3){{width:16%}}th:nth-child(4){{width:15%}}th:nth-child(5){{width:16%}}th:nth-child(6){{width:16%}}tbody tr:nth-child(even){{background:#f8faf4}}tr{{break-inside:avoid}}.amount{{font-size:7pt}}small{{color:#617367;font-size:7pt}}.finding{{padding:15px 18px;border:1px solid #e1e6df;border-radius:9px;margin:12px 0;break-inside:avoid}}.product{{font-size:8pt;color:#617367}}.scope{{margin-top:24px;border-top:1px solid #e1e6df;padding-top:14px;font-size:8pt;color:#617367}}.technical{{font-size:7pt;overflow-wrap:anywhere;color:#617367}}.technical p{{margin:3px 0}}.other-section{{margin-top:0;break-before:page}}.item-page + .item-page{{break-before:page}}.item-page h2{{margin-top:0}}.scope{{break-inside:avoid}}
    </style><body><section class="cover"><div class="masthead"><span class="wordmark">rasputin<span style="color:#95b73f">.</span></span><div class="office">{logo_html}<br>{e(branding.get("nome", "Conferência fiscal para restaurantes"))}</div></div>
    <div class="hero"><p class="eyebrow">DO DOCUMENTO À EVIDÊNCIA</p><h1>Clareza em cada<br>apontamento.</h1><p>Relatório de conferência fiscal</p><img class="mascot" src="{mascot()}" alt="Mascote Rasputin"></div>
    <div class="identity"><strong>{e(context.get("Cliente", "Conferência documental"))}</strong><p>CNPJ {e(cnpj)} &nbsp; | &nbsp; Período {e(period)}</p></div>
    {"".join(overview)}</section><section class="details">{"".join(details)}
    {conclusion}<div class="scope"><h3>Escopo e integridade da conferência</h3><p>Apenas diferenças verificáveis nos dados e na fórmula cadastrada são apresentadas como ocorrências. Suspeitas baseadas no nome ou em classificação presumida de produtos não integram os apontamentos. A classificação fiscal dos demais produtos não foi concluída.</p>{limitations}<p>{e(footer)}</p></div>
    <details class="technical" open><summary>Identificação e rastreabilidade</summary>{metadata}<p>Motor {e(result.engine_version)}<br>Entradas {e(result.input_hash)}<br>Regras {e(result.rules_hash)}</p></details><p class="caption">{e(branding.get("rodape", ""))}</p></section></body></html>'''
