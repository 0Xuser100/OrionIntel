<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>الـ Idempotency وجدول سجلات التاسكات</title>
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

<h1>الـ Idempotency وجدول سجلات التاسكات</h1>
<p class="en" style="text-align:right; direction:rtl;">
سابقة مطلوبة: الدرس الأول (Celery basics)، خصوصاً جزء <code class="en">task_acks_late</code>.
</p>

<h2>1. ليه الموضوع ده أصلاً موجود</h2>
<p>
فيه إعدادين من الدروس اللي فاتت معناهم إن التاسك ممكن فعلاً يشتغل <b>أكتر من مرة</b>:
</p>
<table>
<tr><th>الإعداد</th><th>فين</th><th>النتيجة</th></tr>
<tr><td><code>task_acks_late=True</code></td><td>celery_app.py</td><td>الوركر بيموت في نص التاسك ← مفيش ack ← RabbitMQ بيعيد توصيل الرسالة</td></tr>
<tr><td><code>autoretry_for=(Exception,)</code></td><td>file_processing.py</td><td>نفس id التاسك بيشتغل لحد 4 مرات</td></tr>
</table>
<p>
ولا واحد فيهم باج — دول بالظبط اللي بيخلوا الكيو موثوق (reliable). لكن إعادة تقسيم (re-chunking) مشروع خلص أصلاً بتضيع دقايق من نداءات الـ embedding وبتكرر صفوف. Celery بيدّيك ضمان "at-least-once delivery"، لكن خليك التاسك <b>idempotent</b> (يعني تنفيذه أكتر من مرة بنفس النتيجة) ده شغلانتك إنت.
</p>
<div class="note">
الـ result backend بتاع Celery نفسه مايقدرش يساعد هنا: Redis بيحتفظ بالنتايج لمدة <code>result_expires</code> (ساعة واحدة) وأي ريستارت ممكن يضيع الحالة الشغالة. عشان كده بنضيف <b>سجل دائم (durable ledger) في Postgres</b>.
</div>

<h2>2. الجدول — <span class="en">celery_task_execution.py</span></h2>
<pre>
class CeleryTaskExecution(SQLAlchemyBase):
    __tablename__ = "celery_task_executions"

    execution_id   = Column(Integer, primary_key=True, autoincrement=True)
    task_name      = Column(String(255), nullable=False)
    task_args_hash = Column(String(64),  nullable=False)   # SHA-256
    celery_task_id = Column(UUID(as_uuid=True), nullable=True)
    status         = Column(String(20), nullable=False, default="PENDING")
    task_args      = Column(JSONB, nullable=True)
    result         = Column(JSONB, nullable=True)
    started_at / completed_at / created_at / updated_at
</pre>
<table>
<tr><th>العمود</th><th>ليه موجود</th></tr>
<tr><td><code>task_name</code></td><td>نفس الآرجيومنتس ممكن تعني شغل مختلف تماماً لتاسك مختلف</td></tr>
<tr><td><code>task_args_hash</code></td><td>بصمة "نفس الشغل بالظبط" — SHA-256 hex بطول 64 حرف، فرخيص إنك تعمله index مهما كانت الآرجيومنتس كبيرة</td></tr>
<tr><td><code>celery_task_id</code></td><td>بيربط الصف برسالة Celery؛ nullable لأن الصف ممكن يعيش أطول من الـ id بتاعه</td></tr>
<tr><td><code>status</code></td><td>PENDING → STARTED → SUCCESS/FAILURE. متعمد إنه يشابه مصطلحات Celery، لكن ده عمودنا إحنا، مش حالة Celery نفسها</td></tr>
<tr><td><code>task_args</code> (JSONB)</td><td>النسخة المقروءة من اللي الهاش بيغطيه — للـ debugging</td></tr>
<tr><td><code>result</code> (JSONB)</td><td>بتخلي أي تكرار متجاهَل (skipped duplicate) يرجع الإجابة الأصلية بدل None</td></tr>
<tr><td><code>started_at</code></td><td>محتاجينه عشان نقرر هل تاسك شغال دلوقتي فعلاً عالق (stuck)</td></tr>
</table>

