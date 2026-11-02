def test_health_reports_loaded_data(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["entries"] > 0 and body["example_pairs"] > 0
    assert body["community_entries"] >= 1


def test_translate_returns_model_output_and_context(client):
    res = client.post("/translate", json={"text": "Muke ndimi", "direction": "b2e"})
    assert res.status_code == 200
    body = res.json()
    assert body["translation"] == "**Translation:** What is your name?"
    assert body["context"]["dictionary_lines"][0].startswith("[community] muke")
    assert body["prompt"] is None
    # The prompt really was sent to the model, with the dictionary context in it.
    assert 'SENTENCE TO TRANSLATE: "Muke ndimi"' in client.model_calls[-1]
    assert "[community] muke" in client.model_calls[-1]


def test_translate_can_include_prompt(client):
    body = client.post("/translate", json={"text": "woman", "direction": "e2b", "include_prompt": True}).json()
    assert body["prompt"].startswith("You are a linguistic assistant helping translate English into Chimiini/Bravanese.")


def test_context_does_not_call_the_model(client):
    res = client.post("/context", json={"text": "xyzzy qqq"})
    assert res.status_code == 200
    assert res.json()["context"]["unknown_words"] == ["xyzzy", "qqq"]
    assert client.model_calls == []


def test_rejects_empty_and_too_long_text(client):
    assert client.post("/translate", json={"text": "   "}).status_code == 422
    assert client.post("/translate", json={"text": "a" * 501}).status_code == 422
    assert client.post("/translate", json={"text": "hi", "direction": "sideways"}).status_code == 422


def test_lookup_bravanese_puts_community_first(client):
    """The sample has a community entry for 'dhahamu' that conflicts with the dictionary's 'cold'."""
    body = client.get("/lookup/dhahamu").json()
    assert body["best_match"]["gloss"] == "TEST community override"
    assert body["best_match"]["community"] is True
    assert body["entries"][0]["community"] is True
    assert any(not e["community"] and e["gloss"].startswith("cold") for e in body["entries"])  # dictionary entry still listed


def test_lookup_english(client):
    body = client.get("/lookup/monday", params={"direction": "e2b"}).json()
    assert body["best_match"]["bravanese"][0]["bravanese"] == "Jimatatu"


def test_lookup_unknown_word(client):
    body = client.get("/lookup/xyzzy").json()
    assert body["best_match"] is None and body["entries"] == []


def test_examples_limit(client):
    body = client.get("/examples", params={"q": "muke", "limit": 2}).json()
    assert len(body) == 2
    assert body[0]["community"] is True


def test_translate_without_api_key_gives_clear_error():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        res = c.post("/translate", json={"text": "muke"})
    assert res.status_code == 500
    assert "ANTHROPIC_API_KEY" in res.json()["detail"]
