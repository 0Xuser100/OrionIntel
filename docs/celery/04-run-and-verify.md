<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تشغيل والتحقق — Celery</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 820px;
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

<h1>التشغيل والتحقق (Run &amp; Verify)</h1>

<h2>1. تثبيت الحزم (Dependencies)</h2>
<p>موجودة أصلاً في <code>src/pyproject.toml</code>. عشان تحدّث الـ lock والـ venv:</p>
<pre>
cd src
uv sync
</pre>
<p>لو كنت هتضيفهم من الصفر كانت هتبقى كده:</p>
<pre>
uv add celery redis kombu billiard vine   # tut-016
uv add flower                             # tut-017
</pre>

<h2>2. تشغيل الـ Deploy Stack</h2>
<pre>
# مرة واحدة: اعمل ملفات الـ env
cd docker/env
cp .env.example.rabbitmq .env.rabbitmq
cp .env.example.redis    .env.redis
cd ..
cp .env.example .env          # compose-level, holds REDIS_PASSWORD

# ابني وشغل كل حاجة
docker compose up --build -d
docker compose ps
</pre>
<p>هتلاقي خمس كونتينرات جداد جنب السيرفيسات الموجودة:</p>
<table>
<tr><th>الكونتينر</th><th>الدور</th></tr>
<tr><td><code>orionintel_rabbitmq</code></td><td>البروكر (5672، وواجهة الإدارة 15672)</td></tr>
<tr><td><code>orionintel_redis</code></td><td>الـ result backend (بورت الهوست 6380)</td></tr>
<tr><td><code>orionintel_celery_worker</code></td><td>بيستهلك من file_processing وdata_indexing وdefault</td></tr>
<tr><td><code>orionintel_celery_beat</code></td><td>بينشر عملية التنظيف المجدولة</td></tr>
<tr><td><code>orionintel_flower</code></td><td>لوحة متابعة (dashboard) على 5555</td></tr>
</table>
<p>RabbitMQ محتاج حوالي 20-30 ثانية عشان يبلّغ إنه <code>healthy</code>؛ كل حاجة تانية بتستنى عليه.</p>
<pre>
docker compose logs -f celery_worker
</pre>
<p>الوركر السليم بيطبع لافتة (banner) وبعدين أربع سطور مهمة:</p>
<pre>
 -------------- celery@&lt;id&gt; v5.x
- ** ---------- [config]
- ** ---------- .&gt; app:         orionintel:0x...
- ** ---------- .&gt; transport:   amqp://orionintel_user:**@rabbitmq:5672/orionintel_vhost
- ** ---------- .&gt; results:     redis://:**@redis:6379/0
- *** --- * --- .&gt; concurrency: 2 (prefork)
-- ******* ----
--- ***** ----- [queues]
                .&gt; data_indexing    exchange=data_indexing(direct)    key=data_indexing
                .&gt; default          exchange=default(direct)          key=default
                .&gt; file_processing  exchange=file_processing(direct)  key=file_processing

[tasks]
  . tasks.data_indexing.index_data_content
  . tasks.file_processing.process_project_files
  . tasks.maintenance.clean_celery_executions_table
  . tasks.process_workflow.process_and_push_workflow
  . tasks.process_workflow.push_after_process_task

celery@&lt;id&gt; ready.
</pre>
<div class="note">
تأكد من أربع حاجات: <b>transport</b> و<b>results</b> لازم يكونوا الروابط اللي أنت مظبطها، <b>الكيوهات التلاتة</b> لازم تكون مذكورة، و<b>الخمس تاسكات</b> لازم تظهر تحت <code>[tasks]</code>. تاسك ناقص معناه إن <code>include=</code> في celery_app.py ما اشتغلش. كيو ناقصة معناها إن ليستة <code>-Q</code> في الـ compose ناقصة — التاسكات دي هتتكوم في صمت للأبد.
</div>

