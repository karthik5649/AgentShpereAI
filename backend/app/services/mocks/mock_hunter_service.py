from typing import Any


class MockHunterService:
    """Mock Hunter service returning plausible email addresses and confidence scores."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or "mock_hunter_key"

    async def find_email(self, domain: str, first_name: str, last_name: str) -> dict[str, Any]:
        if not domain or not first_name:
            return {"email": None, "confidence": 0, "sources": []}

        clean_first = first_name.strip().lower()
        clean_last = last_name.strip().lower() if last_name else ""
        clean_domain = domain.strip().lower().removeprefix("http://").removeprefix("https://").removeprefix("www.")

        email = f"{clean_first}.{clean_last}@{clean_domain}" if clean_last else f"{clean_first}@{clean_domain}"

        return {
            "email": email,
            "confidence": 0.94,
            "sources": [
                {"domain": clean_domain, "uri": f"https://{clean_domain}/about", "extracted_on": "2024-02-10"},
                {"domain": clean_domain, "uri": f"https://{clean_domain}/team", "extracted_on": "2024-03-01"},
            ],
        }
