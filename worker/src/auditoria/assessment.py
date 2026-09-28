"""Apuração assistida por período. Valores declarados não são inferidos de notas de saída."""

from __future__ import annotations

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from pathlib import Path

from auditoria.domain import Profile, digest

D = Decimal
VERSION = "2026.09.28.1"
DATA = Path(__file__).parent / "data"


def field(key, label, kind="money", **kwargs):
    return {"key": key, "label": label, "kind": kind, **kwargs}


MODULES = {
    "simples": {
        "title": "Simples Nacional — DAS / Anexo I",
        "regimes": ["simples"],
        "period": "mensal",
        "sources": ["simples"],
        "scope": "Comércio e fornecimento de alimentação enquadrados no Anexo I. "
        "Receitas segregadas já líquidas de cancelamentos e descontos incondicionais.",
        "fields": [
            field("anexo_i", "Enquadramento no Anexo I confirmado", "bool"),
            field("elegivel", "Empresa permanece elegível ao Simples nesta competência", "bool"),
            field(
                "rbt12",
                "RBT12 para determinação da alíquota (proporcionalizada no início de atividade)",
            ),
            field("normal", "Receita sem segregação de PIS/COFINS ou ICMS"),
            field("mono", "Receita com exclusão legal de PIS/COFINS, sem ST de ICMS"),
            field(
                "st", "Receita com ICMS-ST/antecipação com encerramento, sem exclusão de PIS/COFINS"
            ),
            field("mono_st", "Receita com exclusão de PIS/COFINS e ICMS-ST/encerramento"),
            field("icms_fora", "ICMS já deve ser recolhido fora do DAS nesta competência", "bool"),
        ],
    },
    "presumido": {
        "title": "Lucro Presumido — IRPJ e CSLL trimestrais",
        "regimes": ["presumido"],
        "period": "trimestral",
        "sources": ["renda", "csll", "lc224", "in2306"],
        "scope": "Receitas de comércio/alimentação (8% e 12%) e serviços gerais (32%). "
        "Não inclui atividades com percentuais especiais. Valores do trimestre inteiro.",
        "fields": [
            field(
                "elegivel", "Elegibilidade ao Presumido e atividades declaradas confirmadas", "bool"
            ),
            field("comercio", "Receita trimestral de comércio e alimentação"),
            field("servicos", "Receita trimestral de serviços gerais sujeitos a 32%"),
            field(
                "outras_irpj",
                "Acréscimos integrais à base IRPJ (ganhos, receitas financeiras etc.)",
            ),
            field("outras_csll", "Acréscimos integrais à base CSLL"),
            field(
                "limite_transportado_irpj", "Limite não utilizado em trimestres anteriores — IRPJ"
            ),
            field("limite_transportado_csll", "Limite não utilizado desde abril/2026 — CSLL"),
            field("retencoes_irpj", "Retenções/deduções de IRPJ utilizáveis no trimestre"),
            field("retencoes_csll", "Retenções/deduções de CSLL utilizáveis no trimestre"),
            field(
                "excesso_anual_irpj",
                "4º trimestre: parcela excedente após ajuste anual — IRPJ",
                only_q4=True,
            ),
            field(
                "excesso_anual_csll",
                "4º trimestre: parcela excedente após ajuste anual — CSLL",
                only_q4=True,
            ),
            field(
                "credito_ajuste_irpj",
                "4º trimestre: diferença de IRPJ do recálculo dos trimestres anteriores",
                only_q4=True,
            ),
            field(
                "credito_ajuste_csll",
                "4º trimestre: diferença de CSLL do recálculo dos trimestres anteriores",
                only_q4=True,
            ),
        ],
    },
    "real": {
        "title": "Lucro Real — IRPJ e CSLL trimestrais",
        "regimes": ["real"],
        "period": "trimestral",
        "sources": ["renda", "csll", "perdas"],
        "scope": "Lucro Real trimestral de empresa não financeira, sem tratamento excepcional "
        "de prejuízos. Lucros contábeis, adições e exclusões vêm da escrituração.",
        "fields": [
            field("trimestral", "Empresa optante pelo Lucro Real trimestral", "bool"),
            field("lucro_irpj", "Resultado contábil de partida para o IRPJ", "signed"),
            field("adicoes_irpj", "Adições fiscais ao IRPJ"),
            field("exclusoes_irpj", "Exclusões fiscais do IRPJ"),
            field("prejuizos", "Saldo de prejuízos fiscais elegíveis anteriores"),
            field("lucro_csll", "Resultado contábil de partida para a CSLL", "signed"),
            field("adicoes_csll", "Adições à CSLL"),
            field("exclusoes_csll", "Exclusões da CSLL"),
            field("base_negativa", "Saldo de base negativa de CSLL elegível anterior"),
            field("retencoes_irpj", "Retenções/deduções de IRPJ utilizáveis"),
            field("retencoes_csll", "Retenções/deduções de CSLL utilizáveis"),
        ],
    },
    "pis_cofins": {
        "title": "PIS e COFINS — apuração mensal",
        "regimes": ["presumido", "real"],
        "period": "mensal",
        "sources": ["pis", "cofins", "cumulativo", "pis_cumulativo", "lc224"],
        "scope": "Bases segregadas das contribuições cumulativas e não cumulativas às alíquotas "
        "gerais. Débitos especiais e créditos são informados após enquadramento legal.",
        "fields": [
            field("bases_conferidas", "Bases líquidas e tratamentos especiais conferidos", "bool"),
            field("base_pis_cum", "Base de PIS cumulativo (0,65%)"),
            field("base_cofins_cum", "Base de COFINS cumulativa (3%)"),
            field("base_pis_nc", "Base de PIS não cumulativo (1,65%)"),
            field("base_cofins_nc", "Base de COFINS não cumulativa (7,6%)"),
            field("outros_pis", "Outros débitos PIS (regimes/alíquotas especiais)"),
            field("outros_cofins", "Outros débitos COFINS (regimes/alíquotas especiais)"),
            field("creditos_pis", "Créditos legais de PIS utilizáveis, incluindo saldo anterior"),
            field(
                "creditos_cofins", "Créditos legais de COFINS utilizáveis, incluindo saldo anterior"
            ),
            field("retencoes_pis", "Retenções de PIS utilizáveis"),
            field("retencoes_cofins", "Retenções de COFINS utilizáveis"),
        ],
    },
    "icms_sp": {
        "title": "ICMS SP — regime especial de restaurantes",
        "regimes": ["presumido", "real"],
        "period": "mensal",
        "sources": ["sp_rest"],
        "scope": "Optante paulista pelo Decreto 51.597/2007. Percentual mensal de 4%; "
        "não corresponde à alíquota a destacar no item da nota.",
        "fields": [
            field("condicoes", "Opção e condições dos arts. 1º e 2º atendidas", "bool"),
            field("receita", "Receita bruta mensal antes das exclusões abaixo"),
            field("cancelamentos", "Vendas canceladas"),
            field("descontos", "Descontos incondicionais"),
            field("ipi", "IPI incluído na receita informada"),
            field("st", "Receitas com retenção anterior de ICMS-ST"),
            field("imunidade", "Receitas não tributadas por disposição constitucional"),
            field(
                "gorjetas", "Gorjetas elegíveis à exclusão, respeitando condições e limite de 10%"
            ),
            field("entradas_st", "Entradas com ST elegíveis à dedução de 3,9% (art. 1º, §4º)"),
        ],
    },
}

