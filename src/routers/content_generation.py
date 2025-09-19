from __future__ import annotations

from fastapi import APIRouter

from ..models.requests import (
    FlashcardRequest,
    FlashcardsFromTextRequest,
    MindMapRequest,
    NoteRequest,
    QuizRequest,
    StudyConversationRequest,
    StudyPlanRequest,
)
from ..services.ai_service import (
    create_study_plan,
    generate_flashcards_from_text,
    generate_mind_map,
    generate_notes,
    generate_quiz,
    generate_study_conversation,
    start_flashcard_generation,
)
from ..services.database_service import get_user_study_plans

router = APIRouter(tags=["content"], prefix="")


@router.post("/generate-flashcards")
async def generate_flashcards_endpoint(request: FlashcardRequest):
    return await start_flashcard_generation(request)


@router.post("/generate-flashcards/from-text")
async def generate_flashcards_from_text_endpoint(request: FlashcardsFromTextRequest):
    return await generate_flashcards_from_text(request)


@router.post("/generate-quiz")
async def generate_quiz_endpoint(request: QuizRequest):
    return await generate_quiz(request)


@router.post("/generate-notes")
async def generate_notes_endpoint(request: NoteRequest):
    return await generate_notes(request)


@router.post("/generate-mind-map")
async def generate_mind_map_endpoint(request: MindMapRequest):
    return await generate_mind_map(request)


@router.post("/study-plan/create")
async def create_study_plan_endpoint(request: StudyPlanRequest):
    return await create_study_plan(request)


@router.get("/study-plans/{user_id}")
async def get_study_plans_endpoint(user_id: str):
    return await get_user_study_plans(user_id)


@router.post("/study-conversation")
async def generate_study_conversation_endpoint(request: StudyConversationRequest):
    return await generate_study_conversation(request)
