import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import ExternalServiceNotConfiguredError
from app.memory import document_store
from app.memory.cache import get_redis_client


logger = logging.getLogger("agentsphere.agents")

GEMINI_INPUT_COST_PER_TOKEN = 0.075 / 1_000_000
GEMINI_OUTPUT_COST_PER_TOKEN = 0.30 / 1_000_000


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def calculate_cost(prompt_tokens: int, completion_tokens: int, provider: str = "gemini") -> float:
    if provider == "gemini":
        return round(
            prompt_tokens * GEMINI_INPUT_COST_PER_TOKEN + completion_tokens * GEMINI_OUTPUT_COST_PER_TOKEN,
            8,
        )
    return 0.0


def token_usage_from_message(message: Any, prompt_text: str, provider: str = "gemini") -> tuple[int, int, float]:
    usage_metadata = getattr(message, "usage_metadata", {}) or {}
    metadata = getattr(message, "response_metadata", {}) or {}
    usage = metadata.get("token_usage") or metadata.get("usage") or {}
    
    prompt_tokens = (
        usage_metadata.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or estimate_tokens(prompt_text)
    )
    completion_tokens = (
        usage_metadata.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("output_tokens")
        or estimate_tokens(str(message.content))
    )
    return prompt_tokens, completion_tokens, calculate_cost(prompt_tokens, completion_tokens, provider)


def check_ollama_available(base_url: str, model: str) -> bool:
    """Quick check if Ollama is reachable and model is pulled."""
    import httpx
    try:
        clean_url = base_url.rstrip("/")
        with httpx.Client(timeout=1.0) as client:
            resp = client.get(f"{clean_url}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                return any(model == m or model in m or m.startswith(model) for m in models)
    except Exception:
        return False
    return False


def get_llm(settings, temperature: float = 0.0) -> Any:
    """Returns LLM instance with local Ollama as default, cloud as opt-in, and deterministic fallback."""
    if getattr(settings, "MOCK_MODE", False):
        return None

    provider = (getattr(settings, "LLM_PROVIDER", "") or "ollama").lower().strip()

    # 1. Cloud provider only if explicitly opted-in via LLM_PROVIDER
    if provider == "gemini" and getattr(settings, "GEMINI_API_KEY", None):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=temperature,
            )
        except ModuleNotFoundError:
            logger.warning("langchain_google_genai is not installed; trying local Ollama")
        except Exception as exc:
            logger.warning("Failed to initialize ChatGoogleGenerativeAI: %s", exc)

    if provider == "openai" and getattr(settings, "OPENAI_API_KEY", None):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=temperature,
            )
        except ModuleNotFoundError:
            logger.warning("langchain_openai is not installed; trying local Ollama")
        except Exception as exc:
            logger.warning("Failed to initialize ChatOpenAI: %s", exc)

    # 2. Local Ollama as default
    if getattr(settings, "OLLAMA_BASE_URL", None):
        ollama_url = settings.OLLAMA_BASE_URL
        ollama_model = settings.OLLAMA_MODEL
        if check_ollama_available(ollama_url, ollama_model):
            try:
                from langchain_ollama import ChatOllama
                return ChatOllama(
                    model=ollama_model,
                    base_url=ollama_url,
                    temperature=temperature,
                )
            except ModuleNotFoundError:
                logger.warning("langchain_ollama is not installed; using deterministic plan")
            except Exception as exc:
                logger.warning("ChatOllama error: %s; using deterministic plan", exc)
        else:
            logger.debug(
                "Local Ollama not reachable or model '%s' not pulled; falling back to deterministic plan",
                ollama_model,
            )

    return None


def parse_json_object(text: str) -> dict:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?", "", clean).strip()
    clean = re.sub(r"```$", "", clean).strip()
    return json.loads(clean)


async def publish_workflow_event(
    workflow_id: str,
    user_id: str,
    event: str,
    agent_name: str | None = None,
    payload: dict | None = None,
) -> dict:
    message = {
        "event": event,
        "workflow_id": workflow_id,
        "user_id": user_id,
        "agent": agent_name,
        "timestamp": utc_now_iso(),
        **(payload or {}),
    }
    logger.info("workflow_event", extra={"workflow_id": workflow_id, "agent": agent_name, "event": event})
    try:
        if agent_name:
            await document_store.log_agent_event(
                {
                    "workflow_id": workflow_id,
                    "user_id": user_id,
                    "agent_name": agent_name,
                    "event_type": event,
                    "output_summary": payload.get("message") if payload else None,
                    "payload": payload or {},
                }
            )
    except (ExternalServiceNotConfiguredError, ValueError):
        logger.debug("agent_event_not_persisted", extra={"workflow_id": workflow_id, "event": event})
    try:
        redis: Any = get_redis_client()
        await redis.publish(f"workflow:{workflow_id}:events", json.dumps(message, default=str))
        await redis.rpush(f"workflow:{workflow_id}:event_buffer", json.dumps(message, default=str))
        await redis.ltrim(f"workflow:{workflow_id}:event_buffer", -200, -1)
        await redis.expire(f"workflow:{workflow_id}:event_buffer", 86400)
    except ExternalServiceNotConfiguredError:
        logger.debug("workflow_event_not_published", extra={"workflow_id": workflow_id, "event": event})
    return message


async def emit_agent_started(state: dict, agent_name: str) -> None:
    await publish_workflow_event(
        workflow_id=state["workflow_id"],
        user_id=state["user_id"],
        event="agent_started",
        agent_name=agent_name,
        payload={"message": f"{agent_name} started"},
    )


async def emit_agent_completed(state: dict, agent_name: str, payload: dict | None = None) -> None:
    await publish_workflow_event(
        workflow_id=state["workflow_id"],
        user_id=state["user_id"],
        event="agent_completed",
        agent_name=agent_name,
        payload=payload or {"message": f"{agent_name} completed"},
    )


async def emit_agent_error(state: dict, agent_name: str, error: Exception) -> None:
    await publish_workflow_event(
        workflow_id=state["workflow_id"],
        user_id=state["user_id"],
        event="error",
        agent_name=agent_name,
        payload={"message": str(error)},
    )
