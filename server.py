import json, os, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from app import corporate, db, executive, investor, investment_proof, contract_builder, deal_room, portfolio_control, capital_optimizer
from app.analytics import commercial, state
from app.auth import authenticate, auth, body, issue_session, seed_demo_accounts, token_hash
from app.core import audit, notify, promote_waitlist, setv, sval
from app.demo import DEMO_STEPS, reset_demo, run_demo_step
from app.community_commands import handle_command as handle_community_command
from app.learning_commands import handle_command as handle_learning_command
from app.participant_commands import handle_command as handle_participant_command
from app.programme_commands import handle_command as handle_programme_command
from app.operations_commands import handle_command as handle_operations_command
from app.partner_commands import handle_command as handle_partner_command
from app.editorial_commands import handle_command as handle_editorial_command
from app.demo_commands import handle_command as handle_demo_command
from app.investment_commands import handle_command as handle_investment_command
from app.deal_commands import handle_command as handle_deal_command
from app.capital_execution_commands import handle_command as handle_capital_execution_command; from app.intervention_commands import handle_command as handle_intervention_command; from app.reallocation_commands import handle_command as handle_reallocation_command
from app.strategic_reads import read as read_strategic_projection
ROOT=os.path.join(os.path.dirname(__file__),"public"); LOCK=threading.RLock()
def conn(): return db.connect()
def init():
 with LOCK:
  c=conn()
  db.migrate(c)
  if not db.demo_seed_enabled():
   c.close(); return
  # Deterministic demo seed. Production PostgreSQL requires explicit PROMOMED_SEED_DEMO=true.
  seed_demo_accounts(c)
  defaults={"session_time":"11:00","session_room":"Лекторий","live_state":"scheduled","occupied":"116","capacity":"120","phase":"before","change_seq":"0","gift_issued":"0","demo_step":"-1","demo_run":"0"}
  for k,v in defaults.items(): c.execute("INSERT OR IGNORE INTO state(k,v) VALUES(?,?)",(k,v))
  c.execute("INSERT OR IGNORE INTO cms(id,status,version,updated) VALUES('A-014','medical_review',1,?)",(int(time.time()),))
  c.execute("INSERT OR IGNORE INTO placements(id,name,status,leads,ts) VALUES(1,'Наука повседневности','contracted',0,?)",(int(time.time()),))
  program=[
   ("P01","09:00","09:45","Главная сцена","Открытие","keynote","Человек. Наука. Жизнь.","все",600,1,1,"Промомед"),
   ("P02","10:00","10:45","Наука","Метаболическое здоровье","lecture","Метаболическое здоровье: что меняется сегодня","участники",180,1,1,"Промомед"),
   ("P03","10:00","10:40","Beauty Lab","Красота и молодость","practice","Кожа и healthy ageing: диагностика привычек","участники",36,0,1,"Beauty partner · demo"),
   ("P04","10:15","11:00","Business Club","Бизнес","roundtable","Health economy: бренды вокруг человека","бренды / клиенты",90,1,1,"Partner council · demo"),
   ("P05","11:00","11:45","Наука","Научная грамотность","lecture","Как читать исследования без ложной уверенности","все",120,1,1,"Промомед"),
   ("P06","11:00","11:30","Beauty Lab","Красота и молодость","appointment","Skin consultation experience","по записи",12,0,0,"Beauty partner · demo"),
   ("P07","12:00","12:50","Главная сцена","Долголетие","panel","Молодость как система: сон, движение, питание, профилактика","все",600,1,1,"Промомед + partners"),
   ("P08","12:15","13:00","Partner Studio","Питание","workshop","Еда без крайностей: практический разбор","по записи",40,1,1,"Nutrition partner · demo"),
   ("P09","13:10","13:50","Recovery Lab","Сон и восстановление","practice","Сон и восстановление: персональный ритуал","по записи",32,0,1,"Sleep partner · demo"),
   ("P10","14:00","14:50","Business Club","Клиенты","roundtable","Клиентский опыт в health & wellness","клиенты / бренды",80,1,1,"Промомед"),
   ("P11","14:20","14:40","Клуб","Networking","meeting","Meaningful Match · 20 минут","участники / спикеры",24,0,0,"СОСТОЯНИЕ"),
   ("P12","15:00","15:45","Beauty Lab","Красота и молодость","masterclass","Beauty-tech: процедуры, данные и ожидания","по записи",36,1,1,"Beauty partner · demo"),
   ("P13","15:00","15:45","Наука","Неврология","lecture","Энергия, внимание и восстановление","все",160,1,1,"Промомед"),
   ("P14","16:00","16:45","Partner Studio","Движение","workshop","Движение каждый день: минимальная работающая система","по записи",45,1,1,"Fitness partner · demo"),
   ("P15","16:00","16:50","Business Club","Партнёрства","panel","Как брендам создавать health value без рекламного шума","бренды / партнёры",100,1,1,"Промомед + partners"),
   ("P16","17:00","17:45","Главная сцена","Будущее здоровья","keynote","Что будет определять качество жизни завтра","все",600,1,1,"Промомед"),
   ("P17","18:00","18:40","Клуб","Community","closing","Что я забираю с собой: 30 дней продолжения","все",240,1,1,"СОСТОЯНИЕ"),
   ("P18","19:00","20:00","Клуб","Community","club","Closing club & partner encounters","участники / спикеры / бренды",180,0,0,"СОСТОЯНИЕ")
  ]
  c.executemany("INSERT OR IGNORE INTO program_items(id,start,\"end\",venue,track,format,title,audience,capacity,stream,replay,partner) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",program)
  extended_program=[
   ("P19","09:30","10:10","Partner Studio","Диагностика","workshop","Чекап без перегруза: как выбирать действительно нужное","участники",45,1,1,"Diagnostics partner · demo"),
   ("P20","09:45","10:30","Recovery Lab","Восстановление","practice","Утро, энергия, ритм: настройка дня","по записи",32,0,1,"Recovery partner · demo"),
   ("P21","10:30","11:15","Главная сцена","Метаболическое здоровье","debate","Вес, метаболизм и качество жизни: что изменилось за пять лет","все",600,1,1,"Промомед"),
   ("P22","10:50","11:30","Клуб","Community","talk","Как говорить о здоровье без стыда и давления","все",180,1,1,"СОСТОЯНИЕ"),
   ("P23","11:20","12:00","Business Club","Клиенты","case","От продукта к отношениям: consumer health как новая категория","бренды / клиенты",100,1,1,"Промомед"),
   ("P24","11:40","12:20","Partner Studio","Технологии","demo","Wearables и данные: что полезно человеку, а что просто шум","участники",45,1,1,"HealthTech partner · demo"),
   ("P25","11:50","12:30","Recovery Lab","Сон","practice","Дневная энергия без героизма: сон, свет, движение","по записи",32,0,1,"Sleep partner · demo"),
   ("P26","12:30","13:15","Наука","Эндокринология","lecture","ГПП-1 и ГИП: как читать новую эпоху метаболической терапии","все",180,1,1,"Промомед"),
   ("P27","12:40","13:20","Beauty Lab","Healthy ageing","masterclass","Кожа как часть здоровья: ожидания, доказательства, процедуры","по записи",36,1,1,"Beauty partner · demo"),
   ("P28","13:00","13:45","Business Club","Партнёрства","roundtable","Как брендам входить в health ecosystem этично и измеримо","бренды / партнёры",100,1,1,"Промомед + partners"),
   ("P29","13:30","14:10","Partner Studio","Питание","workshop","Белок, клетчатка, режим: собрать рацион без диетической религии","по записи",45,1,1,"Nutrition partner · demo"),
   ("P30","13:45","14:25","Главная сцена","Лидерство","interview","Наука как бренд: почему доверие становится активом компании","все",600,1,1,"Промомед"),
   ("P31","14:00","14:35","Recovery Lab","Стресс","practice","Перезагрузка за 30 минут: recovery session","по записи",32,0,1,"Recovery partner · demo"),
   ("P32","14:45","15:25","Клуб","Community","fishbowl","Вопрос, который я боялся задать врачу","участники / эксперты",180,1,1,"СОСТОЯНИЕ"),
   ("P33","15:30","16:15","Главная сцена","Инновации","keynote","Российская биофарма: от лаборатории до человека","все",600,1,1,"Промомед"),
   ("P34","15:50","16:30","Наука","Онкология","lecture","Сложные состояния: как говорить о новых возможностях ответственно","профессиональный контур",160,1,1,"Промомед"),
   ("P35","16:20","17:00","Beauty Lab","Beauty science","panel","Beauty, медицина и wellness: где проходят границы обещаний","все",36,1,1,"Beauty partner · demo"),
   ("P36","16:30","17:15","Partner Studio","Диагностика","workshop","Личный health dashboard: какие показатели действительно стоит помнить","по записи",45,1,1,"Diagnostics partner · demo"),
   ("P37","17:00","17:40","Business Club","Клиенты","roundtable","CRM после конференции: как удерживать доверие, а не просто контакт","бренды / клиенты",100,1,1,"Промомед"),
   ("P38","17:15","17:55","Recovery Lab","Движение","practice","Mobility reset: тело после целого дня конференции","по записи",32,0,1,"Fitness partner · demo"),
   ("P39","17:50","18:30","Наука","Неврология","panel","Мозг, сон, внимание: что реально можно изменить","все",180,1,1,"Промомед + experts"),
   ("P40","18:00","18:45","Partner Studio","Партнёры","showcase","Partner Demo Hour: сервисы, которые продолжают маршрут","участники / бренды",45,1,1,"Partners · demo"),
   ("P41","18:45","19:25","Главная сцена","Итоги","closing","СОСТОЯНИЕ: 10 идей, которые стоит забрать в следующий год","все",600,1,1,"Промомед + СОСТОЯНИЕ"),
   ("P42","19:20","20:00","Business Club","B2B","reception","Client & Partner Salon: разговоры без сцены","клиенты / партнёры / спикеры",100,0,0,"Промомед")
  ]
  c.executemany("INSERT OR IGNORE INTO program_items(id,start,\"end\",venue,track,format,title,audience,capacity,stream,replay,partner) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",extended_program)
  speakers=[
   ("SP01","Анна Миронова","Медицинский редактор","СОСТОЯНИЕ","Демо-профиль. Переводит исследования в понятный редакционный язык; профиль не представляет реального специалиста.","научная грамотность,сон","expert"),
   ("SP02","Ирина Волкова","R&D / стратегический спикер","Промомед","Демо-профиль представителя компании для показа будущей структуры карточки: роль, компетенции, выступления, материалы и disclosure.","разработка,метаболическое здоровье","promomed"),
   ("SP03","Максим Орлов","Предприниматель","HealthTech demo","Демо-профиль основателя health-tech проекта: технологии, сервисный дизайн и новая health economy.","healthtech,клиентский опыт","business"),
   ("SP04","Елена К.","Участник / клиент","Community demo","Демо-профиль участника с интересом к научной грамотности и восстановлению.","сон,наука","client"),
   ("SP05","Мария Левина","Эксперт beauty/wellness","Beauty partner demo","Демо-профиль партнёрского эксперта. Коммерческая связь всегда раскрывается.","кожа,healthy ageing","partner"),
   ("SP06","Александр Руднев","Врач-эндокринолог","Expert demo","Демо-профиль для метаболического трека. В production квалификация и место работы подтверждаются редакцией.","эндокринология,ожирение,диабет","expert"),
   ("SP07","Дарья Соколова","Научный журналист","СОСТОЯНИЕ Studio","Демо-профиль ведущей Studio: задаёт вопросы о качестве доказательств, рисках и границах знания.","наука,медиа,интервью","opinion"),
   ("SP08","Никита Беляев","Creator / founder","Wellbeing demo","Демо opinion-leader profile для перевода сложных health-тем в повседневную культуру без медицинских советов.","wellbeing,привычки,community","opinion"),
   ("SP09","Ольга Воронцова","Онколог","Expert demo","Демо-профиль профессионального контура. Контент сложных состояний не смешивается с entertainment-механиками.","онкология,patient journey","expert"),
   ("SP10","Софья Громова","Редактор healthy ageing","СОСТОЯНИЕ","Демо-профиль редактора тематического хаба о качестве жизни, коже и профилактике.","healthy ageing,кожа,профилактика","opinion")
  ]
  c.executemany("INSERT OR REPLACE INTO speakers(id,name,role,org,bio,topics,kind) VALUES(?,?,?,?,?,?,?)",speakers)
  partners=[
   ("BR01","Промомед","Core health","Научное и продуктовое ядро экосистемы.","core"),
   ("BR02","Beauty partner · demo","Beauty / healthy ageing","Диагностические и косметические активности в Beauty Lab.","demo"),
   ("BR03","Nutrition partner · demo","Nutrition","Практические форматы питания и lifestyle.","demo"),
   ("BR04","Sleep partner · demo","Sleep / recovery","Практики восстановления и сна.","demo"),
   ("BR05","Fitness partner · demo","Movement","Движение и физическая активность.","demo")
  ]
  c.executemany("INSERT OR IGNORE INTO partners(id,name,category,description,status) VALUES(?,?,?,?,?)",partners)
  links=[("P01","SP02"),("P02","SP02"),("P02","SP06"),("P03","SP05"),("P05","SP01"),("P05","SP07"),("P07","SP01"),("P07","SP02"),("P10","SP03"),("P10","SP04"),("P12","SP05"),("P13","SP02"),("P15","SP03"),("P16","SP02"),("P17","SP04"),("P21","SP06"),("P21","SP07"),("P22","SP08"),("P26","SP06"),("P27","SP05"),("P30","SP02"),("P30","SP07"),("P32","SP07"),("P33","SP02"),("P34","SP09"),("P35","SP05"),("P39","SP01"),("P41","SP07")]
  c.executemany("INSERT OR IGNORE INTO session_speakers(item_id,speaker_id) VALUES(?,?)",links)
  slots=[
   ("SL01","P06","11:00","11:10",1,"BR02"),("SL02","P06","11:10","11:20",1,"BR02"),("SL03","P06","11:20","11:30",1,"BR02"),
   ("SL04","P12","15:00","15:15",2,"BR02"),("SL05","P12","15:15","15:30",2,"BR02"),("SL06","P12","15:30","15:45",2,"BR02")
  ]
  c.executemany("INSERT OR IGNORE INTO appointment_slots(id,item_id,start,\"end\",capacity,partner_id) VALUES(?,?,?,?,?,?)",slots)
  products=[
   ("PR01","Тирзетта®","тирзепатид","ПРОМОМЕД","Метаболическое здоровье","real","Официальный продуктовый контекст внутри темы метаболического здоровья. Не является назначением лечения.","Годовой отчёт ПРОМОМЕД 2024","https://promomed.ru/","Реальный бренд ПРОМОМЕД; показ в MVP требует medical/legal review перед публичным запуском."),
   ("PR02","Велгия®","семаглутид","ПРОМОМЕД","Управление весом","real","Препарат ПРОМОМЕД, представленный в официальных материалах компании для терапии избыточной массы тела и ожирения.","ПРОМОМЕД · официальный пресс-релиз","https://promomed.ru/","Информационная карточка; не медицинская рекомендация и не механизм стимулирования покупки."),
   ("PR03","Квинсента®","семаглутид","ПРОМОМЕД","Эндокринология","real","Бренд ПРОМОМЕД из эндокринологического портфеля; в MVP связан с образовательным контекстом диабета и метаболического здоровья.","ПРОМОМЕД · публичные материалы","https://promomed.ru/","Только официальный продуктовый контекст; решение о терапии принимает врач."),
   ("PR04","Recovery Ring","—","Partner demo","Сон и восстановление","demo","Вымышленный wearable для демонстрации партнёрского product journey.","DEMO","", "Вымышленный продукт; коммерческая интеграция маркируется."),
   ("PR05","Skin Lab Scan","—","Beauty partner demo","Healthy ageing","demo","Демонстрационный сервис диагностики кожи по записи на конференции.","DEMO","", "Вымышленный сервис; не медицинская диагностика.")
  ]
  c.executemany("INSERT OR REPLACE INTO product_catalog(id,name,inn,company,theme,kind,summary,source_label,source_url,disclosure) VALUES(?,?,?,?,?,?,?,?,?,?)",products)
  contents=[
   ("CT01","cover","Метаболическое здоровье","Метаболическое здоровье: новая реальность","Что изменилось в языке веса, диабета и качества жизни — и как читать новую терапевтическую эпоху без упрощений.","12 мин","Редакция СОСТОЯНИЕ","medical review · demo","ПРОМОМЕД","review"),
   ("CT02","explainer","Научная грамотность","Как отличить сильное исследование от громкого заголовка","Шесть вопросов к источнику до того, как делиться выводом.","8 мин","Анна Миронова · demo","medical review · demo","","published"),
   ("CT03","dictionary","Метаболическое здоровье","ГПП-1 и ГИП: понятный словарь","Механизмы, термины и вопросы, которые стоит обсуждать со специалистом.","10 мин","Редакция СОСТОЯНИЕ","medical review · demo","ПРОМОМЕД","review"),
   ("CT04","video","Компания","От идеи к молекуле","R&D, производство, контроль качества и путь продукта до рынка.","14 мин","СОСТОЯНИЕ Studio","corporate review","ПРОМОМЕД","concept"),
   ("CT05","podcast","Мозг и энергия","Можно ли сделать ЗОЖ менее тревожным?","Врач и creator разбирают границу между полезной привычкой и health anxiety.","38 мин","СОСТОЯНИЕ FM","editorial review","","concept"),
   ("CT06","guide","Healthy ageing","Кожа, возраст и ожидания","Что может lifestyle, что может косметология и где начинается медицина.","11 мин","Софья Громова · demo","medical review · demo","Beauty partner · demo","concept"),
   ("CT07","interview","Компания","Наука как бренд","Как R&D, прозрачность и качественная коммуникация создают доверие к компании.","18 мин","Дарья Соколова · demo","corporate review","ПРОМОМЕД","concept"),
   ("CT08","guide","Диагностика","Чекап без перегруза","Как обсуждать профилактику и скрининг без гонки за максимальным числом анализов.","9 мин","Редакция СОСТОЯНИЕ","medical review · demo","Diagnostics partner · demo","concept"),
   ("CT09","video","Онкология","Сложный диагноз: навигация вместо информационного шума","Как устроить профессиональный patient-support контур.","16 мин","Expert Studio · demo","medical review · demo","ПРОМОМЕД","concept"),
   ("CT10","report","Тренды","СОСТОЯНИЕ Index 2027","Какие health-вопросы, форматы и барьеры доверия формируют новую потребительскую повестку.","24 мин","Research desk · demo","methodology review","ПРОМОМЕД","concept"),
   ("CT11","short","Сон и восстановление","Что изменить сегодня вечером","Короткий evidence-aware маршрут без обещаний идеального сна.","4 мин","СОСТОЯНИЕ Studio","editorial review","Sleep partner · demo","concept"),
   ("CT12","case","Health economy","Как бренду создавать health value без рекламного шума","Партнёрская интеграция как полезный сервис, а не логотип на сцене.","7 мин","Business desk","commercial disclosure","Partner council · demo","concept")
  ]
  c.executemany("INSERT OR REPLACE INTO content_catalog(id,kind,theme,title,dek,duration,author,reviewer,partner,status) VALUES(?,?,?,?,?,?,?,?,?,?)",contents)
  packages=[
   ("PK01","Strategic Health Partner","annual","Годовая роль внутри одной тематической вертикали.","Hub co-creation | Studio series | flagship session | partner zone | 1/7/30 continuation | annual report","reach | qualified engagement | booked experiences | consented follow-up | return","Коммерческое участие раскрывается во всех материалах."),
   ("PK02","Conference Track Partner","conference","Кураторство одной программной темы без права подменять редакционную политику.","session | speaker integration | branded experience | replay | post-event content","attendance | dwell | replay | opt-in","Спонсорство не означает медицинское одобрение."),
   ("PK03","Studio Partner","media","Серия видео/подкастов с отдельным editorial review.","4 episodes | shorts | transcript | topic hub | distribution","views | completion | saves | return","Каждый выпуск маркирует партнёрство."),
   ("PK04","Experience Partner","event","Полезная запись по времени: диагностика, практика или сервис.","bookable slots | venue presence | QR route | follow-up | report","bookings | show rate | satisfaction | opt-in","Запрещены скрытые medical claims и стимулирование покупки рецептурных препаратов."),
   ("PK05","Research / Index Partner","thought leadership","Поддержка исследования и публичного отчёта при сохранении методологической прозрачности.","research module | roundtable | report presence | launch event","report reach | citations | executive leads","Методология и спонсорство раскрываются отдельно.")
  ]
  c.executemany("INSERT OR REPLACE INTO partner_packages(id,name,tier,summary,deliverables,measurement,disclosure) VALUES(?,?,?,?,?,?,?)",packages)
  community_threads=[
   ("TH01","Метаболическое здоровье","Как читать новости о весе и терапии без крайностей","Разбираем язык доказательств, рисков и ожиданий. Вопросы проходят модерацию; персональные назначения не публикуются.","Анна Миронова · demo","open","P21"),
   ("TH02","Сон и восстановление","Что действительно помогает восстановлению","Практические вопросы после Studio и лекций: сон, свет, движение, режим. Без диагностики и обещаний результата.","Community host · demo","open","P39"),
   ("TH03","Healthy ageing","Возраст, кожа и качество жизни","Разговор о реалистичных ожиданиях, профилактике и границах между lifestyle, косметологией и медициной.","Софья Громова · demo","open","P27"),
   ("TH04","Научная грамотность","Источник недели: читаем исследование вместе","Модерируемый клуб по разбору источников, абсолютного риска, дизайна исследований и качества выводов.","Редакция СОСТОЯНИЕ","open","P05")
  ]
  c.executemany("INSERT OR REPLACE INTO community_threads(id,topic,title,summary,moderator,status,related_item) VALUES(?,?,?,?,?,?,?)",community_threads)
  learning_tracks=[
   ("LT01","Метаболическое здоровье","Метаболическое здоровье без информационного шума","Материал → эксперт → debate → replay → обсуждение. Короткий маршрут для понимания темы, а не для самолечения.",14,"foundation"),
   ("LT02","Сон и восстановление","Сон и энергия: 7 дней понимания","Studio, практическая сессия, replay и community-разбор вокруг устойчивых привычек.",7,"foundation"),
   ("LT03","Healthy ageing","Healthy ageing: ожидания и доказательства","Редакционный маршрут о качестве жизни, коже, профилактике и корректной коммуникации обещаний.",14,"foundation")
  ]
  c.executemany("INSERT OR REPLACE INTO learning_tracks(id,topic,title,summary,duration_days,level) VALUES(?,?,?,?,?,?)",learning_tracks)
  learning_steps=[
   ("LT01",1,"material","CT01","Прочитать cover story"),("LT01",2,"expert","SP06","Познакомиться с экспертом"),("LT01",3,"event","P21","Добавить debate в маршрут"),("LT01",4,"replay","P21","Открыть replay и тезисы"),("LT01",5,"community","TH01","Продолжить обсуждение"),
   ("LT02",1,"studio","ST02","Посмотреть Studio"),("LT02",2,"material","CT11","Сохранить короткий guide"),("LT02",3,"event","P39","Посетить или открыть replay"),("LT02",4,"community","TH02","Разобрать вопрос в клубе"),
   ("LT03",1,"material","CT06","Разобрать ожидания"),("LT03",2,"expert","SP10","Открыть профиль редактора"),("LT03",3,"event","P27","Добавить masterclass"),("LT03",4,"community","TH03","Продолжить тему после события")
  ]
  c.executemany("INSERT OR REPLACE INTO learning_steps(track_id,step_no,kind,ref_id,title) VALUES(?,?,?,?,?)",learning_steps)
  studio_episodes=[
   ("ST01","Метаболическое здоровье","Почему разговор о весе стал другим","12 минут после сцены: язык доказательств, ожидания и границы уверенности.","12 мин","SP06","CT01","P21","TH01","LT01","ready"),
   ("ST02","Сон и восстановление","Что мы переоцениваем в идеальном сне","Врачебный контекст встречается с повседневной культурой без превращения разговора в назначение.","16 мин","SP07","CT11","P39","TH02","LT02","ready"),
   ("ST03","Healthy ageing","Можно ли говорить о молодости без обещаний чуда","Редактор и эксперт разбирают доказательства, маркетинговый язык и реальные ожидания аудитории.","18 мин","SP10","CT06","P27","TH03","LT03","scheduled")
  ]
  c.executemany("INSERT OR REPLACE INTO studio_episodes(id,topic,title,dek,duration,speaker_id,content_id,item_id,thread_id,track_id,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",studio_episodes)
  chapters=[
   ("CH01","P05",0,"Почему заголовки вводят в заблуждение","chapter"),("CH02","P05",240,"Корреляция и причинность","chapter"),("CH03","P05",510,"Что проверить в источнике","chapter"),
   ("CH04","P13",0,"Энергия и внимание","chapter"),("CH05","P13",330,"Сон и восстановление","chapter"),("CH06","P13",690,"Что можно изменить завтра","takeaway")
  ]
  c.executemany("INSERT OR IGNORE INTO replay_chapters(id,item_id,offset_sec,title,kind) VALUES(?,?,?,?,?)",chapters)
  venue_rows=[("Главная сцена",600,420,"open","P07 · 12:00",int(time.time())),("Наука",180,96,"open","P05 · 11:00",int(time.time())),("Beauty Lab",36,28,"busy","P06 · 11:00",int(time.time())),("Business Club",100,64,"open","P10 · 14:00",int(time.time())),("Partner Studio",45,21,"open","P08 · 12:15",int(time.time())),("Recovery Lab",32,18,"open","P09 · 13:10",int(time.time())),("Клуб",240,72,"open","P11 · 14:20",int(time.time()))]
  c.executemany("INSERT OR IGNORE INTO venue_state(venue,capacity,occupied,status,next_change,updated) VALUES(?,?,?,?,?,?)",venue_rows)
  for iid in ("P01","P02","P04","P05","P07","P08","P10","P12","P13","P15","P16","P17","P19","P21","P22","P23","P24","P26","P27","P28","P29","P30","P32","P33","P34","P35","P36","P37","P39","P40","P41"):
   c.execute("INSERT OR IGNORE INTO stream_state(item_id,status,health,delay_sec,updated) VALUES(?,'scheduled','ok',3,?)",(iid,int(time.time())))
  staff_rows=[("Алексей","Floor lead","Главная сцена","08:00","20:30","on_shift"),("Мария","Check-in","Главная сцена","08:00","13:00","on_shift"),("Олег","Venue manager","Beauty Lab","09:00","18:00","on_shift"),("Дарья","Partner desk","Partner Studio","10:00","18:30","on_shift"),("Илья","AV / Stream","Наука","09:00","18:00","on_shift"),("Светлана","Community host","Клуб","12:00","20:30","on_shift")]
  c.executemany("INSERT OR IGNORE INTO staff_assignments(staff_name,role,venue,shift_start,shift_end,status,updated) VALUES(?,?,?,?,?,?,?)",[(a,b,d,e,f,g,int(time.time())) for a,b,d,e,f,g in staff_rows])
  readiness=[("SP02","P01","ready",1,1,1,1),("SP02","P02","ready",1,1,1,1),("SP05","P03","briefing",1,1,0,1),("SP01","P05","ready",1,1,1,1),("SP03","P10","arriving",0,1,0,1),("SP04","P10","ready",1,1,1,1)]
  c.executemany("INSERT OR IGNORE INTO speaker_readiness(speaker_id,item_id,status,checkin,briefed,mic,slides,updated) VALUES(?,?,?,?,?,?,?,?)",[(a,b,d,e,f,g,h,int(time.time())) for a,b,d,e,f,g,h in readiness])
  for did,label in [("PL-01","Размещение в программе"),("PL-02","Партнёрская зона"),("PL-03","Материалы после события"),("PL-04","Добровольный lead route")]:
   c.execute("INSERT OR IGNORE INTO deliverables(id,label,status,evidence,updated) VALUES(?,?,'contracted','',?)",(did,label,int(time.time())))
  for e in ("participant@demo.ru","participant2@demo.ru","participant3@demo.ru"):
   c.execute("INSERT OR IGNORE INTO attendee_profiles(email,intent,interests,networking,visibility,updated) VALUES(?, 'Понять полезное для себя','сон,наука,движение',1,'event_only',?)",(e,int(time.time())))
   c.execute("INSERT OR IGNORE INTO passport(email,updated) VALUES(?,?)",(e,int(time.time())))
  c.commit(); db.sync_sequences(c); c.close()

