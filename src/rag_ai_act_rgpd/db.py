"""Accès PostgreSQL + pgvector : migrations, chargement du corpus, recherche vectorielle."""

import dataclasses
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from rag_ai_act_rgpd.chunking import Chunk, Strategy
from rag_ai_act_rgpd.parsing.models import Passage

MIGRATIONS_DIR = Path(__file__).parents[2] / "db" / "migrations"

_PASSAGE_COLUMNS = [f.name for f in dataclasses.fields(Passage)]
_MIGRATION_LOCK = 4_242_001  # identifiant arbitraire du verrou consultatif


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    text: str
    passage_ids: tuple[str, ...]
    score: float


def connect(url: str) -> psycopg.Connection:
    """Connexion en autocommit : une lecture ne laisse jamais de transaction ouverte, et
    une erreur SQL ne bloque pas les requêtes suivantes. Les écritures ouvrent leur propre
    transaction (``conn.transaction()``)."""
    return psycopg.connect(url, autocommit=True, connect_timeout=5)


def pool(url: str, max_size: int = 4) -> ConnectionPool:
    """Pool pour l'API et l'UI (plusieurs threads) : reconnexion si la base a redémarré."""
    return ConnectionPool(
        url,
        min_size=1,
        max_size=max_size,
        kwargs={"autocommit": True, "connect_timeout": 5},
        configure=register_vector,
        check=ConnectionPool.check_connection,
    )


def migrate(conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Applique, dans l'ordre, les fichiers SQL pas encore appliqués.

    Le verrou consultatif évite que l'API et l'UI, lancées ensemble sur une base neuve,
    appliquent les mêmes migrations en parallèle.
    """
    applied = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(migrations_dir.glob("*.sql")):
            if path.stem in done:
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
            applied.append(path.stem)
    register_vector(conn)
    return applied


def replace_passages(conn: psycopg.Connection, passages: list[Passage]) -> None:
    columns = ", ".join(_PASSAGE_COLUMNS)
    placeholders = ", ".join(["%s"] * len(_PASSAGE_COLUMNS))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM passages")
        cur.executemany(
            f"INSERT INTO passages ({columns}) VALUES ({placeholders})",
            [
                tuple(list(v) if isinstance(v, tuple) else v for v in dataclasses.astuple(p))
                for p in passages
            ],
        )


def replace_chunks(conn: psycopg.Connection, strategy: Strategy, chunks: list[Chunk]) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM chunks WHERE strategy = %s", (strategy,))
        cur.executemany(
            "INSERT INTO chunks (id, strategy, text, text_sha256, passage_ids, position)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (c.id, c.strategy, c.text, sha256(c.text), list(c.passage_ids), c.position)
                for c in chunks
            ],
        )


def cached_digests(conn: psycopg.Connection, model: str) -> set[str]:
    """Empreintes des textes déjà encodés par ce modèle (cache d'embeddings)."""
    rows = conn.execute("SELECT text_sha256 FROM embeddings WHERE model = %s", (model,))
    return {r[0] for r in rows}


def store_embeddings(
    conn: psycopg.Connection, model: str, rows: list[tuple[str, np.ndarray]]
) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO embeddings (model, text_sha256, embedding) VALUES (%s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            [(model, digest, vector) for digest, vector in rows],
        )


def search(
    conn: psycopg.Connection, query: np.ndarray, model: str, strategy: Strategy, k: int
) -> list[Hit]:
    """k chunks les plus proches (distance cosinus) pour un modèle et une stratégie."""
    rows = conn.execute(
        "SELECT c.id, c.text, c.passage_ids, 1 - (e.embedding <=> %s) AS score"
        " FROM chunks c JOIN embeddings e"
        "   ON e.text_sha256 = c.text_sha256 AND e.model = %s"
        " WHERE c.strategy = %s"
        " ORDER BY e.embedding <=> %s, c.id"
        " LIMIT %s",
        (query, model, strategy, query, k),
    ).fetchall()
    return [Hit(r[0], r[1], tuple(r[2]), float(r[3])) for r in rows]


def get_passages(conn: psycopg.Connection, ids: list[str]) -> dict[str, Passage]:
    columns = ", ".join(_PASSAGE_COLUMNS)
    rows = conn.execute(f"SELECT {columns} FROM passages WHERE id = ANY(%s)", (ids,)).fetchall()
    passages = {}
    for row in rows:
        values = dict(zip(_PASSAGE_COLUMNS, row, strict=True))
        values["amended_by"] = tuple(values["amended_by"])
        passages[values["id"]] = Passage(**values)
    return passages


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
