"""Thin clients for the language model. No vendor SDKs: plain HTTPS via httpx.

- AnthropicLLM: Claude models through the Anthropic Messages API.
- OpenAICompatibleLLM: OpenAI, OpenRouter, Groq, Together, a local Ollama server -
  anything that speaks the OpenAI chat-completions format.
- OfflineLLM: no API key needed. Quotes the best-matching passage. Used for demos,
  tests, and as an automatic fallback if the real provider errors out.
"""
from __future__ import annotations

import logging
import re

import httpx

from .config import Settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class BaseLLM:
    name = "base"

    def complete(self, system: str, messages: list[dict]) -> str:  # pragma: no cover
        raise NotImplementedError


class AnthropicLLM(BaseLLM):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.api_key, self.model, self.timeout = api_key, model or "claude-haiku-5-5", timeout

    def complete(self, system: str, messages: list[dict]) -> str:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": self.model, "max_tokens": 600, "system": system, "messages": messages},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise LLMError(f"Anthropic API {r.status_code}: {r.text[:200]}")
        data = r.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


class OpenAICompatibleLLM(BaseLLM):
    name = "openai"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        self.api_key, self.base_url, self.timeout = api_key, base_url.rstrip("/"), timeout
        self.model = model or "gpt-4o-mini"

    def complete(self, system: str, messages: list[dict]) -> str:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "max_tokens": 600,
                "temperature": 0.2,
                "messages": [{"role": "system", "content": system}, *messages],
            },
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise LLMError(f"OpenAI-compatible API {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"].strip()


class OfflineLLM(BaseLLM):
    """Answers by quoting the most relevant sentences of the top passage."""

    name = "offline"

    def complete(self, system: str, messages: list[dict]) -> str:
        context = re.search(r"<context>(.*?)</context>", system, re.S)
        question = messages[-1]["content"] if messages else ""
        if not context:
            return "Sorry, I couldn't find that in our documents."
        first = re.search(r"<passage[^>]*>(.*?)</passage>", context.group(1), re.S)
        text = (first.group(1) if first else context.group(1)).strip()
        q_words = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2}
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
        ranked = sorted(
            sentences,
            key=lambda s: -len(q_words & set(re.findall(r"[a-z0-9]+", s.lower()))),
        )
        best = [s for s in ranked[:3] if s]
        # keep original order for readability
        best.sort(key=sentences.index)
        return " ".join(best) or text[:400]


def make_llm(s: Settings) -> BaseLLM:
    if s.llm_provider == "anthropic":
        return AnthropicLLM(s.anthropic_api_key, s.llm_model, s.llm_timeout_s)
    if s.llm_provider == "openai":
        return OpenAICompatibleLLM(s.openai_api_key, s.openai_base_url, s.llm_model, s.llm_timeout_s)
    return OfflineLLM()