<h3>الـ Beat والـ Flower</h3>
<pre>
docker compose logs celery_beat | tail -3
# ==> RUN_MIGRATIONS=0 — skipping migrations (another service owns them).
# ==> Starting application: celery -A celery_app beat --loglevel=INFO --schedule=/app/celerybeat/celerybeat-schedule
# [INFO/MainProcess] beat: Starting...

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5555/     # 401 = auth is on
</pre>
<p>
الـ Flower بيسجل مجموعة تحذيرات <code>Inspect method ... failed</code> وقت ما الوركر لسه بيقوم. بتتوقف لما الوركر يرد.
</p>

<h2>3. اختبار من طرف لطرف (End-to-end)</h2>
<pre>
# 1) ارفع ملف
curl -F "file=@sample.pdf" http://localhost:8000/api/v1/data/upload/1
# {"signal":"file_upload_success","file_id":"7"}

# 2) اعمل enqueue للمعالجة — بيرجع فوراً
curl -X POST http://localhost:8000/api/v1/data/process/1 \
     -H 'Content-Type: application/json' \
     -d '{"chunk_size":512,"overlap_size":50,"do_reset":1}'
# 202 {"signal":"processing_enqueued","task_id":"3fa8...e1"}

# 3) اسأل عن الحالة
curl http://localhost:8000/api/v1/data/process/status/3fa8...e1
# {"task_id":"3fa8...e1","state":"SUCCESS",
#  "result":{"signal":"processing_success","inserted_chunks":128,"processed_files":1}}
</pre>
<p>لوج الوركر لنفس التشغيلة:</p>
<pre>
Task tasks.file_processing.process_project_files[3fa8...e1] received
inserted_chunks: 128 / processed_files: 1
Task tasks.file_processing.process_project_files[3fa8...e1] succeeded in 4.31s
</pre>
<div class="note">
الدليل إن ده فعلاً غير متزامن (asynchronous): الخطوة رقم 2 بترجع في أجزاء من الثانية بغض النظر عن الوقت اللي محتاجه الخطوة 3 عشان توصل لـ SUCCESS.
</div>

<h2>4. الفهرسة (Indexing) على الكيو</h2>
<pre>
curl -X POST http://localhost:8000/api/v1/nlp/index/push/1 \
     -H 'Content-Type: application/json' -d '{"do_reset":1}'
# 202 {"signal":"data_push_task_ready","task_id":"1ccfc540-..."}

curl http://localhost:8000/api/v1/nlp/index/push/status/1ccfc540-...
# {"state":"SUCCESS","result":{"signal":"insert_into_vectordb_success","inserted_items_count":10}}
</pre>
<p>وطول ما شغال، نفس الـ endpoint بيرجع الحالة المخصصة PROGRESS:</p>
<pre>
{"task_id":"1ccfc540-...","state":"PROGRESS","meta":{"indexed":40,"total":128}}
</pre>
<p>وبعدين تأكد إن الـ vectors فعلاً قابلة للاستخدام:</p>
<pre>
curl -X POST http://localhost:8000/api/v1/nlp/index/search/1 \
     -H 'Content-Type: application/json' -d '{"text":"something from your file","limit":2}'
# {"signal":"vectordb_search_success","results":[{"text":"...","score":...}]}
</pre>

<h2>5. الـ Workflow المتسلسل (Chain)</h2>
<p>تقسيم (chunk) وفهرسة (index) في نداء واحد. فاكر إن فيه id-ين مختلفين:</p>
<pre>
# 1. الإطلاق (launch) — بيرجع id بتاع اللانشر
curl -X POST http://localhost:8000/api/v1/data/process-and-push/12 \
     -H 'Content-Type: application/json' \
     -d '{"chunk_size":300,"overlap_size":20,"do_reset":1}'
# 202 {"signal":"process_and_push_workflow_ready","workflow_task_id":"2b03befd-..."}

# 2. نتيجة اللانشر بتشيل id بتاع السلسلة (chain)
curl http://localhost:8000/api/v1/data/process/status/2b03befd-...
# {"state":"SUCCESS","result":{"signal":"WORKFLOW_STARTED","workflow_id":"4db5a398-...",...}}

