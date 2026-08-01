<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>الـ Concurrency في Celery</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    font-size: 16px;
  }
  h1 { font-size: 22px; color: #f2c94c; border-bottom: 2px solid #444; padding-bottom: 10px; }
  h2 { font-size: 19px; color: #6fcf97; margin-top: 1.8rem; }
  h3 { font-size: 16px; color: #56ccf2; margin-top: 1.3rem; }
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
</style>
</head>
<body>

<h1>الـ Concurrency — تعريف دقيق</h1>

<p>
مش بالظبط "عدد الوركرز". فيه فرق مهم بين ثلاث حاجات بيتلخبطوا في بعض:
</p>

<table>
<tr><th>المصطلح</th><th>معناه</th></tr>
<tr><td><b>Worker</b> (نود/node)</td><td>بروسيس واحد كامل، النتيجة من <code>celery -A celery_app worker</code>. ده اللي بيتصل بالبروكر ويقول "أنا عندي concurrency = N".</td></tr>
<tr><td><b>Concurrency</b></td><td>عدد البروسيسات (أو الخيوط، أو الـ greenlets) <b>جوه نفس الـ worker node</b> اللي بتشتغل بالتوازي على تاسكات مختلفة في نفس اللحظة.</td></tr>
<tr><td><b>Scaling</b></td><td>تشغيل أكتر من worker node بالكامل (زي <code>docker compose up --scale celery_worker=3</code>). كل node ليه concurrency خاص بيه.</td></tr>
</table>

<div class="note">
يعني لو عندك <code>worker_concurrency=2</code> وworker node واحد، أقصى عدد تاسكات شغالة في نفس اللحظة = 2. لو عملت scale لـ3 workers، كل واحد فيهم عنده concurrency=2 → أقصى عدد تاسكات متوازية = 6 (3×2).
</div>

<h2>1. إزاي ده بيشتغل فعلياً — الـ pool</h2>
<p>
الـ concurrency مش رقم مجرد، هو عدد وحدات التنفيذ في <b>pool</b> معين، ونوع الـ pool بيغير المعنى:
</p>
<table>
<tr><th>نوع الـ pool</th><th>وحدة التنفيذ</th><th>مناسب لـ</th></tr>
<tr><td><b>prefork</b> (الافتراضي)</td><td>بروسيسات حقيقية من نظام التشغيل (fork)</td><td>شغل تقيل على الـ CPU، لأن كل بروسيس بيشتغل فعلياً بالتوازي على كور منفصل</td></tr>
<tr><td><b>threads</b></td><td>خيوط (threads) جوه نفس البروسيس</td><td>شغل I/O-bound خفيف، أقل استهلاك رام من prefork</td></tr>
<tr><td><b>gevent / eventlet</b></td><td>greenlets (تعاونية، مش خيوط حقيقية)</td><td>شغل I/O-bound كتير جداً ومتزامن (زي آلاف الطلبات الشبكية)، ممكن concurrency تبقى في المئات</td></tr>
<tr><td><b>solo</b></td><td>بروسيس واحد بس، تاسك واحد في المرة</td><td>تطوير محلي بس (مثلاً على Windows اللي مفيهاش fork)، أبداً للإنتاج</td></tr>
</table>
<p>
في مشروعك، الـ pool الافتراضي (prefork) هو المستخدم، وده بيفسر ليه كل تاسك بيبني الـ DB engine بتاعه من الصفر جوه <code>get_setup_utils()</code> — لأن كل child process معزول تماماً عن التاني، ومش وارثين نفس الاتصال.
</p>

<h2>2. تظبطه على أساس إيه</h2>
<p>مفيش رقم سحري، بيعتمد على طبيعة الشغل:</p>

<h3>لو الشغل CPU-bound</h3>
<p>
يعني الوقت بيتصرف في حسابات فعلية (زي معالجة صور تقيلة، أو تشفير، أو حسابات رياضية). القاعدة العامة: <b>concurrency ≈ عدد أنوية الـ CPU (cores)</b>. لو رفعتها أكتر من كده مع prefork، البروسيسات هتتزاحم على نفس الأنوية وهيحصل context-switching زيادة يبطّئ الأداء بدل ما يحسنه.
</p>

<h3>لو الشغل I/O-bound</h3>
<p>
يعني معظم الوقت التاسك بيستنى — ديسك، قاعدة بيانات، أو نداء شبكة (زي الـ embedding API). ده بالظبط حالة تاسك الـ ingestion في مشروعك. هنا ممكن concurrency <b>تعدي عدد الأنوية بمراحل</b>، لأن وقت ما بروسيس واحد مستني رد من Postgres، بروسيس تاني يقدر يستخدم الـ CPU.
</p>
<div class="warn">
لكن في حالة I/O-bound برضه فيه سقف: كل child process بيفتح <b>اتصال داتابيز خاص بيه</b> (زي ما شفنا في get_setup_utils()). لو رفعت الـ concurrency لرقم كبير من غير ما ترفع <code>max_connections</code> بتاعة Postgres معاه، هتوصل لـ "too many connections" وهتضرب بدل ما تحسن الأداء. القاعدة: ارفع الاتنين مع بعض.
</div>

<h2>3. طريقة عملية للتظبيط</h2>
<ol>
<li><b>حدد نوع الشغل الأساسي</b> للكيو دي — CPU ولا I/O؟</li>
<li><b>ابدأ برقم متحفظ</b> (زي عدد الأنوية، أو نص العدد لو الذاكرة محدودة — كل prefork process بياخد رام كامل مستقل).</li>
<li><b>راقب من خلال Flower أو inspect active</b> — لو الكيو دايماً فاضية والوركر مستني، ممكن ترفع الرقم. لو الوركر مشحون دايماً والكيو متكدسة، ده وقت الـ scale (زيادة عدد الـ worker nodes نفسها) مش بس رفع concurrency.</li>
<li><b>افحص الموارد التانية المشتركة</b> — اتصالات الداتابيز، rate limits بتاعة أي API خارجي (زي embedding provider)، مساحة الرام.</li>
</ol>

<h2>4. متى ترفع concurrency ومتى تعمل scale بدل كده</h2>
<table>
<tr><th>الموقف</th><th>الحل الأنسب</th></tr>
<tr><td>عايز تستغل الأنوية المتاحة على نفس الجهاز بكفاءة أكتر</td><td>ارفع concurrency</td></tr>
<tr><td>عايز تستخدم أكتر من جهاز/نود فعلياً، أو عايز تحمل أعلى من حد واحد جسدياً</td><td>اعمل scale لعدد الـ workers</td></tr>
<tr><td>عايز تفصل كيو معينة (زي file_processing) عن كيو تانية (default) في أداء مستقل</td><td>وركرز منفصلة، كل واحد بـ -Q مخصصة وconcurrency خاص بيه</td></tr>
</table>

<div class="note">
<b>خلاصة:</b> الـ concurrency هو عدد التاسكات اللي بتشتغل بالتوازي <b>جوه نفس الـ worker node الواحد</b>، مش عدد الـ workers نفسهم. تظبيطه بيعتمد على: (1) هل الشغل CPU أو I/O bound، (2) عدد أنوية الجهاز والرام المتاحة، و(3) أي مورد مشترك تاني هيتحمل الضغط (زي اتصالات الداتابيز). في مشروعك، القيمة 2 معقولة لبداية على شغل ingestion الـ I/O-bound، وترفعها تدريجياً وأنت بتراقب استهلاك Postgres connections.
</div>

</body>
</html>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تظبيط الـ Concurrency على 10 Cores</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    font-size: 16px;
  }
  h1 { font-size: 22px; color: #f2c94c; border-bottom: 2px solid #444; padding-bottom: 10px; }
  h2 { font-size: 19px; color: #6fcf97; margin-top: 1.8rem; }
  h3 { font-size: 16px; color: #56ccf2; margin-top: 1.3rem; }
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
</style>
</head>
<body>

<h1>عندك 10 Cores — إزاي تحسب الـ Concurrency</h1>

<h2>1. لو الشغل CPU-bound</h2>
<p>
القاعدة: <b>concurrency ≈ عدد الأنوية</b>، يعني هنا حوالي <code>10</code>. المنطق: كل بروسيس prefork محتاج نواة كاملة عشان يشتغل بالتوازي فعلياً، فأي رقم أعلى من 10 مش هيزود سرعة — بالعكس، البروسيسات هتقعد تتزاحم على نفس الأنوية (context-switching) وده بيكلفك أداء بدل ما يديك.
</p>
<div class="note">
عملياً، بعض الناس بيسيبوا نواة أو اتنين فاضيين للنظام نفسه (OS) وحاجات تانية شغالة على نفس الجهاز (زي الـ API نفسه لو على نفس السيرفر)، فبيحطوا concurrency = 8 أو 9 بدل 10 بالظبط.
</div>

<h2>2. لو الشغل I/O-bound (زي مشروعك)</h2>
<p>
شغلانة الـ ingestion بتاعتك (قراءة ملف، تقسيمه، كتابة في Postgres، نداء embedding API) معظم وقتها بيتصرف في الانتظار — مش في حسابات فعلية على الـ CPU. هنا ممكن تعدي رقم الـ 10 core بمراحل، لأن وقت ما بروسيس مستني رد من الداتابيز، نواة الـ CPU مش مشغولة أصلاً وممكن بروسيس تاني يستخدمها.
</p>
<p>
مبدأ تقريبي شائع (مش قاعدة رياضية دقيقة، لكنه نقطة انطلاق معقولة):
</p>
<pre>
concurrency ≈ cores × (2 to 4)   للشغل I/O-heavy جداً
</pre>
<p>
يعني على 10 cores، ممكن تجرب حاجة زي <code>20</code> أو حتى <code>30</code>، ​​<b>لكن</b> — وده الجزء المهم — الرقم ده مش نهائي، لازم تتأكد إن الموارد التانية المشتركة تقدر تستحمله.

</p>

<h2>3. الاختناق (bottleneck) الحقيقي غالباً مش الـ CPU</h2>
<p>
في حالتك، كل child process بيفتح اتصال Postgres خاص بيه (زي ما شفنا في <code>get_setup_utils()</code>). يبقى قبل ما تحدد concurrency، اسأل:
</p>
<pre>
كام اتصال Postgres مسموح بيهم فعلياً؟ (max_connections)
</pre>
<div class="warn">
لو رفعت concurrency لـ 30 لكن Postgres مظبوط على max_connections=20 (وفيه اتصالات تانية مستخدمة من الـ API نفسه)، هتاخد أخطاء زي <code>too many connections</code>، أو التاسكات هتقعد تستنى اتصال فاضي — يعني الرقم العالي مش هيديك سرعة أكتر، هيديك أخطاء بس.
</div>
<p>القاعدة العملية:</p>
<pre>
concurrency (لكل worker node) × عدد الـ worker nodes  &lt;  Postgres max_connections - هامش أمان
</pre>

<h2>4. مثال عملي كامل على 10 cores</h2>
<table>
<tr><th>الخطوة</th><th>القيمة المقترحة</th><th>السبب</th></tr>
<tr><td>ابدأ بـ</td><td>concurrency = 8</td><td>قريب من عدد الأنوية، تقدر تتأكد إن الأساس شغال كويس قبل ما تزود</td></tr>
<tr><td>راقب عن طريق Flower</td><td>تاب Broker وActive tasks</td><td>لو الكيو دايماً متكدسة والوركر شغال 100% بس مش لاحق، ده مؤشر إنك محتاج ترفع</td></tr>
<tr><td>لو الاختناق واضح إنه I/O</td><td>جرب concurrency = 16-20</td><td>خطوة بخطوة، مش قفزة كبيرة، عشان تلاحظ أي مشكلة اتصالات بدري</td></tr>
<tr><td>راقب Postgres</td><td>عدد الاتصالات المفتوحة فعلياً</td><td>لو قرّب من max_connections، ارفع max_connections الأول قبل ما ترفع concurrency تاني</td></tr>
</table>

<h2>5. نصيحة أخيرة: افصل الشغل الـ CPU عن الشغل الـ I/O</h2>
<p>
لو عندك كيوهات مختلفة بطبيعة شغل مختلفة (زي <code>file_processing</code> اللي فيها I/O كتير، مقابل تاسك تاني حسابي تقيل)، الأفضل تشغلهم على وركرز منفصلة، كل واحد بـ <code>-Q</code> مخصصة وconcurrency مختلف يناسب طبيعة شغله، بدل ما تحط رقم واحد يرضي الكل ومايظبطش حاجة صح.
</p>

<div class="note">
<b>خلاصة سريعة لـ10 cores عندك:</b> لو الشغل CPU-bound صرف، ابدأ من 8-10. لو I/O-bound زي الـ ingestion بتاعك، تقدر تروح لـ 16-20+، بس اربطها دايماً بسقف اتصالات Postgres، وارفع الاتنين مع بعض. الرقم النهائي بتوصله بالتجربة والمراقبة عن طريق Flower، مش بمعادلة ثابتة.
</div>

</body>
</html>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>هل فيه سقف لعدد الوركرز؟</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    background: #1a1a1a;
    color: #e8e6df;
    line-height: 1.9;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
    font-size: 16px;
  }
  h1 { font-size: 22px; color: #f2c94c; border-bottom: 2px solid #444; padding-bottom: 10px; }
  h2 { font-size: 19px; color: #6fcf97; margin-top: 1.8rem; }
  h3 { font-size: 16px; color: #56ccf2; margin-top: 1.3rem; }
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
</style>
</head>
<body>

<h1>هل فيه سقف؟</h1>

<div class="note">
<b>الإجابة القصيرة: Celery نفسه مفيهوش سقف مبرمج (hardcoded limit).</b> تقدر تحط concurrency = 500 أو تعمل scale لـ100 worker node وCelery مش هيرفض. لكن فيه سقوف حقيقية جاية من حاجات تانية حواليه — الجهاز، الشبكة، والخدمات اللي التاسك بيتكلم معاها.
</div>

<p>خليني أقسملك السقوف دي حسب مصدرها:</p>

<h2>1. سقف الذاكرة (RAM) — الأهم غالباً</h2>
<p>
كل child process في الـ prefork pool هو بروسيس كامل من نظام التشغيل، وبياخد نسخة كاملة من الذاكرة (مش threads خفيفة). لو كل بروسيس مننا بياخد مثلاً 200-300 ميجا (بسبب تحميل الموديلز، المكتبات، الاتصالات)، وعندك 16 جيجا رام:
</p>
<pre>
16000 MB / 250 MB لكل process ≈ 64 process كحد أقصى نظري
</pre>
<div class="warn">
لو عديت الرقم ده، النظام هيبدأ يعمل swap (استخدام الديسك بدل الرام) وده أبطأ بمراحل، أو الـ OOM killer هيقتل بروسيسات عشوائي — ده أسوأ سيناريو ممكن يحصل في الإنتاج.
</div>

<h2>2. سقف نظام التشغيل نفسه</h2>
<p>
لينكس بيحط حد أقصى لعدد البروسيسات لكل يوزر (<code>ulimit -u</code>) وعدد الملفات المفتوحة (<code>ulimit -n</code>، مهم لأن كل اتصال شبكة بياخد file descriptor). لو عديت الحدود دي، هتاخد أخطاء زي <code>Resource temporarily unavailable</code> أو <code>Too many open files</code>.
</p>

<h2>3. سقف الموارد اللي التاسك بيعتمد عليها (الأشهر عملياً)</h2>
<table>
<tr><th>المورد</th><th>السقف الحقيقي</th></tr>
<tr><td>Postgres</td><td><code>max_connections</code> — كل child process بيفتح اتصال، فمجموع (concurrency × عدد الوركرز) لازم يكون أقل من الرقم ده مع هامش أمان</td></tr>
<tr><td>Embedding / LLM API</td><td>rate limit بتاع المزود (requests per minute/second) — لو عديته هتاخد 429 Too Many Requests بغض النظر عن قد إيه concurrency عندك</td></tr>
<tr><td>RabbitMQ</td><td>حد أقصى للاتصالات المتزامنة (افتراضياً كبير جداً، نادراً ما تلمسه، لكنه موجود)</td></tr>
<tr><td>الديسك / الشبكة</td><td>bandwidth محدود — لو كل التاسكات بتقرا/تكتب ملفات كبيرة في نفس اللحظة، الديسك نفسه بيبقى الاختناق</td></tr>
</table>
<div class="warn">
غالباً السقف اللي بتوصله فعلياً في مشروع زي بتاعك مش الـ CPU ولا الذاكرة — ده الـ embedding API rate limit أو Postgres connections. رفع concurrency فوق السقف ده مايديكش سرعة أكتر، بيديك أخطاء وretries أكتر بس.
</div>

<h2>4. سقف "العائد المتناقص" (diminishing returns)</h2>
<p>
حتى لو مفيش حاجة بتمنعك تقنياً، فيه نقطة بعدها زيادة الـ concurrency بتبقى مالهاش قيمة أو حتى بتضر:
</p>
<ul>
<li><b>شغل CPU-bound:</b> بعد ما concurrency يعدي عدد الأنوية، context-switching بيبدأ ياكل وقت أكتر من الفايدة.</li>
<li><b>شغل I/O-bound:</b> السقف بيبقى عند سرعة الخدمة التانية (الداتابيز أو الـ API)، مش عند الـ CPU بتاعك — تقدر تفتح 1000 اتصال، لكن لو Postgres مش قادر يخدم أكتر من 50 في نفس اللحظة، الباقي هيقعد ينتظر بس.</li>
</ul>

<h2>5. سقف عدد الـ worker nodes (الـ scaling)</h2>
<p>
نفس الكلام بينطبق على <code>docker compose up --scale celery_worker=N</code>. مفيش سقف من Celery نفسه، لكن فيه سقف من:
</p>
<ul>
<li>عدد الأجهزة/الـ cores المتاحة فعلياً (لو كله على نفس السيرفر)</li>
<li>سقف الموارد المشتركة اللي شرحناها فوق (كل node بيضيف على نفس الحمل على Postgres مثلاً)</li>
<li>في Kubernetes: resource quotas وlimits اللي أنت حاططها على الـ pods</li>
</ul>

<div class="note">
<b>خلاصة:</b> مفيش رقم سحري اسمه "السقف الأقصى لـCelery". السقف الحقيقي هو أضعف حلقة في السلسلة — وده غالباً مش الـ CPU عندك، إنما الموارد اللي التاسك بيعتمد عليها (اتصالات الداتابيز، rate limit الـ API الخارجي، الرام). الطريقة العملية: ارفع الرقم تدريجياً وراقب أضعف حلقة (عادة Postgres connections أو الـ API rate limit) لحد ما تشوفها بتقرب من حدها، وده سقفك الفعلي في اللحظة دي.
</div>

</body>
</html>