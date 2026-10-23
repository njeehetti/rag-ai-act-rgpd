"""API HTTP. Les endpoints /ask et /agent arriveront en Phases 1 et 4."""

from fastapi import FastAPI

from rag_ai_act_rgpd import __version__

app = FastAPI(title="rag-ai-act-rgpd", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
