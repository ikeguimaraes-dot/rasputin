"""Sobe Postgres WASM descartável e roda a suíte inteira, sem .env nem serviços remotos."""

import os
import select
import socket
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
env = {**os.environ, "TEST_DB_PORT": str(port)}
server = subprocess.Popen(
    ["node", "apps/web/scripts/test-database.mjs", "--serve"],
    cwd=root,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
try:
    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline and server.poll() is None:
        readable, _, _ = select.select([server.stdout], [], [], 1)
        if readable:
            line = server.stdout.readline()
            print(line, end="")
            if line.startswith("TEST_DATABASE_URL="):
                env["TEST_DATABASE_URL"] = line.strip().split("=", 1)[1]
                ready = True
                break
    if not ready:
        raise SystemExit(
            "Banco temporário não inicializou; confira npm ci em apps/web."
        )
    if Path("/opt/homebrew/lib").exists():
        env.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "worker/tests",
            "--cov=auditoria",
            "--cov-report=term-missing",
        ],
        cwd=root,
        env=env,
        check=False,
    )
    raise SystemExit(tests.returncode)
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
