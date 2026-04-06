"""Universal LLM Gateway v1.1 — ssl_patch.py  (MUST be first import everywhere)

Fixes:
  1. Windows async SSL — sets WindowsSelectorEventLoopPolicy (required for aiohttp/asyncio on Windows)
  2. SSL verification — uses certifi CA bundle by default (secure).
     Set env var ULG_DISABLE_SSL_VERIFY=1 ONLY if you have a self-signed cert
     or a corporate MITM proxy you cannot work around any other way.
  3. DNS diagnostics — provides a reusable check_dns() helper for startup pre-flight.
"""
import os
import sys

# ── Optional SSL bypass (opt-in only, NOT recommended) ───────────────────────
_force_no_verify = os.environ.get("ULG_DISABLE_SSL_VERIFY", "0").strip() == "1"

if _force_no_verify:
    # User explicitly opted in — disable verification everywhere
    os.environ.update({
        "PYTHONHTTPSVERIFY": "0",
        "LITELLM_SSL_VERIFY": "false",
        "HTTPX_NO_VERIFY":    "1",
        "CURL_CA_BUNDLE":     "",
        "REQUESTS_CA_BUNDLE": "",
        "SSL_CERT_FILE":      "",
    })
    try:
        import ssl
        _orig_ctx = ssl.create_default_context
        def _no_verify_ctx(*a, **k):
            ctx = _orig_ctx(*a, **k)
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE
            return ctx
        ssl.create_default_context = _no_verify_ctx
        ssl._create_default_https_context = ssl._create_unverified_context
    except Exception:
        pass

    try:
        import httpx
        _orig_async = httpx.AsyncClient.__init__
        def _patched_async(self, *a, verify=False, **k):
            _orig_async(self, *a, verify=verify, **k)
        httpx.AsyncClient.__init__ = _patched_async

        _orig_sync = httpx.Client.__init__
        def _patched_sync(self, *a, verify=False, **k):
            _orig_sync(self, *a, verify=verify, **k)
        httpx.Client.__init__ = _patched_sync
    except Exception:
        pass

    try:
        import aiohttp
        _orig_tcp = aiohttp.TCPConnector.__init__
        def _patched_tcp(self, *a, ssl=False, **k):
            _orig_tcp(self, *a, ssl=ssl, **k)
        aiohttp.TCPConnector.__init__ = _patched_tcp

        _orig_sess = aiohttp.ClientSession.__init__
        def _patched_sess(self, *a, connector=None, **k):
            if connector is None:
                connector = aiohttp.TCPConnector(ssl=False)
            _orig_sess(self, *a, connector=connector, **k)
        aiohttp.ClientSession.__init__ = _patched_sess
    except Exception:
        pass

else:
    # Default: use certifi CA bundle for proper SSL verification
    try:
        import certifi
        ca_bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE",      ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
        os.environ.setdefault("CURL_CA_BUNDLE",     ca_bundle)
    except ImportError:
        pass  # certifi not installed — rely on system certs


# ── Windows event loop fix (always applied) ───────────────────────────────────
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ── aiohttp DNS fix (CRITICAL for Windows VPS) ───────────────────────────────
# aiohttp's default async DNS resolver (aiodns/pycares) cannot read Windows
# DNS settings, causing "Could not contact DNS servers" on every request even
# though synchronous socket.getaddrinfo() works fine.
# Fix: force aiohttp to use ThreadedResolver (wraps the synchronous OS resolver)
# and pre-seed a fallback connector that uses public DNS (8.8.8.8, 1.1.1.1)
# via an AsyncResolver when aiodns IS available but system DNS is misconfigured.
def _patch_aiohttp_dns():
    try:
        import aiohttp
        import aiohttp.resolver

        # Strategy 1: Use ThreadedResolver — always works on Windows because it
        # delegates to socket.getaddrinfo() (same path as the passing preflight).
        _OrigConnector = aiohttp.TCPConnector.__init__

        def _patched_connector(self, *args, resolver=None, **kwargs):
            if resolver is None:
                try:
                    resolver = aiohttp.AsyncResolver(
                        nameservers=["8.8.8.8", "1.1.1.1", "8.8.4.4"]
                    )
                except Exception:
                    resolver = aiohttp.ThreadedResolver()
            _OrigConnector(self, *args, resolver=resolver, **kwargs)

        aiohttp.TCPConnector.__init__ = _patched_connector

    except Exception:
        pass  # aiohttp not installed yet — litellm will install it later

_patch_aiohttp_dns()

# Also configure litellm to use httpx (which uses the system resolver) as a
# fallback transport preference where possible.
try:
    import litellm as _ll
    _ll.client_session = None   # reset any cached broken session
except Exception:
    pass


# ── DNS pre-flight helper ─────────────────────────────────────────────────────
def check_dns(hosts: list = None, timeout: float = 5.0) -> dict:
    """
    Synchronously check DNS resolution for a list of API hosts.
    Returns dict: { host: True/False }
    Call this at startup to warn users about network issues before routing begins.
    """
    import socket
    hosts = hosts or [
        "api.groq.com",
        "generativelanguage.googleapis.com",
        "api.openai.com",
        "api.anthropic.com",
        "api.mistral.ai",
    ]
    results = {}
    for host in hosts:
        try:
            socket.setdefaulttimeout(timeout)
            socket.getaddrinfo(host, 443)
            results[host] = True
        except Exception:
            results[host] = False
    return results
