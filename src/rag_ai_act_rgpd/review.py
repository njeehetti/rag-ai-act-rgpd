"""Relecture du jeu d'évaluation : ``make review``.

Chaque question s'affiche avec le texte intégral de ses passages justificatifs : on valide,
on corrige ou on rejette. Les modifications sont écrites aussitôt dans ``eval/dataset.jsonl``.
"""

from dataclasses import replace
from pathlib import Path
from typing import get_args

import streamlit as st

from rag_ai_act_rgpd import evalset
from rag_ai_act_rgpd.evalset import Question, Status
from rag_ai_act_rgpd.ingest import load_corpus
from rag_ai_act_rgpd.parsing.models import Passage

DATASET = Path("eval") / "dataset.jsonl"
STATUS_ICONS: dict[str, str] = {"draft": "✏️", "validated": "✅", "rejected": "❌"}


@st.cache_resource(show_spinner="Lecture du corpus…")
def get_corpus() -> dict[str, Passage]:
    return {p.id: p for p in load_corpus(Path("data/raw"), Path("data/manifest.json"))}


def save(questions: list[Question], updated: Question) -> None:
    evalset.save([updated if q.id == updated.id else q for q in questions], DATASET)


def next_id(questions: list[Question]) -> str:
    numbers = [int(q.id[1:]) for q in questions if q.id[1:].isdigit()]
    return f"q{max(numbers, default=0) + 1:03}"


def sidebar(questions: list[Question]) -> Question | None:
    st.header("Avancement")
    kept = [q for q in questions if q.status == "validated"]
    st.progress(min(1.0, len(kept) / sum(evalset.TARGETS.values())))
    for t, target in evalset.TARGETS.items():
        done = sum(q.type == t for q in kept)
        drafts = sum(q.type == t and q.status == "draft" for q in questions)
        st.caption(f"{t} : **{done}/{target}** validées · {drafts} brouillons")
    st.divider()
    shown = st.multiselect(
        "Statuts affichés",
        get_args(Status),
        default=["draft"],
        format_func=STATUS_ICONS.__getitem__,
    )
    pool = [q for q in questions if q.status in shown]
    if not pool:
        st.info("Aucune question avec ces statuts.")
        return None
    labels = {q.id: f"{STATUS_ICONS[q.status]} {q.id} · {q.type} · {q.question[:50]}" for q in pool}
    chosen = st.radio("Question", list(labels), format_func=labels.__getitem__)
    return next(q for q in pool if q.id == chosen)


def show_passages(ids: list[str], corpus: dict[str, Passage]) -> None:
    for pid in ids:
        p = corpus.get(pid)
        if p is None:
            st.error(f"Passage inconnu : `{pid}`")
            continue
        with st.expander(f"{p.citation_label} · `{pid}`", expanded=True):
            st.markdown(p.text.replace("$", r"\$"))
            st.markdown(f"[Texte officiel ↗]({p.url})")


def edit(q: Question, questions: list[Question], corpus: dict[str, Passage]) -> None:
    st.subheader(f"{q.id} · {STATUS_ICONS[q.status]} {q.status} · origine {q.origin}")
    with st.form(f"edit-{q.id}"):
        text = st.text_area("Question", q.question, height=80)
        answer = st.text_area("Réponse de référence", q.reference_answer, height=160)
        ids = st.text_area(
            "Passages justificatifs (un identifiant par ligne)", "\n".join(q.passage_ids)
        )
        left, mid, right = st.columns(3)
        qtype = left.selectbox("Type", evalset.TYPES, index=evalset.TYPES.index(q.type))
        difficulty = mid.select_slider("Difficulté", [1, 2, 3], value=q.difficulty)
        tags = right.text_input("Tags (virgules)", ", ".join(q.tags))
        notes = st.text_input("Notes de relecture", q.notes)
        actions = st.columns(3)
        clicked: dict[Status, bool] = {
            "validated": actions[0].form_submit_button("✅ Valider", type="primary"),
            "draft": actions[1].form_submit_button("💾 Enregistrer en brouillon"),
            "rejected": actions[2].form_submit_button("❌ Rejeter"),
        }
    updated = replace(
        q,
        question=text.strip(),
        reference_answer=answer.strip(),
        passage_ids=[line.strip() for line in ids.splitlines() if line.strip()],
        type=qtype,
        difficulty=difficulty,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        notes=notes.strip(),
    )
    status = next((s for s, pressed in clicked.items() if pressed), None)
    if status is not None:
        updated = replace(updated, status=status)
        problems = evalset.check([updated], corpus)
        if status == "validated" and problems:
            st.error("Impossible de valider :\n\n- " + "\n- ".join(problems))
        else:
            save(questions, updated)
            st.toast(f"{q.id} : {status}")
            st.rerun()
    for problem in evalset.check([updated], corpus):
        st.warning(problem)
    show_passages(updated.passage_ids, corpus)


def search(corpus: dict[str, Passage]) -> None:
    with st.expander("🔎 Chercher un passage (identifiant ou texte)"):
        query = st.text_input("Recherche", key="search").strip().lower()
        if len(query) < 3:
            return
        hits = [p for p in corpus.values() if query in p.id or query in p.text.lower()]
        st.caption(f"{len(hits)} passages, 20 premiers affichés")
        for p in hits[:20]:
            st.markdown(f"`{p.id}` · {p.citation_label}")
            st.caption(p.text[:300] + ("…" if len(p.text) > 300 else ""))


def new_question(questions: list[Question]) -> None:
    with (
        st.expander("✍️ Écrire une nouvelle question (origine : njee)"),
        st.form("new", clear_on_submit=True),
    ):
        text = st.text_area("Question", height=80)
        qtype = st.selectbox("Type", evalset.TYPES)
        if st.form_submit_button("Créer le brouillon") and text.strip():
            q = Question(
                id=next_id(questions), question=text.strip(), reference_answer="",
                passage_ids=[], type=qtype, difficulty=2, origin="njee",
            )  # fmt: skip
            evalset.save([*questions, q], DATASET)
            st.toast(f"{q.id} créé : complète la réponse et les passages")
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Relecture du jeu d'évaluation", page_icon="📝", layout="wide")
    st.title("📝 Relecture du jeu d'évaluation")
    corpus = get_corpus()
    questions = evalset.load(DATASET)
    with st.sidebar:
        current = sidebar(questions)
    new_question(questions)
    search(corpus)
    if current is not None:
        edit(current, questions, corpus)


main()
