"""Parsing des pages de recommandations de la CNIL (cnil.fr).

Licence CC BY-ND 4.0 : le texte est conservé **verbatim**. On le découpe par sections,
sans le réécrire, et chaque passage garde l'URL source et la date de la page.

Gabarit des pages : un titre ``h1`` suivi de sa date et d'un chapô, puis des blocs
dépliables (``div.ctn-gen-ascenseur``) titrés en ``h2``, découpés en ``h3`` puis ``h4``.
Un passage = le texte sous le titre le plus fin (``h2``, ``h3`` ou ``h4``).

L'identifiant enchaîne les titres parents (``cnil:{page}:{h2}:{h3}``) : il ne dépend pas du
rang d'une section homonyme (« Le principe », « En pratique »), donc l'ajout d'une section
ailleurs dans la page ne le décale pas. Le jeu d'évaluation s'appuie dessus.
"""

import hashlib
import re
import unicodedata
from collections import Counter
from typing import cast

from lxml import html
from lxml.html import HtmlElement

from rag_ai_act_rgpd.parsing.models import Passage

DOCUMENT_ID = "cnil"
# Fin du contenu éditorial : tout ce qui suit est de la navigation.
_END_MARKERS = ("Ceci peut également vous intéresser", "Textes de référence", "Pour approfondir")
_NOISE = re.compile(r"\s*(Déplier|Replier)\s*$")
# Boutons, navigation entre fiches et mots-clés : du texte d'interface, pas de la doctrine.
_BOILERPLATE = re.compile(
    r"Imprimer l’article|Partager cette page par courriel|(Diminuer|Augmenter) la taille de la "
    r"police|Sommaire|Consulter la version PDF|#.+|< ?Fiche précédente : .+|Fiche suivante : .+>"
)
_TEXT_TAGS = {"p", "li", "td", "th", "blockquote", "dt", "dd"}
_LEVELS = {"h2": 0, "h3": 1, "h4": 2}
_SLUG_WORDS = 8
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

    # Chaque section : (titres h2/h3/h4 en cours, lignes de texte).
    sections: list[tuple[tuple[str, ...], list[str]]] = [((), [])]
    path: list[str] = []
    for el in _blocks(content_root):
        text = _clean(el.text_content())
        if not text or _BOILERPLATE.fullmatch(text):
            continue
        if el.tag in _LEVELS:
            if text.startswith(_END_MARKERS):
                break
            path = [*path[: _LEVELS[el.tag]], text]
            sections.append((tuple(path), []))
            continue
        if el.tag.startswith("h"):  # h5 et au-delà : intertitre gardé dans le texte
            text = f"{text} :"
        sections[-1][1].append(text)

    kept = [(_dedupe(titles), lines) for titles, lines in sections if lines]
    homonyms = Counter(titles[-1] for titles, _ in kept if titles)
    passages: list[Passage] = []
    seen: dict[str, int] = {}
    for titles, lines in kept:
        slug = ":".join(_slug(t) for t in titles) or "introduction"
        seen[slug] = seen.get(slug, 0) + 1
        if seen[slug] > 1:  # dernier recours : titres identiques à tous les niveaux
            slug = f"{slug}-{seen[slug]}"
        heading = titles[-1] if titles else None
        if heading and homonyms[heading] > 1 and len(titles) > 1:
            label_heading = f", « {titles[-2]} », « {heading} »"
        else:
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
                section=titles[0] if titles else None,
                heading=heading,
                version_date=date,
            )
        )
    return passages


def _dedupe(titles: tuple[str, ...]) -> tuple[str, ...]:
    """Retire un titre répété au niveau inférieur (``h3`` identique à son ``h2``)."""
    return tuple(t for i, t in enumerate(titles) if i == 0 or t != titles[i - 1])


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
    if len(words) <= _SLUG_WORDS:
        return "-".join(words)
    # Titre tronqué : l'empreinte du titre complet distingue deux titres au même début.
    digest = hashlib.sha1(" ".join(words).encode()).hexdigest()[:4]
    return "-".join([*words[:_SLUG_WORDS], digest])
