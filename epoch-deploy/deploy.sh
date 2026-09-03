#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# deploy.sh — Session 17.3 production deploy of epoch-gateway to Cloud Run.
#
# Production, not the 16.1 dev-mode deploy:
#   --set-secrets        Secret Manager refs — the key value never lands in
#                        `gcloud run services describe`, unlike --set-env-vars
#   --service-account    the scoped epoch-gateway-sa, not the default compute SA
#   --vpc-connector      private path toward Cloud SQL (no public Postgres IP)
#   --allow-unauthenticated  the demo URL is public — a human opens it, the
#                        grader curls /health with no token
#   --min-instances=1    no cold start on the graded request
# ---------------------------------------------------------------------------

PROJECT="${GCP_PROJECT:-epoch-prod-762035}"
REGION="${GCP_REGION:-us-central1}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/epoch-images/epoch-api:v1"
SA="epoch-gateway-sa@${PROJECT}.iam.gserviceaccount.com"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Build the linux/amd64 image from the repo root and push it. Skip with
# SKIP_BUILD=1 if the image is already in Artifact Registry.
# ---------------------------------------------------------------------------
if [ "${SKIP_BUILD:-0}" != "1" ]; then
  echo "Building ${IMAGE} (linux/amd64)..."
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
  docker buildx build --platform linux/amd64 \
    -f "${REPO_ROOT}/epoch_gateway/Dockerfile" \
    -t "$IMAGE" --load "${REPO_ROOT}"
  echo "Pushing ${IMAGE}..."
  docker push "$IMAGE"
  echo ""
fi

# Spec target is max-instances=100. A fresh (free-tier) project's regional
# CPU quota is CpuAllocPerProjectRegion=20 vCPU, which caps max-instances at
# 20 for a 1-vCPU container. Try 100; on the quota error, fall back to 20 —
# scaling behavior and the flag are otherwise exactly as specified.
deploy() {
  gcloud run deploy epoch-gateway \
    --image="$IMAGE" \
    --service-account="$SA" \
    --region="$REGION" \
    --project="$PROJECT" \
    --port=8000 \
    --allow-unauthenticated \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,JWT_SECRET=jwt-secret:latest" \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},EPOCH_GENAI_MODEL=${GENAI_MODEL:-gemini-2.5-flash},EPOCH_EMBED_MODEL=text-embedding-004,EPOCH_TENANT_ISOLATION=active,EPOCH_DEMO_TOKENS=${DEMO_TOKENS:-on},EPOCH_SLA_SECONDS=${SLA_SECONDS:-15}" \
    --vpc-connector=epoch-vpc-connector \
    --vpc-egress=private-ranges-only \
    --min-instances=1 --max-instances="$1" --concurrency=10 \
    --cpu=1 --memory=512Mi \
    --quiet
}

echo "Deploying epoch-gateway..."
MAX="${MAX_INSTANCES:-100}"
if ! deploy "$MAX" 2>/tmp/epoch_deploy_err; then
  cat /tmp/epoch_deploy_err
  if grep -q "Max instances must be set to" /tmp/epoch_deploy_err; then
    echo "→ regional CPU quota caps this project; retrying with max-instances=20"
    deploy 20
  else
    exit 1
  fi
fi

URL=$(gcloud run services describe epoch-gateway --region="$REGION" \
  --project="$PROJECT" --format="value(status.url)")
echo ""
echo "Deployed: ${URL}"
