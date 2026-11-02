"""Chimiini (Bravanese) Translator API.

Run locally:   uvicorn app.main:app --reload      (from the api/ folder)
Interactive docs: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import llm
from .config import Settings, get_settings
from .data import Dictionary, load_dictionary
from .prompt import build_prompt, lex_lines
from .retrieval import Context, is_community
from .text import normalize_key, strip_diacritics, tokenize

Direction = Literal["b2e", "e2b"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.dictionary = load_dictionary(settings.data_dir)
    yield


app = FastAPI(
    title="Chimiini Translator API",
    description="Translate between Chimiini (Bravanese) and English, grounded in a Chimiini dictionary and corpus. "
                "Community-contributed entries take priority over the original dictionary.",
    version="0.1.0",
    lifespan=lifespan,
)

_startup_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_startup_settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------- dependencies ----------

def get_dictionary(request: Request) -> Dictionary:
    return request.app.state.dictionary


def settings_dep(request: Request) -> Settings:
    return request.app.state.settings


Completer = Callable[[str, Settings], Awaitable[str]]


def get_completer() -> Completer:
    """The function that calls the model. Tests swap this out for a fake."""
    return llm.complete


# ---------- schemas ----------

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, examples=["inayo naani"])
    direction: Direction = Field("b2e", description="b2e = Bravanese to English, e2b = English to Bravanese")
    include_prompt: bool = Field(False, description="Also return the full prompt sent to the model")


class BravaneseOption(BaseModel):
    bravanese: str
    note: str = ""
    community: bool


class Match(BaseModel):
    token: str
    community: bool
    gloss: str | None = Field(None, description="b2e only: English meaning")
    note: str = ""
    bravanese: list[BravaneseOption] = Field(default_factory=list, description="e2b only: up to 3 Bravanese words")


class ExampleOut(BaseModel):
    source: str
    target: str
    score: float
    community: bool


class ContextOut(BaseModel):
    dictionary_matches: list[Match]
    unknown_words: list[str]
    examples: list[ExampleOut]
    dictionary_lines: list[str] = Field(description="The match lines exactly as the model sees them")


class ContextResponse(BaseModel):
    text: str
    direction: Direction
    context: ContextOut
    prompt: str | None = None


class TranslateResponse(ContextResponse):
    translation: str


class EntryOut(BaseModel):
    headword: str
    gloss: str
    pos: str | None = None
    noun_class: str | None = None
    plural_form: str | None = None
    past_tense: str | None = None
    community: bool
    examples: list[ExampleOut] = []


class LookupResponse(BaseModel):
    word: str
    direction: Direction
    best_match: Match | None = Field(None, description="The match the translator itself uses")
    entries: list[EntryOut] = Field(default_factory=list, description="b2e only: full lexicon entries for this headword")


# ---------- helpers ----------

def _check_text(text: str, settings: Settings) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(422, "text must not be empty")
    if len(text) > settings.max_input_chars:
        raise HTTPException(422, f"text is longer than {settings.max_input_chars} characters")
    return text


def _context_out(ctx: Context) -> ContextOut:
    return ContextOut(
        dictionary_matches=[
            Match(
                token=m.token, community=m.community, gloss=m.gloss, note=m.note,
                bravanese=[BravaneseOption(bravanese=h.bravanese, note=h.note, community=h.community) for h in m.bravanese],
            )
            for m in ctx.matches
        ],
        unknown_words=ctx.unknown,
        examples=[ExampleOut(source=e.source_text, target=e.target_text, score=round(e.score, 4), community=e.community) for e in ctx.examples],
        dictionary_lines=lex_lines(ctx),
    )


def _entry_out(e: dict) -> EntryOut:
    return EntryOut(
        headword=e.get("headword_original") or "",
        gloss=e.get("gloss") or "",
        pos=e.get("pos"),
        noun_class=e.get("noun_class"),
        plural_form=e.get("plural_form"),
        past_tense=e.get("past_tense"),
        community=is_community(e),
        examples=[
            ExampleOut(source=x.get("bravanese_original") or "", target=x.get("english") or "", score=1.0, community=is_community(e))
            for x in (e.get("examples") or [])[:3]
        ],
    )


# ---------- routes ----------

@app.get("/", include_in_schema=False)
def root():
    return {"name": "Chimiini Translator API", "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health(d: Dictionary = Depends(get_dictionary)):
    """Liveness check plus how much data is loaded."""
    return {"status": "ok", **d.stats}


@app.post("/context", response_model=ContextResponse, tags=["translate"])
def context(req: TranslateRequest, d: Dictionary = Depends(get_dictionary), s: Settings = Depends(settings_dep)):
    """Dictionary retrieval only (no model call, free). Shows what the model would be given."""
    text = _check_text(req.text, s)
    ctx = d.index.build_context(text, req.direction)
    return ContextResponse(text=text, direction=req.direction, context=_context_out(ctx),
                           prompt=build_prompt(text, ctx) if req.include_prompt else None)


@app.post("/translate", response_model=TranslateResponse, tags=["translate"])
async def translate(
    req: TranslateRequest,
    d: Dictionary = Depends(get_dictionary),
    s: Settings = Depends(settings_dep),
    complete: Completer = Depends(get_completer),
):
    """Translate a sentence using the dictionary context and the model."""
    text = _check_text(req.text, s)
    ctx = d.index.build_context(text, req.direction)
    prompt = build_prompt(text, ctx)
    try:
        translation = await complete(prompt, s)
    except llm.LLMError as e:
        raise HTTPException(e.status_code, str(e)) from e
    return TranslateResponse(text=text, direction=req.direction, translation=translation,
                             context=_context_out(ctx), prompt=prompt if req.include_prompt else None)


@app.get("/lookup/{word}", response_model=LookupResponse, tags=["dictionary"])
def lookup(word: str, direction: Direction = "b2e", d: Dictionary = Depends(get_dictionary)):
    """Look up a single word. b2e: Bravanese word -> English. e2b: English word -> Bravanese words."""
    if direction == "b2e":
        hit = d.index.lookup_bravanese(word)
        key = normalize_key(word)
        entries = [e for e in d.lexicon if normalize_key(e.get("headword_original") or "") == key]
        entries.sort(key=lambda e: not is_community(e))  # community entries first
        best = Match(token=word, community=hit.community, gloss=hit.gloss, note=hit.note) if hit else None
        return LookupResponse(word=word, direction=direction, best_match=best, entries=[_entry_out(e) for e in entries])
    hits = d.index.lookup_english(word)[:3]
    best = Match(token=word, community=hits[0].community,
                 bravanese=[BravaneseOption(bravanese=h.bravanese, note=h.note, community=h.community) for h in hits]) if hits else None
    return LookupResponse(word=word, direction=direction, best_match=best)


@app.get("/examples", response_model=list[ExampleOut], tags=["dictionary"])
def examples(
    q: str = Query(..., min_length=1, description="Words to match against example sentences"),
    direction: Direction = "b2e",
    limit: int = Query(5, ge=1, le=20),
    d: Dictionary = Depends(get_dictionary),
):
    """Example sentences from the corpus that share words with `q`, best first."""
    tokens = tokenize(strip_diacritics(q)) if direction == "b2e" else tokenize(q)
    return [ExampleOut(source=e.source_text, target=e.target_text, score=round(e.score, 4), community=e.community)
            for e in d.index.closest_examples(tokens, direction, limit)]
