"""Contratos canônicos. Dinheiro usa Decimal; ausência nunca vira zero implicitamente."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENGINE_VERSION = "1.2.1"
PARSER_VERSION = "1.1.0"
Regime = Literal["simples", "presumido", "real"]


def digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Profile(Model):
    uf: str = Field(default="SP", pattern=r"^[A-Z]{2}$")
    regime_federal: Regime
    cnae: str | None = None
    optante_regime_especial_rest: bool = False
    contribuinte_ipi: bool | None = None
    metodo_pis_cofins: Literal["com_exclusao_icms", "sem_exclusao_icms"] | None = None
    regime_pis_cofins: Literal["cumulativo", "nao_cumulativo", "misto"] | None = None
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Fim da vigência anterior ao início")
        return self


class Tax(Model):
    cst: str | None = None
    csosn: str | None = None
    base: Decimal | None = None
    rate: Decimal | None = None  # pontos percentuais: 18 significa 18%
    value: Decimal | None = None
    reduction: Decimal | None = None


class Item(Model):
    n_item: int = Field(ge=1)
    code: str | None = None
    description: str = ""
    ncm: str | None = None
    cest: str | None = None
    cfop: str | None = None
    unit: str | None = None
    quantity: Decimal | None = None
    unit_value: Decimal | None = None
    value: Decimal | None = None
    discount: Decimal | None = None
    freight: Decimal | None = None
    insurance: Decimal | None = None
    other: Decimal | None = None
    icms: Tax = Field(default_factory=Tax)
    pis: Tax = Field(default_factory=Tax)
    cofins: Tax = Field(default_factory=Tax)
    ipi: Tax = Field(default_factory=Tax)
    st: Tax = Field(default_factory=Tax)
    fcp: Tax = Field(default_factory=Tax)
    difal: dict = Field(default_factory=dict)
    ibs_cbs: dict = Field(default_factory=dict)
    source: dict = Field(default_factory=dict)

    @field_validator("ncm", "cest", "cfop", mode="before")
    @classmethod
    def clean_codes(cls, value):
        if value is None or str(value).strip() == "":
            return None
        return str(value).strip().replace(".", "").replace("-", "")


class Document(Model):
    key: str | None = None
    model: int | None = None
    series: str | None = None
    number: str | None = None
    issued: date
    issuer_doc: str | None = None
    recipient_doc: str | None = None
    recipient_name: str | None = None
    recipient_uf: str | None = None
    recipient_taxpayer: bool | None = None
    final_consumer: bool | None = None
    operation: Literal["entrada", "saida", "desconhecida"] = "desconhecida"
    purpose: str | None = None
    status: Literal["autorizada", "cancelada", "denegada", "desconhecida"] = "desconhecida"
    total: Decimal | None = None
    items: list[Item]

    @model_validator(mode="after")
    def unique_items(self):
        nums = [i.n_item for i in self.items]
        if len(nums) != len(set(nums)):
            raise ValueError("Número de item duplicado no documento")
        return self


class Ingestion(Model):
    documents: list[Document] = Field(default_factory=list)
    read: int = 0
    discarded: int = 0
    partial: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    parser_version: str = PARSER_VERSION


class Rule(Model):
    id: str
    code: Literal["C02", "C05", "R02", "R04", "R05"]
    title: str
    status: Literal["proposta", "aprovada", "rejeitada"] = "proposta"
    valid_from: date
    valid_to: date | None = None
    uf: str = "SP"
    regimes: list[Regime] = Field(min_length=1)
    ncm_prefix: str = Field(default="", pattern=r"^\d{0,8}$")
    conditions: dict = Field(default_factory=dict)
    expected: dict
    source_url: str = Field(pattern=r"^https://")
    source_hash: str | None = None
    legal_basis: str = Field(min_length=3)
    approved_by: str | None = None
    approved_at: str | None = None
    priority: int = 0

    @model_validator(mode="after")
    def validate_rule(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Vigência inválida")
        allowed = {
            "cfop",
            "icms_cst",
            "icms_csosn",
            "recipient_taxpayer",
            "final_consumer",
            "operation",
            "special_regime",
            "contribuinte_ipi",
            "cest",
            "purpose",
        }
        if set(self.conditions) - allowed:
            raise ValueError("Condição não suportada pelo motor")
        fields = {
            "C02": {"icms_cst", "icms_csosn"},
            "C05": {"cest"},
            "R02": {"subject_to_st"},
            "R04": {"icms_rate"},
            "R05": {"pis_cst", "cofins_cst", "pis_rate", "cofins_rate"},
        }
        if not self.expected or set(self.expected) - fields[self.code]:
            raise ValueError("Resultado esperado incompatível com o código da regra")
        if self.code == "R04" and not {"operation", "final_consumer"} <= self.conditions.keys():
            raise ValueError("R04 exige operação e consumidor final explícitos")
        boolean_fields = {
            "recipient_taxpayer",
            "final_consumer",
            "special_regime",
            "contribuinte_ipi",
        }
        widths = {
            "cfop": 4,
            "icms_cst": 2,
            "icms_csosn": 3,
            "cest": 7,
            "pis_cst": 2,
            "cofins_cst": 2,
        }
        for key, value in self.conditions.items():
            choices = value if isinstance(value, list) else [value]
            if not choices:
                raise ValueError("Condição sem valores")
            for choice in choices:
                if key in boolean_fields and not isinstance(choice, bool):
                    raise ValueError(f"{key} deve ser sim/não (booleano)")
                if key == "operation" and choice not in ("entrada", "saida"):
                    raise ValueError("Operação inválida")
                if key in widths and (
                    not isinstance(choice, str)
                    or not re.fullmatch(r"\d{" + str(widths[key]) + "}", choice)
                ):
                    raise ValueError(f"{key}: código deve ter {widths[key]} dígitos")
        for key, value in self.expected.items():
            if key.endswith("_rate"):
                try:
                    rate = Decimal(str(value))
                    if not rate.is_finite() or not Decimal("0") <= rate <= Decimal("100"):
                        raise ValueError("Alíquota fora de 0..100 pontos percentuais")
                except InvalidOperation as exc:
                    raise ValueError("Alíquota inválida") from exc
            elif key == "subject_to_st":
                if value is not False:
                    raise ValueError("R02 exige sujeição à ST igual a não; presença em ST é R03")
            else:
                choices = value if isinstance(value, list) else [value]
                if not choices or any(
                    not isinstance(c, str) or not re.fullmatch(r"\d{" + str(widths[key]) + "}", c)
                    for c in choices
                ):
                    raise ValueError(f"{key}: informe códigos de {widths[key]} dígitos")
        if self.status == "aprovada" and not (self.approved_by and self.approved_at):
            raise ValueError("Aprovação exige responsável e data")
        return self


class Finding(Model):
    id: str = ""
    code: str
    severity: Literal["erro", "risco", "revisar", "alerta"]
    message: str
    product: str
    description: str
    evidence: list[dict]
    expected: dict = Field(default_factory=dict)
    impact: Decimal | None = None
    direction: Literal["pago_a_mais", "pago_a_menos", "neutro"] = "neutro"
    impact_kind: str = "potencial_documental"
    legal_basis: str = "Checagem de consistência documental; não conclui sobre recolhimento."
    source_url: str | None = None
    rule_id: str | None = None


class Result(Model):
    engine_version: str = ENGINE_VERSION
    input_hash: str
    rules_hash: str
    findings: list[Finding]
    skipped: list[dict]
    summary: dict
