from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import prompts, rag
from app.config import get_settings
from app.models.schemas import HealthResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Tables are created by scripts/init-db.sql on Postgres first boot.
    # Keep lifespan hook for future migrations / warmups.
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Hub — RAG & Prompt Library",
        description=(
            "Custom layer on top of LiteLLM: document RAG (pgvector) and a shared Prompt Library. "
            "All LLM/embedding calls go through LiteLLM Virtual Keys."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(rag.router)
    app.include_router(prompts.router)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health():
        return HealthResponse(status="ok")

    return app


app = create_app()
