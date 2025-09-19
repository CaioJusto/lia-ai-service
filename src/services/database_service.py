from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

from dotenv import load_dotenv

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - optional dependency
    Client = Any  # type: ignore
    create_client = None  # type: ignore


load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

supabase_client: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase client initialized successfully")
    except Exception as exc:  # pragma: no cover - initialization only
        logger.error("❌ Failed to initialize Supabase client: %s", exc)
else:
    logger.warning("⚠️ Supabase credentials missing or create_client unavailable")

conversation_cache: Dict[str, List[Dict[str, Any]]] = {}

T = TypeVar("T")


def env_requirements() -> Dict[str, bool]:
    return {
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "SUPABASE_URL": bool(SUPABASE_URL),
        "SUPABASE_SERVICE_ROLE_KEY": bool(SUPABASE_KEY),
    }


def get_supabase_client() -> Optional[Client]:
    return supabase_client


async def _run_db_call(func: Callable[[], T]) -> T:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)


async def save_message_to_db(
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    message_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not supabase_client:
        logger.warning("⚠️ Supabase not available, message not persisted")
        return None

    def _persist() -> Optional[Dict[str, Any]]:
        payload = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "message_id": message_id
            or f"{role}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}",
            "created_at": datetime.now().isoformat(),
        }
        result = supabase_client.table("ai_messages").insert(payload).execute()
        logger.info("✅ Message saved to database: %s", payload["message_id"])
        return result.data[0] if result.data else None

    try:
        return await _run_db_call(_persist)
    except Exception as exc:
        logger.error("❌ Failed to save message: %s", exc)
        return None


