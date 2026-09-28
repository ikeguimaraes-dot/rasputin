from datetime import date
from decimal import Decimal, localcontext

import pytest

from auditoria.assessment import MODULES, calculate, catalog
from auditoria.domain import Profile


def values(module, **overrides):
    result = {
        f["key"]: True if f["kind"] == "bool" else "0"
        for f in MODULES[module]["fields"]
        if not f.get("only_q4")
    }
    result.update(overrides)
    return result


def calc(module, v, month=9, regime=None, **profile):
    regime = regime or MODULES[module]["regimes"][0]
    return calculate(
        module,
        date(2026, month, 1),
        v,
        Profile(regime_federal=regime, valid_from=date(2026, 1, 1), **profile),
    )


def test_simples_segregated_components_and_rounding():
    r = calc(
        "simples",
        values(
            "simples",
            rbt12="180000",
            normal="10000",
            mono="10000",
            st="10000",
            mono_st="10000",
            icms_fora=False,
        ),
    )
    assert r["total_due"] == "1204.00"
    assert r["memory"]["components"]["ICMS"] == "272.00"
    assert r["memory"]["components"]["PIS"] == "22.08"
    assert r["memory"]["band"] == 1


@pytest.mark.parametrize(
    "rbt,band",
    [
        ("180000", 1),
        ("180000.01", 2),
        ("360000", 2),
        ("360000.01", 3),
        ("720000", 3),
        ("1800000", 4),
        ("3600000", 5),
        ("4800000", 6),
    ],
)
def test_simples_band_boundaries(rbt, band):
    r = calc("simples", values("simples", rbt12=rbt, normal="10000", icms_fora=band == 6))
    assert r["memory"]["band"] == band


def test_missing_values_are_never_zero():
    r = calc("real", {"trimestral": True})
    assert r["status"] == "incompleta" and len(r["missing"]) == 10
    assert "total_due" not in r and not r["lines"]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.001", True, {}, "1.000,00"])
def test_invalid_amount_rejected(value):
    with pytest.raises(ValueError):
        calc("simples", values("simples", rbt12="100000", normal=value))


def test_presumido_2026_irpj_q1_csll_q2_uplift():
    v = values("presumido", comercio="1500000")
    first = calc("presumido", v, month=3)
    second = calc("presumido", v, month=6)
    assert first["lines"][0]["base"] == "122000.00"
    assert first["lines"][0]["due"] == "24500.00"
    assert first["lines"][1]["due"] == "16200.00"
    assert second["lines"][1]["due"] == "16470.00"


def test_presumido_mixed_activities_and_unused_limit():
    r = calc(
        "presumido",
        values(
            "presumido",
            comercio="1000000",
            servicos="500000",
            limite_transportado_irpj="250000",
            limite_transportado_csll="250000",
        ),
    )
    assert r["lines"][0]["base"] == "240000.00"
    assert r["lines"][1]["base"] == "280000.00"
    assert r["memory"]["excess_revenue"]["irpj"] == "0.00"


def test_q4_needs_annual_adjustment_not_silently_ordinary_quarter():
    r = calc("presumido", values("presumido", comercio="2000000"), month=12)
    assert r["status"] == "incompleta"
    assert {x["field"] for x in r["missing"]} == {
        "excesso_anual_irpj",
        "excesso_anual_csll",
        "credito_ajuste_irpj",
        "credito_ajuste_csll",
    }


def test_real_loss_cap_and_no_negative_tax():
    r = calc(
        "real",
        values(
            "real",
            lucro_irpj="100000",
            lucro_csll="100000",
            prejuizos="100000",
            base_negativa="100000",
        ),
    )
    assert r["lines"][0]["due"] == "11500.00"
    assert r["lines"][1]["due"] == "6300.00"
    assert r["memory"]["irpj"]["loss_used"] == "30000.00"
    negative = calc("real", values("real", lucro_irpj="-1000", lucro_csll="-1000"))
    assert negative["total_due"] == "0.00"
    assert negative["memory"]["irpj"]["loss_balance"] == "1000.00"


def test_pis_cofins_mixed_regime_and_unused_credits():
    r = calc(
        "pis_cofins",
        values(
            "pis_cofins",
            base_pis_cum="10000",
            base_pis_nc="10000",
            base_cofins_cum="10000",
            base_cofins_nc="10000",
            creditos_pis="300",
            creditos_cofins="100",
        ),
    )
    assert r["lines"][0]["gross"] == "230.00"
    assert r["lines"][0]["due"] == "0.00" and r["lines"][0]["remaining"] == "70.00"
    assert r["lines"][1]["due"] == "960.00"


def test_sp_special_monthly_regime_and_eligibility():
    v = values("icms_sp", receita="100000", st="10000", gorjetas="5000", entradas_st="10000")
    r = calc("icms_sp", v, optante_regime_especial_rest=True)
    assert r["lines"][0]["base"] == "85000.00"
    assert r["total_due"] == "3010.00"
    for kwargs in ({}, {"uf": "RJ", "optante_regime_especial_rest": True}, {"regime": "simples"}):
        with pytest.raises(ValueError):
            calc("icms_sp", v, **kwargs)


def test_reject_unconfirmed_scope_future_year_unknown_and_wrong_period():
    with pytest.raises(ValueError):
        calc("simples", values("simples", elegivel=False, rbt12="1000"))
    with pytest.raises(ValueError):
        calc("real", values("real"), month=8)
    with pytest.raises(ValueError):
        calc("real", values("real", desconhecido=1))
    with pytest.raises(ValueError):
        calculate(
            "real",
            date(2027, 3, 1),
            values("real"),
            Profile(regime_federal="real", valid_from=date(2026, 1, 1)),
        )


def test_determinism_catalog_integrity_and_decimal_context():
    c = catalog()
    assert len(c["sources"]) == 14 and len(c["hash"]) == 64
    for band in c["parameters"]["simples_anexo_i"]:
        assert sum(Decimal(x) for x in band["shares"].values()) == 100
    v = values("real", lucro_irpj="123456.78")
    before = calc("real", v)
    with localcontext() as ctx:
        ctx.prec = 6
        assert calc("real", v) == before


def test_annual_real_additional_threshold_and_prepayments():
    r = calc(
        "real_anual",
        values(
            "real_anual",
            lucro_irpj="300000",
            lucro_csll="300000",
            antecipacoes_irpj="40000",
            antecipacoes_csll="20000",
        ),
        month=12,
    )
    assert r["lines"][0]["gross"] == "51000.00"
    assert r["lines"][0]["due"] == "11000.00"
    assert r["lines"][1]["due"] == "7000.00"


def test_icms_ledger_saldo_creditor_and_special_regime_exclusion():
    r = calc("icms_normal", values("icms_normal", debitos="1000", creditos="1200"), uf="MG")
    assert r["lines"][0]["base"] is None
    assert r["lines"][0]["remaining"] == "200.00"
    assert r["total_due"] == "0.00"
    with pytest.raises(ValueError):
        calc("icms_normal", values("icms_normal"), optante_regime_especial_rest=True)
