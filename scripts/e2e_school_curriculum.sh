#!/usr/bin/env bash
# End-to-end smoke test for school curriculum RAG + LiteLLM chat.
# Usage:
#   export LITELLM_MASTER_KEY=...
#   export SCHOOL_VIRTUAL_KEY=...
#   export RAG_SERVICE_API_KEY=...
#   ./scripts/e2e_school_curriculum.sh /path/to/curriculum.pdf "What is photosynthesis?"
set -euo pipefail

PDF_PATH="${1:-}"
QUESTION="${2:-}"
LITELLM_URL="${LITELLM_URL:-http://127.0.0.1:4000}"
RAG_URL="${RAG_URL:-http://127.0.0.1:8000}"

if [[ -z "${SCHOOL_VIRTUAL_KEY:-}" || -z "${RAG_SERVICE_API_KEY:-}" ]]; then
  echo "ERROR: Set SCHOOL_VIRTUAL_KEY and RAG_SERVICE_API_KEY in the environment." >&2
  exit 1
fi
if [[ -z "$PDF_PATH" || ! -f "$PDF_PATH" ]]; then
  echo "ERROR: Provide an existing PDF path as arg1." >&2
  exit 1
fi
if [[ -z "$QUESTION" ]]; then
  echo "ERROR: Provide a question as arg2." >&2
  exit 1
fi

echo "==> 1) LiteLLM chat via school virtual key"
CHAT_RESP="$(curl -sS -w '\n%{http_code}' "$LITELLM_URL/v1/chat/completions" \
  -H "Authorization: Bearer $SCHOOL_VIRTUAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"chat-default","messages":[{"role":"user","content":"Reply with exactly: OK"}]}')"
CHAT_BODY="$(echo "$CHAT_RESP" | sed '$d')"
CHAT_CODE="$(echo "$CHAT_RESP" | tail -n1)"
echo "HTTP $CHAT_CODE"
echo "$CHAT_BODY" | head -c 500; echo
if [[ "$CHAT_CODE" != "200" ]]; then
  echo "FAIL: chat/completions did not return 200" >&2
  exit 2
fi

echo "==> 2) Upload curriculum PDF to RAG"
UPLOAD_RESP="$(curl -sS -w '\n%{http_code}' -X POST "$RAG_URL/rag/documents" \
  -H "X-API-Key: $RAG_SERVICE_API_KEY" \
  -F project_id=school \
  -F 'metadata={"stage":"secondary","grade":"10","subject":"biology"}' \
  -F "file=@${PDF_PATH}")"
UPLOAD_BODY="$(echo "$UPLOAD_RESP" | sed '$d')"
UPLOAD_CODE="$(echo "$UPLOAD_RESP" | tail -n1)"
echo "HTTP $UPLOAD_CODE"
echo "$UPLOAD_BODY"
if [[ "$UPLOAD_CODE" != "201" ]]; then
  echo "FAIL: document upload did not return 201" >&2
  exit 3
fi

echo "==> 3) Query RAG with metadata filters"
QUERY_JSON="$(python3 - <<PY
import json
print(json.dumps({
  "project_id": "school",
  "question": """$QUESTION""",
  "metadata_filters": {"grade": "10", "subject": "biology"},
}))
PY
)"
QUERY_RESP="$(curl -sS -w '\n%{http_code}' -X POST "$RAG_URL/rag/query" \
  -H "X-API-Key: $RAG_SERVICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$QUERY_JSON")"
QUERY_BODY="$(echo "$QUERY_RESP" | sed '$d')"
QUERY_CODE="$(echo "$QUERY_RESP" | tail -n1)"
echo "HTTP $QUERY_CODE"
echo "$QUERY_BODY"
if [[ "$QUERY_CODE" != "200" ]]; then
  echo "FAIL: rag query did not return 200" >&2
  exit 4
fi

echo
echo "SUCCESS (HTTP paths). Manually verify:"
echo "  - Answer is grounded in the PDF"
echo "  - sources[].filename matches the upload"
echo "  - LiteLLM Admin UI shows school spend for the chat call"
