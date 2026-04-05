"""Universal LLM Gateway v1.0 — ssl_patch.py  (MUST be first import everywhere)"""
import os, sys

os.environ.update({"PYTHONHTTPSVERIFY":"0","LITELLM_SSL_VERIFY":"false",
    "HTTPX_NO_VERIFY":"1","CURL_CA_BUNDLE":"","REQUESTS_CA_BUNDLE":"","SSL_CERT_FILE":""})

try:
    import ssl
    _o = ssl.create_default_context
    def _f(*a,**k):
        ctx=_o(*a,**k); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE; return ctx
    ssl.create_default_context=_f
    ssl._create_default_https_context=ssl._create_unverified_context
except Exception: pass

try:
    import httpx
    _oa=httpx.AsyncClient.__init__
    def _pa(self,*a,verify=False,**k): _oa(self,*a,verify=verify,**k)
    httpx.AsyncClient.__init__=_pa
    _os=httpx.Client.__init__
    def _ps(self,*a,verify=False,**k): _os(self,*a,verify=verify,**k)
    httpx.Client.__init__=_ps
except Exception: pass

try:
    import aiohttp
    _ot=aiohttp.TCPConnector.__init__
    def _tcp(self,*a,ssl=False,**k): _ot(self,*a,ssl=ssl,**k)
    aiohttp.TCPConnector.__init__=_tcp
    _oss=aiohttp.ClientSession.__init__
    def _sess(self,*a,connector=None,**k):
        if connector is None: connector=aiohttp.TCPConnector(ssl=False)
        _oss(self,*a,connector=connector,**k)
    aiohttp.ClientSession.__init__=_sess
except Exception: pass

if sys.platform=="win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
