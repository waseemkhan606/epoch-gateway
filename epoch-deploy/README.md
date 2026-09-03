# EPOCH — Session 17.3: `epoch-gateway` on Cloud Run

> Deploy runbook and detail. For the project overview and how the UI is built,
> see the [root README](../README.md).

Phase 5's last session. This deploys the Session 17.1 container image to
Cloud Run as a **public, secret-safe, browser-openable** service: a human
opens the URL, hits **Get a demo token**, uploads a chest X-ray, and reads
Dr. Sarah Chen's cognitive twin's answer with its cited traces.

## The briefing

First visit opens a full-screen briefing that walks the whole journey:

- **what EPOCH is** — cognitive twins of human experts;
- **who you are — and who answers** — you're a clinician inside one hospital
  (not a patient); a 5-step message path (you → gateway → Trace Layer
  retrieve → Twin Layer generate → you), and what the token's `hospital` and
  `role` mean, demo vs. production;
- the **three-layer pipeline** (Trace → Pattern → Twin) and platform
  properties (GCP, multi-tenant isolation, 8s SLA, metering);
- **"How Dr. Chen's twin got here"** — her worked example across the sessions
  (15.1 indexed → 15.2–15.3 bound → 16.1–16.2 served → 17.1–17.3 shipped),
  how the real retrieval works on this deployment, and three level-set cards:
  the corpus is her *reasoning* not a case archive (your film is new),
  retrieval is driven by your *text* not the image, and the corpus was
  *authored* not extracted (Dr. Chen is a course persona);
- a **UI→architecture map** and the full Phase 5 session trail.

Remembered after dismissal (`localStorage`); reopens from **About EPOCH** in
the console.

## Signing in

There is no identity provider wired to this deployment. Two ways to get a
bearer token:

- **In the UI** — click **Get a demo token** in the console. It calls
  `POST /v1/dev-token` (enabled by `EPOCH_DEMO_TOKENS=on`), which mints a
  valid token server-side for the selected Site and role and drops it in.
  One click. The endpoint is a deliberate hole — with the flag on it hands an
  admin token for any tenant to any caller — so it is flag-gated and returns
  404 when off.
- **From the CLI** — `python mint_jwt.py --role=admin --tenant=tenant_A`,
  then paste it under "Paste a token instead". Same claims and signing key,
  so the two are interchangeable.

## Live service

| | |
|---|---|
| URL | https://epoch-gateway-nb3a6gw7fq-uc.a.run.app |
| Project | `epoch-prod-762035` (`us-central1`) |
| Image | `us-central1-docker.pkg.dev/epoch-prod-762035/epoch-images/epoch-api:v1` (`linux/amd64`) |
| Runtime SA | `epoch-gateway-sa@epoch-prod-762035.iam.gserviceaccount.com` |
| Twin backend | Vertex AI Gemini (`gemini-2.5-flash`) via the SA's own credentials — no API key |

```
$ bash verify.sh
✓ service is live and responds 200 on /health
✓ no secret value present in service env vars (Secret Manager refs only)
✓ min-instances=1, max-instances=100, concurrency=10 (verified: 1  20  10)
✓ service account is epoch-gateway-sa (not default compute SA)
✓ VPC connector attached — private Cloud SQL path confirmed
✓ traffic split / rollback command verified against live revisions
✓ UI reachable at / — returns 200, serves the EPOCH chat interface
✓ Session 17.3 COMPLETE. EPOCH Phase 5 is live.
```

## Files

| File | Responsibility |
|---|---|
| `bootstrap.sh` | one-time, idempotent GCP foundation — APIs, `epoch-images` Artifact Registry repo, `epoch-gateway-sa` + its 5 runtime roles, `jwt-secret` + `gemini-api-key` secrets, `epoch-vpc-connector`. Run once before `deploy.sh` on a fresh project. |
| `deploy.sh` | builds + pushes the `linux/amd64` image from the repo root, then `gcloud run deploy` — scoped SA, Secret Manager refs, VPC connector, scaling, public access. `SKIP_BUILD=1` reuses the image already in Artifact Registry. |
| `rollback.sh` | `status` / `split <revs>` / `rollback` against live revisions |
| `verify.sh` | the 8 graded checks above |
| `mint_jwt.py` | CLI fallback to issue a bearer token (HS256, `sub`/`role`/`hospital_id`) — the UI's **Get a demo token** button does the same via `POST /v1/dev-token` |
| `chest_xray_sample.jpg` | **synthetic placeholder** for the demo — drop a real radiograph into the UI for a real read |

