from datetime import date

import pytest

from auditoria.domain import Document, Item, Profile, Rule, Tax


@pytest.fixture
def profile():
    return Profile(regime_federal="presumido", valid_from=date(2026, 1, 1), contribuinte_ipi=False)


@pytest.fixture
def item():
    return Item(
        n_item=1,
        code="P1",
        description="Produto sintético",
        ncm="22010000",
        cfop="5102",
        value="100",
        discount="0",
        freight="0",
        insurance="0",
        other="0",
        icms=Tax(cst="00", base="100", rate="18", value="18"),
        pis=Tax(cst="01", base="100", rate="1.65", value="1.65"),
        cofins=Tax(cst="01", base="100", rate="7.6", value="7.60"),
        source={"file": "sintetico.xml", "line": 1},
    )


@pytest.fixture
def document(item):
    return Document(
        key="1" * 44,
        issued=date(2026, 8, 1),
        status="autorizada",
        operation="saida",
        final_consumer=True,
        recipient_taxpayer=False,
        items=[item],
    )


def approved_rule(code="R05", **changes):
    raw = dict(
        id="synthetic-rule",
        code=code,
        title="REGRA SINTÉTICA — não é orientação fiscal",
        status="aprovada",
        valid_from="2026-01-01",
        regimes=["simples", "presumido", "real"],
        ncm_prefix="2201",
        conditions={"operation": "saida"},
        expected={"pis_cst": ["04"], "cofins_cst": ["04"], "pis_rate": "0", "cofins_rate": "0"},
        source_url="https://example.invalid/fixture",
        legal_basis="Fixture sintética de teste",
        approved_by="tester",
        approved_at="2026-01-01T00:00:00Z",
    )
    raw.update(changes)
    return Rule(**raw)
