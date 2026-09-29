from decimal import Decimal

import pytest
from conftest import approved_rule

from auditoria.domain import Profile, Tax
from auditoria.engine import evaluate


def codes(result):
    return {f.code for f in result.findings}


@pytest.mark.parametrize("regime", ["simples", "presumido", "real"])
def test_all_regimes_use_approved_context_rules(document, profile, regime):
    profile.regime_federal = regime
    result = evaluate([document], [profile], [approved_rule()])
    assert "R05" in codes(result)
    f = next(f for f in result.findings if f.code == "R05")
    assert f.impact == Decimal("9.25")
    assert f.impact_kind == "potencial_documental"


def test_proposals_never_execute(document, profile):
    rule = approved_rule(status="proposta", approved_by=None, approved_at=None)
    result = evaluate([document], [profile], [rule])
    assert "R05" not in codes(result)
    assert any(s["code"] == "R05" for s in result.skipped)


def test_regime_mismatch_never_uses_other_regime_rate(document, profile):
    rule = approved_rule(regimes=["real"])
    assert "R05" not in codes(evaluate([document], [profile], [rule]))


def test_validity_uses_document_date(document, profile):
    assert "R05" not in codes(
        evaluate([document], [profile], [approved_rule(valid_from="2026-09-01")])
    )
    assert "R05" in codes(evaluate([document], [profile], [approved_rule(valid_to="2026-08-01")]))


def test_same_snapshot_is_reproducible(document, profile):
    rules = [approved_rule()]
    first = evaluate([document], [profile], rules).model_dump_json()
    assert evaluate([document], [profile], rules).model_dump_json() == first
    different = approved_rule(id="r2", expected={"pis_cst": ["01"], "cofins_cst": ["01"]})
    assert "R05" not in codes(evaluate([document], [profile], [different]))
    assert evaluate([document], [profile], rules).model_dump_json() == first


def test_conflicting_rules_skip_instead_of_guessing(document, profile):
    result = evaluate([document], [profile], [approved_rule(), approved_rule(id="other")])
    assert "R05" not in codes(result)
    assert any("Conflito" in s["reason"] for s in result.skipped)


def test_missing_profile_is_not_a_clean_analysis(document):
    result = evaluate([document], [], [approved_rule()])
    assert result.summary["skipped"] > 0
    assert "R05" not in codes(result)


def test_overlapping_profiles_skip(document, profile):
    result = evaluate([document], [profile, profile.model_copy()], [approved_rule()])
    assert "R05" not in codes(result)


def test_c01_divergence_is_review_not_error(document, profile, item):
    other = item.model_copy(deep=True)
    other.n_item = 2
    other.cfop = "5405"
    document.items.append(other)
    result = evaluate([document], [profile], [])
    assert all(f.severity == "revisar" for f in result.findings if f.code == "C01")
    assert len([f for f in result.findings if f.code == "C01"]) == 2


def test_c02_uses_approved_cst_compatibility(document, profile):
    document.items[0].cfop = "5405"
    rule = approved_rule(code="C02", conditions={"cfop": ["5405"]}, expected={"icms_cst": ["60"]})
    assert "C02" in codes(evaluate([document], [profile], [rule]))


def test_c03_exempt_with_value(document, profile):
    document.items[0].icms.cst = "41"
    assert "C03" in codes(evaluate([document], [profile], []))


@pytest.mark.parametrize(("value", "flag"), [("18.05", False), ("18.06", True)])
def test_c04_rounding_tolerance(document, profile, value, flag):
    document.items[0].icms.value = Decimal(value)
    assert ("C04" in codes(evaluate([document], [profile], []))) is flag


def test_missing_tax_is_not_zero(document, profile):
    document.items[0].icms = Tax()
    result = evaluate([document], [profile], [])
    assert "C04" not in codes(result)
    assert any("ICMS" in x["reason"] for x in result.skipped)


def test_c05_zeros_and_c06_wildcard(document, profile):
    document.items[0].cest = "0000000"
    document.items[0].ncm = "99999999"
    assert {"C05", "C06"} <= codes(evaluate([document], [profile], []))


def test_c05_approved_correspondence(document, profile):
    document.items[0].cest = "1234567"
    rule = approved_rule(code="C05", expected={"cest": ["7654321"]})
    assert "C05" in codes(evaluate([document], [profile], [rule]))


def test_c07_non_contributor_review(document, profile):
    document.items[0].ipi.cst = "50"
    assert "C07" in codes(evaluate([document], [profile], []))
    profile.contribuinte_ipi = True
    assert "C07" not in codes(evaluate([document], [profile], []))


def test_c08_nature_requires_review(document, profile):
    document.items[0].cfop = "5949"
    result = evaluate([document], [profile], [])
    assert next(f for f in result.findings if f.code == "C08").severity == "revisar"


def test_c09_declared_method(document, profile):
    profile.metodo_pis_cofins = "com_exclusao_icms"
    assert "C09" in codes(evaluate([document], [profile], []))
    profile.metodo_pis_cofins = "sem_exclusao_icms"
    assert "C09" not in codes(evaluate([document], [profile], []))


