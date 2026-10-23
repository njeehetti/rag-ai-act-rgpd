"""Parsing d'une fiche CNIL réelle (voir tests/fixtures/README.md)."""

from pathlib import Path

import pytest

from rag_ai_act_rgpd.parsing.cnil import parse_cnil
from rag_ai_act_rgpd.parsing.models import Passage

URL = "https://www.cnil.fr/fr/realiser-une-analyse-dimpact-si-necessaire"
PREFIX = "cnil:realiser-une-analyse-dimpact-si-necessaire:"


@pytest.fixture(scope="module")
def passages() -> dict[str, Passage]:
    html = (Path(__file__).parent / "fixtures" / "cnil_aipd_ia.html").read_bytes()
    return {p.id: p for p in parse_cnil(html, URL)}


def test_one_passage_per_subsection_with_stable_slug_ids(passages: dict[str, Passage]) -> None:
    assert f"{PREFIX}identifier-quand-une-aipd-est-necessaire" in passages
    assert f"{PREFIX}definir-le-perimetre-de-l-aipd" in passages
    assert all(i.startswith(PREFIX) for i in passages)


def test_metadata_and_citation(passages: dict[str, Passage]) -> None:
    p = passages[f"{PREFIX}identifier-quand-une-aipd-est-necessaire"]
    assert p.document_id == "cnil"
    assert p.kind == "section"
    assert p.chapter == "IA : Réaliser une analyse d’impact si nécessaire"
    assert p.section == "La réalisation d’une AIPD pour le développement de systèmes d’IA"
    assert p.version_date == "08 avril 2024"
    assert p.url == URL
    assert p.citation_label == (
        "[CNIL, IA : Réaliser une analyse d’impact si nécessaire, "
        "« Identifier quand une AIPD est nécessaire »]"
    )


def test_text_is_verbatim(passages: dict[str, Passage]) -> None:
    # Licence CC BY-ND : aucune réécriture du texte source.
    text = passages[f"{PREFIX}identifier-quand-une-aipd-est-necessaire"].text
    assert text.startswith(
        "Le développement de systèmes d’IA nécessite, dans certains cas, la réalisation "
        "d’une AIPD. Une AIPD est obligatoire si le traitement envisagé est susceptible "
        "d’engendrer un risque élevé pour les droits et libertés des personnes physiques "
        "(article 35 du RGPD)."
    )


def test_navigation_and_widgets_are_excluded(passages: dict[str, Passage]) -> None:
    for p in passages.values():
        assert "Ceci peut également vous intéresser" not in p.text
        assert "Déplier" not in p.text
        assert "08 avril 2024" not in p.text