MODULES["real_anual"] = {
    **MODULES["real"],
    "title": "Lucro Real anual — balanço acumulado / ajuste",
    "period": "anual_acumulado",
    "sources": ["renda", "csll", "perdas", "renda_anual"],
    "scope": "Balanço/balancete de janeiro até a competência, para empresa com ano completo. "
    "Suspensão/redução durante o ano e ajuste em dezembro. Não some saldos mensais.",
    "fields": [field("anual", "Opção anual e balanço acumulado regular confirmados", "bool")]
    + [f for f in MODULES["real"]["fields"] if f["key"] != "trimestral"]
    + [
        field("antecipacoes_irpj", "IRPJ efetivamente antecipado nos meses anteriores"),
        field("antecipacoes_csll", "CSLL efetivamente antecipada nos meses anteriores"),
    ],
}
MODULES["icms_normal"] = {
    "title": "ICMS — confronto de débitos e créditos da escrituração",
    "period": "mensal",
    "regimes": ["simples", "presumido", "real"],
    "sources": ["icms_geral"],
    "scope": "Saldo do ICMS próprio na UF cadastrada a partir da escrituração conferida. "
    "Não classifica produtos nem determina alíquotas, ST, FCP ou DIFAL.",
    "fields": [
        field("normal", "Regime normal de ICMS aplicável (inclusive fora do DAS)", "bool"),
        field("debitos", "Débitos de ICMS próprio da escrituração"),
        field("estornos_creditos", "Estornos de créditos"),
        field("outros_debitos", "Outros débitos e ajustes devedores"),
        field("creditos", "Créditos admitidos no período"),
        field("estornos_debitos", "Estornos de débitos"),
        field("outros_creditos", "Outros créditos e ajustes credores"),
        field("saldo_anterior", "Saldo credor transportado do período anterior"),
    ],
}


