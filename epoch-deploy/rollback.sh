#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# rollback.sh — traffic split + instant rollback for epoch-gateway.
#
#   rollback.sh status                          show the live traffic split
#   rollback.sh split  rev-A=90,rev-B=10        shift traffic by revision
#   rollback.sh rollback                        send 100% to the previous revision
# ---------------------------------------------------------------------------

REGION="${GCP_REGION:-us-central1}"
PROJECT="${GCP_PROJECT:-epoch-prod-762035}"
ACTION="${1:-status}"

case "$ACTION" in
  split)
    gcloud run services update-traffic epoch-gateway \
      --region="$REGION" --project="$PROJECT" --to-revisions="$2"
    ;;
  rollback)
    LAST_STABLE=$(gcloud run revisions list --service=epoch-gateway \
      --region="$REGION" --project="$PROJECT" \
      --format="value(name)" --sort-by="~creationTimestamp" | sed -n '2p')
    if [ -z "$LAST_STABLE" ]; then
      echo "no previous revision to roll back to"; exit 1
    fi
    gcloud run services update-traffic epoch-gateway \
      --region="$REGION" --project="$PROJECT" --to-revisions="${LAST_STABLE}=100"
    echo "Rolled back to: ${LAST_STABLE}"
    ;;
  status)
    gcloud run services describe epoch-gateway \
      --region="$REGION" --project="$PROJECT" \
      --format="table(status.traffic[].revisionName,status.traffic[].percent)"
    ;;
  *)
    echo "usage: rollback.sh {status|split <revs>|rollback}"; exit 1
    ;;
esac
