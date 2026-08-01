<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>الـ Workflows وسلاسل التاسكات</title>
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

<h1>الـ Workflows: تسلسل التاسكات (Chains) ونقل الفهرسة للكيو</h1>

<h2>1. حاجتين بيحصلوا هنا</h2>
<ol>
<li><b>الـ <span class="en">POST /api/v1/nlp/index/push/{project_id}</span> بينتقل للكيو.</b> الفهرسة (indexing) للـ vectors كانت لسه شغالة inline — أبطأ عملية واحدة في التطبيق كله.</li>
<li><b>Endpoint جديد <span class="en">POST /api/v1/data/process-and-push/{project_id}</span></b> بيشغل التقسيم (chunking) <b>والفهرسة</b> كـ workflow واحد معتمد على بعضه، باستخدام <b>chain</b> بتاعة Celery.</li>
</ol>

<h2>2. الفهرسة كتاسك — <span class="en">src/tasks/data_indexing.py</span></h2>
<p>
الجسم هو نفسه الـ handler القديم بتاع <code>routes/nlp.py</code>، بس العملاء (clients) جايين من <code>get_setup_utils()</code> بدل <code>request.app</code>. فرقين يستاهلوا الذكر:
</p>
<div class="warn">
<b>الفشل بيرمي <span class="en">DataIndexingError</span></b>، نفس نمط <code>FileProcessingError</code> — أبداً <code>update_state(state="FAILURE", meta={dict})</code>، للسبب اللي شرحناه في الدرس الأول.
</div>
<p><b>التقدم (progress) بيتسجل لكل باتش:</b></p>
<pre>
task_instance.update_state(
    state="PROGRESS",
    meta={"indexed": inserted_items_count, "total": total_chunks_count},
)
</pre>
<p>
الفهرسة هي العملية اللي فيها الكلاينت فعلاً محتاج يشوف تقدم — رحلة نداء واحدة لـ embedding API لكل صفحة من الـ chunks. الـ <code>GET /api/v1/nlp/index/push/status/{task_id}</code> بيطلع ده في <code>meta</code>.
</p>
<p>
فيه كمان progress bar بتاعة <code>tqdm</code> موروثة من الريبو المرجعي. بتكتب على stdout بتاع الوركر، فبتظهر في <code>docker compose logs</code>، مش لأي كلاينت. مش ضارة، لكن <code>update_state</code> هي الجزء اللي فعلاً مهم دلوقتي.
</p>

<h3>الـ Route</h3>
<pre>
@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: int, push_request: PushRequest):
    task = index_data_content.delay(
        project_id=project_id,
        do_reset=push_request.do_reset,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"signal": ResponseSignal.DATA_PUSH_TASK_READY.value,
                 "task_id": task.id},
    )
</pre>
<p>
حوالي 75 سطر من الـ handler بقوا خمسة. <code>202</code> بدل <code>200</code>، و<code>inserted_items_count</code> دلوقتي بتوصل عن طريق endpoint الحالة مش جوه الرد المباشر.
</p>

<h2>3. الـ Chain إيه هي</h2>
<p>
الـ chain هي طريقة Celery إنها تقول "شغّل B بعد A، وادّي B اللي A رجّعه". الاعتمادية (dependency) عايشة على السيرفر، مش في لوب الـ polling بتاع الكلاينت.
</p>
<pre>
      .delay()                    chain
 API ─────────▶ process_and_push_workflow
                        │
                        │ apply_async()
                        ▼
              process_project_files ──result dict──▶ push_after_process_task
                 (queue: file_processing)              (queue: default)
                                                              │
                                                    calls _index_data_content()
                                                       in-process
</pre>
<p>ضمانتين بتاخدهم ببلاش:</p>
<ul>
<li>الحلقة التانية بتشتغل <b>بس لو</b> الحلقة الأولى نجحت — لو الأولى انتهت FAILURE، الحلقة التانية أبداً مش بتتبعت.</li>
<li>الـ return value بتاع الحلقة الأولى <b>هو نفسه</b> أول آرجيومنت للحلقة التانية.</li>
</ul>