# 3. الـ id ده هو اللي بيدي الإجابة النهائية
curl http://localhost:8000/api/v1/data/process/status/4db5a398-...
# {"state":"SUCCESS","result":{"project_id":12,"do_reset":1,
#   "task_results":{"signal":"insert_into_vectordb_success","inserted_items_count":10}}}
</pre>
<div class="warn">
وصول اللانشر لـ SUCCESS معناها بس "السلسلة اتبعتت". لازم دايماً تتبع بعدين workflow_id عشان تعرف النتيجة الفعلية.
</div>

<h2>6. سجل الـ Idempotency</h2>
<pre>
docker compose exec pgvector psql -U &lt;user&gt; -d &lt;db&gt; -c \
  "select execution_id, right(task_name,20) as task, status,
          result->>'inserted_chunks' as chunks
   from celery_task_executions order by execution_id;"
</pre>
<pre>
 execution_id |         task         | status  | chunks
--------------+----------------------+---------+--------
            4 | rocess_project_files | SUCCESS | 10
</pre>
<p>
لازم يكون فيه فهرس فريد (unique index) واحد بالظبط (زائد الـ primary key) — لو شفت unique index على <code>(task_name, task_args_hash)</code> بس، يبقى عندك باج الفهرسة المزدوجة الموروثة من الريبو المرجعي:
</p>
<pre>
docker compose exec pgvector psql -U &lt;user&gt; -d &lt;db&gt; -c \
  "select indexname, indexdef like '%UNIQUE%' as is_unique
   from pg_indexes where tablename='celery_task_executions' order by indexname;"
</pre>

<h2>7. الـ Celery Beat</h2>
<p>الفاصل الافتراضي 3600 ثانية، فمتقعدش تستنى. شغل beat مؤقت بفاصل 10 ثواني بدلاً منه — الوركر الشغال هيعمل execute لأي حاجة بيبعتها:</p>
<pre>
docker compose exec -e CELERY_BEAT_CLEANUP_INTERVAL=10 celery_beat \
  celery -A celery_app beat --loglevel=INFO --schedule=/tmp/beat-demo
# [INFO/MainProcess] beat: Starting...
# [INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (...)
# ... every 10s. Ctrl-C to stop.
</pre>
<p>وفي ترمينال تاني، جانب الوركر:</p>
<pre>
docker compose logs -f celery_worker | grep cleanup
# cleanup: deleted 0 task record(s) older than 86400s
</pre>
<p>
<code>deleted 0</code> صح مع فترة الاحتفاظ الافتراضية 24 ساعة. عشان تشوف صفوف فعلاً بتتمسح، حط <code>CELERY_TASK_RECORD_RETENTION=30</code> في .env.app، أعد تشغيل celery_worker، وجرب تاني — وبعدين رجعها زي ما كانت.
</p>

<h2>8. فحص البروكر</h2>
<p>
<code>http://localhost:15672</code> — يوزر <code>orionintel_user</code>، باسورد <code>orionintel_rabbitmq_2222</code>.
</p>
<p>
غيّر الـ vhost selector لـ <code>orionintel_vhost</code>، وبعدين Queues: المفروض تشوف <code>file_processing</code> و<code>default</code>. راقب الرقم اللي بيقفز في Ready لـ 1 وبعدين يرجع 0 وقت ما التاسك بيتستهلك. رقم عالق في Ready معناه إن مفيش حد بيستهلك من الكيو دي.
</p>
<pre>
docker compose exec rabbitmq rabbitmqctl list_queues -p orionintel_vhost name messages consumers
docker compose exec redis redis-cli -a orionintel_redis_2222 keys 'celery-task-meta-*'
</pre>
<p>فحص Celery الذاتي (introspection):</p>
<pre>
docker compose exec celery_worker celery -A celery_app inspect ping
docker compose exec celery_worker celery -A celery_app inspect active        # running now
docker compose exec celery_worker celery -A celery_app inspect registered    # known tasks
</pre>

