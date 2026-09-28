"use client";
import { useCallback, useEffect, useState } from "react";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import {
  ArrowUpRight,
  BookOpen,
  Building2,
  ChevronRight,
  FileCheck2,
  FileSearch,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Plus,
  ShieldCheck,
  UploadCloud,
  Activity,
  Settings2,
  Calculator,
} from "lucide-react";
import { API, formatDate, regimes, supabaseClient } from "@/lib/client";
import type { Analysis, Call, Client, Me, Upload } from "@/lib/types";
import { Button, Empty, Loading, Modal, Notice, Status } from "@/components/ui";
import { ClientForm } from "@/components/client-form";
import { UploadForm } from "@/components/upload-form";
import { AnalysisDetail } from "@/components/analysis-detail";
import { Rules } from "@/components/rules";
import { Assessments } from "@/components/assessments";

function Brand() {
  return (
    <div className="brand">
      <span className="brand-symbol">
        <FileCheck2 size={20} />
      </span>
      rasputin<span style={{ color: "#a7bf8b", fontSize: 18 }}>.</span>
    </div>
  );
}
function Auth({
  client,
  onError,
  error,
}: {
  client: SupabaseClient | null;
  onError: (s: string) => void;
  error: string;
}) {
  const [signup, setSignup] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!client) return;
    setBusy(true);
    onError("");
    const fd = new FormData(e.currentTarget);
    const credentials = {
      email: String(fd.get("email")),
      password: String(fd.get("password")),
    };
    try {
      const { error } = signup
        ? await client.auth.signUp(credentials)
        : await client.auth.signInWithPassword(credentials);
      if (error) throw error;
      if (signup)
        setMessage(
          "Conta criada. Se solicitado, confirme seu e-mail para entrar.",
        );
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <div className="auth-story">
        <Brand />
        <div>
          <p className="eyebrow" style={{ color: "#b1cd92" }}>
            Clareza para decidir
          </p>
          <h1>
            A conferência fiscal,
            <br />
            <em>com todos os detalhes.</em>
          </h1>
          <p>
            Transforme documentos fiscais em apontamentos rastreáveis. Cada
            análise conecta o produto, a evidência e a regra aplicada.
          </p>
          <div className="regime-list">
            {Object.values(regimes).map((r) => (
              <span
                key={r}
                style={{ color: "#cfdfc4", borderColor: "#45614e" }}
              >
                {r}
              </span>
            ))}
          </div>
        </div>
        <small style={{ color: "#8daa95" }}>
          Somente leitura. Seus documentos permanecem intactos.
        </small>
      </div>
      <div className="auth-form">
        <div className="auth-box">
          <p className="eyebrow">Seu espaço de trabalho</p>
          <h2>{signup ? "Crie sua conta" : "Bem-vindo de volta"}</h2>
          <p className="subtitle">Acesse as análises do seu escritório.</p>
          <form onSubmit={submit}>
            <label>
              E-mail profissional
              <input
                type="email"
                name="email"
                autoComplete="email"
                placeholder="voce@escritorio.com.br"
                required
              />
            </label>
            <label>
              Senha
              <input
                type="password"
                name="password"
                autoComplete={signup ? "new-password" : "current-password"}
                minLength={8}
                required
                placeholder="Sua senha"
              />
            </label>
            <Button disabled={busy || !client}>
              {busy
                ? "Aguarde…"
                : signup
                  ? "Criar conta"
                  : "Entrar no escritório"}
              <ArrowUpRight />
            </Button>
          </form>
          {error && <Notice error>{error}</Notice>}
          {message && <Notice>{message}</Notice>}
          <button
            className="button ghost"
            style={{ width: "100%", marginTop: 15 }}
            onClick={() => setSignup(!signup)}
          >
            {signup ? "Já tenho conta. Entrar" : "Primeiro acesso? Criar conta"}
          </button>
          <p className="auth-note">
            <ShieldCheck
              size={14}
              style={{ display: "inline", marginRight: 5 }}
            />
            Documentos e relatórios ficam restritos à sua organização.
          </p>
        </div>
      </div>
    </div>
  );
}
export default function Home() {
  const [supabase, setSupabase] = useState<SupabaseClient | null>(null),
    [session, setSession] = useState<Session | null>(null),
    [initial, setInitial] = useState(true),
    [me, setMe] = useState<Me | null>(null),
    [error, setError] = useState(""),
    [page, setPage] = useState("overview"),
    [clients, setClients] = useState<Client[]>([]),
    [clientId, setClientId] = useState(""),
    [uploads, setUploads] = useState<Upload[]>([]),
    [analyses, setAnalyses] = useState<Analysis[]>([]),
    [modal, setModal] = useState(""),
    [detail, setDetail] = useState<Analysis | null>(null),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState<string[]>([]);
  useEffect(() => {
    let subscription: { unsubscribe: () => void } | undefined;
    try {
      const sb = supabaseClient();
      setSupabase(sb);
      void sb.auth.getSession().then(({ data }) => {
        setSession(data.session);
        setInitial(false);
      });
      subscription = sb.auth.onAuthStateChange((_, s) => {
        setSession(s);
        if (!s) setMe(null);
      }).data.subscription;
    } catch (e) {
      setError((e as Error).message);
      setInitial(false);
    }
    return () => subscription?.unsubscribe();
  }, []);
  const call = useCallback<Call>(
    async <T,>(path: string, body?: unknown, method?: string): Promise<T> => {
      if (!supabase) throw new Error("Sessão indisponível.");
      const { data } = await supabase.auth.getSession();
      if (!data.session) throw new Error("Entre novamente.");
      const headers: Record<string, string> = {
        Authorization: `Bearer ${data.session.access_token}`,
      };
      if (!(body instanceof FormData) && body !== undefined)
        headers["Content-Type"] = "application/json";
      let response: Response;
      try {
        response = await fetch(API + "/api" + path, {
          method: method || (body === undefined ? "GET" : "POST"),
          headers,
          body:
            body === undefined
              ? undefined
              : body instanceof FormData
                ? body
                : JSON.stringify(body),
          cache: "no-store",
        });
      } catch {
        throw new Error(
          "Não foi possível conectar ao serviço de análise. Confira se o worker está disponível.",
        );
      }
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : JSON.stringify(
                result.detail || "Não foi possível concluir a ação.",
              ),
        );
      return result as T;
    },
    [supabase],
  );
  const loadClients = useCallback(async () => {
    const c = await call<Client[]>("/clients");
    setClients(c);
    setClientId((old) =>
      old && c.some((x) => x.id === old) ? old : c[0]?.id || "",
    );
  }, [call]);
  const loadWork = useCallback(async () => {
    if (!clientId) return;
    const [u, a] = await Promise.all([
      call<Upload[]>("/uploads?client_id=" + clientId),
      call<Analysis[]>("/analyses?client_id=" + clientId),
    ]);
    setUploads(u);
    setAnalyses(a);
  }, [call, clientId]);
  useEffect(() => {
    if (!session) return;
    void call<Me>("/me")
      .then((m) => {
        setMe(m);
        if (m.organization) return loadClients();
      })
      .catch((e) => setError(e.message));
  }, [session, call, loadClients]);
  useEffect(() => {
    setUploads([]);
    setAnalyses([]);
    setSelected([]);
    if (!clientId) return;
    void loadWork().catch((e) => setError(e.message));
    const timer = setInterval(() => {
      void loadWork().catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, [clientId, loadWork]);
  const client = clients.find((c) => c.id === clientId);
  const profile = client?.profiles[client.profiles.length - 1];
  const done = analyses.filter((a) => a.status === "concluida");
  const findings = done.reduce((n, a) => n + (a.resumo?.findings || 0), 0);
  async function openAnalysis(id: string) {
    setBusy(true);
    try {
      setDetail(await call<Analysis>("/analyses/" + id));
      setModal("detail");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function startAnalysis(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const fd = new FormData(e.currentTarget);
    try {
      await call("/analyses", {
        client_id: clientId,
        upload_ids: selected,
        start: fd.get("start"),
        end: fd.get("end"),
      });
      setModal("");
      setPage("analyses");
      await loadWork();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function createOrg(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      await call("/organizations", {
        nome: new FormData(e.currentTarget).get("name"),
      });
      setMe(await call<Me>("/me"));
      await loadClients();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (initial) return <Loading />;
  if (!session)
    return <Auth client={supabase} error={error} onError={setError} />;
  if (!me)
    return (
      <div className="auth-form" style={{ minHeight: "100vh" }}>
        <div className="auth-box">
          <h2>Conectando ao escritório</h2>
          {error ? <Notice error>{error}</Notice> : <Loading />}
          <Button
            secondary
            onClick={() => {
              setError("");
              void call<Me>("/me")
                .then(setMe)
                .catch((e) => setError(e.message));
            }}
          >
            Tentar novamente
          </Button>
          <Button secondary onClick={() => supabase?.auth.signOut()}>
            Sair
          </Button>
        </div>
      </div>
    );
  if (!me.organization)
    return (
      <div className="auth-form" style={{ minHeight: "100vh" }}>
        <div className="auth-box">
          <p className="eyebrow">Primeiro acesso</p>
          <h2>Vamos criar seu escritório</h2>
          <p className="subtitle">
            Seus clientes, documentos e análises ficarão organizados aqui.
          </p>
          <form onSubmit={createOrg}>
            <label>
              Nome do escritório
              <input
                name="name"
                required
                minLength={2}
                placeholder="Meu escritório"
              />
            </label>
            <Button disabled={busy}>Criar espaço de trabalho</Button>
          </form>
          {error && <Notice error>{error}</Notice>}
        </div>
      </div>
    );
  return (
    <div className="app">
      <aside className="sidebar">
        <Brand />
        <p className="workspace-label">ESPAÇO DE TRABALHO</p>
        {[
          { id: "overview", label: "Visão geral", icon: LayoutDashboard },
          { id: "clients", label: "Clientes", icon: Building2 },
          { id: "analyses", label: "Análises fiscais", icon: FileSearch },
          { id: "rules", label: "Base de regras", icon: BookOpen },
          {
            id: "assessments",
            label: "Apuração de impostos",
            icon: Calculator,
          },
          { id: "settings", label: "Escritório", icon: Settings2 },
        ].map((n) => (
          <button
            key={n.id}
            className={`nav ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}
          >
            <n.icon size={18} />
            {n.label}
          </button>
        ))}
        <div className="sidebar-bottom">
          <ShieldCheck
            size={20}
            style={{ color: "#b4d583", marginBottom: 12 }}
          />
          <strong>Análise com rastreabilidade</strong>Cada apontamento preserva
          sua origem e a regra utilizada.
          <div style={{ marginTop: 25, fontSize: 10, color: "#7f9f8b" }}>
            RASPUTIN · CONFERÊNCIA FISCAL
          </div>
        </div>
      </aside>
      <div className="shell">
        <header className="topbar">
          <span>
            {me.organization.nome}{" "}
            <ChevronRight
              size={12}
              style={{ display: "inline", margin: "0 9px" }}
            />{" "}
            {
              (
                {
                  overview: "Visão geral",
                  clients: "Clientes",
                  analyses: "Análises",
                  rules: "Base de regras",
                  assessments: "Apuração de impostos",
                  settings: "Escritório",
                } as Record<string, string>
              )[page]
            }
          </span>
          <div className="top-right">
            <div className="pill">
              <ShieldCheck />
              Somente leitura
            </div>
            <div className="avatar">
              {session.user.email?.slice(0, 2).toUpperCase()}
            </div>
            <button
              className="button ghost"
              title="Sair"
              aria-label="Sair"
              onClick={() => supabase?.auth.signOut()}
            >
              <LogOut />
            </button>
          </div>
        </header>
        <main className="content">
          {page === "rules" ? (
            <Rules call={call} admin={me.role === "admin"} />
          ) : page === "assessments" ? (
            <Assessments call={call} clients={clients} />
          ) : page === "settings" ? (
            <Settings call={call} me={me} />
          ) : (
            <>
              <div className="title-row">
                <div>
                  <p className="eyebrow">
                    Conferência fiscal para alimentação e bebidas
                  </p>
                  <h1>
                    {page === "clients"
                      ? "Seus clientes"
                      : page === "analyses"
                        ? "Análises fiscais"
                        : "Clareza em cada análise."}
                  </h1>
                  <p className="subtitle">
                    {page === "clients"
                      ? "Organize os estabelecimentos e seus perfis fiscais."
                      : "Documentos, evidências e regras. Tudo no mesmo lugar."}
                  </p>
                </div>
                <Button
                  onClick={() =>
                    setModal(
                      page === "clients" || !client ? "client" : "upload",
                    )
                  }
                >
                  <Plus />
                  {page === "clients" || !client
                    ? "Cadastrar cliente"
                    : "Enviar documentos"}
                </Button>
              </div>
              {page === "clients" ? (
                <div className="card">
                  <div className="card-head">
                    <h2>Estabelecimentos</h2>
                    <small>{clients.length} cadastrados</small>
                  </div>
                  {!clients.length ? (
                    <Empty
                      title="Seu primeiro cliente começa aqui"
                      text="Cadastre o CNPJ e o perfil fiscal para iniciar a conferência."
                    />
                  ) : (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Cliente</th>
                            <th>CNPJ</th>
                            <th>Regime</th>
                            <th>UF</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {clients.map((c) => (
                            <tr key={c.id}>
                              <td>
                                <div className="cell-title">
                                  {c.razao_social}
                                </div>
                                <small>{c.profiles.length} vigência(s)</small>
                              </td>
                              <td>{c.cnpj}</td>
                              <td>
                                {regimes[
                                  c.profiles.at(-1)?.regime_federal || ""
                                ] || "—"}
                              </td>
                              <td>{c.profiles.at(-1)?.uf}</td>
                              <td>
                                <Button
                                  secondary
                                  onClick={() => {
                                    setClientId(c.id);
                                    setPage("overview");
                                  }}
                                >
                                  Abrir
                                  <ArrowUpRight />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <div className="toolbar" style={{ marginBottom: 24 }}>
                    <select
                      aria-label="Cliente selecionado"
                      className="client-select"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                    >
                      <option value="" disabled>
                        Selecione um cliente
                      </option>
                      {clients.map((c) => (
                        <option value={c.id} key={c.id}>
                          {c.razao_social}
                        </option>
                      ))}
                    </select>
                    {profile && (
                      <>
                        <span className="pill">
                          {regimes[profile.regime_federal]} · {profile.uf}
                        </span>
                        {me.role === "admin" && (
                          <button
                            className="button ghost"
                            onClick={() => setModal("profile")}
                          >
                            Editar vigência
                          </button>
                        )}
                      </>
                    )}
                  </div>
                  {page === "overview" && (
                    <div className="stats">
                      {[
                        {
                          label: "Documentos enviados",
                          value: uploads.length,
                          note: "Arquivos do cliente selecionado",
                          icon: FolderOpen,
                        },
                        {
                          label: "Análises concluídas",
                          value: done.length,
                          note: "Resultados disponíveis para consulta",
                          icon: FileCheck2,
                        },
                        {
                          label: "Apontamentos",
                          value: findings,
                          note: "Nas análises concluídas exibidas",
                          icon: FileSearch,
                        },
                        {
                          label: "Em processamento",
                          value:
                            uploads.filter((u) =>
                              ["enviado", "processando"].includes(u.status),
                            ).length +
                            analyses.filter((a) =>
                              ["pendente", "executando"].includes(a.status),
                            ).length,
                          note: "Ingestões e análises na fila",
                          icon: Activity,
                        },
                      ].map((s) => (
                        <div className="stat" key={s.label}>
                          <div className="stat-label">
                            {s.label}
                            <s.icon />
                          </div>
                          <div className="stat-number">
                            {s.value.toString().padStart(2, "0")}
                          </div>
                          <div className="stat-note">{s.note}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="card">
                    <div className="card-head">
                      <div>
                        <h2>Análises recentes</h2>
                        <p className="subtitle" style={{ marginTop: 5 }}>
                          Histórico preservado por período e versão da base.
                        </p>
                      </div>
                      <Button
                        secondary
                        disabled={
                          !uploads.some((u) => u.status === "processado")
                        }
                        onClick={() => {
                          setSelected(
                            uploads
                              .filter((u) => u.status === "processado")
                              .map((u) => u.id),
                          );
                          setModal("analysis");
                        }}
                      >
                        <Plus />
                        Nova análise
                      </Button>
                    </div>
                    {!analyses.length ? (
                      <Empty
                        title="Tudo pronto para começar a conferir"
                        text={
                          client
                            ? "Envie os documentos deste cliente. Depois da ingestão, escolha o período e inicie a análise."
                            : "Cadastre o primeiro cliente para organizar os documentos e iniciar as análises."
                        }
                      >
                        <Button
                          secondary
                          onClick={() => setModal(client ? "upload" : "client")}
                        >
                          <UploadCloud />
                          {client
                            ? "Enviar primeiro arquivo"
                            : "Cadastrar primeiro cliente"}
                        </Button>
                      </Empty>
                    ) : (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Período</th>
                              <th>Status</th>
                              <th>Apontamentos</th>
                              <th>Cobertura</th>
                              <th></th>
                            </tr>
                          </thead>
                          <tbody>
                            {analyses.map((a) => (
                              <tr key={a.id}>
                                <td className="cell-title">
                                  {formatDate(a.periodo_ini)} —{" "}
                                  {formatDate(a.periodo_fim)}
                                </td>
                                <td>
                                  <Status value={a.status} />
                                  {a.erro && (
                                    <details>
                                      <summary>Ver erro</summary>
                                      {a.erro}
                                    </details>
                                  )}
                                </td>
                                <td>{a.resumo?.findings ?? "—"}</td>
                                <td>
                                  {a.status === "concluida"
                                    ? a.parcial
                                      ? "Parcial / limitada"
                                      : "Checagens executadas"
                                    : "—"}
                                </td>
                                <td>
                                  <Button
                                    secondary
                                    disabled={busy || a.status !== "concluida"}
                                    onClick={() => openAnalysis(a.id)}
                                  >
                                    Ver resultado
                                    <ArrowUpRight />
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                  {page === "overview" && (
                    <div className="two-col">
                      <div className="card">
                        <div className="card-head">
                          <h2>Arquivos do cliente</h2>
                          <small>{uploads.length} enviados</small>
                        </div>
                        {!uploads.length ? (
                          <Empty
                            title="Nenhum documento enviado"
                            text="XMLs e planilhas ficam disponíveis aqui com o resultado da ingestão."
                          />
                        ) : (
                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>Arquivo</th>
                                  <th>Ingestão</th>
                                  <th>Linhas</th>
                                </tr>
                              </thead>
                              <tbody>
                                {uploads.map((u) => (
                                  <tr key={u.id}>
                                    <td>
                                      <div className="cell-title">{u.nome}</div>
                                      <small>
                                        {u.tipo.toUpperCase()}
                                        {u.parcial ? " · parcial" : ""}
                                      </small>
                                      {u.ingestion_report && (
                                        <details>
                                          <summary>Ver leitura</summary>
                                          <pre>
                                            {JSON.stringify(
                                              u.ingestion_report,
                                              null,
                                              2,
                                            )}
                                          </pre>
                                        </details>
                                      )}
                                    </td>
                                    <td>
                                      <Status value={u.status} />
                                    </td>
                                    <td>{u.ingestion_report?.read ?? "—"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                      <div className="card">
                        <div className="card-head">
                          <h2>Da origem à evidência</h2>
                          <ShieldCheck size={18} />
                        </div>
                        <div className="card-body">
                          <div className="steps">
                            {[
                              {
                                t: "Envie os documentos",
                                d: "XMLs de NF-e/NFC-e ou planilhas com colunas confirmadas.",
                              },
                              {
                                t: "Analise com contexto",
                                d: "Regras aprovadas consideram regime, operação e vigência.",
                              },
                              {
                                t: "Compartilhe os resultados",
                                d: "Relatório PDF e anexo XLSX com as ocorrências e suas fontes.",
                              },
                            ].map((s, i) => (
                              <div className="step" key={s.t}>
                                <span className="step-num">0{i + 1}</span>
                                <div>
                                  <h3>{s.t}</h3>
                                  <p>{s.d}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                          <div className="regime-list">
                            <span>Simples Nacional</span>
                            <span>Lucro Presumido</span>
                            <span>Lucro Real</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}
          <footer className="footer">
            <span>
              Relatório de conferência. Não substitui a validação do contador
              responsável.
            </span>
            <span>Rasputin · Somente leitura</span>
          </footer>
        </main>
      </div>
      {error && (
        <div className="alert-toast">
          <Notice error>
            {error}
            <button className="button ghost" onClick={() => setError("")}>
              Fechar
            </button>
          </Notice>
        </div>
      )}
      {modal === "client" && (
        <Modal title="Cadastrar cliente" onClose={() => setModal("")}>
          <ClientForm
            call={call}
            onDone={() => {
              setModal("");
              void loadClients();
            }}
          />
        </Modal>
      )}
      {modal === "profile" && client && (
        <Modal title="Nova vigência fiscal" onClose={() => setModal("")}>
          <ClientForm
            call={call}
            client={client}
            onDone={() => {
              setModal("");
              void loadClients();
            }}
          />
        </Modal>
      )}
      {modal === "upload" && client && (
        <Modal
          title={`Enviar documentos · ${client.razao_social}`}
          onClose={() => setModal("")}
          wide
        >
          <UploadForm
            call={call}
            clientId={clientId}
            onDone={() => {
              setModal("");
              void loadWork();
            }}
          />
        </Modal>
      )}
      {modal === "analysis" && (
        <Modal title="Iniciar análise" onClose={() => setModal("")}>
          <form onSubmit={startAnalysis}>
            <div className="form-grid">
              <label>
                Data inicial
                <input type="date" name="start" required />
              </label>
              <label>
                Data final
                <input type="date" name="end" required />
              </label>
            </div>
            <h3 style={{ marginTop: 25 }}>Arquivos que compõem esta análise</h3>
            <div className="file-list">
              {uploads
                .filter((u) => u.status === "processado")
                .map((u) => (
                  <label className="file-row check" key={u.id}>
                    <input
                      type="checkbox"
                      checked={selected.includes(u.id)}
                      onChange={(e) =>
                        setSelected((old) =>
                          e.target.checked
                            ? [...old, u.id]
                            : old.filter((id) => id !== u.id),
                        )
                      }
                    />
                    <span>{u.nome}</span>
                    {u.parcial && <Status value="revisar" />}
                  </label>
                ))}
            </div>
            <Notice>
              A análise preservará os arquivos, o perfil e a base de regras
              utilizados. Regras não aprovadas ou dados insuficientes serão
              indicados como não avaliados.
            </Notice>
            <div className="actions">
              <Button disabled={busy || !selected.length}>
                Iniciar conferência
              </Button>
            </div>
          </form>
        </Modal>
      )}
      {modal === "detail" && detail && (
        <Modal
          title="Resultado da conferência"
          onClose={() => setModal("")}
          wide
        >
          <AnalysisDetail analysis={detail} call={call} />
        </Modal>
      )}
    </div>
  );
}
function Settings({ call, me }: { call: Call; me: Me }) {
  const [events, setEvents] = useState<
      { acao: string; criado_em: string; entidade_id: string }[]
    >([]),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [logo, setLogo] = useState<string | null>(
      me.organization?.branding.logo_data_url || null,
    );
  useEffect(() => {
    if (me.role === "admin")
      void call<typeof events>("/audit")
        .then(setEvents)
        .catch((e) => setError(e.message));
  }, [call, me.role]);
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await call(
        "/branding",
        {
          nome: f.get("nome"),
          rodape: f.get("rodape"),
          cor: f.get("cor"),
          logo_data_url: logo,
        },
        "PUT",
      );
      setMessage("Identidade do relatório atualizada.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="title-row">
        <div>
          <p className="eyebrow">Seu escritório</p>
          <h1>Identidade e rastreabilidade</h1>
          <p className="subtitle">
            Personalize os relatórios e acompanhe as ações da organização.
          </p>
        </div>
      </div>
      {me.role === "admin" ? (
        <>
          <div className="card">
            <div className="card-head">
              <h2>Identidade dos relatórios</h2>
            </div>
            <form className="card-body" onSubmit={save}>
              <div className="form-grid">
                <label>
                  Nome exibido
                  <input
                    name="nome"
                    defaultValue={
                      me.organization?.branding.nome || me.organization?.nome
                    }
                    required
                  />
                </label>
                <label>
                  Cor principal
                  <input
                    name="cor"
                    type="color"
                    defaultValue={me.organization?.branding.cor || "#173D35"}
                  />
                </label>
                <label className="full">
                  Logo do escritório (PNG/JPEG, até 2 MB)
                  <input
                    type="file"
                    accept="image/png,image/jpeg"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      if (f.size > 2000000) {
                        setError("Logo deve ter até 2 MB.");
                        return;
                      }
                      const reader = new FileReader();
                      reader.onload = () => setLogo(String(reader.result));
                      reader.readAsDataURL(f);
                    }}
                  />
                </label>
                <label className="full">
                  Rodapé adicional
                  <input
                    name="rodape"
                    defaultValue={me.organization?.branding.rodape || ""}
                  />
                </label>
              </div>
              <div className="actions">
                <Button>Salvar identidade</Button>
              </div>
              {message && <Notice>{message}</Notice>}
            </form>
          </div>
          <div className="card">
            <div className="card-head">
              <h2>Registro de atividades</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Quando</th>
                    <th>Ação</th>
                    <th>Referência</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, i) => (
                    <tr key={i}>
                      <td>{new Date(e.criado_em).toLocaleString("pt-BR")}</td>
                      <td>{e.acao.replaceAll("_", " ")}</td>
                      <td className="mono">{e.entidade_id || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <Notice>
          Somente administradores podem alterar a identidade do escritório.
        </Notice>
      )}
      {error && <Notice error>{error}</Notice>}
    </>
  );
}
