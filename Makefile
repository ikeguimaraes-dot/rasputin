.PHONY: env db-start db-stop db-reset up down test lint

env:
	@test -f .env || (cp .env.example .env && echo ".env criado; preencha as chaves")

db-start:
	supabase start

db-stop:
	supabase stop

db-reset:
	supabase db reset

up: env
	docker compose up --build -d

down:
	docker compose down

test:
	cd worker && uv run pytest --cov --cov-report=term-missing

lint:
	cd worker && uv run ruff check .