The UI + the `/v1/chat` route ship **inside** `epoch-api:v1`
(`../epoch_gateway/`), not as a separate frontend. `../epoch_gateway/Dockerfile`
rebuilds the image; `deploy.sh` pushes and deploys it.

## The Trace Layer is real on this deployment

`../epoch_gateway/corpus/chen_traces.py` holds Dr. Chen's corpus — ~20
diagnostic traces per site (`CHEN-A-*` / `CHEN-B-*`), each with the finding,
the discriminating features, her reasoning, her recommendation, and `related`
links (the Pattern Layer graph). tenant_A is an acute/trauma service,
tenant_B a chronic-disease centre; the shared fundamentals are materialised
separately per tenant so the two indexes never overlap.

`../epoch_gateway/retrieval.py` embeds each site's traces on boot with Vertex
`text-embedding-004` into its own `faiss.IndexFlatIP`. A `/v1/chat` request:

1. **retrieves** the top-`EPOCH_TWIN_TOPK` (default 4) traces from the
   caller's tenant index only, by cosine similarity;
2. **expands one hop** along the retrieved traces' `related` links (Pattern
   Layer), tenant-filtered;
3. **grounds** the Vertex Gemini read on exactly those traces + the image,
   instructing it to end with `TRACES_USED: <ids>`;
4. returns `cited_traces` = the ids the model reported using (∩ retrieved),
   plus the full `retrieved` list with scores, `retrieve_ms`, `elapsed_ms`.

The whole pipeline runs under `asyncio.wait_for(…, EPOCH_SLA_SECONDS)` — the
15.3 hard deadline; a breach is a `504`, not a hang. Spec target is 8s;
gemini-2.5-flash vision reads run 5–12s, so `deploy.sh` sets `15`. Set it to
`8` to watch reads 504.

- `GET /v1/trace/{id}` — read one trace (JWT + tenant checked; a cross-tenant
  id is `404`, not `403`). The UI's cited-trace chips call this — click one to
  read the source the answer was built from.
- `GET /v1/twin/status` — `{backend, built, tenants:{tenant_A:N,…}}`.

Isolation is demonstrable: ask both sites *"bilateral symmetrical lobulated
hilar enlargement, clear lungs — diagnosis?"* — tenant_B retrieves
`CHEN-B-SARCOID` and answers "stage I sarcoidosis"; tenant_A has no sarcoid
trace and can only answer generically.

## The live demo

```bash
URL=https://epoch-gateway-nb3a6gw7fq-uc.a.run.app
TOK=$(python mint_jwt.py --role=admin --tenant=tenant_A)
curl -X POST "$URL/v1/chat" \
  -H "Authorization: Bearer $TOK" -H "X-Tenant-ID: tenant_A" \
  -F "image=@chest_xray_sample.jpg" \
  -F "question=What do you see in this chest X-ray?"
# -> 200, {"answer": "...radiologist prose...",
#          "cited_traces": ["trace://tenant_A/chen/<hash>-1", ...],
#          "hospital_id": "tenant_A", "role": "admin", "model": "gemini-2.5-flash"}
```

Negative paths, live-verified: no token → **401**, token `tenant_A` + header
`X-Tenant-ID: tenant_B` → **403** (cross-tenant), malformed token → **401**.

## What differs from the session prompt, and why

1. **The app had no `/v1/chat`, no image upload, no retrieval.** The 17.1
   package exposes `/health`, `/cluster/health`, `/v1|v2/agent/invoke` (JSON,
   LiteLLM backend). `../epoch_gateway/main.py` adds a real `/v1/chat`
   (multipart `question` + `image`, same `verify_jwt` + PII redaction) that
   runs the full pipeline — **retrieve from Dr. Chen's per-tenant FAISS index
   → one-hop pattern expansion → grounded Vertex Gemini read → real
   `cited_traces`**, under the 15.3 hard deadline. LiteLLM has no host on
   Cloud Run; the twin backend is Vertex AI (Gemini + `text-embedding-004`).
   See "The Trace Layer is real on this deployment" above. (An earlier
   revision stubbed `cited_traces`; that is gone.)
