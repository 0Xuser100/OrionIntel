<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>RabbitMQ و Redis في Docker</title>
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

<h1>RabbitMQ و Redis في Docker</h1>
<p>
كل الإحداثيات (line references) هنا بتتكلم عن <code>docker/docker-compose.yml</code> بتاعة الـ deploy stack، غير لو قلنا غير كده. الـ local dev stack فيه نفس التلات سيرفيسات بنفس المنطق، والفروق موجودة في آخر جزء.
</p>

<h2>1. اللي اتضاف</h2>
<table>
<tr><th>السيرفيس</th><th>الإيمج</th><th>البورتات</th><th>الدور</th></tr>
<tr><td><code>rabbitmq</code></td><td>rabbitmq:4.1.2-management-alpine</td><td>5672, 15672</td><td>البروكر — شايل الكيو</td></tr>
<tr><td><code>redis</code></td><td>redis:8.0.3-alpine</td><td>6379</td><td>الـ result backend — شايل حالات التاسكات</td></tr>
<tr><td><code>celery_worker</code></td><td>مبني من نفس الـ Dockerfile</td><td>—</td><td>الكونسيومر — بيشغل التاسكات</td></tr>
</table>
<p>
زائد فوليومين (volumes) واتنين <code>depends_on</code> جداد على الـ fastapi.
</p>
<div class="note">
كل الإيمجات مربوطة بتاج (tag) محدد بالظبط. لو استخدمنا <code>redis:latest</code> كان ممكن أي <code>docker compose pull</code> يبدل السيرفر تحت ملف appendonly شغال فعلاً — ده مصدر مفاجآت مش محتاجينها.
</div>

<h2>2. RabbitMQ</h2>
<pre>
  rabbitmq:
    image: rabbitmq:4.1.2-management-alpine
    container_name: orionintel_rabbitmq
    ports:
      - "5672:5672"                            # AMQP — what Celery talks
      - "15672:15672"                          # management web UI
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf
    env_file:
      - ./env/.env.rabbitmq
    networks:
      - backend
    restart: always
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 10s
      retries: 5
      start_period: 30s
</pre>
<ul>
<li><b><span class="en">-management-alpine</span></b> — جزء الـ management بيضيف الـ plugin بتاع الويب UI؛ وجزء الـ alpine بيخلي الإيمج صغير. من غير management مفيش <code>:15672</code>، ومحاولة تفهم كيو عالقة (stuck) هتبقى تخمين.</li>
<li><b>البورتات</b> — <code>5672</code> هو AMQP، البروتوكول الثنائي (binary) اللي Celery/kombu بيتكلموا بيه. <code>15672</code> بس واجهة المتصفح. الاتنين متنشورين للهوست هنا عشان الفحص؛ في deployment حقيقي المفروض تشيل 5672 من ports (الكونتينرات بتوصل لبعض عن طريق شبكة backend من غير ما تنشر حاجة) وتحط الـ UI ورا nginx.</li>
<li><b><code>rabbitmq_data:/var/lib/rabbitmq</code></b> — الحالة الدائمة (persistent state) بتاعة النود: الـ vhost، اليوزرز، تعريفات الكيوهات الدائمة، وأي رسايل لسه ما اتوصلتش. لو فقدت الفوليوم ده، أي شغل اتعمله enqueue ولسه ما اتعالجش بيضيع.</li>
<li><b>الـ healthcheck</b> — <code>rabbitmq-diagnostics ping</code> بيسأل النود الشغال هل هو حي فعلاً — ده أحسن بكتير من فحص بورت TCP عادي، لأن RabbitMQ بيفتح البورت قبل ما يقدر يخدم بوقت كبير. <code>start_period: 30s</code> مهمة: RabbitMQ (Erlang VM + إقلاع الـ plugins) فعلاً بطيء، ومن غير فترة السماح دي الكونتينر هيتوصف إنه unhealthy وهيعمل ريستارت في لوب.</li>
</ul>

