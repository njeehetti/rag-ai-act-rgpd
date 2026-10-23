"""Deux stratégies de découpage du corpus en chunks de recherche.

Les tailles sont en **mots**, pour rester indépendant du tokenizer du modèle
d'embedding (en français, 1 mot ≈ 1,4 token : 220 mots ≈ 300 tokens).

Chaque chunk garde la liste des passages qu'il recouvre : c'est ce qui permet
d'évaluer les deux stratégies sur les mêmes passages de référence.
"""

from dataclasses import dataclass
from itertools import groupby
from typing import Literal

from rag_ai_act_rgpd.parsing.models import Passage

Strategy = Literal["fixed", "structural"]

FIXED_SIZE = 220
FIXED_OVERLAP = 40
STRUCTURAL_MAX = 220
STRUCTURAL_OVERLAP = 40


@dataclass(frozen=True)
class Chunk:
    id: str
    strategy: Strategy
    text: str
    passage_ids: tuple[str, ...]
    position: int


def chunk_fixed(
    passages: list[Passage], size: int = FIXED_SIZE, overlap: int = FIXED_OVERLAP
) -> list[Chunk]:
    """Baseline : fenêtre glissante sur le texte brut, sans tenir compte de la structure.

    La fenêtre ne franchit jamais la frontière entre deux documents sources (même URL).
    """
    chunks: list[Chunk] = []
    for _, group in groupby(passages, key=lambda p: p.url.split("#")[0]):
        words: list[str] = []
        owners: list[str] = []  # passage d'origine de chaque mot
        for p in group:
            for word in p.text.split():
                words.append(word)
                owners.append(p.id)
        for start, end in _windows(len(words), size, overlap):
            chunks.append(
                Chunk(
                    id=f"fixed:{len(chunks)}",
                    strategy="fixed",
                    text=" ".join(words[start:end]),
                    passage_ids=tuple(dict.fromkeys(owners[start:end])),
                    position=len(chunks),
                )
            )
    return chunks


def chunk_structural(
    passages: list[Passage], max_words: int = STRUCTURAL_MAX, overlap: int = STRUCTURAL_OVERLAP
) -> list[Chunk]:
    """Un passage = un chunk, précédé de sa référence et de son titre.

    L'en-tête apporte au modèle d'embedding le contexte que le paragraphe seul n'a pas
    (« art. 50 — Obligations de transparence… »). Un passage trop long est redécoupé ;
    tous ses morceaux gardent le même identifiant de passage.
    """
    chunks: list[Chunk] = []
    for p in passages:
        header = " ".join(x for x in (p.citation_label, p.heading) if x)
        words = p.text.split()
        spans = (
            [(0, len(words))]
            if len(words) <= max_words
            else _windows(len(words), max_words, overlap)
        )
        for start, end in spans:
            body = p.text if (start, end) == (0, len(words)) else " ".join(words[start:end])
            chunks.append(
                Chunk(
                    id=f"structural:{len(chunks)}",
                    strategy="structural",
                    text=f"{header}\n{body}",
                    passage_ids=(p.id,),
                    position=len(chunks),
                )
            )
    return chunks


def _windows(n: int, size: int, overlap: int) -> list[tuple[int, int]]:
    if not 0 <= overlap < size:
        raise ValueError("il faut 0 <= overlap < size")
    if n == 0:
        return []
    step = size - overlap
    spans = []
    start = 0
    while True:
        end = min(start + size, n)
        spans.append((start, end))
        if end == n:
            return spans
        start += step
