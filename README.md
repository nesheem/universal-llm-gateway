# ⚡ Universal LLM Gateway v1.0

> **By [nesheem](https://github.com/nesheem)**

A self-hosted universal LLM API gateway that routes requests from any OpenAI-compatible client across 100 input slots from 19+ providers — with a single output key, real-time web dashboard, auto health checks, and benchmarking.

---

## What It Does

```
Your App  (OpenAI-compatible client)
      │
      │  ← one Output Key
      ▼
 Universal LLM Gateway v1.0   (port 8900)
      │
      │  ← picks the best healthy slot by rank
      ▼
 100 Input Slots
 [Gemini×N] [Groq×N] [OpenRouter×N] [DeepSeek×N] ...
```

You configure many free/cheap API keys across providers. The gateway health-checks them, benchmarks them, and routes every incoming request to the best available slot automatically. Your AI app only ever needs **one URL and one key**.

---

## Supported Providers

| Provider       | Notes                        |
|----------------|------------------------------|
| Google Gemini  | Free tier available          |
| Groq           | Ultra-fast inference         |
| OpenRouter     | 100s of free models          |
| Mistral        | EU-based                     |
| Cerebras       | Fastest inference            |
| SambaNova      | Fast Llama models            |
| GitHub Models  | Free with GitHub account     |
| LLM7           | Free endpoint                |
| LM Studio      | Local models                 |
| OpenAI         | GPT models                   |
| Anthropic      | Claude models                |
| DeepSeek       | Cheap & capable              |
| xAI / Grok     | Grok models                  |
| Together AI    | Open source models           |
| Kimi K2        | Moonshot AI                  |
| NVIDIA NIM     | GPU accelerated              |
| Cohere         | Command R+                   |
| Fireworks AI   | Fast open source             |
| Ollama         | Local models                 |

---

## Quick Start (Windows VPS)

```
1. Run install.bat   ← first time only
2. Run run.bat
3. Open http://YOUR_VPS_IP:8901
4. Go to Output Key  → copy your key
5. In your AI app:
     API Base URL : http://YOUR_VPS_IP:8900/v1
     API Key      : (paste output key)
     Model        : gemini-2.0-flash  (or any supported model)
```

---

## Configuration

Edit **`config.py`** to set ports:

```python
PROXY_PORT     = 8900   # OpenAI-compatible proxy
DASHBOARD_PORT = 8901   # Web dashboard
```

**API keys are managed entirely via the web dashboard** — use the "Add Slot" page.  
`config.json` is auto-generated and is listed in `.gitignore` — your keys stay local.

---

## Ports

| Port | Purpose                        |
|------|-------------------------------|
| 8900 | OpenAI-compatible proxy API    |
| 8901 | Web dashboard                  |

---

## Web Dashboard Features

| Page           | Description                                      |
|----------------|--------------------------------------------------|
| Overview       | Live health stats, provider breakdown, top slots |
| Output Key     | Copy / regenerate your single output key         |
| Input Slots    | All 100 slots — status, add / edit / delete      |
| Cost Tracking  | Per-provider spend tracking                      |
| Request Logs   | Real-time request history                        |
| Terminal       | Built-in command interface                       |
| Add Slot       | Add new API key slots from the UI                |

---

## File Structure

```
universal-llm-gateway/
├── main.py          — entry point + OpenAI-compatible proxy server
├── router.py        — routing engine, slot manager, benchmarker, cost tracker
├── dashboard.py     — web UI + REST API (all HTML inlined)
├── health_check.py  — direct httpx health checks (bypasses SSL issues)
├── ssl_patch.py     — Windows SSL fix (imported first in all files)
├── config.py        — static settings (edit this)
├── requirements.txt — Python dependencies
├── run.bat          — Windows start script
├── install.bat      — Windows first-time setup
├── .gitignore       — excludes config.json, logs, personal config
└── logs/            — hourly rotating log files (auto-created)
```

> `config.json` and `config_personal.py` are in `.gitignore` and will **never** be pushed to GitHub.

---

## How It Works (Architecture)

- **Health checks** use raw `httpx` with `verify=False` — this bypasses Windows Server SSL issues where provider SDKs cache broken SSL contexts.
- **Routing** uses [LiteLLM](https://github.com/BerriAI/litellm) as the provider translation layer — one unified interface to 100+ providers.
- **Benchmarking** runs a small test prompt on every healthy slot, measures tokens/sec and latency, and ranks slots. The best-ranked slot always gets the next request.
- **Rate limiting** is handled per-provider — when a slot hits a 429, it's automatically cooled down and removed from the routing pool.

---

## Changelog

### v1.0
- 100 input slots across 19+ providers
- Single output key (OpenAI-compatible)
- Web dashboard with real-time stats
- Cost tracking per provider
- Direct httpx health checks (Windows SSL compatible)
- Auto-benchmarking and slot ranking
- No hardcoded API keys — all managed via dashboard

---

## License

MIT — free to use, modify, and distribute.

---

*Built by [nesheem](https://github.com/nesheem)*
