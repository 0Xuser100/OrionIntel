<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Celery Beat — التنظيف المجدول</title>
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

<h1>Celery Beat — التنظيف المجدول</h1>

<h2>1. الـ Beat إيه، وإيه اللي هو مش هو</h2>
<div class="note">
<b>Beat هو بروديوسر (publisher) شغال على ساعة (timer).</b> بيقرا <code>beat_schedule</code>، ولما دور أي مدخل (entry) يحين، بيحط رسالة على البروكر — بالظبط زي اللي <code>.delay()</code> بتعمله، بس بيتفعّل من الساعة مش من ريكوست HTTP. وبعدين بيرجع ينام.
</div>
<div class="warn">
<b>Beat مابينفذش أي حاجة بنفسه.</b> وركر بيستهلك من الكيو دي هو اللي بيعمل الشغل. لو شغلت beat من غير أي وركر، الرسايل هتتكوم في RabbitMQ من غير معالجة، ومن غير أي خطأ يظهر.
</div>
<pre>
 celery beat ──publishes on schedule──▶ RabbitMQ (default) ──▶ celery worker ──▶ Postgres
  (a clock)                                                     (does the work)     DELETE
</pre>
<p>
هو أشبه بـ cron، بس الشغلانة بتشتغل جوه التطبيق بتاعك بنفس الكود ونفس الإعدادات ونفس جلسة الداتابيز — مفيش crontab منفصل، مفيش إيمج منفصل.
</p>

<h2>2. ليه محتاجينه هنا</h2>
<p>
جدول <code>celery_task_executions</code> بيكبر بس (only grows). كل ملف اتعالج بيضيف صف، والأربع فهارس بتكبر معاه. لو سبتناه من غير تنظيف هيبقى أكبر جدول في الداتابيز من غير أي قيمة في الصفوف القديمة.
</p>

<h2>3. الجدولة — <span class="en">src/celery_app.py</span></h2>
<pre>
beat_schedule={
    "cleanup-old-task-records": {
        "task": "tasks.maintenance.clean_celery_executions_table",
        "schedule": float(settings.CELERY_BEAT_CLEANUP_INTERVAL),
        "args": (),
    },
},
timezone="UTC",
</pre>
<table>
<tr><th>المفتاح</th><th>المعنى</th></tr>
<tr><td>"cleanup-old-task-records"</td><td>اسم المدخل. Beat بيتتبع آخر وقت تشغيل لكل اسم، فتغيير اسم المدخل بيخليه يشتغل فوراً مرة واحدة.</td></tr>
<tr><td>task</td><td>اسم التاسك <b>المسجل (registered)</b> كنص، مش الفانكشن نفسها. Beat مش محتاج يعمل import للتاسك — لكن أي خطأ إملائي هنا بيفشل بس وقت التشغيل الفعلي، كـ Received unregistered task.</td></tr>
<tr><td>schedule</td><td>رقم عادي = ثواني بين كل تشغيلة. ممكن كمان يكون timedelta أو crontab(hour=3, minute=0) لـ"كل يوم الساعة 3 الصبح".</td></tr>
<tr><td>args</td><td>آرجيومنتس positional. فاضية هنا.</td></tr>
<tr><td>timezone="UTC"</td><td>Beat بيحسب الجدولة بناءً على المنطقة الزمنية دي. خليها UTC عشان أي كونتينر بمنطقة زمنية مختلفة مايزحزحش الجدولة — ده مهم جداً مع مداخل crontab().</td></tr>
</table>
<p>
الفاصل الزمني جاي من <code>.env</code> عشان يقدر ينزل لأغراض العرض التوضيحي من غير ما تلمس الكود.
</p>

