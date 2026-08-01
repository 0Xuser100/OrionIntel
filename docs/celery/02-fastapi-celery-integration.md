<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Celery + FastAPI — التكامل</title>
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

<h1>Celery + FastAPI — إزاي بيتظبطوا مع بعض</h1>

<p>
الجزء الصعب في التكامل ده مش "نادي على <code>.delay()</code>". الصعوبة الحقيقية إن <b>الوركر مش FastAPI app</b>، يعني أي حاجة FastAPI جهزتها لك وقت الإقلاع لازم تبنيها بإيدك تاني من الصفر.
</p>

<h2>1. المشكلة الجوهرية: <span class="en">request.app</span> مش موجودة في الوركر</h2>
<p>
في <code>src/main.py</code> فيه <code>lifespan</code> بتاع FastAPI، وقت ما التطبيق بيقوم بيربط عملاء (clients) مشتركين على الـ app object نفسه:
</p>
<pre>
app.db_engine        = create_async_engine(postgres_conn)   # main.py:32
app.db_client        = sessionmaker(...)                    # main.py:33
app.generation_client = ...                                 # main.py:43
app.embedding_client  = ...                                 # main.py:49
app.vectordb_client   = ...                                 # main.py:57
app.template_parser   = ...                                 # main.py:61
</pre>
<p>
وكل route بعد كده بيقرا العملاء دول من <code>request.app</code>. الـ handler القديم بتاع <code>/process</code> كان بالظبط بيعمل كده.
</p>
<div class="warn">
لكن Celery worker هو أمر <code>celery -A celery_app worker</code>. مفيش <code>app</code>، مفيش <code>lifespan</code>، مفيش <code>request</code> خالص. يعني التاسك مايقدرش يستخدم أي من الخصائص دي.
</div>

<h2>2. الحل: <span class="en">get_setup_utils()</span></h2>
<p>
الفانكشن دي هي مرآة (mirror) متعمدة للـ lifespan block. نفس بناء الـ DSN (باستخدام <code>quote_plus</code> على اليوزرنيم والباسورد — لأن باسورد الـ Postgres بتاع OrionIntel فيه حرف <code>@</code>، واللي كان ممكن يكسر الـ DSN من غيرها)، نفس الـ factories، ونفس <code>await vectordb_client.connect()</code>.
</p>
<pre>
async def get_setup_utils():
    settings = get_settings()
    postgres_conn = (
        f"postgresql+asyncpg://{quote_plus(settings.POSTGRES_USERNAME)}:"
        f"{quote_plus(settings.POSTGRES_PASSWORD)}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_MAIN_DATABASE}"
    )
    db_engine = create_async_engine(postgres_conn)              # celery_app.py:45
    db_client = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    ...
    await vectordb_client.connect()                             # celery_app.py:70
    return (db_engine, db_client, llm_provider_factory, vectordb_provider_factory,
            generation_client, embedding_client, vectordb_client, template_parser)
</pre>
<p>
بتتنادى <b>لكل تاسك</b> وليس مرة واحدة لكل وركر:
</p>
<pre>
(db_engine, db_client, llm_provider_factory, vectordb_provider_factory,
 generation_client, embedding_client, vectordb_client, template_parser) = await get_setup_utils()
</pre>

<h3>ليه لكل تاسك، مش مرة واحدة وقت ما الوركر بيقوم؟</h3>
<p>
لأن الـ prefork worker بيعمل <b>fork</b> لبروسيسات أبناء (child processes). أي async engine أو socket مفتوح اتعمل في البروسيس الأب واتورث (inherited) عن طريق الـ fork، مش آمن تستخدمه — الأبناء هيبقوا شايركين نفس اتصال TCP ونفس مرجع event loop. فبناء العناصر دي جوه التاسك نفسه معناه إن العناصر بتتبنى في نفس البروسيس الابن اللي هيستخدمها فعلاً.
</p>
<p>
التكلفة هي إعداد اتصال واحد لكل تاسك (كام ميلي ثانية مقارنة بمعالجة بتتقاس بالثواني). والالتزام المقابل هو التفكيك (teardown) في الـ <code>finally</code>.
</p>
<div class="note">
الحفاظ على تطابق المسارين (main.py و celery_app.py) هو تكلفة الصيانة بتاعة التصميم ده: لو غيرت طريقة بناء عميل (client) في main.py، لازم تغير get_setup_utils() كمان.
</div>

