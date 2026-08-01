<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Celery — الأساسيات</title>
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
    font-size: 14px;
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

<h1>Celery — الأساسيات</h1>

<h2>1. المشكلة اللي الـ Celery بيحلها</h2>
<p>
تخيل عندك ريكوست (request) لازم يفضل سريع. لكن مثلاً معالجة ملف PDF من 200 صفحة مش حاجة سريعة. لو عملتها جوه الـ request handler نفسه هيحصل الآتي:
</p>
<ul>
<li>الكلاينت (client) هيفضل مستني، وممكن يحصله تايم آوت، أو nginx يقطع الاتصال بعد 60 ثانية.</li>
<li>الـ uvicorn worker هيتحجز طول مدة المعالجة دي.</li>
<li>لو حصل كراش في النص، الشغل ده بيضيع من غير أي سجل (record) إنه كان مطلوب أصلاً.</li>
<li>مش هتقدر تعمل ريتراي (retry) من غير ما الكلاينت يرفع الملف تاني.</li>
</ul>
<p>
الـ Celery بينقل الشغل ده لبروسيس (process) منفصل تماماً، والحاجة الوحيدة اللي بتعدي بين الاتنين هي رسالة JSON صغيرة.
</p>

<h2>2. الأربع مكونات الأساسية</h2>
<pre>
  producer                broker                consumer              result backend
 ──────────           ─────────────           ──────────            ────────────────
 FastAPI              RabbitMQ                celery worker          Redis
 .delay(...)   ──▶    queue: file_processing  ──▶  runs the task ──▶  task_id → state
</pre>

<h3>البروديوسر (Producer)</h3>
<p>
هو أي حاجة بتنادي على <code>.delay()</code>. في مشروعنا ده الـ FastAPI route. الحاجة المهمة إن البروديوسر مش بيعمل import للشغل التقيل (heavy work) نفسه، هو محتاج بس اسم التاسك (task name) والاتصال بالبروكر.
</p>

<h3>البروكر (Broker) — RabbitMQ</h3>
<p>
هو كيو (queue) دائم (durable). لما تنادي <code>.delay()</code> بتنشر رسالة وترجع في أجزاء من الثانية. لو مفيش ورکر شغال، الرسالة هتفضل مستنية. الجزء ده هو اللي بيخلي السيستم يعيش حتى لو الوركر عمل ريستارت (restart).
</p>

<h3>الكونسيومر (Consumer) — celery worker</h3>
<p>
بروسيس بيشتغل باستمرار بأمر <code>celery -A celery_app worker</code>. بيتصل بالبروكر، بيسحب الرسايل، بيدور على اسم التاسك في الريجستري (registry) بتاعه، وبعدين بينادي على الفانكشن.
</p>

<h3>الـ Result Backend — Redis</h3>
<p>
دي key-value store اختيارية، بيكتب فيها الوركر حالة كل تاسك (<code>PENDING</code> → <code>STARTED</code> → <code>SUCCESS</code>/<code>FAILURE</code>) والـ return value بتاعه. من غيرها الـ <code>.delay()</code> هيشتغل عادي، بس مش هتقدر تسأل "خلص ولا لسه؟".
</p>

<h3>ليه بنستخدم اتنين سيرفيس مختلفين؟</h3>
<p>كل واحد فيهم متعمل عشان حاجة مختلفة تماماً عن التاني:</p>
<table>
<tr><th></th><th>RabbitMQ (broker)</th><th>Redis (result backend)</th></tr>
<tr><td>الشغلانة</td><td>يوصّل كل رسالة مرة واحدة بالظبط لورکر واحد</td><td>يخزن قيمة صغيرة تحت مفتاح، وتتقرا كذا مرة</td></tr>
<tr><td>الضمانات</td><td>كيوهات دائمة، acknowledgements، إعادة توصيل لو حصل كراش</td><td>in-memory مع append-only log، والقيم بتنتهي (expire)</td></tr>
<tr><td>نمط الوصول</td><td>كتابة مرة، قراءة مرة، وخلاص</td><td>كتابة مرة، N قراءة، وبعدين TTL</td></tr>
<tr><td>لو وقع</td><td>مش هتقدر تعمل enqueue لشغل جديد</td><td>الشغل بيفضل شغال، بس مش هتقدر تقرا الحالة</td></tr>
</table>
<div class="note">
Redis ممكن يتستخدم كـ broker كمان، بس مفيهوش موديل acknowledgement حقيقي — يعني ورکر اتقتل في نص الشغل ممكن يضيّع الرسالة. بروتوكول الـ ack بتاع RabbitMQ هو السبب إننا مستخدمينه للكيو.
</div>

