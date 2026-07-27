"""LiteLLM HTTP client — all LLM/embedding calls go through the gateway."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class LiteLLMClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.litellm_base_url.rstrip("/")
        self.api_key = settings.litellm_api_key
        self.embedding_model = settings.embedding_model
        self.chat_model = settings.chat_model

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": model or self.embedding_model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # Ensure order matches input
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            # Some LiteLLM builds also expose /chat/completions without /v1
            if resp.status_code == 404:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]
