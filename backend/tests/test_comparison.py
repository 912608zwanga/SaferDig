from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.comparison import (
    Intention,
    InvalidAmount,
    NotVerifiable,
    Proposed,
    check_verifiable,
    compare,
    parse_amount,
)

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)


def make(**kw):
    base = dict(
        id="i1",
        user_id="u1",
        recipient_name="Thandi Mokoena",
        amount=Decimal("250.00"),
        purpose="Groceries",
        reference="INV-1",
        status="pending",
        expires_at=NOW + timedelta(hours=2),
    )
    base.update(kw)
    return Intention(**base)


def test_exact_match():
    r = compare(make(), Proposed("Thandi Mokoena", Decimal("250.00")))
    assert r.overall == "match" and r.recipient_match and r.amount_match


def test_case_and_whitespace_normalised():
    assert compare(make(), Proposed("  thandi   MOKOENA ", Decimal("250.00"))).overall == "match"


def test_recipient_mismatch():
    r = compare(make(), Proposed("Sipho Dlamini", Decimal("250.00")))
    assert r.overall == "mismatch" and not r.recipient_match and r.amount_match
    assert not r.recipient_needs_review


def test_amount_mismatch():
    r = compare(make(), Proposed("Thandi Mokoena", Decimal("2500.00")))
    assert r.overall == "mismatch" and r.recipient_match and not r.amount_match


def test_multiple_mismatches():
    r = compare(make(), Proposed("Sipho Dlamini", Decimal("999.99")))
    assert r.overall == "mismatch" and not r.recipient_match and not r.amount_match


def test_similar_recipient_is_never_a_match():
    r = compare(make(), Proposed("Thandi Mokoenaa", Decimal("250.00")))
    assert r.overall == "needs_review" and not r.recipient_match and r.recipient_needs_review


def test_reordered_name_needs_review():
    assert compare(make(), Proposed("Mokoena Thandi", Decimal("250.00"))).overall == "needs_review"


def test_similar_recipient_and_wrong_amount_is_mismatch():
    assert compare(make(), Proposed("Thandi Mokoenaa", Decimal("1.00"))).overall == "mismatch"


def test_purpose_is_supporting_only():
    r = compare(make(), Proposed("Thandi Mokoena", Decimal("250.00"), purpose="Something else"))
    assert r.overall == "match" and r.purpose_match is False


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "10.123", "NaN", "Infinity", "", 1.5, True, "99999999999"])
def test_invalid_amounts(bad):
    with pytest.raises(InvalidAmount):
        parse_amount(bad)


def test_decimal_precision():
    assert parse_amount("0.10") + parse_amount("0.20") == parse_amount("0.30")
    assert parse_amount(100) == Decimal("100.00")


def test_expired_by_time_and_status():
    with pytest.raises(NotVerifiable) as e:
        check_verifiable(make(expires_at=NOW - timedelta(seconds=1)), "u1", NOW)
    assert e.value.code == "expired"
    with pytest.raises(NotVerifiable):
        check_verifiable(make(status="expired"), "u1", NOW)


def test_already_checked_and_ownership():
    with pytest.raises(NotVerifiable) as e:
        check_verifiable(make(status="verified_match"), "u1", NOW)
    assert e.value.code == "already_checked"
    with pytest.raises(NotVerifiable) as e:
        check_verifiable(make(), "someone-else", NOW)
    assert e.value.code == "not_found"
    check_verifiable(make(status="mismatch"), "u1", NOW)