<h2>3. دورة حياة التاسك بالتفصيل</h2>
<pre>
client                FastAPI                RabbitMQ           worker              Redis
  │  POST /process       │                      │                  │                  │
  ├─────────────────────▶│                      │                  │                  │
  │                      │ .delay(kwargs)       │                  │                  │
  │                      ├─── JSON message ────▶│                  │                  │
  │                      │                      │   (queued)       │                  │
  │  202 {"task_id":..}  │                      │                  │                  │
  │◀─────────────────────┤                      │                  │                  │
  │                      │                      ├─── deliver ─────▶│                  │
  │                      │                      │                  │ STARTED          │
  │                      │                      │                  ├─────────────────▶│
  │  GET /process/status │                      │                  │  ...work...      │
  ├─────────────────────▶│──────── read state ──┼──────────────────┼─────────────────▶│
  │  {"state":"STARTED"} │                      │                  │                  │
  │◀─────────────────────┤                      │                  │ SUCCESS + result │
  │                      │                      │◀──── ACK ────────┤─────────────────▶│
</pre>
<p>
الـ <code>ACK</code> في الآخر هو بيت القصيد كله بتاع <code>task_acks_late</code> (هنشرحها بعدين). الرسالة مش بتتشال من RabbitMQ إلا لما التاسك يخلص شغله فعلاً.
</p>

