"""Conferência documental SP. Hipóteses de cadastro não certificam tributação.

Captura normativa: 29/09/2026. A emissão, NCM e enquadramento informados
continuam sujeitos à conferência com XML/cadastro; não se calcula recolhimento.
"""

import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal

BASE = "https://legislacao.fazenda.sp.gov.br/Paginas/"
POLICY = {
    "version": "sp-restaurante-2026.09.29.1",
    "valid_from": "2026-01-01",
    "as_of": "2026-09-29",
    "sources": {
        "cfop": {"title": "RICMS/SP, Anexo V: CFOP e CST", "url": BASE + "l6an5.aspx"},
        "st": {
            "title": "RICMS/SP, art. 274: documento do substituído",
            "url": BASE + "art274.aspx",
        },
        "st_2026": {
            "title": "Portaria SRE 64/2025, art. 1º, II: revogação do Anexo X em 01/01/2026",
            "url": BASE + "Portaria-SRE-64-de-2025.aspx",
        },
        "st_catalog": {
            "title": "Portaria CAT 68/2019, art. 2º: exclusão da posição 2204 desde 01/02/2020",
            "url": BASE + "Portaria-CAT-68-de-2019.aspx",
        },
        "alcohol": {
            "title": (
                "RC 24368/2021: bebidas alcoólicas excluídas do regime de alimentação; "
                "percentual atual no Decreto 51.597/2007"
            ),
            "url": BASE + "RC24368_2021.aspx",
        },
        "benefit": {
            "title": (
                "RC 33063/2025, itens 6 a 11 (09/06/2026): 4% e distinção entre modelos "
                "de documento"
            ),
            "url": BASE + "RC33063_2025.aspx",
        },
        "rates": {
            "title": "RICMS/SP, arts. 52 a 56: alíquotas internas e exceções",
            "url": BASE + "art052.aspx",
        },
        "loss": {
            "title": "RC 18590/2018: baixa de estoque, CFOP 5927 e ausência de destaque",
            "url": BASE + "RC18590_2018.aspx",
        },
        "pis": {
            "title": "Receita Federal: CST e tabelas da EFD-Contribuições",
            "url": "https://www.gov.br/receitafederal/pt-br/canais_atendimento/fale-conosco/empresa/sped/efd-contribuicoes/efd-contribuicoes-codigos-de-situacao-tributaria-cst-e-demais-tabelas-da-escrituracao",
        },
        "ncm": {
            "title": (
                "Receita Federal: classificação fiscal depende das características da mercadoria"
            ),
            "url": "https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/classificacao-fiscal-de-mercadorias",
        },
    },
}
CFOPS = {
    "5101": "Venda de produção do estabelecimento",
    "5102": "Venda de mercadoria adquirida ou recebida de terceiros",
    "5202": "Devolução de compra para comercialização",
    "5405": "Venda de mercadoria sujeita à ST, na condição de substituído",
    "5919": "Devolução simbólica de mercadoria recebida em consignação",
    "5927": "Baixa de estoque por perda, roubo ou deterioração",
    "5929": "Documento relativo a operação já registrada em documento fiscal",
    "5949": "Outra saída de mercadoria ou prestação não especificada",
}


def normalized(description):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", description.upper())
        if not unicodedata.combining(c)
    )


def is_tip(item):
    return item.cfop == "5949" and "GORJETA" in normalized(item.description)


def category(item):
    if is_tip(item):
        return "Gorjeta (descrição declarada)"
    ncm = item.ncm or ""
    if ncm.startswith(("2203", "2204", "2205", "2206", "2207", "2208")):
        return "Bebida alcoólica (NCM declarado)"
    if ncm.startswith(("2201", "2202")):
        return "Bebida não alcoólica (NCM declarado)"
    if ncm.startswith(("16", "17", "18", "19", "20", "21")):
        return "Alimento/preparação (NCM declarado)"
    return "Classificação a confirmar"


