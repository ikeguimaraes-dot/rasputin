from datetime import date
from decimal import Decimal

from auditoria.engine import evaluate


def findings(document, profile, code):
    return [f for f in evaluate([document], [profile], []).findings if f.code == code]


def test_st_2026_changes_are_dated_and_do_not_apply_to_beer(document, profile):
    item = document.items[0]
    item.cfop, item.ncm = "5405", "22083020"
    item.icms.rate, item.icms.value = Decimal(0), Decimal(0)
    document.status = "desconhecida"
    assert findings(document, profile, "D01")
    assert findings(document, profile, "D02")
    item.ncm = "22030000"
    assert not findings(document, profile, "D02")
    item.ncm = "22083020"
    document.issued = date(2025, 12, 31)
    profile.valid_from = date(2025, 1, 1)
    assert not findings(document, profile, "D02")
    document.issued = date(2026, 10, 1)
    assert not findings(document, profile, "D02")


def test_special_regime_does_not_turn_all_rates_into_four(document, profile):
    profile.optante_regime_especial_rest = True
    item = document.items[0]
    item.ncm, item.description = "22042100", "Vinho tinto sintético"
    item.icms.rate = Decimal(4)
    assert findings(document, profile, "D03")
    item.icms.rate = Decimal(25)
    assert not findings(document, profile, "D03")
    assert not findings(document, profile, "D04")
    item.icms.rate = Decimal(41)
    assert findings(document, profile, "D04")
    item.cfop = "5202"
    assert not findings(document, profile, "D04")


def test_meal_review_requires_option_and_preserves_document_model(document, profile):
    item = document.items[0]
    item.ncm, item.description = "21069090", "Ravioli de queijo sintético"
    assert not findings(document, profile, "D04")
    profile.optante_regime_especial_rest = True
    assert findings(document, profile, "D04")
    item.icms.rate = Decimal(4)
    assert not findings(document, profile, "D04")
    document.model = 55
    assert findings(document, profile, "D04")


def test_non_sales_do_not_imply_zero_icms_rule(document, profile):
    item = document.items[0]
    for cfop in ("5949", "5929", "5919", "5202"):
        item.cfop = cfop
        assert not findings(document, profile, "D01")
    item.cfop = "5927"
    assert findings(document, profile, "D01")
    item.icms.value = Decimal(0)
    assert not findings(document, profile, "D01")


def test_tip_wildcard_is_not_a_merchandise_classification_error(document, profile):
    item = document.items[0]
    item.cfop, item.description, item.ncm = "5949", "GORJETA CONCEDIDA", "99999999"
    assert findings(document, profile, "C06")[0].severity == "revisar"
    item.cfop = "5102"
    assert findings(document, profile, "C06")[0].severity == "erro"


def test_description_conflict_is_review_not_automatic_ncm_replacement(document, profile):
    item = document.items[0]
    item.ncm, item.description = "21069090", "ÁGUA SEM GÁS"
    f = findings(document, profile, "D05")[0]
    assert f.severity == "revisar" and not f.expected and f.impact is None
    item.description = "AGUARDENTE"
    assert not findings(document, profile, "D05")


def test_pis_differentiated_rate_marks_unknown_regime_as_reference(document, profile):
    item = document.items[0]
    item.pis.cst = item.cofins.cst = "02"
    item.pis.rate, item.cofins.rate = Decimal("0.65"), Decimal(3)
    assert all("de referência" in f.message for f in findings(document, profile, "D06"))
    profile.regime_pis_cofins = "cumulativo"
    assert len(findings(document, profile, "D06")) == 2
    item.pis.cst = item.cofins.cst = "06"
    assert not findings(document, profile, "D06")
    item.pis.cst = "01"
    assert len(findings(document, profile, "D06")) == 1


def test_summary_preserves_missing_money_and_return_description(document, profile):
    item = document.items[0]
    item.cfop, item.value = "5202", None
    result = evaluate([document], [profile], [])
    group = result.summary["operations"][0]
    assert group["nature"].startswith("Devolução") and group["value"] is None
    document.status = "cancelada"
    assert evaluate([document], [profile], []).summary["review_rows"] == []


def test_unknown_ipi_is_skipped_instead_of_assumed_non_contributor(document, profile):
    profile.contribuinte_ipi = None
    document.items[0].ipi.cst = "50"
    result = evaluate([document], [profile], [])
    assert not any(f.code == "C07" for f in result.findings)
    assert any(s["code"] == "C07" for s in result.skipped)