<h2>4. الـ Task Object — <span class="en">src/tasks/file_processing.py:38-63</span></h2>
<pre>
@celery_app.task(
    bind=True,
    name="tasks.file_processing.process_project_files",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def process_project_files(self, project_id, file_id, chunk_size, overlap_size, do_reset):
    return asyncio.run(
        _process_project_files(self, project_id, file_id, chunk_size, overlap_size, do_reset)
    )
</pre>

<table>
<tr><th>الآرجيومنت</th><th>المعنى</th></tr>
<tr><td><code>bind=True</code></td><td>بيمرر التاسك نفسه (instance) كأول باراميتر <code>self</code>. محتاجها عشان تنادي <code>self.update_state(...)</code> أو <code>self.retry(...)</code>. من غيرها أول آرجيومنت هيبقى <code>project_id</code>.</td></tr>
<tr><td><code>name=</code></td><td>الاسم اللي فعلاً بيسافر جوه الرسالة. لازم تحدده بنفسك (pin it): لو اعتمدت على الاسم التلقائي (المسار بتاع الملف) وبعدين نقلت الملف، أي رسالة موجودة في الكيو هتبقى unroutable. لازم كمان يتطابق مع المفتاح في <code>task_routes</code>.</td></tr>
<tr><td><code>autoretry_for=(Exception,)</code></td><td>أي إكسبشن → ريتراي تلقائي بدل ما يروح على طول لـ <code>FAILURE</code>.</td></tr>
<tr><td><code>retry_kwargs</code></td><td>أقصى 3 محاولات، كل واحدة بعد 60 ثانية من اللي قبلها.</td></tr>
</table>

<h3>الجسر بين الـ sync والـ async — السطر 59</h3>
<p>
الـ worker pool الافتراضي (default) بتاع Celery اسمه <b>prefork</b> — يعني بروسيسات حقيقية من نظام التشغيل، بايثون عادي متزامن (synchronous). لكن الطبقة اللي بتتعامل مع الداتا في OrionIntel كلها async (asyncpg، SQLAlchemy async، وحتى الـ vector-DB providers). فالـ <code>asyncio.run()</code> بيعمل event loop جديد، بيشغل الكوروتين (coroutine) لحد ما يخلص، وبعدين بيقفل اللوب.
</p>
<p>
الحركة دي آمنة <b>هنا تحديداً</b> لأن الـ prefork child بيتعامل مع تاسك واحد بس في المرة الواحدة. كان هيبقى غلط إنك تعمل loop جديد لكل نداء جوه لوب واحد طويل العمر مشترك — عشان كده جسم التاسك كله عايش جوه الكوروتين الخاص <code>_process_project_files</code>، والتاسك العام نفسه مجرد wrapper رفيع متزامن.
</p>

<h3>عرض التقدم — <span class="en">update_state</span> بحالة مخصصة</h3>
<pre>
task_instance.update_state(
    state="PROGRESS",
    meta={"current": index, "total": total_files, "file": asset_name},
)
</pre>
<p>
الـ <code>meta</code> بتتكتب في الـ result backend وهي اللي بيرجعها <code>AsyncResult.info</code>. لازم تكون قابلة للتسلسل بصيغة JSON — يعني أعداد ونصوص، و<code>ResponseSignal.X.value</code> بدل الـ enum نفسه في أي مكان بيتخزن فيه سيجنال.
</p>
<div class="warn">
<b><span class="en">"PROGRESS"</span> اسم اخترعناه إحنا، وده بالظبط بيت القصيد.</b> الـ <code>update_state</code> بيقبل كمان حالات Celery المحجوزة (reserved)، واتنين منهم أبداً ما ينفعش تحطهم بإيدك:
<ul>
<li><b>FAILURE</b> — القيمة المخزنة (<code>result</code>) لازم تكون exception payload (<code>exc_type</code> + <code>exc_message</code>). لو خزنت ديكشنري (dict) عادي، الميثود <code>mark_as_failure()</code> بعدين هتحاول تقراه عن طريق <code>exception_to_python()</code> وهترمي <code>ValueError</code> بتقول إن معلومات الإكسبشن لازم تتضمن نوع الإكسبشن. النتيجة إن الخطأ الحقيقي مش بيتسجل خالص. عشان كده مسارات الفشل عندنا بترمي <code>FileProcessingError</code> بدل ما تحط update_state بإيدها.</li>
<li><b>SUCCESS</b> — الفانكشن <code>_store_result()</code> بتعمل short-circuit، يعني لو الحالة الحالية SUCCESS بترجع الـ result من غير ما تكمل. فلو أنت حطيت SUCCESS بإيدك، Celery هتتجاهل الـ return value الحقيقي بتاع التاسك. الحل: عمل <code>return</code> عادي وخلاص.</li>
</ul>
أسماء الحالات المخصصة (زي PROGRESS) بتتجاوز المشكلتين دول لأن Celery أصلاً مش بتحاول تفسر الـ meta بتاعتهم.
</div>

<h3>التنضيف — السطور 213-222</h3>
<pre>
finally:
    if db_engine:
        await db_engine.dispose()
    if vectordb_client:
        await vectordb_client.disconnect()
</pre>
<p>
الـ worker process بيعيش لأيام. كل تاسك بيبني engine خاص بيه، فلازم كل تاسك يفكك (dispose) الـ engine ده كمان، وإلا الـ Postgres هيخلص عنده connections بعد كام مية تاسك. الفرق ده هو أكبر فرق بين "كود جوه request handler" و"كود جوه worker".
</p>

<h2>5. كل الـ Config Keys اللي متظبطة</h2>
<h3>الكونستركتور (Constructor)</h3>
<pre>
celery_app = Celery(
    "orionintel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.file_processing"],
)
</pre>
<ul>
<li><b>"orionintel"</b> — اسم التطبيق الأساسي (main name)، بيستخدم كـ prefix للأسماء التلقائية وبيظهر في شعار الوركر.</li>
<li><b>broker</b> — رابط بصيغة <code>amqp://user:pass@host:5672/vhost</code>.</li>
<li><b>backend</b> — رابط بصيغة <code>redis://:pass@host:6379/0</code>. لاحظ النقطتين في الأول (<code>:pass</code>) — لأن Redis عنده باسورد بس من غير يوزرنيم. والـ <code>/0</code> في الآخر هو رقم الداتابيز المنطقي في Redis.</li>
<li><b>include</b> — الموديولز اللي الوركر بيعملها import وقت ما يبدأ. ده أشهر سبب لخطأ <code>Received unregistered task of type ...</code>: البروديوسر عارف اسم التاسك لأنه عمله import، لكن الوركر أبداً ما عملش import للموديول، فالريجستري بتاعته فاضية.</li>
</ul>

