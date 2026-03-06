from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Base, engine
from .routes import agenda, campanhas, clientes, dashboard, documentos, leads, negocios
from .settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="CRM + Secretária Executiva da Assis Pianos",
        version="1.0.0",
    )

    # CORS — ajuste origins conforme necessário
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Cria tabelas automaticamente (MVP)
    Base.metadata.create_all(bind=engine)

    # Rotas
    app.include_router(clientes)
    app.include_router(leads)
    app.include_router(negocios)
    app.include_router(documentos)
    app.include_router(campanhas)
    app.include_router(agenda)
    app.include_router(dashboard)

    @app.get("/health", tags=["health"])
    def health():
        return {"ok": True, "app": settings.APP_NAME, "version": "1.0.0"}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Ocorreu um erro interno no servidor.", "error": str(exc)},
        )

    return app


app = create_app()
