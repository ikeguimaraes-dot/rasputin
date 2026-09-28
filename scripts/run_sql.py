"""Executa um arquivo .sql contra o banco apontado por DATABASE_URL (do .env ou do ambiente).

Uso: uv run --project worker python scripts/run_sql.py supabase/preflight.sql
Não depende do psql. Nunca imprime a connection string.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ENV_FILE = Path(".env")


def load_env_file(path: Path) -> None:
    """Carrega KEY=VALUE sem sobrescrever variáveis já definidas no ambiente."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def print_results(cursor: psycopg.Cursor) -> None:
    while True:
        if cursor.description:
            for row in cursor.fetchall():
                print(*row)
        if not cursor.nextset():
            break


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: run_sql.py <arquivo.sql>", file=sys.stderr)
        return 2
    sql_file = Path(argv[1])
    if not sql_file.is_file():
        print(f"Arquivo não encontrado: {sql_file}", file=sys.stderr)
        return 2

    load_env_file(ENV_FILE)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL ausente: preencha o .env (veja .env.example).", file=sys.stderr)
        return 1

    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.add_notice_handler(lambda d: print(f"{d.severity}: {d.message_primary}"))
            print_results(conn.execute(sql_file.read_text()))
    except psycopg.Error as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
