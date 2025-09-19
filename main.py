from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import chat, content_generation, health, profile

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "")

if allowed_origins_raw:
    allowed_origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
else:
    allowed_origins = ["*"] if ENVIRONMENT in {"dev", "development", "local"} else []

app = FastAPI(
    title="Lia AI Service",
    description="Sistema de IA para o App de Estudos usando arquitetura modular",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
    max_age=3600,
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(content_generation.router)
app.include_router(profile.router)


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
