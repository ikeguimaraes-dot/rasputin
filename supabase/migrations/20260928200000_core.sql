-- M1 / núcleo: tenancy, entrada, modelo canônico e resultados.
-- Toda tabela de cliente carrega organizacao_id e usa FK composta (id, organizacao_id)
-- para que um registro nunca aponte para um pai de outra organização, mesmo que o worker
-- (service role, sem RLS) tenha um bug.

-- ---------------------------------------------------------------- tenancy
create table public.organizacoes (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  branding jsonb not null default '{}'::jsonb,
  retencao_dias integer not null default 365 check (retencao_dias > 0),
  criado_em timestamptz not null default now()
);

create table public.membros (
  user_id uuid not null references auth.users (id) on delete cascade,
  organizacao_id uuid not null references public.organizacoes (id) on delete cascade,
  papel text not null default 'membro' check (papel in ('admin', 'membro')),
  criado_em timestamptz not null default now(),
  primary key (user_id, organizacao_id)
);
create index membros_organizacao_idx on public.membros (organizacao_id);

create table public.clientes (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null references public.organizacoes (id) on delete cascade,
  cnpj text not null check (cnpj ~ '^[0-9]{14}$'),
  razao_social text not null,
  criado_em timestamptz not null default now(),
  unique (id, organizacao_id),
  unique (organizacao_id, cnpj)
);

create table public.perfil_fiscal (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  cliente_id uuid not null,
  uf char(2) not null,
  cnae text,
  regime_federal text not null check (regime_federal in ('simples', 'presumido', 'real')),
  optante_regime_especial_rest boolean not null default false,
  contribuinte_ipi boolean not null default false,
  -- null = não declarado: C09 usa a moda do período e marca divergentes como "revisar".
  metodo_pis_cofins text check (metodo_pis_cofins in ('com_exclusao_icms', 'sem_exclusao_icms')),
  valid_from date not null,
  valid_to date,
  criado_em timestamptz not null default now(),
  check (valid_to is null or valid_to >= valid_from),
  foreign key (cliente_id, organizacao_id) references public.clientes (id, organizacao_id)
    on delete cascade
);
create index perfil_fiscal_cliente_idx on public.perfil_fiscal (cliente_id, valid_from);

create table public.audit_log (
  id bigint generated always as identity primary key,
  organizacao_id uuid not null references public.organizacoes (id) on delete cascade,
  user_id uuid references auth.users (id) on delete set null,
  acao text not null,
  entidade text,
  entidade_id text,
  detalhe jsonb not null default '{}'::jsonb,
  criado_em timestamptz not null default now()
);
create index audit_log_org_idx on public.audit_log (organizacao_id, criado_em desc);

-- ---------------------------------------------------------------- entrada
create table public.uploads (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  cliente_id uuid not null,
  storage_path text not null,
  nome text not null,
  sha256 text,
  tipo text not null check (tipo in ('xml', 'zip', 'xls', 'xlsx', 'csv', 'sped')),
  status text not null default 'enviado'
    check (status in ('enviado', 'processando', 'processado', 'erro')),
  ingestion_report jsonb,
  parcial boolean not null default false,
  criado_por uuid references auth.users (id) on delete set null,
  criado_em timestamptz not null default now(),
  unique (id, organizacao_id),
  foreign key (cliente_id, organizacao_id) references public.clientes (id, organizacao_id)
    on delete cascade
);
create index uploads_cliente_idx on public.uploads (cliente_id, criado_em desc);

create table public.layout_templates (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null references public.organizacoes (id) on delete cascade,
  assinatura_cabecalhos text not null,
  mapeamento jsonb not null,
  confirmado_por uuid references auth.users (id) on delete set null,
  confirmado_em timestamptz,
  criado_em timestamptz not null default now(),
  unique (organizacao_id, assinatura_cabecalhos)
);

