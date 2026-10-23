"""Pipeline RAG : question → chunks proches → passages → réponse sourcée."""

import time
from dataclasses import dataclass

import psycopg

from rag_ai_act_rgpd import db
from rag_ai_act_rgpd.chunking import Chunk, Strategy, chunk_fixed, chunk_structural
from rag_ai_act_rgpd.embeddings import Embedder
from rag_ai_act_rgpd.generation import Answer, answer_question
from rag_ai_act_rgpd.llm import LLMClient
from rag_ai_act_rgpd.parsing.models import Passage

EMBED_BATCH = 64


@dataclass(frozen=True)
class RagResult:
    answer: Answer
    hits: list[db.Hit]
    retrieval_ms: float
    total_ms: float


class Rag:
    def __init__(
        self,
        conn: psycopg.Connection,
        embedder: Embedder,
        llm: LLMClient,
        strategy: Strategy = "structural",
        top_k_chunks: int = 10,
        max_passages: int = 8,
    ) -> None:
        self.conn = conn
        self.embedder = embedder
        self.llm = llm
        self.strategy = strategy
        self.top_k_chunks = top_k_chunks
        self.max_passages = max_passages

    def retrieve(self, question: str) -> tuple[list[db.Hit], list[Passage]]:
        """Chunks les plus proches, puis passages qu'ils recouvrent, dans l'ordre du rang."""
        query = self.embedder.embed_query(question)
        hits = db.search(self.conn, query, self.embedder.name, self.strategy, self.top_k_chunks)
        ordered_ids = list(dict.fromkeys(pid for hit in hits for pid in hit.passage_ids))
        ordered_ids = ordered_ids[: self.max_passages]
        by_id = db.get_passages(self.conn, ordered_ids)
        return hits, [by_id[pid] for pid in ordered_ids if pid in by_id]

    def ask(self, question: str) -> RagResult:
        start = time.perf_counter()
        hits, passages = self.retrieve(question)
        retrieval_ms = (time.perf_counter() - start) * 1000
        answer = answer_question(question, passages, self.llm)
        return RagResult(answer, hits, retrieval_ms, (time.perf_counter() - start) * 1000)


def index_corpus(
    conn: psycopg.Connection,
    passages: list[Passage],
    embedder: Embedder,
    strategies: tuple[Strategy, ...] = ("fixed", "structural"),
) -> dict[str, int]:
    """Charge passages et chunks, et n'encode que les textes absents du cache."""
    db.replace_passages(conn, passages)
    builders = {"fixed": chunk_fixed, "structural": chunk_structural}
    stats: dict[str, int] = {"passages": len(passages)}
    for strategy in strategies:
        chunks: list[Chunk] = builders[strategy](passages)
        db.replace_chunks(conn, strategy, chunks)
        missing = db.texts_without_embedding(conn, embedder.name, strategy)
        for i in range(0, len(missing), EMBED_BATCH):
            batch = missing[i : i + EMBED_BATCH]
            vectors = embedder.embed_documents([text for _, text in batch])
            db.store_embeddings(
                conn, embedder.name, [(h, v) for (h, _), v in zip(batch, vectors, strict=True)]
            )
        stats[f"{strategy}_chunks"] = len(chunks)
        stats[f"{strategy}_newly_embedded"] = len(missing)
    return stats
