"""Catálogo oficial independente das regras personalizadas aprovadas pelo escritório."""

import gzip
import json
from datetime import datetime
from functools import lru_cache

from auditoria.assessment import DATA, catalog


@lru_cache(maxsize=1)
def ncm_table():
    return json.loads(gzip.decompress((DATA / "ncm.json.gz").read_bytes()))


def document_catalog(documents):
    table = ncm_table()
    codes = {i.get("ncm") for d in documents for i in d["items"] if i.get("ncm")}
    c = catalog()
    return {
        "version": c["version"],
        "parameters": c["parameters"],
        "sources": c["sources"],
        "valid_from": c["valid_from"],
        "valid_to": c["valid_to"],
        "ncm": {
            **{k: v for k, v in table.items() if k != "records"},
            "records": {
                code: table["records"][code] for code in sorted(codes) if code in table["records"]
            },
        },
    }


def check_ncm(code, issued, snapshot):
    table = snapshot["ncm"]
    if not code:
        return "skip", "NCM ausente"
    if len(code) != 8 or not code.isdigit():
        return "error", "NCM deve ter oito dígitos para mercadoria; confira exceções de leiaute."
    if issued.isoformat() > table["as_of"]:
        return "skip", "Competência posterior à captura oficial da NCM"
    record = table["records"].get(code)
    if record:
        start = datetime.strptime(record["Data_Inicio"], "%d/%m/%Y").date()
        end = datetime.strptime(record["Data_Fim"], "%d/%m/%Y").date()
        if start <= issued <= end:
            return "ok", "Código presente na tabela oficial e vigência compatível"
        return "skip", "Código exige consulta à tabela histórica da competência"
    if issued.isoformat() == table["as_of"]:
        return "error", "NCM não localizado na tabela oficial vigente na data do documento"
    return "skip", "NCM ausente da tabela atual; documento anterior exige histórico oficial"