def catalog():
    params = json.loads((DATA / "parameters.json").read_text())
    sources = json.loads((DATA / "sources.json").read_text())
    content = {
        "version": VERSION,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "parameters": params,
        "sources": sources,
        "modules": MODULES,
    }
    return {**content, "hash": digest(content)}


def money(v):
    return str(D(v).quantize(D(".01"), rounding=ROUND_HALF_UP))


def calculate(module: str, period: date, values: dict, profile: Profile):
    with localcontext() as ctx:
        ctx.prec = 38
        ctx.rounding = ROUND_HALF_UP
        return _calculate(module, period, values, profile)


def _calculate(module, period, values, profile):
    if module not in MODULES:
        raise ValueError("Módulo de apuração desconhecido")
    if period.year != 2026 or period.day != 1:
        raise ValueError(
            "Informe o primeiro dia de uma competência de 2026; outras vigências não publicadas"
        )
    spec = MODULES[module]
    if profile.regime_federal not in spec["regimes"]:
        raise ValueError("Módulo incompatível com o regime vigente do cliente")
    if spec["period"] == "trimestral" and period.month not in (3, 6, 9, 12):
        raise ValueError(
            "Selecione março, junho, setembro ou dezembro e informe o trimestre completo"
        )
    if not profile.valid_from <= period or (profile.valid_to and profile.valid_to < period):
        raise ValueError("Perfil não vigente")
    if module == "icms_sp" and (profile.uf != "SP" or not profile.optante_regime_especial_rest):
        raise ValueError("Regime especial exige perfil paulista e opção declarada")
    fields = [f for f in spec["fields"] if not f.get("only_q4") or period.month == 12]
    unknown = set(values) - {f["key"] for f in spec["fields"]}
    if unknown:
        raise ValueError("Campos desconhecidos: " + ", ".join(sorted(unknown)))
    v, missing = {}, []
    for f in fields:
        raw = values.get(f["key"])
        if raw is None or raw == "":
            missing.append({"field": f["key"], "label": f["label"]})
            continue
        if f["kind"] == "bool":
            if not isinstance(raw, bool):
                raise ValueError(f"{f['label']}: informe sim ou não")
            v[f["key"]] = raw
        else:
            try:
                if isinstance(raw, bool):
                    raise ValueError()
                amount = D(str(raw))
                if not amount.is_finite() or abs(amount) > D("1000000000000"):
                    raise ValueError()
                if f["kind"] != "signed" and amount < 0:
                    raise ValueError()
                if amount != amount.quantize(D(".01")):
                    raise ValueError()
                v[f["key"]] = amount
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"{f['label']}: informe valor em reais com até 2 casas") from exc
    c = catalog()
    result = {
        "module": module,
        "title": spec["title"],
        "period": str(period),
        "period_type": spec["period"],
        "status": "incompleta" if missing else "calculada",
        "missing": missing,
        "lines": [],
        "memory": {},
        "warnings": [],
        "scope": spec["scope"],
        "catalog_version": c["version"],
        "catalog_hash": c["hash"],
        "sources": [s for s in c["sources"] if s["id"] in spec["sources"]],
    }
    if missing:
        return result
    for key in ("elegivel", "anexo_i", "trimestral", "anual", "bases_conferidas", "condicoes"):
        if key in v and not v[key]:
            raise ValueError(
                "Condição de aplicação não confirmada: "
                + next(f["label"] for f in fields if f["key"] == key)
            )
    p = c["parameters"]

    def line(tax, base, gross, deductions=0, **extra):
        gross, deductions = D(money(gross)), D(money(deductions))
        result["lines"].append(
            {
                "tax": tax,
                "base": money(base) if base is not None else None,
                "gross": money(gross),
                "deductions": money(deductions),
                "due": money(max(D(0), gross - deductions)),
                "remaining": money(max(D(0), deductions - gross)),
                **extra,
            }
        )

    if module == "simples":
        r = v["rbt12"]
        if r <= 0 or r > D("4800000"):
            raise ValueError(
                "RBT12 deve estar entre 0,01 e 4.800.000; proporcionalize no início de atividade"
            )
        band = next(b for b in p["simples_anexo_i"] if r <= D(b["limit"]))
        if band["number"] == 6 and not v["icms_fora"]:
            raise ValueError(
                "Sexta faixa com ICMS ainda no DAS exige cálculo específico do "
                "sublimite; não aplicar exclusão automática"
            )
        effective = (r * D(band["rate"]) / 100 - D(band["deduction"])) / r
        shares = {k: D(s) / 100 for k, s in band["shares"].items()}
        bases = {k: v[k] for k in ("normal", "mono", "st", "mono_st")}
        detail = []
        components = {k: D(0) for k in shares}
        for kind, revenue in bases.items():
            factors = dict(shares)
            if kind in ("mono", "mono_st"):
                factors["PIS"] = factors["COFINS"] = D(0)
            if kind in ("st", "mono_st") or v["icms_fora"]:
                factors["ICMS"] = D(0)
            for tax, factor in factors.items():
                components[tax] += revenue * effective * factor
            detail.append(
                {
                    "segregation": kind,
                    "revenue": money(revenue),
                    "effective_rate": str(effective * sum(factors.values()) * 100),
                    "tax": money(revenue * effective * sum(factors.values())),
                }
            )
        total = sum((D(money(x)) for x in components.values()), D(0))
        line("DAS", sum(bases.values()), total)
        result["memory"] = {
            "band": band["number"],
            "nominal_rate": band["rate"],
            "deduction": band["deduction"],
            "effective_rate": str(effective * 100),
            "segregations": detail,
            "components": {k: money(x) for k, x in components.items()},
        }
        result["warnings"].append(
            "Segregação depende do enquadramento legal dos produtos; NCM "
            "isolado não comprova monofasia/ST. Não gera nem transmite PGDAS-D."
        )
        if v["icms_fora"]:
            result["warnings"].append(
                "ICMS fora do DAS não está incluído neste valor; requer apuração estadual separada."
            )
    elif module == "presumido":
        revenue = v["comercio"] + v["servicos"]
        bases = {}
        excesses = {}
        quarter = period.month // 3
        for tax in ("irpj", "csll"):
            rate = p["income"]["presumption_" + tax]
            transported = v["limite_transportado_" + tax]
            max_previous = D(p["income"]["quarter_revenue_threshold"]) * max(
                0, quarter - (2 if tax == "csll" else 1)
            )
            if transported > max_previous:
                raise ValueError("Limite transportado supera os trimestres anteriores elegíveis")
            excess = max(D(0), revenue - D(p["income"]["quarter_revenue_threshold"]) - transported)
            if tax == "csll" and quarter == 1:
                excess = D(0)
            if quarter == 4:
                excess = v["excesso_anual_" + tax]
            if excess > revenue:
                raise ValueError("Parcela excedente não pode superar a receita trimestral")
            regular = v["comercio"] * D(rate) + v["servicos"] * D(
                p["income"]["presumption_services"]
            )
            uplift = regular / revenue * excess * D(p["income"]["uplift"]) if revenue else D(0)
            bases[tax] = regular + uplift + v["outras_" + tax]
            excesses[tax] = money(excess)
            gross = (
                bases[tax] * D(p["income"]["csll"])
                if tax == "csll"
                else irpj(bases[tax], 3, p["income"])
            )
            deductions = v["retencoes_" + tax] + (
                v["credito_ajuste_" + tax] if quarter == 4 else D(0)
            )
            line(tax.upper(), bases[tax], gross, deductions)
        result["memory"] = {
            "revenue": money(revenue),
            "excess_revenue": excesses,
            "additional_irpj_threshold": "60000.00",
            "presumption_uplift": "10%",
        }
        result["warnings"].append(
            "Limites transportados e ajuste anual dependem das apurações "
            "anteriores. Na CSLL de 2026, a majoração começa no 2º trimestre."
        )
    elif module in ("real", "real_anual"):
        memory = {}
        for tax, loss in [("irpj", "prejuizos"), ("csll", "base_negativa")]:
            adjusted = v["lucro_" + tax] + v["adicoes_" + tax] - v["exclusoes_" + tax]
            offset = min(v[loss], max(D(0), adjusted) * D(p["income"]["loss_limit"]))
            base = max(D(0), adjusted - offset)
            months = period.month if module == "real_anual" else 3
            gross = (
                irpj(base, months, p["income"]) if tax == "irpj" else base * D(p["income"]["csll"])
            )
            deductions = v["retencoes_" + tax]
            if module == "real_anual":
                deductions += v["antecipacoes_" + tax]
            line(tax.upper(), base, gross, deductions)
            memory[tax] = {
                "adjusted": money(adjusted),
                "loss_used": money(offset),
                "loss_balance": money(v[loss] - offset + max(D(0), -adjusted)),
            }
        result["memory"] = memory
        result["warnings"].append(
            "Compensação de prejuízos limitada a 30% da base positiva. "
            "Escrituração e elegibilidade dos saldos devem ser conferidas; não inclui incentivos."
        )
        if module == "real_anual":
            result["warnings"].append(
                "Dados e retenções são acumulados de janeiro até a competência. "
                "Durante o ano, excedentes não são automaticamente restituíveis. "
                "Saldos de prejuízos informados referem-se a anos anteriores."
            )
    elif module == "pis_cofins":
        for tax in ("pis", "cofins"):
            rate_c = p["contributions"][tax + "_cumulative"]
            rate_nc = p["contributions"][tax + "_noncumulative"]
            cum, nc = v["base_" + tax + "_cum"], v["base_" + tax + "_nc"]
            gross = cum * D(rate_c) + nc * D(rate_nc) + v["outros_" + tax]
            line(
                tax.upper(),
                cum + nc,
                gross,
                v["creditos_" + tax] + v["retencoes_" + tax],
                cumulative_base=money(cum),
                noncumulative_base=money(nc),
            )
        result["warnings"].append(
            "Bases já devem refletir exclusões cabíveis. Benefícios, bebidas "
            "frias e mudanças da LC 224/2025 não são presumidos pela descrição do produto; "
            "débitos especiais precisam ser incluídos."
        )
    elif module == "icms_normal":
        if not v["normal"] or profile.optante_regime_especial_rest:
            raise ValueError("Confirme o regime normal e use perfil sem opção pelo regime especial")
        debit = v["debitos"] + v["estornos_creditos"] + v["outros_debitos"]
        credit = v["creditos"] + v["estornos_debitos"] + v["outros_creditos"] + v["saldo_anterior"]
        line("ICMS-" + profile.uf, None, debit, credit)
        result["memory"] = {"debits": money(debit), "credits": money(credit), "uf": profile.uf}
        result["warnings"].append(
            "Resultado limitado ao ICMS próprio escriturado. "
            "Regras estaduais de incidência, benefícios e créditos precisam "
            "estar refletidas nos valores informados."
        )
    elif module == "icms_sp":
        exclusions = sum(
            (v[k] for k in ("cancelamentos", "descontos", "ipi", "st", "imunidade", "gorjetas")),
            D(0),
        )
        if exclusions > v["receita"]:
            raise ValueError("Exclusões excedem a receita informada")
        base = v["receita"] - exclusions
        line(
            "ICMS-SP",
            base,
            base * D(p["icms_sp"]["rate"]),
            v["entradas_st"] * D(p["icms_sp"]["eligible_st_entry_deduction"]),
        )
        result["memory"] = {
            "monthly_rate": "4",
            "eligible_st_entry_deduction_rate": "3.9",
            "exclusions": money(exclusions),
        }
        result["warnings"].append(
            "Dedução de 3,9% restrita às entradas do art. 1º, §4º. Saldo "
            "excedente não representa automaticamente crédito transportável. "
            "Obrigações fora do regime não incluídas."
        )
    result["total_due"] = money(sum((D(x["due"]) for x in result["lines"]), D(0)))
    result["notice"] = (
        "Memória de apuração do módulo selecionado com dados declarados. "
        "Não emite guias, não transmite declarações e não comprova recolhimento."
    )
    return result


def irpj(base, months, parameters):
    return base * D(parameters["irpj"]) + max(
        D(0), base - D(parameters["additional_monthly_threshold"]) * months
    ) * D(parameters["additional_irpj"])
