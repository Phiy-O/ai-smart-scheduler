
import json
import re
import time
import unicodedata
from pathlib import Path

from benchmarks.evaluate import load_dataset


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "field_extraction_v1.jsonl"

FIELD_PATHS = {
    "create": (
        "task_name",
        "date_reference",
        "duration_minutes",
        "preferred_period",
    ),
    "delete": (
        "target.task_name",
        "target.date_reference",
    ),
    "update": (
        "target.task_name",
        "target.date_reference",
        "changes.duration_minutes",
        "changes.preferred_period",
    ),
    "reschedule": (
        "target.task_name",
        "target.date_reference",
        "new_date_reference",
        "new_period",
    ),
}


def normalize_text(value):
    value = unicodedata.normalize("NFKC", value)
    value = value.casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


def get_field(data, path):
    current = data

    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def values_equal(expected, predicted):
    if isinstance(expected, str) and isinstance(predicted, str):
        return normalize_text(expected) == normalize_text(predicted)

    return expected == predicted


def score_case(expected, predicted):
    expected_action = expected.get("action")
    predicted_action = predicted.get("action")

    intent_correct = expected_action == predicted_action

    # A wrong schema must not receive field-match credit.
    if not intent_correct:
        return {
            "intent_correct": False,
            "exact_match": False,
            "field_correct": 0,
            "field_total": 0,
            "supported_correct": 0,
            "supported_total": 0,
            "unsupported_fields": 0,
            "predicted_non_null": 0,
            "field_details": [],
        }

    paths = FIELD_PATHS.get(expected_action, ())
    details = []

    for path in paths:
        expected_value = get_field(expected, path)
        predicted_value = get_field(predicted, path)

        correct = values_equal(expected_value, predicted_value)

        details.append({
            "field": path,
            "expected": expected_value,
            "predicted": predicted_value,
            "correct": correct,
            "unsupported": (
                expected_value is None
                and predicted_value is not None
            ),
        })

    supported = [
        item for item in details
        if item["expected"] is not None
    ]

    return {
        "intent_correct": True,
        "exact_match": all(item["correct"] for item in details),
        "field_correct": sum(item["correct"] for item in details),
        "field_total": len(details),
        "supported_correct": sum(
            item["correct"] for item in supported
        ),
        "supported_total": len(supported),
        "unsupported_fields": sum(
            item["unsupported"] for item in details
        ),
        "predicted_non_null": sum(
            item["predicted"] is not None
            for item in details
        ),
        "field_details": details,
    }


def run_field_benchmark(parse_instruction, cases=None):
    cases = cases if cases is not None else load_dataset(DATASET)
    results = []

    for case in cases:
        started = time.perf_counter()

        try:
            command = parse_instruction(case["instruction"])
            predicted = command.model_dump(mode="json")
            error = None
        except Exception as exc:
            predicted = {}
            error = f"{type(exc).__name__}: {exc}"

        elapsed = time.perf_counter() - started
        scores = score_case(case["expected"], predicted)

        results.append({
            "id": case["id"],
            "instruction": case["instruction"],
            "expected": case["expected"],
            "predicted": predicted,
            "error": error,
            "latency_seconds": round(elapsed, 3),
            **scores,
        })

    return results


def summarize_fields(results):
    if not results:
        raise ValueError("Empty benchmark")

    total = len(results)
    correct_intents = sum(r["intent_correct"] for r in results)
    exact = sum(r["exact_match"] for r in results)
    field_correct = sum(r["field_correct"] for r in results)
    field_total = sum(r["field_total"] for r in results)
    supported_correct = sum(r["supported_correct"] for r in results)
    supported_total = sum(r["supported_total"] for r in results)
    unsupported = sum(r["unsupported_fields"] for r in results)
    predicted_non_null = sum(r["predicted_non_null"] for r in results)

    return {
        "total": total,
        "intent_accuracy": round(correct_intents / total, 4),
        "exact_match_accuracy": round(exact / total, 4),
        "field_accuracy_given_correct_intent": round(
            field_correct / field_total, 4
        ) if field_total else None,
        "supported_field_recall": round(
            supported_correct / supported_total, 4
        ) if supported_total else None,
        "unsupported_field_rate": round(
            unsupported / predicted_non_null, 4
        ) if predicted_non_null else 0.0,
        "execution_errors": sum(r["error"] is not None for r in results),
    }


def save_field_results(results, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in results:
            file.write(
                json.dumps(row, ensure_ascii=False) + "\n"
            )
