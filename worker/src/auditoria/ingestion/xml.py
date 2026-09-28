from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from lxml import etree

from auditoria.domain import Document, Ingestion, Item, Tax

MAX_BYTES = 30 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_FILES = 2000


def text(node, path):
    value = node.findtext(path) if node is not None else None
    return value.strip() if value and value.strip() else None


def number(node, path):
    value = text(node, path)
    return Decimal(value) if value is not None else None


def tax(node, prefix):
    if node is None:
        return Tax()
    return Tax(
        cst=text(node, "CST"),
        csosn=text(node, "CSOSN"),
        base=number(node, "vBC"),
        rate=number(node, "p" + prefix),
        value=number(node, "v" + prefix),
        reduction=number(node, "pRedBC"),
    )


def parse_xml(data: bytes, filename: str, client_cnpj: str | None = None) -> Document:
    if len(data) > MAX_BYTES:
        raise ValueError("XML excede 30 MB")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    root = etree.fromstring(data, parser)
    if root.getroottree().docinfo.doctype:
        raise ValueError("DTD/entidades externas não são aceitos")
    for node in root.iter():
        if isinstance(node.tag, str):
            node.tag = etree.QName(node).localname
    info = root if root.tag == "infNFe" else root.find(".//infNFe")
    if info is None:
        raise ValueError("Arquivo não contém NF-e/NFC-e; eventos não são notas")
    model = int(text(info, "ide/mod") or 0)
    if model not in (55, 65):
        raise ValueError("Modelo não suportado: esperado 55 ou 65")
    issuer = text(info, "emit/CNPJ") or text(info, "emit/CPF")
    if client_cnpj and issuer != client_cnpj:
        raise ValueError("Emitente não corresponde ao CNPJ do cliente selecionado")
    status_code = text(root, ".//protNFe/infProt/cStat")
    status = "autorizada" if status_code in ("100", "150") else "desconhecida"
    if status_code in ("110", "301", "302"):
        status = "denegada"
    items = []
    for det in info.findall("det"):
        p, taxes = det.find("prod"), det.find("imposto")

        def group(name, taxes=taxes):
            parent = taxes.find(name) if taxes is not None else None
            return parent[0] if parent is not None and len(parent) else None

        icms = group("ICMS")
        difal_node = taxes.find("ICMSUFDest") if taxes is not None else None
        ibs_node = taxes.find("IBSCBS") if taxes is not None else None
        key = (info.get("Id") or "").removeprefix("NFe")
        n = int(det.get("nItem", "0"))
        ipi_node = taxes.find(".//IPITrib") if taxes is not None else None
        if ipi_node is None and taxes is not None:
            ipi_node = taxes.find(".//IPINT")
        items.append(
            Item(
                n_item=n,
                code=text(p, "cProd"),
                description=text(p, "xProd") or "",
                ncm=text(p, "NCM"),
                cest=text(p, "CEST"),
                cfop=text(p, "CFOP"),
                unit=text(p, "uCom"),
                quantity=number(p, "qCom"),
                unit_value=number(p, "vUnCom"),
                value=number(p, "vProd"),
                discount=number(p, "vDesc"),
                freight=number(p, "vFrete"),
                insurance=number(p, "vSeg"),
                other=number(p, "vOutro"),
                icms=tax(icms, "ICMS"),
                pis=tax(group("PIS"), "PIS"),
                cofins=tax(group("COFINS"), "COFINS"),
                ipi=tax(ipi_node, "IPI"),
                st=Tax(
                    base=number(icms, "vBCST"),
                    rate=number(icms, "pICMSST"),
                    value=number(icms, "vICMSST"),
                ),
                fcp=Tax(
                    base=number(icms, "vBCFCP"),
                    rate=number(icms, "pFCP"),
                    value=number(icms, "vFCP"),
                ),
                difal={n.tag: n.text for n in difal_node} if difal_node is not None else {},
                ibs_cbs={"xml": etree.tostring(ibs_node, encoding="unicode")}
                if ibs_node is not None
                else {},
                source={"file": filename, "key": key, "n_item": n, "line": det.sourceline},
            )
        )
    if not items:
        raise ValueError("Nota sem itens")
    taxpayer = text(info, "dest/indIEDest")
    consumer = text(info, "ide/indFinal")
    return Document(
        key=(info.get("Id") or "").removeprefix("NFe") or None,
        model=model,
        series=text(info, "ide/serie"),
        number=text(info, "ide/nNF"),
        issued=date.fromisoformat((text(info, "ide/dhEmi") or text(info, "ide/dEmi") or "")[:10]),
        issuer_doc=issuer,
        recipient_doc=text(info, "dest/CNPJ") or text(info, "dest/CPF"),
        recipient_name=text(info, "dest/xNome"),
        recipient_uf=text(info, "dest/enderDest/UF"),
        recipient_taxpayer=None if taxpayer is None else taxpayer == "1",
        final_consumer=None if consumer is None else consumer == "1",
        operation={"0": "entrada", "1": "saida"}.get(text(info, "ide/tpNF"), "desconhecida"),
        purpose=text(info, "ide/finNFe"),
        status=status,
        total=number(info, "total/ICMSTot/vNF"),
        items=items,
    )


def ingest_xml(data: bytes, filename: str, client_cnpj: str | None = None) -> Ingestion:
    result = Ingestion()
    if len(data) > MAX_BYTES:
        raise ValueError("Upload excede 30 MB")
    files = [(filename, data)]
    if filename.lower().endswith(".zip"):
        try:
            with ZipFile(BytesIO(data)) as z:
                members = [m for m in z.infolist() if not m.is_dir()]
                if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_EXPANDED:
                    raise ValueError("ZIP excede limites de quantidade ou tamanho descompactado")
                files = []
                for member in members:
                    p = PurePosixPath(member.filename)
                    if p.is_absolute() or ".." in p.parts or "\\" in member.filename:
                        raise ValueError("Caminho inválido no ZIP")
                    if member.flag_bits & 1 or member.file_size > MAX_BYTES:
                        raise ValueError("Arquivo criptografado ou acima do limite no ZIP")
                    if p.suffix.lower() != ".xml":
                        result.warnings.append(f"Ignorado no ZIP: {member.filename}")
                        result.partial = True
                        continue
                    files.append((member.filename, z.read(member)))
        except BadZipFile as exc:
            raise ValueError("ZIP inválido ou truncado") from exc
    seen = set()
    for name, content in files:
        try:
            doc = parse_xml(content, name, client_cnpj)
            if doc.key and doc.key in seen:
                result.warnings.append(f"Nota duplicada ignorada: {doc.key}")
                continue
            seen.add(doc.key)
            result.documents.append(doc)
            result.read += len(doc.items)
            if doc.status == "desconhecida":
                result.warnings.append(f"{name}: sem protocolo de autorização informado")
                result.partial = True
        except (ValueError, etree.XMLSyntaxError, ArithmeticError) as exc:
            result.discarded += 1
            result.errors.append({"file": name, "reason": str(exc)[:300]})
            result.partial = True
    if not result.documents:
        result.partial = True
    result.warnings.append(
        "Cobertura limitada aos arquivos enviados; ausência de arquivo não prova dia sem movimento."
    )
    return result
