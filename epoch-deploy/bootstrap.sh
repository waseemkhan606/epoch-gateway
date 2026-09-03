#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# bootstrap.sh — one-time GCP foundation for a clean clone.
#
# Idempotent. Stands up everything `deploy.sh` assumes already exists:
#   - enabled APIs
#   - the epoch-images Artifact Registry repo
#   - the epoch-gateway-sa service account + its 5 runtime roles
#   - the jwt-secret and gemini-api-key secrets
#   - the epoch-vpc-connector Serverless VPC connector
#
# Prereqs: gcloud authenticated (`gcloud auth login`), a project with billing
# linked, and Docker. Then:  bash bootstrap.sh  &&  bash deploy.sh  &&  bash verify.sh
#
#   GCP_PROJECT   (required unless the default is what you want)
#   GCP_REGION    (default: us-central1)
#   JWT_SECRET    (default: the Week 16 demo secret — matches mint_jwt.py)
# ---------------------------------------------------------------------------

PROJECT="${GCP_PROJECT:-epoch-prod-762035}"
REGION="${GCP_REGION:-us-central1}"
SA_NAME="epoch-gateway-sa"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
JWT_SECRET_VALUE="${JWT_SECRET:-epoch-demo-secret-rotate-via-kms-in-prod}"

echo "Project: ${PROJECT}   Region: ${REGION}"
gcloud config set project "$PROJECT" --quiet

echo "==> Enabling APIs"
gcloud services enable \
  run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com \
  aiplatform.googleapis.com vpcaccess.googleapis.com compute.googleapis.com \
  sqladmin.googleapis.com --quiet

echo "==> Artifact Registry repo: epoch-images"
gcloud artifacts repositories describe epoch-images --location="$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create epoch-images \
       --repository-format=docker --location="$REGION" \
       --description="EPOCH production images"

echo "==> Service account: ${SA}"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SA_NAME" --display-name="EPOCH Gateway Runtime"

echo "==> Runtime roles (5)"
for ROLE in \
  roles/secretmanager.secretAccessor \
  roles/run.invoker \
  roles/storage.objectViewer \
  roles/cloudsql.client \
  roles/aiplatform.user
do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${SA}" --role="$ROLE" --condition=None --quiet >/dev/null
  echo "   ✓ ${ROLE}"
done

echo "==> Secrets"
for S in jwt-secret gemini-api-key; do
  if ! gcloud secrets describe "$S" >/dev/null 2>&1; then
    case "$S" in
      jwt-secret)     printf '%s' "$JWT_SECRET_VALUE" ;;
      gemini-api-key) printf '%s' "unused-vertex-uses-adc" ;;
    esac | gcloud secrets create "$S" --replication-policy=automatic --data-file=-
  fi
  gcloud secrets add-iam-policy-binding "$S" \
    --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" \
    --condition=None --quiet >/dev/null
  echo "   ✓ ${S}"
done

echo "==> Serverless VPC connector: epoch-vpc-connector"
if ! gcloud compute networks vpc-access connectors describe epoch-vpc-connector \
       --region="$REGION" >/dev/null 2>&1; then
  gcloud compute networks vpc-access connectors create epoch-vpc-connector \
    --region="$REGION" --network=default --range=10.8.0.0/28 \
    --min-instances=2 --max-instances=3 --machine-type=e2-micro
fi

echo ""
echo "Foundation ready. Next:  bash deploy.sh  &&  bash verify.sh"
