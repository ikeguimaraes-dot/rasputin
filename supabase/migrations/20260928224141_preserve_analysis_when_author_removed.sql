-- A FK criado_por usa ON DELETE SET NULL. A remoção da conta não modifica
-- entradas, regras ou resultados publicados; apenas elimina o vínculo com Auth.
create or replace function public.fiscal_analysis_guard()
returns trigger language plpgsql set search_path='' as $$
begin
  if pg_trigger_depth() > 1
     and old.criado_por is not null and new.criado_por is null
     and (to_jsonb(new) - 'criado_por') = (to_jsonb(old) - 'criado_por')
     and not exists (select 1 from auth.users where id=old.criado_por) then
    return new;
  end if;
  if old.status='concluida' then raise exception 'Análise concluída imutável'; end if;
  if new.input_snapshot is distinct from old.input_snapshot or
     new.rule_set_id is distinct from old.rule_set_id then
    raise exception 'Entradas e regras da análise são imutáveis';
  end if;
  return new;
end $$;
