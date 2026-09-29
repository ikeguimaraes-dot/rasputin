"use client";
import { useEffect, useRef, useState } from "react";
import type { Call } from "@/lib/types";
import { money } from "@/lib/client";
import { Button, Notice } from "./ui";

export type Evidence = {
  hash: string;
  documents: number;
  start: string;
  end: string;
  months: string[];
  recalculated: {
    tax: string;
    base: string;
    gross: string;
    items: number;
    missing: number;
  }[];
  suggestions: Record<string, string>;
  blockers: string[];
  warnings: string[];
  base_review: Record<string, number>;
  cfops: {
    cfop: string;
    description: string;
    items: number;
    amount: string;
    missing: number;
  }[];
  taxes: { tax: string; declared: string; known: number; missing: number }[];
  products: {
    code: string | null;
    description: string;
    ncm: string | null;
    cest: string | null;
    cfops: string[];
  }[];
  rows: {
    document: string;
    item: number;
    description: string;
    cfop: string;
    operation: string | null;
    icms: string | null;
    expected_base: string | null;
    pis_base: string | null;
    cofins_base: string | null;
    status: string;
  }[];
};
type Upload = { id: string; nome: string; status: string; parcial: boolean };
const labels: Record<string, string> = {
  compatible: "Compatível com a fórmula",
  missing_icms: "ICMS não excluído",
  other_difference: "Outra divergência de base",
  unassessed: "Dados insuficientes",
};
export function AssessmentDocuments({
  call,
  clientId,
  module,
  period,
  evidence,
  selected,
  onSelected,
  onEvidence,
  onApply,
  complete,
  onComplete,
}: {
  call: Call;
  clientId: string;
  module: string;
  period: string;
  evidence: Evidence | null;
  selected: string[];
  onSelected: (ids: string[]) => void;
  onEvidence: (e: Evidence | null) => void;
  onApply: (v: Record<string, string>) => void;
  complete: boolean;
  onComplete: (v: boolean) => void;
}) {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setUploads([]);
    call<Upload[]>(`/uploads?client_id=${clientId}`)
      .then((v) => {
        if (active) setUploads(v.filter((u) => u.status === "processado"));
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [call, clientId]);
  async function consolidate() {
    setBusy(true);
    setError("");
    onEvidence(null);
    try {
      const next = await call<Evidence>("/assessments/documents", {
        client_id: clientId,
        module,
        period: period + "-01",
        upload_ids: selected,
      });
      if (mounted.current) onEvidence(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="card">
      <div className="card-head">
        <h2>1. Documentos do período</h2>
        <span className="badge">Consolidação automática</span>
      </div>
      <div className="card-body">
        <p className="subtitle">
          Selecione as fontes desta apuração. O sistema separa os CFOPs, soma os
          valores informados e confere as bases por item. Os totais abaixo ainda
          não são impostos a recolher.
        </p>
        {error && <Notice error>{error}</Notice>}
        {uploads.length ? (
          uploads.map((u) => (
            <label
              key={u.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 10,
              }}
            >
              <input
                type="checkbox"
                style={{ width: "auto" }}
                disabled={busy}
                checked={selected.includes(u.id)}
                onChange={(e) =>
                  onSelected(
                    e.target.checked
                      ? [...selected, u.id]
                      : selected.filter((id) => id !== u.id),
                  )
                }
              />
              {u.nome}
              {u.parcial && <span className="badge">Arquivo parcial</span>}
            </label>
          ))
        ) : (
          <p>
            Nenhum arquivo processado. Importe os documentos deste cliente para
            começar.
          </p>
        )}
        <Button
          secondary
          disabled={busy || !selected.length}
          onClick={consolidate}
        >
          {busy ? "Consolidando…" : "Consolidar documentos"}
        </Button>
        {evidence && (
          <>
            <p>
              <strong>{evidence.documents} documentos</strong> ·{" "}
              {evidence.start} a {evidence.end}
            </p>
            <p className="subtitle">
              Meses com documentos: {evidence.months.join(", ") || "nenhum"}. A
              presença de documentos não comprova a totalidade do movimento.
            </p>
            {evidence.blockers.map((b) => (
              <Notice key={b}>{b}</Notice>
            ))}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>CFOP / operação</th>
                    <th>Itens</th>
                    <th>Valor conhecido</th>
                    <th>Sem composição completa</th>
                  </tr>
                </thead>
                <tbody>
                  {evidence.cfops.map((g) => (
                    <tr key={g.cfop}>
                      <td>
                        <strong>{g.cfop}</strong> · {g.description}
                      </td>
                      <td>{g.items}</td>
                      <td>
                        {g.items === g.missing
                          ? "Não informado"
                          : money(g.amount)}
                      </td>
                      <td>{g.missing}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary>Tributos informados nos documentos</summary>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Tributo</th>
                      <th>Soma dos valores disponíveis</th>
                      <th>Itens sem valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.taxes.map((t) => (
                      <tr key={t.tax}>
                        <td>{t.tax}</td>
                        <td>{t.known ? money(t.declared) : "Não informado"}</td>
                        <td>{t.missing}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            <h3>Débitos documentais recalculados</h3>
            <p>
              Vendas com CST 01/02 e base recomposta, usando as alíquotas
              informadas nos itens. Subtotais antes de créditos, retenções e
              validação do enquadramento; não são saldo a recolher.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Tributo</th>
                    <th>Base recomposta</th>
                    <th>Débito recalculado</th>
                    <th>Itens calculados / sem dados</th>
                  </tr>
                </thead>
                <tbody>
                  {evidence.recalculated.map((t) => (
                    <tr key={t.tax}>
                      <td>{t.tax}</td>
                      <td>{t.items ? money(t.base) : "Não calculado"}</td>
                      <td>{t.items ? money(t.gross) : "Não calculado"}</td>
                      <td>
                        {t.items} / {t.missing}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3>Conferência de PIS e COFINS</h3>
            <p>
              Comparação da base declarada com a composição do valor da operação
              e o método de exclusão de ICMS cadastrado. Não certifica NCM, CST
              ou alíquota.
            </p>
            <ul>
              {Object.entries(evidence.base_review).map(([k, v]) => (
                <li key={k}>
                  <strong>{v}</strong> linhas — {labels[k]}
                </li>
              ))}
            </ul>
            <details>
              <summary>Ver divergências de base por item</summary>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Nota / item</th>
                      <th>Produto</th>
                      <th>Operação</th>
                      <th>ICMS</th>
                      <th>Base esperada</th>
                      <th>PIS / COFINS informados</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.rows
                      .filter((r) =>
                        ["missing_icms", "other_difference"].includes(r.status),
                      )
                      .map((r, i) => (
                        <tr key={i}>
                          <td>
                            {r.document} / {r.item}
                          </td>
                          <td>{r.description}</td>
                          <td>
                            {r.operation === null ? "—" : money(r.operation)}
                          </td>
                          <td>{r.icms === null ? "—" : money(r.icms)}</td>
                          <td>
                            {r.expected_base === null
                              ? "—"
                              : money(r.expected_base)}
                          </td>
                          <td>
                            {r.pis_base === null ? "—" : money(r.pis_base)} /{" "}
                            {r.cofins_base === null
                              ? "—"
                              : money(r.cofins_base)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </details>
            <details>
              <summary>
                Produtos identificados ({evidence.products.length})
              </summary>
              <p>
                Cadastro observado nos documentos; classificação ainda não
                validada. CFOPs pertencem às operações.
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Código / descrição</th>
                      <th>NCM</th>
                      <th>CEST</th>
                      <th>CFOPs observados</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.products.map((p, i) => (
                      <tr key={i}>
                        <td>
                          {p.code} · {p.description}
                        </td>
                        <td>{p.ncm || "Não informado"}</td>
                        <td>{p.cest || "Não informado"}</td>
                        <td>{p.cfops.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            {evidence.warnings.map((w) => (
              <p className="subtitle" key={w}>
                {w}
              </p>
            ))}
            {!!Object.keys(evidence.suggestions).length && (
              <>
                <Notice>
                  As sugestões incluem somente vendas com CST 01, alíquota geral
                  compatível com o regime de PIS/COFINS cadastrado e composição
                  completa da base. Revise o restante do movimento antes de
                  fechar.
                </Notice>
                <Button secondary onClick={() => onApply(evidence.suggestions)}>
                  Usar bases identificadas no formulário
                </Button>
              </>
            )}
            <label
              style={{
                display: "flex",
                gap: 10,
                alignItems: "center",
                marginTop: 16,
              }}
            >
              <input
                style={{ width: "auto" }}
                type="checkbox"
                checked={complete}
                disabled={!!evidence.blockers.length}
                onChange={(e) => onComplete(e.target.checked)}
              />
              Conciliei as bases e confirmei que as fontes cobrem todo o
              período.
            </label>
          </>
        )}
      </div>
    </div>
  );
}
