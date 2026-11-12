import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routes.api import router

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
settings = get_settings()
app = FastAPI(
    title="IntentGuard API",
    version="1.0.0",
    description="Simulation only. Not connected to any bank.",
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def guard(request: Request, call_next):
    if int(request.headers.get("content-length") or 0) > settings.max_body_bytes:
        return JSONResponse({"detail": "Request too large."}, status_code=413)
    resp = await call_next(request)
    resp.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        }
    )
    return resp


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"].removeprefix("Value error, ")}
        for e in exc.errors()
    ]
    return JSONResponse({"detail": "Please check the highlighted fields.", "errors": errors}, status_code=422)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    logging.getLogger("intentguard").error("unhandled %s", type(exc).__name__)
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    ok = bool(settings.supabase_url and settings.supabase_anon_key)
    return JSONResponse({"status": "ready" if ok else "not_configured"}, status_code=200 if ok else 503)


app.include_router(router)
