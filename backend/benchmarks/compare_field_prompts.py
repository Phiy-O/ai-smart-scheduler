
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from schedule_commands import (
    CommandParser,
    EXTRACTION_PROMPT,
)
from extraction_prompts import EXTRACTION_PROMPT_V2

from benchmarks.evaluate import load_dataset
from benchmarks.evaluate_fields import (
    run_field_benchmark,
    summarize_fields,
    save_field_results,
)


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "field_holdout_v1.jsonl"
OUTPUT_DIR = ROOT / "results"

PROMPTS = {
    "v1": EXTRACTION_PROMPT,
    "v2": EXTRACTION_PROMPT_V2,
}

METRICS = (
    "intent_accuracy",
    "exact_match_accuracy",
    "field_accuracy_given_correct_intent",
    "supported_field_recall",
    "unsupported_field_rate",
)


def main():
    model = os.getenv("LLM_MODEL", "qwen3:4b")

    # Use v2-first as an optional order check on later runs.
    order = os.getenv(
        "PROMPT_ORDER", "v1,v2"
    ).split(",")

    if len(order) != 2 or set(order) != {"v1", "v2"}:
        raise ValueError(
            "PROMPT_ORDER must contain v1,v2 or v2,v1"
        )

    cases = load_dataset(DATASET)

    if not cases:
        raise ValueError("Dataset is empty")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_id = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    summaries = {}
    results_by_version = {}

    print("=== FIELD EXTRACTION HOLDOUT ===")
    print("Model:", model)
    print("Dataset:", DATASET.name)
    print("Cases:", len(cases))
    print("Prompt order:", ", ".join(order))

    for version in order:
        print(f"\nRunning Extraction Prompt {version}...")

        parser = CommandParser(
            extraction_prompt=PROMPTS[version]
        )

        results = run_field_benchmark(
            parser.parse,
            cases,
        )
        summary = summarize_fields(results)

        summaries[version] = summary
        results_by_version[version] = results

        results_path = (
            OUTPUT_DIR
            / f"field_holdout_{version}_{run_id}.jsonl"
        )

        save_field_results(results, results_path)

        print(
            "Exact match:",
            f"{summary['exact_match_accuracy']:.2%}",
        )
        print(
            "Execution errors:",
            summary["execution_errors"],
        )
        print("Saved:", results_path)

    print("\n=== V1 VS V2 COMPARISON ===")

    for metric in METRICS:
        v1 = summaries["v1"][metric]
        v2 = summaries["v2"][metric]

        if v1 is None or v2 is None:
            print(f"{metric}: N/A")
            continue

        difference = (v2 - v1) * 100

        print(
            f"{metric}: "
            f"V1={v1:.2%} | "
            f"V2={v2:.2%} | "
            f"delta={difference:+.2f} pp"
        )

    print("\n=== CASE-LEVEL COMPARISON ===")

    v1_by_id = {
        row["id"]: row
        for row in results_by_version["v1"]
    }
    v2_by_id = {
        row["id"]: row
        for row in results_by_version["v2"]
    }

    improved = []
    regressed = []
    both_wrong = []

    for case in cases:
        case_id = case["id"]
        old = v1_by_id[case_id]
        new = v2_by_id[case_id]

        if not old["exact_match"] and new["exact_match"]:
            improved.append(case_id)
        elif old["exact_match"] and not new["exact_match"]:
            regressed.append(case_id)
        elif not old["exact_match"] and not new["exact_match"]:
            both_wrong.append(case_id)

    print("Improved:", improved)
    print("Regressed:", regressed)
    print("Both wrong:", both_wrong)

    print("\n=== V2 FIELD ERRORS ===")

    for row in results_by_version["v2"]:
        if row["exact_match"]:
            continue

        print(f"\n{row['id']}: {row['instruction']}")
        print("Expected:", row["expected"])
        print("Predicted:", row["predicted"])

        if row["error"]:
            print("Error:", row["error"])

        for field in row["field_details"]:
            if not field["correct"]:
                print(
                    f"  {field['field']}: "
                    f"expected={field['expected']!r}, "
                    f"predicted={field['predicted']!r}"
                )

    comparison = {
        "model_configured": model,
        "dataset": DATASET.name,
        "run_id": run_id,
        "order": order,
        "summaries": summaries,
        "improved_cases": improved,
        "regressed_cases": regressed,
        "both_wrong_cases": both_wrong,
    }

    comparison_path = (
        OUTPUT_DIR / f"field_comparison_{run_id}.json"
    )

    comparison_path.write_text(
        json.dumps(
            comparison,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nComparison saved:", comparison_path)


if __name__ == "__main__":
    main()