<h3>باراميترات <span class="en">.env.rabbitmq</span></h3>
<table>
<tr><th>المتغير</th><th>القيمة</th><th>وظيفته</th></tr>
<tr><td><code>RABBITMQ_DEFAULT_USER</code></td><td>orionintel_user</td><td>بيتعمل في أول إقلاع بس</td></tr>
<tr><td><code>RABBITMQ_DEFAULT_PASS</code></td><td>orionintel_rabbitmq_2222</td><td>نفس الفكرة</td></tr>
<tr><td><code>RABBITMQ_DEFAULT_VHOST</code></td><td>orionintel_vhost</td><td>فيرتشوال هوست: namespace للكيوهات والـ exchanges. كيوهات في vhost معينة مش شايفة كيوهات vhost تاني، والصلاحيات بتتمنح لكل vhost لوحده. ده بيخلي OrionIntel معزول لو البروكر اتشارك يوماً ما.</td></tr>
<tr><td><code>RABBITMQ_MANAGEMENT_ENABLED</code></td><td>true</td><td>توثيق بس — الـ plugin أصلاً متفعل من التاج نفسه.</td></tr>
<tr><td><code>RABBITMQ_AUTH_BACKENDS</code></td><td>rabbit_auth_backend_internal</td><td>بيانات الدخول عايشة جوه RabbitMQ نفسه؛ مفيش LDAP ولا auth خارجي.</td></tr>
<tr><td><code>RABBITMQ_DISK_FREE_LIMIT</code></td><td>2000000000 (2GB)</td><td>تحت الرقم ده RabbitMQ بيمنع البروديوسرز بدل ما يملي الديسك.</td></tr>
</table>
<div class="warn">
<b>أول إقلاع بس.</b> <code>RABBITMQ_DEFAULT_*</code> بتتقرا لما فولدر الداتا يكون فاضي. لو غيرتهم بعدين، <b>مفيش أي أثر</b> — اليوزر القديم لسه موجود في rabbitmq_data، والوركر هيفشل في الـ authentication. عشان تغيرهم فعلاً: <code>docker compose down && docker volume rm docker_rabbitmq_data && docker compose up -d</code>، أو ضيف يوزر جديد عن طريق <code>rabbitmqctl</code>.
</div>
<p>القيم التلاتة دول بيتبنى منهم رابط البروكر:</p>
<pre>
amqp://orionintel_user:orionintel_rabbitmq_2222@rabbitmq:5672/orionintel_vhost
       └── DEFAULT_USER ──┘ └─ DEFAULT_PASS ──┘  └ service ┘   └─ DEFAULT_VHOST ─┘
</pre>
<p>
الهوست هنا هو <b>اسم سيرفيس الـ compose</b> (<code>rabbitmq</code>) والبورت الداخلي (<code>5672</code>) — مش <code>localhost</code> ومش بورت منشور.
</p>

<h2>3. Redis</h2>
<pre>
  redis:
    image: redis:8.0.3-alpine
    container_name: orionintel_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    env_file:
      - ./env/.env.redis
    networks:
      - backend
    restart: always
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a $${REDIS_PASSWORD} ping | grep -q PONG"]
      interval: 10s
      timeout: 10s
      retries: 5
      start_period: 10s
</pre>
<p>
<code>command:</code> هنا بيغيّر الـ entrypoint args الافتراضية بتاعة الإيمج:
</p>
<ul>
<li><b>--appendonly yes</b> — بيسجل كل عملية كتابة في ملف <code>appendonly.aof</code>. نتايج التاسكات بتعيش حتى بعد ريستارت. من غيرها، أي ريستارت بيضيع أي نتيجة شغالة، وأي status query هيرجع PENDING.</li>
<li><b>--requirepass ${REDIS_PASSWORD}</b> — Redis <b>مفيهوش authentication افتراضياً</b>. أي كونتينر تاني على شبكة backend كان ممكن يقرا ويمسح أي نتيجة تاسك. الفلاج ده هو اللي بيخلي النقطتين في أول <code>redis://:password@redis:6379/0</code> ليها معنى.</li>
</ul>

