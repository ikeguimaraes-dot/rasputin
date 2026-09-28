"use client";
import { useEffect, useState } from "react";
import { Calculator, Download, Save, BookOpen } from "lucide-react";
import type { Call, Client } from "@/lib/types";
import { money, regimes } from "@/lib/client";
import { Button, Empty, Loading, Notice } from "./ui";

type Source = {
  id: string;
  title: string;
  url: string;
  sha256: string;
  retrieved_at: string;
  capture_kind?: string;
};
type Spec = {
  title: string;
  regimes: string[];
  period: string;
  scope: string;
  fields: { key: string; label: string; kind: string; only_q4?: boolean }[];
};
export type Catalog = {
  version: string;
  valid_from: string;
  valid_to: string;
  hash: string;
  sources: Source[];
  modules: Record<string, Spec>;
};
type Result = {
  title: string;
  period: string;
  period_type: string;
  status: string;
  scope: string;
  total_due?: string;
  notice?: string;
  catalog_version: string;
  catalog_hash: string;
  warnings: string[];
  missing: { field: string; label: string }[];
  lines: {
    tax: string;
    base: string | null;
    gross: string;
    deductions: string;
    due: string;
    remaining: string;
  }[];
  memory: Record<string, unknown>;
  sources: Source[];
};
type Saved = {
  id: string;
  module: string;
  period: string;
  sha256: string;
  result_payload: Result;
};

export function OfficialSources({ catalog }: { catalog: Catalog }) {
  return (
    <div className="card">
      <div className="card-head">
        <h2>
          <BookOpen size={18} /> Fontes oficiais incorporadas
        </h2>
        <small>Versão {catalog.version}</small>
      </div>
      <div className="card-body">
        <p className="subtitle">
          Parâmetros de apuração disponíveis, sem importar planilha. Vigência de
          uso: {catalog.valid_from} a {catalog.valid_to}. Cada cálculo guarda a
          versão utilizada.
        </p>
        {catalog.sources.map((s) => (
          <details key={s.id} style={{ marginTop: 12 }}>
            <summary>{s.title}</summary>
            <p>
              <a href={s.url} target="_blank" rel="noreferrer">
                Consultar publicação oficial ↗
              </a>
            </p>
            <small>
              {s.capture_kind} · consulta em {s.retrieved_at.slice(0, 10)}
            </small>
            <p style={{ overflowWrap: "anywhere" }}>SHA-256: {s.sha256}</p>
          </details>
        ))}
      </div>
    </div>
  );
}

