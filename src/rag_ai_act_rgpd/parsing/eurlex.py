"""Parsing des règlements européens (XHTML servi par Cellar / EUR-Lex).

Deux dialectes HTML coexistent :
- le texte consolidé (classes ``norm``, ``no-parag``), où un paragraphe numéroté est un
  ``div.norm`` contenant un ``span.no-parag`` ;
- le Journal officiel original (classes ``oj-*``), où un paragraphe est un ``div`` dont
  l'id vaut ``AAA.PPP`` (article, paragraphe).

Les deux partagent les ancres ELI (``art_50``, ``cpt_IV``, ``cpt_III.sct_1``, ``rct_1``,
``anx_III``), sur lesquelles repose la structure. Les identifiants de passage sont dérivés
de la numérotation juridique, jamais des ids HTML aléatoires de la version consolidée.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from lxml import html
from lxml.html import HtmlElement

Kind = Literal["paragraph", "point", "article", "recital", "annex_point", "annex"]

EURLEX_URL = "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:{celex}"

# Un article sans paragraphes numérotés mais avec au moins ce nombre de points
# de premier niveau est traité comme une liste de définitions (art. 3 AI Act, art. 4 RGPD).
MIN_POINTS_FOR_DEFINITIONS = 10

LATIN_SUFFIXES = {
    "a": "bis",
    "b": "ter",
    "c": "quater",
    "d": "quinquies",
    "e": "sexies",
    "f": "septies",
}

_PARAGRAPH_ID = re.compile(r"^\d{3}\.(\d{3})$")
_LIST_MARKER = re.compile(r"^(\(?[0-9]{1,3}[a-z]?\)|\(?[a-z]{1,2}\)|\(?[ivx]{1,5}\)|[0-9]{1,3}\.)$")
_ANNEX_HEADING = re.compile(r"^(?:Section\s+)?([A-Z]|\d{1,2})(?:\.|\s*-|\s|$)")
_PARAGRAPH_NUMBER = re.compile(r"^(\d+)(?:\s*(bis|ter|quater|quinquies|sexies|septies))?\b")
_LEADING_NUMBER = re.compile(r"^\(?\d{1,3}[\.\)]\s+")
_AMENDMENT_CELEX = re.compile(r"celex/(\w+)$")
_MARKER_CHARS = re.compile(r"[▼►◄▲]\w*")
_SKIPPED_CLASSES = {
    "modref",
    "arrow",
    "no-parag",
    "superscript",
    "oj-super",
    "oj-note-tag",
    "title-article-norm",
    "stitle-article-norm",
    "oj-ti-art",
    "oj-sti-art",
    "title-annex-1",
    "title-annex-2",
    "oj-ti-grseq-1",
}
_BLOCK_TAGS = {"p", "div", "td", "tr", "table", "li", "br", "h1", "h2", "h3", "h4", "hr"}


@dataclass(frozen=True)
class DocumentSpec:
    id: str
    label: str
    celex: str
    kinds: frozenset[str]

    @property
    def url(self) -> str:
        return EURLEX_URL.format(celex=self.celex)


AIACT_CONSOLIDATED = DocumentSpec(
    id="aiact",
    label="AI Act",
    celex="02024R1689-20260727",
    kinds=frozenset({"article", "annex"}),
)
# La version consolidée ne reprend pas les considérants : ils viennent du JO original.
AIACT_RECITALS = DocumentSpec(
    id="aiact", label="AI Act", celex="32024R1689", kinds=frozenset({"recital"})
)
RGPD = DocumentSpec(
    id="rgpd", label="RGPD", celex="32016R0679", kinds=frozenset({"article", "recital"})
)


@dataclass(frozen=True)
class Passage:
    """Plus petite unité citable du corpus."""

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


@dataclass
class _Unit:
    """Passage en construction, avant numérotation."""

    key: str
    kind: Kind
    label: str
    anchor: str
    parts: list[str] = field(default_factory=list)
    amended_by: list[str] = field(default_factory=list)
    article: str | None = None
    paragraph: str | None = None
    point: str | None = None
    heading: str | None = None
    chapter: str | None = None
    section: str | None = None


def parse_eurlex(content: bytes, spec: DocumentSpec) -> list[Passage]:
    root = html.fromstring(content)
    units: list[_Unit] = []
    if "recital" in spec.kinds:
        units += _recitals(root, spec)
    if "article" in spec.kinds:
        for art in _top_level(root, "art_"):
            units += _article(art, spec)
    if "annex" in spec.kinds:
        for anx in _top_level(root, "anx_"):
            units += _annex(anx, spec)
    passages: list[Passage] = []
    for u in units:
        text = "\n".join(p for p in u.parts if p)
        if not text:
            continue
        passages.append(
            Passage(
                id=f"{spec.id}:{u.key}",
                document_id=spec.id,
                kind=u.kind,
                citation_label=f"[{spec.label}, {u.label}]",
                text=text,
                url=f"{spec.url}#{u.anchor}",
                position=len(passages),
                chapter=u.chapter,
                section=u.section,
                article=u.article,
                paragraph=u.paragraph,
                point=u.point,
                heading=u.heading,
                amended_by=tuple(dict.fromkeys(u.amended_by)),
            )
        )
    return passages


def _top_level(root: HtmlElement, prefix: str) -> list[HtmlElement]:
    """Subdivisions ``art_N`` / ``anx_N`` (sans les sous-ids comme ``art_50.tit_1``)."""
    return [
        el
        for el in root.iter()
        if isinstance(el.get("id"), str)
        and el.get("id").startswith(prefix)
        and "." not in el.get("id")
    ]


def _recitals(root: HtmlElement, spec: DocumentSpec) -> list[_Unit]:
    units = []
    for el in _top_level(root, "rct_"):
        number = el.get("id").removeprefix("rct_")
        lines = _lines(el)
        if lines and _LIST_MARKER.match(lines[0].split(" ", 1)[0]):
            lines[0] = _LEADING_NUMBER.sub("", lines[0])
        units.append(
            _Unit(
                key=f"rct{number}",
                kind="recital",
                label=f"considérant {number}",
                anchor=el.get("id"),
                parts=lines,
            )
        )
    return units


def _article(art: HtmlElement, spec: DocumentSpec) -> list[_Unit]:
    anchor = art.get("id")
    raw = anchor.removeprefix("art_")
    number = _article_number(raw)
    key = "art" + number.replace(" ", "")
    chapter, section = _chapter_and_section(art)
    heading = _heading(art)

    def unit(
        suffix: str, kind: Kind, label: str, paragraph: str | None = None, point: str | None = None
    ) -> _Unit:
        return _Unit(
            key=f"{key}{suffix}",
            kind=kind,
            label=f"art. {number}{label}",
            anchor=anchor,
            article=number,
            paragraph=paragraph,
            point=point,
            heading=heading,
            chapter=chapter,
            section=section,
        )

    paragraphs: list[_Unit] = []
    points: list[_Unit] = []
    loose: list[str] = []  # texte hors paragraphe numéroté
    amended: str | None = None
    current: _Unit | None = None

    for child in art:
        if child.get("class") == "modref":
            amended = _amendment(child, spec)
            continue
        if _is_title(child):
            continue
        number_para = _paragraph_number(child)
        if number_para is not None:
            current = unit(
                f":p{number_para.replace(' ', '')}",
                "paragraph",
                f" §{number_para}",
                paragraph=number_para,
            )
            paragraphs.append(current)
            text = _lines(child)
            if text:
                text[0] = _LEADING_NUMBER.sub("", text[0])
            current.parts += text
        elif current is not None:
            current.parts += _lines(child)
        else:
            marker = _list_item_marker(child)
            if marker is not None:
                body = _lines(child)
                if body and body[0].startswith(marker):
                    body[0] = body[0][len(marker) :].strip()
                point = marker.strip("().")
                points.append(
                    unit(f":pt{point.replace(' ', '')}", "point", f", point {point}", point=point)
                )
                points[-1].parts = body
            else:
                loose += _lines(child)
            continue
        if amended:
            current.amended_by.append(amended)

    if paragraphs:
        if loose:  # chapeau éventuel avant le §1
            paragraphs[0].parts[:0] = loose
        return paragraphs
    if len(points) >= MIN_POINTS_FOR_DEFINITIONS:
        return points
    whole = unit("", "article", "")
    whole.parts = loose + [
        f"{p.point}) {line}" if i == 0 else line for p in points for i, line in enumerate(p.parts)
    ]
    if amended:
        whole.amended_by.append(amended)
    return [whole]


def _annex(anx: HtmlElement, spec: DocumentSpec) -> list[_Unit]:
    """Découpe une annexe selon la première règle qui s'applique :

    1. intertitres numérotés (« 3. Système de gestion… », « Section A ») → un passage chacun ;
    2. points de premier niveau aux marqueurs uniques (annexe III) → un passage chacun ;
    3. sinon (tirets, numérotation qui recommence) → l'annexe entière.
    """
    anchor = anx.get("id")
    number = anchor.removeprefix("anx_")
    children = [c for c in anx if not _is_title(c) and c.get("class") != "modref"]

    def unit(key: str, kind: Kind, label: str, point: str | None = None) -> _Unit:
        return _Unit(
            key=f"anx{number}{key}",
            kind=kind,
            label=f"annexe {number}{label}",
            anchor=anchor,
            point=point,
        )

    intro = unit(":intro", "annex", "")
    sections: list[_Unit] = []
    for child in children:
        heading = _annex_heading_number(child)
        if heading is not None:
            sections.append(
                unit(f":pt{heading.replace(' ', '')}", "annex_point", f", point {heading}", heading)
            )
        (sections[-1] if sections else intro).parts += _lines(child)
    if sections and len({s.key for s in sections}) == len(sections):
        return ([intro] if intro.parts else []) + sections

    intro = unit(":intro", "annex", "")
    points: list[_Unit] = []
    for child in children:
        marker = _list_item_marker(child)
        if marker is not None:
            point = marker.strip("().")
            body = _lines(child)
            if body and body[0].startswith(marker):
                body[0] = body[0][len(marker) :].strip()
            points.append(
                unit(f":pt{point.replace(' ', '')}", "annex_point", f", point {point}", point)
            )
            points[-1].parts = body
        else:
            (points[-1] if points else intro).parts += _lines(child)
    if (
        points
        and len({p.key for p in points}) == len(points)
        and _LIST_MARKER.match(f"{points[0].point})")
    ):
        return ([intro] if intro.parts else []) + points

    whole = unit("", "annex", "")
    for child in children:
        whole.parts += _lines(child)
    return [whole]


def _annex_heading_number(el: HtmlElement) -> str | None:
    if el.get("class") != "title-gr-seq-level-1":
        return None
    match = _ANNEX_HEADING.match(" ".join(el.text_content().split()))
    return match.group(1) if match else None


def _article_number(raw: str) -> str:
    match = re.fullmatch(r"(\d+)([a-z]?)", raw)
    if not match:
        raise ValueError(f"numéro d'article inattendu : {raw!r}")
    digits, suffix = match.groups()
    return f"{digits} {LATIN_SUFFIXES[suffix]}" if suffix else digits


def _chapter_and_section(el: HtmlElement) -> tuple[str | None, str | None]:
    for ancestor in el.iterancestors():
        match = re.fullmatch(r"cpt_([IVXLC]+)(?:\.sct_(\d+))?", ancestor.get("id") or "")
        if match:
            # Une section est imbriquée dans son chapitre : le premier ancêtre trouvé suffit.
            return match.group(1), match.group(2)
    return None, None


def _heading(art: HtmlElement) -> str | None:
    titles = [el for el in art if (el.get("id") or "").endswith(".tit_1")]
    return " ".join(titles[0].text_content().split()) if titles else None


def _is_title(el: HtmlElement) -> bool:
    classes = set((el.get("class") or "").split())
    return (
        bool(classes & _SKIPPED_CLASSES)
        or (el.get("id") or "").endswith(".tit_1")
        or (el.tag in {"p"} and not "".join(el.itertext()).strip())
    )


def _paragraph_number(el: HtmlElement) -> str | None:
    """Numéro de paragraphe (« 1 », « 1 bis ») si ``el`` ouvre un paragraphe numéroté."""
    match = _PARAGRAPH_ID.match(el.get("id") or "")
    if match:
        return str(int(match.group(1)))
    if "norm" in (el.get("class") or "").split() and el.tag == "div":
        spans = [s for s in el if s.tag == "span" and s.get("class") == "no-parag"]
        if spans:
            number = _PARAGRAPH_NUMBER.match(" ".join(spans[0].text_content().split()))
            if number:
                return " ".join(g for g in number.groups() if g)
    return None


def _list_item_marker(el: HtmlElement) -> str | None:
    """Marqueur (« 1) », « a) ») d'un élément de liste de premier niveau, sinon None."""
    if "grid-container" in (el.get("class") or "").split():
        column = el.find_class("grid-list-column-1")
        return str(column[0].text_content()).strip() if column else None
    if el.tag == "table":
        cells = el.findall(".//td")
        if cells:
            marker = str(cells[0].text_content()).strip()
            if _LIST_MARKER.match(marker):
                return marker
    return None


