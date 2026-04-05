"""Peakwise API application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from peakwise.api.routes.ask import router as ask_router
from peakwise.api.routes.debug import router as debug_router
from peakwise.api.routes.feedback import router as feedback_router
from peakwise.api.routes.health import router as health_router
from peakwise.api.routes.manual_input import router as manual_input_router
from peakwise.api.routes.running import router as running_router
from peakwise.api.routes.strength import router as strength_router
from peakwise.api.routes.today import router as today_router
from peakwise.api.routes.weekly_review import router as weekly_review_router


def create_app() -> FastAPI:
    app = FastAPI(title="Peakwise", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(today_router, prefix="/api")
    app.include_router(running_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(strength_router, prefix="/api")
    app.include_router(weekly_review_router, prefix="/api")
    app.include_router(manual_input_router, prefix="/api")
    app.include_router(ask_router, prefix="/api")
    app.include_router(debug_router, prefix="/api")
    app.include_router(feedback_router, prefix="/api")

    return app


app = create_app()
