import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.ratelimit import limiter
from app.repositories.memory import MemoryRepository
from app.routes.api import get_repo

REPO = MemoryRepository()
CURRENT = {"id": "user-a"}


@pytest.fixture(autouse=True)
def setup():
    REPO.intentions.clear()
    REPO.results.clear()
    limiter.hits.clear()
    CURRENT["id"] = "user-a"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(CURRENT["id"], "t")
    app.dependency_overrides[get_repo] = lambda: REPO
    yield
    app.dependency_overrides.clear()


client = TestClient(app, raise_server_exceptions=False)
GOOD = {"recipient_name": "Thandi Mokoena", "amount": "250.00", "purpose": "Groceries"}


def make(**kw):
    r = client.post("/api/v1/intentions", json={**GOOD, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def verify(i, **kw):
    return client.post(
        "/api/v1/verify", json={"intention_id": i["id"], "recipient_name": "Thandi Mokoena", "amount": "250.00", **kw}
    )


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_requires_auth():
    app.dependency_overrides.pop(get_current_user)
    for method, path in [
        ("get", "/api/v1/intentions"),
        ("post", "/api/v1/verify"),
        ("get", "/api/v1/verification-history"),
    ]:
        assert getattr(client, method)(path).status_code == 401
    assert client.get("/api/v1/intentions", headers={"Authorization": "Bearer junk"}).status_code == 401


@pytest.mark.parametrize(
    "patch",
    [
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "1.234"},
        {"amount": 12.5},
        {"recipient_name": "  "},
        {"purpose": ""},
        {"currency": "USD"},
        {"user_id": "someone-else"},
    ],
)
def test_create_validation(patch):
    assert client.post("/api/v1/intentions", json={**GOOD, **patch}).status_code == 422


def test_match_flow_and_single_use():
    i = make()
    r = verify(i)
    assert r.status_code == 200 and r.json()["overall_result"] == "match" and r.json()["simulated"] is True
    assert client.get(f"/api/v1/intentions/{i['id']}").json()["status"] == "verified_match"
    assert verify(i).status_code == 409


def test_mismatch_then_retry_allowed():
    i = make()
    r = verify(i, recipient_name="Sipho Dlamini", amount="900.00").json()
    assert r["overall_result"] == "mismatch" and not r["recipient_match"] and not r["amount_match"]
    assert verify(i).json()["overall_result"] == "match"
    h = client.get("/api/v1/verification-history").json()
    assert [x["overall_result"] for x in h] == ["match", "mismatch"]


def test_ambiguous_recipient_needs_review():
    assert verify(make(), recipient_name="Thandi Mokoenaa").json()["overall_result"] == "needs_review"


def test_expired_intention():
    i = make()
    REPO.intentions[i["id"]]["expires_at"] = REPO.intentions[i["id"]]["created_at"]
    assert verify(i).status_code == 410
    assert client.get(f"/api/v1/intentions/{i['id']}").json()["status"] == "expired"
    assert len(client.get("/api/v1/intentions?status=expired").json()["items"]) == 1


def test_ownership_boundaries():
    i = make()
    CURRENT["id"] = "user-b"
    assert client.get(f"/api/v1/intentions/{i['id']}").status_code == 404
    assert client.delete(f"/api/v1/intentions/{i['id']}").status_code == 404
    assert verify(i).status_code == 404
    assert client.get("/api/v1/intentions").json()["items"] == []
    CURRENT["id"] = "user-a"
    assert client.get(f"/api/v1/intentions/{i['id']}").status_code == 200


def test_delete_and_pagination():
    ids = [make()["id"] for _ in range(3)]
    assert client.delete(f"/api/v1/intentions/{ids[0]}").status_code == 204
    assert client.delete(f"/api/v1/intentions/{ids[0]}").status_code == 404
    page = client.get("/api/v1/intentions?limit=1&offset=1").json()
    assert len(page["items"]) == 1 and page["limit"] == 1
    assert client.get("/api/v1/intentions?limit=1000").status_code == 422


def test_errors_do_not_leak_and_cors_headers():
    r = client.get("/api/v1/intentions/not-a-uuid")
    assert r.status_code == 422 and "Traceback" not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"
    assert (
        client.post("/api/v1/intentions", content="x" * 20000, headers={"content-type": "application/json"}).status_code
        == 413
    )


def test_verify_rate_limit():
    i = make()
    codes = [verify(i, recipient_name="X").status_code for _ in range(25)]
    assert 429 in codes
