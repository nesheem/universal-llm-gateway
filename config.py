# =============================================================================
# Universal LLM Gateway v1.1 — CONFIGURATION
# config.py = static settings only (ports, etc.)
# API keys are managed DYNAMICALLY via the web dashboard → config.json
# Do NOT add API keys here — use the dashboard "Add Slot" page instead.
# =============================================================================

VERSION = "1.1"
APP_NAME = "Universal LLM Gateway"

PROXY_PORT     = 8900
DASHBOARD_PORT = 8901
DASHBOARD_HOST = "0.0.0.0"

MAX_KEY_SLOTS = 100

# API_SLOTS is empty — manage keys via the web dashboard
API_SLOTS = []
