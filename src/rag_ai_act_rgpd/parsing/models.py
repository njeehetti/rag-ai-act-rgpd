"""Modèle commun aux parsers : le passage, plus petite unité citable du corpus."""

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["paragraph", "point", "article", "recital", "annex_point", "annex", "section"]


@dataclass(frozen=True)
class Passage:
    """Plus petite unité citable du corpus.

    ``id`` est stable entre deux ingestions : le jeu d'évaluation s'y réfère.
    """

    id: str
    document_id: str
    kind: Kind
    citation_label: str
    text: str
    url: str
    position: int
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    paragraph: str | None = None
    point: str | None = None
    heading: str | None = None
    amended_by: tuple[str, ...] = field(default_factory=tuple)
    version_date: str | None = None
