"""Migrations via CLI com argv, sem shell e sem imprimir DATABASE_URL."""

import os
import subprocess
import sys
from pathlib import Path

from run_sql import load_env_file

load_env_file(Path(".env"))
commands = {"push": ["db", "push"], "list": ["migration", "list"]}
if len(sys.argv) != 2 or sys.argv[1] not in commands:
    raise SystemExit("Uso: db_cli.py push|list")
url = os.environ.get("DATABASE_URL", "")
if not url or any(marker in url for marker in ("SENHA", "SEU-", "<", ">", "[YOUR")):
    raise SystemExit(
        "Preencha DATABASE_URL no .env com a conexão real do pooler Session."
    )
result = subprocess.run(
    ["supabase", *commands[sys.argv[1]], "--db-url", url],
    capture_output=True,
    text=True,
    check=False,
)
# Mensagens do CLI podem conter DSN em erros: redigir antes de exibir.
for output in (result.stdout, result.stderr):
    print(output.replace(url, "[DATABASE_URL]"), end="")
raise SystemExit(result.returncode)
