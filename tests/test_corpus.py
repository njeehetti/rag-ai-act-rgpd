"""Propriétés du corpus complet. Nécessite ``uv run rag fetch`` (data/raw n'est pas versionné)."""

import json
from collections import Counter
from pathlib import Path

import pytest

from rag_ai_act_rgpd.ingest import load_corpus
from rag_ai_act_rgpd.parsing.models import Passage

DATA = Path(__file__).parents[1] / "data"

pytestmark = pytest.mark.skipif(
    not (DATA / "raw").exists(), reason="corpus absent : lancer `uv run rag fetch`"
)


@pytest.fixture(scope="module")
def corpus() -> list[Passage]:
    return load_corpus(DATA / "raw", DATA / "manifest.json")


def test_expected_structure(corpus: list[Passage]) -> None:
    articles = Counter((p.document_id, p.article) for p in corpus if p.article)
    assert len([k for k in articles if k[0] == "aiact"]) == 119  # 113 + 6 insérés en 2026
    assert len([k for k in articles if k[0] == "rgpd"]) == 99
    recitals = Counter(p.document_id for p in corpus if p.kind == "recital")
    assert recitals == {"aiact": 180, "rgpd": 173}
    assert len({p.url for p in corpus if p.document_id == "cnil"}) == 26


def test_ids_are_unique_and_positions_global(corpus: list[Passage]) -> None:
    ids = [p.id for p in corpus]
    assert len(ids) == len(set(ids))
    assert [p.position for p in corpus] == list(range(len(corpus)))


def test_parsing_is_deterministic(corpus: list[Passage]) -> None:
    again = load_corpus(DATA / "raw", DATA / "manifest.json")
    assert [(p.id, p.text) for p in again] == [(p.id, p.text) for p in corpus]


def test_every_manifest_source_yields_passages(corpus: list[Passage]) -> None:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    used = " ".join({p.url for p in corpus})
    missing = [
        source_id
        for source_id, entry in manifest.items()
        if (source_id if entry["file"].startswith("eurlex/") else entry["url"]) not in used
    ]
    assert missing == []


def test_flop_threshold_keeps_its_exponent(corpus: list[Passage]) -> None:
    art51 = next(p for p in corpus if p.id == "aiact:art51:p2")
    assert art51.text.endswith("supérieure à 10^25.")