class H(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=ROOT,**kw)
 def cors(self):
  self.send_header("Access-Control-Allow-Origin","https://sostoyanie-promomed-preview.onrender.com")
  self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type")
  self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
 def out(self,obj,status=200):
  b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status)
  self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.cors()
  self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_OPTIONS(self):
  self.send_response(204); self.cors(); self.end_headers()
 def do_GET(self):
  p=urlparse(self.path).path; a=auth(self)
  if p=="/health":
   return self.out({"ok":True,"app":"sostoyanie-v18-persistence-admission","backend":db.backend_name(),"durable":db.is_durable_backend(),"demo_seed":db.demo_seed_enabled(),"git_commit":os.environ.get("RENDER_GIT_COMMIT","local")})
  if p=="/ready":
   try:
    r=db.readiness(); c=conn()
    try:
     seeded_data=bool(c.execute("SELECT 1 FROM state LIMIT 1").fetchone() and c.execute("SELECT 1 FROM cms LIMIT 1").fetchone())
    finally:c.close()
    r["data_ready"]=seeded_data if r["demo_seed_enabled"] else True
    r["ready"]=bool(r["ready"] and r["data_ready"]); r["production_ready"]=bool(r["production_ready"] and r["data_ready"])
    return self.out(r,200 if r["ready"] else 503)
   except Exception as e:
    return self.out({"ready":False,"production_ready":False,"error":type(e).__name__,"backend":db.backend_name()},503)
  if p=="/api/state":
   c=conn(); d=state(c,a[2] if a else None); c.close(); return self.out(d)
  if p=="/api/product-quality-proof":
   c=conn()
   proof={
    "ok":True,"version":"v1.5","contract":"product-quality",
    "counts":{
     "products":c.execute("SELECT COUNT(*) n FROM product_catalog").fetchone()["n"],
     "materials":c.execute("SELECT COUNT(*) n FROM content_catalog").fetchone()["n"],
     "speakers":c.execute("SELECT COUNT(*) n FROM speakers").fetchone()["n"],
     "partner_packages":c.execute("SELECT COUNT(*) n FROM partner_packages").fetchone()["n"],
     "program_items":c.execute("SELECT COUNT(*) n FROM program_items").fetchone()["n"],
     "session_speaker_links":c.execute("SELECT COUNT(*) n FROM session_speakers").fetchone()["n"]
    },
    "required_ids":{
     "products":[r["id"] for r in c.execute("SELECT id FROM product_catalog ORDER BY id")],
     "materials":[r["id"] for r in c.execute("SELECT id FROM content_catalog ORDER BY id")],
     "packages":[r["id"] for r in c.execute("SELECT id FROM partner_packages ORDER BY id")]
    },
    "surfaces":["premium_home","topic_hubs","media_catalog","product_detail","speaker_profile","rich_session_detail","studio","partner_marketplace"],
    "disclosure":"real Promomed product context is separated from demo partner content"
   }
   c.close(); return self.out(proof)
  if p=="/api/continuity-proof":
   c=conn()
   proof={
    "ok":True,"version":"v1.6","contract":"continuity",
    "counts":{
     "studio_episodes":c.execute("SELECT COUNT(*) n FROM studio_episodes").fetchone()["n"],
     "community_threads":c.execute("SELECT COUNT(*) n FROM community_threads").fetchone()["n"],
     "learning_tracks":c.execute("SELECT COUNT(*) n FROM learning_tracks").fetchone()["n"],
     "learning_steps":c.execute("SELECT COUNT(*) n FROM learning_steps").fetchone()["n"],
     "direct_messages":c.execute("SELECT COUNT(*) n FROM direct_messages").fetchone()["n"]
    },
    "journey":["studio","expert","topic_hub","community","event","replay","learning_track","account_inbox"],
    "guardrails":["community moderation","medical/editorial disclosure","no personalized treatment advice","explicit follow and subscription actions","direct messaging only after mutual consent or with organizer"],
    "durability":"demo authority remains SQLite until production PostgreSQL admission"
   }
   c.close(); return self.out(proof)
  if p=="/api/me": return self.out({"authenticated":bool(a),"role":a[0] if a else None,"name":a[1] if a else None})
  if p=="/api/command":
   if not a or a[0] not in ("organizer","sales","staff"): return self.out({"error":"forbidden"},403)
   c=conn()
   venues=[]
   for v in c.execute("SELECT venue,capacity,occupied,status,next_change FROM venue_state ORDER BY venue"):
    d=dict(v)
    d["queue"]=c.execute("SELECT COUNT(*) n FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE p.venue=? AND b.status='waitlist'",(v["venue"],)).fetchone()["n"]
    d["staff"]=c.execute("SELECT COUNT(*) n FROM staff_assignments WHERE venue=? AND status='on_shift'",(v["venue"],)).fetchone()["n"]
    d["incidents"]=c.execute("SELECT COUNT(*) n FROM incidents WHERE venue=? AND status='open'",(v["venue"],)).fetchone()["n"]
    venues.append(d)
   staff=[dict(r) for r in c.execute("SELECT id,staff_name,role,venue,shift_start,shift_end,status FROM staff_assignments ORDER BY venue,role")]
   speakers=[dict(r) for r in c.execute("SELECT r.speaker_id,r.item_id,r.status,r.checkin,r.briefed,r.mic,r.slides,s.name,p.title,p.start,p.venue FROM speaker_readiness r JOIN speakers s ON s.id=r.speaker_id JOIN program_items p ON p.id=r.item_id ORDER BY p.start")]
   incidents=[dict(r) for r in c.execute("SELECT id,venue,severity,title,status,recovery,ts,resolved FROM incidents ORDER BY id DESC LIMIT 20")]
   now=int(time.time()); sla_minutes={"critical":5,"high":10,"medium":20,"low":45}
   for i in incidents:
    limit=sla_minutes.get(i["severity"],20); age=max(0,(i["resolved"] or now)-i["ts"])//60
    i["sla_minutes"]=limit; i["age_minutes"]=age; i["sla_status"]="breached" if i["status"]=="open" and age>limit else ("resolved" if i["status"]!="open" else "within_sla")
   streams=[dict(r) for r in c.execute("SELECT item_id,status,health,delay_sec,updated FROM stream_state ORDER BY item_id")]
   broadcasts=[dict(r) for r in c.execute("SELECT id,audience,venue,title,body,status,ts FROM ops_broadcasts ORDER BY id DESC LIMIT 12")]
   partner_desk=[dict(r) for r in c.execute("SELECT pr.name partner,a.id slot_id,a.start,a.\"end\",p.venue,p.title,COUNT(CASE WHEN b.status='booked' THEN 1 END) booked,COUNT(CASE WHEN b.status='waitlist' THEN 1 END) waitlist,a.capacity FROM appointment_slots a JOIN program_items p ON p.id=a.item_id LEFT JOIN partners pr ON pr.id=a.partner_id LEFT JOIN appointment_bookings b ON b.slot_id=a.id GROUP BY pr.name,a.id,a.start,a.\"end\",p.venue,p.title,a.capacity ORDER BY a.start")]
   c.close()
   return self.out({"venues":venues,"staff":staff,"speakers":speakers,"incidents":incidents,"streams":streams,"broadcasts":broadcasts,"partner_desk":partner_desk})
  if p=="/api/intelligence":
   if not a or a[0] not in ("organizer","sales","partner"): return self.out({"error":"forbidden"},403)
   c=conn()
   by_track=[dict(r) for r in c.execute("SELECT p.track,COUNT(b.item_id) bookings FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.status='booked' GROUP BY p.track ORDER BY bookings DESC")]
   by_venue=[dict(r) for r in c.execute("SELECT p.venue,COUNT(b.item_id) bookings FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.status='booked' GROUP BY p.venue ORDER BY bookings DESC")]
   consent=c.execute("SELECT COUNT(*) n FROM product_interests").fetchone()["n"]
   follow=c.execute("SELECT COUNT(DISTINCT email) n FROM followups").fetchone()["n"]
   appts=c.execute("SELECT COUNT(*) n FROM appointment_bookings WHERE status='booked'").fetchone()["n"]
   meetings=c.execute("SELECT COUNT(*) n FROM meetings WHERE status='confirmed'").fetchone()["n"]
   replay=c.execute("SELECT COUNT(*) n FROM journeys WHERE replay=1").fetchone()["n"]
   regs=c.execute("SELECT COUNT(*) n FROM registrations").fetchone()["n"]
   attended=c.execute("SELECT COUNT(*) n FROM checkins").fetchone()["n"]
   bookings=c.execute("SELECT COUNT(*) n FROM activity_bookings WHERE status='booked'").fetchone()["n"]
   mutual=c.execute("SELECT COUNT(*) n FROM mutual_meetings WHERE status='confirmed'").fetchone()["n"]
   challenges=c.execute("SELECT COUNT(*) n FROM challenges WHERE status IN ('active','completed')").fetchone()["n"]
   lead_total=c.execute("SELECT COUNT(*) n FROM leads").fetchone()["n"]
   by_partner=[dict(r) for r in c.execute("SELECT p.partner,COUNT(b.item_id) bookings FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.status='booked' GROUP BY p.partner ORDER BY bookings DESC")]
   attendance_by_track=[dict(r) for r in c.execute("SELECT p.track,COUNT(a.item_id) attendance FROM session_attendance a JOIN program_items p ON p.id=a.item_id WHERE a.status IN ('present','completed') GROUP BY p.track ORDER BY attendance DESC")]
   attendance_by_partner=[dict(r) for r in c.execute("SELECT p.partner,COUNT(a.item_id) attendance FROM session_attendance a JOIN program_items p ON p.id=a.item_id WHERE a.status IN ('present','completed') GROUP BY p.partner ORDER BY attendance DESC")]
   retention=[dict(r) for r in c.execute("SELECT day,COUNT(DISTINCT email) people FROM followups GROUP BY day ORDER BY day")]
   partner_actions=[dict(r) for r in c.execute("SELECT partner,kind,COUNT(*) actions,SUM(consent) consented FROM partner_engagement GROUP BY partner,kind ORDER BY actions DESC")]
   venue_ops=[dict(r) for r in c.execute("SELECT venue,capacity,occupied,status,next_change FROM venue_state ORDER BY venue")]
   incidents_open=c.execute("SELECT COUNT(*) n FROM incidents WHERE status='open'").fetchone()["n"]
   streams=[dict(r) for r in c.execute("SELECT item_id,status,health,delay_sec FROM stream_state ORDER BY item_id")]
   c.close()
   return self.out({"by_track":by_track,"by_venue":by_venue,"by_partner":by_partner,"attendance_by_track":attendance_by_track,"attendance_by_partner":attendance_by_partner,"retention":retention,"partner_actions":partner_actions,"consented_interests":consent,"followup_people":follow,"partner_appointments":appts,"confirmed_meetings":meetings+mutual,"replay_users":replay,"funnel":{"registrations":regs,"program_bookings":bookings,"attendance":attended,"partner_appointments":appts,"consent":consent+lead_total,"day30_active":challenges,"return_replay":replay},"venue_ops":venue_ops,"open_incidents":incidents_open,"streams":streams})
  if p=="/api/investor-proof":
   if not a or a[0] not in ("organizer","partner","sales"): return self.out({"error":"forbidden"},403)
   c=conn()
   try:d=investor.snapshot(c)
   finally:c.close()
   return self.out(d)
  if p=="/api/executive-room":
   if not a or a[0] not in ("organizer","partner","sales"): return self.out({"error":"forbidden"},403)
   c=conn()
   try:d=executive.snapshot(c)
   finally:c.close()
   return self.out(d)
  if a:
   c=conn()
   try: strategic=read_strategic_projection(c,p,a[0])
   finally:c.close()
   if strategic is not None: return self.out(strategic[0],strategic[1])
  if p=="/api/corporate-readiness":
   if not a or a[0] not in ("organizer","partner","sales"): return self.out({"error":"forbidden"},403)
   c=conn()
   try:d=corporate.snapshot(c)
   finally:c.close()
   return self.out(d)
  if p=="/api/analytics":
   if not a or a[0] not in ("organizer","partner","sales"): return self.out({"error":"forbidden"},403)
   c=conn(); d=commercial(c); d["seeded_demo"]=False; d["demo_run"]=sval(c,"demo_run","0"); d["demo_step"]=sval(c,"demo_step","-1"); c.close(); return self.out(d)
  if p=="/api/demo/status":
   if not a or a[0] not in ("sales","organizer"): return self.out({"error":"forbidden"},403)
   c=conn(); idx=int(sval(c,"demo_step","-1")); d=state(c,a[2]); c.close()
   d["step_index"]=idx; d["step_key"]=DEMO_STEPS[idx][0] if 0<=idx<len(DEMO_STEPS) else "not_started"
   d["step_title"]=DEMO_STEPS[idx][1] if 0<=idx<len(DEMO_STEPS) else "Демо не подготовлено"
   d["total_steps"]=len(DEMO_STEPS)
   return self.out(d)
  if p=="/api/demo/evidence":
   if not a or a[0] not in ("sales","organizer","partner"): return self.out({"error":"forbidden"},403)
   c=conn()
   rows=[dict(r) for r in c.execute("SELECT id,kind,actor,payload,ts FROM events ORDER BY id DESC LIMIT 30")]
   rows.reverse()
   metrics=commercial(c)
   metrics["placement_status"]=state(c).get("placement_status")
   metrics["live_state"]=sval(c,"live_state","scheduled")
   metrics["phase"]=sval(c,"phase","before")
   metrics["session_time"]=sval(c,"session_time","11:00")
   metrics["session_room"]=sval(c,"session_room","Лекторий")
   metrics["occupied"]=int(sval(c,"occupied","0"))
   metrics["capacity"]=int(sval(c,"capacity","120"))
   deliverables=[dict(r) for r in c.execute("SELECT id,label,status,evidence,updated FROM deliverables ORDER BY id")]
   notifications=c.execute("SELECT COUNT(*) n FROM notifications").fetchone()["n"]
   metrics["notifications"]=notifications
   c.close()
   return self.out({"events":rows,"metrics":metrics,"deliverables":deliverables,"proposed_pilot_gates":[
    {"id":"audience","label":"Аудитория","criterion":"Регистрация → фактическое участие","target":"Цель пилота согласуется до запуска","status":"to_agree"},
    {"id":"engagement","label":"Вовлечённость","criterion":"Контент → событие → post-event возврат","target":"Цель пилота согласуется до запуска","status":"to_agree"},
    {"id":"partner","label":"Коммерция","criterion":"Добровольные лиды и ценность партнёра","target":"Цель пилота согласуется до запуска","status":"to_agree"},
    {"id":"operations","label":"Операции","criterion":"Check-in / waitlist / venue / live без критических тупиков","target":"0 критических сценариев без recovery path","status":"proposed"},
    {"id":"trust","label":"Доверие","criterion":"Контент, согласия и партнёрская прозрачность","target":"100% обязательных approval / disclosure полей в пилоте","status":"proposed"}
   ]})
  return super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path
  try: data=body(self)
  except Exception: return self.out({"error":"bad_json"},400)
  if p=="/api/login":
   email=str(data.get("email","")).lower(); pw=str(data.get("password",""))
   c=conn()
   try:
    rec=authenticate(c,email,pw)
    if not rec: return self.out({"error":"invalid_credentials"},401)
    token,expires=issue_session(c,rec["email"],rec["role"],rec["name"])
   finally:c.close()
   return self.out({"token":token,"role":rec["role"],"name":rec["name"],"expires_at":expires})
  a=auth(self)
  if not a: return self.out({"error":"unauthorized"},401)
  role,name,email=a
  with LOCK:
   c=conn()
   try:
    outcome=handle_community_command(c,p,role,email,data)
    if outcome is None: outcome=handle_learning_command(c,p,role,email,data)
    if outcome is None: outcome=handle_participant_command(c,p,role,email,data)
    if outcome is None: outcome=handle_programme_command(c,p,role,email,data)
    if outcome is None: outcome=handle_operations_command(c,p,role,email,data)
    if outcome is None: outcome=handle_partner_command(c,p,role,email,data)
    if outcome is None: outcome=handle_editorial_command(c,p,role,email,data)
    if outcome is None: outcome=handle_demo_command(c,p,role,email,data)
    if outcome is None: outcome=handle_investment_command(c,p,role,email,data)
    if outcome is None: outcome=handle_deal_command(c,p,role,email,data)
    if outcome is None: outcome=handle_capital_execution_command(c,p,role,email,data)
    if outcome is None: outcome=handle_intervention_command(c,p,role,email,data)
    if outcome is None: outcome=handle_reallocation_command(c,p,role,email,data)
    if outcome is None: return self.out({"error":"not_found"},404)
    c.commit()
    payload=state(c,email) if outcome.use_state else outcome.payload
    return self.out(payload,outcome.status)
   finally: c.close()
 def log_message(self,fmt,*args): print(fmt%args,flush=True)

if __name__=="__main__":
 init(); port=int(os.environ.get("PORT","10000")); print("SOSTOYANIE v1.8 persistence admission",db.backend_name(),"listening",port,flush=True); ThreadingHTTPServer(("0.0.0.0",port),H).serve_forever()
