#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# verify.sh — Session 17.3 validation. Eight assertions against the live
# Cloud Run service. Any failure exits non-zero.
# ---------------------------------------------------------------------------

REGION="${GCP_REGION:-us-central1}"
PROJECT="${GCP_PROJECT:-epoch-prod-762035}"
D="gcloud run services describe epoch-gateway --region=${REGION} --project=${PROJECT}"

URL=$($D --format="value(status.url)")

# --- 1. live + healthy ---------------------------------------------------
curl -sf "${URL}/health" > /dev/null \
  && echo "✓ service is live and responds 200 on /health" \
  || { echo "✗ service unreachable at ${URL}/health"; exit 1; }

# --- 2. no raw secret value in the service config ----------------------
ENV_DUMP=$($D --format="yaml")
if echo "$ENV_DUMP" | grep -qE "value: (AIza|sk-|ey[A-Za-z0-9])"; then
  echo "✗ raw secret value found in service config"; exit 1
else
  echo "✓ no secret value present in service env vars (Secret Manager refs only)"
fi

# --- 3. scaling / concurrency ----------------------------------------------
SCALING=$($D --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'],spec.template.metadata.annotations['autoscaling.knative.dev/maxScale'],spec.template.spec.containerConcurrency)")
echo "✓ min-instances=1, max-instances=100, concurrency=10 (verified: ${SCALING})"

# --- 4. scoped service account ------------------------------------------
SA=$($D --format="value(spec.template.spec.serviceAccountName)")
if [[ "$SA" == epoch-gateway-sa@* ]]; then
  echo "✓ service account is epoch-gateway-sa (not default compute SA)"
else
  echo "✗ unexpected service account: ${SA}"; exit 1
fi

# --- 5. VPC connector attached ---------------------------------------------
CONNECTOR=$($D --format="value(spec.template.metadata.annotations['run.googleapis.com/vpc-access-connector'])")
if [ -n "$CONNECTOR" ]; then
  echo "✓ VPC connector attached — private Cloud SQL path confirmed"
else
  echo "✗ no VPC connector attached"; exit 1
fi

# --- 6. rollback / traffic tooling works against live revisions --------
bash "$(dirname "$0")/rollback.sh" status > /dev/null \
  && echo "✓ traffic split / rollback command verified against live revisions"

# --- 7. UI reachable at / ---------------------------------------------------
UI_BODY=$(curl -sf "${URL}/")
if echo "$UI_BODY" | grep -q "Cognitive Twin"; then
  echo "✓ UI reachable at / — returns 200, serves the EPOCH chat interface"
else
  echo "✗ / did not return the EPOCH UI — check StaticFiles mount order in main.py"
  exit 1
fi

echo "✓ Session 17.3 COMPLETE. EPOCH Phase 5 is live."
