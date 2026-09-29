"""Cenário integrado SINTÉTICO inspirado na proposta; não valida legislação real."""

from datetime import date
from decimal import Decimal

from conftest import approved_rule

from auditoria.domain import Document, Item, Profile, Tax
from auditoria.engine import evaluate


def make_item(n, code, **changes):
    raw = dict(
        n_item=n,
        code=code,
        description=code,
        ncm="22010000",
        cfop="5405",
        value="100",
        discount="0",
        freight="0",
        insurance="0",
        other="0",
        icms=Tax(cst="00", base="100", rate="0", value="0"),
        pis=Tax(cst="01", base="100", rate="1.65", value="1.65"),
        cofins=Tax(cst="01", base="100", rate="7.6", value="7.60"),
        ipi=Tax(cst="50"),
        source={"file": "gold-sintetico.xml", "line": n},
    )
    raw.update(changes)
    return Item(**raw)


def test_restaurant_scenario_with_b2b_negative_control():
    items = [
        make_item(1, "Água"),
        make_item(2, "Água", cfop="5102"),
        make_item(3, "Café preparado", ncm="21069090"),
        make_item(4, "Black Label", ncm="22083020"),
        make_item(
            5,
            "Vinho",
            ncm="22042100",
            cest="0000000",
            icms=Tax(cst="41", base="100", rate="18", value="18"),
        ),
        make_item(6, "Gorjeta", cfop="5949"),
        make_item(
            7,
            "Prato",
            cfop="5102",
            ncm="21069090",
            icms=Tax(cst="00", base="100", rate="18", value="18"),
        ),
    ]
    document = Document(
        key="1" * 44,
        issued=date(2026, 8, 10),
        operation="saida",
        status="autorizada",
        final_consumer=True,
        recipient_taxpayer=False,
        items=items,
    )
    b2b = Document(
        key="2" * 44,
        issued=date(2026, 8, 10),
        operation="saida",
        status="autorizada",
        final_consumer=False,
        recipient_taxpayer=True,
        items=[
            make_item(
                1,
                "Vinho B2B",
                ncm="22042100",
                cfop="5102",
                icms=Tax(cst="00", base="100", rate="25", value="25"),
            )
        ],
    )
    rules = [
        approved_rule(),
        approved_rule(
            id="c02",
            code="C02",
            ncm_prefix="",
            conditions={"cfop": ["5405"]},
            expected={"icms_cst": ["60"]},
        ),
        approved_rule(id="r02a", code="R02", ncm_prefix="2106", expected={"subject_to_st": False}),
        approved_rule(id="r02b", code="R02", ncm_prefix="2208", expected={"subject_to_st": False}),
        approved_rule(
            id="r04",
            code="R04",
            ncm_prefix="",
            conditions={
                "operation": "saida",
                "final_consumer": True,
                "recipient_taxpayer": False,
                "special_regime": True,
            },
            expected={"icms_rate": "4"},
        ),
    ]
    profile = Profile(
        regime_federal="presumido",
        valid_from="2026-01-01",
        optante_regime_especial_rest=True,
        contribuinte_ipi=False,
    )
    result = evaluate([document, b2b], [profile], rules)
    found = {(f.code, f.product) for f in result.findings}
    assert {
        ("C01", "Água"),
        ("R02", "Café preparado"),
        ("R02", "Black Label"),
        ("C02", "Água"),
        ("R05", "Água"),
        ("C05", "Vinho"),
        ("C03", "Vinho"),
        ("C08", "Gorjeta"),
        ("C07", "Prato"),
        ("R04", "Prato"),
    } <= found
    assert ("R04", "Vinho B2B") not in found
    assert next(
        f.impact for f in result.findings if f.code == "R04" and f.product == "Prato"
    ) == Decimal("14.00")
    assert result.model_dump_json() == evaluate([document, b2b], [profile], rules).model_dump_json()
