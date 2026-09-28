"""Inicializa o ambiente sem executar o conteúdo do .env como shell."""

import os
from pathlib import Path

from run_sql import load_env_file

load_env_file(Path(".env"))
# Bibliotecas nativas de PDF instaladas por Homebrew no macOS.
if Path("/opt/homebrew/lib/libgobject-2.0.dylib").exists():
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
import uvicorn

uvicorn.run(
    "auditoria.main:app",
    host="127.0.0.1",
    port=8000,
    reload=True,
    reload_dirs=["worker/src"],
)
