"""
Universal LLM Gateway v1.0 — dashboard.py
Web dashboard + REST API. All HTML inlined.
"""
import ssl_patch  # must be first

import asyncio
import json
import logging
import uvicorn
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("UniversalLLMGateway.Dashboard")

# =============================================================================
# HTML DASHBOARD
# =============================================================================

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Universal LLM Gateway v1.0</title>
<style>
:root{--bg:#0a0a0f;--bg2:#111118;--card:#16161f;--border:#1f2030;
--text:#e2e8f0;--muted:#5a6480;--dim:#252535;
--green:#22c55e;--cyan:#06b6d4;--yellow:#f59e0b;--red:#ef4444;--purple:#a855f7;--blue:#3b82f6;
--font:'Inter',system-ui,sans-serif;--mono:'Cascadia Code','Fira Code','Courier New',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px;min-height:100vh}
.layout{display:flex;min-height:100vh}
.sidebar{width:210px;background:var(--bg2);border-right:1px solid var(--border);
display:flex;flex-direction:column;flex-shrink:0}
.logo{padding:18px 16px;border-bottom:1px solid var(--border)}
.logo-name{font-size:1rem;font-weight:700;color:var(--green);letter-spacing:.5px}
.logo-sub{font-size:.65rem;color:var(--muted);margin-top:2px}
nav{padding:10px 8px;flex:1}
.nav-item{display:flex;align-items:center;gap:9px;padding:9px 10px;border-radius:8px;
cursor:pointer;color:var(--muted);font-size:.82rem;transition:.15s;margin-bottom:1px}
.nav-item:hover{background:var(--card);color:var(--text)}
.nav-item.on{background:#0f2318;color:var(--green)}
.nav-icon{font-size:.95rem;width:18px;text-align:center}
.sf{padding:14px;border-top:1px solid var(--border);font-size:.67rem;color:var(--dim);line-height:1.7}
.wm{padding:10px 14px;border-top:1px solid var(--border);font-size:.6rem;color:#1e2535;
letter-spacing:.18em;text-transform:uppercase;text-align:center;user-select:none;font-weight:700}
.wm span{background:linear-gradient(90deg,#22c55e44,#06b6d444,#22c55e44);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.content{flex:1;padding:22px;overflow:auto}
.page{display:none}.page.on{display:block}
/* header */
.ph{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:22px}
.ph-title{font-size:1.25rem;font-weight:700}.ph-title span{color:var(--green)}
.hacts{display:flex;gap:8px;flex-wrap:wrap}
/* cards */
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px}
.card-title{font-size:.7rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);margin-bottom:14px;display:flex;align-items:center;gap:7px}
.g2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:900px){.g4{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:1fr 1fr}}
@media(max-width:600px){.g2,.g3,.g4{grid-template-columns:1fr}}
/* stat cards */
.sc{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px}
.sv{font-size:1.9rem;font-weight:700;line-height:1;margin-bottom:4px}
.sl{font-size:.7rem;color:var(--muted)}
.green{color:var(--green)}.red{color:var(--red)}.yellow{color:var(--yellow)}
.cyan{color:var(--cyan)}.blue{color:var(--blue)}.purple{color:var(--purple)}
/* output key */
.ok-box{background:linear-gradient(135deg,#0a200f,#0a1820);border:2px solid var(--green);
border-radius:12px;padding:22px;margin-bottom:22px}
.ok-label{font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--green);
margin-bottom:10px}
.ok-key{font-family:var(--mono);font-size:.95rem;color:#4ade80;word-break:break-all;
padding:12px 14px;background:rgba(0,0,0,.4);border-radius:8px;
border:1px solid #22c55e44;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ok-str{flex:1;word-break:break-all}
.ok-meta{display:flex;gap:18px;flex-wrap:wrap;margin-top:12px;font-size:.78rem;color:var(--muted)}
.ok-meta b{color:var(--text)}
.badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:20px;
font-size:.68rem;font-weight:600}
.b-ok{background:#0f2318;color:var(--green);border:1px solid var(--green)}
.b-off{background:#200f0f;color:var(--red);border:1px solid var(--red)}
.b-lim{background:#20180a;color:var(--yellow);border:1px solid var(--yellow)}
.b-dead{background:#200f0f;color:var(--red)}
/* buttons */
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 13px;border-radius:8px;
border:1px solid var(--border);background:var(--card);color:var(--text);
font-size:.78rem;font-family:var(--font);cursor:pointer;transition:.15s;white-space:nowrap}
.btn:hover{border-color:var(--green);color:var(--green)}
.btn.prim{background:var(--green);color:#000;border-color:var(--green);font-weight:600}
.btn.prim:hover{background:#16a34a}
.btn.danger{border-color:var(--red);color:var(--red)}.btn.danger:hover{background:var(--red);color:#fff}
.btn.sm{padding:4px 9px;font-size:.72rem}
/* table */
.tw{overflow-x:auto}.tw::-webkit-scrollbar{height:4px}
.tw::-webkit-scrollbar-thumb{background:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:.78rem}
th{padding:9px 11px;text-align:left;border-bottom:2px solid var(--border);
color:var(--muted);font-size:.68rem;font-weight:600;letter-spacing:.04em;
text-transform:uppercase;white-space:nowrap}
td{padding:9px 11px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:hover td{background:rgba(255,255,255,.02)}
.chip{padding:2px 7px;border-radius:4px;font-size:.68rem;font-weight:600;
background:var(--dim);color:var(--muted)}
.rank-chip{background:#0d1a2e;color:var(--cyan);padding:2px 7px;border-radius:4px;font-size:.7rem}
/* forms */
.fr{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.fi{flex:1;min-width:130px;padding:8px 11px;background:var(--bg);border:1px solid var(--border);
border-radius:8px;color:var(--text);font-family:var(--font);font-size:.8rem;outline:none;transition:.15s}
.fi:focus{border-color:var(--green)}
select.fi option{background:var(--bg2)}
/* progress */
.prog{height:6px;background:var(--dim);border-radius:3px;overflow:hidden;margin-top:8px}
.prog-fill{height:100%;border-radius:3px;transition:width .6s}
.pf-green{background:var(--green)}.pf-yellow{background:var(--yellow)}.pf-red{background:var(--red)}
/* log */
.logbox{background:#06080f;border:1px solid var(--border);border-radius:8px;
height:260px;overflow-y:auto;padding:12px;font-family:var(--mono);font-size:.7rem;line-height:1.8}
.logbox::-webkit-scrollbar{width:4px}.logbox::-webkit-scrollbar-thumb{background:var(--dim)}
.ls{color:var(--green)}.lf{color:var(--red)}.li{color:var(--cyan)}.lr{color:var(--muted)}
/* terminal */
.term{background:#04060c;border:1px solid var(--border);border-radius:8px;
height:200px;overflow-y:auto;padding:12px;font-family:var(--mono);font-size:.72rem;line-height:1.8}
.term::-webkit-scrollbar{width:3px}.term::-webkit-scrollbar-thumb{background:var(--dim)}
.tc{color:var(--cyan)}.tok{color:var(--green)}.terr{color:var(--red)}.td{color:var(--muted)}
.term-input{display:flex;align-items:center;gap:8px;margin-top:8px;
padding:7px 11px;background:var(--bg);border:1px solid var(--border);border-radius:8px}
.t-prompt{color:var(--green);font-family:var(--mono);font-size:.78rem;white-space:nowrap}
input.t-in{flex:1;background:none;border:none;outline:none;color:var(--text);
font-family:var(--mono);font-size:.78rem}
/* spacer */
.sp{margin-bottom:18px}
hr{border:none;border-top:1px solid var(--border);margin:16px 0}
code{font-family:var(--mono);background:var(--dim);padding:1px 6px;border-radius:4px;font-size:.85em}
/* corner watermark */
#corner-wm{position:fixed;bottom:12px;right:16px;z-index:100;font-size:.58rem;
letter-spacing:.15em;text-transform:uppercase;color:#1a2030;font-weight:700;
pointer-events:none;user-select:none}
/* toast */
#toast{position:fixed;bottom:22px;right:22px;z-index:9999;padding:11px 18px;border-radius:10px;
font-size:.8rem;display:none;max-width:320px;border:1px solid var(--border);
animation:slide-up .22s ease}
.t-ok{background:#0a200f;border-color:var(--green)!important;color:var(--green)}
.t-err{background:#200a0a;border-color:var(--red)!important;color:var(--red)}
@keyframes slide-up{from{transform:translateY(10px);opacity:0}to{transform:translateY(0);opacity:1}}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0}
.d-green{background:var(--green)}.d-red{background:var(--red)}.d-yellow{background:var(--yellow)}
.pulse{animation:pd 2s ease-in-out infinite}
@keyframes pd{0%,100%{opacity:1}50%{opacity:.4}}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="logo">
    <div class="logo-name">⚡ UNIVERSAL LLM GATEWAY</div>
    <div class="logo-sub">v1.0 · Universal API Router</div>
  </div>
  <nav>
    <div class="nav-item on"  onclick="go('overview',this)"><span class="nav-icon">🏠</span>Overview</div>
    <div class="nav-item"     onclick="go('outkey',this)"><span class="nav-icon">🔑</span>Output Key</div>
    <div class="nav-item"     onclick="go('slots',this)"><span class="nav-icon">📦</span>Input Slots</div>
    <div class="nav-item"     onclick="go('costs',this)"><span class="nav-icon">💰</span>Cost Tracking</div>
    <div class="nav-item"     onclick="go('logs',this)"><span class="nav-icon">📋</span>Request Logs</div>
    <div class="nav-item"     onclick="go('terminal',this)"><span class="nav-icon">🖥️</span>Terminal</div>
    <div class="nav-item"     onclick="go('addslot',this)"><span class="nav-icon">➕</span>Add Slot</div>
  </nav>
  <div class="sf">
    <div id="sf-status">● ONLINE</div>
    <div id="sf-time"></div>
    <div id="sf-slots"></div>
    <div id="sf-cost"></div>
  </div>
  <div class="wm"><span>nesheem</span></div>
</aside>

<div class="content">

<!-- OVERVIEW -->
<div id="page-overview" class="page on">
  <div class="ph">
    <div><div class="ph-title">Universal LLM Gateway <span>v1.0</span></div>
    <div style="font-size:.75rem;color:var(--muted);margin-top:3px">Universal LLM Gateway · 100 input slots · 1 output key</div></div>
    <div class="hacts">
      <button class="btn" onclick="doHealth()">⚡ Health Check</button>
      <button class="btn" onclick="doBench()">🏁 Benchmark</button>
      <button class="btn" onclick="refresh()">🔄 Refresh</button>
    </div>
  </div>
  <div class="g4 sp">
    <div class="sc"><div class="sv green" id="s-h">—</div><div class="sl">Healthy Slots</div></div>
    <div class="sc"><div class="sv yellow" id="s-r">—</div><div class="sl">Rate Limited</div></div>
    <div class="sc"><div class="sv red" id="s-o">—</div><div class="sl">Offline</div></div>
    <div class="sc"><div class="sv cyan" id="s-req">—</div><div class="sl">Total Requests</div></div>
  </div>
  <div class="g2 sp">
    <div class="card">
      <div class="card-title"><span class="dot d-green pulse"></span>Slot Health</div>
      <div id="pool-txt" style="font-size:.8rem;color:var(--muted)">Loading…</div>
      <div class="prog sp"><div class="prog-fill pf-green" id="hbar" style="width:0%"></div></div>
      <div id="hpct" style="font-size:.68rem;color:var(--muted)"></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="dot d-cyan pulse"></span>Performance</div>
      <div class="g3" style="gap:6px">
        <div><div class="sv green" style="font-size:1.3rem" id="s-sr">—%</div><div style="font-size:.68rem;color:var(--muted)">Success</div></div>
        <div><div class="sv cyan" style="font-size:1.3rem" id="s-fail">—</div><div style="font-size:.68rem;color:var(--muted)">Failures</div></div>
        <div><div class="sv purple" style="font-size:1.3rem" id="s-cost">$—</div><div style="font-size:.68rem;color:var(--muted)">Total Cost</div></div>
      </div>
      <div id="bench-time" style="font-size:.68rem;color:var(--muted);margin-top:8px"></div>
    </div>
  </div>
  <div class="card sp">
    <div class="card-title">Provider Breakdown</div>
    <div id="prov-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px"></div>
  </div>
  <div class="card">
    <div class="card-title">🏆 Top 5 Slots</div>
    <div class="tw"><table>
      <thead><tr><th>Rank</th><th>Name</th><th>Provider</th><th>Score</th><th>Latency</th><th>TPS</th><th>Cost</th></tr></thead>
      <tbody id="top5"></tbody>
    </table></div>
  </div>
</div>

<!-- OUTPUT KEY -->
<div id="page-outkey" class="page">
  <div class="ph"><div class="ph-title">🔑 Output <span>API Key</span></div></div>
  <div class="ok-box sp">
    <div class="ok-label"><span class="dot d-green pulse"></span> Your Single Output Key</div>
    <div style="font-size:.78rem;color:var(--muted);margin-bottom:10px">
      Use this key in any OpenAI-compatible app. Universal LLM Gateway routes requests across all input slots automatically.
    </div>
    <div class="ok-key">
      <span class="ok-str" id="ok-key-val">Loading…</span>
      <button class="btn sm" onclick="copyKey()">📋 Copy</button>
    </div>
    <div class="ok-meta">
      <div>Status: <span id="ok-status" class="badge b-ok">● Active</span></div>
      <div>Uses: <b id="ok-uses">0</b></div>
      <div>Created: <b id="ok-created">—</b></div>
    </div>
  </div>
  <div class="card sp">
    <div class="card-title">⚡ Quick Setup</div>
    <div style="font-size:.85rem;line-height:2.2">
      <div>1. Copy the Output Key above</div>
      <div>2. In your app, set <strong>API Base URL</strong> to: <code id="base-url-display">http://VPS_IP:8900/v1</code></div>
      <div>3. Set <strong>API Key</strong> to the Output Key</div>
      <div>4. Set any <strong>Model</strong> — <code>gemini-2.0-flash</code>, <code>gpt-4o</code>, <code>ulg-auto</code>, etc.</div>
      <div>5. Universal LLM Gateway picks the best available slot and returns a response in that model's format</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">🔧 Key Management</div>
    <div class="fr">
      <input class="fi" id="ok-note" placeholder="Notes (e.g. used in Open Claw)">
      <button class="btn" onclick="saveNote()">💾 Save</button>
    </div>
    <hr>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn danger" onclick="regenKey()">🔄 Regenerate Key</button>
      <button class="btn" onclick="toggleKey()">⏸ Toggle Active</button>
    </div>
    <div style="font-size:.7rem;color:var(--muted);margin-top:8px">⚠ Regenerating invalidates the key in all apps immediately.</div>
  </div>
</div>

<!-- SLOTS -->
<div id="page-slots" class="page">
  <div class="ph">
    <div class="ph-title">📦 Input <span>Slots</span></div>
    <div class="hacts">
      <button class="btn" onclick="doHealth()">⚡ Health Check</button>
      <button class="btn" onclick="doBench()">🏁 Benchmark</button>
      <span id="slot-count" style="font-size:.75rem;color:var(--muted);align-self:center"></span>
    </div>
  </div>
  <div class="card">
    <div class="fr sp">
      <input class="fi" id="slot-search" placeholder="🔍 Filter name / provider / model…" style="flex:1" oninput="filterSlots()">
      <select class="fi" style="width:140px" id="slot-filter" onchange="filterSlots()">
        <option value="">All</option><option value="healthy">✅ Healthy</option>
        <option value="limited">⏳ Limited</option><option value="offline">❌ Offline</option>
      </select>
    </div>
    <div class="tw"><table>
      <thead><tr><th>#</th><th>Status</th><th>Provider</th><th>Name</th><th>Model</th><th>Score</th><th>Latency</th><th>TPS</th><th>Rank</th><th>Error</th><th></th></tr></thead>
      <tbody id="slots-body"></tbody>
    </table></div>
  </div>
</div>

<!-- COSTS -->
<div id="page-costs" class="page">
  <div class="ph"><div class="ph-title">💰 Cost <span>Tracking</span></div></div>
  <div class="g3 sp">
    <div class="sc"><div class="sv green" id="c-total">$0</div><div class="sl">Total Spend</div></div>
    <div class="sc"><div class="sv cyan" id="c-top-prov">—</div><div class="sl">Top Provider</div></div>
    <div class="sc"><div class="sv yellow" id="c-avg">$0</div><div class="sl">Avg per Request</div></div>
  </div>
  <div class="card sp">
    <div class="card-title">By Provider</div>
    <div class="tw"><table>
      <thead><tr><th>Provider</th><th>Cost (USD)</th><th>Share</th></tr></thead>
      <tbody id="cost-body"></tbody>
    </table></div>
  </div>
  <div class="card">
    <div class="card-title">Recent Transactions</div>
    <div class="tw"><table>
      <thead><tr><th>Time</th><th>Provider</th><th>Model</th><th>In Tokens</th><th>Out Tokens</th><th>Cost</th><th>Latency</th></tr></thead>
      <tbody id="cost-log"></tbody>
    </table></div>
  </div>
</div>

<!-- LOGS -->
<div id="page-logs" class="page">
  <div class="ph">
    <div class="ph-title">📋 Request <span>Logs</span></div>
    <div class="hacts">
      <button class="btn" onclick="loadLogs()">🔄 Refresh</button>
      <button class="btn" onclick="document.getElementById('logbox').innerHTML=''">🗑 Clear</button>
    </div>
  </div>
  <div class="card">
    <div class="logbox" id="logbox"></div>
  </div>
</div>

<!-- TERMINAL -->
<div id="page-terminal" class="page">
  <div class="ph"><div class="ph-title">🖥️ <span>Terminal</span></div></div>
  <div class="card">
    <div class="card-title">Command Interface</div>
    <div class="term" id="term">
      <div class="td">Universal LLM Gateway v1.0 terminal. Commands:</div>
      <div class="tc">  health       — health check all slots</div>
      <div class="tc">  benchmark    — benchmark healthy slots</div>
      <div class="tc">  status       — show summary</div>
      <div class="tc">  add &lt;prov&gt; &lt;key&gt; [model]  — add a slot</div>
      <div class="tc">  regen        — regenerate output key</div>
    </div>
    <div class="term-input">
      <span class="t-prompt">ulg$</span>
      <input class="t-in" id="t-in" placeholder="type command…" onkeydown="if(event.key==='Enter')runCmd()">
      <button class="btn sm" onclick="runCmd()">Run</button>
    </div>
  </div>
</div>

<!-- ADD SLOT -->
<div id="page-addslot" class="page">
  <div class="ph"><div class="ph-title">➕ Add Input <span>Slot</span></div></div>
  <div class="card" style="max-width:580px">
    <div class="card-title">New API Key Slot</div>
    <div class="fr">
      <select class="fi" id="as-prov" style="flex:0 0 160px">
        <option value="gemini">Google Gemini</option>
        <option value="groq">Groq</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
        <option value="deepseek">DeepSeek</option>
        <option value="xai">xAI / Grok</option>
        <option value="openrouter">OpenRouter</option>
        <option value="mistral">Mistral</option>
        <option value="cerebras">Cerebras</option>
        <option value="sambanova">SambaNova</option>
        <option value="github">GitHub Models</option>
        <option value="together">Together AI</option>
        <option value="kimi">Kimi K2</option>
        <option value="nvidia">NVIDIA NIM</option>
        <option value="ollama">Ollama (local)</option>
        <option value="lmstudio">LM Studio (local)</option>
        <option value="cohere">Cohere</option>
        <option value="perplexity">Perplexity</option>
        <option value="fireworks">Fireworks AI</option>
      </select>
      <input class="fi" id="as-key" placeholder="API Key">
    </div>
    <div class="fr">
      <input class="fi" id="as-model" placeholder="Model (optional)">
      <input class="fi" id="as-url" placeholder="Base URL (optional)">
    </div>
    <div class="fr">
      <input class="fi" id="as-name" placeholder="Display name">
      <input class="fi" id="as-notes" placeholder="Notes">
    </div>
    <button class="btn prim" style="width:100%" onclick="addSlot()">➕ Add Slot</button>
    <div style="font-size:.7rem;color:var(--muted);margin-top:8px" id="slot-cap"></div>
  </div>
</div>

</div><!-- /content -->
</div><!-- /layout -->
<div id="toast"></div>
<div id="corner-wm">nesheem</div>

<script>
let allSlots=[];

function go(id,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('on'));
  document.getElementById('page-'+id).classList.add('on');
  el.classList.add('on');
  if(id==='slots')loadSlots();
  if(id==='logs')loadLogs();
  if(id==='outkey')loadKey();
  if(id==='costs')loadCosts();
}

function toast(m,t='ok'){
  const el=document.getElementById('toast');
  el.className=t==='ok'?'t-ok':'t-err';
  el.textContent=m; el.style.display='block';
  setTimeout(()=>el.style.display='none',3200);
}

async function api(path,opts={}){
  const r=await fetch('/api'+path,{headers:{'Content-Type':'application/json'},...opts});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

async function refresh(){
  try{
    const[s,st,cost]=await Promise.all([api('/status'),api('/stats'),api('/costs')]);
    document.getElementById('s-h').textContent=s.healthy;
    document.getElementById('s-r').textContent=s.limited;
    document.getElementById('s-o').textContent=s.offline;
    document.getElementById('s-req').textContent=st.total_requests;
    document.getElementById('s-fail').textContent=st.total_failures;
    document.getElementById('s-sr').textContent=st.success_rate+'%';
    document.getElementById('s-cost').textContent='$'+cost.total_usd.toFixed(4);
    const pct=s.total>0?Math.round(s.healthy/s.total*100):0;
    document.getElementById('hbar').style.width=pct+'%';
    document.getElementById('hpct').textContent=pct+'% healthy ('+s.healthy+'/'+s.total+' slots)';
    document.getElementById('pool-txt').innerHTML=
      '<span class="green">✅ '+s.healthy+' healthy</span>  '+
      '<span class="yellow">⏳ '+s.limited+' limited</span>  '+
      '<span class="red">❌ '+s.offline+' offline</span>';
    if(st.last_benchmark)document.getElementById('bench-time').textContent='Last benchmark: '+st.last_benchmark.substring(0,19);
    document.getElementById('sf-slots').textContent=s.healthy+'/'+s.total+' healthy';
    document.getElementById('sf-cost').textContent='cost: $'+cost.total_usd.toFixed(4);
    // provider grid
    const pg=document.getElementById('prov-grid');
    pg.innerHTML=Object.entries(s.by_provider||{}).map(([p,v])=>`
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px">
        <div style="font-size:.78rem;font-weight:600;margin-bottom:3px">${p}</div>
        <div style="font-size:.7rem;color:var(--muted)">✅${v.healthy}/${v.total}</div>
        <div class="prog" style="margin-top:5px"><div class="prog-fill ${v.healthy>0?'pf-green':'pf-red'}"
          style="width:${v.total>0?Math.round(v.healthy/v.total*100):0}%"></div></div>
      </div>`).join('');
    // top 5
    const top=(s.top5||[]);
    document.getElementById('top5').innerHTML=top.map(k=>`<tr>
      <td><span class="rank-chip">#${k.rank}</span></td>
      <td style="font-size:.78rem">${k.display_name}</td>
      <td><span class="chip">${k.provider}</span></td>
      <td style="font-size:.75rem">${k.benchmark_score>0?k.benchmark_score.toFixed(1):'—'}</td>
      <td style="font-size:.75rem">${k.avg_latency_ms<9000?k.avg_latency_ms.toFixed(0)+'ms':'—'}</td>
      <td style="font-size:.75rem">${k.tokens_per_second>0?k.tokens_per_second.toFixed(1):'—'}</td>
      <td style="font-size:.75rem">$${k.total_cost_usd.toFixed(5)}</td>
    </tr>`).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:20px">No healthy slots — run health check</td></tr>';
  }catch(e){console.error(e)}
}

async function loadKey(){
  try{
    const d=await api('/output-key');
    document.getElementById('ok-key-val').textContent=d.key;
    document.getElementById('ok-status').className='badge '+(d.active?'b-ok':'b-off');
    document.getElementById('ok-status').textContent=d.active?'● Active':'● Inactive';
    document.getElementById('ok-uses').textContent=d.usage_count||0;
    document.getElementById('ok-created').textContent=(d.created_at||'—').substring(0,19);
    document.getElementById('base-url-display').textContent=`http://${location.hostname}:8900/v1`;
  }catch(e){console.error(e)}
}

function copyKey(){
  const k=document.getElementById('ok-key-val').textContent.trim();
  if(navigator.clipboard && window.isSecureContext){
    navigator.clipboard.writeText(k).then(()=>toast('✅ Output key copied!'))
      .catch(()=>_fallbackCopy(k));
  } else { _fallbackCopy(k); }
}
function _fallbackCopy(text){
  const ta=document.createElement('textarea');
  ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
  document.body.appendChild(ta); ta.focus(); ta.select();
  try{ document.execCommand('copy'); toast('✅ Output key copied!'); }
  catch(e){ toast('Copy failed — select key manually','err'); }
  document.body.removeChild(ta);
}

async function regenKey(){
  if(!confirm('Regenerate output key? All apps using the current key will stop working.'))return;
  try{await api('/output-key/regen',{method:'POST'});toast('Key regenerated!');loadKey();}
  catch(e){toast('Error: '+e.message,'err')}
}

async function toggleKey(){
  try{const d=await api('/output-key/toggle',{method:'POST'});toast('Key '+(d.active?'activated':'deactivated'));loadKey();}
  catch(e){toast('Error: '+e.message,'err')}
}

async function saveNote(){
  const notes=document.getElementById('ok-note').value;
  try{await api('/output-key/note',{method:'POST',body:JSON.stringify({notes})});toast('Note saved');}
  catch(e){toast('Error: '+e.message,'err')}
}

async function loadSlots(){
  try{
    const slots=await api('/slots');
    allSlots=slots;
    renderSlots(slots);
    document.getElementById('slot-count').textContent=slots.length+'/100 slots';
    document.getElementById('slot-cap').textContent=slots.length+'/100 slots used';
  }catch(e){console.error(e)}
}

function renderSlots(slots){
  const tb=document.getElementById('slots-body');
  if(!slots.length){tb.innerHTML='<tr><td colspan="11" style="text-align:center;color:var(--muted);padding:20px">No slots</td></tr>';return;}
  tb.innerHTML=slots.map(s=>{
    const bc=s.is_healthy?'b-ok':s.rate_limited?'b-lim':'b-dead';
    const bt=s.is_healthy?'✅ Healthy':s.rate_limited?'⏳ Limited':'❌ Offline';
    return`<tr>
      <td style="color:var(--muted);font-size:.72rem">${s.slot_number}</td>
      <td><span class="badge ${bc}">${bt}</span></td>
      <td><span class="chip">${s.provider}</span></td>
      <td style="font-size:.75rem;max-width:140px;overflow:hidden;text-overflow:ellipsis" title="${s.display_name}">${s.display_name}</td>
      <td style="font-size:.7rem;color:var(--muted)">${s.model_name||'—'}</td>
      <td style="font-size:.73rem">${s.benchmark_score>0?s.benchmark_score.toFixed(1):'—'}</td>
      <td style="font-size:.73rem">${s.avg_latency_ms<9000?s.avg_latency_ms.toFixed(0)+'ms':'—'}</td>
      <td style="font-size:.73rem">${s.tokens_per_second>0?s.tokens_per_second.toFixed(1):'—'}</td>
      <td><span class="rank-chip" style="font-size:.65rem">${s.rank<900?'#'+s.rank:'—'}</span></td>
      <td style="font-size:.7rem;color:var(--muted);max-width:110px;overflow:hidden;text-overflow:ellipsis" title="${s.last_error||''}">${(s.last_error||'').substring(0,30)||'—'}</td>
      <td style="display:flex;gap:4px">
        <button class="btn sm" onclick="editSlot('${s.id}','${s.display_name}','${s.model_name||''}','${s.notes||''}')">✏️</button>
        <button class="btn sm danger" onclick="removeSlot('${s.id}')">🗑</button>
      </td>
    </tr>`;
  }).join('');
}

function filterSlots(){
  const q=document.getElementById('slot-search').value.toLowerCase();
  const f=document.getElementById('slot-filter').value;
  renderSlots(allSlots.filter(s=>{
    const mq=!q||s.display_name.toLowerCase().includes(q)||s.provider.includes(q)||(s.model_name||'').toLowerCase().includes(q);
    const ms=!f||(f==='healthy'&&s.is_healthy)||(f==='limited'&&s.rate_limited)||(f==='offline'&&!s.is_healthy&&!s.rate_limited);
    return mq&&ms;
  }));
}

async function removeSlot(id){
  if(!confirm('Remove this slot?'))return;
  try{await api('/slots/'+id,{method:'DELETE'});toast('Slot removed');loadSlots();}
  catch(e){toast('Error: '+e.message,'err')}
}

async function addSlot(){
  const prov=document.getElementById('as-prov').value;
  const key=document.getElementById('as-key').value.trim();
  const model=document.getElementById('as-model').value.trim();
  const url=document.getElementById('as-url').value.trim();
  const name=document.getElementById('as-name').value.trim();
  const notes=document.getElementById('as-notes').value.trim();
  if(!key&&prov!=='ollama'&&prov!=='lmstudio'){toast('API key is required','err');return;}
  try{
    await api('/slots',{method:'POST',body:JSON.stringify({provider:prov,api_key:key,
      model_name:model||undefined,base_url:url||undefined,display_name:name||undefined,notes})});
    toast('✅ '+prov+' slot added!');
    ['as-key','as-model','as-url','as-name','as-notes'].forEach(id=>document.getElementById(id).value='');
    loadSlots();
  }catch(e){toast('Error: '+e.message,'err')}
}

async function loadCosts(){
  try{
    const[c,st]=await Promise.all([api('/costs'),api('/stats')]);
    document.getElementById('c-total').textContent='$'+c.total_usd.toFixed(6);
    const entries=Object.entries(c.by_provider||{});
    const top=entries.length?entries[0][0]:'—';
    document.getElementById('c-top-prov').textContent=top;
    const avg=st.total_requests>0?c.total_usd/st.total_requests:0;
    document.getElementById('c-avg').textContent='$'+avg.toFixed(8);
    const total=c.total_usd||0.000001;
    document.getElementById('cost-body').innerHTML=entries.map(([p,v])=>`<tr>
      <td><span class="chip">${p}</span></td>
      <td>$${v.toFixed(6)}</td>
      <td><div style="display:flex;align-items:center;gap:8px">
        <div style="width:80px;height:4px;background:var(--dim);border-radius:2px;overflow:hidden">
          <div style="width:${Math.round(v/total*100)}%;height:100%;background:var(--green)"></div></div>
        ${Math.round(v/total*100)}%</div></td>
    </tr>`).join('')||'<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:16px">No cost data yet</td></tr>';
    document.getElementById('cost-log').innerHTML=(c.recent||[]).slice(-20).reverse().map(e=>`<tr>
      <td style="font-size:.72rem;color:var(--muted)">${e.ts.substring(11)}</td>
      <td><span class="chip">${e.provider}</span></td>
      <td style="font-size:.72rem">${e.model}</td>
      <td style="font-size:.72rem">${e.input_tokens}</td>
      <td style="font-size:.72rem">${e.output_tokens}</td>
      <td style="font-size:.72rem;color:var(--green)">$${e.cost_usd.toFixed(8)}</td>
      <td style="font-size:.72rem">${e.latency_ms.toFixed(0)}ms</td>
    </tr>`).join('')||'<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:16px">No transactions yet</td></tr>';
  }catch(e){console.error(e)}
}

async function loadLogs(){
  try{
    const d=await api('/stats');
    const box=document.getElementById('logbox');
    const entries=(d.recent||[]).slice().reverse();
    box.innerHTML=entries.map(r=>{
      const cls=r.status==='success'?'ls':r.status==='failed'?'lf':'li';
      return`<div class="${cls}">[${r.ts.substring(11)}] ${r.status.toUpperCase()} › ${r.provider} / ${r.model} ${r.latency_ms>0?r.latency_ms.toFixed(0)+'ms':''} ${r.error?'| '+r.error.substring(0,60):''}</div>`;
    }).join('')||'<div class="lr">No requests yet.</div>';
    box.scrollTop=box.scrollHeight;
  }catch(e){console.error(e)}
}

function tprint(msg,cls='td'){
  const t=document.getElementById('term');
  const d=document.createElement('div');
  d.className=cls;d.textContent=msg;t.appendChild(d);t.scrollTop=t.scrollHeight;
}

async function runCmd(){
  const inp=document.getElementById('t-in');
  const cmd=inp.value.trim();if(!cmd)return;
  inp.value='';tprint('$ '+cmd,'tc');
  const c=cmd.toLowerCase();
  if(c==='health'){tprint('Running health check…');await doHealth(true);return;}
  if(c==='benchmark'){tprint('Running benchmark…');await doBench(true);return;}
  if(c==='regen'){
    try{await api('/output-key/regen',{method:'POST'});tprint('Output key regenerated.','tok');}
    catch(e){tprint('Error: '+e.message,'terr')}
    return;
  }
  if(c==='status'){
    try{const s=await api('/status');tprint(`${s.healthy} healthy / ${s.limited} limited / ${s.offline} offline`,'tok');}
    catch(e){tprint('Error: '+e.message,'terr')}
    return;
  }
  if(c.startsWith('add ')){
    const p=cmd.split(' ');
    try{await api('/slots',{method:'POST',body:JSON.stringify({provider:p[1],api_key:p[2],model_name:p[3]||undefined})});
    tprint('✅ Slot added: '+p[1],'tok');}
    catch(e){tprint('Error: '+e.message,'terr')}
    return;
  }
  tprint('Unknown command. Try: health, benchmark, status, regen, add <prov> <key>','terr');
}

async function doHealth(silent=false){
  if(!silent)toast('⚡ Health check started…');
  try{await api('/health',{method:'POST'});toast('✅ Health check complete');refresh();}
  catch(e){toast('Error: '+e.message,'err')}
  if(document.getElementById('term').children.length>0)tprint('Health check done.','tok');
}

async function doBench(silent=false){
  if(!silent)toast('🏁 Benchmark started…');
  try{await api('/benchmark',{method:'POST'});toast('✅ Benchmark complete');refresh();}
  catch(e){toast('Error: '+e.message,'err')}
  if(document.getElementById('term').children.length>0)tprint('Benchmark done.','tok');
}

setInterval(()=>{
  const t=new Date().toLocaleTimeString('en-GB',{hour12:false});
  document.getElementById('sf-time').textContent=t;
},1000);
setInterval(refresh,30000);
refresh();
loadKey();
</script>

<!-- Edit Slot Modal -->
<div id="edit-modal" style="display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.8);align-items:center;justify-content:center">
  <div style="background:var(--card);border:1px solid var(--green);border-radius:12px;padding:24px;width:90%;max-width:480px">
    <div style="font-size:.9rem;font-weight:700;margin-bottom:16px;color:var(--green)">✏️ Edit Slot</div>
    <input type="hidden" id="edit-id">
    <div class="fr"><input class="fi" id="edit-name" placeholder="Display name"></div>
    <div class="fr"><input class="fi" id="edit-model" placeholder="Model name"></div>
    <div class="fr"><input class="fi" id="edit-notes" placeholder="Notes"></div>
    <div style="display:flex;gap:8px;margin-top:14px;justify-content:flex-end">
      <button class="btn" onclick="document.getElementById('edit-modal').style.display='none'">Cancel</button>
      <button class="btn prim" onclick="saveEdit()">💾 Save</button>
    </div>
  </div>
</div>
<script>
function editSlot(id,name,model,notes){
  document.getElementById('edit-id').value=id;
  document.getElementById('edit-name').value=name;
  document.getElementById('edit-model').value=model;
  document.getElementById('edit-notes').value=notes;
  document.getElementById('edit-modal').style.display='flex';
}
async function saveEdit(){
  const id=document.getElementById('edit-id').value;
  const name=document.getElementById('edit-name').value;
  const model=document.getElementById('edit-model').value;
  const notes=document.getElementById('edit-notes').value;
  try{
    await api('/slots/'+id,{method:'PATCH',body:JSON.stringify({
      display_name:name,model_name:model,notes:notes})});
    document.getElementById('edit-modal').style.display='none';
    toast('✅ Slot updated');
    loadSlots();
  }catch(e){toast('Error: '+e.message,'err')}
}
</script>
</body>
</html>"""


# =============================================================================
# DASHBOARD SERVER
# =============================================================================

class DashboardServer:

    def __init__(self, cfg, slot_manager, output_key_mgr,
                 health_checker, benchmarker, router, cost_tracker, request_log):
        self.cfg  = cfg
        self.sm   = slot_manager
        self.okm  = output_key_mgr
        self.hc   = health_checker
        self.bm   = benchmarker
        self.rt   = router
        self.ct   = cost_tracker
        self.rl   = request_log

        self.app = FastAPI(title="Universal LLM Gateway v1.0 Dashboard",
                           docs_url=None, redoc_url=None)
        self._routes()

    def _routes(self):
        app = self.app

        @app.get("/", response_class=HTMLResponse)
        async def dash():
            return HTMLResponse(content=HTML)

        # ── Status ───────────────────────────────────────────────────────────
        @app.get("/api/status")
        async def status():
            slots   = self.sm.slots
            healthy = [s for s in slots if s.is_healthy]
            limited = [s for s in slots if s.rate_limited and not s.is_healthy]
            offline = [s for s in slots if not s.is_healthy and not s.rate_limited]

            by_prov = {}
            for s in slots:
                if s.provider not in by_prov:
                    by_prov[s.provider] = {"total": 0, "healthy": 0}
                by_prov[s.provider]["total"] += 1
                if s.is_healthy:
                    by_prov[s.provider]["healthy"] += 1

            top5 = sorted(healthy, key=lambda x: x.rank)[:5]
            return {
                "total":    len(slots),
                "healthy":  len(healthy),
                "limited":  len(limited),
                "offline":  len(offline),
                "by_provider": by_prov,
                "last_check":  self.hc.last_check or "",
                "top5": [s.to_dict() for s in top5],
            }

        # ── Stats ─────────────────────────────────────────────────────────────
        @app.get("/api/stats")
        async def stats():
            s = self.rl.stats()
            s["last_benchmark"] = self.bm.last_benchmark or ""
            return s

        # ── Output Key ────────────────────────────────────────────────────────
        @app.get("/api/output-key")
        async def get_key():
            return self.okm.entry

        @app.post("/api/output-key/regen")
        async def regen_key():
            k = self.okm.regenerate()
            return {"key": k}

        @app.post("/api/output-key/toggle")
        async def toggle_key():
            e = self.okm.entry
            self.okm.set_active(not e.get("active", True))
            return {"active": self.okm.entry["active"]}

        @app.post("/api/output-key/note")
        async def set_note(request: Request):
            b = await request.json()
            self.okm.set_note(b.get("notes", ""))
            return {"ok": True}

        # ── Slots ─────────────────────────────────────────────────────────────
        @app.get("/api/slots")
        async def list_slots():
            return [s.to_dict() for s in self.sm.slots]

        @app.post("/api/slots")
        async def add_slot(request: Request):
            b = await request.json()
            s = self.sm.add(
                provider=b.get("provider", "gemini"),
                api_key=b.get("api_key", ""),
                model_name=b.get("model_name", ""),
                base_url=b.get("base_url", ""),
                display_name=b.get("display_name", ""),
                notes=b.get("notes", ""),
            )
            if not s:
                raise HTTPException(400, "All 100 slots full")
            return s.to_dict()

        @app.delete("/api/slots/{slot_id}")
        async def del_slot(slot_id: str):
            if not self.sm.remove(slot_id):
                raise HTTPException(404, "Slot not found")
            return {"ok": True}

        @app.patch("/api/slots/{slot_id}")
        async def edit_slot(slot_id: str, request: Request):
            s = self.sm.get(slot_id)
            if not s:
                raise HTTPException(404, "Slot not found")
            b = await request.json()
            if "display_name" in b and b["display_name"]:
                s.display_name = b["display_name"]
            if "model_name" in b and b["model_name"]:
                s.model_name = b["model_name"]
            if "notes" in b:
                s.notes = b["notes"]
            self.sm.save()
            return s.to_dict()

        @app.post("/api/slots/{slot_id}/check")
        async def check_slot(slot_id: str):
            s = self.sm.get(slot_id)
            if not s:
                raise HTTPException(404, "Slot not found")
            await self.hc.check_one(s, force=True)
            self.sm.save()
            return {"is_healthy": s.is_healthy, "last_error": s.last_error}

        # ── Health / Benchmark ────────────────────────────────────────────────
        @app.post("/api/health")
        async def health():
            asyncio.create_task(self.hc.check_all(force=True))
            return {"message": "Health check started"}

        @app.post("/api/benchmark")
        async def benchmark():
            asyncio.create_task(self.bm.benchmark_all())
            return {"message": "Benchmark started"}

        # ── Costs ─────────────────────────────────────────────────────────────
        @app.get("/api/costs")
        async def costs():
            return self.ct.summary()

    async def start(self):
        port = self.cfg.get("dash_port", 8901)
        host = "0.0.0.0"
        cfg  = uvicorn.Config(app=self.app, host=host, port=port,
                              log_level="warning", access_log=False)
        logger.info(f"Dashboard at http://{host}:{port}")
        await uvicorn.Server(cfg).serve()
