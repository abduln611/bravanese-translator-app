import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_DIR = FIXTURES / "sample"

# Point the app at the small sample dataset before it is imported.
os.environ["DATA_DIR"] = str(SAMPLE_DIR)
os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture(scope="session")
def dictionary():
    from app.data import load_dictionary
    return load_dictionary(SAMPLE_DIR)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app, get_completer

    calls = []

    async def fake_complete(prompt, settings):
        calls.append(prompt)
        return "**Translation:** What is your name?"

    app.dependency_overrides[get_completer] = lambda: fake_complete
    with TestClient(app) as c:
        c.model_calls = calls
        yield c
    app.dependency_overrides.clear()
