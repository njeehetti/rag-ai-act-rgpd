from rag_ai_act_rgpd.chunking import chunk_fixed, chunk_structural
from rag_ai_act_rgpd.parsing.models import Passage


def passage(pid: str, n_words: int, url: str = "https://x/doc-a", label: str = "") -> Passage:
    words = " ".join(f"{pid}-w{i}" for i in range(n_words))
    return Passage(
        id=pid,
        document_id=pid.split(":")[0],
        kind="paragraph",
        citation_label=label or f"[{pid}]",
        text=words,
        url=url,
        position=0,
        heading="Titre de l'article",
    )


def words_of(passages: list[Passage]) -> list[str]:
    return [w for p in passages for w in p.text.split()]


class TestFixed:
    def test_windows_have_size_and_overlap(self) -> None:
        passages = [passage("a:p1", 150), passage("a:p2", 150)]
        chunks = chunk_fixed(passages, size=100, overlap=20)
        assert all(len(c.text.split()) <= 100 for c in chunks)
        first, second = chunks[0].text.split(), chunks[1].text.split()
        assert first[-20:] == second[:20]

    def test_every_word_is_covered_and_order_is_kept(self) -> None:
        passages = [passage("a:p1", 37), passage("a:p2", 250), passage("a:p3", 3)]
        chunks = chunk_fixed(passages, size=100, overlap=20)
        covered = [w for c in chunks for w in c.text.split()]
        assert set(covered) == set(words_of(passages))
        assert chunks[-1].text.split()[-1] == "a:p3-w2"

    def test_passage_ids_are_exactly_the_overlapped_passages(self) -> None:
        passages = [passage("a:p1", 90), passage("a:p2", 90)]
        chunks = chunk_fixed(passages, size=100, overlap=20)
        assert chunks[0].passage_ids == ("a:p1", "a:p2")  # 90 mots de p1 + 10 de p2
        for c in chunks:
            expected = tuple(p.id for p in passages if set(p.text.split()) & set(c.text.split()))
            assert c.passage_ids == expected

    def test_never_crosses_documents(self) -> None:
        passages = [passage("a:p1", 30, url="https://x/a"), passage("b:p1", 30, url="https://x/b")]
        chunks = chunk_fixed(passages, size=100, overlap=20)
        assert [c.passage_ids for c in chunks] == [("a:p1",), ("b:p1",)]

    def test_ids_and_positions(self) -> None:
        chunks = chunk_fixed([passage("a:p1", 300)], size=100, overlap=20)
        assert [c.id for c in chunks] == [f"fixed:{i}" for i in range(len(chunks))]
        assert [c.position for c in chunks] == list(range(len(chunks)))
        assert {c.strategy for c in chunks} == {"fixed"}


class TestStructural:
    def test_one_chunk_per_short_passage_with_context_header(self) -> None:
        p = passage("aiact:art50:p1", 40, label="[AI Act, art. 50 §1]")
        [chunk] = chunk_structural([p], max_words=220, overlap=40)
        assert chunk.passage_ids == ("aiact:art50:p1",)
        header, body = chunk.text.split("\n", 1)
        assert header == "[AI Act, art. 50 §1] Titre de l'article"
        assert body == p.text

    def test_long_passage_is_split_but_keeps_its_id(self) -> None:
        p = passage("aiact:anxIV", 500)
        chunks = chunk_structural([p], max_words=220, overlap=40)
        assert len(chunks) == 3
        assert all(c.passage_ids == ("aiact:anxIV",) for c in chunks)
        assert all(c.text.startswith("[aiact:anxIV]") for c in chunks)
        body_words = [w for c in chunks for w in c.text.split("\n", 1)[1].split()]
        assert set(body_words) == set(p.text.split())
