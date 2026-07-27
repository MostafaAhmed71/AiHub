# AI Hub — VPS Deployment Checklist

هدف هذا الملف: نشر الأساس على VPS ثم اختبار مسار واحد فقط (بوت المنهج / `school`) قبل أي توسّع.

> لا تكمل لمشاريع أخرى قبل نجاح الاختبار end-to-end على `school`.

---

## 0) ما تحتاجه قبل ما تبدأ

- VPS (Ubuntu 22.04/24.04 مفضّل) مع وصول SSH
- دومين اختياري (ليس مطلوبًا لهذه المرحلة)
- مفاتيح مزود حقيقية لاثنين على الأقل إن أمكن:
  - `GEMINI_API_KEY` (أساسي)
  - `OPENAI_API_KEY` (embeddings و/أو fallback) — مطلوب إذا كان `EMBEDDING_MODEL=text-embedding-3-small`
- مستند PDF واحد حقيقي للمنهج (اختبار RAG)

---

## 1) Checklist قبل `docker compose up`

نفّذ بالترتيب وعلّم كل بند:

### أ. تجهيز السيرفر
- [ ] تحديث النظام: `sudo apt update && sudo apt upgrade -y`
- [ ] تثبيت Docker Engine + Compose plugin (الطريقة الرسمية من docs.docker.com)
- [ ] التأكد: `docker --version` و `docker compose version`
- [ ] إضافة مستخدمك لمجموعة docker ثم إعادة الدخول: `sudo usermod -aG docker $USER`
- [ ] فتح/تقييد المنافذ في الـ firewall (UFW مثال):
  - [ ] SSH فقط من IP موثوق إن أمكن
  - [ ] `4000` (LiteLLM) و `8000` (RAG) — مؤقتًا للاختبار، أو اجعلها localhost فقط عبر SSH tunnel
  - [ ] **لا تفتح `5432` للعامة أبدًا**
- [ ] إنشاء مجلد العمل: `mkdir -p ~/aihub && cd ~/aihub`
- [ ] استنساخ المستودع: `git clone <repo-url> .` (أو رفع الملفات)

### ب. إعداد الأسرار بأمان (بدون Secrets Manager متقدم)
- [ ] إنشاء ملف أسرار بصلاحيات مقيدة:
  ```bash
  cp .env.example .env
  chmod 600 .env
  ```
- [ ] توليد مفاتيح عشوائية قوية:
  ```bash
  # Master Key لـ LiteLLM
  echo "LITELLM_MASTER_KEY=sk-$(openssl rand -hex 24)"
  # Salt
  echo "LITELLM_SALT_KEY=$(openssl rand -hex 32)"
  # API key لحماية RAG/Prompts (Header: X-API-Key)
  echo "RAG_SERVICE_API_KEY=$(openssl rand -hex 32)"
  # كلمة مرور Postgres
  echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
  ```
- [ ] ضع القيم في `.env` (لا تلصقها في Git / Slack / Issues)
- [ ] ضع `GEMINI_API_KEY` و `OPENAI_API_KEY` في `.env`
- [ ] تأكد أن `.env` في `.gitignore` (موجود بالفعل)
- [ ] لا تستخدم قيم `change-me` الافتراضية في الإنتاج
- [ ] اختياري أقوى قليلًا بدون Secrets Manager كامل:
  - خزّن `.env` في `/etc/aihub/.env` بملكية `root:root` و`chmod 600`
  - شغّل compose بـ `--env-file /etc/aihub/.env`
  - أو استخدم Docker Compose `secrets:` لاحقًا بعد نجاح الاختبار

### ج. تشغيل الـ stack
- [ ] من جذر المشروع:
  ```bash
  docker compose --env-file .env up -d --build
  ```
- [ ] انتظر healthy:
  ```bash
  docker compose ps
  curl -s http://127.0.0.1:4000/health/liveliness
  curl -s http://127.0.0.1:8000/health
  ```
- [ ] شغّل bootstrap للـ Teams/Keys:
  ```bash
  LITELLM_BASE_URL=http://127.0.0.1:4000 \
  LITELLM_MASTER_KEY='(من .env)' \
  python3 scripts/bootstrap_teams.py
  ```
- [ ] انسخ مفتاح `rag-service` من المخرجات إلى `.env` كـ `RAG_SERVICE_VIRTUAL_KEY`
- [ ] أعد تشغيل RAG فقط:
  ```bash
  docker compose up -d rag-service
  ```
- [ ] (اختياري) seed prompts: `./scripts/seed_prompts.sh`

---

## 2) اختبار End-to-End — مشروع واحد فقط: بوت المنهج (`school`)

استخدم السكربت الجاهز أو نفّذ يدويًا.

### أ. Chat عبر Virtual Key + ظهوره في Admin UI
```bash
export SCHOOL_VIRTUAL_KEY='(من bootstrap-keys.json)'
curl -s http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer $SCHOOL_VIRTUAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chat-default",
    "messages": [{"role":"user","content":"قل مرحبا في جملة واحدة"}]
  }'
```
- [ ] الرد ناجح (ليس 401/500)
- [ ] افتح LiteLLM Admin UI على `:4000` بالـ Master Key
- [ ] تأكد ظهور الطلب تحت Team/Key الخاصة بـ `school` (tokens/cost)

### ب. RAG: رفع PDF حقيقي → سؤال → إجابة من المصدر فقط
```bash
export RAG_API_KEY='(RAG_SERVICE_API_KEY من .env)'

# 1) رفع مستند المنهج
curl -s -X POST http://127.0.0.1:8000/rag/documents \
  -H "X-API-Key: $RAG_API_KEY" \
  -F project_id=school \
  -F 'metadata={"stage":"secondary","grade":"10","subject":"biology"}' \
  -F file=@./samples/curriculum.pdf

# 2) سؤال يعتمد على محتوى الـ PDF فقط
curl -s -X POST http://127.0.0.1:8000/rag/query \
  -H "X-API-Key: $RAG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "school",
    "question": "(سؤال موجود جوابه في الـ PDF)",
    "metadata_filters": {"grade":"10","subject":"biology"}
  }'
```
- [ ] الرفع يعيد `document.id` و `chunk_count > 0`
- [ ] الإجابة صحيحة ومبنية على الـ PDF
- [ ] `sources` تشير للملف الصحيح
- [ ] سؤال خارج المحتوى يعطي «لا أعرف» / لا يخترع

أو شغّل السكربت:
```bash
./scripts/e2e_school_curriculum.sh /path/to/curriculum.pdf "سؤالك هنا"
```

### ج. قاعدة التوقف
إذا فشلت أي خطوة أعلاه: **قف**، سجّل الخطأ، ولا تربط ClinicFlow/GasFlow بعد.

---

## 3) ملاحظات أمان لهذه المرحلة

| السر | أين يعيش | من يستخدمه |
|---|---|---|
| Provider API keys | `.env` على السيرفر فقط (chmod 600) | LiteLLM فقط |
| `LITELLM_MASTER_KEY` | `.env` | أنت للإدارة / bootstrap |
| Virtual Keys | `bootstrap-keys.json` محليًا (gitignored) ثم توزَّع لكل مشروع | تطبيقات العملاء |
| `RAG_SERVICE_API_KEY` | `.env` | أي عميل يستدعي `/rag` أو `/prompts` عبر header `X-API-Key` |
| `RAG_SERVICE_VIRTUAL_KEY` | `.env` | خدمة RAG داخليًا للحديث مع LiteLLM |

`/health` عام عمدًا للـ healthchecks.  
`/rag/*` و `/prompts/*` محميان بـ `X-API-Key`.
