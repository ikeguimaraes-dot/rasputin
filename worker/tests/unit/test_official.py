from datetime import date

from auditoria.domain import Document, Item, Profile, Tax
from auditoria.engine import evaluate
from auditoria.official import check_ncm, document_catalog, ncm_table


def test_official_ncm_snapshot_keeps_evidence_and_historical_uncertainty():
    table = ncm_table()
    assert len(table["records"]) > 10000
    snap = {"ncm": table}
    assert check_ncm("01012100", date(2026, 8, 1), snap)[0] == "ok"
    assert check_ncm("99999999", date(2026, 8, 1), snap)[0] == "skip"
    assert check_ncm("99999999", date(2026, 9, 28), snap)[0] == "error"
    assert check_ncm("01012100", date(2027, 1, 1), snap)[0] == "skip"


def test_official_pis_rates_require_declared_modality_and_cst01():
    doc = Document(
        issued=date(2026, 8, 1),
        status="autorizada",
        operation="saida",
        items=[
            Item(
                n_item=1,
                ncm="01012100",
                pis=Tax(cst="01", rate="9"),
                cofins=Tax(cst="06", rate="0"),
            )
        ],
    )
    official = document_catalog([doc.model_dump(mode="json")])
    p = Profile(
        regime_federal="real", regime_pis_cofins="nao_cumulativo", valid_from=date(2026, 1, 1)
    )
    r = evaluate([doc], [p], [], official)
    findings = [f for f in r.findings if f.code == "R05"]
    assert len(findings) == 1
    assert findings[0].expected == {"pis_rate": "1.6500"}
    assert findings[0].source_url.endswith("l10637.htm")
    assert findings[0].rule_id is None
    assert r.summary["coverage"]["R01"] == 1
    assert not [
        f
        for f in evaluate(
            [doc], [p.model_copy(update={"regime_pis_cofins": None})], [], official
        ).findings
        if f.code == "R05"
    ]
    assert not [
        f
        for f in evaluate(
            [doc], [p.model_copy(update={"regime_federal": "simples"})], [], official
        ).findings
        if f.code == "R05"
    ]
