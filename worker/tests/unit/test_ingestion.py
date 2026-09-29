import struct
from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

import openpyxl
import pytest

from auditoria.ingestion.biff import recover, rk
from auditoria.ingestion.sheets import headers, ingest_sheet, preview
from auditoria.ingestion.xml import ingest_xml, parse_xml


def xml_data(cnpj="11111111000111"):
    return f"""<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{"1" * 44}">
    <ide><mod>65</mod><serie>1</serie><nNF>123</nNF>
    <dhEmi>2026-08-01T12:00:00-03:00</dhEmi><tpNF>1</tpNF>
    <indFinal>1</indFinal></ide>
    <emit><CNPJ>{cnpj}</CNPJ></emit><dest><indIEDest>9</indIEDest></dest>
    <det nItem="1"><prod><cProd>P1</cProd><xProd>Água sintética</xProd>
    <NCM>22010000</NCM><CFOP>5102</CFOP><vProd>100.00</vProd></prod>
    <imposto><ICMS><ICMS00><CST>00</CST><vBC>100</vBC><pICMS>18</pICMS><vICMS>18</vICMS></ICMS00></ICMS>
    <IBSCBS><cClassTrib>000001</cClassTrib></IBSCBS></imposto></det></infNFe></NFe>
    <protNFe><infProt><cStat>100</cStat></infProt></protNFe></nfeProc>""".encode()


def test_nfe_namespace_decimal_and_provenance():
    d = parse_xml(xml_data(), "nota.xml", "11111111000111")
    assert d.issued == date(2026, 8, 1)
    assert d.items[0].icms.rate == Decimal("18")
    assert d.items[0].discount is None
    assert d.items[0].source["line"] > 0
    assert d.recipient_taxpayer is False
    assert "cClassTrib" in d.items[0].ibs_cbs["xml"]


def test_wrong_issuer_rejected():
    with pytest.raises(ValueError, match="Emitente"):
        parse_xml(xml_data(), "n.xml", "22222222000122")


