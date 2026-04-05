"""
Universal LLM Gateway v1.0 — router.py
Core LiteLLM-powered routing engine.
Handles: provider translation, load balancing, cost tracking,
         health checks, benchmarking, request logging.
"""
import ssl_patch  # MUST be first

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
import litellm

# ── Silence litellm ───────────────────────────────────────────────────────────
litellm.suppress_debug_info  = True
litellm.set_verbose          = False
litellm.drop_params          = True   # ignore unsupported params per provider
litellm.num_retries          = 0      # we handle retries ourselves
litellm.ssl_verify           = False  # global SSL bypass

logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.client").setLevel(logging.ERROR)

logger = logging.getLogger("UniversalLLMGateway.Router")

# =============================================================================
# PROVIDER CONFIGURATION
# =============================================================================

# litellm model string prefix per provider
PROVIDER_PREFIX: Dict[str, str] = {
    "gemini":     "gemini",
    "groq":       "groq",
    "openai":     "",
    "anthropic":  "",
    "mistral":    "mistral",
    "deepseek":   "deepseek",
    "together":   "together_ai",
    "cerebras":   "cerebras",
    "openrouter": "openrouter",
    "ollama":     "ollama",
    "xai":        "xai",
    "sambanova":  "openai",
    "github":     "openai",
    "llm7":       "openai",
    "lmstudio":   "openai",
    "kimi":       "openai",
    "nvidia":     "openai",
    "cohere":     "cohere",
    "perplexity": "perplexity",
    "fireworks":  "fireworks_ai",
    "hyperbolic": "openai",
    "lepton":     "openai",
    "aiml":       "openai",
    "novita":     "openai",
}

# Providers that need explicit api_base
NEEDS_API_BASE = {
    "sambanova", "github", "llm7", "lmstudio", "kimi", "nvidia",
    "hyperbolic", "lepton", "aiml", "novita", "groq", "deepseek",
    "cerebras", "mistral", "together", "openrouter", "xai",
}