<h3>الفهارس (Indexes)، وباج اتحاشيناه</h3>
<p>الموديل بيعرّف أربع فهارس، واحد بس فيهم فريد (unique):</p>
<pre>
Index("ixz_task_name_args_celery_hash",
      task_name, task_args_hash, celery_task_id, unique=True)
Index("ixz_task_execution_status", status)
Index("ixz_task_execution_created_at", created_at)   # used by the cleanup sweep
Index("ixz_celery_task_id", celery_task_id)
</pre>
<div class="warn">
<b>الريبو المرجعي فيه ميجريشنين وبيتعارضوا مع بعض.</b> الأول بيعمل فهرس فريد على <code>(task_name, task_args_hash)</code> بس. التاني بيضيف الفهرس التلاتي (three-column) <b>من غير ما يشيل الأول</b>. النتيجة إن الاتنين بيبقوا موجودين، فالفهرس الثنائي بيرفض أي طلب تاني بنفس الآرجيومنتس — معالجة نفس المشروع مرتين بترمي <code>IntegrityError</code>، واللي بعدين <code>autoretry_for=(Exception,)</code> بيعيد محاولتها 3 مرات قبل ما تفشل. الميجريشن الواحد عندنا بيعمل بس الفهرس التلاتي، متطابق مع الموديل.
</div>
<pre>
           indexname            | is_unique
--------------------------------+-----------
 celery_task_executions_pkey    | t
 ixz_celery_task_id             | f
 ixz_task_execution_created_at  | f
 ixz_task_execution_status      | f
 ixz_task_name_args_celery_hash | t
</pre>
<p>
و<code>alembic revision --autogenerate</code> ضد الداتابيز الشغالة دي بيطلع <b>مفيش</b> تغييرات لجدول ده — الميجريشن والموديل متفقين تماماً.
</p>

<h2>3. البصمة (Fingerprint) — <span class="en">idempotency_manager.py</span></h2>
<pre>
def create_args_hash(self, task_name: str, task_args: dict) -> str:
    combined_data = {**task_args, "task_name": task_name}
    json_string = json.dumps(combined_data, sort_keys=True, default=str)
    return hashlib.sha256(json_string.encode()).hexdigest()
</pre>
<ul>
<li><b>sort_keys=True</b> — من غيرها، <code>{"a":1,"b":2}</code> و<code>{"b":2,"a":1}</code> بيطلعوا هاش مختلف، وشغل متطابق بيبان جديد.</li>
<li><b>default=str</b> — أي قيمة مش JSON غريبة بتتحول لنص بدل ما ترمي إكسبشن.</li>
<li><b>task_name</b> داخل الهاش نفسه، فنفس الآرجيومنتس تحت تاسك مختلف أبداً مش هتتصادم (collide).</li>
</ul>

<h2>4. البوابة (Gate) جوه التاسك</h2>
<pre>
settings = get_settings()
idempotency_manager = IdempotencyManager(db_client, db_engine)

task_args = {"project_id": ..., "file_id": ..., "chunk_size": ...,
             "overlap_size": ..., "do_reset": ...}

should_execute, existing_task = await idempotency_manager.should_execute_task(
    task_name=TASK_NAME,
    task_args=task_args,
    celery_task_id=task_instance.request.id,     # line 110
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
)

if not should_execute:
    logger.warning(f"skipping duplicate execution | status: {existing_task.status}")
    return existing_task.result                  # line 120