<h2>3. الإعدادات (Configuration): كلاس Settings واحد، بروسيسين</h2>
<pre>
CELERY_BROKER_URL: str = None
CELERY_RESULT_BACKEND: str = None
CELERY_TASK_SERIALIZER: str = "json"
CELERY_TASK_TIME_LIMIT: int = 600
CELERY_TASK_ACKS_LATE: bool = True
CELERY_WORKER_CONCURRENCY: int = 2
CELERY_RESULT_EXPIRES: int = 3600
</pre>
<p>
الـ <code>Settings</code> هي <code>pydantic_settings.BaseSettings</code> بتقرا من ملف <code>.env</code>. الـ API والوركر الاتنين بينادوا على <code>get_settings()</code> وبيقروا نفس الـ <code>.env</code>، فـ <b>رابط البروكر مايقدرش ينحرف (drift) بين البروديوسر والكونسيومر</b> — واللي غير كده كان ممكن يخلي الـ API ينشر في كيو مفيش حد بيقراها، من غير أي خطأ في الاتجاهين.
</p>
<p>
بس <code>CELERY_BROKER_URL</code> و<code>CELERY_RESULT_BACKEND</code> مالهمش default قابل للاستخدام، لازم تتحط بإيدك. الخمسة الباقيين ليهم قيم افتراضية معقولة عشان أي <code>.env</code> موجود يفضل شغال.
</p>

<h2>4. جانب البروديوسر — <span class="en">src/routes/data.py</span></h2>

<h3>الاستيراد (Imports)</h3>
<pre>
from celery.result import AsyncResult      # line 4
from celery_app import celery_app          # line 9
from tasks.file_processing import process_project_files   # line 16
</pre>
<p>
عمل import لموديول التاسك جوه بروسيس الـ API هو اللي بيخلي <code>.delay()</code> ممكن أصلاً (بيدّيك proxy object بتاع التاسك). لاحظ الأثر الجانبي (side effect):
</p>
<div class="warn">
الـ API بيعمل import لموديول التاسك، فأي خطأ استيراد جوه <code>tasks/</code> هيكسر إقلاع الـ API نفسه، مش بس الوركر. عشان كده خلي موديولات التاسكات فاضية من أي شغل تقيل وقت الاستيراد.
</div>

<h3>عمل الـ Enqueue</h3>
<pre>
@data_router.post("/process/{project_id}")
async def process_data(request: Request, project_id: int, process_request: ProcessRequest):
    task = process_project_files.delay(          # line 88
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
        do_reset=process_request.do_reset,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,    # line 97
        content={
            "signal": ResponseSignal.PROCESSING_ENQUEUED.value,
            "task_id": task.id,                  # line 100
        },
    )
</pre>
<p>ثلاث حاجات مهمة هنا:</p>
<ol>
<li><b>بس أنواع قابلة للتسلسل بـJSON (JSON-serializable primitives) هي اللي بتعدي الحدود.</b> أعداد، نص، وخلاص. مايصحش تبعت الـ Session، أو الـ UploadFile، أو أي ORM object — الرسالة أصلاً JSON. ابعت الـ ids بس، وسيب التاسك يجيب الباقي بنفسه.</li>
<li><b>الرد بيبقى <code>202 Accepted</code>، مش <code>200 OK</code>.</b> ده السيمانتيكس الصح لـ"استلمت الشغل بس لسه ما خلصتوش". الـ handler القديم كان بيرجع 200 مع <code>inserted_chunks</code>؛ أي كلاينت كان مستني الحقول دي دلوقتي لازم يعمل polling.</li>
<li><b><code>.delay()</code> متزامنة (sync) وسريعة</b>، فنداءها من جوه <code>async def</code> handler عادي جداً. هي نشر TCP قصير، مش معالجة. (لو البروكر بعيد وبطيء، الحل الصح هو <code>await run_in_threadpool(...)</code> مش <code>await</code> مباشرة — لأن <code>.delay()</code> أصلاً مش awaitable.)</li>
</ol>
<p>
<code>task.id</code> هو UUID بيتولد <b>من ناحية الكلاينت</b>، قبل ما البروكر حتى يرد — عشان كده الرد ممكن يبقى فوري.
</p>

