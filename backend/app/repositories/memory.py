"""In-memory repository used by tests. Mirrors the ownership rules RLS enforces in Postgres."""

import uuid
from datetime import datetime, timedelta, timezone

from .base import NotVerifiableInDb


class MemoryRepository:
    def __init__(self):
        self.intentions: dict[str, dict] = {}
        self.results: list[dict] = []

    def create(self, user_id, data):
        now = datetime.now(timezone.utc)
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "currency": "ZAR",
            "status": "pending",
            "created_at": now,
            "expires_at": now + timedelta(minutes=data.pop("expires_in_minutes")),
            **data,
        }
        self.intentions[row["id"]] = row
        return dict(row)

    def list(self, user_id, status, limit, offset):
        rows = [r for r in self.intentions.values() if r["user_id"] == user_id]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return [dict(r) for r in rows if status in (None, r["status"])][offset : offset + limit]

    def get(self, user_id, intention_id):
        r = self.intentions.get(intention_id)
        return dict(r) if r and r["user_id"] == user_id else None

    def delete(self, user_id, intention_id):
        if not self.get(user_id, intention_id):
            return False
        del self.intentions[intention_id]
        self.results = [x for x in self.results if x["intention_id"] != intention_id]
        return True

    def record_verification(self, user_id, intention_id, result):
        row = self.intentions.get(intention_id)
        if not row or row["user_id"] != user_id or row["status"] not in ("pending", "mismatch", "needs_review"):
            raise NotVerifiableInDb()
        row["status"] = "verified_match" if result["overall_result"] == "match" else result["overall_result"]
        out = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "intention_id": intention_id,
            "created_at": datetime.now(timezone.utc),
            **result,
        }
        self.results.append(out)
        return out

    def history(self, user_id, limit, offset):
        rows = sorted((r for r in self.results if r["user_id"] == user_id), key=lambda r: r["created_at"], reverse=True)
        return rows[offset : offset + limit]
