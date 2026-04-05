"""
Universal LLM Gateway v1.0 — main.py
Entry point. ssl_patch MUST be the first import.
"""
import ssl_patch  # ← fixes Windows async SSL — must be first

import asyncio
import base64
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

# ── Logging ───────────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
_fh = TimedRotatingFileHandler("logs/ulg.log", when="h", interval=1,
                                backupCount=24, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), _fh],
)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logger = logging.getLogger("UniversalLLMGateway")

CONFIG_PATH = Path("config.json")

# =============================================================================
# CONFIG
# =============================================================================

def _read_config_py() -> dict:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_cfg", Path("config.py"))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {
            "proxy_port":     getattr(mod, "PROXY_PORT", 8900),
            "dashboard_port": getattr(mod, "DASHBOARD_PORT", 8901),
            "api_slots":      getattr(mod, "API_SLOTS", []),
        }
    except Exception as e:
        logger.warning(f"config.py read failed: {e}")
        return {}


def load_config() -> dict:
    static = _read_config_py()
    if not CONFIG_PATH.exists():
        cfg = {
            "engine":         "Universal LLM Gateway v1.0",
            "version":        "1.0",
            "proxy_port":     static.get("proxy_port", 8900),
            "dash_port":      static.get("dashboard_port", 8901),
            "output_key":     _make_output_key_entry(),
            "slots":          [],
            "cost_log":       [],
            "request_log":    [],
            "total_cost_usd": 0.0,
            "total_requests": 0,
            "total_failures": 0,
        }
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["version"]      = "1.0"
    cfg["engine"]       = "Universal LLM Gateway v1.0"
    cfg["_config_path"] = str(CONFIG_PATH)

    # Migrate old key format
    if "master_keys" in cfg and "output_key" not in cfg:
        old = cfg["master_keys"]
        if old:
            cfg["output_key"] = {
                "key": old[0]["key"], "name": "Output Key",
                "active": True, "usage_count": 0, "notes": "",
                "created_at": old[0].get("created_at", datetime.now().isoformat()),
            }
        del cfg["master_keys"]
    if "output_key" not in cfg:
        cfg["output_key"] = _make_output_key_entry()
    if "model_keys" in cfg and not cfg.get("slots"):
        cfg["slots"] = cfg.pop("model_keys")
        for s in cfg["slots"]:
            s.setdefault("id", str(uuid.uuid4()))

    return cfg


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, default=str), encoding="utf-8")


def _make_output_key_entry() -> dict:
    raw = os.urandom(24)
    b64 = base64.urlsafe_b64encode(raw).decode().rstrip("=")[:35]
    return {
        "key":         f"AIzaSy{b64}",
        "name":        "Output Key",
        "active":      True,
        "usage_count": 0,
        "notes":       "",
        "created_at":  datetime.now().isoformat(),
    }


def _bootstrap_slots(cfg: dict):
    """Import API_SLOTS from config.py into config.json on first run."""
    static = _read_config_py()
    slots_cfg = cfg.get("slots", [])
    existing_keys = {s.get("api_key") for s in slots_cfg if s.get("api_key")}
    added = 0

    for i, sl in enumerate(static.get("api_slots", []), 1):
        ak  = sl.get("api_key", "").strip()
        prv = sl.get("provider", "gemini")
        if not ak and prv not in ("ollama", "lmstudio"):
            continue
        if ak and ak in existing_keys:
            continue
        if len(slots_cfg) >= 100:
            break
        slots_cfg.append({
            "id":           str(uuid.uuid4()),
            "provider":     prv,
            "api_key":      ak,
            "model_name":   sl.get("model_name") or "",
            "display_name": sl.get("display_name", f"Slot {i}"),
            "base_url":     sl.get("base_url"),
            "notes":        sl.get("notes", ""),
            "slot_number":  len(slots_cfg) + 1,
            "is_healthy":   False,
            "created_at":   datetime.now().isoformat(),
        })
        if ak:
            existing_keys.add(ak)
        added += 1

    if added:
        cfg["slots"] = slots_cfg
        save_config(cfg)
        logger.info(f"Imported {added} slots from config.py")


