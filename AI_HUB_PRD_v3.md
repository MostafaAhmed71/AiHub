# PRD – AI Hub v3.0

## بنية تحتية داخلية خاصة، مبنية فوق LiteLLM

> **التغيير الجوهري عن v2.0**: بدل بناء Gateway كامل من الصفر (NestJS + Prisma + Key Manager + Rotation Engine مخصص)، نستخدم **LiteLLM** (مفتوح المصدر، https://github.com/BerriAI/litellm) كنواة جاهزة تغطي 70-80% من احتياجات الـ Gateway، ونبني فوقه فقط الأجزاء اللي مش موجودة: **RAG Layer + Prompt Library**، مخصصة لمشاريعك.

---

## 1. نظرة عامة

AI Hub هو بنية تحتية داخلية (Internal Platform) تخدم مشاريع المطور المتعددة (School Platform, ClinicFlow, GasFlow, CRM, ERP, Chatbots...). كل مشروع يتصل بنقطة واحدة بدل التعامل المباشر مع مزودي الذكاء الاصطناعي.

**المشروع مكوّن من طبقتين:**
1. **الطبقة الأساسية (Core)**: LiteLLM — جاهز، مفتوح المصدر، self-hosted.
2. **الطبقة المخصصة (Custom Layer)**: RAG Service + Prompt Library — تُبنى من الصفر لأنها مش موجودة في LiteLLM.

---

## 2. الأهداف

- توحيد اتصالات الذكاء الاصطناعي لكل المشاريع عبر نقطة واحدة.
- عدم تخزين API Keys داخل أي مشروع فردي.
- تبديل تلقائي بين المفاتيح/المزودين عند الفشل (fallback).
- مراقبة الاستهلاك والتكلفة لكل مشروع.
- دعم RAG موحّد لأي مشروع محتاج "إجابة من مستندات محددة" (زي بوت المنهج).
- تقليل وقت التطوير عبر استخدام أداة جاهزة بدل إعادة اختراعها.

---

## 3. الطبقة الأساسية: LiteLLM (Core Gateway)

### لماذا LiteLLM ولا بناء من الصفر
- Rust core + Python SDK، مفتوح المصدر بالكامل (MIT)، self-hosted بالكامل — لا بيانات بتطلع بره سيرفرك.
- يغطي جاهزاً: Unified API (chat/embeddings/vision/image/speech)، Virtual Keys مع budgets وrate limits، Load Balancing + Automatic Fallback، Admin UI، Logging، Cost Tracking، Teams/RBAC، Redis Cache، Health Checks.

### الإعداد المطلوب
- تنصيب عبر Docker Compose على نفس السيرفر (أو VPS منفصل صغير).
- قاعدة بيانات PostgreSQL (وليس SQLite — ضروري لتفادي race conditions في الـ budgets تحت الحمل المتزامن).
- إنشاء **Master Key** للإدارة.
- إنشاء **Team واحد لكل مشروع** (School, ClinicFlow, GasFlow...) مع budget شهري/يومي مستقل لكل Team.
- إنشاء **Virtual Key لكل مشروع** مربوطة بالـ Team بتاعه، مع:
  - `allowed_models` (تحديد الموديلات المسموحة لكل مشروع)
  - `max_budget` + `budget_duration`
  - `rpm_limit` / `tpm_limit`
- ربط المزودين (Gemini, OpenAI, DeepSeek, Groq, إلخ) عبر `config.yaml` بمفاتيح API الحقيقية — المشاريع الفردية متعرفش المفاتيح دي خالص، بس بتستخدم الـ Virtual Key بتاعها.

### ما لا يُعاد بناؤه (موجود جاهز في LiteLLM)
- Key rotation / cooldown / fallback logic.
- Admin Dashboard الأساسي (مشاريع، مفاتيح، طلبات، تكلفة).
- Logging تفصيلي لكل request (project, provider, model, tokens, latency, cost).
- Prometheus metrics (لو احتجت مراقبة متقدمة لاحقًا).

---

## 4. الطبقة المخصصة: ما يُبنى فوق LiteLLM

هذه الأجزاء **غير موجودة** في LiteLLM ولازم تُبنى كخدمة منفصلة (RAG Service) بتتصل بـ LiteLLM كـ backend للـ LLM/Embeddings:

### 4.1 RAG Service
- **الوظيفة**: يستقبل ملفات (PDF/DOCX/TXT/CSV) من أي مشروع، يقسّمها (chunking)، يولّد embeddings (عبر استدعاء LiteLLM بدل استدعاء المزود مباشرة — كده حتى الـ RAG بياخد فوائد الـ rotation/fallback)، يخزّنها في Vector DB.
- **Vector DB**: `pgvector` داخل نفس Postgres (أو قاعدة منفصلة لو الحمل كبير).
- **البحث**: عند سؤال، الخدمة تعمل similarity search **بعد فلترة metadata إجبارية** (مثلاً project_id, stage, grade — حسب سياق كل مشروع)، ثم تبعت الـ context لـ LiteLLM لتوليد الإجابة.
- **مثال استخدام فعلي**: بوت المنهج الدراسي (مشروع منفصل قائم بالفعل) ممكن يتحول لاحقًا يستخدم هذا الـ RAG Service المركزي بدل نسخة مستقلة.

### 4.2 Prompt Library
- تخزين Prompts جاهزة مصنّفة (School, Medical, ERP, CRM, Marketing).
- كل مشروع يقدر يسحب prompt جاهز بدل ما يكتبه من الصفر كل مرة.
- جدول بسيط: `id, category, title, content, variables (JSON), project_id (nullable لو عام)`.

### 4.3 لا شيء غير ذلك في Phase 1
- أي ميزة تانية مذكورة في PRD القديم (Vision, OCR, Speech, Agents, Workflow Builder) هتُستخدم **مباشرة عبر LiteLLM** بدون طبقة إضافية، لأنها endpoints بيدعمها LiteLLM نفسه لو المزود بيدعمها.

---

## 5. المعمارية العامة

```
[School Platform]  [ClinicFlow]  [GasFlow]  [CRM]  ...
        |               |            |         |
        └───────────────┴────────────┴─────────┘
                         |
                         v
              [LiteLLM Proxy (Docker)]
              - Virtual Keys per project
              - Fallback/Rotation
              - Cost tracking + Admin UI
                         |
              ┌──────────┴──────────┐
              v                     v
     [AI Providers مباشرة]   [RAG Service (مبني من الصفر)]
     (Gemini, OpenAI,              |
      DeepSeek...)          [Postgres + pgvector]
                             (مستندات كل مشروع، مفلترة بـ project_id)
```

---

## 6. قاعدة البيانات

**جداول LiteLLM**: يديرها LiteLLM نفسه تلقائياً (لا تُنشأ يدويًا) — teams, keys, spend logs, budgets.

**جداول مخصصة (لطبقتنا فوق LiteLLM):**

### `rag_documents`
| العمود | النوع |
|---|---|
| id | uuid |
| project_id | text (يطابق اسم الـ Team في LiteLLM) |
| filename | text |
| uploaded_at | timestamp |
| metadata | jsonb (مرن حسب نوع المشروع: stage/grade للمدرسة، department للعيادة...) |

### `rag_chunks`
| العمود | النوع |
|---|---|
| id | uuid |
| document_id | uuid (FK) |
| content | text |
| embedding | vector(N) |
| metadata | jsonb |

### `prompts`
| العمود | النوع |
|---|---|
| id | uuid |
| category | text |
| title | text |
| content | text |
| variables | jsonb |
| project_id | text (nullable) |

---

## 7. الأمان

- كل مشروع بياخد **Virtual Key من LiteLLM بس** — لا يشوف أي API Key حقيقي لأي مزود.
- الـ RAG Service نفسه بيتعامل مع LiteLLM عبر Virtual Key مخصص له (Team باسم `rag-service`).
- كل الاتصالات HTTPS.
- الـ Master Key بتاع LiteLLM يُخزَّن في Secrets Manager (مش في كود ولا env عادي بدون تشفير).

---

## 8. مراحل التنفيذ (Roadmap)

### Phase 1 — Core Gateway (LiteLLM)
- تنصيب LiteLLM عبر Docker Compose (مع Postgres مخصص للـ Gateway).
- إنشاء Team + Virtual Key لكل مشروع حالي (School, ClinicFlow, GasFlow).
- ربط مزودين على الأقل (Gemini + مزود بديل للـ fallback).
- اختبار: كل مشروع يقدر يستدعي `/chat/completions` عبر الـ Virtual Key بتاعه بنجاح، ويظهر الاستخدام في Admin UI.

### Phase 2 — RAG Service (المخصص)
- بناء endpoint لرفع مستند → chunking → embedding (عبر LiteLLM) → تخزين في `pgvector`.
- بناء endpoint للسؤال → فلترة metadata → بحث → توليد إجابة (عبر LiteLLM).
- اختبار على مشروع واحد فقط أولاً (مثلاً بوت المنهج) قبل التوسع لباقي المشاريع.

### Phase 3 — Prompt Library + تحسينات
- جدول الـ prompts + واجهة بسيطة لإدارتها.
- ربط أي مشروع جديد بالـ Hub خلال دقائق (Team + Key جديدة بس، مفيش كود إضافي).

---

## 9. معايير النجاح

- كل مشروع حالي ومستقبلي يتصل بنقطة واحدة (LiteLLM) بدون أي API Key مباشر بداخله.
- Fallback تلقائي بين المزودين عند الفشل، بدون توقف خدمة.
- مراقبة تكلفة دقيقة لكل مشروع من نفس الـ Admin UI.
- إضافة مشروع جديد = Team + Key جديدة، بدون كتابة كود إضافي في الـ Gateway نفسه.
- الوقت المستثمر في التطوير يتركّز فقط على RAG + Prompt Library (القيمة المضافة الحقيقية)، مش على إعادة بناء Gateway موجود أصلاً.

---

## 10. ملاحظات وتنبيهات

- **لا تبني أي جزء من منطق الـ Key Rotation/Fallback بنفسك** — استخدم إعدادات LiteLLM (`fallbacks`, `cooldown_time` في `config.yaml`).
- **الـ RAG Service مشروع منفصل حقيقي**، مش "قسم صغير" — يحتاج نفس عناية بوت المنهج (مراجعة جودة الـ chunking، فلترة metadata إجبارية قبل البحث، منع الـ hallucination بتعليمات صارمة في الـ prompt).
- قبل ما توسّع لمشاريع كتير، جرّب المسار الكامل (Gateway + RAG) على مشروع واحد بس (بوت المنهج مثال جيد) للتأكد من الاستقرار.
