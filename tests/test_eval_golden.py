from collections import Counter

from papertrail.evaluation.golden import load_extraction, load_rulebook, load_verdicts
from papertrail.models import VerdictLabel


def test_verdict_set_shape():
    full, smoke = load_verdicts("full"), load_verdicts("smoke")
    assert len(full) == 95 and len(smoke) == 15  # golden set v2
    labels = Counter(i.gold_label for i in full)
    assert set(labels) == set(VerdictLabel) and min(labels.values()) >= 23  # balanced
    assert {i.language.value for i in full} == {"en", "hi", "hinglish"}
    assert set(Counter(i.gold_label for i in smoke)) == set(VerdictLabel)  # every label in smoke


def test_evidence_is_clearly_synthetic():
    for item in load_verdicts():
        for e in item.evidence:
            assert ".eval.test/" in e.url, f"{item.id}/{e.id} must use a .eval.test URL"


def test_extraction_and_rulebook_sets():
    ext = load_extraction()
    assert len(ext) == 20 and sum(len(t.claims) for t in ext) == 55
    rb = load_rulebook()
    assert len(rb) == 52 and any(not s.expect for s in rb)  # includes negatives
    assert load_extraction("smoke") and load_rulebook("smoke")
