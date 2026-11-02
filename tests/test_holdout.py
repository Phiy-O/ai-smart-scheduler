
from pathlib import Path
from collections import Counter

from benchmarks.evaluate import load_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_holdout_has_30_unique_cases():
    path = ROOT / "benchmarks" / "intent_holdout_v1.jsonl"
    cases = load_dataset(path)

    assert len(cases) == 30
    assert len({case["id"] for case in cases}) == 30


def test_holdout_intent_balance():
    path = ROOT / "benchmarks" / "intent_holdout_v1.jsonl"
    cases = load_dataset(path)

    counts = Counter(
        row["expected_action"]
        for row in cases
    )

    assert counts == {
        "create": 6,
        "update": 6,
        "reschedule": 6,
        "delete": 6,
        "clarify": 6,
    }


def test_holdout_does_not_duplicate_dev_instructions():
    dev = load_dataset(
        ROOT / "benchmarks" / "intent_v1.jsonl"
    )
    holdout = load_dataset(
        ROOT / "benchmarks" / "intent_holdout_v1.jsonl"
    )

    dev_instructions = {
        row["instruction"].strip().casefold()
        for row in dev
    }

    holdout_instructions = {
        row["instruction"].strip().casefold()
        for row in holdout
    }

    assert not (
        dev_instructions & holdout_instructions
    )
