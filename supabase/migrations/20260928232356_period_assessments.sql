alter table public.perfil_fiscal add column regime_pis_cofins text
 check(regime_pis_cofins in ('cumulativo','nao_cumulativo','misto'));

create table public.fiscal_assessments (
 id uuid primary key default gen_random_uuid(),
 organizacao_id uuid not null,
 cliente_id uuid not null,
 module text not null,
 period date not null,
 input_snapshot jsonb not null,
 catalog_snapshot jsonb not null,
 result_payload jsonb not null,
 sha256 text not null,
 criado_por uuid not null,
 criado_em timestamptz not null default now(),
 foreign key(cliente_id,organizacao_id) references public.clientes(id,organizacao_id),
 unique(organizacao_id,sha256)
);
comment on column public.fiscal_assessments.criado_por is
 'Identificador histórico do autor; não usa FK para preservar apuração após exclusão em Auth.';
alter table public.fiscal_assessments enable row level security;
revoke all on public.fiscal_assessments from anon,authenticated;
grant select on public.fiscal_assessments to authenticated;
create policy fiscal_assessments_read on public.fiscal_assessments for select to authenticated
 using(organizacao_id in (select public.minhas_organizacoes()));
create index fiscal_assessments_client on public.fiscal_assessments(organizacao_id,cliente_id,period);
create trigger fiscal_assessments_immutable before update or delete on public.fiscal_assessments
 for each row execute function public.fiscal_immutable();