<h2>4. التاسك — <span class="en">src/tasks/maintenance.py</span></h2>
<pre>
@celery_app.task(
    bind=True,
    name="tasks.maintenance.clean_celery_executions_table",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def clean_celery_executions_table(self):
    return asyncio.run(_clean_celery_executions_table(self))
</pre>
<p>الجسم:</p>
<pre>
deleted = await idempotency_manager.cleanup_old_tasks(
    time_retention=settings.CELERY_TASK_RECORD_RETENTION
)
logger.info(f"cleanup: deleted {deleted} task record(s) older than "
            f"{settings.CELERY_TASK_RECORD_RETENTION}s")
return {"deleted": deleted}
</pre>
<p>والـ SQL:</p>
<pre>
cutoff_time = _utcnow() - timedelta(seconds=time_retention)
stmt = delete(CeleryTaskExecution).where(CeleryTaskExecution.created_at < cutoff_time)
</pre>
<p>
<code>ixz_task_execution_created_at</code> موجود بالظبط عشان الشرط ده.
</p>
<div class="note">
عدم كفاءة واحدة موروثة من الريبو المرجعي: التاسك ده بينادي <code>get_setup_utils()</code>، واللي بيبني عملاء الـ embedding والـ generation والـ vector-DB كمان — ولا واحد فيهم محتاجه DELETE بسيط. على فاصل ساعة ده مجرد ضوضاء بسيطة؛ لو قصرت الفاصل كتير، اعمل helper منفصل للـ setup بيبني الداتابيز بس.
</div>

<h2>5. الرقمين، وليه القيم الافتراضية عندنا مختلفة عن الريبو المرجعي</h2>
<table>
<tr><th>متغير البيئة</th><th>عندنا</th><th>الريبو المرجعي</th><th>بيتحكم في إيه</th></tr>
<tr><td>CELERY_BEAT_CLEANUP_INTERVAL</td><td>3600</td><td>10 (hardcoded)</td><td>كل قد إيه التنظيف بيشتغل</td></tr>
<tr><td>CELERY_TASK_RECORD_RETENTION</td><td>86400</td><td>5 (hardcoded)</td><td>الصف لازم يكون عمره قد إيه عشان يتمسح</td></tr>
</table>
<div class="warn">
الريبو المرجعي بيمسح صفوف عمرها <b>5 ثواني، كل 10 ثواني</b>. ده إعداد تعليمي (teaching setting) — بيخلي التنظيف يظهر فوراً — لكن ده كمان معناه إن سجل الـ idempotency فاضي تقريباً طول الوقت، فالحماية اللي شرحناها في الدرس السابق أبداً ما بتشتغلش فعلياً. فترة الاحتفاظ (retention) <b>هي</b> عمر ضمانتك للـ idempotency.
</div>
<p>
عندنا الافتراضي هو تنظيف كل ساعة مع الاحتفاظ بـ24 ساعة من التاريخ، والاتنين متغيرات بيئة.
</p>
<p><b>عشان تشوفه شغال</b>، حط دول في .env.app وأعد تشغيل celery_beat وcelery_worker:</p>
<pre>
CELERY_BEAT_CLEANUP_INTERVAL=10
CELERY_TASK_RECORD_RETENTION=30
</pre>
<p>وارجعهم زي ما كانوا بعد كده.</p>

<h2>6. الكونتينر</h2>
<pre>
  celery_beat:
    build:
      context: ..
      dockerfile: docker/orionintel/Dockerfile
    container_name: orionintel_celery_beat
    volumes:
      - celery_beat_data:/app/celerybeat
    depends_on:
      pgvector:  {condition: service_healthy}
      rabbitmq:  {condition: service_healthy}
      redis:     {condition: service_healthy}
    env_file:
      - ./env/.env.app
    environment:
      - RUN_MIGRATIONS=0
    command: ["celery", "-A", "celery_app", "beat", "--loglevel=INFO",
              "--schedule=/app/celerybeat/celerybeat-schedule"]
</pre>
<div class="warn">
<b>شغّل كونتينر <span class="en">beat</span> واحد بالظبط.</b> اتنين هينشروا كل تيك مرتين — beat مفيهوش قفل (lock) ولا leader election. عشان كده beat سيرفيس منفصل مش فلاج على الوركر: <code>docker compose up --scale celery_worker=3</code> عادي، لكن عمل scale لـ beat لأ.
</div>
<p>
<b>RUN_MIGRATIONS=0</b> — نفس الإيمج، نفس الـ entrypoint، فـ beat كان هيشغل alembic upgrade head جنب fastapi لولا الفلاج ده.
</p>
<p>
<b>--schedule=/app/celerybeat/celerybeat-schedule</b> — beat بيسجل "امتى آخر مرة شغلت كل مدخل" في ملف Python اسمه <code>shelve</code>. مساره الافتراضي هو <code>./celerybeat-schedule</code>، جوه الطبقة القابلة للكتابة بتاعة الكونتينر، واللي بتتمسح مع كل إعادة إنشاء (recreate)؛ وبعدين أي ريستارت بيعيد إطلاق كل حاجة كأنها مستحقة (due). توجيهه لفوليوم celery_beat_data بيخلي الذاكرة دي تعيش.
</p>
<p>الفوليوم ده كمان محتاج نقطة الـ mount بتاعته تكون موجودة في الإيمج، مملوكة لليوزر بتاع التطبيق:</p>
<pre>
RUN mkdir -p /app/assets/files /app/celerybeat \
    && chmod +x /entrypoint.sh \
    && chown -R appuser:appuser /app
</pre>
<div class="note">
Docker بينسخ ملكية الفولدر لفوليوم <b>جديد</b>. لو <code>/app/celerybeat</code> مش موجود في الإيمج، الفوليوم بيتعمل بملكية root، وbeat — الشغال كـ appuser — مايقدرش يكتب ملف الجدولة بتاعه.
</div>
<p>
<code>shelve</code> بيكتب واحد من <code>celerybeat-schedule.bak</code> / <code>.dat</code> / <code>.dir</code> حسب backend الـ dbm بتاع البلاتفورم، عشان كده <code>src/.gitignore</code> بيسرد التلاتة مع <code>celerybeat-schedule</code>.
</p>

<h2>7. تأكيد فعلي</h2>
<p>Beat بفاصل مؤقت 10 ثواني:</p>
<pre>
[08:34:50: INFO/MainProcess] beat: Starting...
[08:35:00: INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (tasks.maintenance.clean_celery_executions_table)
[08:35:10: INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (…)
[08:35:20: INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (…)
[08:35:30: INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (…)
</pre>
<p>
أول تشغيلة كانت عند +10 ثانية، مش وقت الإقلاع — <b>لأن الديمو ده استخدم ملف جدولة جديد تماماً</b>. من غير أي <code>last_run_at</code> مخزن، beat بيهيّئه على "دلوقتي" والمدخل بيبقى مستحق بعد فاصل واحد كامل.
</p>
<div class="note">
ده <b>مش</b> اللي بيحصل في ريستارت عادي، والفرق ده هو بيت القصيد كله من حفظ الملف. سيرفيس celery_beat الحقيقي، لما اتعمله ريستارت الساعة 11:01:27 ضد ملف جدولة مكتوب الساعة 08:26، اشتغل <b>فوراً</b>:
</div>
<pre>
[2026-07-30 11:01:27,883: INFO/MainProcess] beat: Starting...
[2026-07-30 11:01:27,955: INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (…)
[2026-07-30 12:01:29,045: INFO/MainProcess] Scheduler: Sending due task cleanup-old-task-records (…)
</pre>
<p>
الـ <code>last_run_at</code> المخزن كان عدى عليه أكتر من 3600 ثانية، فالمدخل كان أصلاً متأخر (overdue) وbeat شغله فوراً — وبعدين استقر على الإيقاع الساعي. يعني:
</p>
<ul>
<li><b>ملف جدولة جديد</b> ← أول تشغيلة بعد فاصل كامل من الإقلاع</li>
<li><b>ملف محفوظ، المدخل متأخر</b> ← يشتغل فوراً، وبعدين على الإيقاع</li>
<li><b>ملف محفوظ، المدخل لسه ما استحقش</b> ← بينتظر الباقي، وده اللي بيمنع لوب ريستارت من إعادة إطلاق كل حاجة</li>
</ul>
<p>الوركر بياخد كل واحدة:</p>
<pre>
Task tasks.maintenance.clean_celery_executions_table[1a8e6d3f…] received
tasks.maintenance:_clean_celery_executions_table - cleanup: deleted 0 task record(s) older than 86400s
Task tasks.maintenance.clean_celery_executions_table[1a8e6d3f…] succeeded in 0.164s: {'deleted': 0}
</pre>
<p>
<code>deleted 0</code> صحيحة — الاحتفاظ كان لسه 86400 ثانية ومفيش صف عمره يوم. الـ DELETE نفسه اتأكد منه لوحده مع <code>retention=1</code>:
</p>
<pre>
rows before: 2
cleanup_old_tasks(retention=1) deleted 2 row(s)
rows after:  0
</pre>
<p>وملف الجدولة فعلاً موجود جوه الفوليوم، مملوك لليوزر بتاع التطبيق:</p>
<pre>
$ docker compose exec celery_beat ls -la /app/celerybeat/
-rw-r--r-- 1 appuser appuser 16384 Jul 30 12:21 celerybeat-schedule
</pre>
<p><code>appuser appuser</code>، مش <code>root root</code>.</p>

<h2>8. حل المشاكل</h2>
<table>
<tr><th>العرض</th><th>السبب</th></tr>
<tr><td>beat بيسجل "Sending due task"، بس مفيش حاجة بتشتغل</td><td>مفيش وركر بيستهلك من كيو default — تأكد من -Q</td></tr>
<tr><td>Received unregistered task وقت التشغيل الفعلي</td><td>نص task في beat_schedule مش متطابق مع name= في @celery_app.task</td></tr>
<tr><td>كل حاجة بتشتغل تاني على كل ريستارت</td><td>ملف الجدولة مش persisted — تأكد من --schedule والفوليوم</td></tr>
<tr><td>PermissionError: /app/celerybeat/...</td><td>الفوليوم مملوك لـ root؛ نقطة الـ mount ما كانتش في الإيمج</td></tr>
<tr><td>كل تيك بيشتغل مرتين</td><td>أكتر من كونتينر beat واحد شغال</td></tr>
<tr><td>التنظيف بيمسح صفوف كنت محتاجها</td><td>CELERY_TASK_RECORD_RETENTION قصير جداً — ده بيحدد ضمانة الـ idempotency كمان</td></tr>
</table>

<div class="note">
<b>خلاصة سريعة:</b> Beat بس "ساعة" بتنشر رسايل مجدولة — التنفيذ الفعلي مسؤولية الوركر زي أي تاسك عادي. أكتر نقطتين خطر هنا: (1) أبداً متعملش scale لأكتر من beat واحد، و(2) لازم ملف الجدولة يكون persisted في فوليوم حقيقي وإلا هتشوف "إعادة إطلاق كل حاجة" على كل ريستارت.
</div>

</body>
</html>

<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>الفرق بين CLEANUP_INTERVAL وRECORD_RETENTION</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 780px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    font-size: 16px;
  }
  h1 { font-size: 22px; color: #f2c94c; border-bottom: 2px solid #444; padding-bottom: 10px; }
  h2 { font-size: 18px; color: #6fcf97; margin-top: 1.8rem; }
  p { margin: 0.8rem 0; text-align: right; }
  .note {
    background: #262626;
    border-right: 4px solid #f2c94c;
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
    line-height: 1.6;
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
</style>
</head>
<body>

<h1>الفرق بين المتغيرين</h1>

<p>
دول مش نفس الحاجة خالص — واحد بيجاوب "امتى؟" والتاني بيجاوب "أمسح إيه؟".
</p>

<table>
<tr><th>المتغير</th><th>بيجاوب على سؤال</th><th>القيمة عندنا</th></tr>
<tr><td><code>CELERY_BEAT_CLEANUP_INTERVAL</code></td><td>Beat بيبعت رسالة "نظّف" كل قد إيه؟</td><td>3600 ثانية (كل ساعة)</td></tr>
<tr><td><code>CELERY_TASK_RECORD_RETENTION</code></td><td>الصف لازم يكون عمره قد إيه عشان يتحسب "قديم" ويتمسح؟</td><td>86400 ثانية (24 ساعة)</td></tr>
</table>

<h2>المتغير الأول — كل قد إيه Beat بيشتغل</h2>
<p>
ده مدخل في جدولة <code>beat_schedule</code>. Beat بيقرا الرقم ده وبينشر رسالة "شغّل التنظيف" كل ما الفاصل ده يعدي:
</p>
<pre>
"schedule": float(settings.CELERY_BEAT_CLEANUP_INTERVAL),  # 3600
</pre>
<p>
يعني بـ3600، Beat هيبعت رسالة تنظيف كل ساعة بالظبط — سواء فيه صفوف تستاهل تتمسح ولا لأ. ده بس تحديد <b>تكرار التشغيل</b>.
</p>

<h2>المتغير التاني — امتى الصف يستاهل يتمسح</h2>
<p>
لما التنظيف يشتغل فعلاً (كل ساعة زي ما قلنا)، هو بيسأل: "أي صف أقدم من الرقم ده بالثواني، امسحه":
</p>
<pre>
cutoff_time = _utcnow() - timedelta(seconds=time_retention)  # 86400
stmt = delete(CeleryTaskExecution).where(CeleryTaskExecution.created_at < cutoff_time)
</pre>
<p>
يعني بـ86400، أي صف عمره أكتر من 24 ساعة هيتمسح. الصفوف اللي عمرها أقل من كده — حتى لو التنظيف اشتغل عليها — هتفضل موجودة.
</p>

<div class="note">
<b>تخيلها كده:</b> <code>CLEANUP_INTERVAL</code> هي "كل قد إيه اطلع أفحص الثلاجة"، و<code>RETENTION</code> هي "إرمي أي حاجة عمرها أكتر من كام يوم". لو فحصت الثلاجة كل ساعة (interval) بس بترمي بس اللي عمره أسبوع (retention)، غالباً هتلاقي "0 items deleted" في أغلب الفحصات — وده بالظبط اللي بتشوفه في اللوج: <code>deleted 0 task record(s) older than 86400s</code>.
</div>

<h2>ليه الفصل بين الاتنين مهم</h2>
<p>
الـ retention مش مجرد "تنضيف مساحة" — هي <b>عمر ضمانة الـ idempotency</b> بتاعتك. طول ما الصف موجود، الحماية من إعادة توصيل نفس التاسك (redelivery) شغالة عليه. لو الـ retention قصير جداً، ممكن تمسح صف لسه محتاج يمنع تكرار حقيقي.
</p>
<p>
فلو قللت <code>CLEANUP_INTERVAL</code> بس (خليه يشتغل كل 10 ثواني مثلاً) من غير ما تلمس الـ retention، هتشوف تنظيف بيشتغل كتير لكن بيمسح صفر أغلب الوقت — لأن أي صف لسه عمره أقل من 24 ساعة. عشان "تشوف مسح فعلي" لازم تقلل الاتنين مع بعض:
</p>
<pre>
CELERY_BEAT_CLEANUP_INTERVAL=10
CELERY_TASK_RECORD_RETENTION=30
</pre>

</body>
</html>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>امتى Redis بيتمسح؟</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 780px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    font-size: 16px;
  }
  h1 { font-size: 22px; color: #f2c94c; border-bottom: 2px solid #444; padding-bottom: 10px; }
  h2 { font-size: 18px; color: #6fcf97; margin-top: 1.8rem; }
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
    line-height: 1.6;
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
</style>
</head>
<body>

<h1>امتى Redis بيتمسح؟</h1>

<p>
ده نظام <b>تالت مختلف تماماً</b> عن الاتنين اللي اتكلمنا عنهم قبل كده. متلخبطش بين التلاتة:
</p>

<table>
<tr><th>النظام</th><th>القيمة</th><th>بيتحكم فيه إيه</th></tr>
<tr><td>Beat cleanup interval</td><td>3600 ثانية</td><td>كل قد إيه Beat بيبعت رسالة "نظّف"</td></tr>
<tr><td>Postgres retention</td><td>86400 ثانية</td><td>عمر صف celery_task_executions قبل ما يتمسح</td></tr>
<tr><td><b>Redis result_expires</b></td><td><b>3600 ثانية</b></td><td>عمر نتيجة التاسك (state + result) في Redis قبل ما تتمسح</td></tr>
</table>

<h2>مين بيتحكم فيه</h2>
<pre>
result_expires = 3600
</pre>
<p>
ده إعداد من إعدادات Celery نفسها (<code>conf.update(...)</code> في <code>celery_app.py</code>)، مش من عندك في <code>.env.app</code> زي الاتنين التانيين. القيمة الافتراضية عندنا ساعة واحدة.
</p>

<h2>إزاي بيشتغل — مفيش Beat خالص هنا</h2>
<div class="note">
الفرق الجوهري: مسح Postgres بيحصل عن طريق <b>تاسك بيشتغله Beat</b> — يعني نظام بيتحرك بإرادته (active) وبينفذ DELETE فعلي. لكن Redis بيمسح نفسه <b>بنفسه</b> عن طريق آلية <code>TTL</code> (Time To Live) المدمجة فيه أصلاً — لما Celery بيكتب نتيجة تاسك، بيحطها بمفتاح (key) وعليه TTL يساوي result_expires. لما الوقت ده يخلص، Redis بيمسح المفتاح تلقائياً من غير أي تدخل من Celery ولا Beat ولا أي تاسك بتاعنا.
</div>
<p>
يعني: <code>celery-task-meta-&lt;task_id&gt;</code> بيتحط في Redis وقت ما التاسك يخلص، وبعد ساعة بالظبط من وقت الكتابة، Redis بيشيله لوحده.
</p>

<h2>الأثر العملي</h2>
<div class="warn">
لو حد سأل عن حالة تاسك بعد ما ساعة تعدي من وقت ما خلص، <code>AsyncResult</code> هيرجع <code>PENDING</code> — مش لأن التاسك اختفى أو فشل، لكن لأن نتيجته انتهت من Redis. وده بالظبط نفس الغموض اللي اتكلمنا عليه قبل كده: PENDING لتاسك خلص فعلاً ونتيجته راحت، مش قابل للتفريق عن PENDING لتاسك أصلاً ما اتبعتش.
</div>

<h2>خلاصة الفرق التلاتي</h2>
<ul>
<li><b>Beat interval</b> — تكرار تشغيل عملية تنظيف Postgres (فعل بيحصل بإرادة)</li>
<li><b>Postgres retention</b> — عمر سجل الـ idempotency الدائم، وهو اللي بيحمي من تكرار التنفيذ</li>
<li><b>Redis result_expires</b> — عمر "إجابة السؤال: خلص ولا لأ؟" اللي الكلاينت بيسأل عنها، وده بيتمسح تلقائياً بدون أي تاسك أو Beat</li>
</ul>

</body>
</html>