<h3>الفخ الحقيقي الوحيد هنا: <span class="en">${REDIS_PASSWORD}</span> ضد <span class="en">$${REDIS_PASSWORD}</span></h3>
<p>الاتنين شكلهم شبه بعض تقريباً، لكن معناهم مختلف تماماً:</p>
<table>
<tr><th>مكتوبة إزاي</th><th>مين اللي بيوسعها</th><th>بتقرا من فين</th></tr>
<tr><td><code>${REDIS_PASSWORD}</code></td><td>docker compose، وقت ما بيقرا الـ YAML</td><td><code>docker/.env</code>، الملف جنب docker-compose.yml</td></tr>
<tr><td><code>$${REDIS_PASSWORD}</code></td><td>الشل جوه الكونتينر نفسه — compose بيحول $$ لعلامة $ واحدة</td><td>بيئة الكونتينر، يعني <code>env_file: ./env/.env.redis</code></td></tr>
</table>
<p>
فالباسورد لازم يكون موجود في <b>مكانين</b>، ودي مش زيادة عشوائية — إنما بيتقرا من برنامجين مختلفين في وقتين مختلفين:
</p>
<ul>
<li><code>docker/.env</code> ← عشان compose يقدر يحطه بدل <code>${REDIS_PASSWORD}</code> جوه سطر command.</li>
<li><code>docker/env/.env.redis</code> ← عشان healthcheck بتاعة <code>redis-cli -a</code> جوه الكونتينر تقدر تعمل authenticate.</li>
</ul>
<div class="warn">
مدخلات <code>env_file:</code> مش ظاهرة لـ compose interpolation. لو حطيت <code>REDIS_PASSWORD</code> بس في <code>.env.redis</code>، compose هيوسع <code>${REDIS_PASSWORD}</code> لنص فاضي، Redis هيقوم بـ <code>--requirepass ""</code>، وأي كلاينت هياخد <code>NOAUTH Authentication required</code> — مع إن ملف الإعدادات <b>شكله سليم تماماً</b>. عشان كده <code>docker/.env.example</code> موجود وموثق في الهيدر بتاعه.
</div>
<p>
<code>grep -q PONG</code> موجودة لأن <code>redis-cli -a</code> بيطبع تحذير عن تمرير الباسورد في سطر الأوامر؛ فمطابقة PONG بتتجاهل الضوضاء دي.
</p>

<h3>باراميترات <span class="en">.env.redis</span></h3>
<table>
<tr><th>المتغير</th><th>القيمة</th><th>الأثر</th></tr>
<tr><td><code>REDIS_PASSWORD</code></td><td>orionintel_redis_2222</td><td>مستخدم من الـ healthcheck (ولازم يتطابق مع docker/.env)</td></tr>
<tr><td><code>REDIS_APPENDONLY</code></td><td>yes</td><td>توثيق — المفتاح الحقيقي هو <code>--appendonly</code> في سطر الـ command</td></tr>
<tr><td><code>REDIS_MAXMEMORY</code></td><td>512mb</td><td>توثيق — شوف الملاحظة تحت</td></tr>
<tr><td><code>REDIS_MAXMEMORY_POLICY</code></td><td>allkeys-lru</td><td>نفس الفكرة: اطرد المفاتيح الأقل استخداماً مؤخراً (أقدم نتايج التاسكات) لما الذاكرة تمتلي</td></tr>
<tr><td><code>REDIS_PROTECTED_MODE</code></td><td>yes</td><td>نفس الفكرة: ارفض أي اتصال غير محلي لو مفيش باسورد متظبط. شبكة أمان، إحنا أصلاً حاطين باسورد.</td></tr>
</table>
<div class="warn">
<b>إيمج Redis العادي بيتجاهل متغيرات <span class="en">REDIS_*</span> تماماً.</b> على عكس postgres أو rabbitmq، مفيهوش entrypoint script بيقراهم. بس <code>REDIS_PASSWORD</code> ليها أثر حقيقي، وده بس لأن الـ healthcheck بيقراها. الباقي بيوثق النية بس، موروث من الريبو المرجعي. عشان تفعّلهم فعلاً، ضيفهم لسطر command — زي <code>"--maxmemory", "512mb", "--maxmemory-policy", "allkeys-lru"</code> — أو اعمل mount لملف redis.conf زي ما بنعمل مع rabbitmq.conf. سايبينها كده هنا لأن <code>result_expires=3600</code> أصلاً بيحد الداتا.
</div>
<p>رابط الـ result backend:</p>
<pre>
redis://:orionintel_redis_2222@redis:6379/0
        │                      │      │    └── logical DB number (0-15)
        │                      │      └─────── internal port
        │                      └────────────── compose service name
        └───────────────────────────────────── empty username, then the password