# =============================================================================
# OUTPUT KEY MANAGER
# =============================================================================

class OutputKeyManager:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        if "output_key" not in cfg:
            cfg["output_key"] = _make_output_key_entry()
            save_config(cfg)

    @property
    def entry(self) -> dict:
        return self.cfg["output_key"]

    @property
    def key(self) -> str:
        return self.cfg["output_key"]["key"]

    def validate(self, key: str) -> bool:
        ok = self.cfg["output_key"]
        if ok.get("active", True) and ok["key"] == key:
            ok["usage_count"] = ok.get("usage_count", 0) + 1
            return True
        return False

    def regenerate(self) -> str:
        new = _make_output_key_entry()
        self.cfg["output_key"]["key"]         = new["key"]
        self.cfg["output_key"]["created_at"]  = new["created_at"]
        self.cfg["output_key"]["usage_count"] = 0
        save_config(self.cfg)
        return new["key"]

    def set_active(self, v: bool):
        self.cfg["output_key"]["active"] = v
        save_config(self.cfg)

    def set_note(self, v: str):
        self.cfg["output_key"]["notes"] = v
        save_config(self.cfg)


# =============================================================================
# SCHEDULERS
# =============================================================================

async def _hourly_health(hc):
    while True:
        now      = datetime.now()
        next_run = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_run - now).total_seconds())
        logger.info("Hourly health check")
        await hc.check_all()

async def _daily_benchmark(hc, bm):
    while True:
        now  = datetime.now()
        tmrw = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep((tmrw - now).total_seconds())
        logger.info("Daily benchmark (midnight)")
        await hc.check_all()
        await bm.benchmark_all()


# =============================================================================
# PROXY SERVER (FastAPI)
# =============================================================================

def build_proxy(cfg, output_key_mgr: OutputKeyManager, router):
    from fastapi import FastAPI, Request, HTTPException, Header
    from fastapi.responses import JSONResponse, StreamingResponse

    app = FastAPI(title="Universal LLM Gateway v1.0", version="1.0",
                  docs_url=None, redoc_url=None)

    def _key(auth: Optional[str]) -> Optional[str]:
        if not auth:
            return None
        return auth[7:] if auth.startswith("Bearer ") else auth

    @app.get("/")
    async def root():
        slots   = router.sm.slots
        healthy = sum(1 for s in slots if s.is_healthy)
        return {
            "name":    "Universal LLM Gateway v1.0",
            "status":  "running",
            "slots":   f"{len(slots)}/100",
            "healthy": healthy,
            "version": "1.0",
        }

    @app.get("/v1/models")
    @app.get("/models")
    async def list_models(authorization: Optional[str] = Header(None)):
        if not output_key_mgr.validate(_key(authorization) or ""):
            raise HTTPException(401, "Invalid output key")
        models = [
            "ulg-auto", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
            "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo",
            "claude-3-5-sonnet-20241022", "claude-3-opus-20240229",
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
            "deepseek-chat", "deepseek-reasoner",
            "grok-4-1-fast", "grok-3-mini-fast",
            "kimi-k2", "mistral-small-latest",
            "Meta-Llama-3.3-70B-Instruct", "cerebras/llama-3.3-70b",
            "openrouter/auto",
        ]
        return {
            "object": "list",
            "data":   [{"id": m, "object": "model",
                        "created": int(time.time()), "owned_by": "ulg-engine"}
                       for m in models],
        }

    @app.post("/v1/chat/completions")
    @app.post("/chat/completions")
    async def chat(request: Request, authorization: Optional[str] = Header(None)):
        k = _key(authorization) or ""
        if not output_key_mgr.validate(k):
            raise HTTPException(401, {
                "error": {"message": "Invalid output key. Use your Universal LLM Gateway output key.",
                          "type": "invalid_request_error", "code": "invalid_api_key"}})
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Invalid JSON")

        requested_model = body.get("model", "ulg-auto")
        params = {
            "messages":    body.get("messages", []),
            "model":       requested_model,
            "temperature": body.get("temperature", 0.7),
            "max_tokens":  body.get("max_tokens", 4096),
            "top_p":       body.get("top_p", 1.0),
            "stop":        body.get("stop"),
        }

        if body.get("stream", False):
            async def gen():
                failed  = False
                err_msg = ""
                try:
                    async for chunk in router.route_stream(**params):
                        yield chunk
                except Exception as e:
                    failed  = True
                    err_msg = str(e)
                if failed:
                    ec = {"id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                          "object": "chat.completion.chunk",
                          "model": requested_model,
                          "choices": [{"index": 0,
                                       "delta": {"content": f"\n\n[ULG Error: {err_msg}]"},
                                       "finish_reason": "stop"}]}
                    yield f"data: {json.dumps(ec)}\n\n"
                    yield "data: [DONE]\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache"})

        try:
            result = await router.route(**params)
            return JSONResponse({
                "id":      f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object":  "chat.completion",
                "created": int(time.time()),
                "model":   requested_model,
                "choices": [{"index": 0,
                             "message": {"role": "assistant", "content": result.content},
                             "finish_reason": result.finish_reason}],
                "usage": result.usage or {"prompt_tokens": 0,
                                          "completion_tokens": 0, "total_tokens": 0},
                "system_fingerprint": "ulg-engine-v1",
            })
        except Exception as e:
            logger.error(f"Route failed: {e}")
            raise HTTPException(503, {"error": {"message": str(e), "type": "server_error"}})

    return app


