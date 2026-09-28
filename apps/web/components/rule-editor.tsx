"use client";
import { useState } from "react";
import type { Call } from "@/lib/types";
import { regimes } from "@/lib/client";
import { Button, Notice } from "./ui";
const definitions: Record<
  string,
  { name: string; fields: Record<string, string> }
> = {
  C02: {
    name: "Compatibilidade CFOP × CST/CSOSN",
    fields: { icms_cst: "CST ICMS aceitos", icms_csosn: "CSOSN aceitos" },
  },
  C05: { name: "Correspondência NCM × CEST", fields: { cest: "CEST aceitos" } },
  R02: {
    name: "Operação fora da substituição tributária",
    fields: { subject_to_st: "Sujeito à ST" },
  },
  R04: {
    name: "Alíquota documental de ICMS",
    fields: { icms_rate: "Alíquota ICMS esperada (%)" },
  },
  R05: {
    name: "Tratamento de PIS/COFINS",
    fields: {
      pis_cst: "CST PIS aceitos",
      cofins_cst: "CST COFINS aceitos",
      pis_rate: "Alíquota PIS esperada (%)",
      cofins_rate: "Alíquota COFINS esperada (%)",
    },
  },
};
export function RuleEditor({
  call,
  onDone,
  title = "",
}: {
  call: Call;
  onDone: () => void;
  title?: string;
}) {
  const [code, setCode] = useState("R05"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    const expected: Record<string, unknown> = {};
    for (const field of Object.keys(definitions[code].fields)) {
      const value = String(f.get("expected_" + field) || "").trim();
      if (value === "") continue;
      expected[field] =
        field === "subject_to_st"
          ? value === "true"
          : field.endsWith("_rate")
            ? value
            : value
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean);
    }
    const conditions: Record<string, unknown> = {
      operation: f.get("operation"),
    };
    for (const field of [
      "final_consumer",
      "recipient_taxpayer",
      "special_regime",
    ]) {
      const v = f.get(field);
      if (v === "true" || v === "false") conditions[field] = v === "true";
    }
    const cfop = String(f.get("cfop") || "").trim();
    if (cfop) conditions.cfop = cfop.split(",").map((x) => x.trim());
    try {
      await call("/rules", {
        code,
        title: f.get("title"),
        valid_from: f.get("valid_from"),
        valid_to: f.get("valid_to") || null,
        uf: f.get("uf"),
        regimes: f.getAll("regimes"),
        ncm_prefix: f.get("ncm_prefix") || "",
        conditions,
        expected,
        source_url: f.get("source_url"),
        legal_basis: f.get("legal_basis"),
        priority: Number(f.get("priority") || 0),
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save}>
      <div className="form-grid">
        <label className="full">
          Descrição do apontamento
          <input
            name="title"
            required
            minLength={3}
            defaultValue={title}
            placeholder="Descreva a divergência que esta regra verifica"
          />
        </label>
        <label>
          Verificação
          <select value={code} onChange={(e) => setCode(e.target.value)}>
            {Object.entries(definitions).map(([k, d]) => (
              <option key={k} value={k}>
                {k} · {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          UF
          <input
            name="uf"
            defaultValue="SP"
            required
            pattern="[A-Z]{2}"
            maxLength={2}
          />
        </label>
        <label>
          Vigente a partir de
          <input type="date" name="valid_from" required />
        </label>
        <label>
          Vigente até (opcional)
          <input type="date" name="valid_to" />
        </label>
        <div className="full">
          <label style={{ marginBottom: 10 }}>
            Regimes aos quais a regra se aplica
          </label>
          <div className="row" style={{ flexWrap: "wrap" }}>
            {Object.entries(regimes).map(([k, v]) => (
              <label key={k} className="check">
                <input type="checkbox" name="regimes" value={k} />
                {v}
              </label>
            ))}
          </div>
        </div>
        <label>
          NCM ou prefixo (opcional)
          <input
            name="ncm_prefix"
            pattern="[0-9]{0,8}"
            placeholder="Ex.: 2201"
          />
        </label>
        <label>
          CFOPs da operação (opcional)
          <input name="cfop" placeholder="Ex.: 5405, 5403" />
        </label>
        <label>
          Operação
          <select name="operation">
            <option value="saida">Saída</option>
            <option value="entrada">Entrada</option>
          </select>
        </label>
        <label>
          Consumidor final
          <select name="final_consumer" required={code === "R04"}>
            <option value="">Qualquer / não condiciona</option>
            <option value="true">Sim</option>
            <option value="false">Não</option>
          </select>
        </label>
        <label>
          Destinatário contribuinte
          <select name="recipient_taxpayer">
            <option value="">Qualquer / não condiciona</option>
            <option value="true">Sim</option>
            <option value="false">Não</option>
          </select>
        </label>
        <label>
          Regime especial de restaurante
          <select name="special_regime">
            <option value="">Qualquer / não condiciona</option>
            <option value="true">Optante</option>
            <option value="false">Não optante</option>
          </select>
        </label>
        <div className="full">
          <h3>Tratamento esperado</h3>
          <p className="subtitle">
            Preencha apenas os campos sustentados pela fonte. Separe códigos
            aceitos por vírgula.
          </p>
        </div>
        {Object.entries(definitions[code].fields).map(([key, label]) => (
          <label key={key}>
            {label}
            {key === "subject_to_st" ? (
              <select name={"expected_" + key}>
                <option value="false">
                  Não sujeito — confirmar operação fora da ST
                </option>
              </select>
            ) : (
              <input
                name={"expected_" + key}
                type={key.endsWith("_rate") ? "number" : "text"}
                step="0.0001"
                min={0}
                max={100}
                placeholder={
                  key.endsWith("_rate")
                    ? "Percentual"
                    : "Códigos, separados por vírgula"
                }
              />
            )}
          </label>
        ))}
        <label>
          Prioridade em caso de regras específicas
          <input name="priority" type="number" defaultValue={0} />
        </label>
        <label className="full">
          Link da fonte oficial
          <input
            type="url"
            name="source_url"
            placeholder="https://…"
            required
            pattern="https://.*"
          />
        </label>
        <label className="full">
          Base legal e condições de aplicação
          <textarea
            name="legal_basis"
            required
            minLength={3}
            style={{ minHeight: 110, fontFamily: "inherit" }}
            placeholder="Ato, artigo, trecho relevante e condições verificadas pelo responsável fiscal"
          />
        </label>
      </div>
      {code === "R04" && (
        <Notice>
          O percentual de apuração mensal de um regime especial não define
          automaticamente a alíquota a informar no item. Confirme o tratamento
          documental antes de aprovar esta regra.
        </Notice>
      )}
      {error && <Notice error>{error}</Notice>}
      <div className="actions">
        <Button disabled={busy}>Salvar como proposta</Button>
      </div>
    </form>
  );
}
