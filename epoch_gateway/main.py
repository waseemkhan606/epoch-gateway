"""
main.py — EPOCH gateway (packaged form, Session 17.1).

Routes:
    GET  /health              liveness probe — reports tenant_isolation state
    GET  /cluster/health      human-readable backend status (litellm)
    POST /v1/agent/invoke     frozen, carries Deprecation/Sunset/Link headers
    POST /v2/agent/invoke     live, no deprecation headers

Both invoke versions share _handle_invoke: verify JWT -> parse body -> bind
tenant (reject cross-tenant hospital_id) -> redact PII -> enforce admin-only
tools -> call the LLM backend -> redact the answer -> return
{status, hospital_id, role, answer}.

Everything except the tenant-binding step and the /health body is carried
forward unchanged from Week 16.2 (phase5/session5/services/fastapi/app/main.py).
"""
import json
import os
import re

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .epoch_auth import verify_jwt

app = FastAPI(title="epoch-gateway", version="17.1.0")

LITELLM_URL        = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-epoch-demo-master-key")

# "active" (default) enforces the cross-tenant check below. Any other value
# disables enforcement but is still reported verbatim by /health, so a
# misconfigured deployment is visible on the probe, not silent.
TENANT_ISOLATION = os.environ.get("EPOCH_TENANT_ISOLATION", "active")

CC_PATTERN  = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Prompts that route to the admin-only generate_client_deliverable tool.
ADMIN_ONLY_KEYWORDS = ("clinical pdf", "deliverable")


def redact_pii(text: str) -> str:
    text = CC_PATTERN.sub("[REDACTED_CC]", text)
    text = SSN_PATTERN.sub("[REDACTED_SSN]", text)
    return text


def redact_json(obj):
    if isinstance(obj, str):
        return redact_pii(obj)
    if isinstance(obj, dict):
        return {k: redact_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_json(v) for v in obj]
    return obj


def requires_admin_tool(prompt: str) -> bool:
    p = prompt.lower()
    return any(kw in p for kw in ADMIN_ONLY_KEYWORDS)


def resolve_tenant(claims: dict, body: dict) -> str:
    """
    The tenant is the caller's hospital_id claim — never a value the client
    sends. When isolation is active, a body that names a *different*
    hospital_id is a cross-tenant attempt and is rejected upstream; here we
    just surface the mismatch.
    """
    claimed = claims["hospital_id"]
    requested = body.get("hospital_id")
    if TENANT_ISOLATION == "active" and requested is not None and requested != claimed:
        raise ValueError(f"cross-tenant request: token={claimed} body={requested}")
    return claimed


@app.get("/health")
async def health():
    """Liveness probe. No backend calls — HEALTHCHECK and depends_on poll this."""
    return {"status": "ok", "tenant_isolation": TENANT_ISOLATION}


@app.get("/cluster/health")
async def cluster_health():
    """Human-readable backend status. Calls the LLM backend only."""
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{LITELLM_URL}/health")
            results["litellm"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
        except Exception as e:
            results["litellm"] = f"error:{str(e)[:50]}"
    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "tenant_isolation": TENANT_ISOLATION, "backends": results}


@app.post("/v1/agent/invoke")
async def agent_invoke_v1(request: Request):
    """v1 — frozen. Returns deprecation headers so clients know to migrate."""
    resp = await _handle_invoke(request)
    resp.headers["Deprecation"] = "true"
    resp.headers["Sunset"]      = "Sat, 31 Dec 2026 23:59:59 GMT"
    resp.headers["Link"]        = '</v2/agent/invoke>; rel="successor-version"'
    return resp


@app.post("/v2/agent/invoke")
async def agent_invoke_v2(request: Request):
    """v2 — live. No deprecation headers."""
    return await _handle_invoke(request)


async def _handle_invoke(request: Request) -> JSONResponse:
    auth = request.headers.get("Authorization", "")
    try:
        claims = verify_jwt(auth)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=401)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "malformed JSON body"}, status_code=400)

    try:
        tenant = resolve_tenant(claims, body)
    except ValueError as e:
        return JSONResponse(
            {"error": f"forbidden: {e}", "hospital_id": claims["hospital_id"]},
            status_code=403,
        )

    prompt = redact_pii(body.get("prompt") or body.get("question", ""))

    if requires_admin_tool(prompt) and claims["role"] != "admin":
        return JSONResponse(
            {"error": "forbidden: admin role required for this tool", "role": claims["role"]},
            status_code=403,
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            llm_resp = await client.post(
                f"{LITELLM_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                json={"model": "epoch-default",
                      "messages": [{"role": "user", "content": prompt}]},
            )
            answer = llm_resp.json()
        except Exception as e:
            return JSONResponse({"error": f"litellm:{e}"}, status_code=502)

    answer = redact_json(answer)

    resp = JSONResponse({
        "status": 200,
        "hospital_id": claims["hospital_id"],
        "role": claims["role"],
        "answer": answer,
    })
    resp.headers["X-Epoch-Tenant"] = tenant
    resp.headers["X-Epoch-Tenant-Isolation"] = TENANT_ISOLATION
    return resp