<h2>4. الكود — <span class="en">src/tasks/process_workflow.py</span></h2>
<h3>بناء الـ Chain</h3>
<pre>
def process_and_push_workflow(self, project_id, file_id, chunk_size,
                              overlap_size, do_reset):
    workflow = chain(
        process_project_files.s(project_id, file_id, chunk_size, overlap_size, do_reset),
        push_after_process_task.s(),
    )
    result = workflow.apply_async()

    return {
        "signal": "WORKFLOW_STARTED",
        "workflow_id": result.id,
        "tasks": [...],
    }
</pre>
<table>
<tr><th>الجزء</th><th>المعنى</th></tr>
<tr><td><code>.s(args...)</code></td><td><b>Signature</b>: التاسك زائد آرجيوماتته، متجهزة لكن مش متبعتة. السلاسل بتتبني من الـ signatures، مش من النداءات المباشرة.</td></tr>
<tr><td><code>push_after_process_task.s()</code></td><td>لاحظ الـ <code>.s()</code> <b>الفاضية</b>. جوه chain، الـ signature اللي من غير آرجيومنتس بتستقبل الـ return value بتاع التاسك اللي قبلها كأول آرجيومنت positional ليها.</td></tr>
<tr><td><code>chain(a, b)</code></td><td>بيوصّل بينهم: b بتشتغل بعد نجاح a، بنتيجة a.</td></tr>
<tr><td><code>apply_async()</code></td><td>بينشر الحلقة الأولى وبيرجع <code>AsyncResult</code> <b>للحلقة الأخيرة</b>. يعني الـ id الراجع هو اللي هيديك الإجابة النهائية.</td></tr>
</table>
<p>
<code>process_and_push_workflow</code> هو نفسه تاسك، ومش بيعمل أي شغل حقيقي — بيبني الشغل وبينشره وبيرجع في أجزاء من الثانية. ده اللي بيخلي الـ route يسلّم بنداء <code>.delay()</code> واحد. التكلفة هي قفزة (hop) إضافية في البروكر واتنين id لازم تتابعهم.
</p>

<h3>ليه نتيجة الحلقة الأولى شايلة <span class="en">project_id</span></h3>
<pre>
result = {
    "signal": ...,
    "inserted_chunks": no_records,
    "processed_files": no_files,
    "project_id": project_id,   # for the chain
    "do_reset": do_reset,       # for the chain
}
</pre>
<p>والحلقة التانية بتقراهم تاني:</p>
<pre>
project_id = prev_task_result.get("project_id")
do_reset = prev_task_result.get("do_reset")
</pre>
<div class="note">
حلقة في السلسلة بتستقبل بس الـ return value بتاعة اللي قبلها — مفيش context مشترك بينهم. أي حاجة الخطوة الجاية محتاجاها لازم تكون جوه الديكشنري ده. ده كمان السبب إن أي تكرار متجاهَل (skipped duplicate) بيرجع existing_task.result بدل None.
</div>

<h3>الحلقة التانية بتنادي على الكوروتين مباشرة</h3>
<pre>
task_results = asyncio.run(_index_data_content(self, project_id, do_reset))
</pre>
<p>
مش <code>index_data_content.delay(...)</code>. الفهرسة بتشتغل <b>جوه الحلقة التانية نفسها</b>، في نفس مكان الوركر ده. النتائج، بالسلب والإيجاب:
</p>
<table>
<tr><th></th><th>الأثر</th></tr>
<tr><td>كويس</td><td>قفزة بروكر أقل واحدة؛ نتيجة السلسلة النهائية هي نفسها نتيجة الفهرسة، فـ id واحد بيجاوب على "الشغل كله نجح ولا لأ؟"</td></tr>
<tr><td>وحش</td><td>بيتجاهل task_routes، فالفهرسة دي مش بتنزل على كيو data_indexing — بتشتغل في أي مكان اشتغلت فيه الحلقة التانية (default). فمش هتقدر تعمل scale للفهرسة المسلسلة بمعزل عن الفهرسة المستقلة.</td></tr>
</table>
<p>
عشان كده <code>_index_data_content</code> كوروتين على مستوى الموديول مش متداخل (nested) جوه التاسك بتاعه — كولرين، وجسم واحد.
</p>

