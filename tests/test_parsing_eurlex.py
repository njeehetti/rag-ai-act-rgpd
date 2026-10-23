"""Parsing EUR-Lex sur des extraits réels (voir tests/fixtures/)."""

import re
from pathlib import Path

import pytest

from rag_ai_act_rgpd.parsing.eurlex import (
    AIACT_CONSOLIDATED,
    AIACT_RECITALS,
    RGPD,
    parse_eurlex,
)
from rag_ai_act_rgpd.parsing.models import Passage

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def aiact() -> dict[str, Passage]:
    html = (FIXTURES / "aiact_consolidated.html").read_bytes()
    return {p.id: p for p in parse_eurlex(html, AIACT_CONSOLIDATED)}


@pytest.fixture(scope="module")
def recitals() -> dict[str, Passage]:
    html = (FIXTURES / "aiact_oj.html").read_bytes()
    return {p.id: p for p in parse_eurlex(html, AIACT_RECITALS)}


@pytest.fixture(scope="module")
def rgpd() -> dict[str, Passage]:
    html = (FIXTURES / "rgpd_oj.html").read_bytes()
    return {p.id: p for p in parse_eurlex(html, RGPD)}


class TestAiActArticle50:
    def test_seven_numbered_paragraphs(self, aiact: dict[str, Passage]) -> None:
        ids = [i for i in aiact if i.startswith("aiact:art50:")]
        assert ids == [f"aiact:art50:p{n}" for n in range(1, 8)]

    def test_unnumbered_subparagraph_belongs_to_previous_paragraph(
        self, aiact: dict[str, Passage]
    ) -> None:
        p4 = aiact["aiact:art50:p4"].text
        assert p4.startswith("Les déployeurs d’un système d’IA qui génère ou manipule des images")
        assert "textes publiés dans le but d’informer le public" in p4
        assert "textes publiés" not in aiact["aiact:art50:p5"].text

    def test_metadata_and_citation(self, aiact: dict[str, Passage]) -> None:
        p = aiact["aiact:art50:p1"]
        assert p.document_id == "aiact"
        assert p.kind == "paragraph"
        assert p.chapter == "IV"
        assert p.article == "50"
        assert p.paragraph == "1"
        assert p.heading == (
            "Obligations de transparence pour les fournisseurs et les déployeurs "
            "de certains systèmes d’IA"
        )
        assert p.citation_label == "[AI Act, art. 50 §1]"
        assert p.url.endswith("?uri=CELEX:02024R1689-20260727#art_50")

    def test_amendment_markers_are_metadata_not_text(self, aiact: dict[str, Passage]) -> None:
        assert aiact["aiact:art50:p7"].amended_by == ("32026R1744",)
        assert aiact["aiact:art50:p6"].amended_by == ()
        assert all("▼" not in p.text and "►" not in p.text for p in aiact.values())


class TestAiActOtherSubdivisions:
    def test_definitions_are_split_by_point(self, aiact: dict[str, Passage]) -> None:
        p = aiact["aiact:art3:pt1"]
        assert p.kind == "point"
        assert p.text.startswith("«système d’IA», un système automatisé")
        assert p.citation_label == "[AI Act, art. 3, point 1]"
        assert len([i for i in aiact if i.startswith("aiact:art3:pt")]) >= 68

    def test_inserted_article_uses_latin_suffix(self, aiact: dict[str, Passage]) -> None:
        art4bis = [p for p in aiact.values() if p.article == "4 bis"]
        assert art4bis
        assert all(p.id.startswith("aiact:art4bis") for p in art4bis)
        assert art4bis[0].citation_label.startswith("[AI Act, art. 4 bis")

    def test_annex_points(self, aiact: dict[str, Passage]) -> None:
        p = aiact["aiact:anxIII:pt1"]
        assert p.kind == "annex_point"
        assert p.text.startswith("Biométrie")
        assert "reconnaissance des émotions" in p.text
        assert p.citation_label == "[AI Act, annexe III, point 1]"
        assert len([i for i in aiact if i.startswith("aiact:anxIII:pt")]) == 8


def test_recitals(recitals: dict[str, Passage]) -> None:
    assert list(recitals) == ["aiact:rct1", "aiact:rct132"]
    p = recitals["aiact:rct1"]
    assert p.kind == "recital"
    assert p.text.startswith("L’objectif du présent règlement est d’améliorer")
    assert p.citation_label == "[AI Act, considérant 1]"


class TestRgpd:
    def test_paragraph_keeps_its_points(self, rgpd: dict[str, Passage]) -> None:
        p1 = rgpd["rgpd:art6:p1"].text
        assert p1.startswith("Le traitement n'est licite que si")
        assert "\na) la personne concernée a consenti" in p1
        assert "\nf) le traitement est nécessaire aux fins des intérêts légitimes" in p1
        assert rgpd["rgpd:art6:p1"].citation_label == "[RGPD, art. 6 §1]"

    def test_definitions(self, rgpd: dict[str, Passage]) -> None:
        assert rgpd["rgpd:art4:pt1"].text.startswith("«données à caractère personnel»")
        assert rgpd["rgpd:art4:pt1"].citation_label == "[RGPD, art. 4, point 1]"

    def test_article_7_paragraphs(self, rgpd: dict[str, Passage]) -> None:
        assert [i for i in rgpd if i.startswith("rgpd:art7:")] == [
            f"rgpd:art7:p{n}" for n in range(1, 5)
        ]


@pytest.mark.parametrize("name", ["aiact", "recitals", "rgpd"])
def test_ids_unique_texts_non_empty_and_parsing_deterministic(
    name: str, request: pytest.FixtureRequest
) -> None:
    passages: dict[str, Passage] = request.getfixturevalue(name)
    assert all(p.text.strip() for p in passages.values())
    assert all(re.fullmatch(r"[a-z]+:[A-Za-z0-9:]+", i) for i in passages), "id non normalisé"
    assert [p.position for p in passages.values()] == list(range(len(passages)))
    spec, fixture = {
        "aiact": (AIACT_CONSOLIDATED, "aiact_consolidated.html"),
        "recitals": (AIACT_RECITALS, "aiact_oj.html"),
        "rgpd": (RGPD, "rgpd_oj.html"),
    }[name]
    again = parse_eurlex((FIXTURES / fixture).read_bytes(), spec)
    assert [p.id for p in again] == list(passages)  # ids uniques (clés du dict) et stables
