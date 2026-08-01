<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Celery في OrionIntel — الخريطة الكاملة</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 830px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    font-size: 16px;
  }
  h1 { font-size: 24px; color: #f2c94c; border-bottom: 2px solid #444; padding-bottom: 10px; }
  h2 { font-size: 20px; color: #6fcf97; margin-top: 2.2rem; }
  h3 { font-size: 17px; color: #56ccf2; margin-top: 1.5rem; }
  p { margin: 0.8rem 0; text-align: right; }
  .note {
    background: #262626;
    border-right: 4px solid #f2c94c;
    padding: 0.8rem 1rem;
    margin: 1rem 0;
    border-radius: 6px;
  }
  .warn {
    background: #2b1f1f;
    border-right: 4px solid #eb5757;
    padding: 0.8rem 1rem;
    margin: 1rem 0;
    border-radius: 6px;
  }
  code {
    direction: ltr;
    unicode-bidi: isolate;
    background: #2d2d2d;
    padding: 2px 6px;
    border-radius: 4px;
    color: #f2994a;
    font-family: 'Consolas', monospace;
  }
  pre {
    direction: ltr;
    text-align: left;
    background: #111;
    color: #d4d4d4;
    padding: 1rem;
    border-radius: 8px;
    overflow-x: auto;
    margin: 1rem 0;
    font-size: 13px;
    border: 1px solid #333;
    font-family: 'Consolas', monospace;
    line-height: 1.5;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    background: #222;
  }
  th, td {
    border: 1px solid #444;
    padding: 8px 12px;
    text-align: right;
    font-size: 14px;
  }
  th { background: #2d2d2d; color: #6fcf97; }
  ul, ol { padding-right: 1.5rem; margin: 0.8rem 0; }
  li { margin: 0.4rem 0; }
  .en { direction: ltr; unicode-bidi: isolate; color: #9b9b9b; font-size: 14px; }
</style>
</head>
<body>

<h1>Celery في OrionIntel — الخريطة الكاملة</h1>

<p>
ده الملف اللي بيربط الدروس التمنية اللي اتكلمنا عنها كلها مع بعض. مش درس جديد بقدر ما هو خريطة (map) توضح ليه كل حاجة اتعملت، وترجع بيك للدرس المناسب لو محتاج تفاصيل.
</p>

<h2>1. الفكرة الأساسية في جملة واحدة</h2>
<p>
<code>POST /api/v1/data/process/{project_id}</code> بقى مابيقسمش الملفات جوه الـ HTTP request نفسه — بيسلّم الشغلانة لـ <b>Celery worker</b> ويرجّع <code>task_id</code> فوراً.
</p>

<h2>2. ترتيب القراءة — جزءين</h2>
<h3>الجزء الأول: الكيو نفسها (tut-016)</h3>
<table>
<tr><th>#</th><th>الدرس</th><th>بيغطي إيه</th></tr>
<tr><td>1</td><td>الأساسيات</td><td>Celery إيه، الفرق بين broker وresult backend، الكيوهات، دورة حياة التاسك، كل مفتاح إعدادات اتحط</td></tr>
<tr><td>2</td><td>تكامل FastAPI</td><td>إزاي الـ API والوركر بيشاركوا نفس كود OrionIntel، سطر سطر</td></tr>
<tr><td>3</td><td>RabbitMQ وRedis في Docker</td><td>سيرفيسات الـ compose وكل باراميتر env/config</td></tr>
<tr><td>4</td><td>التشغيل والتحقق</td><td>البناء، التشغيل، وإثبات إن كل حاجة شغالة من طرف لطرف</td></tr>
</table>

<h3>الجزء التاني: الموثوقية والـ workflows والعمليات (tut-017)</h3>
<table>
<tr><th>#</th><th>الدرس</th><th>بيغطي إيه</th></tr>
<tr><td>5</td><td>الـ Idempotency</td><td>جدول celery_task_executions، تجزئة الآرجيومنتس (hashing)، وامتى التكرار بيتجاهل</td></tr>
<tr><td>6</td><td>الـ Workflows والسلاسل</td><td>الفهرسة بتنتقل للكيو؛ ربط chunk ← index بـ chain()</td></tr>
<tr><td>7</td><td>Celery Beat</td><td>التنظيف الدوري، ورقمين الاحتفاظ (retention)</td></tr>
<tr><td>8</td><td>Flower</td><td>لوحة المتابعة، التوثيق، وFlower ضد واجهة RabbitMQ</td></tr>
</table>

<h2>3. ليه اتعمل التغيير ده أصلاً</h2>
<p>
قبل كده، نداء <code>/process</code> لملف PDF كبير كان بيحجز اتصال الـ HTTP طول مدة المعالجة كلها: قراءة الملف ← تقسيمه لـ chunks ← إدخال جماعي (bulk-insert) في Postgres. مع 4 uvicorn workers، أربع معالجات متزامنة كانت بتقفل الـ API كله.
</p>
<p>
دلوقتي، الريكوست بس بينشر رسالة. المعالجة بتحصل في بروسيس منفصل قابل للتوسيع (<code>docker compose up -d --scale celery_worker=3</code>) من غير ما تلمس الـ API خالص.
</p>

<h2>4. الخريطة المعمارية الكاملة</h2>
<pre>
                         PUBLISH                        CONSUME
 client ──▶ FastAPI ───────────────▶ RabbitMQ ────────────────▶ celery worker
              │                     (the broker)                     │
              │  202 + task_id      queues:                          │ writes
              │                       file_processing                ▼
              ▼                       data_indexing        Postgres/pgvector
           client                     default              + assets volume
                                          ▲                          │
                          publishes       │                          │ task state
                     celery beat ─────────┘                          ▼
                      (a clock)                       Redis (result backend)
                                                                     ▲
                                                    flower :5555 ────┘
                                                   (read-only dashboard)
</pre>
<p>
كل صندوق في الرسمة دي شرحناه في درس منفصل: RabbitMQ والكيوهات (1، 3)، الوركر ونقله للكود المشترك (2)، Postgres كسجل idempotency (5)، السلسلة اللي بتوصل لـ Postgres/pgvector عن طريق chain (6)، celery beat اللي بينشر تنظيف دوري (7)، Redis كـ result backend (1)، وFlower كواجهة مراقبة فوق الكل (8).
</p>

<h2>5. سطح الـ API بعد الدرسين مع بعض</h2>
<table>
<tr><th>Endpoint</th><th>السلوك</th></tr>
<tr><td>POST /data/upload/{project_id}</td><td>زي ما هو — متزامن (synchronous)</td></tr>
<tr><td>POST /data/process/{project_id}</td><td>202 + task_id — التقسيم على الكيو</td></tr>
<tr><td>GET /data/process/status/{task_id}</td><td>حالة التاسك / النتيجة / الخطأ</td></tr>
<tr><td>POST /data/process-and-push/{project_id}</td><td>202 + workflow_task_id — تقسيم ثم فهرسة، كسلسلة</td></tr>
<tr><td>POST /nlp/index/push/{project_id}</td><td>202 + task_id — الفهرسة على الكيو</td></tr>
<tr><td>GET /nlp/index/push/status/{task_id}</td><td>حالة الفهرسة، شاملة PROGRESS meta</td></tr>
<tr><td>GET /nlp/index/info/{project_id}</td><td>زي ما هو — متزامن</td></tr>
<tr><td>POST /nlp/index/search/{project_id}</td><td>زي ما هو — متزامن</td></tr>
<tr><td>POST /nlp/index/answer/{project_id}</td><td>زي ما هو — متزامن</td></tr>
</table>

<h2>6. أهم القرارات المتعمدة اللي اتاخدت (مختلفة عن الريبو المرجعي)</h2>
<p>الوثيقة دي فيها ليستة طويلة من الفروق المتعمدة عن الريبو المرجعي. أهمهم اللي فعلاً غيروا سلوك حقيقي:</p>

<h3>من tut-016</h3>
<ul>
<li><b>الفشل بيرمي إكسبشن، مش يكتب FAILURE يدوي</b> — الريبو المرجعي كان بيكسر نفسه لما يحاول يقرا الفشل تاني، ويضيع الخطأ الحقيقي.</li>
<li><b>التاسك بيرجّع نتيجته فعلاً</b> — الريبو المرجعي كان بيتجاهل قيمة <code>asyncio.run(...)</code> فالـ result backend كان بيخزن None.</li>
<li><b>ملفات الـ chunk الفاضية بتتجاهل، مش بتفشل الكل</b> — بدل ما تكسر الحلقة على enumerate لقيمة فاضية.</li>
<li><b>quote_plus على بيانات اعتماد Postgres</b> — لأن الباسورد فيه @ واللي كان هيكسر الـ DSN.</li>
</ul>

<h3>من tut-017</h3>
<ul>
<li><b>ميجريشن واحد، فهرس فريد واحد</b> — الريبو المرجعي عنده ميجريشنين متعارضين بيعملوا IntegrityError على أي طلب مكرر.</li>
<li><b>datetimes واعية بالمنطقة الزمنية (timezone-aware)</b> — الريبو المرجعي كان بيرمي TypeError في مسار إعادة المحاولة تحديداً.</li>
<li><b>Flower بيقرا environment قبل .env</b> — الريبو المرجعي كان بيفشل بـKeyError في Docker.</li>
<li><b>فاصل ومدة احتفاظ الـ Beat كـ env vars بقيم إنتاجية</b> (ساعة / 24 ساعة) بدل 10 ثواني/5 ثواني مكتوبة في الكود — قيم الريبو المرجعي كانت بتخلي سجل الـ idempotency فاضي دايماً، يعني الحماية اللي اتضافت بتتعطل في صمت.</li>
<li><b>باج تقسيم موروث اتصلح</b> — chunk فاضي في الآخر كان بيرفضه الـ embedding API، ده مش جزء من الدمج نفسه لكن ميزة tut-017 مش هتشتغل من غيره.</li>
</ul>

<div class="note">
<b>الخيط المشترك بين كل الفروق دي:</b> الريبو المرجعي غالباً بيوضح الفكرة الأساسية (المفهوم) صح، لكن بيسيب تفاصيل تشغيلية (operational details) — زي التعامل مع الأخطاء، أو التزامن، أو المنطقة الزمنية — اللي مابتظهرش إلا تحت ضغط حقيقي (retry, restart, طلب مكرر). كل الفروق المتعمدة هنا هي بالظبط النوع ده من التفاصيل.
</div>

<h2>7. حاجات لسه مش متعملة (عن قصد)</h2>
<ul>
<li>الـ <code>group()</code>/<code>chord()</code> لتفريع الشغل (fan-out) على تاسكات متوازية</li>
<li>بوابة idempotency على <code>index_data_content</code> — بس <code>process_project_files</code> محمي دلوقتي، زي الريبو المرجعي بالظبط</li>
<li>مقاييس Prometheus للكيو</li>
</ul>

<div class="note">
<b>خلاصة نهائية للسلسلة كلها:</b> بدأنا بمشكلة بسيطة (ريكوست بطيء بيقفل الـ API)، وحليناها بنقل الشغل لبروسيس منفصل. لكن الحل ده فتح أسئلة جديدة — إزاي الوركر يوصل لنفس الموارد، إزاي تتأكد إنه مايكررش الشغل، إزاي تربط خطوات ببعض، إزاي تنضف السجلات القديمة، وإزاي تراقب كل ده. كل درس من الدروس التمنية كان بيحل واحدة من الأسئلة دي، وده بالظبط اللي بيخلي أي نظام background jobs — سواء ده أو أي نظام تاني هتبنيه في hakeem — معقد بالقدر ده: مش لأن الفكرة صعبة، لكن لأن الحواف (edges) كتير.
</div>

</body>
</html>