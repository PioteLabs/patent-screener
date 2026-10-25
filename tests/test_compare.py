from compare import overlap_score
from models import ClaimComparison, ElementMatch


def _comparison(presences: list[str]) -> ClaimComparison:
    return ClaimComparison(
        claim_text="a widget comprising A, B, and C",
        reads_on_idea=all(p == "present" for p in presences),
        elements=[
            ElementMatch(claim_element=f"element-{i}", presence=p, note="")
            for i, p in enumerate(presences)
        ],
        design_around="element-0",
    )


def test_overlap_score_all_present_is_one():
    assert overlap_score([_comparison(["present", "present"])]) == 1.0


def test_overlap_score_none_present_is_zero():
    assert overlap_score([_comparison(["absent", "absent"])]) == 0.0


def test_overlap_score_takes_max_across_claims():
    low = _comparison(["absent", "present"])
    high = _comparison(["present", "present"])
    assert overlap_score([low, high]) == 1.0


def test_overlap_score_empty_list_is_zero():
    assert overlap_score([]) == 0.0


def test_overlap_score_ignores_claim_with_no_elements():
    empty = ClaimComparison(
        claim_text="x", reads_on_idea=False, elements=[], design_around="n/a"
    )
    assert overlap_score([empty]) == 0.0