</pre>
<p>
<code>task_instance.request.id</code> هنا هو المكان اللي <code>bind=True</code> بيرد فيه الجميل — التاسك محتاج يعرف الـ id بتاعه هو نفسه، و<code>self.request</code> هي الطريقة الوحيدة تجيبه بيها.
</p>
<div class="note">
<b>رجوع <span class="en">existing_task.result</span> مهم للسلاسل (chains).</b> التكرار المتجاهَل لازم يرجّع نفس الديكشنري اللي التاسك اللي بعده مستنيه؛ رجوع None كان هيخلي <code>push_after_process_task</code> يفشل لما يحاول <code>prev_task_result.get("project_id")</code>.
</div>
<p>وبعدين الصف بيتعمل أو بيتاخد تاني:</p>
<pre>
if existing_task:
    await idempotency_manager.update_task_status(
        execution_id=existing_task.execution_id, status="PENDING")
    task_record = existing_task          # reuse: don't insert a duplicate
else:
    task_record = await idempotency_manager.create_task_record(...)

await idempotency_manager.update_task_status(
    execution_id=task_record.execution_id, status="STARTED")
</pre>
<p>وكل مخرج بيحدّث الحالة: FAILURE قبل الـ raise مباشرة، وSUCCESS مع الـ result dict الكامل.</p>

<h2>5. جدول القرار في <span class="en">should_execute_task</span></h2>
<table>
<tr><th>حالة الصف</th><th>القيمة الراجعة</th><th>المنطق</th></tr>
<tr><td>مفيش صف</td><td>(True, None)</td><td>أول مرة</td></tr>
<tr><td>SUCCESS</td><td>(False, row)</td><td>خلص فعلاً — استخدم row.result</td></tr>
<tr><td>PENDING/STARTED/RETRY، جوه الحد الزمني</td><td>(False, row)</td><td>شغال فعلاً في مكان تاني؛ تكراره هيدي double-write</td></tr>
<tr><td>PENDING/STARTED/RETRY، بعد task_time_limit + 60 ثانية</td><td>(True, row)</td><td><b>عالق (stuck)</b> — شوف تحت</td></tr>
<tr><td>FAILURE</td><td>(True, row)</td><td>يستاهل محاولة تانية</td></tr>
</table>

<h3>فحص "العلوق" (stuck check)</h3>
<pre>
time_elapsed = (_utcnow() - existing_task.started_at).total_seconds()
grace_period = 60
if time_elapsed > (task_time_limit + grace_period):
    return True, existing_task
</pre>
<p>
<code>task_time_limit</code> (600 ثانية) هو السقف الصارم اللي بعده Celery بتعمل <code>SIGKILL</code> للبروسيس الابن — فصف لسه STARTED بعد ده زائد فترة السماح مايقدرش حد يخلّصه أبداً. من غير الفحص ده، وركر عمل كراش هيقفل الشغل ده للأبد.
</p>

<h3>باج المنطقة الزمنية (timezone bug) اللي اتصلح</h3>
<pre>
def _utcnow():
    return datetime.now(timezone.utc)
</pre>
<div class="warn">
الريبو المرجعي بيستخدم <code>datetime.utcnow()</code>، واللي بيرجع datetime <b>ساذج (naive)</b> بدون منطقة زمنية. عمود <code>started_at</code> هو <code>DateTime(timezone=True)</code>، فـ Postgres بيرجعه <b>aware</b>، والسطر اللي بيطرح الاتنين بيديك <code>TypeError: can't subtract offset-naive and offset-aware datetimes</code>. المشكلة دي بتظهر بس في مسار إعادة المحاولة — بالظبط وقت ما أكتر محتاج الفحص ده يشتغل صح. (وكمان datetime.utcnow() أصلاً deprecated من بايثون 3.12). كل datetime في الموديول ده بيعدي على _utcnow().
</div>