</pre>

<h2>4. ملف <span class="en">docker/rabbitmq/rabbitmq.conf</span></h2>
<p>إعدادات على مستوى النود مش عن طريق environment variables. متعمول عليها mount في <code>/etc/rabbitmq/rabbitmq.conf</code>.</p>
<table>
<tr><th>الإعداد</th><th>القيمة</th><th>المعنى</th></tr>
<tr><td><code>vm_memory_high_watermark.relative</code></td><td>0.6</td><td>امنع البروديوسرز لما RabbitMQ يستخدم 60% من رامات الجهاز. بيطبق back-pressure على .delay() بدل ما يتقتل بـ OOM وكيو كامل في الذاكرة.</td></tr>
<tr><td><code>disk_free_limit.absolute</code></td><td>2GB</td><td>نفس الفكرة للديسك.</td></tr>
<tr><td><code>ssl_options.verify</code></td><td>verify_none</td><td>إحنا بنتكلم AMQP عادي جوه شبكة الـ compose. <b>لا تسيب الإعداد ده لو 5672 اتنشر بره يوماً ما</b> — استخدم TLS وverification حقيقي.</td></tr>
<tr><td><code>management.tcp.port</code></td><td>15672</td><td>بورت الويب UI</td></tr>
<tr><td><code>log.console</code> / <code>log.console.level</code></td><td>true / info</td><td>سجل الـ logs على stdout عشان docker compose logs rabbitmq يشتغل. قاعدة الكونتينرز: أبداً متسجلش في ملف جوه الكونتينر.</td></tr>
<tr><td><code>log.file.level</code></td><td>info</td><td>مستوى الـ logger بتاع الملف</td></tr>
</table>

<h2>5. سيرفيس <span class="en">celery_worker</span></h2>
<pre>
  celery_worker:
    build:
      context: ..
      dockerfile: docker/orionintel/Dockerfile
    container_name: orionintel_celery_worker
    volumes:
      - fastapi_data:/app/assets
    networks: [backend]
    restart: always
    depends_on:
      pgvector:  {condition: service_healthy}
      qdrant:    {condition: service_started}
      rabbitmq:  {condition: service_healthy}
      redis:     {condition: service_healthy}
    env_file:
      - ./env/.env.app
    environment:
      - RUN_MIGRATIONS=0
    command: ["celery", "-A", "celery_app", "worker", "--loglevel=INFO", "-Q", "file_processing,default"]
</pre>
<p>
ده بيرد على سؤال "لازم أغير الـ Dockerfile؟" — <b>لأ.</b>
</p>

<h3>إيمج واحد، سيرفيسين</h3>
<p>
الوركر بيشغل <b>نفس الكود</b> بتاع الـ API: نفس celery_app.py، نفس controllers/، نفس models/. لو عملنا Dockerfile تاني كان هيبقى حاجة تانية لازم تظل متزامنة مع الأولى، وأي انحراف (drift) بين الاتنين بينتج بالظبط أسوأ باج ممكن Celery يطلعهولك (تاسك الوركر ما بيعرفش الـ signature بتاعه). عشان كده السيرفيسين بيعملوا build من نفس الـ Dockerfile ويختلفوا بس في الـ command. Docker بيبنيه مرة واحدة ويعيد استخدام الـ layer cache للسيرفيس التاني، فده مجاناً تماماً.
</p>

