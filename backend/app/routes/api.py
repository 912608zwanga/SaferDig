import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..auth import CurrentUser, get_current_user
from ..config import Settings, get_settings
from ..domain.comparison import Intention, NotVerifiable, Proposed, check_verifiable, compare
from ..ratelimit import limiter
from ..repositories.base import NotVerifiableInDb, Repository, RepositoryError
from ..repositories.supabase import SupabaseRepository
from ..schemas import HistoryItem, IntentionCreate, IntentionOut, IntentionPage, VerifyRequest, VerifyResponse

log = logging.getLogger("intentguard")
router = APIRouter(prefix="/api/v1")
OPEN = ("pending", "mismatch", "needs_review")


def get_repo(user: CurrentUser = Depends(get_current_user), s: Settings = Depends(get_settings)) -> Repository:
    return SupabaseRepository(s.supabase_url, s.supabase_anon_key, user.token)


def _limited(user: CurrentUser = Depends(get_current_user), s: Settings = Depends(get_settings)) -> CurrentUser:
    limiter.check(f"api:{user.id}", s.rate_limit_per_minute)
    return user


def _present(row: dict) -> dict:
    """Lazily mark time-expired open intentions as 'expired' so users never see stale 'pending'."""
    exp = row["expires_at"]
    exp = datetime.fromisoformat(exp.replace("Z", "+00:00")) if isinstance(exp, str) else exp
    if row["status"] in OPEN and exp <= datetime.now(timezone.utc):
        row = {**row, "status": "expired"}
    return row


def _db(fn, *a):
    try:
        return fn(*a)
    except RepositoryError:
        log.error("repository failure")
        raise HTTPException(503, "We couldn't reach the data service. Nothing was saved. Please try again.") from None


@router.post("/intentions", response_model=IntentionOut, status_code=201)
def create_intention(
    body: IntentionCreate,
    user: CurrentUser = Depends(_limited),
    repo: Repository = Depends(get_repo),
):
    data = body.model_dump()
    return _present(_db(repo.create, user.id, data))


@router.get("/intentions", response_model=IntentionPage)
def list_intentions(
    status: Literal["pending", "verified_match", "mismatch", "needs_review", "expired"] | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
    user: CurrentUser = Depends(_limited),
    repo: Repository = Depends(get_repo),
):
    db_status = status if status in ("verified_match", "mismatch", "needs_review") else None
    rows = [_present(r) for r in _db(repo.list, user.id, db_status, limit, offset)]
    if status in ("pending", "expired"):
        rows = [r for r in rows if r["status"] == status]
    return {"items": rows, "limit": limit, "offset": offset}


@router.get("/intentions/{intention_id}", response_model=IntentionOut)
def get_intention(intention_id: UUID, user: CurrentUser = Depends(_limited), repo: Repository = Depends(get_repo)):
    row = _db(repo.get, user.id, str(intention_id))
    if not row:
        raise HTTPException(404, "Intention not found.")
    return _present(row)


@router.delete("/intentions/{intention_id}", status_code=204)
def delete_intention(intention_id: UUID, user: CurrentUser = Depends(_limited), repo: Repository = Depends(get_repo)):
    if not _db(repo.delete, user.id, str(intention_id)):
        raise HTTPException(404, "Intention not found.")
    return Response(status_code=204)


@router.post("/verify", response_model=VerifyResponse)
def verify(
    body: VerifyRequest,
    user: CurrentUser = Depends(get_current_user),
    repo: Repository = Depends(get_repo),
    s: Settings = Depends(get_settings),
):
    limiter.check(f"verify:{user.id}", s.verify_rate_limit_per_minute)
    row = _db(repo.get, user.id, str(body.intention_id))
    if not row:
        raise HTTPException(404, "Intention not found.")
    row = _present(row)
    exp = row["expires_at"]
    exp = datetime.fromisoformat(exp.replace("Z", "+00:00")) if isinstance(exp, str) else exp
    intention = Intention(
        id=str(row["id"]),
        user_id=user.id,
        recipient_name=row["recipient_name"],
        amount=Decimal(str(row["amount"])),
        purpose=row["purpose"],
        reference=row.get("reference"),
        status=row["status"],
        expires_at=exp,
    )
    try:
        check_verifiable(intention, user.id, datetime.now(timezone.utc))
    except NotVerifiable as e:
        raise HTTPException({"expired": 410, "already_checked": 409}.get(e.code, 404), e.message) from None
    result = compare(intention, Proposed(body.recipient_name, body.amount, body.purpose, body.reference))
    try:
        _db(
            repo.record_verification,
            user.id,
            str(body.intention_id),
            {
                "recipient_match": result.recipient_match,
                "amount_match": result.amount_match,
                "purpose_match": result.purpose_match,
                "recipient_review": result.recipient_needs_review,
                "overall_result": result.overall,
            },
        )
    except HTTPException:
        raise
    except NotVerifiableInDb:
        raise HTTPException(409, "This intention can no longer be checked. Please refresh.") from None
    return VerifyResponse(
        intention_id=body.intention_id,
        overall_result=result.overall,
        recipient_match=result.recipient_match,
        recipient_needs_review=result.recipient_needs_review,
        amount_match=result.amount_match,
        purpose_match=result.purpose_match,
        explanation=result.explanation,
    )


@router.get("/verification-history", response_model=list[HistoryItem])
def verification_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
    user: CurrentUser = Depends(_limited),
    repo: Repository = Depends(get_repo),
):
    return _db(repo.history, user.id, limit, offset)
