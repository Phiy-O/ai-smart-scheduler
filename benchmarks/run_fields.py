
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from schedule_commands import CommandParser
from extraction_prompts import EXTRACTION_PROMPT_V2

from benchmarks.evaluate_fields import (
    DATASET,
    load_dataset,
    run_field_benchmark,
    summarize_fields,
    save_field_results,
)


def main():
    model = os.getenv("LLM_MODEL", "qwen3:4b")
    cases = load_dataset(DATASET)
    prompt_version = os.getenv("EXTRACTION_PROMPT_VERSION", "v1")

    if prompt_version not in ("v1", "v2"):
        raise ValueError("Unknown extraction prompt version")

    parser = CommandParser(
        extraction_prompt=(
            EXTRACTION_PROMPT_V2
            if prompt_version == "v2"
            else None
        )
    )

    print(f"Model: {model}")
    print(f"Cases: {len(cases)}")
    print("Running field extraction benchmark...\n")

    results = run_field_benchmark(parser.parse, cases)
    summary = summarize_fields(results)

    directory = Path(__file__).resolve().parent / "results"
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    results_path = (
        directory / f"fields_{prompt_version}_{timestamp}.jsonl"
    )

    summary_path = (
        directory / f"fields_summary_{prompt_version}_{timestamp}.json"
    )

    save_field_results(results, results_path)

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("=== FIELD EXTRACTION BENCHMARK ===")

    for name, value in summary.items():
        if isinstance(value, float):
            print(f"{name}: {value:.2%}")
        else:
            print(f"{name}: {value}")

    print("\nIncorrect or incomplete cases:")

    for row in results:
        if row["exact_match"]:
            continue

        print(f"\n{row['id']}: {row['instruction']}")
        print("Expected action:", row["expected"]["action"])
        print("Predicted action:", row["predicted"].get("action"))

        if row["error"]:
            print("Error:", row["error"])

        for field in row["field_details"]:
            if not field["correct"]:
                print(
                    f"  {field['field']}: "
                    f"expected={field['expected']!r}, "
                    f"predicted={field['predicted']!r}"
                )

    print("\nSaved results:", results_path)
    print("Saved summary:", summary_path)


if __name__ == "__main__":
    main()
