"""Intégration avec un vrai PostgreSQL + pgvector (docker compose up db, ou service CI)."""

import os
import uuid
from collections.abc import Iterator

import numpy as np
import psycopg
import pytest

from rag_ai_act_rgpd import db
from rag_ai_act_rgpd.chunking import Chunk
from rag_ai_act_rgpd.parsing.models import Passage

ADMIN_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag")


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """Base jetable : créée pour le test, supprimée ensuite."""
    try:
        admin = psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL injoignable (docker compose up -d db)")
    name = f"test_{uuid.uuid4().hex[:8]}"
    admin.execute(f"CREATE DATABASE {name}")
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    connection = db.connect(url)
    try:
        yield connection
    finally:
        connection.close()
        admin.execute(f"DROP DATABASE {name}")
        admin.close()


def passage(pid: str) -> Passage:
    return Passage(
        id=pid,
        document_id="aiact",
        kind="paragraph",
        citation_label=f"[{pid}]",
        text=f"texte de {pid}",
        url="https://x",
        position=0,
        amended_by=("32026R1744",),
    )


def test_migrations_are_idempotent(conn: psycopg.Connection) -> None:
    assert db.migrate(conn) == ["001_corpus"]
    assert db.migrate(conn) == []


def test_round_trip_and_vector_search(conn: psycopg.Connection) -> None:
    db.migrate(conn)
    db.replace_passages(conn, [passage("aiact:art50:p1"), passage("aiact:art50:p2")])
    chunks = [
        Chunk("structural:0", "structural", "chunk A", ("aiact:art50:p1",), 0),
        Chunk("structural:1", "structural", "chunk B", ("aiact:art50:p2",), 1),
        Chunk("structural:2", "structural", "chunk C", ("aiact:art50:p1", "aiact:art50:p2"), 2),
    ]
    db.replace_chunks(conn, "structural", chunks)

    missing = db.texts_without_embedding(conn, "m", "structural")
    assert len(missing) == 3
    vectors = {"chunk A": [1.0, 0.0], "chunk B": [0.0, 1.0], "chunk C": [0.7, 0.7]}
    db.store_embeddings(conn, "m", [(h, np.array(vectors[t])) for h, t in missing])
    assert db.texts_without_embedding(conn, "m", "structural") == []
    assert len(db.texts_without_embedding(conn, "autre-modele", "structural")) == 3

    hits = db.search(conn, np.array([1.0, 0.1]), "m", "structural", k=2)
    assert [h.chunk_id for h in hits] == ["structural:0", "structural:2"]
    assert hits[0].passage_ids == ("aiact:art50:p1",)
    assert hits[0].score > hits[1].score

    stored = db.get_passages(conn, ["aiact:art50:p1"])
    assert stored["aiact:art50:p1"] == passage("aiact:art50:p1")


def test_replace_chunks_keeps_embedding_cache(conn: psycopg.Connection) -> None:
    db.migrate(conn)
    db.replace_passages(conn, [passage("aiact:art50:p1")])
    chunk = Chunk("fixed:0", "fixed", "même texte", ("aiact:art50:p1",), 0)
    db.replace_chunks(conn, "fixed", [chunk])
    [(digest, _)] = db.texts_without_embedding(conn, "m", "fixed")
    db.store_embeddings(conn, "m", [(digest, np.array([1.0, 0.0]))])
    db.replace_chunks(conn, "fixed", [chunk])  # réindexation : rien à réencoder
    assert db.texts_without_embedding(conn, "m", "fixed") == []