def review(doc, item, profile, add, skip, coverage):
    """Run even for unknown status: findings explicitly ask for documentary review."""
    if not profile or profile.uf != "SP" or profile.regime_federal == "simples":
        return
    if (
        not date.fromisoformat(POLICY["valid_from"])
        <= doc.issued
        <= date.fromisoformat(POLICY["as_of"])
    ):
        skip(
            "D-SP", doc, item, "Conferência SP fora da janela normativa pesquisada (2026 até 29/09)"
        )
        return
    coverage["D-SP"] += 1
    ncm, icms = item.ncm or "", item.icms
    desc = normalized(item.description)

    def flag(code, message, source, severity="revisar", expected=None):
        add(code, doc, item, message, severity, expected=expected, source=POLICY["sources"][source])

    if item.cfop == "5405":
        if icms.cst is not None and icms.cst != "60":
            flag(
                "D01",
                (
                    "CFOP 5405 declara venda por substituído, mas CST ICMS não é 60. "
                    "Conferir o CST e se o produto realmente permanece em ST na "
                    "competência."
                ),
                "cfop",
                expected={"icms_cst_se_substituido": "60"},
            )
        if icms.value is not None and icms.value != 0:
            flag(
                "D01",
                (
                    "CFOP 5405 com ICMS próprio destacado; conferir documento do "
                    "substituído e separar valores de ICMS-ST retido."
                ),
                "st",
            )
        if ncm.startswith(("2205", "2206", "2207", "2208")):
            flag(
                "D02",
                (
                    "Bebida do antigo Anexo X em CFOP 5405 após sua retirada da ST paulista "
                    "em 01/01/2026. Conferir NCM, operação e tratamento do estoque de "
                    "transição."
                ),
                "st_2026",
                "risco",
            )
        elif ncm.startswith("2204"):
            flag(
                "D02",
                (
                    "Vinho em CFOP 5405: posição 2204 excluída da ST paulista desde "
                    "01/02/2020. Conferir a classificação e a operação."
                ),
                "st_catalog",
                "risco",
            )
    if item.cfop == "5927" and icms.value is not None and icms.value != 0:
        flag(
            "D01",
            (
                "Baixa de estoque (CFOP 5927) com ICMS destacado. Conferir a baixa e "
                "eventual estorno de créditos separadamente."
            ),
            "loss",
        )
    if item.cfop in ("5101", "5102") and profile.optante_regime_especial_rest:
        if ncm.startswith(("2203", "2204", "2205", "2206", "2207", "2208")) and icms.rate == 4:
            flag(
                "D03",
                (
                    "NCM declarado de bebida alcoólica com ICMS de 4%: benefício de "
                    "alimentação não abrange essa categoria. Validar o NCM e a alíquota "
                    "própria antes de corrigir."
                ),
                "alcohol",
                "risco",
            )
        # A description alone is insufficient to prescribe a tax rate or a replacement NCM.
        meal = re.search(
            r"\b(RAVIOLLI|RAVIOLI|RISOTTO|TORTELLONI|COUVERT|PAO|ASPARGUI|SPAGHETTI)\b", desc
        )
        if meal and not ncm.startswith("22") and icms.rate in (18, 25):
            flag(
                "D04",
                (
                    "Descrição sugere alimentação com alíquota de 18%/25% em empresa "
                    "optante pelo regime especial. Confirmar produto e modelo fiscal: "
                    "alimentação abrangida usa 4%, observada a vedação de destaque na NF-e "
                    "modelo 55."
                ),
                "benefit",
            )
        if meal and not ncm.startswith("22") and doc.model == 55 and icms.value not in (None, 0):
            flag(
                "D04",
                (
                    "NF-e modelo 55 de possível alimentação abrangida pelo regime especial "
                    "com destaque de ICMS. Confirmar enquadramento e informações adicionais "
                    "obrigatórias."
                ),
                "benefit",
            )
    if item.cfop in ("5101", "5102") and icms.rate is not None and icms.rate > 25:
        flag(
            "D04",
            (
                "Alíquota de ICMS próprio superior a 25% nesta venda: conferir possível "
                "troca entre CST e alíquota, modelo e enquadramento. Não corrigir "
                "apenas pelo cálculo aritmético."
            ),
            "rates",
            "risco",
        )
    suggestions = []
    if re.search(r"^AGUA\b", desc) and not ncm.startswith("2201"):
        suggestions.append(
            "descrição de água com NCM fora da posição 2201; confirmar composição e embalagem"
        )
    if re.search(r"\b(VODKA|STOLICHNAYA)\b", desc) and not ncm.startswith("220860"):
        suggestions.append("descrição sugere vodka, mas o NCM não está na subposição 2208.60")
    if ncm.startswith("2204") and re.search(r"\b(RISOTTO|COUVERT|ENTREGA)\b", desc):
        suggestions.append("descrição de alimento/entrega com NCM da posição de vinhos 2204")
    if not ncm.startswith("22") and re.search(r"\b(CHARDONNAY|CABERNET|GRAPPA)\b", desc):
        suggestions.append("descrição sugere bebida alcoólica com NCM fora do capítulo 22")
    if ncm.startswith("220410") and re.search(r"\bBAROLO\b", desc):
        suggestions.append(
            "descrição sugere vinho tranquilo, mas NCM 2204.10 identifica "
            "espumante; conferir rótulo"
        )
    if suggestions:
        flag(
            "D05",
            "Possível conflito entre descrição e NCM: "
            + "; ".join(suggestions)
            + ". A descrição comercial não basta para classificação definitiva.",
            "ncm",
        )
    if item.pis.cst and item.cofins.cst and item.pis.cst != item.cofins.cst:
        flag(
            "D06",
            (
                "PIS e COFINS com CST diferentes no mesmo item. Confirmar fundamento "
                "específico para o tratamento distinto."
            ),
            "pis",
        )
    basic = {
        "cumulativo": (Decimal("0.65"), Decimal("3")),
        "nao_cumulativo": (Decimal("1.65"), Decimal("7.6")),
    }.get(profile.regime_pis_cofins)
    reference_only = profile.regime_pis_cofins is None and profile.regime_federal == "presumido"
    if reference_only:
        basic = (Decimal("0.65"), Decimal("3"))
    basis = (
        "de referência do regime cumulativo; confirmar o regime de PIS/COFINS"
        if reference_only
        else "do regime declarado"
    )
    # CST consistency does not decide monophase/zero-rate entitlement from the NCM alone.
    if basic:
        for name, rate in zip(("pis", "cofins"), basic, strict=True):
            tax = getattr(item, name)
            if tax.cst == "02" and tax.rate == rate:
                flag(
                    "D06",
                    (
                        f"{name.upper()}: CST 02 (alíquota diferenciada) informado com a "
                        f"alíquota básica {basis}. Conferir CST e fundamento legal."
                    ),
                    "pis",
                )


