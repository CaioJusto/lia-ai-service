from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Modelo base para requisições de chat."""

    message: str = Field(..., description="Mensagem enviada pelo usuário")
    conversation_id: str = Field(..., description="Identificador da conversa")
    user_id: str = Field(..., description="Identificador do usuário")


class UserProfile(BaseModel):
    """Estrutura de perfil de usuário sincronizada com o banco."""

    user_id: str
    name: Optional[str] = None
    age: Optional[int] = None
    education_level: Optional[str] = None
    favorite_subjects: Optional[List[str]] = []
    learning_style: Optional[str] = None
    study_goals: Optional[List[str]] = []
    difficulty_topics: Optional[List[str]] = []
    preferred_explanation_style: Optional[str] = "friendly"
    timezone: Optional[str] = "America/Sao_Paulo"
    study_schedule: Optional[Dict[str, Any]] = {}


class UpdateProfileRequest(BaseModel):
    user_id: str
    profile_data: Dict[str, Any]


class GenerateTitleRequest(BaseModel):
    conversation_id: str
    user_id: str


class FlashcardRequest(BaseModel):
    topic: str
    subject: str
    user_id: str
    difficulty: str = "medium"
    count: int = Field(default=5, ge=1, le=30)


class QuizRequest(BaseModel):
    topic: str
    user_id: str
    difficulty: str = "medium"
    question_count: int = Field(default=5, ge=1, le=50)


class NoteRequest(BaseModel):
    topic: str
    user_id: str
    type: str = "resumo"
    length: str = "medium"
    complexity: str = "basic"
    subject: Optional[str] = None


class MindMapRequest(BaseModel):
    topic: str
    node_count: int = Field(default=7, ge=3, le=20)
    user_id: Optional[str] = ""


class StudyPlanRequest(BaseModel):
    subject: str
    user_id: str
    duration_weeks: int = Field(default=4, ge=1, le=52)
    hours_per_day: int = Field(default=2, ge=1, le=12)


class CompletionMessage(BaseModel):
    role: str
    content: str


class CompletionRequest(BaseModel):
    messages: List[CompletionMessage]
    user_id: Optional[str] = ""


class FlashcardsFromTextRequest(BaseModel):
    text: str
    user_id: Optional[str] = ""
    subject: Optional[str] = None
    count: int = Field(default=5, ge=1, le=30)
    difficulty: str = "medium"


class StudyConversationRequest(BaseModel):
    question: str
    answer: str
    user_id: Optional[str] = ""


class CreateConversationRequest(BaseModel):
    user_id: str
    title: Optional[str] = "Nova Conversa"


class ConversationTitleRequest(BaseModel):
    title: str
