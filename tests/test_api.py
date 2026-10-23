from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from rag_ai_act_rgpd import __version__
from rag_ai_act_rgpd.api import app, get_rag
from rag_ai_act_rgpd.generation import Answer
from rag_ai_act_rgpd.llm import Completion
from rag_ai_act_rgpd.parsing.models import Passage
from rag_ai_act_rgpd.rag import RagResult

ART50 = Passage(
    id="aiact:art50:p1", document_id="aiact", kind="paragraph",
    citation_label="[AI Act, art. 50 §1]", text="Les fournisseurs veillent…",
    url="https://eur-lex.europa.eu/x#art_50", position=0,
)  # fmt: skip


class FakeRag:
    def ask(self, question: str) -> RagResult:
        answer = Answer(
            question=question,
            answer="Le chatbot doit informer l'utilisateur [AI Act, art. 50 §1].",
            refused=False,
            citations=[ART50],
            invalid_citations=[],
            context_ids=[ART50.id],
            completion=Completion("…", "qwen3:8b", 1200, 80, 900.0),
        )
        return RagResult(answer=answer, hits=[], retrieval_ms=12.0, total_ms=950.0)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_rag] = FakeRag
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_ask_returns_answer_citations_and_disclaimer(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "Obligations d'un chatbot ?"})

    assert response.status_code == 200
    body = response.json()
    assert body["refused"] is False
    assert body["citations"] == [
        {
            "passage_id": "aiact:art50:p1",
            "label": "[AI Act, art. 50 §1]",
            "url": "https://eur-lex.europa.eu/x#art_50",
            "text": "Les fournisseurs veillent…",
        }
    ]
    assert body["usage"] == {"model": "qwen3:8b", "input_tokens": 1200, "output_tokens": 80}
    assert "pas un conseil juridique" in body["disclaimer"]


def test_ask_rejects_empty_question(client: TestClient) -> None:
    assert client.post("/ask", json={"question": ""}).status_code == 422
