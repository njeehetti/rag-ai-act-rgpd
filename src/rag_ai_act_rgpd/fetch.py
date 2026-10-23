"""Téléchargement des sources dans data/raw/ et tenue du manifeste (URL, date, SHA-256)."""

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from rag_ai_act_rgpd.sources import Source

USER_AGENT = "rag-ai-act-rgpd/0.1 (student open-source project)"  # en-tête HTTP : ASCII
# Politesse envers cnil.fr : une requête par seconde au plus.
DELAY_BETWEEN_REQUESTS_S = 1.0


def fetch_all(
    sources: list[Source], raw_dir: Path, manifest_path: Path, force: bool = False
) -> dict[str, dict[str, str | int]]:
    manifest: dict[str, dict[str, str | int]] = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60
    ) as client:
        for source in sources:
            target = raw_dir / source.filename
            if target.exists() and source.id in manifest and not force:
                continue
            response = client.get(source.url, headers=source.headers)
            response.raise_for_status()
            if not response.content:
                raise RuntimeError(f"réponse vide pour {source.url}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            manifest[source.id] = {
                "url": source.url,
                "resolved_url": str(response.url),
                "file": source.filename,
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(response.content).hexdigest(),
                "bytes": len(response.content),
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            time.sleep(DELAY_BETWEEN_REQUESTS_S)
    return manifest


def verify(raw_dir: Path, manifest_path: Path) -> list[str]:
    """Liste les fichiers absents ou dont l'empreinte ne correspond plus au manifeste."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    for source_id, entry in manifest.items():
        path = raw_dir / str(entry["file"])
        if not path.exists():
            problems.append(f"{source_id} : fichier absent")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            problems.append(f"{source_id} : empreinte différente")
    return problems