async def get_conversation_history(
    conversation_id: str,
    user_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    cache_key = f"{user_id}_{conversation_id}"

    if not supabase_client:
        logger.warning("⚠️ Supabase not available, using cache for %s", cache_key)
        return conversation_cache.get(cache_key, [])

    def _fetch() -> List[Dict[str, Any]]:
        result = (
            supabase_client.table("ai_messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        messages: List[Dict[str, Any]] = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in result.data
        ]
        logger.info(
            "✅ Retrieved %s messages from database for conversation %s",
            len(messages),
            conversation_id,
        )
        return messages

    try:
        return await _run_db_call(_fetch)
    except Exception as exc:
        logger.error("❌ Failed to fetch conversation history: %s", exc)
        cached = conversation_cache.get(cache_key, [])
        logger.info("📦 Using cached messages: %s for %s", len(cached), cache_key)
        return cached


async def ensure_conversation_exists(conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    if not supabase_client:
        return None

    def _ensure() -> Optional[Dict[str, Any]]:
        existing = (
            supabase_client.table("ai_conversations")
            .select("id")
            .eq("id", conversation_id)
            .execute()
        )
        if not existing.data:
            payload = {
                "id": conversation_id,
                "user_id": user_id,
                "title": "Nova Conversa com Lia",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            inserted = supabase_client.table("ai_conversations").insert(payload).execute()
            logger.info("✅ Created new conversation: %s", conversation_id)
            return inserted.data[0] if inserted.data else None

        supabase_client.table("ai_conversations").update(
            {"updated_at": datetime.now().isoformat()}
        ).eq("id", conversation_id).execute()
        return existing.data[0]

    try:
        return await _run_db_call(_ensure)
    except Exception as exc:
        logger.error("❌ Failed to ensure conversation exists: %s", exc)
        return None


async def update_conversation_title(conversation_id: str, title: str) -> bool:
    if not supabase_client:
        return False

    def _update() -> bool:
        supabase_client.table("ai_conversations").update(
            {"title": title, "updated_at": datetime.now().isoformat()}
        ).eq("id", conversation_id).execute()
        logger.info("✅ Updated conversation title: %s -> %s", conversation_id, title)
        return True

    try:
        return await _run_db_call(_update)
    except Exception as exc:
        logger.error("❌ Failed to update conversation title: %s", exc)
        return False


async def create_conversation(user_id: str, title: str) -> Optional[Dict[str, Any]]:
    if not supabase_client:
        return None

    def _create() -> Optional[Dict[str, Any]]:
        conversation_id = str(uuid.uuid4())
        payload = {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "assistant_id": "lia-langgraph",
            "thread_id": conversation_id,
        }
        result = supabase_client.table("ai_conversations").insert(payload).execute()
        if result.data:
            return result.data[0]
        return None

    try:
        return await _run_db_call(_create)
    except Exception as exc:
        logger.error("❌ Failed to create conversation: %s", exc)
        return None


async def delete_conversation(conversation_id: str) -> bool:
    if not supabase_client:
        return False

    def _delete() -> bool:
        supabase_client.table("ai_messages").delete().eq(
            "conversation_id", conversation_id
        ).execute()
        supabase_client.table("ai_conversations").delete().eq(
            "id", conversation_id
        ).execute()
        return True

    try:
        return await _run_db_call(_delete)
    except Exception as exc:
        logger.error("❌ Failed to delete conversation: %s", exc)
        return False


async def get_user_conversations(user_id: str) -> Dict[str, Any]:
    if not supabase_client:
        return {
            "success": False,
            "error": "Database not available",
            "conversations": [],
        }

    def _fetch() -> Dict[str, Any]:
        result = (
            supabase_client.table("ai_conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return {
            "success": True,
            "conversations": result.data,
            "count": len(result.data),
        }

    try:
        return await _run_db_call(_fetch)
    except Exception as exc:
        logger.error("❌ Failed to fetch conversations: %s", exc)
        return {"success": False, "error": str(exc), "conversations": []}


async def get_conversation_messages(conversation_id: str) -> Dict[str, Any]:
    if not supabase_client:
        return {
            "success": False,
            "error": "Database not available",
            "messages": [],
        }

    def _fetch() -> Dict[str, Any]:
        result = (
            supabase_client.table("ai_messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )
        return {
            "success": True,
            "messages": result.data,
            "count": len(result.data),
        }

    try:
        return await _run_db_call(_fetch)
    except Exception as exc:
        logger.error("❌ Failed to fetch messages: %s", exc)
        return {"success": False, "error": str(exc), "messages": []}


async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    if not supabase_client:
        logger.warning("⚠️ Supabase not available for user profiles")
        return None

    def _fetch() -> Optional[Dict[str, Any]]:
        result = (
            supabase_client.table("user_profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        if result.data:
            profile = result.data[0]
            logger.info("✅ Retrieved profile for user %s", user_id)
            return profile
        logger.info("📝 No profile found for user %s", user_id)
        return None

    try:
        return await _run_db_call(_fetch)
    except Exception as exc:
        logger.error("❌ Failed to get user profile: %s", exc)
        return None


async def save_user_profile(user_id: str, profile_data: Dict[str, Any]) -> bool:
    if not supabase_client:
        logger.warning("⚠️ Supabase not available for saving profiles")
        return False

    try:
        existing = await get_user_profile(user_id)

        profile_record = {
            "user_id": user_id,
            "name": profile_data.get("name"),
            "age": profile_data.get("age"),
            "education_level": profile_data.get("education_level"),
            "favorite_subjects": profile_data.get("favorite_subjects", []),
            "learning_style": profile_data.get("learning_style"),
            "study_goals": profile_data.get("study_goals", []),
            "difficulty_topics": profile_data.get("difficulty_topics", []),
            "preferred_explanation_style": profile_data.get(
                "preferred_explanation_style", "friendly"
            ),
            "study_schedule": profile_data.get("study_schedule", {}),
            "updated_at": datetime.now().isoformat(),
        }

        def _persist() -> bool:
            if existing:
                supabase_client.table("user_profiles").update(profile_record).eq(
                    "user_id", user_id
                ).execute()
                logger.info("✅ Updated profile for user %s", user_id)
            else:
                profile_record["created_at"] = datetime.now().isoformat()
                supabase_client.table("user_profiles").insert(profile_record).execute()
                logger.info("✅ Created profile for user %s", user_id)
            return True

        return await _run_db_call(_persist)
    except Exception as exc:
        logger.error("❌ Failed to save user profile: %s", exc)
        return False


async def get_user_study_plans(user_id: str) -> Dict[str, Any]:
    if not supabase_client:
        return {"success": False, "error": "Database not available"}

    def _fetch() -> Dict[str, Any]:
        response = (
            supabase_client.table("study_plans")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {"success": True, "plans": response.data}

    try:
        return await _run_db_call(_fetch)
    except Exception as exc:
        logger.error("❌ Failed to fetch study plans: %s", exc)
        return {"success": False, "error": str(exc)}


async def test_supabase_connection() -> Dict[str, Any]:
    if not supabase_client:
        return {
            "success": False,
            "error": "Supabase client not initialized",
            "configured": False,
        }

    def _test() -> Dict[str, Any]:
        result = supabase_client.table("ai_conversations").select(
            "count", count="exact"
        ).execute()
        return {
            "success": True,
            "configured": True,
            "conversations_count": result.count if hasattr(result, "count") else None,
        }

    try:
        return await _run_db_call(_test)
    except Exception as exc:
        logger.error("❌ Supabase connection test failed: %s", exc)
        return {"success": False, "configured": False, "error": str(exc)}
