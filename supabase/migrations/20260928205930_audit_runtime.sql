-- Runtime do MVP: contratos imutáveis, fila recuperável e regras por escritório.
-- Não altera arquivos nem sistemas dos clientes.
alter table public.uploads add column canonical_payload jsonb;
alter table public.uploads add column mapping_snapshot jsonb;
alter table public.uploads add column parser_version text;
alter table public.uploads add constraint uploads_id_client_org unique (id, cliente_id, organizacao_id);
alter table public.analises add constraint analises_id_client_org unique (id, cliente_id, organizacao_id);
alter table public.documentos add constraint documentos_upload_cliente_fk
  foreign key (upload_id, cliente_id, organizacao_id)
  references public.uploads (id, cliente_id, organizacao_id);
alter table public.analise_uploads add column cliente_id uuid;
update public.analise_uploads au set cliente_id = a.cliente_id from public.analises a where a.id=au.analise_id;
alter table public.analise_uploads alter column cliente_id set not null;
alter table public.analise_uploads add constraint analise_uploads_analysis_client_fk
  foreign key (analise_id, cliente_id, organizacao_id)
  references public.analises (id, cliente_id, organizacao_id);
alter table public.analise_uploads add constraint analise_uploads_upload_client_fk
  foreign key (upload_id, cliente_id, organizacao_id)
  references public.uploads (id, cliente_id, organizacao_id);

create table public.fiscal_rules (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null references public.organizacoes(id),
  code text not null check (code in ('C02','C05','C07','C08','R02','R04','R05')),
  status text not null default 'proposta' check (status in ('proposta','aprovada','rejeitada')),
  definition jsonb not null,
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  criado_em timestamptz not null default now(),
  unique(id, organizacao_id),
  check (status <> 'aprovada' or (approved_by is not null and approved_at is not null))
);
create index fiscal_rules_org_idx on public.fiscal_rules(organizacao_id,status);
create table public.rule_sets (
  id uuid primary key default gen_random_uuid(),
  organizacao_id uuid not null references public.organizacoes(id),
  sha256 text not null,
  rules jsonb not null,
  criado_em timestamptz not null default now(),
  unique(id, organizacao_id),
  unique(organizacao_id, sha256)
);
alter table public.analises add column rule_set_id uuid;
alter table public.analises add column input_snapshot jsonb;
alter table public.analises add column result_payload jsonb;
alter table public.analises add column input_hash text;
alter table public.analises add column erro text;
alter table public.analises add constraint analysis_rules_org_fk foreign key(rule_set_id, organizacao_id)
  references public.rule_sets(id, organizacao_id);
alter table public.jobs add column dedupe_key text;
alter table public.jobs add column lock_token uuid;
create unique index jobs_dedupe_idx on public.jobs(organizacao_id, dedupe_key) where dedupe_key is not null;
alter table public.relatorios add constraint relatorios_analysis_unique unique(analise_id);

-- Toda regra publicada é imutável; revisões são novas propostas.
create function public.fiscal_immutable() returns trigger language plpgsql set search_path='' as $$
begin
  raise exception 'Registro publicado imutável';
end $$;
create trigger rule_sets_immutable before update or delete on public.rule_sets
  for each row execute function public.fiscal_immutable();
create function public.fiscal_rule_guard() returns trigger language plpgsql set search_path='' as $$
begin
  if old.status <> 'proposta' then raise exception 'Regra publicada/rejeitada é imutável'; end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end $$;
create trigger fiscal_rules_guard before update or delete on public.fiscal_rules
  for each row execute function public.fiscal_rule_guard();

-- Serializa alterações do perfil por cliente e impede sobreposição de vigências.
create function public.fiscal_profile_guard() returns trigger language plpgsql set search_path='' as $$
begin
  perform 1 from public.clientes where id=new.cliente_id for update;
  if exists(select 1 from public.perfil_fiscal p where p.cliente_id=new.cliente_id
    and p.id <> new.id and daterange(p.valid_from,p.valid_to,'[]') &&
    daterange(new.valid_from,new.valid_to,'[]')) then
    raise exception 'Vigências de perfil fiscal sobrepostas';
  end if;
  return new;
