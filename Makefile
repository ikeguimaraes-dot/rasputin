.PHONY: env web-env dev web test test-integration test-db lint build db-preflight db-list db-push db-test-rls
RUN = uv run --project worker

env:
	@test -f .env || cp .env.example .env

web-env:
	$(RUN) python scripts/web_env.py

dev:
	$(RUN) python scripts/dev_worker.py

web:
	npm --prefix apps/web run dev

test:
	cd worker && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run pytest --cov --cov-report=term-missing

test-db:
	node apps/web/scripts/test-database.mjs

test-integration:
	$(RUN) python scripts/test_integration.py

lint:
	$(RUN) ruff check worker scripts
	npm --prefix apps/web run typecheck

build:
	npm --prefix apps/web run build

# Preflight só para implantação inicial em banco ainda não inicializado.
db-preflight:
	$(RUN) python scripts/run_sql.py supabase/preflight.sql

db-list:
	$(RUN) python scripts/db_cli.py list

# O histórico de migrations do Supabase garante que apenas as novas sejam aplicadas.
db-push:
	$(RUN) python scripts/db_cli.py push

db-test-rls:
	$(RUN) python scripts/run_sql.py supabase/tests/rls_isolation.sql
	$(RUN) python scripts/run_sql.py supabase/tests/runtime_integrity.sql
