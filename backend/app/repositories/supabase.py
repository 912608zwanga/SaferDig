"""PostgREST repository. The user's own JWT is forwarded, so Postgres RLS is the final
authority; user_id filters below are defence in depth. No service-role key is used."""

import httpx

from .base import NotVerifiableInDb, RepositoryError

COLS = "id,recipient_name,amount,currency,purpose,reference,status,expires_at,created_at"


class SupabaseRepository:
    def __init__(self, base_url: str, anon_key: str, token: str, client: httpx.Client | None = None):
        self.c = client or httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0))
        self.base = base_url.rstrip("/") + "/rest/v1"
        self.h = {"apikey": anon_key, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _req(self, method, path, **kw):
        try:
            r = self.c.request(method, self.base + path, headers={**self.h, **kw.pop("headers", {})}, **kw)
        except httpx.HTTPError as e:
            raise RepositoryError("database unreachable") from e
        if r.status_code == 400 and "intention_not_verifiable" in r.text:
            raise NotVerifiableInDb()
        if r.status_code >= 400:
            raise RepositoryError(f"database error {r.status_code}")
        return r.json() if r.content else None

    def create(self, user_id, data):
        from datetime import datetime, timedelta, timezone

        body = {k: (str(v) if k == "amount" else v) for k, v in data.items() if k != "expires_in_minutes"}
        body["expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=data["expires_in_minutes"])).isoformat()
        return self._req("POST", f"/intentions?select={COLS}", json=body, headers={"Prefer": "return=representation"})[
            0
        ]

    def list(self, user_id, status, limit, offset):
        q = f"/intentions?select={COLS}&user_id=eq.{user_id}&order=created_at.desc&limit={limit}&offset={offset}"
        if status:
            q += f"&status=eq.{status}"
        return self._req("GET", q)

    def get(self, user_id, intention_id):
        rows = self._req("GET", f"/intentions?select={COLS}&id=eq.{intention_id}&user_id=eq.{user_id}")
        return rows[0] if rows else None

    def delete(self, user_id, intention_id):
        rows = self._req(
            "DELETE",
            f"/intentions?id=eq.{intention_id}&user_id=eq.{user_id}&select=id",
            headers={"Prefer": "return=representation"},
        )
        return bool(rows)

    def record_verification(self, user_id, intention_id, result):
        return self._req(
            "POST",
            "/rpc/record_verification",
            json={
                "p_intention_id": intention_id,
                "p_recipient_match": result["recipient_match"],
                "p_amount_match": result["amount_match"],
                "p_purpose_match": result["purpose_match"],
                "p_recipient_review": result["recipient_review"],
                "p_overall": result["overall_result"],
            },
        )

    def history(self, user_id, limit, offset):
        return self._req(
            "GET",
            "/verification_results?select=id,intention_id,overall_result,recipient_match,"
            f"amount_match,purpose_match,created_at&user_id=eq.{user_id}"
            f"&order=created_at.desc&limit={limit}&offset={offset}",
        )
