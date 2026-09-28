"""Copie somente configurações públicas; nunca copia service_role nem DATABASE_URL."""

import os
from pathlib import Path

from run_sql import load_env_file

load_env_file(Path(".env"))
keys = (
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_API_URL",
)
values = {k: os.environ.get(k, "") for k in keys}
values["NEXT_PUBLIC_API_URL"] = values["NEXT_PUBLIC_API_URL"] or "http://localhost:8000"
path = Path("apps/web/.env.local")
path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
path.chmod(0o600)
print("Configuração pública escrita em apps/web/.env.local (sem chaves privilegiadas).")