# ===========================================================================
# Session 17.3 additions — the browser demo surface, full pipeline.
#
#   POST /v1/chat          multipart (question + optional image) -> the twin
#   GET  /v1/trace/{id}    read one retrieved trace (tenant-scoped)
#   GET  /v1/twin/status   index backend + per-tenant trace counts
#   GET  /                 the EPOCH chat UI (StaticFiles, mounted LAST)
#
# /v1/chat runs the real pipeline: verify_jwt (sub/role/hospital_id) -> bind
# tenant -> RETRIEVE from Dr. Chen's corpus for that tenant only (Trace Layer,
# epoch_gateway/retrieval.py) with a one-hop expansion along `related` links
# (Pattern Layer) -> ground a Vertex AI Gemini read on those traces and the
# image (Twin Layer) -> return the answer with the trace ids it actually drew
# on. The whole thing runs under a hard per-query deadline (15.3): a timeout
# is a 504, not a hang.
# ===========================================================================
import asyncio
import time
import uuid

import jwt as _pyjwt
from fastapi import File, Form, Header, UploadFile
from fastapi.staticfiles import StaticFiles

from . import epoch_auth as _auth
from .retrieval import INDEX

# Demo convenience: mint a valid bearer token from the browser so there is a
# one-click path in. Off by default — this deployment has no real IdP, so with
# it on the endpoint will hand an admin token for any tenant to any caller.
DEMO_TOKENS = os.environ.get("EPOCH_DEMO_TOKENS", "off").lower() in ("on", "1", "true", "yes")

GENAI_PROJECT  = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GENAI_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
GENAI_MODEL    = os.environ.get("EPOCH_GENAI_MODEL", "gemini-2.0-flash-001")

# 15.3's hard per-query deadline. Spec target is 8s; gemini-2.5-flash vision
# reads run 5-12s, so this deployment defaults to 15s and the mechanism stays
# real — set EPOCH_SLA_SECONDS=8 to watch reads 504.
SLA_SECONDS = float(os.environ.get("EPOCH_SLA_SECONDS", "15"))

TWIN_TOPK = int(os.environ.get("EPOCH_TWIN_TOPK", "4"))

_TWIN_SYSTEM = (
    "You are the cognitive twin of Dr. Sarah Chen, a thoracic radiologist. "
    "You are given RETRIEVED TRACES from her own corpus and, usually, a chest "
    "radiograph. Read the film the way she would: lead with the dominant "
    "finding, name the discriminating features it rests on, hedge explicitly "
    "where the image is ambiguous, and close with the single most useful next "
    "step. Ground every claim in a retrieved trace or in something clearly "
    "visible on the film — do not introduce findings neither supports. Never "
    "invent patient history. End your reply with one final line, exactly:\n"
    "TRACES_USED: <comma-separated ids of the traces you relied on>"
)