def test_external_entities_rejected():
    with pytest.raises(ValueError, match="DTD"):
        parse_xml(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x/>', "x.xml")


def test_zip_duplicate_and_corrupt_are_reported():
    b = BytesIO()
    with ZipFile(b, "w") as z:
        z.writestr("one.xml", xml_data())
        z.writestr("two.xml", xml_data())
        z.writestr("broken.xml", "<")
    r = ingest_xml(b.getvalue(), "lote.zip")
    assert len(r.documents) == 1 and r.partial and r.discarded == 1
    assert any("duplicada" in s for s in r.warnings)


def test_zip_path_traversal_rejected():
    b = BytesIO()
    with ZipFile(b, "w") as z:
        z.writestr("../escape.xml", xml_data())
    with pytest.raises(ValueError, match="Caminho"):
        ingest_xml(b.getvalue(), "x.zip")


def test_multiline_headers_and_decimal_comma():
    names, signature = headers([["Produto", "ICMS", None], ["Descrição", "Base", "Alqt"]], 2)
    assert names == ["Produto / Descrição", "ICMS / Base", "ICMS / Alqt"]
    assert len(signature) == 64
    content = (
        "Data;Descrição;Valor;NCM\n01/08/2026;Água;1.234,56;22010000\ninválida;X;10;22010000"
    ).encode()
    r = ingest_sheet(content, "x.csv", {"issued": 0, "description": 1, "value": 2, "ncm": 3})
    assert r.documents[0].items[0].value == Decimal("1234.56")
    assert r.discarded == 1 and r.partial


def test_xlsx_dates_and_mapping():
    wb = openpyxl.Workbook()
    s = wb.active
    s.append(["Data", "Descrição", "Valor"])
    s.append([date(2026, 8, 1), "Água", 10])
    b = BytesIO()
    wb.save(b)
    p = preview(b.getvalue(), "x.xlsx")
    assert p["rows"] == 1
    r = ingest_sheet(b.getvalue(), "x.xlsx", {"issued": 0, "description": 1, "value": 2})
    assert r.documents[0].issued == date(2026, 8, 1)


def test_missing_required_mapping_rejected():
    with pytest.raises(ValueError, match="Mapeie"):
        ingest_sheet(b"data,descricao,valor\n", "x.csv", {"issued": 0})


def test_biff_truncated_numeric_recovery():
    def rec(k, p):
        return struct.pack("<HH", k, len(p)) + p

    bof = rec(0x809, struct.pack("<HH", 0x600, 0x10))
    number = rec(0x203, struct.pack("<HHHd", 0, 0, 0, 123.45))
    truncated = struct.pack("<HH", 0x203, 14) + b"\x00"
    books, warnings = recover(b"\0" * 512 + bof + number + truncated)
    assert books["Recuperada 1"][0][0] == 123.45
    assert any("truncado" in w for w in warnings)
    assert rk((42 << 2) | 2) == 42


def test_biff_sst_continue_unicode():
    def rec(k, p):
        return struct.pack("<HH", k, len(p)) + p

    global_bof = rec(0x809, struct.pack("<HH", 0x600, 0x5))
    sst = rec(0xFC, struct.pack("<IIHB", 1, 1, 4, 0) + b"ab")
    continuation = rec(0x3C, b"\x01" + "çd".encode("utf-16-le"))
    sheet = rec(0x809, struct.pack("<HH", 0x600, 0x10))
    cell = rec(0xFD, struct.pack("<HHHI", 0, 0, 0, 0))
    books, _ = recover(b"\0" * 512 + global_bof + sst + continuation + sheet + cell)
    assert books["Recuperada 1"][0][0] == "abçd"


def test_biff_recovered_dates_respect_1904_and_do_not_convert_amounts():
    def rec(k, p):
        return struct.pack("<HH", k, len(p)) + p

    global_bof = rec(0x809, struct.pack("<HH", 0x600, 0x5))
    modes = rec(0x22, struct.pack("<H", 1))
    formats = rec(0xE0, struct.pack("<HH", 0, 14)) + rec(0xE0, struct.pack("<HH", 0, 0))
    sheet = rec(0x809, struct.pack("<HH", 0x600, 0x10))
    cells = rec(0x203, struct.pack("<HHHd", 0, 0, 0, 1))
    cells += rec(0x203, struct.pack("<HHHd", 0, 1, 1, 45000))
    books, _ = recover(b"\0" * 512 + global_bof + modes + formats + sheet + cells)
    row = books["Recuperada 1"][0]
    assert row[0].date() == date(1904, 1, 2)
    assert row[1] == 45000


def test_conference_autodetection_signature_and_incomplete_row(monkeypatch):
    from auditoria.ingestion import sheets

    labels = [None] * 48
    for col, value in sheets.CONFERENCE_LABELS.items():
        labels[col] = value
    groups = [None] * 48
    for col, value in ((24, "ICMS"), (36, "IPI"), (40, "PIS"), (44, "COFINS")):
        groups[col] = value
    valid = [None] * 48
    valid[0], valid[1], valid[2] = date(2026, 8, 1), 123, 5102
    valid[5], valid[13], valid[19] = "11111111000111", "Produto sintético", 12
    rows = [["Título"], ["Empresa sintética"], ["Período"], [], groups, labels, valid, valid[:19]]
    monkeypatch.setattr(sheets, "workbook", lambda *_: ({"Recuperada 1": rows}, ["Parcial"], True))
    p = sheets.preview(b"", "teste.xls")
    assert p["header_rows"] == 6 and p["suggested_mapping"]["pis.cst"] == 40
    rows[1] = ["Outra empresa sintética"]
    assert sheets.preview(b"", "teste.xls")["signature"] == p["signature"]
    result = sheets.ingest_sheet(b"", "teste.xls", p["suggested_mapping"], header_rows=6)
    assert result.read == 1 and result.discarded == 1 and result.partial
    assert result.documents[0].recipient_doc == "11111111000111"
    assert result.documents[0].issuer_doc is None
    assert result.documents[0].status == "desconhecida"
    assert result.errors[0]["line"] == 8