<h3>التوجيه (Routing)</h3>
<pre>
task_routes={
    "tasks.file_processing.process_project_files": {"queue": "file_processing"},
    "tasks.data_indexing.index_data_content":      {"queue": "data_indexing"},
    "tasks.process_workflow.process_and_push_workflow": {"queue": "file_processing"},
    "tasks.maintenance.clean_celery_executions_table":  {"queue": "default"},
}
</pre>
<div class="warn">
<code>push_after_process_task</code> <b>مش</b> متوجهة، فبتنزل على <code>task_default_queue = "default"</code>. الوركر لازم بالتالي يستهلك من التلات كيوهات:
</div>
<pre>
command: ["celery", "-A", "celery_app", "worker", "--loglevel=INFO",
          "-Q", "file_processing,data_indexing,default"]
</pre>
<p>
لو شيلت <code>default</code> من الليستة دي، السلسلة هتقف للأبد بعد الحلقة الأولى، من غير أي خطأ يظهر في أي مكان — الحلقة التانية بتقعد في كيو مفيش حد بيقراها.
</p>

<h2>5. الـ Endpoint</h2>
<pre>
@data_router.post("/process-and-push/{project_id}")
async def process_and_push(request: Request, project_id: int,
                           process_request: ProcessRequest):
    workflow_task = process_and_push_workflow.delay(...)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"signal": ResponseSignal.PROCESS_AND_PUSH_WORKFLOW_READY.value,
                 "workflow_task_id": workflow_task.id},
    )
</pre>

<h2>6. الـ id-ين — الجزء المحيّر</h2>
<p>هتاخد <b>اتنين</b> id مختلفين للتاسك وكل واحد بيجاوب على سؤال مختلف.</p>
<pre>
# 1. الإطلاق
curl -X POST localhost:8000/api/v1/data/process-and-push/12 \
  -H 'Content-Type: application/json' \
  -d '{"chunk_size":300,"overlap_size":20,"do_reset":1}'
# 202 {"signal":"process_and_push_workflow_ready",
#      "workflow_task_id":"2b03befd-...-6adfc0964432"}     <-- اللانشر
</pre>
<pre>
# 2. نتيجة اللانشر نفسها شايلة id السلسلة
curl localhost:8000/api/v1/data/process/status/2b03befd-...
# {"state":"SUCCESS","result":{"signal":"WORKFLOW_STARTED",
#   "workflow_id":"4db5a398-...-09ad6fe75dd3",             <-- آخر حلقة في السلسلة
#   "tasks":["tasks.file_processing.process_project_files",
#            "tasks.process_workflow.push_after_process_task"]}}
</pre>
<pre>
# 3. الـ id ده هو اللي بيدي الإجابة الحقيقية النهائية
curl localhost:8000/api/v1/data/process/status/4db5a398-...
# {"state":"SUCCESS","result":{"project_id":12,"do_reset":1,
#   "task_results":{"signal":"insert_into_vectordb_success",
#                   "inserted_items_count":10}}}
</pre>
<div class="warn">
وصول <code>workflow_task_id</code> لـ SUCCESS معناها بس <b>"السلسلة اتبعتت (dispatched)"</b> — ده مش دليل إن الشغل نجح فعلاً. لازم دايماً تتبع بعدين workflow_id. API أنظف كان المفروض يرجع الاتنين من الـ endpoint نفسه؛ الشكل بخطوتين ده موروث من الريبو المرجعي وسايبينه كده للأمانة (fidelity).
</div>

