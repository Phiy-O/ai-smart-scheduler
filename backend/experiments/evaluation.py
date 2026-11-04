
import json
import re
from pathlib import Path
from typing import Literal

from ollama import chat
from pydantic import BaseModel, Field, ConfigDict

MODEL = "qwen3:4b"
THINKING = False
FIELDS = [
    "action", "title", "duration_minutes",
    "preferred_period", "avoid_period", "date_reference"
]

Period = Literal["morning", "afternoon", "evening"]


class ScheduleIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["create", "update", "delete"] = Field(
        description="create=tambah, update=ubah, delete=hapus"
    )
    title: str = Field(description="Nama aktivitas dalam bahasa Indonesia")
    duration_minutes: int | None = Field(ge=1)
    preferred_period: list[Period]
    avoid_period: list[Period]
    date_reference: Literal["today", "tomorrow"] | None


SYSTEM_PROMPT = """
Kamu adalah parser instruksi AI Smart Scheduler.

Ekstrak informasi, jangan membuat rekomendasi jadwal.

Aturan:
- create = membuat aktivitas baru
- update = mengubah aktivitas
- delete = menghapus aktivitas
- Pagi = morning
- Siang atau sore = afternoon
- Malam = evening
- Hari ini = today
- Besok = tomorrow
- Jika durasi tidak ada, gunakan null
- Jika preferensi tidak ada, gunakan []
- Jika tanggal tidak ada, gunakan null
- Jangan mengarang informasi
- Pertahankan nama aktivitas dalam bahasa Indonesia
- Kembalikan hanya JSON sesuai schema
"""

FEW_SHOT_EXAMPLES = [
    (
        "Tambahkan menulis jurnal selama 20 menit hari ini sore.",
        {
            "action": "create",
            "title": "Menulis jurnal",
            "duration_minutes": 20,
            "preferred_period": ["afternoon"],
            "avoid_period": [],
            "date_reference": "today"
        }
    ),
    (
        "Besok aku mau merapikan meja selama satu jam, "
        "pagi atau malam boleh, jangan siang.",
        {
            "action": "create",
            "title": "Merapikan meja",
            "duration_minutes": 60,
            "preferred_period": ["morning", "evening"],
            "avoid_period": ["afternoon"],
            "date_reference": "tomorrow"
        }
    ),
    (
        "Tolong tambahkan aktivitas menyiram tanaman.",
        {
            "action": "create",
            "title": "Menyiram tanaman",
            "duration_minutes": None,
            "preferred_period": [],
            "avoid_period": [],
            "date_reference": None
        }
    )
]


def build_messages(instruction, mode):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    if mode == "few_shot":
        for example_input, example_output in FEW_SHOT_EXAMPLES:
            messages.append({
                "role": "user",
                "content": example_input
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(
                    example_output, ensure_ascii=False
                )
            })

    messages.append({
        "role": "user",
        "content": instruction
    })

    return messages


def normalize_title(value):
    value = str(value).casefold().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^jadwal\s+", "", value)
    return value


def compare_fields(actual, expected):
    result = {}

    for field in FIELDS:
        a = actual.get(field)
        e = expected.get(field)

        if field == "title":
            result[field] = normalize_title(a) == normalize_title(e)
        elif field in ("preferred_period", "avoid_period"):
            result[field] = (
                isinstance(a, list)
                and set(a) == set(e)
            )
        else:
            result[field] = a == e

    return result


def evaluate(case, mode):
    try:
        response = chat(
            model=MODEL,
            messages=build_messages(case["input"], mode),
            format=ScheduleIntent.model_json_schema(),
            think=THINKING,
            options={
                "temperature": 0,
                "num_ctx": 4096
            }
        )

        actual = ScheduleIntent.model_validate_json(
            response.message.content
        ).model_dump()

        fields = compare_fields(actual, case["expected"])

        return {
            "id": case["id"],
            "mode": mode,
            "valid_schema": True,
            "exact_match": all(fields.values()),
            "fields": fields,
            "expected": case["expected"],
            "actual": actual,
            "total_seconds": round(
                response.total_duration / 1e9, 3
            ),
            "load_seconds": round(
                (response.load_duration or 0) / 1e9, 3
            ),
            "generated_tokens": response.eval_count,
            "prompt_tokens": response.prompt_eval_count
        }

    except Exception as exc:
        return {
            "id": case["id"],
            "mode": mode,
            "valid_schema": False,
            "exact_match": False,
            "fields": {key: False for key in FIELDS},
            "error": str(exc)
        }


def summarize(results, mode):
    group = [r for r in results if r["mode"] == mode]
    count = len(group)
    valid = [r for r in group if r["valid_schema"]]

    correct = sum(r["exact_match"] for r in group)
    schema_ok = len(valid)

    print(f"\n--- SUMMARY: {mode.upper()} ---")
    print(f"Schema validity: {schema_ok}/{count}")
    print(f"Exact match: {correct}/{count}")
    print(f"Accuracy: {correct / count * 100:.1f}%")

    print("\nField accuracy:")
    for field in FIELDS:
        passed = sum(r["fields"][field] for r in group)
        print(f"  {field}: {passed}/{count}")

    if valid:
        avg = sum(r["total_seconds"] for r in valid) / len(valid)
        print(f"\nAverage total duration: {avg:.2f}s")

    return {
        "mode": mode,
        "cases": count,
        "schema_valid": schema_ok,
        "exact_matches": correct,
        "field_accuracy": {
            field: sum(r["fields"][field] for r in group) / count
            for field in FIELDS
        }
    }


def main():
    cases = json.loads(
        Path("test_cases.json").read_text(encoding="utf-8")
    )

    modes = ["zero_shot", "few_shot"]
    results = []

    for mode in modes:
        print(f"\n=== {mode.upper()} | thinking={THINKING} ===")

        for case in cases:
            print(f"Running {case['id']}...", flush=True)
            result = evaluate(case, mode)
            results.append(result)

            status = "PASS" if result["exact_match"] else "FAIL"
            print(f"  {status}")

            if not result["exact_match"]:
                failed = [
                    key for key, ok in result["fields"].items()
                    if not ok
                ]
                print("  Failed fields:", failed)
                if "actual" in result:
                    print("  Actual:", result["actual"])
                if "error" in result:
                    print("  Error:", result["error"])

    summaries = [
        summarize(results, mode) for mode in modes
    ]

    output = {
        "model": MODEL,
        "thinking": THINKING,
        "results": results,
        "summaries": summaries
    }

    filename = f"benchmark_thinking_{str(THINKING).lower()}.json"

    Path(filename).write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\nSaved: {filename}")


if __name__ == "__main__":
    main()
