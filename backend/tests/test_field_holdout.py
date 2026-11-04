
from collections import Counter
from pathlib import Path

from benchmarks.evaluate import load_dataset
from benchmarks.evaluate_fields import FIELD_PATHS


ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = ROOT / "benchmarks" / "field_holdout_v1.jsonl"
DEVELOPMENT = ROOT / "benchmarks" / "field_extraction_v1.jsonl"


def test_holdout_size_and_unique_ids():
    cases = load_dataset(HOLDOUT)

    assert len(cases) == 32
    assert len({case["id"] for case in cases}) == 32


def test_holdout_balanced_actions():
    cases = load_dataset(HOLDOUT)

    counts = Counter(
        case["expected"]["action"]
        for case in cases
    )

    assert counts == {
        "create": 8,
        "update": 8,
        "reschedule": 8,
        "delete": 8,
    }


def test_holdout_schema_shape():
    cases = load_dataset(HOLDOUT)

    for case in cases:
        action = case["expected"]["action"]

        assert action in FIELD_PATHS
        assert case["instruction"].strip()

        for path in FIELD_PATHS[action]:
            value = case["expected"]

            for part in path.split("."):
                assert part in value, (
                    case["id"], path
                )
                value = value[part]


def test_holdout_has_no_exact_dev_duplicates():
    dev = load_dataset(DEVELOPMENT)
    holdout = load_dataset(HOLDOUT)

    dev_texts = {
        case["instruction"].strip().casefold()
        for case in dev
    }

    holdout_texts = {
        case["instruction"].strip().casefold()
        for case in holdout
    }

    assert not dev_texts & holdout_texts
