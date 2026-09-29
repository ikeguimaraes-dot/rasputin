-- Teste de isolamento entre organizações. Rodar com psql como dono do banco:
--   make db-test-rls   (usa scripts/run_sql.py; não precisa de psql)
-- Tudo acontece numa transação que termina em ROLLBACK: não deixa nada no banco.
begin;

-- Fixtures (como dono, ignorando RLS)
insert into auth.users (id, aud, role, email)
values ('aaaaaaaa-0000-0000-0000-00000000000a', 'authenticated', 'authenticated', 'rls-a@test.local'),
       ('bbbbbbbb-0000-0000-0000-00000000000b', 'authenticated', 'authenticated', 'rls-b@test.local');
insert into public.organizacoes (id, nome)
values ('a0000000-0000-0000-0000-000000000001', 'Org A'),
       ('b0000000-0000-0000-0000-000000000002', 'Org B');
insert into public.membros (user_id, organizacao_id, papel)
values ('aaaaaaaa-0000-0000-0000-00000000000a', 'a0000000-0000-0000-0000-000000000001', 'membro'),
       ('bbbbbbbb-0000-0000-0000-00000000000b', 'b0000000-0000-0000-0000-000000000002', 'admin');
insert into public.clientes (id, organizacao_id, cnpj, razao_social)
values ('c0000000-0000-0000-0000-00000000000a', 'a0000000-0000-0000-0000-000000000001', '11111111000111', 'Cliente A'),
       ('c0000000-0000-0000-0000-00000000000b', 'b0000000-0000-0000-0000-000000000002', '22222222000122', 'Cliente B');

insert into public.product_catalog_versions(organizacao_id,cliente_id,code,definition,sha256,criado_por)
values ('a0000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-00000000000a',
 'P1','{}','a','aaaaaaaa-0000-0000-0000-00000000000a'),
 ('b0000000-0000-0000-0000-000000000002','c0000000-0000-0000-0000-00000000000b',
 'P2','{}','b','bbbbbbbb-0000-0000-0000-00000000000b');

-- A partir daqui, o usuário da Org A
set local role authenticated;
select set_config('request.jwt.claims',
  '{"sub":"aaaaaaaa-0000-0000-0000-00000000000a","role":"authenticated"}', true);

do $$
begin
  if (select count(*) from public.product_catalog_versions) <> 1
     or (select code from public.product_catalog_versions) <> 'P1' then
    raise exception 'FALHA: catálogo de produto vazou entre organizações';
  end if;
  if has_table_privilege('authenticated','public.product_catalog_versions','INSERT')
     or has_table_privilege('authenticated','public.product_catalog_versions','UPDATE')
     or has_table_privilege('authenticated','public.product_catalog_versions','DELETE')
     or has_table_privilege('anon','public.product_catalog_versions','SELECT') then
    raise exception 'FALHA: privilégios indevidos no catálogo';
  end if;
  if (select count(*) from public.clientes) <> 1
     or (select razao_social from public.clientes) <> 'Cliente A' then
    raise exception 'FALHA: usuário da Org A enxerga clientes de outra organização';
  end if;
  if (select count(*) from public.organizacoes) <> 1 then
    raise exception 'FALHA: usuário da Org A enxerga outras organizações';
  end if;
end $$;

do $$
begin
  begin
    insert into public.clientes (organizacao_id, cnpj, razao_social)
    values ('b0000000-0000-0000-0000-000000000002', '33333333000133', 'Invasor');
    raise exception 'FALHA: inseriu cliente na Org B';
  exception when insufficient_privilege then null;
  end;
end $$;

do $$
begin
  begin
    insert into public.documentos (organizacao_id, cliente_id, upload_id, data_emissao)
    values ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-00000000000a',
            gen_random_uuid(), current_date);
    raise exception 'FALHA: usuário escreveu em documentos (deveria ser só o worker)';
  exception when insufficient_privilege then null;
  end;
end $$;

do $$
begin
  begin
    update public.audit_log set acao = 'x';
    raise exception 'FALHA: audit_log aceitou UPDATE';
  exception when insufficient_privilege then null;
  end;
end $$;

do $$
begin
  if public.eh_admin_da_organizacao('a0000000-0000-0000-0000-000000000001') then
    raise exception 'FALHA: membro simples foi tratado como admin';
  end if;
end $$;

-- anon não lê nada
reset role;
set local role anon;
do $$
begin
  begin
    perform 1 from public.clientes;
    raise exception 'FALHA: anon conseguiu ler clientes';
  exception when insufficient_privilege then null;
  end;
end $$;

reset role;
rollback;
select 'RLS OK: isolamento entre organizações verificado (transação revertida).' as resultado;
