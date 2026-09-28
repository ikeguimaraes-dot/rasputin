"use client";
import { useState } from "react";
import type { Call, Client } from "@/lib/types";
import { regimes } from "@/lib/client";
import { Button, Notice } from "./ui";
export function ClientForm({
  call,
  onDone,
  client,
}: {
  call: Call;
  onDone: () => void;
  client?: Client;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    const profile = {
      uf: f.get("uf"),
      regime_federal: f.get("regime"),
      valid_from: f.get("date"),
      optante_regime_especial_rest: f.get("special") === "on",
      contribuinte_ipi: f.get("ipi") === "on",
      metodo_pis_cofins: f.get("method") || null,
      regime_pis_cofins: f.get("contributions") || null,
    };
    try {
      if (client) await call(`/clients/${client.id}/profiles`, profile);
      else
        await call("/clients", {
          razao_social: f.get("name"),
          cnpj: String(f.get("cnpj")).replace(/\D/g, ""),
          profile,
        });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        {!client && (
          <>
            <label className="full">
              Razão social
              <input
                name="name"
                placeholder="Nome do restaurante ou estabelecimento"
                required
                minLength={2}
              />
            </label>
            <label>
              CNPJ
              <input
                name="cnpj"
                placeholder="00.000.000/0001-00"
                required
                pattern="[0-9./-]{14,18}"
              />
            </label>
          </>
        )}
        <label>
          UF
          <select name="uf" defaultValue="SP">
            {[
              "AC",
              "AL",
              "AP",
              "AM",
              "BA",
              "CE",
              "DF",
              "ES",
              "GO",
              "MA",
              "MT",
              "MS",
              "MG",
              "PA",
              "PB",
              "PR",
              "PE",
              "PI",
              "RJ",
              "RN",
              "RS",
              "RO",
              "RR",
              "SC",
              "SP",
              "SE",
              "TO",
            ].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Regime federal
          <select name="regime">
            {Object.entries(regimes).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Início da vigência
          <input name="date" type="date" required />
        </label>
        <label className="full">
          Regime declarado de PIS/COFINS
          <select name="contributions">
            <option value="">Não informado</option>
            <option value="cumulativo">Cumulativo</option>
            <option value="nao_cumulativo">Não cumulativo</option>
            <option value="misto">Misto — tratamento por operação</option>
          </select>
        </label>
        <label className="full">
          Método declarado de base PIS/COFINS
          <select name="method">
            <option value="">Não informado — checagem limitada</option>
            <option value="com_exclusao_icms">Com exclusão do ICMS</option>
            <option value="sem_exclusao_icms">Sem exclusão do ICMS</option>
          </select>
        </label>
        <label className="check full">
          <input type="checkbox" name="special" />
          Optante de regime especial estadual de restaurante
        </label>
        <label className="check full">
          <input type="checkbox" name="ipi" />
          Contribuinte de IPI
        </label>
      </div>
      <Notice>
        As regras dependem do regime, UF, operação e data. Informe o
        enquadramento confirmado pelo contador.{" "}
        {client &&
          "A nova vigência encerra o perfil anterior aberto; análises anteriores ficam preservadas."}
      </Notice>
      {error && <Notice error>{error}</Notice>}
      <div className="actions">
        <Button disabled={busy}>
          {busy
            ? "Salvando…"
            : client
              ? "Salvar nova vigência"
              : "Cadastrar cliente"}
        </Button>
      </div>
    </form>
  );
}
