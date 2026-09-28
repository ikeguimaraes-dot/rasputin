begin;
insert into auth.users(id) values('aaaaaaaa-1111-1111-1111-111111111111');
insert into organizacoes(id,nome) values('11111111-1111-1111-1111-111111111111','Teste A'),
 ('22222222-2222-2222-2222-222222222222','Teste B');
insert into membros(user_id,organizacao_id,papel) values('aaaaaaaa-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111111','admin');
insert into clientes(id,organizacao_id,cnpj,razao_social) values
 ('c1111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111111','11111111000111','A'),
 ('c2222222-2222-2222-2222-222222222222','11111111-1111-1111-1111-111111111111','22222222000122','B');
insert into uploads(id,organizacao_id,cliente_id,storage_path,nome,tipo) values
 ('f1111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111111','c1111111-1111-1111-1111-111111111111','a','a.xml','xml');
do $$ begin
 begin
 insert into documentos(organizacao_id,cliente_id,upload_id,data_emissao) values
 ('11111111-1111-1111-1111-111111111111','c2222222-2222-2222-2222-222222222222','f1111111-1111-1111-1111-111111111111',current_date);
 raise exception 'FALHA: documento aceitou upload de outro cliente';
 exception when foreign_key_violation then null; end;
end $$;
insert into perfil_fiscal(organizacao_id,cliente_id,uf,regime_federal,valid_from) values
 ('11111111-1111-1111-1111-111111111111','c1111111-1111-1111-1111-111111111111','SP','real','2026-01-01');
do $$ begin
 begin
 insert into perfil_fiscal(organizacao_id,cliente_id,uf,regime_federal,valid_from) values
 ('11111111-1111-1111-1111-111111111111','c1111111-1111-1111-1111-111111111111','SP','simples','2026-02-01');
 raise exception 'FALHA: perfil sobreposto aceito';
 exception when raise_exception then
 if sqlerrm not like '%sobrepostas%' then raise; end if;
 end;
end $$;
insert into rule_sets(id,organizacao_id,sha256,rules) values
 ('e1111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111111','hash','[]');
do $$ begin
 begin update rule_sets set sha256='mudou'; raise exception 'FALHA: snapshot alterável';
 exception when raise_exception then
 if sqlerrm <> 'Registro publicado imutável' then raise; end if; end;
end $$;
insert into fiscal_rules(organizacao_id,code,status,definition,approved_by,approved_at) values
 ('11111111-1111-1111-1111-111111111111','R05','aprovada','{}','aaaaaaaa-1111-1111-1111-111111111111',now());
do $$ begin
 begin update fiscal_rules set definition='{"changed":true}'; raise exception 'FALHA: regra publicada alterável';
 exception when raise_exception then
 if sqlerrm <> 'Regra publicada/rejeitada é imutável' then raise; end if; end;
end $$;
insert into storage.objects(bucket_id,name) values
 ('uploads','11111111-1111-1111-1111-111111111111/cliente/arquivo.xml'),
 ('uploads','22222222-2222-2222-2222-222222222222/cliente/arquivo.xml');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"aaaaaaaa-1111-1111-1111-111111111111"}',true);
do $$ begin
 if (select count(*) from storage.objects)<>1 then raise exception 'FALHA: storage não isolado'; end if;
 begin insert into jobs(organizacao_id,tipo) values('11111111-1111-1111-1111-111111111111','ingest_upload');
 raise exception 'FALHA: usuário forjou job'; exception when insufficient_privilege then null; end;
 begin update fiscal_rules set definition='{}'; raise exception 'FALHA: usuário alterou regra';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
rollback;
