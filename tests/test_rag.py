from rag_ai_act_rgpd.parsing.models import Passage
from rag_ai_act_rgpd.rag import TRUNCATED, fit_to_budget


def passage(pid: str, size: int) -> Passage:
    return Passage(
        id=pid, document_id="cnil", kind="section", citation_label=f"[{pid}]",
        text="x" * size, url="https://x", position=0,
    )  # fmt: skip


def test_passages_kept_in_rank_order_within_budget() -> None:
    kept = fit_to_budget([passage("a", 400), passage("b", 500), passage("c", 200)], 1000)
    assert [p.id for p in kept] == ["a", "b"]


def test_oversized_passage_is_skipped_for_smaller_ones() -> None:
    kept = fit_to_budget([passage("a", 400), passage("huge", 27_000), passage("c", 200)], 1000)
    assert [p.id for p in kept] == ["a", "c"]


def test_oversized_first_passage_is_truncated_not_dropped() -> None:
    [kept] = fit_to_budget([passage("huge", 27_000), passage("b", 500)], 1000)
    assert kept.id == "huge"
    assert len(kept.text) == 1000
    assert kept.text.endswith(TRUNCATED)