# =============================================================================
# MAIN
# =============================================================================

async def main():
    cfg = load_config()
    cfg["_config_path"] = str(CONFIG_PATH)
    _bootstrap_slots(cfg)
    save_config(cfg)

    from router import SlotManager, HealthChecker, Benchmarker, CostTracker, RequestLog, ULGRouter
    from dashboard import DashboardServer

    sm     = SlotManager(cfg)
    hc     = HealthChecker(sm)
    bm     = Benchmarker(sm)
    ct     = CostTracker(cfg)
    rl     = RequestLog(cfg)
    router = ULGRouter(sm, ct, rl)
    okm    = OutputKeyManager(cfg)

    proxy_port = cfg.get("proxy_port", 8900)
    dash_port  = cfg.get("dash_port", 8901)

    print()
    print("=" * 64)
    print("   UNIVERSAL LLM GATEWAY v1.0")
    print("=" * 64)
    print(f"  Proxy API   : http://0.0.0.0:{proxy_port}/v1")
    print(f"  Dashboard   : http://0.0.0.0:{dash_port}")
    print(f"  Input Slots : {len(sm.slots)}/100")
    print(f"  Health Check: every 1h")
    print(f"  Benchmark   : daily at 00:00")
    print("=" * 64)
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║  OUTPUT KEY — paste into your AI app                ║")
    print(f"  ║  {okm.key:<52} ║")
    print(f"  ║  Base URL: http://VPS_IP:{proxy_port}/v1{'':>20} ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    logger.info("Initial health check...")
    await hc.check_all()

    h = sum(1 for s in sm.slots if s.is_healthy)
    if h == 0:
        logger.warning("No healthy slots after health check!")
    else:
        logger.info(f"{h}/{len(sm.slots)} healthy — benchmarking...")
        await bm.benchmark_all()

    save_config(cfg)

    proxy_app = build_proxy(cfg, okm, router)
    dashboard = DashboardServer(
        cfg=cfg, slot_manager=sm, output_key_mgr=okm,
        health_checker=hc, benchmarker=bm,
        router=router, cost_tracker=ct, request_log=rl,
    )

    import uvicorn

    async def _proxy():
        c = uvicorn.Config(app=proxy_app, host="0.0.0.0", port=proxy_port,
                           log_level="warning", access_log=False)
        await uvicorn.Server(c).serve()

    logger.info("Universal LLM Gateway v1.0 running!")

    await asyncio.gather(
        asyncio.create_task(_proxy()),
        asyncio.create_task(dashboard.start()),
        asyncio.create_task(_hourly_health(hc)),
        asyncio.create_task(_daily_benchmark(hc, bm)),
    )


if __name__ == "__main__":
    asyncio.run(main())
