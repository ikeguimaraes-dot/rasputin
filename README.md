# Rasputin — conferência fiscal para restaurantes

MVP web de **somente leitura**: upload de XML/ZIP, XLS/XLSX/CSV, normalização, checagens
determinísticas, evidências e relatórios PDF/XLSX. Perfis com vigência para **Simples Nacional,
Lucro Presumido e Lucro Real**. Não emite, transmite nem corrige documentos do cliente.

## Estado da entrega

Implementado e testado localmente:
- Interface Next.js: autenticação Supabase, escritório, clientes/perfis, upload/mapeamento,
  acompanhamento, resultados agrupados por produto, downloads, base/aprovação e atividades.
- API Python autenticada: valida usuário no Supabase Auth e organização no banco em cada chamada.
- Fila PostgreSQL com `SKIP LOCKED`, deduplicação, tentativas, bloqueio por tarefa e recuperação.
- XML/NFC-e e ZIP com limites; planilhas com cabeçalhos compostos e templates confirmados;
  recuperação conservadora BIFF8 para XLS danificado, sempre marcada parcial.
- Motor C01–C09, R02/R04/R05 por regras/contextos aprovados. Ver [contrato fiscal](docs/fiscal/contrato.md).
- Snapshots de entradas, perfil, layout, fontes de ingestão, regras e identidade do relatório.
- PDF/XLSX, evidências, cobertura não avaliada, impactos **potenciais documentais**, reemissão.
- RLS, vínculos por organização/cliente, regras publicadas imutáveis e log de ações.
- Ingestão do seed original para área de revisão; aprovação explícita de regras executáveis.
- IA opcional somente para sugerir mapeamento **a partir dos cabeçalhos**, sem enviar linhas de clientes.

**Ainda não publicado em produção.** A API Supabase do projeto fornecido respondeu, mas a
conexão PostgreSQL local não estava utilizável. Os buckets privados `uploads` e `reports` já foram
criados e verificados no projeto informado. As migrations foram executadas e validadas em
PostgreSQL WASM isolado. Não foram aplicadas ao projeto remoto. A planilha fiscal real e sua
validação também estão pendentes; não há alíquotas de teste ativadas em produção.

## Rodar localmente

Pré-requisitos: Python 3.12 + `uv`, Node 22+, npm e Supabase CLI.

```sh
uv sync --project worker --frozen
npm ci --prefix apps/web
make env
# Preencher .env com as configurações reais; nunca versionar esse arquivo.
make web-env
make db-preflight   # somente primeira instalação, em banco sem estas tabelas
make db-push
make db-test-rls
make dev           # terminal 1 — API/worker em http://localhost:8000
make web           # terminal 2 — frontend em http://localhost:3000
```

No macOS, instale Pango (`brew install pango`) para PDF. `make dev` configura a busca das bibliotecas
Homebrew em Apple Silicon. No Linux, instale `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz0b` e fontes.

`DATABASE_URL` deve ser a URL PostgreSQL real, preferencialmente pooler **Session**, porta 5432.
Codifique caracteres especiais da senha. `anon/service_role` são chaves HTTP e não substituem a senha
do banco. `/health` verifica processo; `/ready` verifica conectividade e schema.

Para Supabase local: `supabase start`, use as URLs/chaves apresentadas pelo CLI e aplique as migrations.
O `compose.yaml` sobe o worker; Supabase local é gerenciado pelo próprio CLI. Em Docker, ajuste os
endereços do Supabase local para `host.docker.internal` quando necessário.

## Primeiro uso

1. Criar conta ou entrar; configurar confirmação/SMTP pelo painel Supabase conforme o ambiente.
2. Criar escritório e cadastrar cliente com CNPJ, regime e início da vigência.
3. Enviar XML/ZIP ou conferir e confirmar o mapeamento da planilha.
4. Esperar a ingestão; conferir linhas descartadas, advertências e período coberto.
5. Em “Base de regras”, importar a planilha e cadastrar/aprovar os tratamentos validados.
6. Iniciar análise escolhendo arquivos e período. Sem base fiscal aprovada, serão executadas
   somente as checagens possíveis e as limitações aparecerão explicitamente.
7. Abrir resultado; conferir evidências/não avaliadas; baixar PDF e XLSX.

O arquivo [fixtures/sinteticas/nota.xml](fixtures/sinteticas/nota.xml) é exclusivamente sintético:
CNPJ `11111111000111`, agosto/2026. Não é nota fiscal válida nem fonte de alíquotas reais.

## Verificação

```sh
make lint
make test-db          # migrations + RLS + imutabilidade em Postgres descartável
make test            # unitários; integração exige TEST_DATABASE_URL
make test-integration # sobe Postgres descartável e executa toda a suíte
make build
```

**Validação da entrega:** 65 testes passaram, cobertura total 84% e motor 95%; lint, TypeScript,
build de produção, migrations/RLS e navegação desktop/mobile passaram.

O teste integrado usa PostgreSQL de verdade compilado em WASM (PGlite), simula somente Auth/Storage
externos e exercita API → fila → ingestão → análise → PDF/XLSX → reemissão, além de isolamento.
Não substitui teste de concorrência de múltiplos processos em PostgreSQL de produção.

Para validar interface: iniciar `npm --prefix apps/web run start -- --port 3100`, depois
`node apps/web/scripts/test-browser.mjs` (Chrome instalado). Usa sessão e dados sintéticos em um
contexto de navegador separado; não acessa documentos ou conta real. Screenshots em `/private/tmp/rasputin-*.png`.

## Deploy

- **Railway:** repositório na raiz, `railway.toml`, Dockerfile `worker/Dockerfile`, variáveis privadas
  do `.env.example`, `CORS_ORIGINS` com domínio exato do frontend. O processo HTTP também consome a fila.
- **Vercel:** root directory `apps/web`, framework Next.js; configurar somente as três variáveis
  `NEXT_PUBLIC_*` do [exemplo do frontend](apps/web/.env.example).
- **Supabase:** migrations aplicadas, Auth habilitado, buckets privados `uploads`/`reports`, usuários
  vinculados a organizações. Chaves privilegiadas ficam apenas no worker.
- Validar `/ready`, cadastro, upload e download em staging antes de disponibilizar para clientes.

## Estrutura

```text
apps/web/                    Next.js, interface e testes PostgreSQL/navegador
worker/src/auditoria/
  domain.py                  Contratos e Decimal
  ingestion/                 XML/ZIP, planilhas, BIFF8
  engine.py                  Avaliação pura e determinística
  service.py                 Persistência, snapshots e pipeline
  queue.py                   Consumidor idempotente e recuperação
  api.py auth.py storage.py  Fronteiras autenticadas
  reports.py                 HTML/PDF e XLSX
supabase/migrations/          Estrutura + endurecimento + runtime
supabase/tests/               Isolamento, integridade e imutabilidade
fixtures/sinteticas/          Somente dados artificiais
fixtures_privadas/            Ignorado pelo Git
scripts/                     Inicialização, configuração e verificação
docs/fiscal/                 Contrato, hipóteses e limites
```

Não há dependência de IA para decidir um apontamento nem gerar um relatório. Sem chave Anthropic,
a sugestão de mapeamento usa heurística e exige confirmação. O modelo é configurável por ambiente.
A retenção automática e os módulos das fases seguintes não estão ativados neste MVP.
