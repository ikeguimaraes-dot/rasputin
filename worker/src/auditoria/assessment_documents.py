"""Document evidence for settlement. Declared tax is never certified liability."""

from calendar import monthrange
from collections import defaultdict
from decimal import Decimal

from auditoria.assessment import MODULES, money
from auditoria.domain import Document, digest
from auditoria.restaurant_review import CFOPS

D = Decimal
SALES = {"5101", "5102", "5405", "6101", "6102", "6404", "6405", "7101", "7102"}
VERSION = "documentos-2026.09.29.1"


def period_bounds(module, period):
    if module not in MODULES:
        raise ValueError("Módulo desconhecido")
    if period.day != 1 or period.year != 2026:
        raise ValueError("Informe uma competência de 2026")
    start = period
    kind = MODULES[module]["period"]
    if kind == "trimestral":
        if period.month not in (3, 6, 9, 12):
            raise ValueError("Escolha o mês de encerramento do trimestre")
        start = period.replace(month=((period.month - 1) // 3) * 3 + 1)
    elif kind == "anual_acumulado":
        start = period.replace(month=1)
    return start, period.replace(day=monthrange(period.year, period.month)[1])


def consolidate(uploads, module, period, profile):
    start, end = period_bounds(module, period)
    groups = defaultdict(lambda: {"items": 0, "amount": D(0), "missing": 0})
    totals = {
        t: {"value": D(0), "known": 0, "missing": 0}
        for t in ("icms", "pis", "cofins", "ipi", "st", "fcp")
    }
    rows, seen, warnings, months, products = [], {}, [], set(), {}
    excluded = duplicates = count = unknown_status = 0
    suggestions, bases = {}, defaultdict(lambda: D(0))
    recalculated = {
        t: {"base": D(0), "gross": D(0), "items": 0, "missing": 0} for t in ("pis", "cofins")
    }
    base_counts = {"compatible": 0, "missing_icms": 0, "other_difference": 0, "unassessed": 0}
    reasons = set()
    for upload in uploads:
        if upload.get("parcial"):
            reasons.add("Arquivo parcialmente recuperado: envie uma origem completa para fechar.")
        for raw in upload.get("canonical_payload") or []:
            doc = Document(**raw)
            if not start <= doc.issued <= end:
                continue
            clean = doc.model_dump(mode="json")
            for item in clean["items"]:
                item["source"] = {}
            # With no access key, only exact copies are safely suppressed. Same invoice
            # number from different issuers/series must not be merged.
            fingerprint = digest(clean)
            key = doc.key or fingerprint
            if key in seen:
                if seen[key] != fingerprint:
                    raise ValueError("Mesma chave com conteúdo divergente: selecione uma origem")
                duplicates += 1
                continue
            seen[key] = fingerprint
            if doc.status in ("cancelada", "denegada"):
                excluded += 1
                continue
            count += 1
            months.add(doc.issued.strftime("%Y-%m"))
            unknown_status += int(doc.status == "desconhecida")
            for item in doc.items:
                cfop = item.cfop or "Não informado"
                group = groups[cfop]
                group["items"] += 1
                parts = (item.value, item.discount, item.freight, item.insurance, item.other)
                amount = (
                    None
                    if any(x is None for x in parts)
                    else (item.value - item.discount + item.freight + item.insurance + item.other)
                )
                if amount is None:
                    group["missing"] += 1
                else:
                    group["amount"] += amount
                pkey = (item.code, item.description, item.ncm, item.cest)
                products.setdefault(pkey, set()).add(cfop)
                for tax, total in totals.items():
                    value = getattr(item, tax).value
                    total["missing" if value is None else "known"] += 1
                    if value is not None:
                        total["value"] += value
                review = {
                    "document": doc.number or doc.key,
                    "issued": str(doc.issued),
                    "item": item.n_item,
                    "description": item.description,
                    "cfop": cfop,
                    "source": item.source,
                    "upload_id": str(upload["id"]),
                    "operation": None if amount is None else money(amount),
                    "icms": None if item.icms.value is None else money(item.icms.value),
                }
                eligible = [t for t in ("pis", "cofins") if getattr(item, t).cst in ("01", "02")]
                expected = None
                if eligible and amount is not None and profile and profile.metodo_pis_cofins:
                    if profile.metodo_pis_cofins == "sem_exclusao_icms":
                        expected = amount
                    elif item.icms.value is not None:
                        expected = amount - item.icms.value
                    if expected is not None and expected < 0:
                        expected = None
                differences = []
                for tax in ("pis", "cofins"):
                    declared = getattr(item, tax)
                    review[tax + "_base"] = None if declared.base is None else money(declared.base)
                    review[tax + "_rate"] = None if declared.rate is None else str(declared.rate)
                    if tax in eligible and expected is not None and declared.base is not None:
                        if D(money(declared.base)) != D(money(expected)):
                            differences.append(declared.base)
                    if tax in eligible and expected is not None and declared.rate is not None:
                        review[tax + "_recomputed"] = money(expected * declared.rate / 100)
                    if cfop in SALES and doc.operation != "entrada" and tax in eligible:
                        subtotal = recalculated[tax]
                        if tax + "_recomputed" in review:
                            subtotal["base"] += expected
                            subtotal["gross"] += D(review[tax + "_recomputed"])
                            subtotal["items"] += 1
                        else:
                            subtotal["missing"] += 1
                    # Suggestions are restricted to declared CST01 at the general rate.
                    # CST02 is deliberately left for its specific legal rule.
                    regime = profile.regime_pis_cofins if profile else None
                    rate = {
                        ("pis", "cumulativo"): D("0.65"),
                        ("cofins", "cumulativo"): D("3"),
                        ("pis", "nao_cumulativo"): D("1.65"),
                        ("cofins", "nao_cumulativo"): D("7.6"),
                    }.get((tax, regime))
                    if (
                        cfop in SALES
                        and doc.operation != "entrada"
                        and expected is not None
                        and declared.cst == "01"
                        and rate is not None
                        and declared.rate == rate
                    ):
                        bases[f"base_{tax}_{'cum' if regime == 'cumulativo' else 'nc'}"] += expected
                if eligible:
                    review["expected_base"] = None if expected is None else money(expected)
                    status = "unassessed"
                    if expected is not None and all(
                        getattr(item, t).base is not None for t in eligible
                    ):
                        status = (
                            "compatible"
                            if not differences
                            else (
                                "missing_icms"
                                if item.icms.value
                                and all(D(money(v)) == D(money(amount)) for v in differences)
                                else "other_difference"
                            )
                        )
                    review["status"] = status
                    base_counts[status] += 1
                    rows.append(review)
    if not count:
        reasons.add("Nenhum documento ativo no período selecionado.")
    if unknown_status:
        reasons.add(f"Situação fiscal não informada em {unknown_status} documento(s).")
    if duplicates:
        warnings.append(
            f"{duplicates} documento(s) idêntico(s) desconsiderado(s) para evitar duplicidade."
        )
    if any(
        not d.key
        for u in uploads
        for r in (u.get("canonical_payload") or [])
        if start <= (d := Document(**r)).issued <= end
    ):
        warnings.append("Há documentos sem chave: a deduplicação reconhece somente cópias exatas.")
    warnings.append(
        "Totais documentais não certificam enquadramento, créditos ou saldo a recolher."
    )
    if module == "pis_cofins":
        suggestions = {k: money(v) for k, v in bases.items()}
    cfops = [
        {
            "cfop": k,
            "description": CFOPS.get(k, "Operação a classificar"),
            "items": v["items"],
            "amount": money(v["amount"]),
            "missing": v["missing"],
            "revenue_candidate": k in SALES,
        }
        for k, v in sorted(groups.items())
    ]
    result = {
        "version": VERSION,
        "profile": profile.model_dump(mode="json") if profile else None,
        "recalculated": [
            {
                "tax": k.upper(),
                "base": money(v["base"]),
                "gross": money(v["gross"]),
                "items": v["items"],
                "missing": v["missing"],
            }
            for k, v in recalculated.items()
        ],
        "start": str(start),
        "end": str(end),
        "documents": count,
        "excluded": excluded,
        "duplicates": duplicates,
        "months": sorted(months),
        "cfops": cfops,
        "base_review": base_counts,
        "rows": rows,
        "suggestions": suggestions,
        "blockers": sorted(reasons),
        "warnings": warnings,
        "taxes": [
            {
                "tax": k.upper(),
                "declared": money(v["value"]),
                "known": v["known"],
                "missing": v["missing"],
            }
            for k, v in totals.items()
        ],
        "products": [
            {
                "code": k[0],
                "description": k[1],
                "ncm": k[2],
                "cest": k[3],
                "cfops": sorted(v),
                "status": "observado",
            }
            for k, v in products.items()
        ],
        "uploads": [
            {"id": str(u["id"]), "name": u["nome"], "sha256": u["sha256"], "partial": u["parcial"]}
            for u in uploads
        ],
    }
    return {**result, "hash": digest(result)}
