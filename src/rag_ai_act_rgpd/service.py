"""Assemblage du pipeline à partir de la configuration (partagé par l'API et la CLI)."""

from functools import lru_cache

from rag_ai_act_rgpd import db
from rag_ai_act_rgpd.config import get_settings
from rag_ai_act_rgpd.embeddings import SentenceTransformerEmbedder
from rag_ai_act_rgpd.llm import OllamaClient
from rag_ai_act_rgpd.rag import Rag


@lru_cache
def build_rag() -> Rag:
    s = get_settings()
    conn = db.connect(s.database_url)
    db.migrate(conn)
    return Rag(
        conn=conn,
        embedder=SentenceTransformerEmbedder(s.embedding_model),
        llm=OllamaClient(
            s.llm_model,
            s.ollama_url,
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            num_ctx=s.llm_num_ctx,
        ),
        strategy=s.chunk_strategy,
        top_k_chunks=s.top_k_chunks,
        max_passages=s.max_passages,
    )
