.PHONY: env dev test lint db-preflight db-list db-push db-test-rls

RUN_SQL = uv run --project worker python scripts/run_sql.py

env:
	@test -f .env || (cp .env.example .env && echo ".env criado; preencha as chaves")

# Worker local, direto com uv (sem Docker), contra o Supabase na nuvem.
dev:
	cd worker && set -a && . ../.env && set +a && uv run uvicorn auditoria.main:app --reload --port 8000

test:
	cd worker && uv run pytest --cov --cov-report=term-missing

lint:
	cd worker && uv run ruff check . ../scripts

# Migrations vão para o banco apontado por DATABASE_URL no .env (nunca por link salvo),
# então é impossível atingir outro projeto por engano.
db-preflight:
	$(RUN_SQL) supabase/preflight.sql

db-list:
	@set -a && . ./.env && set +a && supabase migration list --db-url "$$DATABASE_URL"

db-push: db-preflight
	@set -a && . ./.env && set +a && supabase db push --db-url "$$DATABASE_URL"

# Só depois do db-push. Roda numa transação que termina em ROLLBACK.
db-test-rls:
	$(RUN_SQL) supabase/tests/rls_isolation.sql
