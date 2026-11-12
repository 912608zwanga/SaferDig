from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    supabase_url: str = ""
    supabase_anon_key: str = ""  # public key; user JWT is forwarded so RLS applies
    supabase_jwt_secret: str = ""  # only for legacy HS256 projects; leave empty if using JWKS
    allowed_origins: str = "http://localhost:3000"
    environment: str = "development"
    max_body_bytes: int = 16_384
    rate_limit_per_minute: int = 60
    verify_rate_limit_per_minute: int = 20

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip() and o.strip() != "*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