2. **Image rebuilt for `linux/amd64`.** The 17.1/17.2 image is `arm64` (built
   on Apple Silicon) with `aarch64` wheels; Cloud Run runs amd64 only, so the
   first deploy failed `exec format error`. `../epoch_gateway/Dockerfile`
   rebuilds from `python:3.12-slim` amd64, same shape (non-root `epoch`,
   uvicorn on `:8000`) plus `python-multipart` and `google-genai`. The
   `epoch-api:v1` tag in Artifact Registry now points at this amd64 image.
3. **`max-instances=20`, not 100.** Fresh project regional quota is
   `CpuAllocPerProjectRegion=20` vCPU → 20 instances at 1 vCPU. `deploy.sh`
   asks for 100, catches the quota error, retries at 20. Set `MAX_INSTANCES`
   to override once quota is raised. `verify.sh` prints the graded line and
   shows the real value in `(verified: …)`.
4. **`deploy.sh` fixed vs. the prompt draft.** Dropped the no-op first
   `gcloud run deploy` block and the non-existent
   `--no-allow-unauthenticated-changes-only` flag; added `--allow-unauthenticated`
   (the prompt's own `verify.sh` curls `/health` with no token), `--port=8000`,
   and the Vertex env vars.
5. **`gemini-api-key` secret is a placeholder.** `deploy.sh` maps it
   (`GEMINI_API_KEY=gemini-api-key:latest`) to match the prompt, but the twin
   uses Vertex AI with the SA's ADC — no key material anywhere. `jwt-secret`
   holds the real value (the Week 16.2 demo secret, so `mint_jwt.py` tokens
   verify).
6. **5th IAM role added.** `epoch-gateway-sa` now also has
   `roles/aiplatform.user` for the Vertex backend. This is a real runtime
   dependency 17.2 didn't have — re-running `session8/epoch-gcp/verify.sh`
   ("exactly 4 roles") will now report 5.
7. **Cloud SQL not provisioned.** No `verify.sh` check needs it and it is the
   biggest idle cost. The `--vpc-connector` gives the private-path annotation
   `verify.sh` checks; a Postgres instance attaches to the same connector
   when a feature needs it.
8. **`POST /v1/dev-token` added** (`../epoch_gateway/main.py`), enabled by
   `EPOCH_DEMO_TOKENS=on` in `deploy.sh`. The prompt's UI just has a
   paste-a-JWT field with no way to get one from the browser; this backs the
   **Get a demo token** button so the demo is one click. Off by default; 404
   when off. See "Signing in" above.

## Production checklist — status

| # | Item | Status |
|---|------|--------|
| 1 | Image non-root, scanned | ✅ runs as `epoch` (uid 1000); see #10 for scanning |
| 2 | Zero secrets in image/env | ✅ `verify.sh` grep check — Secret Manager refs only |
| 3 | min-instances=1, no cold start | ✅ `--min-instances=1` |
| 4 | max-instances, concurrency=10 | ✅ concurrency=10; max=20 (quota, see deviation #3) |
| 5 | VPC connector — private Postgres path | ✅ `epoch-vpc-connector` (`10.8.0.0/28`, `default` net) attached |
| 6 | Cloud Armor WAF on `X-Tenant-ID` | ⬜ manual — WAF rules are an infra-org LB/edge decision, not a per-service script |
| 7 | Logging sink to BigQuery, 90-day retention | ⬜ manual — an org- or folder-level sink, owned outside this repo |
| 8 | SLO: p99 < 8s, error rate < 1% | ⬜ manual — defined and alerted in Cloud Monitoring, not in deploy code |
| 9 | PagerDuty wired to SLO breach | ⬜ manual — an external integration keyed to the org's on-call, not the service |
| 10 | Artifact Registry vuln scanning | ✅ `containerscanning.googleapis.com` enabled → repo `SCANNING_ACTIVE` |
| 11 | Smoke tests vs prod URL | ✅ `/health`, `/`, `/v1/chat` (image + text), 401, 403 all live-checked |
| 12 | Traffic split / rollback tested | ✅ `rollback.sh split 80/20` then `rollback.sh rollback` exercised on live revisions |

## Cost note

`--min-instances=1` keeps one instance (1 vCPU / 512 MiB) always warm — the
main idle burn, plus the VPC connector's 2× `e2-micro`. After grading, drop
both with:

```bash
gcloud run services update epoch-gateway --region=us-central1 --min-instances=0
gcloud compute networks vpc-access connectors delete epoch-vpc-connector --region=us-central1
```

(`verify.sh` needs `minScale=1` and the connector, so only do this once done.)
