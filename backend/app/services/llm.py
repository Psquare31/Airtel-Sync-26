"""Groq access with cooldown-aware model rotation.

Every call walks a chain of models. A 429 / quota error parks that model until
its reset time and the next model is tried; 5xx and timeouts get one retry.
When every model is unavailable the caller gets LLMUnavailable and falls back
to deterministic behaviour.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings

log = logging.getLogger("llm")

try:  # the SDK is optional at import time so tests can run without it
    import groq
except ImportError:  # pragma: no cover
    groq = None


class LLMUnavailable(Exception):
    pass


# per-model request tweaks (sent via extra_body)
MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "qwen/qwen3-32b": {"reasoning_format": "hidden"},
    "openai/gpt-oss-120b": {"reasoning_effort": "low"},
    "openai/gpt-oss-20b": {"reasoning_effort": "low"},
}


@dataclass
class CallInfo:
    model: str
    latency_ms: int
    tokens: int | None = None
    tried: list[str] = field(default_factory=list)


def _parse_reset(value: str | None) -> float | None:
    """Groq reset headers look like '2.5s', '1m3.2s', '450ms' or plain seconds."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    total, matched = 0.0, False
    for num, unit in re.findall(r"([\d.]+)(ms|h|m|s)", value):
        matched = True
        total += float(num) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total if matched else None


class ModelRouter:
    def __init__(self, client=None, default_cooldown_s: float = 30.0):
        self._client = client
        self._cooldowns: dict[str, float] = {}
        self._lock = threading.Lock()
        self.default_cooldown_s = default_cooldown_s
        self.last_call: CallInfo | None = None

    @property
    def client(self):
        if self._client is None:
            settings = get_settings()
            if not settings.groq_api_key or groq is None:
                raise LLMUnavailable("GROQ_API_KEY not configured")
            self._client = groq.Groq(
                api_key=settings.groq_api_key, max_retries=0, timeout=settings.llm_timeout_s
            )
        return self._client

    def available(self) -> bool:
        return bool(self._client) or bool(get_settings().groq_api_key)

    def cooling(self, model: str) -> bool:
        with self._lock:
            return self._cooldowns.get(model, 0) > time.monotonic()

    def cool_down(self, model: str, seconds: float) -> None:
        with self._lock:
            self._cooldowns[model] = time.monotonic() + max(seconds, 1.0)
        log.warning("model %s cooling down for %.0fs", model, seconds)

    def status(self, models: list[str]) -> list[dict]:
        now = time.monotonic()
        with self._lock:
            return [
                {"model": m, "cooldown_s": max(0, round(self._cooldowns.get(m, 0) - now))}
                for m in models
            ]

    def _cooldown_from_error(self, err) -> float:
        headers = getattr(getattr(err, "response", None), "headers", None) or {}
        for key in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
            secs = _parse_reset(headers.get(key))
            if secs:
                return secs
        return self.default_cooldown_s

    def chat(
        self,
        messages: list[dict],
        models: list[str] | None = None,
        json_mode: bool = False,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> tuple[str, CallInfo]:
        models = models or get_settings().chat_models
        tried: list[str] = []
        for model in models:
            if self.cooling(model):
                continue
            for attempt in range(2):
                tried.append(model)
                start = time.monotonic()
                try:
                    kwargs: dict[str, Any] = dict(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}
                    if model in MODEL_PARAMS:
                        kwargs["extra_body"] = MODEL_PARAMS[model]
                    resp = self.client.chat.completions.create(**kwargs)
                    text = resp.choices[0].message.content or ""
                    if json_mode:
                        json.loads(_strip_fences(text))  # malformed JSON -> next model
                    usage = getattr(resp, "usage", None)
                    info = CallInfo(
                        model=model,
                        latency_ms=int((time.monotonic() - start) * 1000),
                        tokens=getattr(usage, "total_tokens", None),
                        tried=tried,
                    )
                    self.last_call = info
                    log.info("llm ok model=%s ms=%s", model, info.latency_ms)
                    return _strip_fences(text) if json_mode else text, info
                except LLMUnavailable:
                    raise
                except Exception as err:  # noqa: BLE001 - classify below
                    status = getattr(err, "status_code", None)
                    if status == 429 or "rate_limit" in str(err).lower():
                        self.cool_down(model, self._cooldown_from_error(err))
                        break
                    if isinstance(err, json.JSONDecodeError) or status in (400, 404, 413, 422):
                        log.warning("model %s rejected request: %s", model, str(err)[:200])
                        break
                    if status in (401, 403):
                        raise LLMUnavailable("Groq rejected the API key") from err
                    log.warning("model %s attempt %d failed: %s", model, attempt + 1, str(err)[:200])
                    if attempt == 1:
                        self.cool_down(model, 10)
        raise LLMUnavailable(f"all models unavailable (tried {tried})")

    def chat_json(self, messages: list[dict], **kw) -> tuple[dict, CallInfo]:
        text, info = self.chat(messages, json_mode=True, **kw)
        return json.loads(text), info

    def vision_json(self, prompt: str, image_bytes: bytes, mime: str = "image/png") -> tuple[dict, CallInfo]:
        b64 = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ]
        return self.chat_json(messages, models=get_settings().vision_models, temperature=0, max_tokens=600)

    def guard(self, text: str) -> float | None:
        """Prompt-injection probability from Llama Prompt Guard 2, or None if unavailable."""
        model = get_settings().groq_guard_model
        if not self.available() or self.cooling(model):
            return None
        try:
            resp = self.client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": text[:2000]}]
            )
            content = (resp.choices[0].message.content or "").strip()
            try:
                return float(content)
            except ValueError:
                return 1.0 if re.search(r"malicious|jailbreak|injection", content, re.I) else 0.0
        except Exception as err:  # noqa: BLE001
            if getattr(err, "status_code", None) == 429:
                self.cool_down(model, self._cooldown_from_error(err))
            log.warning("guard unavailable: %s", str(err)[:120])
            return None

    def transcribe(self, audio: bytes, filename: str, language: str | None = None) -> str:
        kwargs: dict[str, Any] = {"file": (filename, audio), "model": get_settings().groq_stt_model}
        if language:
            kwargs["language"] = language
        try:
            return self.client.audio.transcriptions.create(**kwargs).text
        except LLMUnavailable:
            raise
        except Exception as err:  # noqa: BLE001
            raise LLMUnavailable(f"transcription failed: {str(err)[:120]}") from err


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    # some models wrap JSON in prose; keep the outermost object
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            text = m.group(0)
    return text


_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def set_router(router: ModelRouter | None) -> None:
    global _router
    _router = router


PII_PATTERNS = [
    (re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}\b"), "[GSTIN]"),
    (re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b", re.I), "[UDYAM]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[ID]"),
    (re.compile(r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b"), "[PHONE]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
]


def redact(text: str) -> str:
    """Strips identifiers before text leaves our boundary for the LLM."""
    for pattern, token in PII_PATTERNS:
        text = pattern.sub(token, text)
    return text
