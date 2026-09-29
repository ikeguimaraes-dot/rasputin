"use client";
import { useEffect, useState } from "react";
import type { Call, Client } from "@/lib/types";
import { Button, Empty, Notice } from "./ui";
type Definition = {
  code: string;
  description: string;
  kind: string;
  ncm: string | null;
  cest: string | null;
  service_code: string | null;
  municipality: string | null;
  status: string;
  valid_from: string;
  valid_to: string | null;
  basis: string;
  source_url: string | null;
};
type Version = { id: string; criado_em: string; definition: Definition };
type Observed = {
  code: string | null;
  description: string;
  ncm: string | null;
  cest: string | null;
  cfops: string[];
};
const blank = (): Definition => ({
  code: "",
  description: "",
  kind: "produto",
  ncm: null,
  cest: null,
  service_code: null,
  municipality: null,
  status: "proposta",
  valid_from: new Date().toISOString().slice(0, 10),
  valid_to: null,
  basis: "",
  source_url: null,
});
export function ProductCatalog({
  call,
  clients,
  admin,
}: {
  call: Call;
  clients: Client[];
  admin: boolean;
}) {
  const [clientId, setClientId] = useState(clients[0]?.id || "");
  const [rows, setRows] = useState<Version[]>([]),
    [observed, setObserved] = useState<Observed[]>([]);
  const [form, setForm] = useState<Definition>(blank),
    [versions, setVersions] = useState<Version[]>([]);
  const [query, setQuery] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    setRows([]);
    setObserved([]);
    setForm(blank());
    setVersions([]);
    setError("");
    setMessage("");
    if (clientId)
      Promise.all([
        call<Version[]>(`/product-catalog?client_id=${clientId}`),
        call<Observed[]>(`/product-catalog/observed?client_id=${clientId}`),
      ])
        .then(([r, o]) => {
          if (active) {
            setRows(r);
            setObserved(o);
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [call, clientId]);
  function field(key: keyof Definition, value: string) {
    setForm((f) => ({
      ...f,
      [key]:
        value || (["code", "description", "basis"].includes(key) ? "" : null),
    }));
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await call("/product-catalog", { client_id: clientId, definition: form });
      setRows(await call<Version[]>(`/product-catalog?client_id=${clientId}`));
      setMessage(
        "Versão registrada. A classificação não altera os documentos originais nem publica uma regra de tributação.",
      );
      setForm(blank());
      setVersions([]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function edit(v: Version) {
    setForm(v.definition);
    setVersions([]);
    setError("");
    try {
      setVersions(
        await call<Version[]>(
          `/product-catalog/history?client_id=${clientId}&code=${encodeURIComponent(v.definition.code)}`,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!clients.length)
    return (
      <Empty
        title="Cadastre um cliente"
        text="O catálogo de produtos e serviços pertence a cada empresa."
      />
    );
  return (
    <>
      <div className="title-row">
        <div>
          <p className="eyebrow">Classificação com histórico</p>
          <h1>Produtos e serviços</h1>
          <p className="subtitle">
            Reaproveite os itens dos documentos e registre a classificação
            conferida. As regras tributárias permanecem na Base de regras.
          </p>
        </div>
      </div>
      <label>
        Cliente
        <select
          disabled={busy}
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
      {error && <Notice error>{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      <div className="card">
        <div className="card-head">
          <h2>Catálogo da empresa</h2>
          <small>{rows.length} cadastros</small>
        </div>
        <div className="card-body">
          <label>
            Buscar por código, descrição ou NCM
            <input value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          {rows
            .filter((v) =>
              `${v.definition.code} ${v.definition.description} ${v.definition.ncm || ""}`
                .toLowerCase()
                .includes(query.toLowerCase()),
            )
            .map((v) => (
              <div className="finding" key={v.id}>
                <strong>
                  {v.definition.code} · {v.definition.description}
                </strong>
                <p>
                  {v.definition.ncm ||
                    v.definition.service_code ||
                    "Classificação pendente"}{" "}
                  · {v.definition.status} · vigência {v.definition.valid_from}
                </p>
                <Button secondary disabled={busy} onClick={() => edit(v)}>
                  Ver histórico / nova versão
                </Button>
              </div>
            ))}
          {!rows.length && <p>Nenhuma classificação registrada.</p>}
          <details>
            <summary>
              Itens encontrados nos arquivos ({observed.length})
            </summary>
            <p>
              A origem é declaratória. O mesmo código com descrições ou NCMs
              diferentes aparece separadamente para conferência.
            </p>
            {observed
              .filter((p) =>
                `${p.code} ${p.description} ${p.ncm}`
                  .toLowerCase()
                  .includes(query.toLowerCase()),
              )
              .map((p, i) => (
                <div className="finding" key={i}>
                  <strong>
                    {p.code || "Sem código"} · {p.description}
                  </strong>
                  <p>
                    NCM {p.ncm || "não informado"} · CFOPs observados{" "}
                    {p.cfops.join(", ")}
                  </p>
                  {admin && (
                    <Button
                      secondary
                      disabled={busy}
                      onClick={() => {
                        setForm({
                          ...blank(),
                          code: p.code || "",
                          description: p.description || "",
                          ncm: p.ncm,
                          cest: p.cest,
                        });
                        setVersions([]);
                      }}
                    >
                      Preparar cadastro
                    </Button>
                  )}
                </div>
              ))}
          </details>
        </div>
      </div>
      {admin && (
        <form className="card" onSubmit={save}>
          <div className="card-head">
            <h2>Registrar classificação</h2>
          </div>
          <div className="card-body">
            <div className="form-grid">
              <label>
                Código interno
                <input
                  required
                  maxLength={120}
                  value={form.code}
                  onChange={(e) => field("code", e.target.value)}
                />
              </label>
              <label>
                Tipo
                <select
                  value={form.kind}
                  onChange={(e) => field("kind", e.target.value)}
                >
                  <option value="produto">Produto</option>
                  <option value="servico">Serviço</option>
                </select>
              </label>
              <label className="full">
                Descrição técnica
                <input
                  required
                  minLength={2}
                  maxLength={500}
                  value={form.description}
                  onChange={(e) => field("description", e.target.value)}
                />
              </label>
              {(form.kind === "produto"
                ? [
                    ["ncm", "NCM (8 dígitos)"],
                    ["cest", "CEST (7 dígitos)"],
                  ]
                : [
                    ["service_code", "Código do serviço"],
                    ["municipality", "Município IBGE (7 dígitos)"],
                  ]
              ).map(([k, l]) => (
                <label key={k}>
                  {l}
                  <input
                    value={form[k as keyof Definition] || ""}
                    onChange={(e) =>
                      field(k as keyof Definition, e.target.value)
                    }
                  />
                </label>
              ))}
              <label>
                Início da vigência
                <input
                  required
                  type="date"
                  value={form.valid_from}
                  onChange={(e) => field("valid_from", e.target.value)}
                />
              </label>
              <label>
                Fim da vigência
                <input
                  type="date"
                  value={form.valid_to || ""}
                  onChange={(e) => field("valid_to", e.target.value)}
                />
              </label>
              <label>
                Situação
                <select
                  value={form.status}
                  onChange={(e) => field("status", e.target.value)}
                >
                  <option value="proposta">Proposta — a conferir</option>
                  <option value="validada">Classificação conferida</option>
                  <option value="inativa">Inativa</option>
                </select>
              </label>
              <label>
                Fonte de consulta
                <input
                  type="url"
                  placeholder="https://"
                  value={form.source_url || ""}
                  onChange={(e) => field("source_url", e.target.value)}
                />
              </label>
              <label className="full">
                Fundamento e características verificadas
                <textarea
                  maxLength={3000}
                  value={form.basis}
                  onChange={(e) => field("basis", e.target.value)}
                />
              </label>
            </div>
            <p className="subtitle">
              Validar a classificação não determina uma alíquota única. CFOP,
              benefício e tributação dependem da operação e da regra vigente.
            </p>
            <Button disabled={busy}>
              {busy ? "Registrando…" : "Salvar nova versão"}
            </Button>
            {!!versions.length && (
              <details>
                <summary>Histórico ({versions.length} versões)</summary>
                {versions.map((v) => (
                  <div key={v.id}>
                    <p>
                      {v.criado_em} · {v.definition.status} · NCM{" "}
                      {v.definition.ncm || "—"}
                    </p>
                    <p>{v.definition.basis}</p>
                  </div>
                ))}
              </details>
            )}
          </div>
        </form>
      )}
    </>
  );
}
