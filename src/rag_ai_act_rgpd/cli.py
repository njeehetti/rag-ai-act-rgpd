"""Point d'entrée en ligne de commande : ``uv run rag <commande>``."""

import argparse
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

    args = parser.parse_args(argv)
    if args.command == "fetch":
        manifest = fetch_all(ALL_SOURCES, RAW_DIR, MANIFEST, force=args.force)
        print(f"{len(manifest)} sources dans {MANIFEST}")
    elif args.command == "verify":
        problems = verify(RAW_DIR, MANIFEST)
        print("\n".join(problems) or "data/raw/ conforme au manifeste")
        if problems:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