def _amendment(modref: HtmlElement, spec: DocumentSpec) -> str | None:
    """``▼M1`` ouvre une zone modifiée par l'acte lié ; ``▼B`` revient au texte de base."""
    link = modref.find(".//a")
    if link is None:
        return None
    match = _AMENDMENT_CELEX.search(link.get("href") or "")
    if not match or link.text_content().strip().endswith("B"):
        return None
    return match.group(1)


def _lines(el: HtmlElement) -> list[str]:
    """Texte d'un élément, une ligne par bloc, marqueurs de liste recollés à leur texte."""
    chunks: list[str] = []
    _collect(el, chunks)
    lines = [" ".join(_MARKER_CHARS.sub("", line).split()) for line in "".join(chunks).split("\n")]
    lines = [line for line in lines if line]
    merged: list[str] = []
    for line in lines:
        if merged and _LIST_MARKER.match(merged[-1]):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _collect(el: HtmlElement, out: list[str]) -> None:
    if set((el.get("class") or "").split()) & _SKIPPED_CLASSES:
        if el.tail:
            out.append(el.tail)
        return
    block = el.tag in _BLOCK_TAGS
    if block:
        out.append("\n")
    if el.text:
        out.append(el.text)
    for child in el:
        _collect(child, out)
    if block:
        out.append("\n")
    if el.tail:
        out.append(el.tail)


def iter_passages(*parsed: list[Passage]) -> Iterator[Passage]:
    """Concatène plusieurs parsings en renumérotant les positions globalement."""
    position = 0
    for passages in parsed:
        for p in passages:
            yield Passage(**{**p.__dict__, "position": position})
            position += 1
