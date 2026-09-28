-- M1 / base de conhecimento versionada. Regras tributárias são dados, não código.
-- Faixas de NCM ficam normalizadas em 8 dígitos: ncm_de preenchido com 0 e ncm_ate com 9
-- (ex.: posição 0701 -> 07010000..07019999). Percentuais em fração (0.07 = 7%).

create table public.ncm_oficial (
  codigo char(8) not null check (codigo ~ '^[0-9]{8}$'),
  descricao text not null
);

create table public.cest (
  codigo char(7) not null check (codigo ~ '^[0-9]{7}$'),
  ncm_prefixo text not null check (ncm_prefixo ~ '^[0-9]{2,8}$'),
  segmento text,
  descricao text
);

create table public.cfop (
  codigo char(4) not null check (codigo ~ '^[0-9]{4}$'),
  descricao text not null,
  natureza text
);

create table public.cst_icms (codigo char(2) not null, descricao text not null);
create table public.csosn (codigo char(3) not null, descricao text not null);
create table public.cst_pis_cofins (codigo char(2) not null, descricao text not null);
create table public.cst_ipi (codigo char(2) not null, descricao text not null);

create table public.uf_aliquota_modal (
  uf char(2) not null,
  aliquota_modal numeric(7, 6) not null,
  fcp numeric(7, 6) not null default 0,
  base_legal text
);

create table public.icms_regra_produto (
  uf char(2) not null,
  ncm_de char(8) not null check (ncm_de ~ '^[0-9]{8}$'),
  ncm_ate char(8) not null check (ncm_ate ~ '^[0-9]{8}$'),
  ncm_original text,
  descricao text,
  categoria text,
  condicao jsonb not null default '{}'::jsonb,
  aliquota numeric(7, 6),
  carga_efetiva numeric(7, 6),
  tipo_beneficio text,
  tratamento text,
  base_legal text,
  observacao text,
  check (ncm_de <= ncm_ate)
);

create table public.st_vigente (
  uf char(2) not null,
  cest char(7),
  ncm_de char(8) not null check (ncm_de ~ '^[0-9]{8}$'),
  ncm_ate char(8) not null check (ncm_ate ~ '^[0-9]{8}$'),
  sujeita boolean not null,
  base_legal text,
  observacao text,
  check (ncm_de <= ncm_ate)
);

create table public.pis_cofins_regra (
  ncm_de char(8) not null check (ncm_de ~ '^[0-9]{8}$'),
  ncm_ate char(8) not null check (ncm_ate ~ '^[0-9]{8}$'),
  tratamento text not null check (tratamento in ('monofasico', 'aliquota_zero', 'normal')),
  base_legal text,
  observacao text,
  check (ncm_de <= ncm_ate)
);

create table public.regime_especial_restaurante (
  uf char(2) not null,
  percentual numeric(7, 6) not null,
  condicoes jsonb not null default '{}'::jsonb,
  base_legal text
);

-- Colunas comuns de versionamento e aprovação, aplicadas a todas as tabelas acima.
do $$
declare
  t text;
begin
  foreach t in array array[
    'ncm_oficial', 'cest', 'cfop', 'cst_icms', 'csosn', 'cst_pis_cofins', 'cst_ipi',
    'uf_aliquota_modal', 'icms_regra_produto', 'st_vigente', 'pis_cofins_regra',
    'regime_especial_restaurante'
  ]
  loop
    execute format($f$
      alter table public.%1$I
        add column id uuid primary key default gen_random_uuid(),
        add column valid_from date not null,
        add column valid_to date,
        add column source_url text,
        add column source_hash text,
        add column status text not null default 'proposta'
          check (status in ('proposta', 'aprovada', 'rejeitada')),
        add column approved_by uuid references auth.users (id) on delete set null,
        add column approved_at timestamptz,
        add column knowledge_version_id bigint references public.knowledge_versions (id),
        add column criado_em timestamptz not null default now(),
        add constraint %1$I_vigencia_chk check (valid_to is null or valid_to >= valid_from),
        add constraint %1$I_aprovacao_chk check (
          status <> 'aprovada' or (approved_at is not null and knowledge_version_id is not null)
        )
    $f$, t);
    execute format(
      'create index %1$I_vigencia_idx on public.%1$I (status, valid_from, valid_to)', t);
  end loop;
end
$$;
