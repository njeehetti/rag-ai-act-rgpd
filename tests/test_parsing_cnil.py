"""Parsing d'une fiche CNIL réelle (voir tests/fixtures/README.md)."""

from pathlib import Path

import pytest

from rag_ai_act_rgpd.parsing.cnil import parse_cnil
from rag_ai_act_rgpd.parsing.models import Passage

URL = "https://www.cnil.fr/fr/realiser-une-analyse-dimpact-si-necessaire"
PREFIX = "cnil:realiser-une-analyse-dimpact-si-necessaire:"
SECTION = f"{PREFIX}la-realisation-d-une-aipd-pour-le-developpement-068f:"
IDENTIFIER = f"{SECTION}identifier-quand-une-aipd-est-necessaire"


@pytest.fixture(scope="module")
def passages() -> dict[str, Passage]:
    html = (Path(__file__).parent / "fixtures" / "cnil_aipd_ia.html").read_bytes()
    return {p.id: p for p in parse_cnil(html, URL)}


def test_ids_chain_parent_headings(passages: dict[str, Passage]) -> None:
    assert IDENTIFIER in passages
    assert f"{SECTION}definir-le-perimetre-de-l-aipd" in passages
    assert all(i.startswith(PREFIX) for i in passages)


def test_h4_subsections_are_separate_passages(passages: dict[str, Passage]) -> None:
    # Deux titres h4 au même début : l'empreinte du titre complet les distingue.
    h4 = [i for i in passages if i.startswith(f"{SECTION}definir-le-perimetre-de-l-aipd:")]
    assert len(h4) == 2
    assert len({passages[i].citation_label for i in h4}) == 2


def test_metadata_and_citation(passages: dict[str, Passage]) -> None:
    p = passages[IDENTIFIER]
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
    text = passages[IDENTIFIER].text
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


def _page(sections: str) -> bytes:
    return (
        "<html><head><meta charset='utf-8'></head><body><div class='ctn-gen'><h1>Titre</h1>"
        f"<p class='ctn-gen-auteur'>08 avril 2024</p>{sections}</div></body></html>"
    ).encode()


def _ids(sections: str) -> list[str]:
    return [p.id for p in parse_cnil(_page(sections), "https://www.cnil.fr/fr/page")]


def test_ids_do_not_depend_on_homonym_rank() -> None:
    a = "<h2>Étape A</h2><h3>Le principe</h3><p>a</p>"
    b = "<h2>Étape B</h2><h3>Le principe</h3><p>b</p>"
    new = "<h2>Étape 0</h2><h3>Le principe</h3><p>nouveau</p>"
    before, after = _ids(a + b), _ids(new + a + b)
    assert before == ["cnil:page:etape-a:le-principe", "cnil:page:etape-b:le-principe"]
    assert after[1:] == before


def test_homonym_headings_get_distinct_labels() -> None:
    html = _page(
        "<h2>Étape A</h2><h3>Le principe</h3><p>a</p><h2>Étape B</h2><h3>Le principe</h3><p>b</p>"
    )
    labels = [p.citation_label for p in parse_cnil(html, "https://www.cnil.fr/fr/page")]
    assert labels == [
        "[CNIL, Titre, « Étape A », « Le principe »]",
        "[CNIL, Titre, « Étape B », « Le principe »]",
    ]
