# Chimiini Translator API (FastAPI)

A Python API for the Chimiini (Bravanese) ↔ English translator. It does the
same thing as the website, but on the server: finds the relevant dictionary
entries and example sentences, builds the prompt, and calls the model.
Community entries (`"source": "user_added"`) take priority, same as the site.

```
client (website / mobile app)
        │  POST /translate {"text": "...", "direction": "b2e"}
        ▼
 FastAPI ── retrieval.py  →  dictionary matches + example sentences
        │── prompt.py     →  prompt (same wording as the website)
        └── llm.py        →  Anthropic API (key stays on the server)
```

It reads `lexicon.json` and `parallel_sentences.jsonl` from the repo root, so
it automatically uses whatever the submissions pipeline has merged.

## Project layout

| File | What it does |
|---|---|
| `app/main.py` | FastAPI app: routes, request/response models, dependencies |
| `app/retrieval.py` | The search index (port of `Index` in `index.html`) |
| `app/text.py` | Normalizing words: accents, hyphens, tokenizing |
| `app/prompt.py` + `grammar_notes.json` | Builds the prompt for the model |
| `app/llm.py` | Calls the Anthropic Messages API |
| `app/data.py` | Loads the data files |
| `app/config.py` | Settings from environment variables |
| `tests/` | pytest suite (59 tests) |

## Run it locally

From the `api/` folder:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

# Optional: only needed for /translate. Everything else works without it.
# Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_API_KEY=sk-ant-...

uvicorn app.main:app --reload
```

Then open **http://localhost:8000/docs**. FastAPI generates interactive
docs where you can try every endpoint from the browser.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Status plus how many entries and example pairs are loaded |
| POST | `/translate` | Translate a sentence (calls the model) |
| POST | `/context` | Dictionary retrieval only, no model call (free; good for debugging) |
| GET | `/lookup/{word}?direction=b2e` | Look up one word (`e2b` for English → Bravanese) |
| GET | `/examples?q=...&direction=b2e&limit=5` | Matching example sentences |

```bash
curl -X POST localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "inayo naani", "direction": "b2e"}'
```

`/translate` and `/context` take `"include_prompt": true` if you want to see
the exact prompt sent to the model.

## Settings (environment variables)

| Variable | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Required for `/translate` |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Same model as the Netlify function |
| `MAX_TOKENS` | `1000` | |
| `MAX_INPUT_CHARS` | `500` | Longer input is rejected with a 422 |
| `ALLOWED_ORIGINS` | the Netlify site + localhost | Comma-separated, for CORS |
| `DATA_DIR` | repo root | Where the two data files live |

## Tests

```bash
pytest
```

- `test_text.py`: the normalization helpers.
- `test_parity.py`: **the Python retrieval must match the website's
  JavaScript.** `tests/fixtures/js_parity.json` holds the results of
  running `index.html`'s own code on a small sample dataset. If you change
  the retrieval logic in `index.html`, change `retrieval.py` to match and
  regenerate the fixture from the repo root:
  `node api/tests/fixtures/generate_parity.js`
- `test_api.py`: every endpoint, with the model call faked (no API key or
  credits needed).
- `test_llm.py`: the Anthropic call, with HTTP faked.

## Deploy (Render)

Netlify can't run a Python server, so the API is hosted separately. The
`render.yaml` file in the repo root sets it up:

1. On render.com, choose **New → Blueprint** and connect the
   `bravanese-translator-app` repo.
2. When asked, set `ANTHROPIC_API_KEY`.
3. Render deploys on every push to `main`, so merged submissions show up
   automatically.

Check Render's current pricing: free instances may go to sleep when idle,
which makes the first request after a pause slow. Railway and Fly.io work
too; the start command is
`uvicorn app.main:app --host 0.0.0.0 --port $PORT` from the `api/` folder.

## Ideas for next steps

- **Rate limiting** (e.g. `slowapi`): `/translate` costs API credits, so
  limit requests per IP before sharing the URL widely.
- **Point the website at the API**, so visitors stop downloading 19 MB of
  data files. `index.html` would just call `POST /translate`.
- **React Native app (Expo)**: Translate, Look up and Contribute screens
  calling these endpoints.
- **`POST /submissions`**: move the contribute flow from Netlify Forms into
  the API.
