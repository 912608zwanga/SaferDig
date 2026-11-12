from __future__ import annotations

from typing import Protocol


class RepositoryError(Exception):
    """Persistence failed (provider outage etc.). Surfaced as 503, never faked as success."""


class NotVerifiableInDb(Exception):
    pass


class Repository(Protocol):
    def create(self, user_id: str, data: dict) -> dict: ...
    def list(self, user_id: str, status: str | None, limit: int, offset: int) -> list[dict]: ...
    def get(self, user_id: str, intention_id: str) -> dict | None: ...
    def delete(self, user_id: str, intention_id: str) -> bool: ...
    def record_verification(self, user_id: str, intention_id: str, result: dict) -> dict: ...
    def history(self, user_id: str, limit: int, offset: int) -> list[dict]: ...
