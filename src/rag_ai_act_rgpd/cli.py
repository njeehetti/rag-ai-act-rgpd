"""Point d'entrée en ligne de commande : ``uv run rag <commande>``."""

import argparse
import json
from pathlib import Path

from rag_ai_act_rgpd.fetch import fetch_all, verify
from rag_ai_act_rgpd.sources import ALL_SOURCES

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
MANIFEST = DATA_DIR / "manifest.json"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rag")
    commands = parser.add_subparsers(dest="command", required=True)

    fetch = commands.add_parser("fetch", help="télécharge les sources dans data/raw/")
    fetch.add_argument("--force", action="store_true", help="retélécharge tout")
    commands.add_parser("verify", help="vérifie data/raw/ contre le manifeste")
    commands.add_parser("index", help="parse, découpe et encode le corpus dans PostgreSQL")
    ask = commands.add_parser("ask", help="pose une question au RAG")
    ask.add_argument("question")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        manifest = fetch_all(ALL_SOURCES, RAW_DIR, MANIFEST, force=args.force)
        print(f"{len(manifest)} sources dans {MANIFEST}")
    elif args.command == "verify":
        problems = verify(RAW_DIR, MANIFEST)
        print("\n".join(problems) or "data/raw/ conforme au manifeste")
        if problems:
            raise SystemExit(1)
    elif args.command == "index":
        _index()
    elif args.command == "ask":
        _ask(args.question)


def _index() -> None:
    # Imports différés : torch et le modèle ne se chargent que pour ces commandes.
    from rag_ai_act_rgpd import db
    from rag_ai_act_rgpd.config import get_settings
    from rag_ai_act_rgpd.embeddings import SentenceTransformerEmbedder
    from rag_ai_act_rgpd.ingest import load_corpus
    from rag_ai_act_rgpd.rag import index_corpus

    settings = get_settings()
    conn = db.connect(settings.database_url)
    db.migrate(conn)
    stats = index_corpus(
        conn, load_corpus(RAW_DIR, MANIFEST), SentenceTransformerEmbedder(settings.embedding_model)
    )
    print(json.dumps(stats, indent=2))


def _ask(question: str) -> None:
    from rag_ai_act_rgpd.service import build_rag

    result = build_rag().ask(question)
    print(result.answer.answer)
    print("\nSources :")
    for p in result.answer.citations:
        print(f"  {p.citation_label} {p.url}")
    if result.answer.invalid_citations:
        print("Citations invalides (hors contexte) :", ", ".join(result.answer.invalid_citations))
    print(f"\n{result.total_ms:.0f} ms (recherche {result.retrieval_ms:.0f} ms)")


if __name__ == "__main__":
    main()
