-- Ausência de informação não equivale a declarar não contribuinte.
-- Perfis existentes e análises históricas permanecem inalterados.
alter table public.perfil_fiscal alter column contribuinte_ipi drop not null;
alter table public.perfil_fiscal alter column contribuinte_ipi drop default;
