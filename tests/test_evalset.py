from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from rag_ai_act_rgpd import evalset
from rag_ai_act_rgpd.evalset import Question
from rag_ai_act_rgpd.parsing.models import Passage

EVAL = Path(__file__).parents[1] / "eval"


def question(qid: str = "q001", **kw: object) -> Question:
    fields: dict[str, object] = {
        "id": qid, "question": "Qu'est-ce qu'un fournisseur ?", "reference_answer": "…",
        "passage_ids": ["aiact:art3:pt3"], "type": "definition", "difficulty": 1,
        "origin": "proposee_validee",
    }  # fmt: skip
    return Question(**(fields | kw))  # type: ignore[arg-type]


def passage(pid: str, document_id: str, article: str | None) -> Passage:
    return Passage(
        id=pid, document_id=document_id, kind="paragraph", citation_label=f"[{pid}]",
        text="…", url="https://x", position=0, article=article,
    )  # fmt: skip


CORPUS = {
    p.id: p
    for p in [
        passage("aiact:art3:pt3", "aiact", "3"),
        passage("aiact:art6:p2", "aiact", "6"),
        passage("aiact:art6:p3", "aiact", "6"),
        passage("rgpd:art22:p1", "rgpd", "22"),
    ]
}


def test_well_formed_question_has_no_problem() -> None:
    assert evalset.check([question()], CORPUS) == []


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    qs = [question("q001"), question("q002", question="Définition « d'IA » ?", tags=["banque"])]
    evalset.save(qs, path)
    assert evalset.load(path) == qs
    assert b"\r\n" not in path.read_bytes()
    assert "« d'IA »" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({"passage_ids": ["aiact:art99:p1"]}, "passage inconnu aiact:art99:p1"),
        ({"type": "hors_corpus"}, "pas de passage justificatif"),
        ({"passage_ids": []}, "aucun passage justificatif"),
        ({"difficulty": 4}, "difficulté 4"),
        ({"type": "multi_articles"}, "au moins deux passages"),
        (
            {"type": "multi_articles", "passage_ids": ["aiact:art6:p2", "aiact:art6:p3"]},
            "un seul article",
        ),
        (
            {"type": "multi_reglements", "passage_ids": ["aiact:art3:pt3", "aiact:art6:p2"]},
            "une seule source",
        ),
        ({"reference_answer": " "}, "vide"),
    ],
)
def test_malformed_question_is_reported(kw: dict[str, Any], expected: str) -> None:
    problems = evalset.check([question(**kw)], CORPUS)
    assert any(expected in p for p in problems), problems


def test_duplicate_ids_are_reported() -> None:
    assert evalset.check([question(), question()]) == ["q001 : identifiant en double (2 fois)"]


def test_cross_regulation_question_is_accepted() -> None:
    q = question(type="multi_reglements", passage_ids=["aiact:art6:p2", "rgpd:art22:p1"])
    assert evalset.check([q], CORPUS) == []


def validated_set() -> list[Question]:
    qs = []
    for t, n in evalset.TARGETS.items():
        for i in range(n):
            ids = [] if t == "hors_corpus" else ["aiact:art6:p2", "rgpd:art22:p1"]
            qs.append(question(f"{t}-{i:02}", type=t, passage_ids=ids, status="validated"))
    return qs


def test_split_is_stratified_and_reproducible() -> None:
    qs = validated_set()
    evalset.assign_splits(qs)
    dev = [q for q in qs if q.split == "dev"]
    assert len(dev) == evalset.DEV_SIZE
    assert all(q.split == "test" for q in qs if q.split != "dev")
    # Chaque type est représenté en dev, en proportion de son effectif.
    assert Counter(q.type for q in dev) == {
        "factuelle": 4, "cas_pratique": 3, "multi_articles": 2, "multi_reglements": 2,
        "definition": 2, "hors_corpus": 2,
    }  # fmt: skip
    again = validated_set()
    evalset.assign_splits(again)
    assert [q.split for q in again] == [q.split for q in qs]


def test_rejected_and_draft_questions_get_no_split() -> None:
    qs = [*validated_set(), question("x1", status="rejected"), question("x2")]
    evalset.assign_splits(qs)
    assert qs[-2].split is None and qs[-1].split is None


def test_freeze_requires_review_and_targets() -> None:
    qs = validated_set()
    assert evalset.freeze_problems(qs)[0] == "factuelle-00 : pas de split"
    evalset.assign_splits(qs)
    assert evalset.freeze_problems(qs) == []
    assert evalset.freeze_problems([*qs, question("q999")]) == ["q999 : encore en brouillon"]
    assert "factuelle : 19 questions validées pour 20 visées" in evalset.freeze_problems(qs[1:])


@pytest.mark.skipif(
    not (EVAL / "dataset.sha256").exists(), reason="jeu d'évaluation pas encore gelé"
)
def test_frozen_dataset_is_unchanged() -> None:
    # Toute modification après le gel invalide la comparaison des expériences : il faut
    # une nouvelle version (eval-v2) et la documenter, pas éditer le fichier en place.
    expected = (EVAL / "dataset.sha256").read_text(encoding="utf-8").split()[0]
    assert evalset.digest(EVAL / "dataset.jsonl") == expected
