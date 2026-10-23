"""Parsing des pages de recommandations de la CNIL (cnil.fr).

Licence CC BY-ND 4.0 : le texte est conservé **verbatim**. On le découpe par sections,
sans le réécrire, et chaque passage garde l'URL source et la date de la page.

Gabarit des pages : un titre ``h1`` suivi de sa date et d'un chapô, puis des blocs
dépliables (``div.ctn-gen-ascenseur``) titrés en ``h2``, découpés en sous-sections ``h3``.
Un passage = une sous-section ``h3`` (ou une section ``h2`` sans sous-section).
"""

import re
import unicodedata
from typing import cast

from lxml import html
from lxml.html import HtmlElement

from rag_ai_act_rgpd.parsing.models import Passage

DOCUMENT_ID = "cnil"
# Fin du contenu éditorial : tout ce qui suit est de la navigation.
_END_MARKERS = ("Ceci peut également vous intéresser", "Textes de référence", "Pour approfondir")
_NOISE = re.compile(r"\s*(Déplier|Replier)\s*$")
_TEXT_TAGS = {"p", "li", "td", "th", "blockquote", "dt", "dd"}
_HEADINGS = {"h2", "h3"}
_DATE = re.compile(r"\d{1,2}(?:er)? \w+ \d{4}")
_DATE_CLASS = "ctn-gen-auteur"


def parse_cnil(content: bytes, url: str) -> list[Passage]:
    root = cast(HtmlElement, html.fromstring(content))
    title_el = next((cast(HtmlElement, el) for el in root.iter("h1")), None)
    if title_el is None:
        raise ValueError(f"pas de titre h1 : {url}")
    title = _clean(title_el.text_content())
    page_slug = url.rstrip("/").rsplit("/fr/", 1)[-1].replace("/", "--")

    content_root = next((el for el in root.find_class("ctn-gen") if el.tag == "div"), None)
    if content_root is None:
        raise ValueError(f"contenu introuvable : {url}")
    date = _page_date(content_root)

    sections: list[tuple[str | None, str | None, list[str]]] = [(None, None, [])]
    h2: str | None = None
    for el in _blocks(content_root):
        text = _clean(el.text_content())
        if not text:
            continue
        if el.tag in _HEADINGS:
            if text.startswith(_END_MARKERS):
                break
            if el.tag == "h2":
                h2 = text
                sections.append((h2, None, []))
            else:
                sections.append((h2, text, []))
            continue
        if el.tag.startswith("h"):  # h4 et au-delà : intertitre gardé dans le texte
            text = f"{text} :"
        sections[-1][2].append(text)

    passages: list[Passage] = []
    seen: dict[str, int] = {}
    for h2_title, h3_title, lines in sections:
        if not lines:
            continue
        heading = h3_title or h2_title
        slug = _slug(heading) if heading else "introduction"
        seen[slug] = seen.get(slug, 0) + 1
        if seen[slug] > 1:
            slug = f"{slug}-{seen[slug]}"
        label_heading = f", « {heading} »" if heading else ""
        passages.append(
            Passage(
                id=f"{DOCUMENT_ID}:{page_slug}:{slug}",
                document_id=DOCUMENT_ID,
                kind="section",
                citation_label=f"[CNIL, {title}{label_heading}]",
                text="\n".join(lines),
                url=url,
                position=len(passages),
                chapter=title,
                section=h2_title,
                heading=heading,
                version_date=date,
            )
        )
    return passages


def _blocks(root: HtmlElement) -> list[HtmlElement]:
    """Titres et blocs de texte de plus haut niveau, dans l'ordre du document.

    Un ``li`` contenant des ``p`` n'est pris qu'une fois (le plus externe), pour ne pas
    dupliquer le texte. Le titre ``h1`` et son bloc (date, boutons) sont ignorés : le chapô
    est repris séparément s'il est dans un ``p``.
    """
    out = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag
        if not (tag in _TEXT_TAGS or (tag.startswith("h") and tag[1:].isdigit())) or tag == "h1":
            continue
        if any(a.tag in _TEXT_TAGS for a in el.iterancestors()):
            continue
        if any("ctn-gen-titre" in (a.get("class") or "") for a in el.iterancestors()):
            continue
        if {"date", _DATE_CLASS} & set((el.get("class") or "").split()):
            continue
        out.append(el)
    return out


def _page_date(content_root: HtmlElement) -> str | None:
    """Date affichée sous le titre (``p.ctn-gen-auteur``), par ex. « 08 avril 2024 »."""
    for p in content_root.find_class(_DATE_CLASS):
        match = _DATE.search(p.text_content())
        if match:
            return match.group()
    return None


def _clean(text: str) -> str:
    return _NOISE.sub("", " ".join(text.split()))


def _slug(text: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", re.sub(r"[’']", " ", text)).encode("ascii", "ignore").decode()
    )
    words = re.findall(r"[a-z0-9]+", ascii_text.lower())
    return "-".join(words[:12])
