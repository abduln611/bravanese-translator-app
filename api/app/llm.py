"""Calls the Anthropic Messages API. The API key only ever lives on the server."""
import httpx

from .config import Settings

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class LLMError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


async def complete(prompt: str, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Send the prompt and return the model's text. `transport` lets tests fake the HTTP call."""
    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY is not set on the server.", 500)
    try:
        async with httpx.AsyncClient(timeout=60, transport=transport) as client:
            res = await client.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": settings.max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the model API: {e}") from e

    data = res.json() if res.content else {}
    if res.status_code != 200:
        msg = (data.get("error") or {}).get("message") or f"Model API returned {res.status_code}"
        raise LLMError(msg, 502)
    text = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise LLMError("The model returned no text.")
    return text