<h2>7. لوج الوركر الموثّق</h2>
<p>نداء واحد لـ <code>/process-and-push</code>، بالترتيب:</p>
<pre>
Task tasks.process_workflow.process_and_push_workflow[51a13b67…] received
Task tasks.file_processing.process_project_files[5a9d043a…] received
Task tasks.process_workflow.process_and_push_workflow[51a13b67…] succeeded in 0.047s:
    {'signal': 'WORKFLOW_STARTED', 'workflow_id': '2f14e112…', …}
tasks.file_processing:_process_project_files - inserted_chunks: 11 / processed_files: 1
Task tasks.file_processing.process_project_files[5a9d043a…] succeeded in 0.219s:
    {'signal': 'processing_success', 'inserted_chunks': 11, 'processed_files': 1,
     'project_id': 11, 'do_reset': 1}
Task tasks.process_workflow.push_after_process_task[2f14e112…] received
tasks.process_workflow:push_after_process_task - chain link 2: indexing project_id=11
</pre>
<p>
اقرا التسلسل: اللانشر بيخلص <b>قبل</b> الحلقة الأولى (هو بس نشرها)، نتيجة الحلقة الأولى شايلة project_id وdo_reset، والحلقة التانية بتبدأ بيهم. لاحظ إن id بتاع <code>push_after_process_task</code> (2f14e112…) هو نفسه الـ workflow_id اللي اللانشر رجّعه — بيأكد إن apply_async() بتديك آخر حلقة.
</p>

<h2>8. باج اتكشف من خلال ده (بره الدمج نفسه)</h2>
<p>أول تشغيلة للسلسلة فشلت في الحلقة التانية:</p>
<pre>
Task failed: Error code: 400 - {'error': {'message':
  "Invalid 'input[10]': input cannot be an empty string." …}}
</pre>
<p>مش مشكلة Celery. <code>ProcessController.process_simpler_splitter</code> كانت بتنتهي بـ:</p>
<pre>
if len(current_chunk) >= 0:      # always true
    chunks.append(Document(page_content=current_chunk.strip(), metadata={}))
</pre>
<div class="warn">
<code>&gt;= 0</code> صحيحة دايماً حتى للنص الفاضي، فأي وقت النص كان بينقسم بالظبط على chunk_size، chunk أخير <b>فاضي</b> كان بيتضاف. اتأكد من ده في الداتابيز نفسها — chunk رقم 11 من 11 كان طوله صفر. النص الفاضي ده بيوصل لـ embedding API واللي بيرفض الباتش كله.
</div>
<p>
الباج ده موجود من الأول (نفس الحاجة في mini-rag) وكان بيخلي فهرسة الـ vectors مستحيلة لملفات زي دي، سواء inline أو على الكيو. اتصلح في <code>ProcessController.py</code>:
</p>
<pre>
if len(current_chunk.strip()) > 0:
    chunks.append(Document(page_content=current_chunk.strip(), metadata={}))
</pre>
<p>
بعد الإصلاح، نفس السلسلة بتوصل لـ <code>{"signal":"insert_into_vectordb_success","inserted_items_count":10}</code>، وبحث RAG على مشروع 12 بيرجّع النص المفهرس.
</p>

<div class="note">
<b>خلاصة سريعة:</b> الـ chain بتخليك تبني workflow معتمد على بعضه على السيرفر بدل ما الكلاينت يعمل polling ويقرر بنفسه امتى يبعت الخطوة الجاية. الحاجتين اللي لازم تفتكرهم دايماً: (1) كل حلقة بتاخد بس اللي الحلقة اللي قبلها رجعته، فأي بيانات لازم تتنقل صريحة جوه الديكشنري، و(2) apply_async() بترجع id آخر حلقة، فده اللي لازم تتابعه للإجابة الحقيقية، مش id اللانشر.
</div>

</body>
</html>