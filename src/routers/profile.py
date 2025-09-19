from __future__ import annotations

from fastapi import APIRouter

from ..models.requests import UpdateProfileRequest
from ..services.database_service import get_user_profile, save_user_profile

router = APIRouter(tags=["profile"])


@router.get("/profile/{user_id}")
async def get_profile(user_id: str):
    try:
        profile = await get_user_profile(user_id)
        if profile:
            return {"success": True, "profile": profile}
        return {"success": True, "profile": None, "message": "No profile found for user"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"success": False, "error": str(exc)}


@router.post("/profile/update")
async def update_profile(request: UpdateProfileRequest):
    try:
        success = await save_user_profile(request.user_id, request.profile_data)
        if success:
            updated_profile = await get_user_profile(request.user_id)
            return {
                "success": True,
                "message": "Profile updated successfully",
                "profile": updated_profile,
            }
        return {"success": False, "error": "Failed to update profile"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"success": False, "error": str(exc)}


@router.post("/profile/setup")
async def setup_profile(request: UpdateProfileRequest):
    try:
        profile_data = request.profile_data
        if not profile_data.get("name"):
            return {"success": False, "error": "Name is required for profile setup"}

        defaults = {
            "preferred_explanation_style": "friendly",
            "study_schedule": {"morning": True, "afternoon": True, "evening": True},
        }
        for key, value in defaults.items():
            profile_data.setdefault(key, value)

        success = await save_user_profile(request.user_id, profile_data)
        if success:
            return {
                "success": True,
                "message": f"Perfil criado com sucesso! Olá, {profile_data['name']}! 🎉",
                "profile": profile_data,
            }
        return {"success": False, "error": "Failed to create profile"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"success": False, "error": str(exc)}


@router.post("/profile/setup-wizard")
async def setup_profile_legacy(request: UpdateProfileRequest):
    return await setup_profile(request)

