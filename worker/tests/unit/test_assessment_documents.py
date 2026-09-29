from datetime import date

import pytest

from auditoria.assessment_documents import consolidate, period_bounds
from auditoria.domain import Document, Item, Profile, Tax

PROFILE = Profile(
    regime_federal="presumido",
    valid_from=date(2026, 1, 1),
    metodo_pis_cofins="com_exclusao_icms",
    regime_pis_cofins="cumulativo",
)


def upload(**changes):
    item = Item(
        n_item=1,
        description="Produto",
        cfop="5102",
        value="1992",
        discount="0",
        freight="0",
        insurance="0",
        other="0",
        icms=Tax(value="498"),
        pis=Tax(cst="01", rate="0.65", base="1992"),
        cofins=Tax(cst="01", rate="3", base="1992"),
    )
    doc = Document(
        number="1438", issued=date(2026, 8, 1), operation="saida", status="autorizada", items=[item]
    )
    return {
        "id": "one",
        "nome": "origem",
        "sha256": "hash",
        "parcial": False,
        "canonical_payload": [doc.model_dump(mode="json")],
        **changes,
    }


def run(uploads):
    return consolidate(uploads, "pis_cofins", date(2026, 8, 1), PROFILE)


def test_recovered_example_and_exact_duplicates():
    a, b = upload(), upload(id="two")
    b["canonical_payload"][0]["items"][0]["source"] = {"file": "copy"}
    result = run([a, b])
    assert result["documents"] == 1 and result["duplicates"] == 1
    assert result["base_review"]["missing_icms"] == 1
    assert result["rows"][0]["expected_base"] == "1494.00"
    assert result["rows"][0]["pis_recomputed"] == "9.71"
    assert result["suggestions"] == {"base_pis_cum": "1494.00", "base_cofins_cum": "1494.00"}
    assert result["taxes"][0]["declared"] == "498.00"
    assert result["taxes"][1]["missing"] == 1


def test_missing_composition_never_turns_into_zero():
    data = upload(parcial=True)
    data["canonical_payload"][0]["items"][0]["freight"] = None
    result = run([data])
    assert result["blockers"]
    assert result["suggestions"] == {}
    assert result["base_review"]["unassessed"] == 1
    assert result["rows"][0]["expected_base"] is None
    assert result["cfops"][0]["missing"] == 1


@pytest.mark.parametrize("cfop", ["5202", "5927", "5929", "5949", "1102"])
def test_non_sales_are_not_suggested_as_revenue(cfop):
    data = upload()
    data["canonical_payload"][0]["items"][0]["cfop"] = cfop
    assert run([data])["suggestions"] == {}


def test_cst02_not_silently_treated_as_general_rate():
    data = upload()
    item = data["canonical_payload"][0]["items"][0]
    item["pis"]["cst"] = item["cofins"]["cst"] = "02"
    result = run([data])
    assert result["suggestions"] == {}
    assert result["base_review"]["missing_icms"] == 1


def test_conflicting_access_keys_stop_consolidation():
    a, b = upload(), upload(id="two")
    a["canonical_payload"][0]["key"] = b["canonical_payload"][0]["key"] = "1" * 44
    b["canonical_payload"][0]["items"][0]["value"] = "2000"
    with pytest.raises(ValueError, match="divergente"):
        run([a, b])


def test_cancelled_out_of_period_and_unknown_status():
    a, b, c = upload(), upload(id="two"), upload(id="three")
    a["canonical_payload"][0]["status"] = "cancelada"
    b["canonical_payload"][0]["issued"] = "2026-07-31"
    c["canonical_payload"][0]["status"] = "desconhecida"
    result = run([a, b, c])
    assert result["documents"] == 1 and result["excluded"] == 1
    assert any("Situação" in b for b in result["blockers"])
    assert period_bounds("presumido", date(2026, 9, 1)) == (date(2026, 7, 1), date(2026, 9, 30))
    with pytest.raises(ValueError):
        period_bounds("presumido", date(2026, 8, 1))