def test_r02_outside_st(document, profile):
    document.items[0].cfop = "5405"
    rule = approved_rule(code="R02", expected={"subject_to_st": False})
    assert "R02" in codes(evaluate([document], [profile], [rule]))


def test_r04_context_prevents_b2b_false_positive(document, profile):
    rule = approved_rule(
        code="R04",
        conditions={"operation": "saida", "final_consumer": True, "recipient_taxpayer": False},
        expected={"icms_rate": "4"},
    )
    assert "R04" in codes(evaluate([document], [profile], [rule]))
    document.recipient_taxpayer = True
    document.final_consumer = False
    document.items[0].icms.rate = Decimal("25")
    document.items[0].icms.value = Decimal("25")
    assert "R04" not in codes(evaluate([document], [profile], [rule]))


def test_r04_unknown_consumer_does_not_guess(document, profile):
    document.final_consumer = None
    rule = approved_rule(
        code="R04",
        conditions={"operation": "saida", "final_consumer": True},
        expected={"icms_rate": "4"},
    )
    assert "R04" not in codes(evaluate([document], [profile], [rule]))


def test_cancelled_document_excluded(document, profile):
    document.status = "cancelada"
    document.items[0].ncm = "00000000"
    assert not evaluate([document], [profile], [approved_rule()]).findings


def test_unknown_status_only_consistency(document, profile):
    document.status = "desconhecida"
    assert "R05" not in codes(evaluate([document], [profile], [approved_rule()]))


def test_arbitrary_rule_condition_rejected():
    with pytest.raises(ValueError):
        approved_rule(conditions={"eval": "arbitrary code"})


def test_approval_requires_actor():
    with pytest.raises(ValueError):
        approved_rule(approved_by=None)


def test_invalid_profile_period_rejected():
    with pytest.raises(ValueError):
        Profile(regime_federal="real", valid_from="2026-09-01", valid_to="2026-08-01")


@pytest.mark.parametrize(
    "changes",
    [
        {"expected": {"pis_cst": ["4"]}},
        {"expected": {"pis_rate": "NaN"}},
        {"conditions": {"final_consumer": "false"}},
        {"code": "R02", "expected": {"subject_to_st": "false"}},
        {"conditions": {"cfop": ["123"]}},
    ],
)
def test_rule_contract_rejects_ambiguous_values(changes):
    with pytest.raises(ValueError):
        approved_rule(**changes)


def test_decimal_context_does_not_change_results(document, profile):
    from decimal import ROUND_DOWN, localcontext

    expected = evaluate([document], [profile], [approved_rule()]).model_dump_json()
    with localcontext() as ctx:
        ctx.prec = 8
        ctx.rounding = ROUND_DOWN
        assert evaluate([document], [profile], [approved_rule()]).model_dump_json() == expected


@pytest.mark.parametrize("cst", ["01", "02"])
def test_c09_excludes_own_item_icms_and_explains_difference(document, profile, cst):
    profile.metodo_pis_cofins = "com_exclusao_icms"
    item = document.items[0]
    item.icms.value = Decimal("4")
    item.pis.cst = item.cofins.cst = cst
    item.pis.base = Decimal("96")
    item.cofins.base = Decimal("100")
    second = item.model_copy(deep=True)
    second.n_item = 2
    second.value = Decimal("200")
    second.icms.value = Decimal("50")
    second.pis.base = second.cofins.base = Decimal("150")
    document.items.append(second)
    checks = [f for f in evaluate([document], [profile], []).findings if f.code == "C09"]
    assert len(checks) == 1
    assert checks[0].expected["cofins_base"] == "96.00"
    assert checks[0].expected["diferenca_base"] == "4.00"
    assert "não foi descontado" in checks[0].message
    assert checks[0].impact is None


def test_c09_components_rounding_and_missing_are_not_zero(document, profile):
    profile.metodo_pis_cofins = "com_exclusao_icms"
    item = document.items[0]
    item.discount, item.freight = Decimal("10"), Decimal("5")
    item.insurance, item.other = Decimal("2"), Decimal("3")
    item.icms.value = Decimal("4")
    item.pis.base = item.cofins.base = Decimal("96")
    assert not any(f.code == "C09" for f in evaluate([document], [profile], []).findings)
    item.pis.base = Decimal("96.01")
    assert sum(f.code == "C09" for f in evaluate([document], [profile], []).findings) == 1
    item.icms.value = None
    result = evaluate([document], [profile], [])
    assert not any(f.code == "C09" for f in result.findings)
    assert any(s["code"] == "C09" and "incompletos" in s["reason"] for s in result.skipped)


def test_c09_does_not_apply_to_other_cst_or_negative_calculation(document, profile):
    profile.metodo_pis_cofins = "com_exclusao_icms"
    item = document.items[0]
    item.pis.cst = item.cofins.cst = "06"
    assert not any(f.code == "C09" for f in evaluate([document], [profile], []).findings)
    item.pis.cst = "01"
    item.icms.value = Decimal("101")
    result = evaluate([document], [profile], [])
    assert any(s["code"] == "C09" and "negativa" in s["reason"] for s in result.skipped)
