import logging
import warnings
from contextlib import asynccontextmanager

# Suppress FutureWarning from langchain_google_genai about deprecated google.generativeai
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.memory.cache import init_cache
from app.memory.document_store import init_document_store
from app.memory.vector_store import init_vector_store, vector_stats
from app.routers import (
    agents,
    analytics,
    auth,
    companies,
    contacts,
    domain_profiles,
    eval,
    memory,
    system,
    websockets,
    workflows,
)


settings = get_settings()


def create_embeddings(settings):
    if settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            return GoogleGenerativeAIEmbeddings(
                model=settings.GEMINI_EMBEDDING_MODEL,
                google_api_key=settings.GEMINI_API_KEY
            )
        except ModuleNotFoundError:
            logging.getLogger("agentsphere").warning(
                "langchain_google_genai is not installed; trying local Ollama embeddings"
            )

    try:
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.OLLAMA_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )
    except ModuleNotFoundError:
        logging.getLogger("agentsphere").warning(
            "langchain_ollama is not installed; vector embeddings will use local fallback"
        )

    return None


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger = logging.getLogger("agentsphere")
    logger.info("starting_agentsphere_backend")

    mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    embeddings = create_embeddings(settings)

    app.state.mongo_client = mongo_client
    app.state.db = mongo_client[settings.MONGODB_DB_NAME]
    app.state.redis = redis_client

    init_document_store(app.state.db)
    init_cache(redis_client)
    init_vector_store(embeddings, settings.FAISS_INDEX_PATH)

    # Seed default domain profiles if not already present
    try:
        from app.domain.domain_profile import DEFAULT_DOMAIN_PROFILES
        from app.memory.document_store import get_domain_profile, save_domain_profile
        for profile in DEFAULT_DOMAIN_PROFILES:
            existing = await get_domain_profile(profile.id)
            if not existing:
                await save_domain_profile(profile.model_dump())
    except Exception as exc:
        logger.warning(f"Failed to seed domain profiles: {exc}")

    # Ollama startup health check and diagnostic logging
    try:
        from app.routers.system import get_ollama_health
        ollama_health = await get_ollama_health()
        if ollama_health.get("reachable"):
            if ollama_health.get("model_pulled"):
                logger.info("Local Ollama ready with model '%s' at %s", settings.OLLAMA_MODEL, settings.OLLAMA_BASE_URL)
            else:
                logger.warning(
                    "Ollama is reachable at %s but configured model '%s' is NOT pulled! Run: %s",
                    settings.OLLAMA_BASE_URL,
                    settings.OLLAMA_MODEL,
                    ollama_health.get("pull_command"),
                )
        else:
            logger.info("Local Ollama not reachable at %s. Agents will use deterministic fallback.", settings.OLLAMA_BASE_URL)
    except Exception as exc:
        logger.warning("Ollama startup check failed: %s", exc)

    try:
        yield
    finally:
        logger.info("stopping_agentsphere_backend")
        await redis_client.aclose()
        mongo_client.close()


app = FastAPI(
    title="AgentSphere AI Backend",
    version="1.0.0",
    description="Enterprise Agentic AI Platform backend for B2B customer discovery and prospect intelligence.",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(domain_profiles.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(system.router)
app.include_router(websockets.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    from app.services.provider_tracker import provider_tracker
    checks = {
        "app": "ok",
        "mongodb": "unknown",
        "redis": "unknown",
        "vector_store": vector_stats(),
        "providers": provider_tracker.get_status(),
    }
    try:
        await app.state.db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:
        checks["mongodb"] = f"error: {exc}"
    try:
        await app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # Report which API keys are configured
    checks["api_keys"] = {
        "GEMINI_API_KEY": bool(settings.GEMINI_API_KEY),
        "OLLAMA_BASE_URL": bool(settings.OLLAMA_BASE_URL),
        "SERPER_API_KEY": bool(settings.SERPER_API_KEY),
        "HUNTER_API_KEY": bool(settings.HUNTER_API_KEY),
        "APOLLO_API_KEY": bool(settings.APOLLO_API_KEY),
        "CORESIGNAL_API_KEY": bool(settings.CORESIGNAL_API_KEY),
        "FAISS_INDEX_PATH": bool(settings.FAISS_INDEX_PATH),
    }

    return {"status": "ok" if checks["mongodb"] == "ok" and checks["redis"] == "ok" else "degraded", "checks": checks}