<h3>الفحص عن طريق Flower</h3>
<p><code>http://localhost:5555</code> — يوزر <code>admin</code>، باسورد <code>CELERY_FLOWER_PASSWORD</code>.</p>
<pre>
curl -s -u admin:orionintel_flower_2222 "http://localhost:5555/api/workers?refresh=1"
# {"celery@&lt;id&gt;": {"active_queues": [{"name":"file_processing"},
#                                    {"name":"data_indexing"},
#                                    {"name":"default"}], ...}}
</pre>
<p>استخدم تاب Broker عشان تشوف أي كيو متكدسة، وتاب Tasks مفلتر على FAILURE عشان تقرا الـ tracebacks من غير ما تعمل grep في اللوجات.</p>

<h2>9. توسيع الوركر (Scale)</h2>
<pre>
docker compose up -d --scale celery_worker=3
</pre>
<p>
تلات مستهلكين (consumers) على نفس الكيوهات؛ RabbitMQ بيوزعهم round-robin. من غير أي تغيير في الكود أو الإعدادات — ده بالظبط ثمرة نقل الشغل بره الريكوست.
</p>
<div class="warn">
شيل <code>container_name</code> من السيرفيس لو هتعمل scale، لأن اسم ثابت مايقدرش ينطبق على تلات كونتينرات.
<br><br>
<b>أبداً متعملش scale لـ celery_beat.</b> مفيهاش قفل (lock) ولا leader election، فلو شغلت اتنين هينشروا كل تيك مجدول مرتين.
</div>
<p>عشان تقسم الكيوهات على وركرز مخصصة بدل وركر واحد بيستهلك من التلاتة:</p>
<pre>
command: ["celery", "-A", "celery_app", "worker", "-Q", "file_processing", "--concurrency=4"]
command: ["celery", "-A", "celery_app", "worker", "-Q", "data_indexing,default", "--concurrency=2"]
</pre>
<p>
بين الاتنين، ليستات الـ -Q لازم تغطي <b>كل</b> الكيوهات، بما فيها default — لأن الحلقة التانية في السلسلة (chain) بتكون unrouted وبتنزل هناك.
</p>

<h2>10. التشغيل من غير Docker</h2>
<p>تلات ترمينالات من جوه <code>src/</code>:</p>
<pre>
# عدّل src/.env الأول: rabbitmq -> localhost, redis -> localhost, pgvector -> localhost
# (redis منشور على بورت الهوست 6380، فاستخدم localhost:6380)
docker compose -f ../docker/docker-compose.yml up -d rabbitmq redis pgvector
uv run uvicorn main:app --reload
uv run celery -A celery_app worker --loglevel=INFO -Q file_processing,data_indexing,default
</pre>
<p>الـ Beat والـ Flower محلياً، لو عايزهم:</p>
<pre>
uv run celery -A celery_app beat --loglevel=INFO
uv run celery -A celery_app flower --conf=flowerconfig.py
</pre>
<div class="note">
على Windows الـ prefork pool مش شغالة (مفيش fork). استخدم:
</div>
<pre>
uv run celery -A celery_app worker --loglevel=INFO -Q file_processing,default --pool=solo
</pre>
<p>
<code>--pool=solo</code> بيشغل تاسك واحد بس في المرة في البروسيس الأساسي — كويس للتطوير، أبداً للإنتاج (production).
</p>

