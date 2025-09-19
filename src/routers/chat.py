from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.requests import (
    ChatMessage,
    CompletionRequest,
    ConversationTitleRequest,
    CreateConversationRequest,
    GenerateTitleRequest,
)
from ..models.responses import ChatResponse
from ..services.ai_service import (
    generate_conversation_title,
    generate_completion,
    get_thread_history,
    get_user_threads,
    handle_advanced_chat,
    handle_chat,
)
from ..services.database_service import (
    create_conversation,
    get_conversation_messages,
    get_user_conversations,
    delete_conversation,
    update_conversation_title,
)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatMessage) -> ChatResponse:
    return await handle_chat(request)


@router.post("/chat/advanced")
async def advanced_chat_endpoint(request: ChatMessage):
    return await handle_advanced_chat(request)


@router.post("/chat/completion")
async def chat_completion_endpoint(request: CompletionRequest):
    result = await generate_completion(request.messages, request.user_id or "")
    return result


@router.get("/chat/threads/{user_id}")
async def get_user_threads_endpoint(user_id: str):
    return await get_user_threads(user_id)


@router.get("/chat/history/{user_id}/{thread_id}")
async def get_thread_history_endpoint(user_id: str, thread_id: str, limit: int = 50):
    return await get_thread_history(user_id, thread_id, limit)


@router.get("/conversations/{user_id}")
async def get_user_conversations_endpoint(user_id: str):
    return await get_user_conversations(user_id)


@router.post("/conversation/{conversation_id}/generate-title")
async def generate_title_endpoint(conversation_id: str, request: GenerateTitleRequest):
    title = await generate_conversation_title(conversation_id, request.user_id)
    success = await update_conversation_title(conversation_id, title)
    return {
        "success": success,
        "title": title,
        "conversation_id": conversation_id,
    }


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages_endpoint(conversation_id: str):
    return await get_conversation_messages(conversation_id)


@router.post("/conversations")
async def create_conversation_endpoint(request: CreateConversationRequest):
    record = await create_conversation(request.user_id, request.title)
    if not record:
        raise HTTPException(status_code=500, detail="Falha ao criar conversa")
    return {"success": True, "conversation": record}


@router.patch("/conversations/{conversation_id}")
async def update_conversation_title_endpoint(
    conversation_id: str, request: ConversationTitleRequest
):
    success = await update_conversation_title(conversation_id, request.title)
    if not success:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")
    return {"success": True}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    success = await delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")
    return {"success": True}
