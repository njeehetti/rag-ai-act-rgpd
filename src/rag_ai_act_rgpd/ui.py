"""Interface de démo : ``make ui`` (ou ``uv run streamlit run src/rag_ai_act_rgpd/ui.py``)."""

import streamlit as st

from rag_ai_act_rgpd.api import DISCLAIMER
from rag_ai_act_rgpd.config import get_settings
from rag_ai_act_rgpd.llm import OllamaClient
from rag_ai_act_rgpd.rag import Rag, RagResult

EXAMPLES = [
    "Un système de scoring de crédit est-il un système d'IA à haut risque ?",
    "Un système de détection de la fraude bancaire est-il à haut risque ?",
    "Quelles obligations de transparence pour un chatbot de service client ?",
    "Quand une analyse d'impact relative à la protection des données est-elle obligatoire ?",
    "Quels sont les droits d'une personne face à une décision entièrement automatisée ?",
]


@st.cache_resource(show_spinner="Chargement des modèles (embedding, LLM)…")
def get_rag() -> Rag:
    from rag_ai_act_rgpd.service import build_rag

    rag = build_rag()
    if isinstance(rag.llm, OllamaClient):
        rag.llm.warm_up()
    return rag


def render_answer(result: RagResult) -> None:
    answer = result.answer
    text = answer.answer.replace("$", r"\$")  # « $ » déclencherait le rendu LaTeX
    for p in answer.citations:
        escaped = p.citation_label.replace("[", r"\[").replace("]", r"\]")
        text = text.replace(p.citation_label, f"[{escaped}]({p.url})")
    if answer.refused:
        st.warning(text)
    else:
        st.markdown(text)

    if answer.truncated:
        st.warning("Réponse ou contexte tronqué par le LLM : la réponse peut être incomplète.")
    if not answer.refused and not answer.citations:
        st.warning("Aucune source vérifiable dans cette réponse : ne pas s'y fier.")
    if answer.invalid_citations:
        st.error(
            "Citations absentes des passages fournis (à ne pas prendre pour des sources) : "
            + ", ".join(answer.invalid_citations)
        )

    if answer.citations:
        st.markdown("**Sources citées**")
        for p in answer.citations:
            with st.expander(p.citation_label):
                st.markdown(p.text.replace("$", r"\$"))
                st.markdown(f"[Texte officiel ↗]({p.url})")

    with st.expander(f"Recherche : {len(result.hits)} extraits les plus proches"):
        for rank, hit in enumerate(result.hits, start=1):
            st.markdown(f"**{rank}.** similarité {hit.score:.3f} · `{', '.join(hit.passage_ids)}`")
            st.caption(hit.text[:400] + ("…" if len(hit.text) > 400 else ""))

    usage = answer.completion
    tokens = f" · {usage.input_tokens} → {usage.output_tokens} tokens" if usage else ""
    st.caption(f"{result.total_ms / 1000:.1f} s (recherche {result.retrieval_ms:.0f} ms){tokens}")


def main() -> None:
    st.set_page_config(page_title="Assistant AI Act · RGPD", page_icon="⚖️", layout="centered")
    settings = get_settings()

    with st.sidebar:
        st.header("Exemples")
        for example in EXAMPLES:
            if st.button(example, use_container_width=True):
                st.session_state.pending = example
        st.divider()
        st.caption(
            f"LLM : `{settings.llm_model}` (Ollama, local)  \n"
            f"Embedding : `{settings.embedding_model}`  \n"
            f"Découpage : `{settings.chunk_strategy}`, top {settings.top_k_chunks}"
        )
        if st.button("Effacer la conversation", use_container_width=True):
            st.session_state.history = []

    st.title("⚖️ Assistant AI Act · RGPD · CNIL")
    st.caption(f"Réponses sourcées à partir des textes officiels. {DISCLAIMER}")

    history: list[tuple[str, RagResult]] = st.session_state.setdefault("history", [])
    for asked, result in history:
        with st.chat_message("user"):
            st.markdown(asked)
        with st.chat_message("assistant"):
            render_answer(result)

    typed = st.chat_input("Pose ta question sur l'AI Act, le RGPD ou la doctrine CNIL")
    question: str | None = typed or st.session_state.pop("pending", None)
    if not question:
        return

    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            rag = get_rag()
            with st.spinner("Recherche dans le corpus et rédaction de la réponse…"):
                result = rag.ask(question)
        except Exception as exc:  # base ou Ollama arrêtés : message lisible plutôt qu'une trace
            st.error(
                f"Erreur : {exc}\n\nVérifie que la base tourne (`docker compose up -d db`) "
                "et qu'Ollama est lancé."
            )
            return
        render_answer(result)
    history.append((question, result))


main()