def operation_rows(documents):
    rows = []
    for doc in documents:
        if doc.status in ("cancelada", "denegada"):
            continue
        for item in doc.items:
            rows.append(
                {
                    "document": doc.key or doc.number,
                    "issued": doc.issued.isoformat(),
                    "code": item.code,
                    "description": item.description,
                    "ncm": item.ncm,
                    "cfop": item.cfop,
                    "nature": CFOPS.get(item.cfop, "Natureza a conferir"),
                    "category": category(item),
                    "icms_rate": str(item.icms.rate) if item.icms.rate is not None else None,
                    "icms_cst": item.icms.cst,
                    "pis_cst": item.pis.cst,
                    "cofins_cst": item.cofins.cst,
                    "value": str(item.value) if item.value is not None else None,
                    "icms_value": str(item.icms.value) if item.icms.value is not None else None,
                    "source": item.source,
                }
            )
    return rows


def operation_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["cfop"] or "", row["category"], row["icms_rate"] or "")].append(row)
    return [
        {
            "cfop": cfop,
            "nature": CFOPS.get(cfop, "Natureza a conferir"),
            "category": category,
            "icms_rate": rate or None,
            "items": len(items),
            **{
                field: str(sum(Decimal(i[field]) for i in items if i[field] is not None))
                if all(i[field] is not None for i in items)
                else None
                for field in ("value", "icms_value")
            },
        }
        for (cfop, category, rate), items in sorted(groups.items())
    ]
