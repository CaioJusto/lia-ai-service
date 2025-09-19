from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
OPENAI_CONCURRENCY_LIMIT = int(os.getenv("OPENAI_CONCURRENCY_LIMIT", "8"))

_async_client: Optional[AsyncOpenAI] = None
_sync_client: Optional[OpenAI] = None
_semaphore: Optional[asyncio.Semaphore] = None

if OPENAI_API_KEY and OPENAI_API_KEY != "sk-test-key-placeholder":
    _async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    _sync_client = OpenAI(api_key=OPENAI_API_KEY)
    _semaphore = asyncio.Semaphore(max(1, OPENAI_CONCURRENCY_LIMIT))


def sync_openai_client() -> Optional[OpenAI]:
    return _sync_client


def is_openai_configured() -> bool:
    return _async_client is not None or _sync_client is not None


async def create_chat_completion(
    messages: List[Dict[str, Any]],
    **kwargs: Any,
):
    if not is_openai_configured():
        raise RuntimeError("OpenAI client not configured")

    params = dict(kwargs)
    params.setdefault("model", OPENAI_DEFAULT_MODEL)

    if _async_client is not None:
        if _semaphore is not None:
            async with _semaphore:
                return await _async_client.chat.completions.create(
                    messages=messages,
                    **params,
                )
        return await _async_client.chat.completions.create(
            messages=messages,
            **params,
        )

    # Fallback to synchronous client
    assert _sync_client is not None
    if _semaphore is not None:
        async with _semaphore:
            return await asyncio.to_thread(
                _sync_client.chat.completions.create,
                messages=messages,
                **params,
            )

    return await asyncio.to_thread(
        _sync_client.chat.completions.create,
        messages=messages,
        **params,
    )
