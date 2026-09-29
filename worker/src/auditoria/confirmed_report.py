"""Publicação apenas de diferenças documentais demonstráveis; sem inferir classificação."""

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal, localcontext

from auditoria.domain import Document, Finding, Profile, Result, digest


def confirmed(f: Finding) -> bool:
    if f.code in ("C04", "C09"):
        return bool(f.evidence and f.expected)
    return (
        f.code == "C03"
        and bool(f.evidence)
        and all(
            ev["item"]["icms"]["cst"] in ("40", "41")
            and ev["item"]["icms"]["value"] is not None
            and Decimal(str(ev["item"]["icms"]["value"])) != 0
            for ev in f.evidence
        )
    )


def line_key(ev):
    return digest(
        [ev.get("document"), ev.get("issued"), ev["item"]["n_item"], ev["item"]["source"]]
    )


def publish(result: Result, snapshot: dict | None = None) -> Result:
    result = result.model_copy(deep=True)
    result.findings = [f for f in result.findings if confirmed(f)]
    result.summary["report_policy"] = "documentary-only-v1"
    result.summary["findings"] = len({line_key(ev) for f in result.findings for ev in f.evidence})
    result.summary["check_failures"] = len(result.findings)
    result.summary["severity"] = dict(Counter(f.severity for f in result.findings))
    result.summary["potential_impact"] = {
        direction: str(
            sum((f.impact or Decimal(0)) for f in result.findings if f.direction == direction)
        )
        for direction in ("pago_a_mais", "pago_a_menos")
    }
    if snapshot is not None:
        with localcontext() as ctx:
            ctx.prec = 38
            ctx.rounding = ROUND_HALF_UP
            result.summary["base_review"] = base_review(result, snapshot)
    return result


def base_review(result, snapshot):
    by_line = {}
    for f in result.findings:
        if f.code == "C09":
            for ev in f.evidence:
                by_line.setdefault(line_key(ev), []).append(f)
    summary = dict(missing_icms=0, other_difference=0, compatible=0, unassessed=0, rows=[])
    profiles = [Profile(**p) for p in snapshot["profiles"]]
    for raw in snapshot["documents"]:
        doc = Document(**raw)
        if doc.status in ("cancelada", "denegada"):
            continue
        active = [
            p
            for p in profiles
            if p.valid_from <= doc.issued and (p.valid_to is None or doc.issued <= p.valid_to)
        ]
        for item in doc.items:
            taxes = [t for t in (item.pis, item.cofins) if t.cst in ("01", "02")]
            if not taxes:
                continue
            parts = (item.value, item.discount, item.freight, item.insurance, item.other)
            if len(active) != 1 or not active[0].metodo_pis_cofins or any(x is None for x in parts):
                summary["unassessed"] += 1
                continue
            exclusion = active[0].metodo_pis_cofins == "com_exclusao_icms"
            if exclusion and item.icms.value is None:
                summary["unassessed"] += 1
                continue
            operation = item.value - item.discount + item.freight + item.insurance + item.other
            icms = item.icms.value if exclusion else Decimal(0)
            expected = (operation - icms).quantize(Decimal(".01"))
            if expected < 0:
                summary["unassessed"] += 1
                continue
            ev = dict(
                document=doc.key or doc.number,
                issued=str(doc.issued),
                item=item.model_dump(mode="json"),
            )
            failures = by_line.get(line_key(ev), [])
            # An older engine may not have evaluated this check. Never infer a pass from silence.
            mismatches = [
                t
                for t in taxes
                if t.base is not None and t.base.quantize(Decimal(".01")) != expected
            ]
            if not mismatches:
                summary["unassessed" if any(t.base is None for t in taxes) else "compatible"] += 1
                continue
            if not failures:
                summary["unassessed"] += 1
                continue
            kind = (
                "missing_icms"
                if exclusion
                and icms > 0
                and all(
                    t.base.quantize(Decimal(".01")) == operation.quantize(Decimal(".01"))
                    for t in mismatches
                )
                else "other_difference"
            )
            summary[kind] += 1
            summary["rows"].append(
                dict(
                    document=ev["document"],
                    issued=ev["issued"],
                    source=item.source,
                    description=item.description,
                    cfop=item.cfop,
                    kind=kind,
                    operation_value=str(operation),
                    icms=str(icms),
                    expected_base=str(expected),
                    pis_base=str(item.pis.base) if item.pis.base is not None else None,
                    cofins_base=str(item.cofins.base) if item.cofins.base is not None else None,
                    pis_cst=item.pis.cst,
                    cofins_cst=item.cofins.cst,
                )
            )
    return summary


def brl(value):
    if value is None:
        return "não informada"
    return "R$ " + f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace(
        "_", "."
    )


def example(row):
    return (
        f"Nota {row['document']}, linha {row['source'].get('line', '—')} — "
        f"valor da operação de {brl(row['operation_value'])}, ICMS de {brl(row['icms'])}. "
        f"A base esperada é {brl(row['expected_base'])}; "
        f"PIS informa {brl(row['pis_base'])} e COFINS informa {brl(row['cofins_base'])}."
    )
