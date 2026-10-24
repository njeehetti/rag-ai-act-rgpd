"""Jeu d'évaluation : format, contrôles, découpage dev/test et gel.

Une ligne de ``eval/dataset.jsonl`` = une question. Les passages justificatifs sont des
identifiants de passages (jamais de chunks) : ils restent valables quelle que soit la stratégie
de découpage comparée en Phase 3.
"""

import hashlib
import json
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, get_args

from rag_ai_act_rgpd.parsing.models import Passage

QuestionType = Literal[
    "factuelle", "definition", "multi_articles", "multi_reglements", "hors_corpus", "cas_pratique"
]
Origin = Literal["njee", "proposee_validee"]
Status = Literal["draft", "validated", "rejected"]
Split = Literal["dev", "test"]

TYPES: tuple[QuestionType, ...] = get_args(QuestionType)
TARGETS: dict[str, int] = {
    "factuelle": 20,
    "definition": 10,
    "multi_articles": 12,
    "multi_reglements": 12,
    "hors_corpus": 10,
    "cas_pratique": 16,
}
DEV_SIZE = 15
SEED = 20261116


@dataclass
class Question:
    id: str
    question: str
    reference_answer: str
    passage_ids: list[str]
    type: QuestionType
    difficulty: int
    origin: Origin
    status: Status = "draft"
    split: Split | None = None
    notes: str = ""
    tags: list[str] = field(default_factory=list)


def load(path: Path) -> list[Question]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Question(**json.loads(line)) for line in lines if line.strip()]


def save(questions: Iterable[Question], path: Path) -> None:
    lines = [json.dumps(asdict(q), ensure_ascii=False) for q in questions]
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def check(questions: list[Question], corpus: dict[str, Passage] | None = None) -> list[str]:
    """Problèmes de forme (et de références si ``corpus`` est fourni) ; vide si tout va bien."""
    problems: list[str] = []
    for qid, n in Counter(q.id for q in questions).items():
        if n > 1:
            problems.append(f"{qid} : identifiant en double ({n} fois)")
    for q in questions:
        problems += [f"{q.id} : {p}" for p in _check_one(q, corpus)]
    return problems


def _check_one(q: Question, corpus: dict[str, Passage] | None) -> list[str]:
    out = []
    if q.type not in TYPES:
        out.append(f"type inconnu « {q.type} »")
    if q.difficulty not in (1, 2, 3):
        out.append(f"difficulté {q.difficulty} hors de 1-3")
    if q.origin not in get_args(Origin):
        out.append(f"origine inconnue « {q.origin} »")
    if q.status not in get_args(Status):
        out.append(f"statut inconnu « {q.status} »")
    if not q.question.strip() or not q.reference_answer.strip():
        out.append("question ou réponse de référence vide")
    if q.type == "hors_corpus" and q.passage_ids:
        out.append("une question hors corpus n'a pas de passage justificatif")
    if q.type != "hors_corpus" and not q.passage_ids:
        out.append("aucun passage justificatif")
    if q.type in ("multi_articles", "multi_reglements") and len(q.passage_ids) < 2:
        out.append("au moins deux passages attendus")
    if len(set(q.passage_ids)) != len(q.passage_ids):
        out.append("passage cité deux fois")
    if corpus is not None:
        unknown = [pid for pid in q.passage_ids if pid not in corpus]
        out += [f"passage inconnu {pid}" for pid in unknown]
        known = [corpus[pid] for pid in q.passage_ids if pid in corpus]
        # La doctrine CNIL compte comme une source distincte du RGPD qu'elle interprète.
        if q.type == "multi_reglements" and len({p.document_id for p in known}) < 2:
            out.append("multi-règlements : les passages viennent d'une seule source")
        if q.type == "multi_articles" and len({(p.document_id, p.article) for p in known}) < 2:
            out.append("multi-articles : les passages viennent d'un seul article")
    return out


def assign_splits(questions: list[Question], dev_size: int = DEV_SIZE, seed: int = SEED) -> None:
    """Tirage stratifié par type des questions validées, reproductible (graine fixe).

    Le quota de dev par type est proportionnel à son effectif (méthode du plus fort reste),
    pour que le dev ressemble au test sans le recouper.
    """
    kept = [q for q in questions if q.status == "validated"]
    by_type: dict[str, list[Question]] = defaultdict(list)
    for q in sorted(kept, key=lambda q: q.id):
        by_type[q.type].append(q)
    exact = {t: dev_size * len(qs) / len(kept) for t, qs in by_type.items()}
    quotas = {t: int(x) for t, x in exact.items()}
    by_remainder = sorted(exact, key=lambda t: (quotas[t] - exact[t], t))
    for t in by_remainder[: dev_size - sum(quotas.values())]:
        quotas[t] += 1
    rng = random.Random(seed)
    for t in sorted(by_type):
        group = by_type[t]
        dev = {q.id for q in rng.sample(group, quotas[t])}
        for q in group:
            q.split = "dev" if q.id in dev else "test"
    for q in questions:
        if q.status != "validated":
            q.split = None


def freeze_problems(questions: list[Question]) -> list[str]:
    """Conditions du gel : tout est relu, découpé, et la répartition cible est atteinte."""
    problems = [f"{q.id} : encore en brouillon" for q in questions if q.status == "draft"]
    kept = [q for q in questions if q.status == "validated"]
    problems += [f"{q.id} : pas de split" for q in kept if q.split is None]
    counts: Counter[str] = Counter(q.type for q in kept)
    problems += [
        f"{t} : {counts[t]} questions validées pour {n} visées"
        for t, n in TARGETS.items()
        if counts[t] < n
    ]
    return problems


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