<h3>قراءة الحالة تاني</h3>
<pre>
@data_router.get("/process/status/{task_id}")
async def process_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)   # line 108
    payload = {"task_id": task_id, "state": result.state}
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    elif isinstance(result.info, dict):
        payload["meta"] = result.info
    return JSONResponse(content=payload)
</pre>
<p>
الـ <code>AsyncResult</code> بيقرا <b>بس</b> من Redis — من غير أي رحلة (round-trip) للبروكر، من غير تدخل من الوركر. تمرير <code>app=celery_app</code> مطلوب عشان يستخدم الـ backend المظبوط عندنا مش واحد افتراضي.
</p>
<p>
<code>result.result</code> هو الـ return value بتاع التاسك لو نجح، والـ <b>exception object نفسه</b> لو فشل، عشان كده بيتحول بـ <code>str(...)</code>. الفرع <code>elif isinstance(result.info, dict)</code> بيطلع أي حاجة دفعها <code>update_state(meta=...)</code>.
</p>
<div class="note">
فاكر من الدرس اللي فات: PENDING لِـ id ماتبعتش أصلاً مش ممكن تفرقه عن PENDING لواحد لسه في الكيو. تخزين task ids في جدول هو اللي بيشيل الغموض ده.
</div>

<h3>حقل الطلب الجديد — <span class="en">file_id</span></h3>
<pre>
file_id: Optional[str] = None
</pre>
<p>
حقل جديد. <code>None</code> (الافتراضي، عشان الكلاينتات القديمة ما تتأثرش) → عالج كل ملفات المشروع. قيمة معينة → عالج ملف واحد بس، بيتطابق مع <code>Asset.asset_name</code>.
</p>
<div class="warn">
<b>خد بالك:</b> <code>POST /upload</code> بيرجع <code>"file_id": str(asset_record.asset_id)</code> وهو الـ primary key الرقمي. لكن التاسك بيدور على <code>file_id</code> كـ <code>asset_name</code> (اسم الملف الفريد المولّد). دول شيئين مختلفين شايلين نفس الاسم، موروثين من الريبو المرجعي. عشان تعالج ملف واحد النهاردة، لازم تبعت الـ asset_name المخزن، مش الـ id الرقمي.
</div>

