from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ChatResponse(BaseModel):
    success: bool
    conversation_id: str
    message_id: str
    response: Optional[str] = None
    error: Optional[str] = None


class FlashcardResponse(BaseModel):
    success: bool
    flashcards: Optional[List[Dict[str, Any]]] = None
    topic: Optional[str] = None
    subject: Optional[str] = None
    count: Optional[int] = None
    difficulty: Optional[str] = None
    generation_method: Optional[str] = None
    error: Optional[str] = None


class QuizResponse(BaseModel):
    success: bool
    quiz: Optional[Any] = None
    topic: Optional[str] = None
    question_count: Optional[int] = None
    difficulty: Optional[str] = None
    error: Optional[str] = None


class NoteResponse(BaseModel):
    success: bool
    text: Optional[str] = None
    topic: Optional[str] = None
    type: Optional[str] = None
    length: Optional[str] = None
    complexity: Optional[str] = None
    error: Optional[str] = None


class MindMapResponse(BaseModel):
    success: bool
    mind_map: Optional[Any] = None
    topic: Optional[str] = None
    node_count: Optional[int] = None
    error: Optional[str] = None


class StudyPlanResponse(BaseModel):
    success: bool
    plans: Optional[List[Dict[str, Any]]] = None
    plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CompletionResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None


class StudyConversationResponse(BaseModel):
    success: bool
    conversation: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