-- Fila: o worker faz SELECT ... FOR UPDATE SKIP LOCKED sobre esta tabela.
create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null references public.organizacoes (id) on delete cascade,
  tipo text not null check (tipo in ('ingest_upload', 'run_analysis', 'build_report')),
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pendente'
    check (status in ('pendente', 'executando', 'concluido', 'erro')),
  tentativas integer not null default 0,
  locked_at timestamptz,
  erro text,
  run_after timestamptz not null default now(),
  criado_por uuid references auth.users (id) on delete set null,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
create index jobs_fila_idx on public.jobs (run_after) where status = 'pendente';

-- ---------------------------------------------------------------- modelo canônico
create table public.documentos (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  cliente_id uuid not null,
  upload_id uuid not null,
  chave text check (chave is null or chave ~ '^[0-9]{44}$'),
  modelo smallint check (modelo in (55, 65)),
  serie text,
  numero text,
  data_emissao date not null,
  dest_doc text,
  dest_nome text,
  dest_uf char(2),
  -- null = desconhecido: R04 não aponta e o motivo vai para o relatório de ingestão.
  dest_contribuinte boolean,
  cfop_predominante text,
  v_total numeric(14, 2),
  situacao text not null default 'autorizada'
    check (situacao in ('autorizada', 'cancelada', 'denegada', 'inutilizada')),
  criado_em timestamptz not null default now(),
  unique (id, organizacao_id),
  foreign key (cliente_id, organizacao_id) references public.clientes (id, organizacao_id)
    on delete cascade,
  foreign key (upload_id, organizacao_id) references public.uploads (id, organizacao_id)
    on delete cascade
);
create unique index documentos_chave_uk on public.documentos (cliente_id, chave)
  where chave is not null;
create index documentos_emissao_idx on public.documentos (cliente_id, data_emissao);

create table public.itens (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  documento_id uuid not null,
  n_item integer not null,
  cod_produto text,
  descricao text,
  ncm text,
  cest text,
  cfop text,
  unidade text,
  quantidade numeric(15, 4),
  v_unit numeric(15, 6),
  v_prod numeric(14, 2),
  v_desc numeric(14, 2) not null default 0,
  v_frete numeric(14, 2) not null default 0,
  v_seg numeric(14, 2) not null default 0,
  v_outras numeric(14, 2) not null default 0,
  unique (id, organizacao_id),
  unique (documento_id, n_item),
  foreign key (documento_id, organizacao_id) references public.documentos (id, organizacao_id)
    on delete cascade
);
create index itens_produto_idx on public.itens (organizacao_id, cod_produto);

create table public.itens_tributos (
  item_id uuid primary key,
  organizacao_id uuid not null,
  icms_cst text, icms_csosn text,
  icms_bc numeric(14, 2), icms_aliq numeric(9, 4), icms_valor numeric(14, 2),
  icms_red_bc numeric(9, 4),
  st_bc numeric(14, 2), st_valor numeric(14, 2),
  fcp_bc numeric(14, 2), fcp_aliq numeric(9, 4), fcp_valor numeric(14, 2),
  difal_bc numeric(14, 2), difal_aliq numeric(9, 4),
  difal_valor_origem numeric(14, 2), difal_valor_destino numeric(14, 2),
  ipi_cst text, ipi_bc numeric(14, 2), ipi_aliq numeric(9, 4), ipi_valor numeric(14, 2),
  pis_cst text, pis_bc numeric(14, 2), pis_aliq numeric(9, 4), pis_valor numeric(14, 2),
  cofins_cst text, cofins_bc numeric(14, 2), cofins_aliq numeric(9, 4),
  cofins_valor numeric(14, 2),
  -- Reservado para IBS/CBS (cClassTrib etc.), 2027.
  ibs_cbs jsonb,
  foreign key (item_id, organizacao_id) references public.itens (id, organizacao_id)
    on delete cascade
);

