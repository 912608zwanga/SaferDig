"""Verifies Supabase access tokens server-side. Identity always comes from the token."""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    token: str


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, timeout=5)


def decode_token(token: str, settings: Settings) -> dict:
    opts = {"require": ["exp", "sub"]}
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise jwt.InvalidTokenError("HS256 not configured")
        return jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated", options=opts
        )
    if alg in ("ES256", "RS256") and settings.supabase_url:
        key = _jwks_client(f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
        signing = key.get_signing_key_from_jwt(token).key
        return jwt.decode(token, signing, algorithms=[alg], audience="authenticated", options=opts)
    raise jwt.InvalidTokenError("unsupported algorithm")  # never accept alg=none


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    unauthorised = HTTPException(401, "Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorised
    try:
        claims = decode_token(creds.credentials, settings)
    except Exception:  # noqa: BLE001 - any failure is a 401; details are not leaked
        raise unauthorised from None
    return CurrentUser(id=str(claims["sub"]), token=creds.credentials)
