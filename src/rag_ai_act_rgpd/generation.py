"""Génération d'une réponse sourcée à partir des passages récupérés.

Garde-fous :
- sans passage pertinent, l'assistant refuse **sans appeler le LLM** ;
- chaque citation de la réponse est confrontée aux passages fournis : une citation
  inventée est signalée dans ``invalid_citations`` (jamais présentée comme une source).
"""

import re
import unicodedata
from dataclasses import dataclass, field

from rag_ai_act_rgpd.llm import Completion, LLMClient, Message
from rag_ai_act_rgpd.parsing.models import Passage

REFUSAL = (
    "Je ne peux pas répondre à cette question à partir du corpus "
    "(AI Act, RGPD, recommandations de la CNIL)."
)

SYSTEM_PROMPT = f"""Tu es un assistant pédagogique sur l'AI Act, le RGPD et la doctrine de la CNIL.
Règles impératives :
1. Réponds uniquement à partir des extraits fournis, jamais de mémoire.
2. Après chaque affirmation, cite l'extrait qui la justifie en recopiant exactement sa référence entre crochets, par exemple [AI Act, art. 50 §1]. N'invente jamais de référence.
3. Si les extraits ne permettent pas de répondre, réponds exactement et uniquement : « {REFUSAL} »
4. Réponds en français, de façon claire et concise (5 à 10 phrases au plus).
Tu ne donnes pas de conseil juridique."""  # noqa: E501

_CITATION = re.compile(r"\[(?:AI Act|RGPD|CNIL)[^\[\]]*\]")


@dataclass(frozen=True)
class Answer:
    question: str
    answer: str
    refused: bool
    citations: list[Passage] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    context_ids: list[str] = field(default_factory=list)
    completion: Completion | None = None


def build_messages(question: str, passages: list[Passage]) -> list[Message]:
    excerpts = "\n\n".join(f"{p.citation_label}\n{p.text}" for p in passages)
    user = f"Extraits :\n\n{excerpts}\n\nQuestion : {question}"
    return [Message("system", SYSTEM_PROMPT), Message("user", user)]


def answer_question(question: str, passages: list[Passage], llm: LLMClient) -> Answer:
    if not passages:
        return Answer(question=question, answer=REFUSAL, refused=True)

    completion = llm.complete(build_messages(question, passages))
    text = completion.text
    context_ids = [p.id for p in passages]
    if _is_refusal(text):
        return Answer(question, REFUSAL, True, context_ids=context_ids, completion=completion)

    by_label = {_normalize(p.citation_label): p for p in passages}
    cited: dict[str, Passage] = {}
    invalid: list[str] = []
    for label in _CITATION.findall(text):
        passage = by_label.get(_normalize(label))
        if passage is None:
            invalid.append(label)
        else:
            cited.setdefault(passage.id, passage)
    return Answer(
        question=question,
        answer=text,
        refused=False,
        citations=list(cited.values()),
        invalid_citations=list(dict.fromkeys(invalid)),
        context_ids=context_ids,
        completion=completion,
    )


def _is_refusal(text: str) -> bool:
    return _normalize(REFUSAL)[:60] in _normalize(text)


def _normalize(text: str) -> str:
    """Tolère les variantes typographiques (’ vs ', espaces, guillemets) d'une citation."""
    text = unicodedata.normalize("NFKC", text).replace("’", "'").replace("«", "").replace("»", "")
    return " ".join(text.split()).strip(' «»"').lower()
