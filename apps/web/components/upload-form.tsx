"use client";
import { useState } from "react";
import { UploadCloud, WandSparkles } from "lucide-react";
import type { Call, Preview } from "@/lib/types";
import { Button, Notice } from "./ui";
export function UploadForm({
  call,
  clientId,
  onDone,
}: {
  call: Call;
  clientId: string;
  onDone: () => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [info, setInfo] = useState<Preview | null>(null),
    [mapping, setMapping] = useState<Record<string, number>>({}),
    [headerRows, setHeaderRows] = useState(1),
    [sheet, setSheet] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [dragging, setDragging] = useState(false);
  const spreadsheet = file && /\.(xlsx?|csv)$/i.test(file.name);
  async function inspect(f: File, h: number, s: string) {
    setBusy(true);
    setError("");
    setConfirmed(false);
    try {
      const fd = new FormData();
      fd.set("file", f);
      fd.set("header_rows", String(h));
      if (s) fd.set("sheet", s);
      const p = await call<Preview>("/uploads/preview", fd);
      setInfo(p);
      setSheet(p.sheet);
      setHeaderRows(p.header_rows || h);
      const template = await call<{
        mapeamento: { mapping: Record<string, number> };
      } | null>("/templates/" + p.signature);
      setMapping(template?.mapeamento.mapping || p.suggested_mapping || {});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function choose(f?: File) {
    if (!f || busy) return;
    setError("");
    if (!/\.(xml|zip|xlsx?|csv)$/i.test(f.name)) {
      setError("Escolha uma planilha, XML ou ZIP de XMLs.");
      return;
    }
    if (f.size > 30 * 1024 * 1024) {
      setError("O arquivo deve ter no máximo 30 MB.");
      return;
    }
    setFile(f);
    setInfo(null);
    setMapping({});
    setConfirmed(false);
    setHeaderRows(1);
    setSheet("");
    if (/\.(xlsx?|csv)$/i.test(f.name)) void inspect(f, 1, "");
  }
  async function suggest() {
    if (!info) return;
    setBusy(true);
    try {
      const r = await call<{ mapping: Record<string, number> }>(
        "/mapping/suggest",
        { headers: info.headers },
      );
      setMapping(r.mapping);
      setConfirmed(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function send() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      fd.set("file", file);
      fd.set("client_id", clientId);
      if (spreadsheet) {
        fd.set("mapping", JSON.stringify(mapping));
        fd.set("sheet", sheet);
        fd.set("header_rows", String(headerRows));
      }
      await call("/uploads", fd);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div
        className={`drop ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          choose(e.dataTransfer.files[0]);
        }}
      >
        <UploadCloud
          size={27}
          style={{ margin: "0 auto 10px", color: "#729264" }}
        />
        <h3>{file ? file.name : "Arraste seu arquivo para começar"}</h3>
        <p className="subtitle">
          XML, ZIP de XMLs, XLS, XLSX ou CSV · até 30 MB
        </p>
        <input
          aria-label="Arquivo fiscal"
          type="file"
          accept=".xml,.zip,.xls,.xlsx,.csv"
          disabled={busy}
          onChange={(e) => choose(e.target.files?.[0])}
        />
      </div>
      {busy && (
        <p role="status" className="subtitle">
          Preparando o arquivo. Aguarde a conclusão para continuar…
        </p>
      )}
      {spreadsheet && (
        <>
          <div className="form-grid" style={{ marginTop: 20 }}>
            <label>
              Linhas do cabeçalho
              <input
                type="number"
                min={1}
                max={10}
                value={headerRows}
                onChange={(e) => {
                  const h = Number(e.target.value);
                  setHeaderRows(h);
                  if (file && h >= 1 && h <= 10) void inspect(file, h, sheet);
                }}
              />
            </label>
            {info && (
              <label>
                Aba
                <select
                  value={sheet}
                  onChange={(e) => {
                    setSheet(e.target.value);
                    if (file) void inspect(file, headerRows, e.target.value);
                  }}
                >
                  {info.sheets.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {info && (
            <>
              <div className="row" style={{ marginTop: 24 }}>
                <h3>Confirme as colunas</h3>
                <span className="spacer" />
                <Button
                  secondary
                  type="button"
                  disabled={busy}
                  onClick={suggest}
                >
                  <WandSparkles />
                  Sugerir mapeamento
                </Button>
              </div>
              <p className="subtitle">
                {info.rows} linhas encontradas. Data, descrição e valor são
                obrigatórios.
              </p>
              <div className="mapping">
                {Object.entries(info.fields).map(([field, label]) => (
                  <label key={field}>
                    {label}
                    {["issued", "description", "value"].includes(field)
                      ? " *"
                      : ""}
                    <select
                      value={mapping[field] ?? ""}
                      onChange={(e) => {
                        const next = { ...mapping };
                        if (e.target.value === "") delete next[field];
                        else next[field] = Number(e.target.value);
                        setMapping(next);
                        setConfirmed(false);
                      }}
                    >
                      <option value="">Não informado</option>
                      {info.headers.map((h, i) => (
                        <option key={i} value={i}>
                          {i + 1}. {h}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <details>
                <summary>Prévia das primeiras linhas</summary>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {info.headers.map((h, i) => (
                          <th key={i}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {info.sample.map((r, i) => (
                        <tr key={i}>
                          {r.map((v, j) => (
                            <td key={j}>{v}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
              {info.warnings.map((w, i) => (
                <Notice key={i}>{w}</Notice>
              ))}
              <label className="check">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                Conferi o mapeamento e autorizo reutilizá-lo neste layout.
              </label>
            </>
          )}
        </>
      )}
      <Notice>
        O arquivo original é preservado. A análise somente lê os dados e gera
        apontamentos.
      </Notice>
      {error && <Notice error>{error}</Notice>}
      <div className="actions">
        <Button
          disabled={
            busy ||
            !file ||
            !!(
              spreadsheet &&
              (!info ||
                !confirmed ||
                ["issued", "description", "value"].some(
                  (f) => mapping[f] === undefined,
                ))
            )
          }
          onClick={send}
        >
          {busy ? "Processando…" : "Enviar para ingestão"}
        </Button>
      </div>
    </div>
  );
}
