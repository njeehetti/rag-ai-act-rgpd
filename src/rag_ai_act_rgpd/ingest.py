"""Assemblage du corpus : sources brutes (data/raw) → passages citables."""

import dataclasses
import json
from pathlib import Path

from rag_ai_act_rgpd.parsing.cnil import parse_cnil
from rag_ai_act_rgpd.parsing.eurlex import (
    AIACT_CONSOLIDATED,
    AIACT_RECITALS,
    RGPD,
    DocumentSpec,
    parse_eurlex,
)
from rag_ai_act_rgpd.parsing.models import Passage

EURLEX_SPECS: list[DocumentSpec] = [AIACT_CONSOLIDATED, AIACT_RECITALS, RGPD]


def load_corpus(raw_dir: Path, manifest_path: Path) -> list[Passage]:
    """Parse toutes les sources du manifeste, dans un ordre fixe, positions globales."""
    manifest: dict[str, dict[str, str]] = json.loads(manifest_path.read_text(encoding="utf-8"))
    passages: list[Passage] = []
    for spec in EURLEX_SPECS:
        entry = manifest[spec.celex]
        passages += parse_eurlex((raw_dir / entry["file"]).read_bytes(), spec)
    for source_id in sorted(k for k, v in manifest.items() if v["file"].startswith("cnil/")):
        entry = manifest[source_id]
        passages += parse_cnil((raw_dir / entry["file"]).read_bytes(), entry["url"])
    return [dataclasses.replace(p, position=i) for i, p in enumerate(passages)]
