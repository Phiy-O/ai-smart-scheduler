
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)

from llm_provider import OllamaProvider


Period = Literal["morning", "afternoon", "evening"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# STAGE 1: INTENT CLASSIFICATION

class IntentResult(StrictModel):
    action: Literal[
        "create", "update", "reschedule",
        "delete", "clarify"
    ]


# SHARED DATA STRUCTURES

class Target(StrictModel):
    task_name: str = Field(min_length=1)
    date_reference: Literal["today", "tomorrow"] | None = None


class Changes(StrictModel):
    duration_minutes: int | None = Field(default=None, ge=1)
    preferred_period: Period | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if (
            self.duration_minutes is None
            and self.preferred_period is None
        ):
            raise ValueError("Tidak ada perubahan yang diberikan")
        return self


# STAGE 2: OPERATION-SPECIFIC COMMANDS

class CreateCommand(StrictModel):
    action: Literal["create"]
    task_name: str = Field(min_length=1)
    duration_minutes: int | None = Field(default=None, ge=1)
    date_reference: Literal["today", "tomorrow"] | None = None
    preferred_period: Period | None = None


class UpdateCommand(StrictModel):
    action: Literal["update"]
    target: Target
    changes: Changes


class RescheduleCommand(StrictModel):
    action: Literal["reschedule"]
    target: Target
    new_date_reference: Literal[
        "today", "tomorrow"
    ] | None = None
    new_period: Period | None = None

    @model_validator(mode="after")
    def validate_destination(self):
        if (
            self.new_date_reference is None
            and self.new_period is None
        ):
            raise ValueError("Tujuan pemindahan tidak ada")
        return self


class DeleteCommand(StrictModel):
    action: Literal["delete"]
    target: Target


class ClarifyCommand(StrictModel):
    action: Literal["clarify"]
    clarification_question: str = Field(min_length=1)


# DISCRIMINATED UNION

ScheduleCommand = Annotated[
    Union[
        CreateCommand,
        UpdateCommand,
        RescheduleCommand,
        DeleteCommand,
        ClarifyCommand,
    ],
    Field(discriminator="action"),
]

command_adapter = TypeAdapter(ScheduleCommand)

COMMAND_MODELS = {
    "create": CreateCommand,
    "update": UpdateCommand,
    "reschedule": RescheduleCommand,
    "delete": DeleteCommand,
    "clarify": ClarifyCommand,
}


INTENT_PROMPT = """
Klasifikasikan instruksi pengguna.

Pilih tepat satu:
- create: menambahkan aktivitas baru
- update: mengubah atribut aktivitas
- reschedule: memindahkan waktu aktivitas
- delete: menghapus aktivitas
- clarify: maksud atau tindakan tidak jelas

Hanya tentukan jenis operasi.
Jangan mengekstraksi parameter lainnya.
"""


EXTRACTION_PROMPT = """
Kamu adalah instruction parser AI Smart Scheduler.

Ekstrak informasi yang BENAR-BENAR disebutkan pengguna.

Aturan:
- Jangan mengarang nama, durasi, tanggal, atau periode.
- Pagi = morning.
- Siang/sore = afternoon.
- Malam = evening.
- Hari ini = today.
- Besok = tomorrow.
- 1 jam = 60 menit; 2 jam = 120 menit.
- Jika informasi tidak disebutkan, gunakan null.
- Pertahankan nama aktivitas dalam bahasa Indonesia.

Definisi field:
- target = aktivitas yang sudah ada dan ingin ditemukan.
- changes = atribut yang diminta untuk diubah.
- new_period = periode tujuan pemindahan.
- new_date_reference = tanggal BARU tujuan pemindahan.
- date_reference dalam target = tanggal untuk mencari
  aktivitas lama, bukan tanggal baru.

Jika pengguna hanya mengatakan "pindahkan ke sore",
isi new_period=afternoon.

Jangan mengarang perubahan tambahan.
Output hanya JSON sesuai schema.
"""


class CommandParser:
    def __init__(self, provider=None):
        self.provider = provider or OllamaProvider()

    def _generate(self, system_prompt, instruction, model):
        raw = self.provider.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": instruction},
            ],
            schema=model.model_json_schema(),
        )
        return model.model_validate_json(raw)

    def parse(self, instruction: str):
        if not instruction.strip():
            return ClarifyCommand(
                action="clarify",
                clarification_question=(
                    "Aktivitas apa yang ingin kamu kelola?"
                ),
            )

        # Stage 1
        intent = self._generate(
            INTENT_PROMPT,
            instruction,
            IntentResult,
        )

        # Stage 2
        command_model = COMMAND_MODELS[intent.action]

        prompt = (
            EXTRACTION_PROMPT
            + f"\nOperasi wajib: {intent.action}."
        )

        extracted = self._generate(
            prompt,
            instruction,
            command_model,
        )

        # Validate the complete union contract
        return command_adapter.validate_python(
            extracted.model_dump()
        )


def review_command(command: ScheduleCommand) -> dict:
    data = command.model_dump()

    if command.action == "clarify":
        return {
            "status": "needs_clarification",
            "question": command.clarification_question,
        }

    if command.action == "create":
        if command.duration_minutes is None:
            return {
                "status": "needs_clarification",
                "question": (
                    f"Berapa lama aktivitas "
                    f"'{command.task_name}' berlangsung?"
                ),
            }

        return {
            "status": "needs_scheduling",
            "message": (
                "Cari slot valid sebelum mengajukan "
                "persetujuan pembuatan jadwal."
            ),
            "proposal": data,
        }

    return {
        "status": "needs_target_resolution",
        "message": (
            "Temukan aktivitas yang tepat, validasi "
            "perubahan, lalu minta persetujuan pengguna."
        ),
        "proposal": data,
    }