_TRACES_LINE = re.compile(r"^\s*TRACES_USED:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _context_block(traces: list[dict]) -> str:
    rows = []
    for t in traces:
        tag = " (linked)" if t.get("linked") else ""
        rows.append(
            f"[{t['id']}]{tag} {t['pattern']}\n"
            f"Findings: {t['finding']}\n"
            f"Discriminating features: {'; '.join(t['features'])}\n"
            f"Dr. Chen's reasoning: {t['reasoning']}\n"
            f"Her recommendation: {t['recommendation']}"
        )
    return "\n\n".join(rows)


def _split_traces_used(text: str, valid_ids: set[str]) -> tuple[str, list[str]]:
    """Pull the trailing TRACES_USED line out of the model's reply."""
    used: list[str] = []
    m = _TRACES_LINE.search(text)
    if m:
        for tok in re.split(r"[,\s]+", m.group(1)):
            tok = tok.strip().strip(".")
            if tok in valid_ids and tok not in used:
                used.append(tok)
        text = _TRACES_LINE.sub("", text).rstrip()
    return text, used


@app.on_event("startup")
async def _warm_index() -> None:
    if GENAI_PROJECT:
        asyncio.create_task(_safe_build())


async def _safe_build() -> None:
    try:
        await INDEX.build()
    except Exception:  # first real request will retry and surface the error
        pass


@app.get("/v1/twin/status")
async def twin_status():
    return INDEX.stats()


@app.get("/v1/trace/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    try:
        claims = verify_jwt(request.headers.get("Authorization", ""))
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=401)
    t = INDEX.get(claims["hospital_id"], trace_id)
    if not t:
        # 404 rather than 403 — don't confirm a trace exists for another tenant
        return JSONResponse({"detail": "no such trace for this tenant"}, status_code=404)
    return t


@app.post("/v1/chat")
async def v1_chat(
    request: Request,
    question: str = Form(...),
    image: UploadFile | None = File(default=None),
    x_tenant_id: str | None = Header(default=None),
):
    auth = request.headers.get("Authorization", "")
    try:
        claims = verify_jwt(auth)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=401)

    tenant = claims["hospital_id"]
    if x_tenant_id and TENANT_ISOLATION == "active" and x_tenant_id != tenant:
        return JSONResponse(
            {"detail": f"cross-tenant request: token={tenant} header={x_tenant_id}"},
            status_code=403,
        )

    q = redact_pii(question)

    if not GENAI_PROJECT:
        return JSONResponse(
            {"detail": "twin backend not configured (GOOGLE_CLOUD_PROJECT unset)"},
            status_code=503,
        )

    try:
        from google import genai
        from google.genai import types
    except Exception as e:  # pragma: no cover - import guard
        return JSONResponse({"detail": f"genai sdk unavailable: {e}"}, status_code=500)

    img_bytes = await image.read() if image is not None else None
    img_mime = (image.content_type or "image/jpeg") if image is not None else None
    t0 = time.perf_counter()

    async def _pipeline():
        # --- Trace Layer: retrieve from this tenant's corpus only ----------
        retrieved = await INDEX.retrieve(tenant, q, k=TWIN_TOPK)
        t_ret = time.perf_counter()

        # --- Twin Layer: ground the read on the retrieved traces ----------
        parts = []
        if img_bytes is not None:
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type=img_mime))
        parts.append(types.Part.from_text(text=(
            "RETRIEVED TRACES (from Dr. Chen's corpus for this tenant):\n\n"
            + (_context_block(retrieved) if retrieved
               else "(none matched — say so and answer only from the film)")
            + f"\n\n---\nQUESTION: {q}"
        )))
        client = genai.Client(
            vertexai=True, project=GENAI_PROJECT, location=GENAI_LOCATION
        )
        resp = await client.aio.models.generate_content(
            model=GENAI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=_TWIN_SYSTEM, temperature=0.2
            ),
        )
        return retrieved, (resp.text or ""), (t_ret - t0)

    try:
        retrieved, raw, retrieve_s = await asyncio.wait_for(
            _pipeline(), timeout=SLA_SECONDS
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            {"detail": f"twin exceeded the {SLA_SECONDS:g}s SLA",
             "sla_seconds": SLA_SECONDS},
            status_code=504,
        )
    except Exception as e:
        return JSONResponse({"detail": f"twin backend error: {e}"}, status_code=502)

    retrieved_ids = {t["id"] for t in retrieved}
    answer, used = _split_traces_used(raw, retrieved_ids)
    cited = used or [t["id"] for t in retrieved if not t.get("linked")]

    out = JSONResponse({
        "answer": redact_pii(answer),
        "cited_traces": cited,
        "retrieved": [
            {"id": t["id"], "pattern": t["pattern"],
             "score": round(t["score"], 3) if t.get("score") is not None else None,
             "linked": bool(t.get("linked"))}
            for t in retrieved
        ],
        "hospital_id": tenant,
        "role": claims["role"],
        "model": GENAI_MODEL,
        "retrieve_ms": round(retrieve_s * 1000),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        "sla_seconds": SLA_SECONDS,
    })
    out.headers["X-Epoch-Tenant"] = tenant
    out.headers["X-Epoch-Tenant-Isolation"] = TENANT_ISOLATION
    return out


@app.post("/v1/dev-token")
async def dev_token(request: Request):
    """
    DEMO ONLY. Mints a bearer token the gateway will accept, so the UI has a
    one-click sign-in — there is no identity provider wired to this deployment.
    Returns 404 unless EPOCH_DEMO_TOKENS is on. Same claims contract and
    signing key as epoch_auth.verify_jwt, so tokens from here and from
    mint_jwt.py are interchangeable.
    """
    if not DEMO_TOKENS:
        return JSONResponse({"detail": "demo token endpoint is disabled"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    role = str(body.get("role") or "admin").strip() or "admin"
    tenant = str(body.get("tenant") or "tenant_A").strip() or "tenant_A"

    now = int(time.time())
    ttl = 3600
    payload = {
        "sub": f"demo.{role}", "role": role, "hospital_id": tenant,
        "iss": _auth.JWT_ISSUER, "aud": _auth.JWT_AUDIENCE,
        "iat": now, "exp": now + ttl, "jti": str(uuid.uuid4()),
    }
    token = _pyjwt.encode(payload, _auth.JWT_SECRET, algorithm=_auth.JWT_ALG)
    return JSONResponse({"token": token, "role": role, "tenant": tenant, "exp": now + ttl})


# StaticFiles(html=True) serves index.html at "/" and handles the SPA route.
# Mounted LAST so it never shadows /health, /cluster/health, /v1/chat, or the
# /vN/agent/invoke routes registered above — FastAPI matches in registration
# order, and a "/" mount registered earlier would swallow every request.
app.mount(
    "/", StaticFiles(directory="epoch_gateway/static", html=True), name="ui"
)
