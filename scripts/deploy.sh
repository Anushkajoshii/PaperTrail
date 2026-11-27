#!/usr/bin/env bash
# Build the Lambda image, push it to ECR and apply Terraform.
#   AWS_PROFILE=portfolio scripts/deploy.sh plan     # show what would change (creates nothing)
#   AWS_PROFILE=portfolio scripts/deploy.sh apply    # build, push and deploy (asks to confirm)
#   AWS_PROFILE=portfolio scripts/deploy.sh destroy  # remove everything (asks to confirm)
set -euo pipefail
cd "$(dirname "$0")/.."

ACTION="${1:-plan}"
REGION="${AWS_REGION:-ap-southeast-2}"
TF="terraform -chdir=infra"
TAG="$(git rev-parse --short=12 HEAD)$(git diff --quiet || echo -dirty)"

[[ -f infra/backend.hcl ]] || {
  echo "infra/backend.hcl is missing. Run the one-time bootstrap first (docs/DEPLOY.md)."
  exit 1
}
$TF init -input=false -backend-config=backend.hcl >/dev/null

case "$ACTION" in
  plan)
    $TF plan -input=false -var "image_tag=$TAG"
    ;;
  apply)
    # 1) The image registry must exist before an image can be pushed.
    $TF apply -input=false -target=aws_ecr_repository.app -target=aws_ecr_lifecycle_policy.app
    REPO="$($TF output -raw ecr_repository_url)"
    # 2) Build for arm64 (Graviton) and push.
    aws ecr get-login-password --region "$REGION" |
      docker login --username AWS --password-stdin "${REPO%%/*}"
    docker build --platform linux/arm64 --provenance=false -f Dockerfile.lambda -t "$REPO:$TAG" .
    docker push "$REPO:$TAG"
    # 3) Everything else, using that image.
    $TF apply -input=false -var "image_tag=$TAG"
    echo
    echo "Live at: $($TF output -raw app_url)"
    ;;
  destroy)
    $TF destroy -input=false -var "image_tag=$TAG"
    ;;
  *)
    echo "usage: $0 plan|apply|destroy" >&2
    exit 2
    ;;
esac
