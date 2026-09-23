"""FastAPI application factory for kit-api.

`uvicorn apps.api.app.main:app` serves the module-level instance. Startup does
schema + index creation, tracing install, and one tool registry; the embed
model is deliberately NOT warmed here — it loads lazily on first
upload/search so the process answers /healthz quickly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .agent.trace import install_tracing
from .agent.tools import ToolRegistry
from .api.routes import router, unhandled_exception_handler, validation_exception_handler
from .config import get_settings
from .rag import search as rag_search
from .rag import store as rag_store

API_VERSION = "0.1.0"


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.init_schema()
        rag_store.ensure_index()
        install_tracing()
        registry = ToolRegistry()
        rag_search.register_tools(registry)
        app.state.tools = registry
        yield

    app = FastAPI(title="kit-api", version=API_VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    return app


app = create_app()
