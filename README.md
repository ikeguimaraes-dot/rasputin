# Auditoria Fiscal para Restaurantes (somente leitura)

Sistema web em que se sobem arquivos fiscais de clientes (XML de NF-e/NFC-e e planilhas de ERP).
Ele analisa, aponta erros com evidência e base legal e gera um relatório (PDF + XLSX).

Princípios: somente leitura sobre os dados do cliente; motor determinístico (a IA não decide se
um item está errado); regras tributárias são dados versionados, não código; toda análise grava a
versão da base usada e avalia cada item pela vigência na data de emissão da nota.

## Estado

Fase 1 (MVP), em andamento. Ordem das etapas: M0 → M1 → M2 → **M5** → M3 → M4 → M6 → M7 → M8 → M9.

- [x] M0 Fundação (esqueleto do worker, compose, CI)
- [ ] M1 Schema e RLS
- [ ] M2 Modelo canônico
- [ ] M5 Base de regras e importador do seed
- [ ] M3 Ingestão XML
- [ ] M4 Ingestão de planilha
- [ ] M6 Motor (C01–C09, R02, R04, R05 para SP)
- [ ] M7 Relatório PDF/XLSX
- [ ] M8 Frontend
- [ ] M9 Fechamento

## Pré-requisitos

Docker, [uv](https://docs.astral.sh/uv/), [Supabase CLI](https://supabase.com/docs/guides/cli),
Node 20+ e pnpm (o frontend entra na M8).

## Como rodar localmente

```bash
make env          # cria .env a partir de .env.example
make db-start     # Supabase local (Postgres, Auth, Storage)
supabase status   # copie a service_role key para SUPABASE_SERVICE_ROLE_KEY no .env
make up           # worker em http://localhost:8000/health
make test         # testes + cobertura
make lint
```

## Variáveis de ambiente

Todas documentadas em `.env.example`. Nenhuma chave no código. O worker valida as obrigatórias
na inicialização (`worker/src/auditoria/config.py`).

## Dados privados

`fixtures_privadas/` está no `.gitignore` e recebe arquivos reais de clientes (CNPJ e nomes de
terceiros). Nunca versionar. Fixtures versionadas são sintéticas.

## Estrutura

```
supabase/   migrations e config do Supabase local
worker/     Python 3.12: ingestão, base de regras, motor, relatórios
apps/web/   Next.js (M8)
docs/seed/  planilha seed da base fiscal
```