<h3>إعدادات <span class="en">conf.update(...)</span></h3>
<table>
<tr><th>المفتاح</th><th>القيمة</th><th>السبب</th></tr>
<tr><td><code>task_serializer</code> / <code>result_serializer</code> / <code>accept_content</code></td><td>json</td><td>JSON بس. البديل التاني بتاع Celery وهو <code>pickle</code> بيعمل deserialize لأي كود بايثون — بروكر مخترق (compromised) هيبقى عملياً remote code execution جوه الوركر.</td></tr>
<tr><td><code>task_acks_late</code></td><td>True</td><td>الـ ack بيحصل بعد ما التاسك يخلص، مش وقت الاستلام. لو الوركر اتقتل في النص، RabbitMQ ما استلمتش ack فبتعيد توصيل الرسالة لوركر تاني. الميزة دي معناها إن التاسك ممكن يشتغل مرتين، فلازم يكون idempotent — وفعلاً عندنا كده لما <code>do_reset=1</code> بيمسح الـ chunks القديمة الأول.</td></tr>
<tr><td><code>task_time_limit</code></td><td>600</td><td>ليميت صارم بالثانية. عند 600 ثانية البروسيس الابن (child) بيتقتل بـ <code>SIGKILL</code> والتاسك بيفشل. من غيرها تاسك واحد عالق ممكن ياخد concurrency slot للأبد.</td></tr>
<tr><td><code>task_ignore_result</code></td><td>False</td><td>يعني فعلاً اكتب النتايج في Redis. لو كانت True، أي endpoint بيتابع حالة التاسك هيفضل يرجع PENDING على طول.</td></tr>
<tr><td><code>result_expires</code></td><td>3600</td><td>النتايج بتتمسح من Redis بعد ساعة، وإلا الـ backend هيكبر من غير حد.</td></tr>
<tr><td><code>worker_concurrency</code></td><td>2</td><td>عدد الـ prefork child processes اللي كل وركر بيشغلهم، يعني كام تاسك بيشتغلوا بالتوازي. المعالجة هنا I/O-bound (ديسك وPostgres)، فممكن الرقم ده يعدي عدد الـ CPU cores، بس كل child بيفتح engine خاص بيه، فلازم ترفع الرقم ده مع max_connections بتاعة Postgres مع بعض.</td></tr>
<tr><td><code>broker_connection_retry_on_startup</code></td><td>True</td><td>في Celery 5.x، لو البروكر مش شغال وقت الإقلاع (boot)، الوركر بيموت غير لو ده متظبط. أساسي جداً تحت compose، لأن RabbitMQ بياخد حوالي 20 ثانية عشان يبقى جاهز.</td></tr>
<tr><td><code>broker_connection_retry</code></td><td>True</td><td>يعيد الاتصال لو البروكر وقع بعدين.</td></tr>
<tr><td><code>broker_connection_max_retries</code></td><td>10</td><td>يستسلم بعد 10 محاولات بدل ما يفضل يلف للأبد.</td></tr>
<tr><td><code>worker_cancel_long_running_tasks_on_connection_loss</code></td><td>True</td><td>لو اتصال البروكر مات في نص التاسك، سيب التاسك بدل ما تكمله — لأن الـ ack بتاعه أصلاً مش هيتوصل. ومع task_acks_late، هيتم إعادة توصيله برضه، فإكماله هيدي duplicate للكتابة.</td></tr>
<tr><td><code>task_routes</code></td><td>→ queue file_processing</td><td>شوف الشرح تحت</td></tr>
<tr><td><code>task_default_queue</code></td><td>default</td><td>أي حاجة مش متطابقة مع task_routes بتروح هنا.</td></tr>
</table>

