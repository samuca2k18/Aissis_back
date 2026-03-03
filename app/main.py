from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .settings import settings
from .database import engine, Base
from .routes import clientes, leads, negocios, documentos, campanhas, agenda, dashboard


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

    return app


app = create_app()
