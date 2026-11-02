import asyncio

import httpx
import pytest

from app.config import get_settings
from app.llm import LLMError, complete


def run(handler, key="test-key"):
    settings = get_settings()
    settings = type(settings)(**{**settings.__dict__, "anthropic_api_key": key})
    return asyncio.run(complete("hello", settings, transport=httpx.MockTransport(handler)))


def test_returns_text_and_sends_expected_request():
    seen = {}

    def handler(request):
        seen["key"] = request.headers["x-api-key"]
        seen["body"] = request.read()
        return httpx.Response(200, json={"content": [{"type": "text", "text": "What is your name?"}]})

    assert run(handler) == "What is your name?"
    assert seen["key"] == "test-key"
    assert b'"content":"hello"' in seen["body"].replace(b" ", b"")


def test_api_error_is_reported():
    def handler(request):
        return httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})

    with pytest.raises(LLMError, match="invalid x-api-key"):
        run(handler)


def test_missing_key():
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        run(lambda r: httpx.Response(200), key=None)
