"""Pipeline real em Postgres isolado; somente Supabase Auth/Storage são simulados."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auditoria.auth import Actor, identity
from auditoria.config import Settings
from auditoria.db import connect
from auditoria.main import create_app
from auditoria.queue import tick
from auditoria.storage import Storage

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="Postgres de teste não iniciado"
)


@pytest.fixture
def runtime(monkeypatch):
    settings = Settings(
        database_url=os.environ["TEST_DATABASE_URL"],
        supabase_url="https://test.invalid",
        supabase_service_role_key="test",
    )
    objects = {}
    monkeypatch.setattr(
        Storage,
        "put",
        lambda self, bucket, path, content, mime: objects.__setitem__((bucket, path), content),
    )
    monkeypatch.setattr(Storage, "get", lambda self, bucket, path: objects[bucket, path])
    monkeypatch.setattr(
        Storage,
        "sign",
        lambda self, bucket, path: f"https://test.invalid/{bucket}/{path}?expires=120",
    )
    actor = Actor(str(uuid4()), "", "sem_organizacao")
    with connect(settings) as conn:
        conn.execute("insert into auth.users(id) values(%s)", (actor.user,))
    app = create_app(settings, run_queue=False)
    app.dependency_overrides[identity] = lambda: actor
    with TestClient(app) as client:
        yield settings, client, actor, objects


def setup_client(http, actor, regime="real"):
    r = http.post("/api/organizations", json={"nome": "Escritório sintético"})
    assert r.status_code == 200, r.text
    actor.org = r.json()["id"]
    actor.role = "admin"
    r = http.post(
        "/api/clients",
        json={
            "razao_social": "Restaurante de teste",
            "cnpj": "11111111000111",
            "profile": {"regime_federal": regime, "valid_from": "2026-01-01"},
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_upload_to_reports_and_reissue_immutable(runtime):
    settings, http, actor, objects = runtime
    ident = setup_client(http, actor)
    data = (
        Path(__file__)
        .parents[3]
        .joinpath("fixtures", "sinteticas", "nota.xml")
        .resolve()
        .read_bytes()
    )
    r = http.post(
        "/api/uploads",
        data={"client_id": ident},
        files={"file": ("nota.xml", data, "application/xml")},
    )
    assert r.status_code == 200, r.text
    upload = r.json()["id"]
    assert tick(settings)
    rows = http.get("/api/uploads", params={"client_id": ident}).json()
    assert rows[0]["status"] == "processado", rows
    r = http.post(
        "/api/analyses",
        json={
            "client_id": ident,
            "upload_ids": [upload],
            "start": "2026-08-01",
            "end": "2026-08-31",
        },
    )
    assert r.status_code == 200, r.text
    analysis = r.json()["id"]
    assert tick(settings)
    result = http.get("/api/analyses/" + analysis).json()
    assert result["status"] == "concluida", result
    assert result["parcial"]  # nenhuma base fiscal validada ainda
    assert any(v.startswith(b"%PDF") for v in objects.values())
    assert any(
        v.startswith(b"PK") for (bucket, path), v in objects.items() if path.endswith(".xlsx")
    )
    old_result = result["result_payload"]
    assert (
        http.post(
            f"/api/clients/{ident}/profiles",
            json={"regime_federal": "simples", "valid_from": "2026-09-01"},
        ).status_code
        == 200
    )
    assert (
        http.put("/api/branding", json={"nome": "Novo nome", "rodape": "Nova marca"}).status_code
        == 200
    )
    assert http.post(f"/api/analyses/{analysis}/reissue").status_code == 200
    assert http.get("/api/analyses/" + analysis).json()["result_payload"] == old_result
    download = http.get(f"/api/analyses/{analysis}/download/pdf")
    assert download.status_code == 200 and download.json()["expires_in"] == 120
    # Segunda organização não pode ler/baixar o resultado nem enfileirar o upload alheio.
    actor.org = str(uuid4())
    assert http.get("/api/analyses/" + analysis).status_code == 404
    assert http.get(f"/api/analyses/{analysis}/download/pdf").status_code == 404


def test_duplicate_upload_is_idempotent(runtime):
    settings, http, actor, _ = runtime
    ident = setup_client(http, actor)
    data = b"data;descricao;valor\n01/08/2026;Produto;100"
    kwargs = {
        "data": {"client_id": ident, "mapping": '{"issued":0,"description":1,"value":2}'},
        "files": {"file": ("x.csv", data, "text/csv")},
    }
    a = http.post("/api/uploads", **kwargs)
    b = http.post("/api/uploads", **kwargs)
    assert a.status_code == b.status_code == 200, (a.text, b.text)
    assert a.json()["id"] == b.json()["id"]
    tick(settings)
    assert len(http.get("/api/uploads", params={"client_id": ident}).json()) == 1


def test_rule_approval_and_member_cannot_approve(runtime):
    _, http, actor, _ = runtime
    setup_client(http, actor)
    rule = {
        "code": "R05",
        "title": "Fixture de aprovação",
        "valid_from": "2026-01-01",
        "regimes": ["real"],
        "expected": {"pis_cst": ["04"]},
        "source_url": "https://example.invalid/fiscal",
        "legal_basis": "Somente teste sintético",
    }
    r = http.post("/api/rules", json=rule)
    assert r.status_code == 200, r.text
    ident = r.json()["id"]
    actor.role = "membro"
    assert http.post(f"/api/rules/{ident}/approve").status_code == 403
    actor.role = "admin"
    assert http.post(f"/api/rules/{ident}/approve").status_code == 200
    assert http.post(f"/api/rules/{ident}/approve").status_code == 409


def test_auth_verifies_user_and_membership(runtime, monkeypatch):
    import httpx

    settings, http, actor, _ = runtime
    setup_client(http, actor)
    http.app.dependency_overrides.clear()
    assert http.get("/api/clients").status_code == 401
    monkeypatch.setattr(
        "auditoria.auth.httpx.get",
        lambda *a, **k: httpx.Response(
            200,
            json={"id": actor.user},
            request=httpx.Request("GET", "https://test.invalid/auth/v1/user"),
        ),
    )
    headers = {"Authorization": "Bearer synthetic-user-token"}
    assert http.get("/api/clients", headers=headers).status_code == 200
    assert (
        http.get("/api/clients", headers={**headers, "X-Organization-Id": str(uuid4())}).status_code
        == 403
    )
    monkeypatch.setattr(
        "auditoria.auth.httpx.get",
        lambda *a, **k: httpx.Response(
            401, json={}, request=httpx.Request("GET", "https://test.invalid/auth/v1/user")
        ),
    )
    assert http.get("/api/clients", headers=headers).status_code == 401


def test_bad_input_fails_job_without_poisoning_next_job(runtime):
    settings, http, actor, _ = runtime
    ident = setup_client(http, actor)
    bad = http.post(
        "/api/uploads",
        data={"client_id": ident},
        files={"file": ("bad.xml", b"<broken>", "application/xml")},
    )
    assert bad.status_code == 200, bad.text
    assert tick(settings)
    rows = http.get("/api/uploads", params={"client_id": ident}).json()
    assert rows[0]["status"] == "erro"
    good = http.post(
        "/api/uploads",
        data={"client_id": ident, "mapping": '{"issued":0,"description":1,"value":2}'},
        files={"file": ("good.csv", b"Data;Descricao;Valor\n01/08/2026;Teste;100", "text/csv")},
    )
    assert good.status_code == 200, good.text
    assert tick(settings)
    rows = http.get("/api/uploads", params={"client_id": ident}).json()
    assert rows[0]["status"] == "processado"


def test_storage_transient_error_retries_without_duplicate_documents(runtime, monkeypatch):
    settings, http, actor, objects = runtime
    ident = setup_client(http, actor)
    data = Path(__file__).parents[3].joinpath("fixtures", "sinteticas", "nota.xml").read_bytes()
    r = http.post(
        "/api/uploads",
        data={"client_id": ident},
        files={"file": ("n.xml", data, "application/xml")},
    )
    assert r.status_code == 200, r.text
    upload = r.json()["id"]

    def fail(*args):
        raise RuntimeError("Temporary storage failure")

    monkeypatch.setattr(Storage, "get", fail)
    assert tick(settings)
    with connect(settings) as conn:
        job = conn.execute("select * from jobs where organizacao_id=%s", (actor.org,)).fetchone()
        assert job["status"] == "pendente" and job["tentativas"] == 1
        conn.execute("update jobs set run_after=now() where id=%s", (job["id"],))
    monkeypatch.setattr(Storage, "get", lambda self, bucket, path: objects[bucket, path])
    assert tick(settings)
    with connect(settings) as conn:
        assert (
            conn.execute(
                "select count(*) as n from documentos where upload_id=%s", (upload,)
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute("select status from jobs where id=%s", (job["id"],)).fetchone()["status"]
            == "concluido"
        )
