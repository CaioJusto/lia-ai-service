from __future__ import annotations

import platform
import socket
from datetime import datetime

from fastapi import APIRouter

from ..services.ai_service import (
    get_ai_capabilities_status,
    get_lia_agent,
    get_openai_client,
    stream_progress,
)
from ..services.database_service import (
    conversation_cache,
    env_requirements,
    get_supabase_client,
    test_supabase_connection,
)

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {
        "service": "Lia AI Service",
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def health_check():
    supabase_client = get_supabase_client()
    openai_ready = get_openai_client() is not None
    env_missing = [key for key, present in env_requirements().items() if not present]

    return {
        "status": "healthy" if not env_missing else "degraded",
        "conversations_cached": len(conversation_cache),
        "openai_configured": openai_ready,
        "supabase_configured": supabase_client is not None,
        "env_missing": env_missing,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/services")
async def services_health_check():
    status = get_ai_capabilities_status()
    status["timestamp"] = datetime.now().isoformat()
    return status


@router.get("/mobile-test")
async def mobile_connectivity_test():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    return {
        "status": "mobile_ready",
        "message": "Conectividade móvel funcionando!",
        "server_info": {
            "hostname": hostname,
            "local_ip": local_ip,
            "platform": platform.system(),
            "python_version": platform.python_version(),
        },
        "services": {
            "openai": get_openai_client() is not None,
            "supabase": get_supabase_client() is not None,
            "agent": get_lia_agent() is not None,
        },
        "cors_enabled": True,
        "timestamp": datetime.now().isoformat(),
        "test_endpoints": {
            "health": "/health",
            "chat": "/chat/advanced",
            "mobile_test": "/mobile-test",
            "progress": "/progress/{operation_id}",
        },
    }


@router.get("/progress/{operation_id}")
async def get_progress_stream(operation_id: str):
    return await stream_progress(operation_id)


@router.get("/progress/legacy/{operation_id}")
async def get_progress_stream_legacy(operation_id: str):
    return await stream_progress(operation_id)


@router.get("/test-supabase")
async def test_supabase_endpoint():
    return await test_supabase_connection()