<h3>الأمر (command) فلاج فلاج</h3>
<table>
<tr><th>الفلاج</th><th>المعنى</th></tr>
<tr><td><code>celery</code></td><td>الـ CLI، أصلاً موجود على PATH</td></tr>
<tr><td><code>-A celery_app</code></td><td>موديول التطبيق: اعمل import لـ celery_app (يعني /app/celery_app.py) ودور على الـ object اسمه celery_app. WORKDIR /app بيخلي ده يشتغل.</td></tr>
<tr><td><code>worker</code></td><td>اشتغل كـ consumer (مقابل beat أو flower أو inspect)</td></tr>
<tr><td><code>--loglevel=INFO</code></td><td>سطر لوج واحد لكل تاسك استلمته وكل تاسك خلص — ده اللي فعلاً عايزه في docker compose logs</td></tr>
<tr><td><code>-Q file_processing,default</code></td><td>استهلك من الكيوهين. file_processing هي الكيو اللي task_routes بيبعتلها المعالجة؛ default هي أي حاجة تانية. لو نسيت كيو هنا تاسكاتها هتتكوم في صمت.</td></tr>
</table>
<div class="note">
الـ concurrency <b>مش</b> بتتمرر في سطر الأمر — بتيجي من <code>CELERY_WORKER_CONCURRENCY</code> في .env.app عن طريق worker_concurrency، فهي قابلة للتعديل من غير ما تلمس ملف الـ compose. لو حطيت <code>--concurrency</code> في الـ CLI هتتجاوز (override) القيمة دي.
</div>

<h3><span class="en">RUN_MIGRATIONS=0</span> والـ entrypoint</h3>
<p>
الـ ENTRYPOINT بتاع الإيمج هو <code>docker/orionintel/entrypoint.sh</code>، واللي بيشغل <code>alembic upgrade head</code> قبل ما يسلّم للـ CMD. مع كونتينرين من نفس الإيمج، <b>الاتنين</b> كانوا هيعملوا migration في نفس اللحظة ويحصل تسابق (race) على صف alembic_version. فالـ entrypoint دلوقتي محمي:
</p>
<pre>
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "==> Running database migrations (alembic upgrade head)..."
  cd /app/models/db_schemes/minirag/
  alembic upgrade head
  cd /app
else
  echo "==> RUN_MIGRATIONS=0 — skipping migrations (another service owns them)."
fi

exec "$@"
</pre>
<p>
الافتراضي <code>1</code> بيخلي سلوك سيرفيس fastapi زي ما هو؛ الوركر بيحط <code>0</code>. الـ <code>exec "$@"</code> في الآخر هو اللي بيخلي celery (أو uvicorn) يبقى PID 1 فيستقبل <code>SIGTERM</code> بتاعة Docker — بالنسبة لـ Celery ده بيفعّل <b>warm shutdown</b>: يوقف استقبال رسايل جديدة، يخلص التاسك الحالي، وبعدين يخرج. من غير <code>exec</code>، الـ bash بتفضل PID 1، بتبلع الإشارة، و<code>docker compose stop</code> بيقتل الوركر في نص التاسك بعد فترة السماح (10 ثواني).
</p>

<h3>الفوليوم المشترك — أسهل حاجة تغلط فيها</h3>
<pre>
volumes:
  - fastapi_data:/app/assets     # the SAME named volume as the fastapi service
</pre>
<p>
<code>POST /upload</code> بيكتب الملف جوه كونتينر الـ <b>API</b>، في <code>assets/files/&lt;project_id&gt;/&lt;name&gt;</code>. التاسك بعدين بيرجع يقراه بـ <code>ProcessController.get_file_content()</code> من جوه كونتينر <b>الوركر</b>. كونتينرين، فايل سيستمين — إلا لو الاتنين عاملين mount لنفس الفوليوم.
</p>
<div class="warn">
لو غلطت هنا هتشوف عرض محيّر: الرفع بيرجع نجاح، التاسك بيشتغل، واللوج بيقول <code>Error while processing file: ...</code> لأن <code>get_file_loader()</code> ملقاش المسار ده أصلاً.
</div>

