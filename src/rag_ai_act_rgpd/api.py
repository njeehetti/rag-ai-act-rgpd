"""API HTTP. L'endpoint /agent arrivera en Phase 4."""

from typing import Annotated

import httpx
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field

from rag_ai_act_rgpd import __version__
from rag_ai_act_rgpd.rag import Rag

DISCLAIMER = (
    "Outil pédagogique, pas un conseil juridique. Seul le Journal officiel de l'UE fait foi."
)

app = FastAPI(title="rag-ai-act-rgpd", version=__version__)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class Citation(BaseModel):
    passage_id: str
    label: str
    url: str
    text: str


class Usage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int


class AskResponse(BaseModel):
    answer: str
    refused: bool
    grounded: bool = Field(description="au moins une citation vérifiée et aucune inventée")
    truncated: bool = Field(description="réponse ou prompt tronqué par le LLM")
    citations: list[Citation]
    invalid_citations: list[str]
    context_ids: list[str]
    retrieval_ms: float
    total_ms: float
    usage: Usage | None
    disclaimer: str = DISCLAIMER


def get_rag() -> Rag:
    from rag_ai_act_rgpd.service import build_rag  # charge le modèle d'embedding au 1er appel

    return build_rag()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/ask")
def ask(request: AskRequest, rag: Annotated[Rag, Depends(get_rag)]) -> AskResponse:
    try:
        result = rag.ask(request.question)
    except (httpx.HTTPError, psycopg.OperationalError, PoolTimeout) as exc:
        raise HTTPException(
            503, f"Service indisponible (base PostgreSQL ou Ollama) : {exc}"
        ) from exc
    answer = result.answer
    completion = answer.completion
    return AskResponse(
        answer=answer.answer,
        refused=answer.refused,
        grounded=answer.grounded,
        truncated=answer.truncated,
        citations=[
            Citation(passage_id=p.id, label=p.citation_label, url=p.url, text=p.text)
            for p in answer.citations
        ],
        invalid_citations=answer.invalid_citations,
        context_ids=answer.context_ids,
        retrieval_ms=result.retrieval_ms,
        total_ms=result.total_ms,
        usage=Usage(
            model=completion.model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
        if completion
        else None,
    )
