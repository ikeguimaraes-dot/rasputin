"use client";
import { useState } from "react";
import { Download, RefreshCw, ExternalLink } from "lucide-react";
import type { Analysis, Call, ReviewRow } from "@/lib/types";
import { money } from "@/lib/client";
import { Button, Notice, Status } from "./ui";
export function AnalysisDetail({
  analysis,
  call,
}: {
  analysis: Analysis;
  call: Call;
}) {
  const [tab, setTab] = useState("findings"),
    [cfop, setCfop] = useState(""),
    [rate, setRate] = useState(""),
    [category, setCategory] = useState(""),
    [page, setPage] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const result = analysis.result_payload;
  async function download(kind: string) {
    setBusy(true);
    try {
      const { url } = await call<{ url: string }>(
        `/analyses/${analysis.id}/download/${kind}`,
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reissue() {
    setBusy(true);
    try {
      await call(`/analyses/${analysis.id}/reissue`, {});
      await download("pdf");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!result)
    return (
      <Notice>
        {analysis.erro || "A análise ainda está na fila de processamento."}
      </Notice>
    );
  const rows = result.summary?.review_rows || [];
  const matches = (r: ReviewRow) =>
    (!cfop || r.cfop === cfop) &&
    (!rate || r.icms_rate === rate) &&
    (!category || r.category === category);
  const filteredRows = rows.filter(matches);
  const selected = new Set(filteredRows.map((r) => JSON.stringify(r.source)));
  const findings =
    cfop || rate || category
      ? result.findings.filter((f) =>
          f.evidence.some((ev) => selected.has(JSON.stringify(ev.item.source))),
        )
      : result.findings;
  const groups = Object.groupBy(findings, (f) => f.product);
  return (
    <div>
      <div className="row">
        <Status value={analysis.status} />
        <span className="spacer" />
        <Button secondary disabled={busy} onClick={() => download("xlsx")}>
          <Download />
          XLSX
        </Button>
        <Button disabled={busy} onClick={() => download("pdf")}>
          <Download />
          PDF
        </Button>
      </div>
      <Notice>
        {analysis.parcial
          ? "Análise parcial: há dados ou regras insuficientes para parte das checagens. "
          : "Análise das checagens disponíveis. "}
        Os impactos são estimativas documentais e não comprovam imposto
        recolhido.
      </Notice>
      {error && <Notice error>{error}</Notice>}
      {rows.length > 0 && (
        <>
          <div className="form-grid">
            <label>
              CFOP
              <select
                aria-label="CFOP"
                value={cfop}
                onChange={(e) => {
                  setCfop(e.target.value);
                  setPage(0);
                }}
              >
                <option value="">Todos</option>
                {[...new Set(rows.map((r) => r.cfop).filter(Boolean))]
                  .sort()
                  .map((v) => (
                    <option key={v} value={v!}>
                      {v}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Alíquota ICMS
              <select
                aria-label="Alíquota ICMS"
                value={rate}
                onChange={(e) => {
                  setRate(e.target.value);
                  setPage(0);
                }}
              >
                <option value="">Todas</option>
                {[
                  ...new Set(
                    rows.map((r) => r.icms_rate).filter((v) => v !== null),
                  ),
                ]
                  .sort((a, b) => Number(a) - Number(b))
                  .map((v) => (
                    <option key={v} value={v!}>
                      {v}%
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Categoria declarada
              <select
                aria-label="Categoria declarada"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setPage(0);
                }}
              >
                <option value="">Todas</option>
                {[...new Set(rows.map((r) => r.category))].sort().map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
          </div>
          <p className="subtitle">
            {filteredRows.length} itens · {findings.length} apontamentos no
            filtro. Categoria derivada do cadastro, sujeita a revisão. Totais
            não representam apuração mensal.
          </p>
        </>
      )}
      <div className="tabs">
        {rows.length > 0 && (
          <button
            className={`tab ${tab === "items" ? "active" : ""}`}
            onClick={() => setTab("items")}
          >
            Itens por CFOP{" "}
            <span className="badge-count">{filteredRows.length}</span>
          </button>
        )}
        <button
          className={`tab ${tab === "findings" ? "active" : ""}`}
          onClick={() => setTab("findings")}
        >
          Apontamentos <span className="badge-count">{findings.length}</span>
        </button>
        <button
          className={`tab ${tab === "skipped" ? "active" : ""}`}
          onClick={() => setTab("skipped")}
        >
          Não avaliadas{" "}
          <span className="badge-count">{result.skipped.length}</span>
        </button>
      </div>
      {tab === "items" ? (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nota / linha</th>
                  <th>Produto / NCM</th>
                  <th>CFOP / natureza</th>
                  <th>Categoria</th>
                  <th>ICMS CST / %</th>
                  <th>PIS / COFINS CST</th>
                  <th>Valor / ICMS R$</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows
                  .slice(page * 100, (page + 1) * 100)
                  .map((r, i) => (
                    <tr key={i}>
                      <td>
                        {r.document || "—"}
                        <br />
                        Linha {String(r.source.line ?? "—")}
                      </td>
                      <td>
                        {r.description}
                        <br />
                        {r.ncm || "—"}
                      </td>
                      <td>
                        {r.cfop || "—"}
                        <br />
                        {r.nature}
                      </td>
                      <td>{r.category}</td>
                      <td>
                        {r.icms_cst ?? "—"} / {r.icms_rate ?? "—"}%
                      </td>
                      <td>
                        {r.pis_cst ?? "—"} / {r.cofins_cst ?? "—"}
                      </td>
                      <td>
                        {r.value === null ? "—" : money(r.value)}
                        <br />
                        {r.icms_value === null ? "—" : money(r.icms_value)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <Button
              secondary
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Anterior
            </Button>
            <span>
              Página {page + 1} de{" "}
              {Math.max(1, Math.ceil(filteredRows.length / 100))}
            </span>
            <Button
              secondary
              disabled={(page + 1) * 100 >= filteredRows.length}
              onClick={() => setPage(page + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      ) : tab === "findings" ? (
        Object.entries(groups).map(([product, findings]) => (
          <div className="card" key={product}>
            <div className="card-head">
              <h3>{findings?.[0].description || product}</h3>
              <small>Código {product}</small>
            </div>
            {findings?.map((f) => (
              <article className="finding" key={f.id}>
                <div className="finding-title">
                  <Status value={f.severity} />
                  <strong>{f.code}</strong>
                  <span>{f.message}</span>
                </div>
                {f.impact !== null && (
                  <p>Impacto potencial: {money(f.impact)}</p>
                )}
                <details>
                  <summary>Ver evidências e revisão sugerida</summary>
                  {f.evidence.map((ev, i) => (
                    <p key={i}>
                      Nota {ev.document || "não informada"} · item{" "}
                      {ev.item.n_item} · NCM {ev.item.ncm || "—"} · CFOP{" "}
                      {ev.item.cfop || "—"}
                      <br />
                      Origem: {JSON.stringify(ev.item.source)}
                    </p>
                  ))}
                  <pre>
                    {Object.keys(f.expected).length
                      ? JSON.stringify(f.expected, null, 2)
                      : "Conferir o enquadramento com o contador."}
                  </pre>
                  <p>{f.legal_basis}</p>
                  {f.source_url && (
                    <a target="_blank" rel="noreferrer" href={f.source_url}>
                      Consultar fonte oficial{" "}
                      <ExternalLink size={11} style={{ display: "inline" }} />
                    </a>
                  )}
                </details>
              </article>
            ))}
          </div>
        ))
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Regra</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {result.skipped.slice(0, 300).map((s, i) => (
                <tr key={i}>
                  <td>{s.code}</td>
                  <td>{s.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.skipped.length > 300 && (
            <p className="card-body">
              Mostrando 300 registros. Baixe o XLSX para a lista completa.
            </p>
          )}
        </div>
      )}
      {tab === "findings" && !findings.length && (
        <Notice>
          Nenhum apontamento nos filtros selecionados. Consulte a aba “Não
          avaliadas” antes de concluir sobre a conformidade.
        </Notice>
      )}
      <details>
        <summary>Rastreabilidade</summary>
        <p className="mono">
          Entrada: {result.input_hash}
          <br />
          Regras: {result.rules_hash}
        </p>
        <Button secondary disabled={busy} onClick={reissue}>
          <RefreshCw />
          Reemitir resultados preservados
        </Button>
      </details>
    </div>
  );
}
