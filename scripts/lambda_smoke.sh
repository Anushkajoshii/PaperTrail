#!/usr/bin/env bash
# Smoke-test the Lambda image locally with the Lambda Runtime Interface Emulator (built into
# the AWS base image): sends API Gateway events for the API and the web app. No AWS needed.
#   scripts/lambda_smoke.sh papertrail-lambda:local
set -euo pipefail
IMAGE="${1:-papertrail-lambda:local}"
NAME="pt-lambda-smoke-$$"

docker run -d --rm --name "$NAME" -p 9009:8080 \
  -e PAPERTRAIL_STORE_BACKEND=memory -e PAPERTRAIL_LLM_PROVIDER=mock "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
URL=http://localhost:9009/2015-03-31/functions/function/invocations

event() {
  printf '{"version":"2.0","routeKey":"$default","rawPath":"%s","rawQueryString":"",
  "headers":{"host":"example.test"},"requestContext":{"http":{"method":"GET","path":"%s",
  "protocol":"HTTP/1.1","sourceIp":"127.0.0.1","userAgent":"smoke"},"domainName":"example.test",
  "stage":"$default","requestId":"r1","accountId":"1","apiId":"a"},"isBase64Encoded":false}' "$1" "$1"
}

for i in $(seq 1 20); do curl -s -o /dev/null "$URL" -d '{}' && break; sleep 1; done

health="$(curl -sf "$URL" -d "$(event /api/health)")"
echo "$health" | grep -q '"statusCode": *200' && echo "$health" | grep -q 'llm_provider' ||
  { echo "API health failed: $health"; exit 1; }
home="$(curl -sf "$URL" -d "$(event /)")"
echo "$home" | grep -q '"statusCode": *200' && echo "$home" | grep -q 'root' ||
  { echo "Web app failed: ${home:0:300}"; exit 1; }
echo "Lambda image OK: /api/health and / both respond"
