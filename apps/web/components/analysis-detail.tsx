"use client";
import { useState } from "react";
import { Download, RefreshCw, ExternalLink } from "lucide-react";
import type { Analysis, Call } from "@/lib/types";
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
  const groups = Object.groupBy(result.findings, (f) => f.product);
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
      <div className="tabs">
        <button
          className={`tab ${tab === "findings" ? "active" : ""}`}
          onClick={() => setTab("findings")}
        >
          Apontamentos{" "}
          <span className="badge-count">{result.findings.length}</span>
        </button>
        <button
          className={`tab ${tab === "skipped" ? "active" : ""}`}
          onClick={() => setTab("skipped")}
        >
          Não avaliadas{" "}
          <span className="badge-count">{result.skipped.length}</span>
        </button>
      </div>
      {tab === "findings" ? (
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
      {tab === "findings" && !result.findings.length && (
        <Notice>
          Nenhuma divergência nas checagens executadas. Consulte a aba “Não
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
