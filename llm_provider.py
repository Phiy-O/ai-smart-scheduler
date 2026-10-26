
import os
from typing import Any

from ollama import Client


class OllamaProvider:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "qwen3:4b")
        self.client = Client(
            host=os.getenv(
                "OLLAMA_HOST",
                "http://localhost:11434"
            )
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
    ) -> str:
        response = self.client.chat(
            model=self.model,
            messages=messages,
            format=schema,
            think=False,
            options={
                "temperature": 0,
                "num_ctx": 4096
            },
        )
        return response.message.content or ""
