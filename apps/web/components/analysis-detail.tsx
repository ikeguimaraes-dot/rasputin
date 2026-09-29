"use client";
import { useState } from "react";
import {
  Download,
  RefreshCw,
  ExternalLink,
  Copy,
  CheckCircle2,
  Search,
} from "lucide-react";
import type { Analysis, Call, ReviewRow } from "@/lib/types";
import { money, formatDate } from "@/lib/client";
import { ReviewChart } from "./review-chart";
import { Button, Notice, Status } from "./ui";
export function AnalysisDetail({
  analysis,
  call,
  clientName,
}: {
  analysis: Analysis;
  call: Call;
  clientName?: string;
}) {
  const [tab, setTab] = useState("findings"),
    [cfop, setCfop] = useState(""),
    [rate, setRate] = useState(""),
    [category, setCategory] = useState(""),
    [page, setPage] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState(""),
    [feedback, setFeedback] = useState("");
  const result = analysis.result_payload;
  async function download(kind: string) {
    setBusy(true);
    setError("");
    setFeedback("");
    try {
      const { url } = await call<{ url: string }>(
        `/analyses/${analysis.id}/download/${kind}`,
      );
      const response = await fetch(url);
      if (!response.ok)
        throw new Error(
          "Não foi possível baixar o relatório. Tente novamente.",
        );
      const blob = await response.blob();
      const localUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = localUrl;
      link.download = `Rasputin-conferencia-${analysis.periodo_ini}.${kind}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(localUrl), 60_000);
      setFeedback(
        kind === "pdf"
          ? "PDF exportado. O arquivo está pronto para você anexar e enviar ao cliente."
          : "Planilha exportada com o detalhamento da conferência.",
      );
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
  const base = result.summary?.base_review;
  const example = base?.rows[0];
  const certain = result.findings.filter(
    (f) =>
      ["C04", "C09"].includes(f.code) ||
      (f.code === "C03" &&
        f.evidence.length > 0 &&
        f.evidence.every(
          (ev) =>
            ["40", "41"].includes(ev.item.icms?.cst || "") &&
            ev.item.icms?.value != null &&
            Number(ev.item.icms.value) !== 0,
        )),
  );
  const rows = result.summary?.review_rows || [];
  const matches = (r: ReviewRow) =>
    (!query ||
      `${r.document} ${r.description} ${r.ncm} ${r.source.line}`
        .toLocaleLowerCase("pt-BR")
        .includes(query.toLocaleLowerCase("pt-BR"))) &&
    (!cfop || r.cfop === cfop) &&
    (!rate || r.icms_rate === rate) &&
    (!category || r.category === category);
  const filteredRows = rows.filter(matches);
  const selected = new Set(filteredRows.map((r) => JSON.stringify(r.source)));
  const findings =
    cfop || rate || category || query
      ? certain.filter((f) =>
          f.evidence.some((ev) => selected.has(JSON.stringify(ev.item.source))),
        )
      : certain;
  const groups = Object.groupBy(
    findings.filter((f) => !base || f.code !== "C09"),
    (f) => f.product,
  );
  return (
    <div className="report-view">
      <div className="report-actions">
        <Status value={analysis.status} />
        <span className="spacer" />
        <Button secondary disabled={busy} onClick={() => download("xlsx")}>
          <Download />
          Planilha detalhada
        </Button>
        <Button disabled={busy} onClick={() => download("pdf")}>
          <Download />
          {busy ? "Preparando…" : "Exportar PDF para cliente"}
        </Button>
      </div>
      {feedback && (
        <div role="status" className="report-feedback">
          {feedback}
        </div>
      )}
      {error && <Notice error>{error}</Notice>}
      {base && (
        <section className="card">
          <div className="report-intro">
            <p className="eyebrow">RELATÓRIO DE CONFERÊNCIA DOCUMENTAL</p>
            <h2>Os números, com clareza.</h2>
            <p>
              {clientName || "Cliente selecionado"} ·{" "}
              {formatDate(analysis.periodo_ini)} a{" "}
              {formatDate(analysis.periodo_fim)}
            </p>
            <p>
              Conferimos os valores informados para identificar diferenças
              demonstráveis na formação das bases de PIS e COFINS. Abaixo, você
              encontra o resultado e os itens que precisam de ajuste ou
              esclarecimento.
            </p>
          </div>
          <div className="report-overview">
            <div className="report-prose">
              <h3>O resultado da conferência</h3>
              <ul className="report-summary-list">
                <li>
                  <strong>{base.missing_icms}</strong>{" "}
                  {base.missing_icms === 1 ? "linha" : "linhas"} sem descontar o
                  ICMS da base.
                </li>
                <li>
                  <strong>{base.other_difference}</strong>{" "}
                  {base.other_difference === 1 ? "linha" : "linhas"} com outra
                  divergência na composição da base.
                </li>
                <li>
                  <strong>{base.compatible}</strong>{" "}
                  {base.compatible === 1
                    ? "linha compatível"
                    : "linhas compatíveis"}{" "}
                  com a fórmula.
                </li>
              </ul>
              <p className="subtitle">
                Cada item é contado uma única vez, mesmo quando a diferença
                aparece nos dois tributos.
              </p>
            </div>
            <ReviewChart base={base} />
          </div>
          {example && (
            <div className="report-example">
              <strong>Como a diferença aparece na prática</strong>
              Exemplo: nota {example.document}, linha{" "}
              {String(example.source.line ?? "—")} — valor de{" "}
              {money(example.operation_value)}, ICMS de {money(example.icms)}. A
              base esperada é {money(example.expected_base)}, mas PIS informa{" "}
              {example.pis_base === null
                ? "base não informada"
                : money(example.pis_base)}{" "}
              e COFINS informa{" "}
              {example.cofins_base === null
                ? "base não informada"
                : money(example.cofins_base)}
              .
            </div>
          )}
          <p className="report-method">
            Valor da operação = valor do item − desconto + frete + seguro +
            outras despesas. Comparação conforme o método cadastrado. Cada linha
            é contada uma vez.
          </p>
          {base.unassessed > 0 && (
            <p>
              {base.unassessed} linha(s) sem comparação completa; não contadas
              como compatíveis ou como erro.
            </p>
          )}
          {base.rows.length > 0 && (
            <details className="report-table-detail">
              <summary>
                Ver {base.rows.length}{" "}
                {base.rows.length === 1 ? "linha" : "linhas"} com divergência na
                base
              </summary>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Nota / linha</th>
                      <th>Produto / CFOP</th>
                      <th>Valor / ICMS</th>
                      <th>Base esperada</th>
                      <th>Base PIS / COFINS</th>
                      <th>Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {base.rows.map((r, i) => (
                      <tr key={i}>
                        <td>
                          {r.document}
                          <br />
                          Linha {String(r.source.line ?? "—")}
                        </td>
                        <td>
                          {r.description}
                          <br />
                          CFOP {r.cfop}
                        </td>
                        <td>
                          {money(r.operation_value)}
                          <br />
                          {money(r.icms)}
                        </td>
                        <td>{money(r.expected_base)}</td>
                        <td>
                          {r.pis_base === null ? "—" : money(r.pis_base)}
                          <br />
                          {r.cofins_base === null ? "—" : money(r.cofins_base)}
                        </td>
                        <td>
                          {r.kind === "missing_icms"
                            ? "ICMS não descontado"
                            : "Outra divergência de composição"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </section>
      )}
      <div className="report-next">
        <CheckCircle2 size={23} />
        <div>
          <h3>
            {certain.length
              ? "Próximo passo: revisar os itens identificados"
              : "Conferência documental concluída"}
          </h3>
          <p>
            {certain.length
              ? "Confira os valores destacados nas notas de origem e ajuste a composição da base no sistema fiscal, quando confirmada a diferença. A ocorrência de composição exige verificar também descontos, frete e outras despesas. Os valores apresentados são diferenças documentais; não representam, por si só, imposto a recolher."
              : "Não foram identificadas divergências nas comparações realizadas. O resultado se limita aos dados e às regras disponíveis para esta conferência."}
          </p>
        </div>
      </div>
      <div className="report-section-label">
        <h3>Explore as evidências</h3>
        <Button
          secondary
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(
                `Olá! Segue o relatório de conferência fiscal de ${clientName || "sua empresa"}, referente a ${formatDate(analysis.periodo_ini)} a ${formatDate(analysis.periodo_fim)}. ${base ? `A revisão identificou ${base.missing_icms} linha(s) sem descontar o ICMS da base, ${base.other_difference} com outra diferença de composição e ${base.compatible} compatíveis com a fórmula. ` : ""}O documento apresenta os valores informados, a base esperada e a localização dos itens para facilitar a revisão. Ficamos à disposição para esclarecer os apontamentos.`,
              );
              setFeedback(
                "Mensagem copiada. Anexe o PDF antes de enviar ao cliente.",
              );
            } catch {
              setError("Não foi possível copiar a mensagem neste navegador.");
            }
          }}
        >
          <Copy />
          Copiar mensagem para o cliente
        </Button>
      </div>
      <p className="subtitle">
        Somente divergências verificáveis nos dados e na fórmula cadastrada. A
        classificação fiscal dos demais produtos não foi concluída.
      </p>
      {rows.length > 0 && (
        <div className="report-filters">
          <label className="search-field" style={{ marginBottom: 16 }}>
            <Search />
            <input
              aria-label="Buscar nota ou produto"
              placeholder="Buscar por nota, produto, NCM ou linha…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(0);
              }}
            />
          </label>
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
            {filteredRows.length} itens ·{" "}
            {
              new Set(
                findings.flatMap((f) =>
                  f.evidence.map((ev) =>
                    JSON.stringify([
                      ev.document,
                      ev.issued,
                      ev.item.n_item,
                      ev.item.source,
                    ]),
                  ),
                ),
              ).size
            }{" "}
            linhas com divergência no filtro. Categoria derivada do cadastro,
            sujeita a revisão. Totais não representam apuração mensal.
          </p>
        </div>
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
          Outras divergências{" "}
          <span className="badge-count">
            {findings.filter((f) => !base || f.code !== "C09").length}
          </span>
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
                  <span className="status erro">Divergência documental</span>
                  <span>{f.message}</span>
                </div>
                {f.evidence.map((ev, i) => (
                  <div className="report-evidence" key={i}>
                    <span>
                      <strong>Nota {ev.document || "não informada"}</strong> ·
                      linha {String(ev.item.source.line ?? "—")}
                    </span>
                    {f.code === "C03" && (
                      <span>
                        CST {ev.item.icms?.cst} · ICMS{" "}
                        {money(ev.item.icms?.value || "0")}
                      </span>
                    )}
                  </div>
                ))}
                {f.code === "C03" && (
                  <p>
                    A situação tributária declarada e o destaque do imposto se
                    contradizem. Confira a nota de origem para identificar qual
                    informação precisa de correção.
                  </p>
                )}
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
                      Linha {String(ev.item.source.line ?? "—")} · Arquivo{" "}
                      {String(ev.item.source.file ?? "não informado")}
                    </p>
                  ))}
                  <pre>
                    {Object.keys(f.expected).length
                      ? JSON.stringify(f.expected, null, 2)
                      : "Confirme o CST e o ICMS no documento de origem."}
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
      ) : null}
      {tab === "findings" && !Object.keys(groups).length && (
        <Notice>
          Nenhuma outra divergência documental nos filtros selecionados.
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
