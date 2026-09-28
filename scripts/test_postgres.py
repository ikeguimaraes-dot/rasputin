"""Suíte CI com PostgreSQL descartável. Exige TEST_DATABASE_URL; não lê .env."""

import os
import subprocess
import sys
from pathlib import Path

import psycopg

root = Path(__file__).resolve().parents[1]
url = os.environ.get("TEST_DATABASE_URL")
if not url:
    raise SystemExit("TEST_DATABASE_URL obrigatório; use um banco descartável vazio")
with psycopg.connect(url, autocommit=True) as conn:
    if conn.execute("select to_regclass('public.organizacoes')").fetchone()[0]:
        raise SystemExit("Banco já inicializado; recusando reutilização")
    files = [root / "supabase/tests/bootstrap.sql"]
    files += sorted((root / "supabase/migrations").glob("*.sql"))
    files += [root / "supabase/tests" / f for f in ("rls_isolation.sql", "runtime_integrity.sql")]
    for file in files:
        conn.execute(file.read_text(), prepare=False)
        print("SQL OK:", file.name, flush=True)
result = subprocess.run(
    [sys.executable, "-m", "pytest", "worker/tests", "--cov=auditoria", "--cov-report=term-missing"],
    cwd=root,
    check=False,
)
raise SystemExit(result.returncode)
