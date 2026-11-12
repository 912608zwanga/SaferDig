"""Pure comparison logic. No I/O, so it is fully unit-testable.

Matching rules (shown to users in the UI):
  * Recipient: equal after Unicode NFKC, trimming, collapsing inner whitespace and
    case-folding. Anything merely similar is "needs review", never a match.
  * Amount: exact Decimal equality at two decimal places. Currency is ZAR only.
  * Purpose/reference: supporting information only; never changes the overall result.
A match means the details agree with what you wrote down. It does not mean the
payment is safe, and a mismatch does not mean fraud.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher

MAX_AMOUNT = Decimal("9999999999.99")
SIMILARITY_REVIEW_THRESHOLD = 0.8
_TWO_PLACES = Decimal("0.01")


class InvalidAmount(ValueError):
    pass


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", text).strip().casefold()


def parse_amount(value: str | int | Decimal) -> Decimal:
    """Parse to a positive 2dp Decimal. Floats are rejected to avoid binary rounding."""
    if isinstance(value, (float, bool)):
        raise InvalidAmount("Amount must be given as text or a whole number, not a float.")
    try:
        amount = Decimal(str(value).strip().replace(" ", ""))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidAmount("Amount is not a valid number.") from exc
    if not amount.is_finite():
        raise InvalidAmount("Amount is not a valid number.")
    if amount != amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP):
        raise InvalidAmount("Amount can have at most two decimal places.")
    amount = amount.quantize(_TWO_PLACES)
    if amount <= 0:
        raise InvalidAmount("Amount must be greater than zero.")
    if amount > MAX_AMOUNT:
        raise InvalidAmount("Amount is too large.")
    return amount


@dataclass(frozen=True)
class Intention:
    id: str
    user_id: str
    recipient_name: str
    amount: Decimal
    purpose: str
    reference: str | None
    status: str
    expires_at: datetime


@dataclass(frozen=True)
class Proposed:
    recipient_name: str
    amount: Decimal
    purpose: str | None = None
    reference: str | None = None


@dataclass(frozen=True)
class Comparison:
    recipient_match: bool
    recipient_needs_review: bool
    amount_match: bool
    purpose_match: bool | None
    overall: str
    explanation: list[str]


class NotVerifiable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def check_verifiable(intention: Intention, owner_id: str, now: datetime) -> None:
    if intention.user_id != owner_id:
        raise NotVerifiable("not_found", "Intention not found.")
    if intention.status == "expired" or intention.expires_at <= now:
        raise NotVerifiable("expired", "This intention has expired. Please create a new one.")
    if intention.status == "verified_match":
        raise NotVerifiable("already_checked", "This intention has already been checked and matched.")


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if sorted(a.split()) == sorted(b.split()):
        return True
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_REVIEW_THRESHOLD


def compare(intention: Intention, proposed: Proposed) -> Comparison:
    want, got = normalize_text(intention.recipient_name), normalize_text(proposed.recipient_name)
    recipient_match = want == got
    needs_review = (not recipient_match) and _similar(want, got)
    amount_match = intention.amount == proposed.amount

    purpose_match: bool | None = None
    checks = []
    if proposed.purpose:
        checks.append(normalize_text(proposed.purpose) == normalize_text(intention.purpose))
    if proposed.reference:
        checks.append(normalize_text(proposed.reference) == normalize_text(intention.reference))
    if checks:
        purpose_match = all(checks)

    notes: list[str] = []
    if recipient_match:
        notes.append("The recipient matches what you intended.")
    elif needs_review:
        notes.append(
            f"The recipient is similar to, but not exactly, what you intended "
            f"(you intended “{intention.recipient_name}”; the payment shows “{proposed.recipient_name}”). "
            "Please check carefully."
        )
    else:
        notes.append(
            f"The recipient is different (you intended “{intention.recipient_name}”; "
            f"the payment shows “{proposed.recipient_name}”)."
        )
    if amount_match:
        notes.append("The amount matches what you intended.")
    else:
        notes.append(
            f"The amount is different (you intended R{intention.amount}; the payment shows R{proposed.amount})."
        )
    if purpose_match is False:
        notes.append("The purpose or reference differs. This is for information and does not change the result.")

    if recipient_match and amount_match:
        overall = "match"
    elif needs_review and amount_match:
        overall = "needs_review"
    else:
        overall = "mismatch"
    return Comparison(recipient_match, needs_review, amount_match, purpose_match, overall, notes)
