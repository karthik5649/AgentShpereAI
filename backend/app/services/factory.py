from app.core.config import get_settings
from app.services.apollo_service import ApolloService
from app.services.crunchbase_service import CrunchbaseService
from app.services.hunter_service import HunterService
from app.services.mocks.mock_apollo_service import MockApolloService
from app.services.mocks.mock_crunchbase_service import MockCrunchbaseService
from app.services.mocks.mock_hunter_service import MockHunterService
from app.services.mocks.mock_serper_service import MockSerperService
from app.services.provider_tracker import provider_tracker
from app.services.serper_service import SerperService


def get_serper_service(api_key: str | None = None):
    settings = get_settings()
    key = api_key or getattr(settings, "SERPER_API_KEY", None)
    if getattr(settings, "MOCK_MODE", True) or not key or not provider_tracker.is_available("serper"):
        return MockSerperService(api_key=key)
    return SerperService(api_key=key)


def get_crunchbase_service(api_key: str | None = None):
    settings = get_settings()
    key = api_key or getattr(settings, "CRUNCHBASE_API_KEY", None)
    if getattr(settings, "MOCK_MODE", True) or not key or not provider_tracker.is_available("crunchbase"):
        return MockCrunchbaseService(api_key=key)
    return CrunchbaseService(api_key=key)


def get_hunter_service(api_key: str | None = None):
    settings = get_settings()
    key = api_key or getattr(settings, "HUNTER_API_KEY", None)
    if getattr(settings, "MOCK_MODE", True) or not key or not provider_tracker.is_available("hunter"):
        return MockHunterService(api_key=key)
    return HunterService(api_key=key)


def get_apollo_service(api_key: str | None = None):
    settings = get_settings()
    key = api_key or getattr(settings, "APOLLO_API_KEY", None)
    if getattr(settings, "MOCK_MODE", True) or not key or not provider_tracker.is_available("apollo"):
        return MockApolloService(api_key=key)
    return ApolloService(api_key=key)
