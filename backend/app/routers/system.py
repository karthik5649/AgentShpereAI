from typing import Any

from fastapi import APIRouter
import httpx

from app.core.config import get_settings
from app.services.provider_tracker import provider_tracker

router = APIRouter(prefix="/system", tags=["System"])


async def get_ollama_health() -> dict[str, Any]:
    settings = get_settings()
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    configured_model = settings.OLLAMA_MODEL

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_pulled = any(
                    configured_model == m or configured_model in m or m.startswith(configured_model)
                    for m in models
                )
                return {
                    "reachable": True,
                    "base_url": base_url,
                    "configured_model": configured_model,
                    "model_pulled": model_pulled,
                    "available_models": models,
                    "pull_command": None if model_pulled else f"ollama pull {configured_model}",
                }
    except Exception as exc:
        return {
            "reachable": False,
            "base_url": base_url,
            "configured_model": configured_model,
            "model_pulled": False,
            "error": str(exc),
            "hint": "Local Ollama is offline. Falling back to deterministic plan.",
        }
    return {
        "reachable": False,
        "base_url": base_url,
        "configured_model": configured_model,
        "model_pulled": False,
    }


@router.get("/status")
async def get_system_status() -> dict[str, Any]:
    """Returns provider status, health, request counts, and Ollama status."""
    settings = get_settings()
    ollama_info = await get_ollama_health()
    providers_status = provider_tracker.get_status()

    return {
        "status": "ok",
        "mock_mode": settings.MOCK_MODE,
        "default_llm_provider": settings.LLM_PROVIDER,
        "providers": providers_status,
        "ollama": ollama_info,
        "configured_keys": {
            "SERPER_API_KEY": bool(settings.SERPER_API_KEY),
            "HUNTER_API_KEY": bool(settings.HUNTER_API_KEY),
            "APOLLO_API_KEY": bool(settings.APOLLO_API_KEY),
            "CORESIGNAL_API_KEY": bool(settings.CORESIGNAL_API_KEY),
            "GEMINI_API_KEY": bool(settings.GEMINI_API_KEY),
            "OPENAI_API_KEY": bool(settings.OPENAI_API_KEY),
        },
    }
