from rag_ai_act_rgpd.generation import REFUSAL, answer_question, build_messages
from rag_ai_act_rgpd.llm import Completion, Message
from rag_ai_act_rgpd.parsing.models import Passage


class FakeLLM:
    model = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.truncated = False
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message]) -> Completion:
        self.calls.append(messages)
        return Completion(self.reply, self.model, 100, 20, 1.0, truncated=self.truncated)


def passage(pid: str, label: str, text: str = "texte") -> Passage:
    return Passage(
        id=pid, document_id="aiact", kind="paragraph", citation_label=label,
        text=text, url="https://x", position=0,
    )  # fmt: skip


ART50 = passage("aiact:art50:p1", "[AI Act, art. 50 §1]", "Les fournisseurs veillent…")
CNIL = passage(
    "cnil:x:y", "[CNIL, IA : Réaliser une analyse d’impact si nécessaire, « Identifier »]"
)


def test_no_context_refuses_without_calling_the_llm() -> None:
    llm = FakeLLM("ne doit pas être appelé")
    answer = answer_question("Quel est le meilleur LLM ?", [], llm)
    assert answer.refused
    assert answer.answer == REFUSAL
    assert llm.calls == []


def test_model_refusal_is_detected() -> None:
    answer = answer_question("q", [ART50], FakeLLM(f"« {REFUSAL} »"))
    assert answer.refused
    assert answer.citations == []


def test_valid_citations_are_resolved_to_passages() -> None:
    reply = "Un chatbot doit informer l'utilisateur [AI Act, art. 50 §1]."
    answer = answer_question("q", [ART50, CNIL], FakeLLM(reply))
    assert not answer.refused
    assert [p.id for p in answer.citations] == ["aiact:art50:p1"]
    assert answer.invalid_citations == []
    assert answer.context_ids == ["aiact:art50:p1", "cnil:x:y"]


def test_citation_typography_variants_are_tolerated() -> None:
    reply = "Voir [CNIL, IA : Réaliser une analyse d'impact si nécessaire, « Identifier »]."
    answer = answer_question("q", [CNIL], FakeLLM(reply))
    assert [p.id for p in answer.citations] == ["cnil:x:y"]


def test_invented_citation_is_flagged() -> None:
    reply = "C'est interdit [AI Act, art. 5 §1] et il faut informer [AI Act, art. 50 §1]."
    answer = answer_question("q", [ART50], FakeLLM(reply))
    assert answer.invalid_citations == ["[AI Act, art. 5 §1]"]
    assert [p.id for p in answer.citations] == ["aiact:art50:p1"]


def test_prompt_contains_labelled_excerpts_and_question() -> None:
    system, user = build_messages("Quelles obligations ?", [ART50])
    assert system.role == "system"
    assert "N'invente jamais de référence" in system.content
    assert "[AI Act, art. 50 §1]\nLes fournisseurs veillent…" in user.content
    assert user.content.endswith("Question : Quelles obligations ?")


ART5_P1 = passage(
    "aiact:art5:p1", "[AI Act, art. 5 §1]", "Les pratiques suivantes sont interdites : a) …"
)


def test_citation_of_a_point_resolves_to_its_paragraph() -> None:
    # Les points a), b)… restent dans le passage du paragraphe : le modèle les cite pourtant.
    reply = "Interdit [AI Act, art. 5 §1 a] et [AI Act, art. 5 §1, point b bis]."
    answer = answer_question("q", [ART5_P1], FakeLLM(reply))
    assert [p.id for p in answer.citations] == ["aiact:art5:p1"]
    assert answer.invalid_citations == []


def test_inserted_paragraph_is_not_its_neighbour() -> None:
    # « §1 bis » est un autre paragraphe (inséré par amendement), pas un point du §1.
    answer = answer_question("q", [ART5_P1], FakeLLM("Voir [AI Act, art. 5 §1 bis]."))
    assert answer.invalid_citations == ["[AI Act, art. 5 §1 bis]"]


def test_refusal_mixed_with_an_answer_is_not_a_refusal() -> None:
    reply = f"{REFUSAL} Sur le point X en revanche, il faut informer [AI Act, art. 50 §1]."
    answer = answer_question("q", [ART50], FakeLLM(reply))
    assert not answer.refused
    assert answer.answer == reply


def test_answer_without_valid_citation_is_not_grounded() -> None:
    assert not answer_question("q", [ART50], FakeLLM("Il faut informer.")).grounded
    assert not answer_question("q", [ART50], FakeLLM("Voir [AI Act, art. 9 §1].")).grounded
    assert answer_question("q", [ART50], FakeLLM("Voir [AI Act, art. 50 §1].")).grounded


def test_truncated_completion_is_flagged() -> None:
    llm = FakeLLM("Un chatbot doit informer [AI Act, art. 50")
    llm.truncated = True
    assert answer_question("q", [ART50], llm).truncated
