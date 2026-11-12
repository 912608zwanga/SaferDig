"""Sliding-window limiter, in-memory. Per-instance only: use Redis/edge limiting if you scale out."""

import time
from collections import defaultdict, deque

from fastapi import HTTPException


class RateLimiter:
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(
                429, "Too many requests. Please wait a moment and try again.", headers={"Retry-After": "30"}
            )
        q.append(now)


limiter = RateLimiter()