export function Assessments({
  call,
  clients,
}: {
  call: Call;
  clients: Client[];
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [clientId, setClientId] = useState(clients[0]?.id || "");
  const [period, setPeriod] = useState("2026-09");
  const [module, setModule] = useState("");
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [savedId, setSavedId] = useState("");
  const [history, setHistory] = useState<Saved[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const client = clients.find((c) => c.id === clientId);
  const profile = client?.profiles.find(
    (p) =>
      p.valid_from <= period + "-01" &&
      (!p.valid_to || p.valid_to >= period + "-01"),
  );
  const spec = catalog?.modules[module];
  function reset() {
    setResult(null);
    setSavedId("");
    setError("");
  }
  useEffect(() => {
    call<Catalog>("/fiscal-catalog")
      .then(setCatalog)
      .catch((e) => setError(e.message));
  }, [call]);
  useEffect(() => {
    if (clientId)
      call<Saved[]>(`/assessments?client_id=${clientId}`)
        .then(setHistory)
        .catch((e) => setError(e.message));
  }, [call, clientId]);
  useEffect(() => {
    setModule("");
    setValues({});
    setResult(null);
    setSavedId("");
  }, [clientId, period]);
  async function calculate(save: boolean) {
    setBusy(true);
    setError("");
    try {
      const parsed = Object.fromEntries(
        Object.entries(values)
          .filter(([, v]) => v !== "")
          .map(([k, v]) => [
            k,
            typeof v === "string" ? v.replace(",", ".") : v,
          ]),
      );
      const body = {
        client_id: clientId,
        module,
        period: period + "-01",
        values: parsed,
      };
      if (save) {
        const row = await call<Saved>("/assessments", body);
        setResult(row.result_payload);
        setSavedId(row.id);
        setHistory(await call<Saved[]>(`/assessments?client_id=${clientId}`));
      } else {
        setResult(await call<Result>("/assessments/preview", body));
        setSavedId("");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function download(kind: string) {
    setBusy(true);
    setError("");
    try {
      const d = await call<{ url: string }>(
        `/assessments/${savedId}/download/${kind}`,
      );
      window.location.assign(d.url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!clients.length)
    return (
      <Empty
        title="Cadastre um cliente para apurar"
        text="O cálculo usa o regime e a vigência do perfil fiscal do cliente."
      />
    );
  return (
    <>
      <div className="title-row">
        <div>
          <p className="eyebrow">Regras oficiais e dados declarados</p>
          <h1>Apuração de impostos</h1>
          <p className="subtitle">
            Escolha o tributo e o período. Confira a memória e salve uma versão
            imutável.
          </p>
        </div>
        <Calculator />
      </div>
      {error && <Notice error>{error}</Notice>}
      {!catalog ? (
        <Loading />
      ) : (
        <>
          <div className="card">
            <div className="card-body">
              <div className="form-grid">
                <label>
                  Cliente
                  <select
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                  >
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.razao_social}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Competência / mês de encerramento
                  <input
                    aria-label="Competência de apuração"
                    type="month"
                    min="2026-01"
                    max="2026-12"
                    value={period}
                    onChange={(e) => setPeriod(e.target.value)}
                  />
                </label>
                <label className="full">
                  Módulo de apuração
                  <select
                    value={module}
                    onChange={(e) => {
                      setModule(e.target.value);
                      setValues({});
                      reset();
                    }}
                  >
                    <option value="">Selecione o cálculo</option>
                    {Object.entries(catalog.modules)
                      .filter(
                        ([, s]) =>
                          profile && s.regimes.includes(profile.regime_federal),
                      )
                      .map(([key, s]) => (
                        <option key={key} value={key}>
                          {s.title}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <p className="subtitle">
                {profile
                  ? `${regimes[profile.regime_federal]} · ${profile.uf}`
                  : "Não há perfil vigente para esta competência."}
              </p>
              {spec && (
                <>
                  <Notice>
                    {spec.scope}{" "}
                    {spec.period === "trimestral" &&
                      "Escolha março, junho, setembro ou dezembro. Informe valores do trimestre inteiro."}
                  </Notice>
                  <p className="subtitle">
                    Informe 0 somente quando o valor for comprovadamente zero.
                    Valores desconhecidos devem permanecer vazios. Não use
                    separador de milhar.
                  </p>
                  <div className="form-grid">
                    {spec.fields
                      .filter((f) => !f.only_q4 || period.endsWith("-12"))
                      .map((f) => (
                        <label
                          key={f.key}
                          className={f.kind === "bool" ? "full" : ""}
                        >
                          {f.label}
                          {f.kind === "bool" ? (
                            <select
                              aria-label={f.label}
                              value={
                                values[f.key] === true
                                  ? "sim"
                                  : values[f.key] === false
                                    ? "nao"
                                    : ""
                              }
                              onChange={(e) => {
                                setValues({
                                  ...values,
                                  [f.key]:
                                    e.target.value === ""
                                      ? ""
                                      : e.target.value === "sim",
                                });
                                reset();
                              }}
                            >
                              <option value="">Não informado</option>
                              <option value="sim">Sim</option>
                              <option value="nao">Não</option>
                            </select>
                          ) : (
                            <input
                              aria-label={f.label}
                              inputMode="decimal"
                              placeholder="Não informado"
                              value={String(values[f.key] ?? "")}
                              onChange={(e) => {
                                setValues({
                                  ...values,
                                  [f.key]: e.target.value,
                                });
                                reset();
                              }}
                            />
                          )}
                        </label>
                      ))}
                  </div>
                  <div className="actions">
                    <Button disabled={busy} onClick={() => calculate(false)}>
                      <Calculator />
                      {busy ? "Calculando…" : "Calcular e conferir"}
                    </Button>
                    {result?.status === "calculada" && !savedId && (
                      <Button disabled={busy} onClick={() => calculate(true)}>
                        <Save />
                        Salvar apuração
                      </Button>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          {result && (
            <div className="card">
              <div className="card-head">
                <h2>{result.title}</h2>
                <span className="badge">
                  {savedId
                    ? "Versão salva"
                    : result.status === "calculada"
                      ? "Prévia calculada"
                      : "Dados pendentes"}
                </span>
              </div>
              <div className="card-body">
                <p>
                  {result.period.slice(0, 7)} · {result.period_type}
                </p>
                {result.missing.length > 0 && (
                  <Notice>
                    <strong>Faltam dados para calcular:</strong>
                    <ul>
                      {result.missing.map((m) => (
                        <li key={m.field}>{m.label}</li>
                      ))}
                    </ul>
                  </Notice>
                )}
                {!!result.lines.length && (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Tributo</th>
                          <th>Base</th>
                          <th>Débito</th>
                          <th>Deduções</th>
                          <th>A recolher</th>
                          <th>Excedente*</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.lines.map((l) => (
                          <tr key={l.tax}>
                            <td>{l.tax}</td>
                            <td>{l.base === null ? "—" : money(l.base)}</td>
                            <td>{money(l.gross)}</td>
                            <td>{money(l.deductions)}</td>
                            <td>
                              <strong>{money(l.due)}</strong>
                            </td>
                            <td>{money(l.remaining)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {result.total_due && (
                  <h2>Total deste módulo: {money(result.total_due)}</h2>
                )}
                {!!result.lines.length && (
                  <small>
                    *Excedente exige verificação de sua natureza e das regras de
                    transporte/compensação.
                  </small>
                )}
                {result.warnings.map((w) => (
                  <Notice key={w}>{w}</Notice>
                ))}
                <p className="subtitle">{result.notice}</p>
                <details>
                  <summary>Memória de cálculo</summary>
                  <pre>{JSON.stringify(result.memory, null, 2)}</pre>
                </details>
                <details>
                  <summary>
                    Fontes aplicadas e versão {result.catalog_version}
                  </summary>
                  {result.sources.map((s) => (
                    <p key={s.id}>
                      <a target="_blank" rel="noreferrer" href={s.url}>
                        {s.title}
                      </a>
                    </p>
                  ))}
                  <p style={{ overflowWrap: "anywhere" }}>
                    Hash: {result.catalog_hash}
                  </p>
                </details>
                {savedId && (
                  <div className="actions">
                    <Button
                      secondary
                      disabled={busy}
                      onClick={() => download("pdf")}
                    >
                      <Download />
                      PDF
                    </Button>
                    <Button
                      secondary
                      disabled={busy}
                      onClick={() => download("xlsx")}
                    >
                      <Download />
                      Excel
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
          <div className="card">
            <div className="card-head">
              <h2>Histórico do cliente</h2>
              <small>{history.length} versões</small>
            </div>
            <div className="card-body">
              {history.length ? (
                history.map((h) => (
                  <div className="finding" key={h.id}>
                    <button
                      className="button ghost"
                      onClick={() => {
                        setResult(h.result_payload);
                        setSavedId(h.id);
                      }}
                    >
                      {h.period.slice(0, 7)} · {h.result_payload.title} ·{" "}
                      {money(h.result_payload.total_due || "0")}
                    </button>
                  </div>
                ))
              ) : (
                <p className="subtitle">Nenhuma apuração salva.</p>
              )}
            </div>
          </div>
          <OfficialSources catalog={catalog} />
        </>
      )}
    </>
  );
}
