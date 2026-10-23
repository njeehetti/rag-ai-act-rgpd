"""Interface LLM unique : le fournisseur se change dans .env sans toucher au reste du code."""

import time
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMClient(Protocol):
    model: str

    def complete(self, messages: list[Message]) -> Completion: ...


class OllamaClient:
    """LLM local servi par Ollama (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout_s: float = 180.0,
    ) -> None:
        self.model = model
        self._options = {"temperature": temperature, "num_predict": max_tokens, "seed": 0}
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def complete(self, messages: list[Message]) -> Completion:
        start = time.perf_counter()
        response = self._client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
                # Pas de phase de « réflexion » (Qwen3) : réponses plus rapides et
                # prévisibles ; on demande une réponse factuelle courte et sourcée.
                "think": False,
                "options": self._options,
            },
        )
        response.raise_for_status()
        body = response.json()
        return Completion(
            text=body["message"]["content"].strip(),
            model=body["model"],
            input_tokens=int(body.get("prompt_eval_count", 0)),
            output_tokens=int(body.get("eval_count", 0)),
            latency_ms=(time.perf_counter() - start) * 1000,
        )