<h2>6. حدود النطاق — اقرا ده قبل ما تثق فيه</h2>
<p>
الفانكشن <code>get_existing_task</code> بتفلتر على <b>ثلاث</b> أعمدة:
</p>
<pre>
stmt = select(CeleryTaskExecution).where(
    CeleryTaskExecution.celery_task_id == celery_task_id,   # <-- this one
    CeleryTaskExecution.task_name == task_name,
    CeleryTaskExecution.task_args_hash == args_hash,
)
</pre>
<div class="warn">
بما إن <code>celery_task_id</code> جزء من البحث، ده بيمنع تكرار (deduplicate) <b>إعادة التوصيل وإعادة المحاولة لنفس id التاسك</b> — وده بالظبط الخطر اللي task_acks_late عمله. لكنه <b>مابيمنعش</b> تكرار بين طلبين HTTP مستقلين بنفس الآرجيومنتس بالظبط: دول بياخدوا ids مختلفة، مالقيش صف، والاتنين بيشتغلوا.
</div>
<p>على النظام الشغال فعلاً:</p>
<pre>
1. no row yet                 -> should_execute=True,  existing=None
2. SUCCESS row, SAME task id  -> should_execute=False, result={'inserted_chunks': 42}
3. SUCCESS row, DIFF task id  -> should_execute=True,  existing=None      <-- the limit
4. FAILURE row, SAME task id  -> should_execute=True,  status=FAILURE
5. STARTED (fresh), same id   -> should_execute=False  (in flight)
6. STARTED past time limit    -> should_execute=True   (stuck, reclaimed)
</pre>

<h3>عشان توسّعها لتكرار عبر الطلبات (cross-request dedup)</h3>
<p>محتاج تغييرين متزامنين مع بعض:</p>
<ol>
<li>شيل <code>celery_task_id</code> من الـ where في get_existing_task.</li>
<li>شيل <code>celery_task_id</code> من الفهرس الفريد في الموديل <b>و</b>في ميجريشن جديد، عشان <code>(task_name, task_args_hash)</code> يبقى هو المفتاح الحقيقي.</li>
</ol>
<div class="warn">
اعمل الاتنين مع بعض أو ولا واحد فيهم. لو غيرت الكويري بس، طلب تاني هيلاقي الصف الأول ويتجاهله — لكن أي مسار كود بيعمل insert هيصطدم بالفهرس التلاتي وينشئ تكرار (duplicate). ولو غيرت الفهرس بس، هتاخد نفس IntegrityError بتاع الريبو المرجعي.
</div>
<p>
كن واعي (deliberate) لأي اختيار عايزه. تكرار عبر الطلبات معناه إن <code>POST /process</code> مرتين ورا بعض بيرجّع الإجابة الأولى في صمت — عادة صح لمعالجة idempotent، لكن غريب لو الكولر متوقع إعادة تشغيل بعد ما عدّل ملفات على الديسك. لاحظ إن <code>do_reset</code> جزء من الهاش، فأي إعادة معالجة فيها reset دايماً بتتعامل كشغل جديد تماماً.
</p>

<h2>7. شكل السجل عملياً</h2>
<pre>
select execution_id, right(task_name,20) as task, status,
       result->>'inserted_chunks' as chunks
from celery_task_executions order by execution_id;
</pre>
<pre>
 execution_id |         task         | status  | chunks
--------------+----------------------+---------+--------
            4 | rocess_project_files | SUCCESS | 10
</pre>
<div class="note">
<b>بس</b> <code>process_project_files</code> هي اللي بتكتب في الجدول ده. تاسكات زي <code>index_data_content</code> و<code>push_after_process_task</code> و<code>clean_celery_executions_table</code> <b>مش</b> محمية بالبوابة دي — زي الريبو المرجعي بالظبط. الفهرسة (indexing) هي التاسك الأغلى، فتوسيع البوابة عشان تشملها هي التحسين الجاي الواضح: تعمل instantiate للمانجر بنفس الطريقة وتلف الجسم، مستخدماً <code>{"project_id": ..., "do_reset": ...}</code> كـ task_args.
</div>

</body>
</html>