<h2>11. حل المشاكل (Troubleshooting)</h2>
<table>
<tr><th>العرض</th><th>الحل</th></tr>
<tr><td>Received unregistered task of type ...</td><td>ناقص من include=، أو إيمج الوركر قديم — <code>docker compose up -d --build celery_worker</code></td></tr>
<tr><td>Cannot connect to amqp://...:5672</td><td>عدم تطابق بيانات الدخول/vhost بين .env.rabbitmq وCELERY_BROKER_URL. لو عدّلت RABBITMQ_DEFAULT_* بعد أول إقلاع، التعديل ما بيتطبقش خالص.</td></tr>
<tr><td>NOAUTH Authentication required من Redis</td><td>REDIS_PASSWORD ناقص من docker/.env، فcompose وسّع --requirepass لنص فاضي.</td></tr>
<tr><td>endpoint الحالة دايماً PENDING</td><td>مفيش حد بيستهلك من الكيو دي، أو الـ API والوركر عندهم روابط بروكر مختلفة، أو الـ id أصلاً مش موجود.</td></tr>
<tr><td>Error while processing file في الوركر</td><td>فوليوم الرفع مش مشترك — celery_worker لازم يعمل mount لـ fastapi_data:/app/assets.</td></tr>
<tr><td>الكونتينرين بيسجلوا أخطاء alembic وقت up</td><td>RUN_MIGRATIONS=0 ناقص من celery_worker.</td></tr>
<tr><td>التاسك بيعيد المحاولة 3 مرات على خطأ واضح إنه دائم</td><td>متوقع: autoretry_for=(Exception,). ضيّقها لو عايز فشل سريع.</td></tr>
<tr><td>الوركر بيتقتل عند الثانية 600 بالظبط</td><td>task_time_limit — ارفع CELERY_TASK_TIME_LIMIT.</td></tr>
<tr><td>kombu.exceptions.EncodeError</td><td>حاجة مش JSON اتبعتت لـ .delay() أو meta=. ابعت ids وأنواع بسيطة بس.</td></tr>
<tr><td>السلسلة بتوقف بعد الحلقة الأولى من غير خطأ</td><td>الوركر مش بيستهلك من default — push_after_process_task بقت unrouted.</td></tr>
<tr><td>workflow_task_id بقى SUCCESS بس مفيش حاجة اتفهرست</td><td>سألت عن اللانشر مش السلسلة. تابع workflow_id.</td></tr>
<tr><td>IntegrityError على celery_task_executions</td><td>فهرسين فريدين — باج الميجريشن المزدوج الموروث.</td></tr>
<tr><td>TypeError: can't subtract offset-naive and offset-aware datetimes</td><td>datetime.utcnow() بدون timezone وصل لفحص الـ idempotency.</td></tr>
<tr><td>Flower container بيقفل بـ KeyError: 'CELERY_FLOWER_PASSWORD'</td><td>إعدادات Flower بتقرا من .env بس، ومش موجود في الإيمج.</td></tr>
<tr><td>PermissionError وقت الكتابة في /app/celerybeat/...</td><td>فوليوم الـ beat مملوك لـ root؛ نقطة الـ mount لازم تكون موجودة في الإيمج.</td></tr>
<tr><td>Beat بيعيد إطلاق كل حاجة بعد ريستارت</td><td>ملف الجدولة مش persisted — تأكد من --schedule والفوليوم.</td></tr>
<tr><td>Invalid 'input[n]': input cannot be an empty string من الـ embedding API</td><td>chunk فاضي وصل للـ embedder.</td></tr>
</table>

<h2>12. الهدم (Tear Down)</h2>
<pre>
cd docker
docker compose down             # يحافظ على الداتا
docker compose down -v          # يمسح الفوليومز كمان: الرسايل المتكدسة، النتايج، الداتابيز
</pre>
<div class="warn">
<code>down -v</code> هي الطريقة الوحيدة عشان تغير RABBITMQ_DEFAULT_USER/PASS/VHOST بعد أول إقلاع. وبتمسح كمان celery_beat_data (ذاكرة آخر تنفيذ بتاعة beat) والداتابيز، بما فيها celery_task_executions.
</div>

<div class="note">
<b>خلاصة سريعة:</b> الدرس ده عملي بالكامل — إزاي تتأكد إن السيستم شغال صح (من خلال لوج الوركر واللي لازم يظهر فيه)، إزاي تعمل اختبار من طرف لطرف، وإزاي تفرق بين نتيجة اللانشر ونتيجة السلسلة الحقيقية في الـ workflows. جدول الأعطال في الآخر أساساً خريطة سريعة لأي مشكلة هتقابلك، وأغلبها بيرجع لحاجة من الدروس اللي فاتت: كيو ناقصة من -Q، فوليوم مش مشترك، أو باسورد اتغير بعد أول إقلاع.
</div>

</body>
</html>