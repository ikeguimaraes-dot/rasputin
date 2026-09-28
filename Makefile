SUPABASE_PROJECT_REF ?= iqgrvptrtphvbmvrqntm

.PHONY: env dev test lint db-link db-list db-push

env:
	@test -f .env || (cp .env.example .env && echo ".env criado; preencha as chaves")

# Worker local, direto com uv (sem Docker), contra o Supabase na nuvem.
dev:
	cd worker && set -a && . ../.env && set +a && uv run uvicorn auditoria.main:app --reload --port 8000

test:
	cd worker && uv run pytest --cov --cov-report=term-missing

lint:
	cd worker && uv run ruff check .

# Migrations no projeto Supabase remoto (exige `supabase login`).
db-link:
	supabase link --project-ref $(SUPABASE_PROJECT_REF)

db-list:
	supabase migration list

db-push:
	supabase db push
