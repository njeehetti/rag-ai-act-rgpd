"""Pipeline RAG : question → chunks proches → passages → réponse sourcée."""

import dataclasses
import time
from dataclasses import dataclass

import psycopg
from psycopg_pool import ConnectionPool

from rag_ai_act_rgpd import db
from rag_ai_act_rgpd.chunking import Chunk, Strategy, chunk_fixed, chunk_structural
from rag_ai_act_rgpd.embeddings import Embedder
from rag_ai_act_rgpd.generation import Answer, answer_question
from rag_ai_act_rgpd.llm import LLMClient
from rag_ai_act_rgpd.parsing.models import Passage

EMBED_BATCH = 64
TRUNCATED = " […]"


@dataclass(frozen=True)
class RagResult:
    answer: Answer
    hits: list[db.Hit]
    retrieval_ms: float
    total_ms: float


class Rag:
    def __init__(
        self,
        pool: ConnectionPool,
        embedder: Embedder,
        llm: LLMClient,
        strategy: Strategy = "structural",
        top_k_chunks: int = 10,
        max_passages: int = 8,
        max_context_chars: int = 12_000,
    ) -> None:
        self.pool = pool
        self.embedder = embedder
        self.llm = llm
        self.strategy = strategy
        self.top_k_chunks = top_k_chunks
        self.max_passages = max_passages
        self.max_context_chars = max_context_chars

    def retrieve(self, question: str) -> tuple[list[db.Hit], list[Passage]]:
        """Chunks les plus proches, puis passages qu'ils recouvrent, dans l'ordre du rang."""
        query = self.embedder.embed_query(question)
        with self.pool.connection() as conn:
            hits = db.search(conn, query, self.embedder.name, self.strategy, self.top_k_chunks)
            ordered_ids = list(dict.fromkeys(pid for hit in hits for pid in hit.passage_ids))
            by_id = db.get_passages(conn, ordered_ids[: self.max_passages])
        passages = [by_id[pid] for pid in ordered_ids if pid in by_id]
        return hits, fit_to_budget(passages, self.max_context_chars)

    def ask(self, question: str) -> RagResult:
        start = time.perf_counter()
        hits, passages = self.retrieve(question)
        retrieval_ms = (time.perf_counter() - start) * 1000
        answer = answer_question(question, passages, self.llm)
        return RagResult(answer, hits, retrieval_ms, (time.perf_counter() - start) * 1000)


def fit_to_budget(passages: list[Passage], max_chars: int) -> list[Passage]:
    """Passages, par rang, tant qu'ils tiennent dans le budget du prompt.

    Sans plafond, quelques sections CNIL très longues (jusqu'à 27 000 caractères) feraient
    dépasser la fenêtre du LLM, qu'Ollama tronque sans erreur. Un passage trop long est
    écarté au profit des suivants, sauf le premier (le plus pertinent), tronqué.
    """
    kept: list[Passage] = []
    used = 0
    for p in passages:
        if used + len(p.text) <= max_chars:
            kept.append(p)
            used += len(p.text)
        elif not kept:
            cut = max_chars - len(TRUNCATED)
            kept.append(dataclasses.replace(p, text=p.text[:cut] + TRUNCATED))
            used = max_chars
    return kept


def index_corpus(
    conn: psycopg.Connection,
    passages: list[Passage],
    embedder: Embedder,
    strategies: tuple[Strategy, ...] = ("fixed", "structural"),
) -> dict[str, int]:
    """Charge passages et chunks, et n'encode que les textes absents du cache.

    Les embeddings sont calculés d'abord, puis passages et chunks sont remplacés dans une
    seule transaction : une requête concurrente voit l'ancien index ou le nouveau, jamais
    des tables vides ou des chunks sans embedding.
    """
    builders = {"fixed": chunk_fixed, "structural": chunk_structural}
    stats: dict[str, int] = {"passages": len(passages)}
    all_chunks: dict[Strategy, list[Chunk]] = {s: builders[s](passages) for s in strategies}
    for strategy, chunks in all_chunks.items():
        known = db.cached_digests(conn, embedder.name)
        texts = {db.sha256(c.text): c.text for c in chunks}
        missing = sorted((h, t) for h, t in texts.items() if h not in known)
        for i in range(0, len(missing), EMBED_BATCH):
            batch = missing[i : i + EMBED_BATCH]
            vectors = embedder.embed_documents([text for _, text in batch])
            db.store_embeddings(
                conn, embedder.name, [(h, v) for (h, _), v in zip(batch, vectors, strict=True)]
            )
        stats[f"{strategy}_chunks"] = len(chunks)
        stats[f"{strategy}_newly_embedded"] = len(missing)
    with conn.transaction():
        db.replace_passages(conn, passages)
        for strategy, chunks in all_chunks.items():
            db.replace_chunks(conn, strategy, chunks)
    return stats
