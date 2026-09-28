-- M1 / RLS por organização. O worker usa o papel dono do banco (ignora RLS), por isso o
-- isolamento entre organizações também está nas FKs compostas do 0001.

-- ---------------------------------------------------------------- funções auxiliares
create function public.minhas_organizacoes()
returns setof uuid
language sql
stable
security definer
set search_path = ''
as $$
  select m.organizacao_id from public.membros m where m.user_id = (select auth.uid())
$$;

create function public.eh_admin_da_organizacao(org uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.membros m
     where m.user_id = (select auth.uid()) and m.organizacao_id = org and m.papel = 'admin'
  )
$$;

revoke all on function public.minhas_organizacoes() from public, anon;
revoke all on function public.eh_admin_da_organizacao(uuid) from public, anon;
grant execute on function public.minhas_organizacoes() to authenticated;
grant execute on function public.eh_admin_da_organizacao(uuid) to authenticated;

-- ---------------------------------------------------------------- habilitar RLS + privilégios
do $$
declare
  t text;
begin
  foreach t in array array[
    'organizacoes', 'membros', 'clientes', 'perfil_fiscal', 'audit_log', 'uploads',
    'layout_templates', 'jobs', 'documentos', 'itens', 'itens_tributos', 'origem_linha',
    'knowledge_versions', 'analises', 'analise_uploads', 'findings', 'relatorios',
    'ia_chamadas', 'ncm_oficial', 'cest', 'cfop', 'cst_icms', 'csosn', 'cst_pis_cofins',
    'cst_ipi', 'uf_aliquota_modal', 'icms_regra_produto', 'st_vigente', 'pis_cofins_regra',
    'regime_especial_restaurante'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on table public.%I from anon', t);
  end loop;
end
$$;

-- Tabelas escritas só pelo worker: o usuário autenticado apenas lê.
do $$
declare
  t text;
begin
  foreach t in array array[
    'organizacoes', 'membros', 'documentos', 'itens', 'itens_tributos', 'origem_linha',
    'analises', 'analise_uploads', 'findings', 'relatorios', 'ia_chamadas',
    'knowledge_versions', 'ncm_oficial', 'cest', 'cfop', 'cst_icms', 'csosn',
    'cst_pis_cofins', 'cst_ipi', 'uf_aliquota_modal', 'icms_regra_produto', 'st_vigente',
    'pis_cofins_regra', 'regime_especial_restaurante'
  ]
  loop
    execute format('revoke insert, update, delete on table public.%I from authenticated', t);
  end loop;
end
$$;

-- Log de auditoria imutável: sem update/delete para ninguém que passe pela API.
revoke update, delete on table public.audit_log from authenticated;
-- Jobs: o usuário só enfileira e consulta; quem muda estado é o worker.
revoke update, delete on table public.jobs from authenticated;

-- ---------------------------------------------------------------- políticas
create policy organizacoes_select on public.organizacoes
  for select to authenticated using (id in (select public.minhas_organizacoes()));

create policy membros_select on public.membros
  for select to authenticated using (user_id = (select auth.uid()));

-- Leitura por organização (tabelas escritas pelo worker).
do $$
declare
  t text;
begin
  foreach t in array array[
    'documentos', 'itens', 'itens_tributos', 'origem_linha', 'analises', 'analise_uploads',
    'findings', 'relatorios', 'ia_chamadas'
  ]
  loop
    execute format(
      'create policy %1$I_select on public.%1$I for select to authenticated '
      'using (organizacao_id in (select public.minhas_organizacoes()))', t);
  end loop;
end
$$;

-- CRUD por organização; apagar exige papel admin.
do $$
declare
  t text;
begin
  foreach t in array array['clientes', 'perfil_fiscal', 'uploads', 'layout_templates']
  loop
    execute format(
      'create policy %1$I_select on public.%1$I for select to authenticated '
      'using (organizacao_id in (select public.minhas_organizacoes()))', t);
    execute format(
      'create policy %1$I_insert on public.%1$I for insert to authenticated '
      'with check (organizacao_id in (select public.minhas_organizacoes()))', t);
    execute format(
      'create policy %1$I_update on public.%1$I for update to authenticated '
      'using (organizacao_id in (select public.minhas_organizacoes())) '
      'with check (organizacao_id in (select public.minhas_organizacoes()))', t);
    execute format(
      'create policy %1$I_delete on public.%1$I for delete to authenticated '
      'using (public.eh_admin_da_organizacao(organizacao_id))', t);
  end loop;
end
$$;

create policy jobs_select on public.jobs
  for select to authenticated using (organizacao_id in (select public.minhas_organizacoes()));
create policy jobs_insert on public.jobs
  for insert to authenticated
  with check (
    organizacao_id in (select public.minhas_organizacoes())
    and criado_por = (select auth.uid())
    and status = 'pendente'
  );

create policy audit_log_select on public.audit_log
  for select to authenticated using (organizacao_id in (select public.minhas_organizacoes()));
create policy audit_log_insert on public.audit_log
  for insert to authenticated
  with check (
    organizacao_id in (select public.minhas_organizacoes())
    and user_id = (select auth.uid())
  );

-- Base de conhecimento: global e sem dado de cliente; qualquer usuário autenticado lê.
do $$
declare
  t text;
begin
  foreach t in array array[
    'knowledge_versions', 'ncm_oficial', 'cest', 'cfop', 'cst_icms', 'csosn',
    'cst_pis_cofins', 'cst_ipi', 'uf_aliquota_modal', 'icms_regra_produto', 'st_vigente',
    'pis_cofins_regra', 'regime_especial_restaurante'
  ]
  loop
    execute format(
      'create policy %1$I_select on public.%1$I for select to authenticated using (true)', t);
  end loop;
end
$$;

-- ---------------------------------------------------------------- Storage (buckets privados)
-- Convenção de caminho: {organizacao_id}/{cliente_id}/{upload_id}/{arquivo}
insert into storage.buckets (id, name, public)
values ('uploads', 'uploads', false), ('reports', 'reports', false)
on conflict (id) do nothing;

create policy fiscal_uploads_insert on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'uploads'
    and (storage.foldername(name))[1] in (select public.minhas_organizacoes()::text)
  );

create policy fiscal_uploads_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'uploads'
    and (storage.foldername(name))[1] in (select public.minhas_organizacoes()::text)
  );

create policy fiscal_reports_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'reports'
    and (storage.foldername(name))[1] in (select public.minhas_organizacoes()::text)
  );
