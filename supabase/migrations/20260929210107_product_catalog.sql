-- Append-only classifications; corrections create new versions, preserving evidence.
create table public.product_catalog_versions (
 id uuid primary key default gen_random_uuid(),
 organizacao_id uuid not null,
 cliente_id uuid not null,
 code text not null,
 definition jsonb not null,
 sha256 text not null,
 criado_por uuid not null,
 criado_em timestamptz not null default now(),
 foreign key(cliente_id,organizacao_id) references public.clientes(id,organizacao_id),
 unique(organizacao_id,cliente_id,code,sha256)
);
create index product_catalog_client on public.product_catalog_versions
 (organizacao_id,cliente_id,code,criado_em desc);
alter table public.product_catalog_versions enable row level security;
revoke all on public.product_catalog_versions from anon,authenticated;
grant select on public.product_catalog_versions to authenticated;
create policy product_catalog_read on public.product_catalog_versions for select to authenticated
 using(organizacao_id in (select public.minhas_organizacoes()));
create trigger product_catalog_immutable before update or delete on public.product_catalog_versions
 for each row execute function public.fiscal_immutable();
