
from benchmarks.evaluate import load_dataset
from benchmarks.evaluate_fields import (
    DATASET,
    score_case,
    summarize_fields,
)


def test_field_dataset_has_20_cases():
    cases = load_dataset(DATASET)

    assert len(cases) == 20
    assert len({row["id"] for row in cases}) == 20


def test_exact_match():
    expected = {
        "action": "delete",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "tomorrow",
        },
    }

    predicted = {
        "action": "delete",
        "target": {
            "task_name": "belajar python",
            "date_reference": "tomorrow",
        },
    }

    result = score_case(expected, predicted)

    assert result["intent_correct"]
    assert result["exact_match"]
    assert result["field_correct"] == 2


def test_wrong_intent_cannot_pass():
    expected = {
        "action": "delete",
        "target": {"task_name": "Belajar Python"},
    }
    predicted = {"action": "create"}

    result = score_case(expected, predicted)

    assert not result["intent_correct"]
    assert not result["exact_match"]


def test_unsupported_field_is_detected():
    expected = {
        "action": "delete",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": None,
        },
    }

    predicted = {
        "action": "delete",
        "target": {
            "task_name": "Belajar Python",
            "date_reference": "tomorrow",
        },
    }

    result = score_case(expected, predicted)

    assert result["unsupported_fields"] == 1
    assert not result["exact_match"]


def test_summary_counts_errors():
    sample = {
        "intent_correct": False,
        "exact_match": False,
        "field_correct": 0,
        "field_total": 0,
        "supported_correct": 0,
        "supported_total": 0,
        "unsupported_fields": 0,
        "predicted_non_null": 0,
        "error": "ValidationError",
    }

    summary = summarize_fields([sample])

    assert summary["intent_accuracy"] == 0
    assert summary["exact_match_accuracy"] == 0
    assert summary["execution_errors"] == 1
