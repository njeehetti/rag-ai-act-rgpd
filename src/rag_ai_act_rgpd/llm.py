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
    # Réponse coupée (max_tokens atteint) ou prompt tronqué par la fenêtre de contexte.
    truncated: bool = False


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
        num_ctx: int = 8192,
        timeout_s: float = 180.0,
    ) -> None:
        self.model = model
        self._options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
            "seed": 0,
        }
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def warm_up(self) -> None:
        """Charge le modèle en mémoire GPU sans rien générer (évite ~10 s au 1er appel)."""
        self._client.post(
            "/api/generate",
            json={"model": self.model, "options": {"num_ctx": self._options["num_ctx"]}},
        ).raise_for_status()

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
            truncated=body.get("done_reason") == "length"
            or int(body.get("prompt_eval_count", 0)) >= self._options["num_ctx"],
        )
