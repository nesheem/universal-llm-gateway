"""
Universal LLM Gateway v1.0 — health_check.py
Direct httpx-based health checker — bypasses litellm and all its
internal SDK SSL handling. Uses verify=False directly on httpx.
"""
import ssl_patch  # must be first

import asyncio
import httpx
import logging
from typing import Optional

logger = logging.getLogger("UniversalLLMGateway.Health")

_TIMEOUT = httpx.Timeout(15.0)

OPENAI_COMPAT_PROVIDERS = {
    "groq":       "https://api.groq.com/openai/v1/chat/completions",
    "deepseek":   "https://api.deepseek.com/v1/chat/completions",
    "xai":        "https://api.x.ai/v1/chat/completions",
    "mistral":    "https://api.mistral.ai/v1/chat/completions",
    "cerebras":   "https://api.cerebras.ai/v1/chat/completions",
    "sambanova":  "https://api.sambanova.ai/v1/chat/completions",
    "github":     "https://models.inference.ai.azure.com/chat/completions",
    "llm7":       "https://api.llm7.io/v1/chat/completions",
    "together":   "https://api.together.xyz/v1/chat/completions",
    "kimi":       "https://api.moonshot.cn/v1/chat/completions",
    "nvidia":     "https://integrate.api.nvidia.com/v1/chat/completions",
    "openai":     "https://api.openai.com/v1/chat/completions",
    "lmstudio":   None,  # uses base_url
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "hyperbolic": "https://api.hyperbolic.xyz/v1/chat/completions",
    "lepton":     None,
    "aiml":       None,
    "novita":     None,
    "perplexity": "https://api.perplexity.ai/chat/completions",
    "fireworks":  "https://api.fireworks.ai/inference/v1/chat/completions",
    "cohere":     None,
}

SMALL_CHAT_BODY = {
    "messages": [{"role": "user", "content": "Hi"}],
    "max_tokens": 5,
    "stream": False,
}


async def check_slot_direct(slot) -> tuple[bool, Optional[str]]:
    """
    Direct httpx health check — never uses litellm.
    Returns (is_healthy, error_message).
    """
    provider = slot.provider
    api_key  = slot.api_key
    base_url = slot.base_url
    model    = slot.model_name

    try:
        # ── Gemini: native REST API ──────────────────────────────────────
        if provider == "gemini":
            url  = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            body = {"contents": [{"parts": [{"text": "Hi"}]}],
                    "generationConfig": {"maxOutputTokens": 5}}
            async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as c:
                r = await c.post(url, json=body, params={"key": api_key})
            if r.status_code in (200, 400):
                return True, None
            if r.status_code == 429:
                return False, "Rate limited"
            if r.status_code in (401, 403):
                return False, f"Auth error ({r.status_code})"
            return False, f"HTTP {r.status_code}"

        # ── Anthropic: custom format ──────────────────────────────────────
        if provider == "anthropic":
            url  = "https://api.anthropic.com/v1/messages"
            body = {"model": model, "max_tokens": 5,
                    "messages": [{"role": "user", "content": "Hi"}]}
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01",
                       "content-type": "application/json"}
            async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as c:
                r = await c.post(url, json=body, headers=headers)
            if r.status_code in (200, 400):
                return True, None
            if r.status_code == 429:
                return False, "Rate limited"
            if r.status_code in (401, 403):
                return False, "Auth error"
            return False, f"HTTP {r.status_code}"

        # ── Ollama: local REST ───────────────────────────────────────────
        if provider == "ollama":
            base = (base_url or "http://localhost:11434").rstrip("/").removesuffix("/v1")
            async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as c:
                r = await c.get(f"{base}/api/tags")
            return r.status_code == 200, None if r.status_code == 200 else f"HTTP {r.status_code}"

        # ── OpenAI-compatible providers ──────────────────────────────────
        url = None
        if provider in OPENAI_COMPAT_PROVIDERS:
            url = OPENAI_COMPAT_PROVIDERS[provider]
        if url is None and base_url:
            url = base_url.rstrip("/")
            if not url.endswith("/chat/completions"):
                url = url.rstrip("/v1") + "/v1/chat/completions"
        if url is None:
            return False, f"No endpoint for provider '{provider}'"

        body = {**SMALL_CHAT_BODY, "model": model}
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://ulg-engine.local"
            headers["X-Title"]      = "Universal LLM Gateway v1.0"

        async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as c:
            r = await c.post(url, json=body, headers=headers)

        if r.status_code in (200, 400, 422):
            return True, None
        if r.status_code == 429:
            return False, "Rate limited"
        if r.status_code in (401, 403):
            return False, f"Auth error ({r.status_code})"
        if r.status_code == 402:
            return False, "No credits"
        if r.status_code == 404:
            return True, None
        return False, f"HTTP {r.status_code}: {r.text[:80]}"

    except httpx.ConnectTimeout:
        return False, "Connection timeout"
    except httpx.ConnectError as e:
        return False, f"Connect error: {str(e)[:60]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"
