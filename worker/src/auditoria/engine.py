"""Motor puro: sem relógio, rede, banco ou IA. Regras aprovadas são a única fonte fiscal."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal, localcontext

from auditoria.domain import Document, Finding, Profile, Result, Rule, digest
from auditoria.restaurant_review import POLICY, is_tip, operation_rows, operation_summary, review

CODES = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "R02", "R04", "R05"]
D = Decimal


def _evaluate(
    documents: list[Document], profiles: list[Profile], rules: list[Rule], official=None
) -> Result:
    findings, skipped = [], []
    products = defaultdict(list)
    coverage = Counter()

    def skip(code, doc, item, why):
        skipped.append(
            {"code": code, "document": doc.key or doc.number, "source": item.source, "reason": why}
        )

    def add(
        code,
        doc,
        item,
        message,
        severity="revisar",
        rule=None,
        expected=None,
        impact=None,
        source=None,
    ):
        evidence = {
            "document": doc.key or doc.number,
            "issued": doc.issued.isoformat(),
            "item": item.model_dump(mode="json"),
        }
        finding = Finding(
            code=code,
            severity=severity,
            message=message,
            product=item.code or f"sem-codigo:{digest(item.source)[:12]}",
            description=item.description,
            evidence=[evidence],
            expected=expected or {},
            impact=abs(impact) if impact is not None else None,
            direction=("pago_a_mais" if impact > 0 else "pago_a_menos") if impact else "neutro",
        )
        if rule:
            finding.rule_id = rule.id
            finding.legal_basis = rule.legal_basis
            finding.source_url = rule.source_url
        elif source:
            finding.legal_basis = source["title"]
            finding.source_url = source["url"]
        finding.id = digest(finding.model_dump(mode="json"))
        findings.append(finding)

    for doc in documents:
        eligible = [
            p
            for p in profiles
            if p.valid_from <= doc.issued and (p.valid_to is None or doc.issued <= p.valid_to)
        ]
        profile = eligible[0] if len(eligible) == 1 else None
        for item in doc.items:
            if doc.status in ("cancelada", "denegada"):
                for code in CODES:
                    skip(code, doc, item, "Documento cancelado/denegado excluído")
                continue
            if item.code:
                products[item.code].append((doc, item))
            else:
                skip("C01", doc, item, "Código do produto ausente")
            review(doc, item, profile, add, skip, coverage)
            if official and not is_tip(item):
                from auditoria.official import check_ncm

                state, explanation = check_ncm(item.ncm, doc.issued, official)
                if state == "skip":
                    skip("R01", doc, item, explanation)
                else:
                    coverage["R01"] += 1
                    if state == "error":
                        add(
                            "R01",
                            doc,
                            item,
                            explanation,
                            "revisar",
                            source=next(s for s in official["sources"] if s["id"] == "ncm"),
                        )
            if item.ncm in ("00000000", "99999999"):
                add(
                    "C06",
                    doc,
                    item,
                    (
                        "Gorjeta com NCM coringa: conferir o tratamento de valor acessório no "
                        "documento, sem equiparar automaticamente a mercadoria."
                    )
                    if is_tip(item)
                    else "NCM coringa: revisar a classificação do produto.",
                    "revisar" if is_tip(item) else "erro",
                )
            if not item.ncm:
                skip("C06", doc, item, "NCM ausente")
            else:
                coverage["C06"] += 1
            if item.cest == "0000000":
                add(
                    "C05",
                    doc,
                    item,
                    (
                        "CEST zerado na planilha: conferir se representa campo ausente ou "
                        "código inválido no documento original."
                    ),
                    "revisar",
                )
            icms = item.icms
            if icms.cst is not None:
                coverage["C03"] += 1
                if icms.cst in ("40", "41") and icms.value is not None and icms.value != 0:
                    add(
                        "C03",
                        doc,
                        item,
                        "CST de isenção/não tributação com valor de ICMS informado.",
                        "erro",
                    )
                if (
                    icms.cst == "00"
                    and icms.rate == 0
                    and item.cfop not in ("5405", "5919", "5927", "5929", "5949")
                ):
                    add("C03", doc, item, "CST 00 com alíquota zero: revisar enquadramento.")
            else:
                skip("C03", doc, item, "CST ICMS ausente ou operação com CSOSN")
            for name in ("icms", "pis", "cofins"):
                tax = getattr(item, name)
                if None in (tax.base, tax.rate, tax.value):
                    skip("C04", doc, item, f"{name.upper()}: base/alíquota/valor ausentes")
                    continue
                expected_value = (tax.base * tax.rate / 100).quantize(
                    D(".01"), rounding=ROUND_HALF_UP
                )
                coverage["C04"] += 1
                if abs(tax.value - expected_value) > D(".05"):
                    add(
                        "C04",
                        doc,
                        item,
                        f"{name.upper()}: valor difere de base × alíquota.",
                        "erro",
                        expected={f"{name}_value": str(expected_value)},
                    )
            if not profile:
                for code in ("C02", "C05", "C07", "C08", "C09", "R02", "R04", "R05"):
                    skip(code, doc, item, "Perfil fiscal ausente ou vigências sobrepostas")
                continue
            if profile.contribuinte_ipi is None:
                skip("C07", doc, item, "Condição de contribuinte de IPI não informada")
            else:
                coverage["C07"] += 1
            if profile.contribuinte_ipi is False and item.ipi.cst == "50":
                add("C07", doc, item, "IPI CST 50 com perfil declarado não contribuinte de IPI.")
            coverage["C08"] += 1
            if item.cfop in ("5927", "5949"):
                add(
                    "C08",
                    doc,
                    item,
                    "Operação de natureza específica: conferir finalidade e documentação.",
                )
            if profile.metodo_pis_cofins:
                needed = (item.value, item.discount, item.freight, item.insurance, item.other)
                if any(v is None for v in needed) or (
                    profile.metodo_pis_cofins == "com_exclusao_icms" and icms.value is None
                ):
                    skip("C09", doc, item, "Componentes da base incompletos")
                else:
                    expected_base = (
                        item.value - item.discount + item.freight + item.insurance + item.other
                    )
                    operation_value = expected_base
                    exclusion = profile.metodo_pis_cofins == "com_exclusao_icms"
                    if exclusion:
                        expected_base -= icms.value
                    expected_base = expected_base.quantize(D(".01"))
                    for name in ("pis", "cofins"):
                        tax = getattr(item, name)
                        if tax.cst in ("01", "02") and tax.base is not None:
                            if expected_base < 0:
                                skip(
                                    "C09",
                                    doc,
                                    item,
                                    f"{name.upper()}: base negativa; conferir componentes",
                                )
                                continue
                            coverage["C09"] += 1
                            difference = tax.base.quantize(D(".01")) - expected_base
                            if difference != 0:
                                missing_exclusion = (
                                    exclusion
                                    and icms.value > 0
                                    and tax.base.quantize(D(".01"))
                                    == operation_value.quantize(D(".01"))
                                )
                                formula = (
                                    "valor do item - desconto + frete + seguro + outras despesas"
                                )
                                if exclusion:
                                    formula += " - ICMS destacado do próprio item"
                                add(
                                    "C09",
                                    doc,
                                    item,
                                    (
                                        f"{name.upper()} CST {tax.cst}: ICMS destacado do item "
                                        "não foi descontado da base informada."
                                        if missing_exclusion
                                        else f"{name.upper()} CST {tax.cst}: base divergente "
                                        "por item; conferir componentes e outras exclusões."
                                    ),
                                    expected={
                                        f"{name}_base": str(expected_base),
                                        "base_informada": str(tax.base),
                                        "valor_operacao_item": str(operation_value),
                                        "icms_excluido_item": str(icms.value) if exclusion else "0",
                                        "diferenca_base": str(difference),
                                        "formula": formula,
                                    },
                                    source={
                                        "title": "Exclusão do ICMS destacado por item (Tema 69)",
                                        "url": "https://www.gov.br/pgfn/pt-br/cidadania-tributaria/por-assunto/pis-cofins-2/icms-e-tributos-na-base-de-calculo-pis-cofins-1",
                                    }
                                    if exclusion
                                    else None,
                                )
                        else:
                            skip("C09", doc, item, f"{name.upper()}: CST/base não comparável")
            else:
                skip("C09", doc, item, "Método de formação da base não declarado")
            context = {
                "cfop": item.cfop,
                "icms_cst": icms.cst,
                "icms_csosn": icms.csosn,
                "recipient_taxpayer": doc.recipient_taxpayer,
                "final_consumer": doc.final_consumer,
                "operation": doc.operation,
                "special_regime": profile.optante_regime_especial_rest,
                "contribuinte_ipi": profile.contribuinte_ipi,
                "cest": item.cest,
                "purpose": doc.purpose,
            }
            for code in ("C02", "C05", "R02", "R04", "R05"):
                if doc.status != "autorizada" or doc.operation == "desconhecida":
                    skip(code, doc, item, "Situação ou operação não confirmada")
                    continue
                matches = [
                    r
                    for r in rules
                    if r.status == "aprovada"
                    and r.code == code
                    and r.uf == profile.uf
                    and profile.regime_federal in r.regimes
                    and r.valid_from <= doc.issued
                    and (r.valid_to is None or doc.issued <= r.valid_to)
                    and (not r.ncm_prefix or (item.ncm or "").startswith(r.ncm_prefix))
                    and all(
                        context.get(k) is not None
                        and (context[k] in v if isinstance(v, list) else context[k] == v)
                        for k, v in r.conditions.items()
                    )
                ]
                if not matches:
                    if (
                        code == "R05"
                        and official
                        and official["valid_from"] <= doc.issued.isoformat() <= official["valid_to"]
                        and profile.regime_federal != "simples"
                        and profile.regime_pis_cofins in ("cumulativo", "nao_cumulativo")
                    ):
                        checked = False
                        for name in ("pis", "cofins"):
                            tax = getattr(item, name)
                            if tax.cst != "01" or tax.rate is None:
                                skip(
                                    code,
                                    doc,
                                    item,
                                    f"{name.upper()}: catálogo geral exige CST 01 e alíquota",
                                )
                                continue
                            checked = True
                            suffix = (
                                "cumulative"
                                if profile.regime_pis_cofins == "cumulativo"
                                else "noncumulative"
                            )
                            rate = (
                                D(official["parameters"]["contributions"][name + "_" + suffix])
                                * 100
                            )
                            coverage[code] += 1
                            if abs(tax.rate - rate) > D(".0001"):
                                source_id = (
                                    ("pis_cumulativo" if name == "pis" else "cumulativo")
                                    if suffix == "cumulative"
                                    else name
                                )
                                add(
                                    code,
                                    doc,
                                    item,
                                    f"{name.upper()}: CST 01 com alíquota divergente "
                                    "do regime declarado.",
                                    "risco",
                                    expected={name + "_rate": str(rate)},
                                    source=next(
                                        s for s in official["sources"] if s["id"] == source_id
                                    ),
                                )
                        if checked:
                            continue
                    skip(code, doc, item, "Sem regra aprovada aplicável ao contexto e à data")
                    continue
                rank = max((r.priority, len(r.ncm_prefix), len(r.conditions)) for r in matches)
                selected = [
                    r for r in matches if (r.priority, len(r.ncm_prefix), len(r.conditions)) == rank
                ]
                if len(selected) != 1:
                    skip(code, doc, item, "Conflito entre regras: exige revisão da base")
                    continue
                rule = selected[0]
                coverage[code] += 1
                actual = {
                    "icms_cst": icms.cst,
                    "icms_csosn": icms.csosn,
                    "icms_rate": icms.rate,
                    "cest": item.cest,
                    "pis_cst": item.pis.cst,
                    "cofins_cst": item.cofins.cst,
                    "pis_rate": item.pis.rate,
                    "cofins_rate": item.cofins.rate,
                }
                mismatch, missing = {}, False
                for field, wanted in rule.expected.items():
                    if field == "subject_to_st":
                        # R02 só confirma inconsistência com operação ST expressamente selecionada.
                        if not wanted and item.cfop in ("5405", "5403", "6404", "6403"):
                            mismatch[field] = wanted
                        continue
                    current = actual.get(field)
                    if current is None:
                        missing = True
                        continue
                    choices = wanted if isinstance(wanted, list) else [wanted]
                    if field.endswith("_rate"):
                        ok = any(abs(current - D(str(v))) <= D(".0001") for v in choices)
                    else:
                        ok = current in choices
                    if not ok:
                        mismatch[field] = wanted
                if missing:
                    skip(code, doc, item, "Campo necessário para comparação ausente")
                if mismatch:
                    impact = None
                    if code == "R04" and icms.base is not None and icms.value is not None:
                        impact = icms.value - (
                            icms.base * D(str(rule.expected["icms_rate"])) / 100
                        ).quantize(D(".01"))
                    if code == "R05":
                        deltas = []
                        for name in ("pis", "cofins"):
                            tax = getattr(item, name)
                            rate = rule.expected.get(name + "_rate")
                            if rate is None or tax.base is None or tax.value is None:
                                break
                            deltas.append(
                                tax.value - (tax.base * D(str(rate)) / 100).quantize(D(".01"))
                            )
                        if len(deltas) == 2:
                            impact = sum(deltas)
                    add(code, doc, item, rule.title, "risco", rule, mismatch, impact)
    for _product, rows in sorted(products.items()):
        signatures = {
            (i.ncm, i.cfop, i.icms.cst, i.icms.csosn, i.pis.cst, i.cofins.cst) for _, i in rows
        }
        coverage["C01"] += len(rows)
        if len(signatures) > 1:
            for doc, item in rows:
                add(
                    "C01",
                    doc,
                    item,
                    "Mesmo produto apresenta classificações diferentes; "
                    "conferir o contexto das operações.",
                )
    findings.sort(key=lambda f: (f.code, f.product, f.id))
    skipped.sort(key=lambda x: digest(x))
    directions = {
        k: str(sum((f.impact or D(0)) for f in findings if f.direction == k))
        for k in ("pago_a_mais", "pago_a_menos")
    }
    return Result(
        input_hash=digest(
            {
                "documents": [d.model_dump(mode="json") for d in documents],
                "profiles": [p.model_dump(mode="json") for p in profiles],
            }
        ),
        rules_hash=digest(
            {
                "custom": sorted([r.model_dump(mode="json") for r in rules], key=lambda r: r["id"]),
                "official": official,
                "document_review": POLICY,
            }
        ),
        findings=findings,
        skipped=skipped,
        summary={
            "document_review_policy": POLICY,
            "operations": operation_summary(operation_rows(documents)),
            "review_rows": operation_rows(documents),
            "findings": len(findings),
            "severity": dict(Counter(f.severity for f in findings)),
            "coverage": dict(coverage),
            "skipped": len(skipped),
            "potential_impact": directions,
            "impact_notice": "Estimativa documental; não comprova imposto recolhido.",
            "regimes": sorted({p.regime_federal for p in profiles}),
            "official_catalog_version": official["version"] if official else None,
            "limitations": [
                "Simples: não calcula DAS sem RBT12, anexos e segregação de receitas.",
                "Este relatório é documental. Use Apuração de impostos para "
                "calcular por período com dados complementares.",
                "Zero apontamentos não comprova conformidade quando há checagens não avaliadas.",
                (
                    "Categorias são derivadas do NCM/descrição declarados. Não certificam "
                    "classificação ou direito a benefício; modelo fiscal ausente limita a "
                    "revisão do destaque de ICMS."
                ),
            ],
        },
    )


def evaluate(
    documents: list[Document], profiles: list[Profile], rules: list[Rule], official=None
) -> Result:
    # Não herdar precisão/arredondamento de outras operações no processo.
    with localcontext() as ctx:
        ctx.prec = 38
        ctx.rounding = ROUND_HALF_UP
        return _evaluate(documents, profiles, rules, official)