<h3>شروط <span class="en">depends_on</span></h3>
<p>
<code>service_healthy</code> لـ pgvector/rabbitmq/redis معناها إن compose بينتظر الـ healthcheck تنجح، مش بس إن الكونتينر يبدأ. من غيرها الوركر بيقوم الأول، بيفشل في الوصول للبروكر، وحتى مع <code>broker_connection_retry_on_startup=True</code>، هتاخد دقيقة كاملة من لوجات reconnect مقلقة على كل <code>up</code>. الـ <code>qdrant</code> مفيهوش healthcheck في الـ stack ده، فبياخد <code>service_started</code> بس.
</p>

<h2>6. كل باسورد عايش فين</h2>
<p>لو غيرت أي credential لازم تغيره في <b>كل</b> صف من المجموعة:</p>
<table>
<tr><th>القيمة</th><th>الملفات</th></tr>
<tr><td>يوزر/باسورد/vhost بتاع RabbitMQ</td><td>.env.rabbitmq <b>و</b> جوه CELERY_BROKER_URL في .env.app (وsrc/.env للتشغيل من غير Docker)</td></tr>
<tr><td>باسورد Redis</td><td>docker/.env <b>و</b> .env.redis <b>و</b> جوه CELERY_RESULT_BACKEND في .env.app (+ src/.env)</td></tr>
<tr><td>يوزر/باسورد/داتابيز Postgres</td><td>.env.postgres، .env.app، .env.postgres-exporter، alembic.ini</td></tr>
</table>
<p>
<code>docker/.gitignore</code> بيمنع أي <code>.env*</code> حقيقي من إنه يتسجل في git، وبيسجل بس نسخ <code>.env.example.*</code>؛ سطر <code>/.env</code> الجديد بيغطي ملف الـ compose نفسه.
</p>

<h2>7. الإعداد لأول مرة</h2>
<pre>
cd docker/env
cp .env.example.rabbitmq .env.rabbitmq
cp .env.example.redis    .env.redis
cd ..
cp .env.example .env            # <- the compose-level file, easy to miss
</pre>
<p>
وبعدين تأكد إن قسم <code>CELERY_*</code> في آخر <code>env/.env.app</code> متطابق مع الـ credentials دي.
</p>

<h2>8. الـ local dev stack</h2>
<p>
<code>docker/local/docker-compose.yml</code> استلم نفس التلات سيرفيسات، بثلاث فروق:
</p>
<ol>
<li>الـ credentials جايه من <code>docker/local/.env</code> (عن طريق <code>environment:</code> + <code>${...}</code>) بدل env_file لكل سيرفيس — ده النمط اللي الـ stack ده أصلاً مستخدمه.</li>
<li>الوركر بيعمل build من <code>src/Dockerfile</code>، واللي <b>مفيهوش</b> entrypoint، فمحتاجش فلاج RUN_MIGRATIONS (الـ migrations مش أوتوماتيك في الـ local stack أصلاً).</li>
<li>الفوليوم المشترك هو <code>app_files:/app/assets/files</code>، متطابق مع نقطة الـ mount بتاعة سيرفيس app في الـ stack ده.</li>
</ol>

<div class="note">
<b>خلاصة سريعة:</b> الجزء ده كله عن التفاصيل العملية اللي بتخلي التلات سيرفيسات دول يشتغلوا مع بعض فعلاً — تثبيت التاجات، الفرق الدقيق بين ${VAR} و$${VAR} في compose، ليه الوركر بيستخدم نفس الـ Dockerfile بتاع الـ API، وأهمية الفوليوم المشترك والـ healthcheck conditions. أغلب الأعطال اللي هتقابلها في الحقيقة سببها حاجة من دول، مش خطأ في منطق الكود نفسه.
</div>

</body>
</html>