end $$;
create trigger fiscal_profile_period before insert or update on public.perfil_fiscal
  for each row execute function public.fiscal_profile_guard();
create function public.fiscal_analysis_guard() returns trigger language plpgsql set search_path='' as $$
begin
  if old.status='concluida' then raise exception 'Análise concluída imutável'; end if;
  if new.input_snapshot is distinct from old.input_snapshot or
     new.rule_set_id is distinct from old.rule_set_id then
    raise exception 'Entradas e regras da análise são imutáveis';
  end if;
  return new;
end $$;
create trigger fiscal_analysis_snapshot before update on public.analises
  for each row execute function public.fiscal_analysis_guard();

-- Escritas da aplicação passam por endpoints autenticados que validam referências,
-- registram o ator e não permitem forjar hashes, status, evidências ou jobs.
do $$ declare t text; begin
  foreach t in array array['clientes','perfil_fiscal','uploads','layout_templates','jobs','audit_log'] loop
    execute format('revoke insert,update,delete on public.%I from authenticated',t);
  end loop;
  foreach t in array array['fiscal_rules','rule_sets'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon,authenticated',t);
    execute format('grant select on public.%I to authenticated',t);
    execute format('create policy %I on public.%I for select to authenticated using '
      ||'(organizacao_id in (select public.minhas_organizacoes()))',t||'_read',t);
  end loop;
  foreach t in array array['organizacoes','membros','clientes','perfil_fiscal','uploads',
    'layout_templates','jobs','documentos','itens','itens_tributos','origem_linha','analises',
    'analise_uploads','findings','relatorios','audit_log','ia_chamadas','knowledge_versions',
    'ncm_oficial','cest','cfop','cst_icms','csosn','cst_pis_cofins','cst_ipi',
    'uf_aliquota_modal','icms_regra_produto','st_vigente','pis_cofins_regra',
    'regime_especial_restaurante'] loop
    execute format('grant select on public.%I to authenticated',t);
  end loop;
end $$;
revoke all on function public.fiscal_immutable() from public,anon,authenticated;
revoke all on function public.fiscal_rule_guard() from public,anon,authenticated;
revoke all on function public.fiscal_profile_guard() from public,anon,authenticated;
revoke all on function public.fiscal_analysis_guard() from public,anon,authenticated;
-- O seed original é preservado para revisão, mesmo se não tiver todos os campos
-- necessários a uma regra executável. 'Confirmar' jamais se torna aprovação.
create table public.seed_rows (
 id uuid primary key default gen_random_uuid(),
 organizacao_id uuid not null references public.organizacoes(id),
 source_hash text not null,
 sheet text not null,
 row_number integer not null,
 raw jsonb not null,
 criado_em timestamptz not null default now(),
 unique(organizacao_id,source_hash,sheet,row_number)
);
alter table public.seed_rows enable row level security;
revoke all on public.seed_rows from anon,authenticated;
grant select on public.seed_rows to authenticated;
create policy seed_rows_read on public.seed_rows for select to authenticated
 using(organizacao_id in (select public.minhas_organizacoes()));
alter table public.documentos drop constraint documentos_situacao_check;
alter table public.documentos add constraint documentos_situacao_check
 check(situacao in ('autorizada','cancelada','denegada','inutilizada','desconhecida'));
alter table public.itens alter column v_desc drop not null;
alter table public.itens alter column v_frete drop not null;
alter table public.itens alter column v_seg drop not null;
alter table public.itens alter column v_outras drop not null;
alter table public.analises add column report_context jsonb;
alter table public.findings add column fiscal_rule_id uuid;
alter table public.findings add constraint findings_fiscal_rule_fk
 foreign key(fiscal_rule_id,organizacao_id) references public.fiscal_rules(id,organizacao_id);
