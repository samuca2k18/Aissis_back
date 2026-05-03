import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Base, SessionLocal, check_database_health, engine
from .routes import (
    agenda,
    auditoria,
    auth,
    campanhas,
    clientes,
    dashboard,
    documentos,
    leads,
    negocios,
    whatsapp_router,
)
from .services import auth as auth_service
from .services.audit import AuditEvent, register_audit_event
from .services.evolution_api import check_evolution_health
from .services.scheduler import start_scheduler, stop_scheduler
from .settings import settings

log = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
        log.warning("AUTO_CREATE_TABLES está ativo. Use migrações (Alembic) em produção.")
    db = SessionLocal()
    try:
        auth_service.bootstrap_admin_if_needed(db)
    except Exception:
        log.exception("Falha ao executar bootstrap de usuário admin.")
    finally:
        db.close()

    if settings.SCHEDULER_ENABLED:
        start_scheduler()
    yield
    if settings.SCHEDULER_ENABLED:
        stop_scheduler()


def create_app() -> FastAPI:
    _configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        description="CRM + Secretária Executiva da Assis Pianos",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID", "X-Webhook-Token", "X-Bootstrap-Token"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        started_at = time.perf_counter()
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            log.exception(
                "request_error request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request_done request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        if settings.AUDIT_LOG_ENABLED and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            path = request.url.path
            excluded_prefixes = ("/health", "/docs", "/redoc", "/openapi.json", "/whatsapp/webhook")
            if not any(path.startswith(prefix) for prefix in excluded_prefixes):
                db = SessionLocal()
                try:
                    register_audit_event(
                        db,
                        AuditEvent(
                            user_id=getattr(request.state, "auth_user_id", None),
                            role=getattr(request.state, "auth_user_role", None),
                            action=f"{request.method} {path}",
                            method=request.method,
                            path=path,
                            status_code=response.status_code,
                            request_id=request_id,
                            ip_address=request.client.host if request.client else None,
                            user_agent=request.headers.get("user-agent"),
                            details={
                                "query_params": dict(request.query_params),
                            },
                        ),
                    )
                except Exception:
                    log.exception("Falha ao registrar evento de auditoria request_id=%s", request_id)
                finally:
                    db.close()

        return response

    app.include_router(auth)
    app.include_router(clientes)
    app.include_router(leads)
    app.include_router(negocios)
    app.include_router(documentos)
    app.include_router(campanhas)
    app.include_router(agenda)
    app.include_router(dashboard)
    app.include_router(auditoria)
    app.include_router(whatsapp_router)

    @app.get("/health", tags=["health"])
    async def health():
        db_ok = check_database_health()
        evo_ok = await check_evolution_health()
        checks = {"database": db_ok, "evolution_api": evo_ok}
        overall_ok = all(checks.values())
        status = "ok" if overall_ok else "degraded"
        return {
            "status": status,
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "checks": checks,
        }

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        log.exception("unhandled_exception request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocorreu um erro interno no servidor.", "request_id": request_id},
        )

    return app


app = create_app()
