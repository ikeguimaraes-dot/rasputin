-- Roda ANTES de aplicar as migrations. Aborta se algum objeto que vamos criar já existir,
-- para nunca alterar nem sobrescrever nada do banco. Em caso de conflito: renomear com o
-- prefixo fiscal_ nas migrations e neste arquivo.
do $$
declare
  tabelas constant text[] := array[
    'organizacoes', 'membros', 'clientes', 'perfil_fiscal', 'audit_log', 'uploads',
    'layout_templates', 'jobs', 'documentos', 'itens', 'itens_tributos', 'origem_linha',
    'knowledge_versions', 'analises', 'analise_uploads', 'findings', 'relatorios',
    'ia_chamadas', 'ncm_oficial', 'cest', 'cfop', 'cst_icms', 'csosn', 'cst_pis_cofins',
    'cst_ipi', 'uf_aliquota_modal', 'icms_regra_produto', 'st_vigente', 'pis_cofins_regra',
    'regime_especial_restaurante'
  ];
  funcoes constant text[] := array['minhas_organizacoes', 'eh_admin_da_organizacao'];
  conflitos text;
begin
  select string_agg('tabela public.' || t, ', ') into conflitos
    from unnest(tabelas) as t
   where to_regclass('public.' || t) is not null;

  select concat_ws(', ', conflitos,
                   (select string_agg('função public.' || f, ', ')
                      from unnest(funcoes) as f
                     where exists (select 1 from pg_proc p
                                     join pg_namespace n on n.oid = p.pronamespace
                                    where n.nspname = 'public' and p.proname = f)))
    into conflitos;

  if conflitos is not null and conflitos <> '' then
    raise exception 'PREFLIGHT: nomes já existentes no banco: %. Use o prefixo fiscal_.', conflitos;
  end if;

  raise notice 'PREFLIGHT ok: nenhum conflito de nome.';
end
$$;
