# AiHub

بنية تحتية داخلية للذكاء الاصطناعي فوق [LiteLLM](https://github.com/BerriAI/litellm).  
المواصفات: [`AI_HUB_PRD_v3.md`](./AI_HUB_PRD_v3.md)

## Phase 1 — Core Gateway

LiteLLM Proxy + PostgreSQL عبر Docker Compose.

### المتطلبات

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (أو Docker Engine + Compose)
- مفتاح Gemini (أساسي) ومفتاح Groq (fallback)

### التشغيل

```bash
# 1) انسخ إعدادات البيئة
copy .env.example .env

# 2) عدّل .env: LITELLM_MASTER_KEY, LITELLM_SALT_KEY, POSTGRES_PASSWORD, GEMINI_API_KEY, GROQ_API_KEY

# 3) شغّل الـ stack
docker compose up -d

# 4) تحقق من الصحة
curl http://localhost:4000/health/readiness
```

### Admin UI

- الرابط: http://localhost:4000/ui  
- Username: `admin`  
- Password: قيمة `LITELLM_MASTER_KEY` من ملف `.env`

### إنشاء Team + Virtual Key لكل مشروع

من الـ Admin UI (أو عبر API بالمaster key):

| المشروع    | Team name   |
|-----------|-------------|
| School    | school      |
| ClinicFlow| clinicflow  |
| GasFlow   | gasflow     |
| RAG (Phase 2) | rag-service |

لكل Team: Virtual Key مع `allowed_models`, `max_budget`, `rpm_limit` / `tpm_limit`.

### اختبار من مشروع

```bash
curl http://localhost:4000/v1/chat/completions ^
  -H "Authorization: Bearer sk-<VIRTUAL_KEY>" ^
  -H "Content-Type: application/json" ^
  -d "{\"model\": \"chat-default\", \"messages\": [{\"role\": \"user\", \"content\": \"مرحبا\"}]}"
```

الموديلات المتاحة في `litellm/config.yaml`:

| model name     | الاستخدام        |
|----------------|------------------|
| `chat-default` | الافتراضي للمشاريع |
| `gemini-flash` | Gemini مباشرة    |
| `groq-llama`   | Groq (fallback)  |
| `text-embedding` | Embeddings لـ RAG |

### إيقاف

```bash
docker compose down
```

البيانات تبقى في volume `aihub_postgres_data`. لحذفها نهائيًا: `docker compose down -v`.

## المراحل التالية

- **Phase 2** — RAG Service (`pgvector` + ingest/query)
- **Phase 3** — Prompt Library