<h3>الكيوهات (Queues) والـ Routing</h3>
<pre>
task_routes={
    "tasks.file_processing.process_project_files": {"queue": "file_processing"},
}
</pre>
<p>
الكيو هي طابور (line) بأسم معين جوه البروكر. لما تحول (route) الشغل التقيل لكيو خاصة بيه، تقدر بعدين تشغل:
</p>
<pre>
celery -A celery_app worker -Q file_processing --concurrency=4   # heavy box
celery -A celery_app worker -Q default        --concurrency=8   # light box
</pre>
<p>
عشان ملفات الـ PDF الكبيرة اللي متكدسة (backlog) مايقدروش يخنقوا التاسكات الصغيرة. دلوقتي وركر واحد بيستهلك من الكيوهين مع بعض، والفصل ده متجهز فعلاً عشان الفصل الفعلي يبقى تغيير في الـ deployment مش تغيير في الكود.
</p>
<div class="warn">
الوركر بيستهلك من الكيوهات المذكورة في <code>-Q</code> فقط. لو ضفت route لكيو جديدة ونسيت تضيفها في <code>-Q</code>، التاسكات هتقعد في RabbitMQ للأبد من غير أي خطأ يظهر في أي مكان. دي ثاني أشهر غلطة في Celery بعد الـ include.
</div>

<h2>6. حالات التاسك (Task States)</h2>
<table>
<tr><th>الحالة</th><th>المعنى</th></tr>
<tr><td><code>PENDING</code></td><td>الإجابة الافتراضية بتاعة Celery لأي id مش معروف. معناها "مفيش سجل في Redis" — يا إما لسه في الكيو، أو الـ id ده أصلاً مش موجود، أو النتيجة انتهت (expired). مش دليل إن التاسك موجود فعلاً.</td></tr>
<tr><td><code>STARTED</code></td><td>بتتسجل بس لو <code>task_track_started</code> متفعلة (إحنا مش مفعلينها).</td></tr>
<tr><td><code>PROGRESS</code></td><td>حالة مخصصة بتاعتنا إحنا مش بتاعة Celery — بتتحط لكل ملف عن طريق update_state.</td></tr>
<tr><td><code>RETRY</code></td><td>فشل، وبينتظر المحاولة الجاية من الـ3 محاولات.</td></tr>
<tr><td><code>SUCCESS</code></td><td>خلص؛ الـ result فيه القيمة اللي رجعت.</td></tr>
<tr><td><code>FAILURE</code></td><td>استسلم؛ الـ result فيه الإكسبشن.</td></tr>
</table>

<h2>7. أشهر الأعطال (Common Failure Modes)</h2>
<table>
<tr><th>العرض (Symptom)</th><th>السبب</th></tr>
<tr><td><code>Received unregistered task of type ...</code></td><td>الوركر مش عامل import للموديول ← ناقص من <code>include</code>.</td></tr>
<tr><td>التاسك فاضل PENDING للأبد</td><td>مفيش وركر بيستهلك من الكيو دي (تأكد من <code>-Q</code>)، أو رابط البروكر مختلف بين الـ API والوركر.</td></tr>
<tr><td><code>consumer: Cannot connect to amqp://...</code></td><td>بيانات دخول أو vhost غلط، أو RabbitMQ لسه مش شغال.</td></tr>
<tr><td>endpoint الحالة دايماً بيرجع PENDING مع إن التاسك فعلاً اشتغل</td><td>الـ result backend مش قادر يوصله، أو <code>task_ignore_result=True</code>.</td></tr>
<tr><td><code>FileNotFoundError</code> في الوركر مع إن الرفع نجح</td><td>الـ API والوركر مش شايفين نفس الـ uploads volume.</td></tr>
<tr><td><code>kombu.exceptions.EncodeError: Object of type X is not JSON serializable</code></td><td>بعتّ حاجة مش JSON جوه <code>.delay()</code> أو جوه <code>meta=</code>.</td></tr>
<tr><td><code>ValueError: Exception information must include the exception type</code></td><td>حد نادى <code>update_state(state="FAILURE", meta={...})</code> بديكشنري عادي. الحل: ارمي إكسبشن بدل ده.</td></tr>
</table>

<div class="note">
<b>خلاصة سريعة:</b> الفكرة الأساسية كلها إنك بتفصل الشغل التقيل عن الـ request handler، وبتخلي الرسالة اللي عابرة الحدود بين الاتنين صغيرة قدر الإمكان (JSON بس). البروكر بيضمن التوصيل، الـ result backend بيدّيك مكان تشوف فيه الحالة، وباقي الإعدادات كلها بتحل مشاكل عملية واقعية (كراش، تكدس، تسريب اتصالات) مش مجرد نظرية.
</div>

</body>
</html>