-- Evidência: de onde veio cada item (arquivo+linha, ou chave+n_item).
create table public.origem_linha (
  item_id uuid primary key,
  organizacao_id uuid not null,
  arquivo text,
  linha integer,
  chave text,
  n_item integer,
  foreign key (item_id, organizacao_id) references public.itens (id, organizacao_id)
    on delete cascade
);

-- ---------------------------------------------------------------- resultados
-- Contador global da base de regras: cada mudança aprovada gera uma versão.
create table public.knowledge_versions (
  id bigint generated always as identity primary key,
  descricao text not null,
  criado_em timestamptz not null default now()
);

create table public.analises (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  cliente_id uuid not null,
  periodo_ini date not null,
  periodo_fim date not null,
  knowledge_version_id bigint references public.knowledge_versions (id),
  engine_version text,
  parcial boolean not null default false,
  limitada_simples boolean not null default false,
  status text not null default 'pendente'
    check (status in ('pendente', 'executando', 'concluida', 'erro')),
  resumo jsonb,
  criado_por uuid references auth.users (id) on delete set null,
  criado_em timestamptz not null default now(),
  check (periodo_fim >= periodo_ini),
  unique (id, organizacao_id),
  foreign key (cliente_id, organizacao_id) references public.clientes (id, organizacao_id)
    on delete cascade
);
create index analises_cliente_idx on public.analises (cliente_id, criado_em desc);

create table public.analise_uploads (
  analise_id uuid not null,
  upload_id uuid not null,
  organizacao_id uuid not null,
  primary key (analise_id, upload_id),
  foreign key (analise_id, organizacao_id) references public.analises (id, organizacao_id)
    on delete cascade,
  foreign key (upload_id, organizacao_id) references public.uploads (id, organizacao_id)
    on delete cascade
);

create table public.findings (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  analise_id uuid not null,
  regra_codigo text not null,
  severidade text not null check (severidade in ('erro', 'risco', 'revisar', 'alerta')),
  direcao_impacto text not null check (direcao_impacto in ('pago_a_mais', 'pago_a_menos', 'neutro')),
  -- null quando não dá para calcular com segurança (nunca estimar às cegas).
  impacto_brl numeric(14, 2),
  produto_cod text,
  documento_id uuid,
  item_id uuid,
  evidencia jsonb not null,
  correcao_sugerida jsonb,
  base_legal text,
  fonte_url text,
  rule_ref jsonb,
  knowledge_version_id bigint references public.knowledge_versions (id),
  foreign key (analise_id, organizacao_id) references public.analises (id, organizacao_id)
    on delete cascade,
  foreign key (documento_id, organizacao_id) references public.documentos (id, organizacao_id)
    on delete set null (documento_id),
  foreign key (item_id, organizacao_id) references public.itens (id, organizacao_id)
    on delete set null (item_id)
);
create index findings_analise_idx on public.findings (analise_id, regra_codigo);
create index findings_produto_idx on public.findings (analise_id, produto_cod);

create table public.relatorios (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null,
  analise_id uuid not null,
  pdf_path text,
  xlsx_path text,
  gerado_em timestamptz not null default now(),
  foreign key (analise_id, organizacao_id) references public.analises (id, organizacao_id)
    on delete cascade
);

-- Prompt e resposta de cada chamada ao Claude, sem dados pessoais (sanitizados antes de gravar).
create table public.ia_chamadas (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null references public.organizacoes (id) on delete cascade,
  analise_id uuid,
  upload_id uuid,
  finalidade text not null check (finalidade in ('mapeamento_colunas', 'redacao_relatorio')),
  modelo text not null,
  prompt text not null,
  resposta text,
  criado_em timestamptz not null default now(),
  foreign key (analise_id, organizacao_id) references public.analises (id, organizacao_id)
    on delete set null (analise_id),
  foreign key (upload_id, organizacao_id) references public.uploads (id, organizacao_id)
    on delete set null (upload_id)
);