<h2>5. اللي اتنقل من جوه الـ route</h2>
<p>
كل الـ pipeline اللي كانت جوه الـ route — تحديد المشروع، سرد الملفات، الريسيت الاختياري، تحميل كل ملف، تقسيمه لـ chunks، والإدخال الجماعي (bulk-insert) — بقت كلها جوه <code>src/tasks/file_processing.py</code>. المنطق نفسه ما اتغيرش؛ اللي اتغير هو مكانها ومصدر العملاء بتاعتها:
</p>
<table>
<tr><th>القديم، في الـ route</th><th>الجديد، في التاسك</th></tr>
<tr><td><code>request.app.db_client</code></td><td><code>db_client</code> من <code>get_setup_utils()</code></td></tr>
<tr><td><code>request.app.vectordb_client</code></td><td><code>vectordb_client</code> من نفس الـ tuple</td></tr>
<tr><td><code>request.app.generation_client</code> وغيرها</td><td>نفس الفكرة</td></tr>
<tr><td><code>return JSONResponse(400, NO_FILES_ERROR)</code></td><td><code>raise FileProcessingError(NO_FILES_ERROR, ...)</code></td></tr>
<tr><td><code>return JSONResponse(400, FILE_ID_ERROR)</code></td><td><code>raise FileProcessingError(FILE_ID_ERROR, ...)</code></td></tr>
<tr><td><code>return JSONResponse(PROCESSING_SUCCESS, ...)</code></td><td><code>return {...}</code> — بتتخزن في Redis</td></tr>
<tr><td>—</td><td><code>update_state("PROGRESS", ...)</code> لكل ملف</td></tr>
<tr><td>—</td><td><code>finally:</code> بتفكك الـ engine وعميل الـ vector</td></tr>
</table>
<div class="note">
لاحظ انعكاس طريقة الإبلاغ عن الخطأ: الـ route بيبلغ عن فشل عن طريق إنه <b>يرجع</b> (return) كود 4xx؛ لكن التاسك بيبلغ عن فشله عن طريق إنه <b>يرمي (raise)</b> إكسبشن. التاسك اللي بيرجع عادي يبقى SUCCESS، خلاص، مفيش نص تاني.
</div>
<p>
الـ <code>FileProcessingError</code> موجودة عشان الـ <code>ResponseSignal</code> يوصل للكلاينت برضه. بتشيل السيجنال جوه رسالتها، فـ <code>str(result.result)</code> في endpoint الحالة بيطلع مثلاً: <code>not_found_files: no files for project_id: 999</code>. البديل — <code>update_state(state="FAILURE", meta={"signal": ...})</code> — ده فخ بيبوظ سجل النتيجة، زي ما شرحنا قبل كده.
</p>

<h3>نتيجة جانبية بتاعة <span class="en">autoretry_for=(Exception,)</span></h3>
<p>
الإعداد ده بيعيد المحاولة (retry) لـ <b>أي</b> إكسبشن لحد 3 مرات، كل مرة بعد 60 ثانية. وده شامل الحالات الحتمية (deterministic) كمان: "مفيش ملفات في المشروع ده" هيتعاد ثلاث مرات على مدار ثلاث دقايق قبل ما يستقر على FAILURE. ده سلوك الريبو المرجعي وهو مش ضار هنا (مفيش حاجة بتتكتب)، لكن لو عايز فشل سريع للحالات دي، اعمل نوع إكسبشن مخصص وضيّق <code>autoretry_for</code> للحالات العابرة (transient) بس زي <code>OSError</code> وأخطاء asyncpg.
</p>

<h2>6. شكل الـ API قبل وبعد</h2>
<pre>
# قبل — بيتحجز لحد ما المعالجة تخلص
curl -X POST localhost:8000/api/v1/data/process/1 \
  -H 'Content-Type: application/json' -d '{"chunk_size":512,"overlap_size":50,"do_reset":1}'
# 200 {"signal":"processing_success","inserted_chunks":128,"processed_files":3}

# بعد — بيرجع فوراً
curl -X POST localhost:8000/api/v1/data/process/1 \
  -H 'Content-Type: application/json' -d '{"chunk_size":512,"overlap_size":50,"do_reset":1}'
# 202 {"signal":"processing_enqueued","task_id":"9f1c...e2"}

curl localhost:8000/api/v1/data/process/status/9f1c...e2
# {"task_id":"9f1c...e2","state":"SUCCESS",
#  "result":{"signal":"processing_success","inserted_chunks":128,"processed_files":3}}
</pre>

<div class="note">
<b>خلاصة سريعة:</b> كل حاجة في الدرس ده بتدور حوالين نقطة واحدة — الوركر معزول تماماً عن عالم FastAPI، فأي حاجة عايزها جوه التاسك لازم تبنيها بنفسك بدل ما تعتمد على حاجة FastAPI جهزتها. get_setup_utils() هو التكرار المتعمد لده، والـ 202 + polling هو الشكل الصح للتواصل مع كلاينت مبقاش مستني رد فوري.
</div>

</body>
</html>