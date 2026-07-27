# AI Hub

Internal AI platform for multiple projects (School, ClinicFlow, GasFlow, CRM, ERP…).

Built as two layers per the PRD:

1. **Core Gateway** — [LiteLLM](https://github.com/BerriAI/litellm) (self-hosted): unified API, virtual keys, budgets, fallback, cost tracking, Admin UI.
2. **Custom Layer** — RAG Service + Prompt Library: document ingest, pgvector search with mandatory metadata filters, shared prompts.

Client apps never hold real provider API keys. They only use LiteLLM **Virtual Keys**.

## Architecture

```
[School] [ClinicFlow] [GasFlow] [CRM] ...
              |
              v
     [LiteLLM Proxy :4000]
      Virtual Keys / Fallback / Spend
              |
     +--------+--------+
     |                 |
  Providers      [RAG Service :8000]
  (Gemini…)       Postgres + pgvector
                  Documents + Prompts
```

## Quick start

### 1. Configure secrets

```bash
cp .env.example .env
# Set LITELLM_MASTER_KEY, GEMINI_API_KEY and/or OPENAI_API_KEY, etc.
```

### 2. Start the stack

```bash
docker compose up -d --build
```

Services:

| Service | URL |
|---|---|
| LiteLLM Proxy + Admin UI | http://localhost:4000 |
| RAG & Prompt Library API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres (pgvector) | localhost:5432 |

### 3. Bootstrap Teams + Virtual Keys

```bash
python scripts/bootstrap_teams.py
```

Creates Teams/Keys for `school`, `clinicflow`, `gasflow`, and `rag-service`.  
Copy the `rag-service` key into `.env` as `RAG_SERVICE_VIRTUAL_KEY`, then:

```bash
docker compose up -d rag-service
```

Keys are also written to `bootstrap-keys.json` (gitignored).

### 4. Seed Prompt Library

```bash
./scripts/seed_prompts.sh
# or:
docker compose exec rag-service python /app/scripts/seed_prompts.py
```

## Client usage

### Chat via LiteLLM (any project)

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $SCHOOL_VIRTUAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat-default",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Upload a document (RAG)

```bash
curl -X POST http://localhost:8000/rag/documents \
  -F project_id=school \
  -F 'metadata={"stage":"secondary","grade":"10"}' \
  -F file=@curriculum.pdf
```

### Ask a question (filtered RAG)

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "school",
    "question": "What is photosynthesis?",
    "metadata_filters": {"grade": "10"}
  }'
```

### Prompt Library

```bash
# List
curl "http://localhost:8000/prompts?category=School&project_id=school"

# Render variables
curl -X POST http://localhost:8000/prompts/{id}/render \
  -H "Content-Type: application/json" \
  -d '{"variables": {"subject": "Biology", "grade": "10", "language": "ar"}}'
```

## Project layout

```
├── docker-compose.yml          # LiteLLM + Postgres(pgvector) + RAG
├── litellm/config.yaml         # Models, fallbacks, cooldown (no custom rotation code)
├── scripts/
│   ├── init-db.sql             # rag_documents, rag_chunks, prompts + pgvector
│   ├── bootstrap_teams.py      # Teams + Virtual Keys
│   └── seed_prompts.py
└── rag-service/                # FastAPI custom layer
    ├── app/
    │   ├── api/                # /rag, /prompts
    │   ├── services/           # chunking, LiteLLM client, RAG, prompts
    │   └── models/
    └── tests/
```

## Security notes

- Real provider keys live only in LiteLLM env / secrets manager.
- Each app gets a Virtual Key scoped to its Team (`allowed_models`, budget, rpm/tpm).
- RAG Service uses its own Team (`rag-service`) Virtual Key for embeddings + chat.
- Do not commit `.env` or `bootstrap-keys.json`.

## Development / tests

```bash
cd rag-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Roadmap mapping (PRD)

| Phase | Status in this repo |
|---|---|
| Phase 1 — LiteLLM Core Gateway | `docker-compose` + `litellm/config.yaml` + bootstrap script |
| Phase 2 — RAG Service | `/rag/documents`, `/rag/query` with metadata filters + pgvector |
| Phase 3 — Prompt Library | `/prompts` CRUD + render + seed prompts |