DEFAULT_BASE_URLS: Dict[str, str] = {
    "groq":       "https://api.groq.com/openai/v1",
    "cerebras":   "https://api.cerebras.ai/v1",
    "sambanova":  "https://api.sambanova.ai/v1",
    "mistral":    "https://api.mistral.ai/v1",
    "together":   "https://api.together.xyz/v1",
    "deepseek":   "https://api.deepseek.com/v1",
    "xai":        "https://api.x.ai/v1",
    "github":     "https://models.inference.ai.azure.com",
    "llm7":       "https://api.llm7.io/v1",
    "kimi":       "https://api.moonshot.cn/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

DEFAULT_MODELS: Dict[str, str] = {
    "gemini":     "gemini-2.0-flash",
    "groq":       "llama-3.3-70b-versatile",
    "openai":     "gpt-4o-mini",
    "anthropic":  "claude-3-5-sonnet-20241022",
    "mistral":    "mistral-small-latest",
    "deepseek":   "deepseek-chat",
    "together":   "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    "cerebras":   "llama-3.3-70b",
    "openrouter": "google/gemma-3-27b-it:free",
    "ollama":     "llama3",
    "xai":        "grok-4-1-fast",
    "sambanova":  "Meta-Llama-3.3-70B-Instruct",
    "github":     "gpt-4o-mini",
    "llm7":       "gpt-4o",
    "lmstudio":   "local-model",
    "kimi":       "kimi-k2",
    "nvidia":     "meta/llama-3.3-70b-instruct",
    "cohere":     "command-r-plus",
    "perplexity": "llama-3.1-sonar-small-128k-online",
    "fireworks":  "accounts/fireworks/models/llama-v3p3-70b-instruct",
}

# Cost per 1M tokens (USD) — approximate
COST_PER_1M: Dict[str, Dict[str, float]] = {
    "gemini":    {"input": 0.075, "output": 0.30},
    "groq":      {"input": 0.05,  "output": 0.10},
    "openai":    {"input": 0.15,  "output": 0.60},
    "anthropic": {"input": 3.0,   "output": 15.0},
    "deepseek":  {"input": 0.07,  "output": 0.28},
    "xai":       {"input": 2.0,   "output": 10.0},
    "mistral":   {"input": 0.20,  "output": 0.60},
    "cerebras":  {"input": 0.10,  "output": 0.10},
    "sambanova": {"input": 0.40,  "output": 0.60},
    "openrouter":{"input": 0.0,   "output": 0.0},
    "ollama":    {"input": 0.0,   "output": 0.0},
    "lmstudio":  {"input": 0.0,   "output": 0.0},
    "llm7":      {"input": 0.0,   "output": 0.0},
    "github":    {"input": 0.0,   "output": 0.0},
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Slot:
    """Represents one input API key slot."""
    id:           str
    provider:     str
    api_key:      str
    model_name:   str
    display_name: str
    base_url:     Optional[str]
    notes:        str
    slot_number:  int

    # Runtime state
    is_healthy:       bool  = False
    last_checked:     Optional[str] = None
    last_error:       Optional[str] = None
    rate_limited:     bool  = False
    rate_limit_until: Optional[str] = None

    # Performance
    rank:              int   = 999
    benchmark_score:   float = 0.0
    avg_latency_ms:    float = 9999.0
    tokens_per_second: float = 0.0
    success_rate:      float = 0.0

    # Stats
    total_requests:  int = 0
    failed_requests: int = 0
    total_cost_usd:  float = 0.0
    created_at:      str = field(default_factory=lambda: datetime.now().isoformat())

    def litellm_model(self) -> str:
        prefix = PROVIDER_PREFIX.get(self.provider, "openai")
        return f"{prefix}/{self.model_name}" if prefix else self.model_name

    def litellm_kwargs(self) -> dict:
        kw = {
            "model":       self.litellm_model(),
            "api_key":     self.api_key,
            "num_retries": 0,
            "ssl_verify":  False,
            "request_timeout": 120,
        }
        if self.provider in NEEDS_API_BASE:
            base = self.base_url or DEFAULT_BASE_URLS.get(self.provider, "")
            if base:
                if self.provider == "deepseek":
                    base = base.rstrip("/").removesuffix("/v1")
                kw["api_base"] = base
        if self.provider == "ollama":
            base = (self.base_url or "http://localhost:11434").rstrip("/").removesuffix("/v1")
            kw["api_base"] = base
        return kw

    def to_dict(self) -> dict:
        return {
            "id": self.id, "provider": self.provider,
            "api_key": ("*" * 8 + self.api_key[-4:]) if len(self.api_key) > 4 else "***",
            "model_name": self.model_name, "display_name": self.display_name,
            "base_url": self.base_url, "notes": self.notes,
            "slot_number": self.slot_number, "is_healthy": self.is_healthy,
            "last_checked": self.last_checked, "last_error": self.last_error,
            "rate_limited": self.rate_limited, "rank": self.rank,
            "benchmark_score": self.benchmark_score,
            "avg_latency_ms": self.avg_latency_ms,
            "tokens_per_second": self.tokens_per_second,
            "success_rate": self.success_rate,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "created_at": self.created_at,
        }


@dataclass
class RouteResult:
    content:      str
    model:        str
    provider:     str
    finish_reason: str = "stop"
    usage:        dict = field(default_factory=dict)
    latency_ms:   float = 0.0
    cost_usd:     float = 0.0


# =============================================================================
# SLOT MANAGER
# =============================================================================

class SlotManager:
    MAX_SLOTS = 100

    def __init__(self, config: dict):
        self.config = config
        self.slots:  List[Slot] = []
        self._load()

    def _load(self):
        self.slots = []
        for i, d in enumerate(self.config.get("slots", [])):
            self.slots.append(Slot(
                id=d.get("id", str(uuid.uuid4())),
                provider=d.get("provider", "gemini"),
                api_key=d.get("api_key", ""),
                model_name=d.get("model_name", "gemini-2.0-flash"),
                display_name=d.get("display_name", f"Slot {i+1}"),
                base_url=d.get("base_url"),
                notes=d.get("notes", ""),
                slot_number=d.get("slot_number", i + 1),
                is_healthy=d.get("is_healthy", False),
                last_checked=d.get("last_checked"),
                last_error=d.get("last_error"),
                rate_limited=d.get("rate_limited", False),
                rate_limit_until=d.get("rate_limit_until"),
                rank=d.get("rank", 999),
                benchmark_score=d.get("benchmark_score", 0.0),
                avg_latency_ms=d.get("avg_latency_ms", 9999.0),
                tokens_per_second=d.get("tokens_per_second", 0.0),
                success_rate=d.get("success_rate", 0.0),
                total_requests=d.get("total_requests", 0),
                failed_requests=d.get("failed_requests", 0),
                total_cost_usd=d.get("total_cost_usd", 0.0),
                created_at=d.get("created_at", datetime.now().isoformat()),
            ))
        logger.info(f"Loaded {len(self.slots)} input slots.")

    def save(self):
        self.config["slots"] = [{
            "id": s.id, "provider": s.provider, "api_key": s.api_key,
            "model_name": s.model_name, "display_name": s.display_name,
            "base_url": s.base_url, "notes": s.notes,
            "slot_number": s.slot_number, "is_healthy": s.is_healthy,
            "last_checked": s.last_checked, "last_error": s.last_error,
            "rate_limited": s.rate_limited, "rate_limit_until": s.rate_limit_until,
            "rank": s.rank, "benchmark_score": s.benchmark_score,
            "avg_latency_ms": s.avg_latency_ms,
            "tokens_per_second": s.tokens_per_second,
            "success_rate": s.success_rate,
            "total_requests": s.total_requests,
            "failed_requests": s.failed_requests,
            "total_cost_usd": s.total_cost_usd,
            "created_at": s.created_at,
        } for s in self.slots]
        cfg_path = Path(self.config.get("_config_path", "config.json"))
        cfg_path.write_text(json.dumps(self.config, indent=2, default=str), encoding="utf-8")

    def healthy(self) -> List[Slot]:
        now = datetime.now()
        result = []
        for s in self.slots:
            if not s.is_healthy:
                continue
            if s.rate_limited and s.rate_limit_until:
                try:
                    if datetime.fromisoformat(s.rate_limit_until) > now:
                        continue
                    else:
                        s.rate_limited = False
                except Exception:
                    pass
            result.append(s)
        return sorted(result, key=lambda x: x.rank)

    def add(self, provider: str, api_key: str, model_name: str = "",
            base_url: str = "", display_name: str = "", notes: str = "") -> Optional[Slot]:
        if len(self.slots) >= self.MAX_SLOTS:
            return None
        slot = Slot(
            id=str(uuid.uuid4()),
            provider=provider,
            api_key=api_key,
            model_name=model_name or DEFAULT_MODELS.get(provider, ""),
            display_name=display_name or f"{provider.title()} Slot {len(self.slots)+1}",
            base_url=base_url or None,
            notes=notes,
            slot_number=len(self.slots) + 1,
        )
        self.slots.append(slot)
        self.save()
        return slot

    def remove(self, slot_id: str) -> bool:
        n = len(self.slots)
        self.slots = [s for s in self.slots if s.id != slot_id]
        if len(self.slots) < n:
            for i, s in enumerate(self.slots):
                s.slot_number = i + 1
            self.save()
            return True
        return False

    def get(self, slot_id: str) -> Optional[Slot]:
        return next((s for s in self.slots if s.id == slot_id), None)


# =============================================================================
# HEALTH CHECKER  — uses direct httpx (NOT litellm) so SSL verify=False works
# =============================================================================

RATE_LIMIT_MINUTES = {
    "gemini": 61, "groq": 2, "openrouter": 2, "cerebras": 2,
    "deepseek": 10, "default": 5,
}


class HealthChecker:

    def __init__(self, slot_manager: SlotManager):
        self.sm = slot_manager
        self.last_check: Optional[str] = None

    async def check_one(self, slot: Slot, force: bool = False) -> bool:
        if slot.rate_limited and not force:
            if slot.rate_limit_until:
                try:
                    if datetime.fromisoformat(slot.rate_limit_until) > datetime.now():
                        return False
                except Exception:
                    pass
            slot.rate_limited = False

        from health_check import check_slot_direct
        healthy, error = await check_slot_direct(slot)

        slot.last_checked = datetime.now().isoformat()
        slot.is_healthy   = healthy

        if healthy:
            slot.last_error       = None
            slot.rate_limited     = False
            slot.rate_limit_until = None
        else:
            slot.last_error = error or "Unknown error"
            if error and ("rate" in error.lower() or "429" in error):
                mins = RATE_LIMIT_MINUTES.get(slot.provider, RATE_LIMIT_MINUTES["default"])
                slot.rate_limited     = True
                slot.rate_limit_until = (datetime.now() + timedelta(minutes=mins)).isoformat()

        return healthy

    async def check_all(self, force: bool = False):
        slots = self.sm.slots
        if not slots:
            return
        logger.info(f"Health check: {len(slots)} slots...")
        sem = asyncio.Semaphore(12)

        async def _chk(s):
            async with sem:
                await self.check_one(s, force)

        await asyncio.gather(*[_chk(s) for s in slots], return_exceptions=True)
        h = sum(1 for s in slots if s.is_healthy)
        r = sum(1 for s in slots if s.rate_limited)
        o = len(slots) - h - r
        logger.info(f"Health done: ✅ {h} healthy / ⏳ {r} rate-limited / ❌ {o} offline")
        self.last_check = datetime.now().isoformat()
        self.sm.save()


# =============================================================================
# BENCHMARKER
# =============================================================================

class Benchmarker:

    def __init__(self, slot_manager: SlotManager):
        self.sm = slot_manager
        self.last_benchmark: Optional[str] = None

    async def bench_one(self, slot: Slot):
        kw = {**slot.litellm_kwargs(),
              "messages":    [{"role": "user", "content": "Count 1 to 20."}],
              "max_tokens":  80,
              "temperature": 0.3,
              "timeout":     30}
        try:
            start    = time.time()
            resp     = await litellm.acompletion(**kw)
            latency  = (time.time() - start) * 1000
            usage    = dict(resp.usage) if resp.usage else {}
            tokens   = usage.get("completion_tokens") or usage.get("total_tokens", 20)
            elapsed  = max(time.time() - start, 0.001)
            tps      = tokens / elapsed
            slot.avg_latency_ms    = round(latency, 1)
            slot.tokens_per_second = round(tps, 2)
            slot.benchmark_score   = round(tps * 10 + 10000 / max(latency, 1), 2)
            slot.total_requests   += 1
            total = slot.total_requests
            slot.success_rate = round(((total - slot.failed_requests) / total) * 100, 1)
        except litellm.RateLimitError:
            slot.benchmark_score = 0
            slot.failed_requests += 1
            slot.last_error = "Rate limited during benchmark"
        except Exception as e:
            slot.benchmark_score = 0
            slot.failed_requests += 1
            slot.last_error = str(e)[:80]

    async def benchmark_all(self):
        healthy = [s for s in self.sm.slots if s.is_healthy]
        if not healthy:
            logger.info("No healthy slots to benchmark.")
            return
        logger.info(f"Benchmarking {len(healthy)} healthy slots...")
        sem = asyncio.Semaphore(5)

        async def _bench(s):
            async with sem:
                await self.bench_one(s)

        await asyncio.gather(*[_bench(s) for s in healthy], return_exceptions=True)
        self._rank()
        self.last_benchmark = datetime.now().isoformat()
        self.sm.save()
        logger.info("Benchmark complete.")

    def _rank(self):
        scored = sorted(
            [s for s in self.sm.slots if s.is_healthy and s.benchmark_score > 0],
            key=lambda x: x.benchmark_score, reverse=True,
        )
        for i, s in enumerate(scored, 1):
            s.rank = i
        for s in self.sm.slots:
            if not s.is_healthy or s.benchmark_score <= 0:
                s.rank = 999


# =============================================================================
# COST TRACKER
# =============================================================================

class CostTracker:

    def __init__(self, config: dict):
        self.config   = config
        self.log:     List[dict] = []
        self.by_provider: Dict[str, float] = defaultdict(float)
        self.total_usd: float = 0.0
        self._load()

    def _load(self):
        self.log      = self.config.get("cost_log", [])[-500:]
        self.total_usd = self.config.get("total_cost_usd", 0.0)
        for entry in self.log:
            self.by_provider[entry.get("provider", "?")] += entry.get("cost_usd", 0)

    def _save(self):
        self.config["cost_log"]       = self.log[-500:]
        self.config["total_cost_usd"] = self.total_usd

    def calculate(self, provider: str, input_tokens: int, output_tokens: int) -> float:
        rates = COST_PER_1M.get(provider, {"input": 0, "output": 0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000

    def record(self, provider: str, model: str, input_tokens: int,
               output_tokens: int, latency_ms: float):
        cost = self.calculate(provider, input_tokens, output_tokens)
        self.total_usd += cost
        self.by_provider[provider] += cost
        entry = {
            "ts": datetime.now().isoformat()[:19],
            "provider": provider, "model": model,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": round(cost, 8), "latency_ms": round(latency_ms, 1),
        }
        self.log.append(entry)
        if len(self.log) > 500:
            self.log = self.log[-500:]
        self._save()
        return cost

    def summary(self) -> dict:
        return {
            "total_usd":   round(self.total_usd, 6),
            "by_provider": {k: round(v, 6) for k, v in sorted(
                self.by_provider.items(), key=lambda x: x[1], reverse=True)},
            "recent":      self.log[-20:],
        }


# =============================================================================
# REQUEST LOG
# =============================================================================

class RequestLog:

    def __init__(self, config: dict):
        self.config = config
        self.entries: List[dict] = config.get("request_log", [])[-1000:]
        self.total_requests = config.get("total_requests", 0)
        self.total_failures = config.get("total_failures", 0)

    def record(self, slot_name: str, provider: str, model: str,
               status: str, latency_ms: float = 0,
               error: str = "", msg_preview: str = ""):
        entry = {
            "ts":          datetime.now().isoformat()[:19],
            "slot":        slot_name,
            "provider":    provider,
            "model":       model,
            "status":      status,
            "latency_ms":  round(latency_ms, 1),
            "error":       error[:120] if error else "",
            "preview":     msg_preview[:100] if msg_preview else "",
        }
        self.entries.append(entry)
        if len(self.entries) > 1000:
            self.entries = self.entries[-1000:]
        self.total_requests += 1
        if status == "failed":
            self.total_failures += 1
        self.config["request_log"]    = self.entries
        self.config["total_requests"] = self.total_requests
        self.config["total_failures"] = self.total_failures

    def stats(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "success_rate":   round(
                ((self.total_requests - self.total_failures) / max(self.total_requests, 1)) * 100, 1),
            "recent":         self.entries[-50:],
        }


# =============================================================================
# MAIN ROUTER
# =============================================================================

class ULGRouter:
    """
    The core universal LLM router.
    Accepts OpenAI-format requests and routes them to the best
    available input slot using litellm as the translation layer.
    """

    def __init__(self, slot_manager: SlotManager,
                 cost_tracker: CostTracker, request_log: RequestLog):
        self.sm   = slot_manager
        self.cost = cost_tracker
        self.log  = request_log

    def _preview(self, messages: list) -> str:
        if not messages:
            return ""
        content = messages[-1].get("content", "")
        if isinstance(content, list):
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        return str(content)[:100]

    async def route(self, messages: list, model: str = "ulg-auto",
                    temperature: float = 0.7, max_tokens: int = 4096,
                    stream: bool = False, top_p: float = 1.0,
                    stop=None, **extra) -> RouteResult:
        slots = self.sm.healthy()
        if not slots:
            raise RuntimeError(
                "No healthy input slots available. "
                "Run a health check from the dashboard."
            )

        max_tries = min(len(slots), 5)
        last_err  = None
        preview   = self._preview(messages)

        for i in range(max_tries):
            slot  = slots[i]
            start = time.time()
            kw    = {
                **slot.litellm_kwargs(),
                "messages":    messages,
                "temperature": temperature,
                "max_tokens":  max_tokens,
                "top_p":       top_p,
                "stream":      False,
                "timeout":     120,
            }
            if stop:
                kw["stop"] = stop

            try:
                logger.info(f"→ Routing to [{slot.display_name}] rank={slot.rank}")
                resp    = await litellm.acompletion(**kw)
                latency = (time.time() - start) * 1000

                content = resp.choices[0].message.content or ""
                usage   = dict(resp.usage) if resp.usage else {}
                finish  = resp.choices[0].finish_reason or "stop"
                in_tok  = usage.get("prompt_tokens", 0)
                out_tok = usage.get("completion_tokens", 0)
                cost    = self.cost.record(slot.provider, slot.model_name,
                                           in_tok, out_tok, latency)
                slot.total_requests += 1
                slot.total_cost_usd += cost
                n = slot.total_requests
                slot.success_rate = round(((n - slot.failed_requests) / n) * 100, 1)
                self.log.record(slot.display_name, slot.provider,
                                slot.model_name, "success", latency, "", preview)
                return RouteResult(
                    content=content, model=model,
                    provider=slot.provider, finish_reason=finish,
                    usage=usage, latency_ms=latency, cost_usd=cost,
                )
            except litellm.RateLimitError as e:
                slot.rate_limited     = True
                slot.rate_limit_until = (datetime.now() + timedelta(minutes=5)).isoformat()
                slot.failed_requests += 1
                last_err = str(e)
                self.log.record(slot.display_name, slot.provider,
                                slot.model_name, "failed", 0, "Rate limited", preview)
            except Exception as e:
                slot.failed_requests += 1
                last_err = str(e)
                self.log.record(slot.display_name, slot.provider,
                                slot.model_name, "failed", 0, last_err[:80], preview)
                logger.warning(f"Slot {slot.display_name} failed: {last_err[:80]}")

        raise RuntimeError(f"All {max_tries} slots failed. Last: {last_err}")

    async def route_stream(self, messages: list, model: str = "ulg-auto",
                           temperature: float = 0.7, max_tokens: int = 4096,
                           top_p: float = 1.0, stop=None,
                           **extra) -> AsyncIterator[str]:
        slots = self.sm.healthy()
        if not slots:
            raise RuntimeError("No healthy input slots available.")

        max_tries = min(len(slots), 5)
        last_err  = None
        preview   = self._preview(messages)

        for i in range(max_tries):
            slot = slots[i]
            kw = {
                **slot.litellm_kwargs(),
                "messages":    messages,
                "temperature": temperature,
                "max_tokens":  max_tokens,
                "top_p":       top_p,
                "stream":      True,
                "timeout":     120,
            }
            if stop:
                kw["stop"] = stop
            try:
                resp = await litellm.acompletion(**kw)
                slot.total_requests += 1
                async for chunk in resp:
                    if (chunk.choices and chunk.choices[0].delta
                            and chunk.choices[0].delta.content):
                        text = chunk.choices[0].delta.content
                        out  = {
                            "id":      f"chatcmpl-{uuid.uuid4().hex[:8]}",
                            "object":  "chat.completion.chunk",
                            "model":   model,
                            "choices": [{
                                "index":        0,
                                "delta":        {"content": text},
                                "finish_reason": None,
                            }],
                        }
                        yield f"data: {json.dumps(out)}\n\n"
                yield "data: [DONE]\n\n"
                self.log.record(slot.display_name, slot.provider,
                                slot.model_name, "success", 0, "", preview)
                return
            except litellm.RateLimitError as e:
                slot.rate_limited     = True
                slot.rate_limit_until = (datetime.now() + timedelta(minutes=5)).isoformat()
                slot.failed_requests += 1
                last_err = str(e)
            except Exception as e:
                slot.failed_requests += 1
                last_err = str(e)
                logger.warning(f"Stream slot {slot.display_name} failed: {last_err[:80]}")

        raise RuntimeError(f"All stream slots failed. Last: {last_err}")
