"use client";
import { useEffect, useState } from "react";
import { Plus, Upload, Check, X } from "lucide-react";
import type { Call, Rule } from "@/lib/types";
import { Button, Empty, Modal, Notice, Status } from "./ui";
import { RuleEditor } from "./rule-editor";
import { OfficialSources, type Catalog } from "./assessments";
export function Rules({ call, admin }: { call: Call; admin: boolean }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [rules, setRules] = useState<Rule[]>([]),
    [seed, setSeed] = useState<
      {
        id: string;
        sheet: string;
        row_number: number;
        raw: Record<string, string>;
      }[]
    >([]),
    [show, setShow] = useState(false),
    [initialTitle, setInitialTitle] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function load() {
    try {
      setCatalog(await call<Catalog>("/fiscal-catalog"));
      const [r, s] = await Promise.all([
        call<Rule[]>("/rules"),
        call<typeof seed>("/seed"),
      ]);
      setRules(r);
      setSeed(s);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [call]); // eslint-disable-line react-hooks/exhaustive-deps
  async function decide(id: string, decision: string) {
    setBusy(true);
    try {
      await call(`/rules/${id}/${decision}`, {});
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function importSeed(file: File) {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.set("file", file);
      const r = await call<{ imported: number; message: string }>("/seed", fd);
      setMessage(`${r.imported} linhas importadas. ${r.message}`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="title-row">
        <div>
          <p className="eyebrow">Conhecimento fiscal</p>
          <h1>Base de regras</h1>
          <p className="subtitle">
            Parâmetros oficiais de apuração e regras documentais do escritório.
          </p>
        </div>
        {admin && (
          <Button onClick={() => setShow(true)}>
            <Plus />
            Nova proposta
          </Button>
        )}
      </div>
      <Notice>
        Regras são específicas por regime, UF e operação. Propostas não entram
        nas análises. A aprovação deve ser feita pelo responsável fiscal após
        conferir a fonte e as condições.
      </Notice>
      {error && <Notice error>{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      {catalog && <OfficialSources catalog={catalog} />}
      <div className="card">
        <div className="card-head">
          <h2>
            Regras do escritório{" "}
            <span className="badge-count">{rules.length}</span>
          </h2>
          <small>Histórico preservado</small>
        </div>
        {!rules.length ? (
          <Empty
            title="Nenhuma regra documental personalizada"
            text="Os parâmetros oficiais acima já estão disponíveis em Apuração de impostos. Acrescente regras de produto e operação conforme o enquadramento dos clientes."
          />
        ) : (
          rules.map((r) => (
            <div className="finding" key={r.id}>
              <div className="row">
                <Status value={r.status} />
                <strong>
                  {r.code} · {r.definition.title}
                </strong>
                <span className="spacer" />
              </div>
              <p>
                {r.definition.regimes.join(" · ")} · vigente a partir de{" "}
                {r.definition.valid_from}
              </p>
              <details>
                <summary>Condições, resultado esperado e fonte</summary>
                <pre>{JSON.stringify(r.definition, null, 2)}</pre>
                <a
                  href={r.definition.source_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  Consultar fonte
                </a>
              </details>
              {admin && r.status === "proposta" && (
                <div className="actions">
                  <Button
                    secondary
                    disabled={busy}
                    onClick={() => decide(r.id, "reject")}
                  >
                    <X />
                    Rejeitar
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => decide(r.id, "approve")}
                  >
                    <Check />
                    Aprovar regra conferida
                  </Button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      {admin && (
        <div className="card">
          <div className="card-head">
            <h2>Planilha de referência</h2>
            <Upload size={18} />
          </div>
          <div className="card-body">
            <p className="subtitle">
              Abas “SP por NCM” e “27 Estados”. Cada linha é preservada para
              revisão; nenhuma alíquota é aprovada automaticamente.
            </p>
            <input
              aria-label="Importar seed fiscal"
              type="file"
              accept=".xlsx,.xls"
              disabled={busy}
              style={{ marginTop: 18 }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void importSeed(f);
              }}
            />
            {seed.length > 0 && (
              <details>
                <summary>{seed.length} linhas disponíveis para revisão</summary>
                {seed.map((s) => (
                  <details key={s.id}>
                    <summary>
                      {s.sheet} · linha {s.row_number}
                    </summary>
                    <pre>{JSON.stringify(s.raw, null, 2)}</pre>
                    <Button
                      secondary
                      onClick={() => {
                        setInitialTitle(
                          `Revisão: ${s.sheet}, linha ${s.row_number}`,
                        );
                        setShow(true);
                      }}
                    >
                      Criar proposta desta referência
                    </Button>
                  </details>
                ))}
              </details>
            )}
          </div>
        </div>
      )}
      {show && (
        <Modal title="Nova proposta de regra" onClose={() => setShow(false)}>
          <RuleEditor
            call={call}
            title={initialTitle}
            onDone={() => {
              setShow(false);
              void load();
            }}
          />
        </Modal>
      )}
    </>
  );
}
