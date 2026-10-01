import json, os, threading, secrets, time
from app.db.core import connect as db_connect, db_status
from app.db.migrate import migrate, migration_status
from app.auth.security import authenticate_headers, authenticate_password, create_session, ensure_demo_accounts
from app.integration_api import handle_get as integration_get, handle_post as integration_post, handle_public_post as integration_public_post
from app import notifications as notification_delivery
from app.venue import ensure_demo_asset
from app.gates import ensure_defaults as ensure_integration_gates
from app.content import ensure_legacy_demo_publications
from app.search import rebuild as rebuild_search_projection
from app.observability import configure_observability, http_handler_trace, set_response_status
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT=os.path.join(os.path.dirname(__file__),"public")
DB=os.environ.get("SQLITE_PATH","/tmp/sostoyanie-v06.db")
LOCK=threading.RLock()
TOKENS={}
ACCOUNTS={
 "participant@demo.ru":("demo2027","participant","Участник"),
 "participant2@demo.ru":("demo2027","participant","Участник 2"),
 "participant3@demo.ru":("demo2027","participant","Участник 3"),
 "organizer@demo.ru":("demo2027","organizer","Организатор"),
 "partner@demo.ru":("demo2027","partner","Партнёр"),
 "staff@demo.ru":("demo2027","staff","Check-in"),
 "editor@demo.ru":("demo2027","editor","Редактор"),
 "moderator@demo.ru":("demo2027","moderator","Модератор"),
 "sales@demo.ru":("demo2027","sales","Demo Director"),
}
DEMO_STEPS=[
 ("ready","Исходное состояние подготовлено"),
 ("full","Зал заполнен: 120 / 120"),
 ("waitlist","P2 и P3 поставлены в waitlist"),
 ("promoted","Место освобождено: P2 автоматически повышен"),
 ("hall_move","Сессия перенесена, участникам создано уведомление"),
 ("pause","Live переведён в technical pause"),
 ("live","Эфир восстановлен"),
 ("replay","Эфир завершён, replay доступен"),
 ("checkin","QR-билет подтверждён на входе"),
 ("placement","Contracted placement активирован"),
 ("lead","Создан добровольный consented lead"),
 ("post_event","Post-event replay открыт, dashboard готов"),
]

def conn():
 return db_connect()

def init():
 migrate()
 with LOCK:
  c=conn()
  c.executescript("""CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY,v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkins(ticket TEXT PRIMARY KEY,ts INTEGER,staff TEXT);
CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,status TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS registrations(email TEXT PRIMARY KEY,status TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS bookings(email TEXT,session_id TEXT,status TEXT,ts INTEGER,PRIMARY KEY(email,session_id));
CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY AUTOINCREMENT,text TEXT,status TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS placements(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,status TEXT,leads INTEGER DEFAULT 0,ts INTEGER);
CREATE TABLE IF NOT EXISTS deliverables(id TEXT PRIMARY KEY,label TEXT,status TEXT,evidence TEXT,updated INTEGER);\nCREATE TABLE IF NOT EXISTS attendee_profiles(email TEXT PRIMARY KEY,intent TEXT,interests TEXT,networking INTEGER DEFAULT 0,visibility TEXT DEFAULT 'event_only',updated INTEGER);\nCREATE TABLE IF NOT EXISTS meetings(id INTEGER PRIMARY KEY AUTOINCREMENT,requester TEXT,target TEXT,slot TEXT,place TEXT,status TEXT,ts INTEGER);\nCREATE TABLE IF NOT EXISTS session_feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,session_id TEXT,rating INTEGER,useful INTEGER,comment TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS takeaways(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,session_id TEXT,note TEXT,source TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS product_interests(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,track TEXT,context TEXT,consent_version TEXT,status TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS followups(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,day INTEGER,track TEXT,status TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS program_items(id TEXT PRIMARY KEY,start TEXT,end TEXT,venue TEXT,track TEXT,format TEXT,title TEXT,audience TEXT,capacity INTEGER,stream INTEGER,replay INTEGER,partner TEXT);
CREATE TABLE IF NOT EXISTS activity_bookings(email TEXT,item_id TEXT,status TEXT,ts INTEGER,PRIMARY KEY(email,item_id));
CREATE TABLE IF NOT EXISTS challenges(email TEXT,challenge_id TEXT,status TEXT,days_required INTEGER,started INTEGER,verified INTEGER,reward TEXT,PRIMARY KEY(email,challenge_id));
CREATE TABLE IF NOT EXISTS challenge_actions(email TEXT,challenge_id TEXT,action_id TEXT,label TEXT,status TEXT,ts INTEGER,PRIMARY KEY(email,challenge_id,action_id));
CREATE TABLE IF NOT EXISTS speakers(id TEXT PRIMARY KEY,name TEXT,role TEXT,org TEXT,bio TEXT,topics TEXT,kind TEXT);
CREATE TABLE IF NOT EXISTS partners(id TEXT PRIMARY KEY,name TEXT,category TEXT,description TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS product_catalog(id TEXT PRIMARY KEY,name TEXT,inn TEXT,company TEXT,theme TEXT,kind TEXT,summary TEXT,source_label TEXT,source_url TEXT,disclosure TEXT);
CREATE TABLE IF NOT EXISTS content_catalog(id TEXT PRIMARY KEY,kind TEXT,theme TEXT,title TEXT,dek TEXT,duration TEXT,author TEXT,reviewer TEXT,partner TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS partner_packages(id TEXT PRIMARY KEY,name TEXT,tier TEXT,summary TEXT,deliverables TEXT,measurement TEXT,disclosure TEXT);
CREATE TABLE IF NOT EXISTS studio_episodes(id TEXT PRIMARY KEY,topic TEXT,title TEXT,dek TEXT,duration TEXT,speaker_id TEXT,content_id TEXT,item_id TEXT,thread_id TEXT,track_id TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS community_threads(id TEXT PRIMARY KEY,topic TEXT,title TEXT,summary TEXT,moderator TEXT,status TEXT,related_item TEXT);
CREATE TABLE IF NOT EXISTS community_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,thread_id TEXT,email TEXT,body TEXT,status TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS topic_subscriptions(email TEXT,topic TEXT,status TEXT,ts INTEGER,PRIMARY KEY(email,topic));
CREATE TABLE IF NOT EXISTS expert_follows(email TEXT,speaker_id TEXT,status TEXT,ts INTEGER,PRIMARY KEY(email,speaker_id));
CREATE TABLE IF NOT EXISTS learning_tracks(id TEXT PRIMARY KEY,topic TEXT,title TEXT,summary TEXT,duration_days INTEGER,level TEXT);
CREATE TABLE IF NOT EXISTS learning_steps(track_id TEXT,step_no INTEGER,kind TEXT,ref_id TEXT,title TEXT,PRIMARY KEY(track_id,step_no));
CREATE TABLE IF NOT EXISTS learning_enrollments(email TEXT,track_id TEXT,status TEXT,current_step INTEGER DEFAULT 0,started INTEGER,updated INTEGER,PRIMARY KEY(email,track_id));
CREATE TABLE IF NOT EXISTS session_speakers(item_id TEXT,speaker_id TEXT,PRIMARY KEY(item_id,speaker_id));
CREATE TABLE IF NOT EXISTS appointment_slots(id TEXT PRIMARY KEY,item_id TEXT,start TEXT,end TEXT,capacity INTEGER,partner_id TEXT);
CREATE TABLE IF NOT EXISTS appointment_bookings(email TEXT,slot_id TEXT,status TEXT,ts INTEGER,PRIMARY KEY(email,slot_id));
CREATE TABLE IF NOT EXISTS replay_chapters(id TEXT PRIMARY KEY,item_id TEXT,offset_sec INTEGER,title TEXT,kind TEXT);
CREATE TABLE IF NOT EXISTS mutual_meetings(id INTEGER PRIMARY KEY AUTOINCREMENT,requester TEXT,target_email TEXT,target_name TEXT,slot TEXT,place TEXT,status TEXT,requester_ok INTEGER DEFAULT 1,target_ok INTEGER DEFAULT 0,ts INTEGER);
CREATE TABLE IF NOT EXISTS venue_state(venue TEXT PRIMARY KEY,capacity INTEGER,occupied INTEGER,status TEXT,next_change TEXT,updated INTEGER);
CREATE TABLE IF NOT EXISTS incidents(id INTEGER PRIMARY KEY AUTOINCREMENT,venue TEXT,severity TEXT,title TEXT,status TEXT,recovery TEXT,ts INTEGER,resolved INTEGER);
CREATE TABLE IF NOT EXISTS stream_state(item_id TEXT PRIMARY KEY,status TEXT,health TEXT,delay_sec INTEGER,updated INTEGER);
CREATE TABLE IF NOT EXISTS appointment_history(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,slot_id TEXT,action TEXT,from_slot TEXT,to_slot TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS session_attendance(email TEXT,item_id TEXT,status TEXT,checkin_ts INTEGER,checkout_ts INTEGER,source TEXT,PRIMARY KEY(email,item_id));
CREATE TABLE IF NOT EXISTS partner_engagement(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,partner TEXT,kind TEXT,ref_id TEXT,consent INTEGER DEFAULT 0,ts INTEGER);
CREATE TABLE IF NOT EXISTS staff_assignments(id INTEGER PRIMARY KEY AUTOINCREMENT,staff_name TEXT,role TEXT,venue TEXT,shift_start TEXT,shift_end TEXT,status TEXT,updated INTEGER);
CREATE TABLE IF NOT EXISTS speaker_readiness(speaker_id TEXT,item_id TEXT,status TEXT,checkin INTEGER DEFAULT 0,briefed INTEGER DEFAULT 0,mic INTEGER DEFAULT 0,slides INTEGER DEFAULT 0,updated INTEGER,PRIMARY KEY(speaker_id,item_id));
CREATE TABLE IF NOT EXISTS ops_broadcasts(id INTEGER PRIMARY KEY AUTOINCREMENT,audience TEXT,venue TEXT,title TEXT,body TEXT,status TEXT,ts INTEGER);\nCREATE TABLE IF NOT EXISTS passport(email TEXT PRIMARY KEY,content INTEGER DEFAULT 0,event INTEGER DEFAULT 0,network INTEGER DEFAULT 0,partner INTEGER DEFAULT 0,updated INTEGER);
CREATE TABLE IF NOT EXISTS journeys(email TEXT PRIMARY KEY,attended INTEGER DEFAULT 0,replay INTEGER DEFAULT 0,club INTEGER DEFAULT 0,updated INTEGER);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,kind TEXT,title TEXT,body TEXT,seen INTEGER DEFAULT 0,ts INTEGER);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,actor TEXT,payload TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS cms(id TEXT PRIMARY KEY,status TEXT,version INTEGER,updated INTEGER);""")
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
  c.executemany("INSERT OR IGNORE INTO program_items(id,start,end,venue,track,format,title,audience,capacity,stream,replay,partner) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",program)
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
  c.executemany("INSERT OR IGNORE INTO program_items(id,start,end,venue,track,format,title,audience,capacity,stream,replay,partner) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",extended_program)
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
  c.executemany("INSERT OR IGNORE INTO appointment_slots(id,item_id,start,end,capacity,partner_id) VALUES(?,?,?,?,?,?)",slots)
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
  ensure_demo_accounts(c)
  ensure_integration_gates(c)
  ensure_demo_asset(c)
  ensure_legacy_demo_publications(c)
  rebuild_search_projection(c)
  c.commit(); c.close()

def sval(c,k,default=""):
 r=c.execute("SELECT v FROM state WHERE k=?",(k,)).fetchone(); return r["v"] if r else default

def setv(c,k,v):
 c.execute("INSERT INTO state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(k,str(v)))

def audit(c,kind,actor,payload=None):
 c.execute("INSERT INTO events(kind,actor,payload,ts) VALUES(?,?,?,?)",(kind,actor,json.dumps(payload or {},ensure_ascii=False),int(time.time())))

def notify(c,email,kind,title,body):
 row=c.execute("INSERT INTO notifications(email,kind,title,body,seen,ts) VALUES(?,?,?,?,0,?) RETURNING id",(email,kind,title,body,int(time.time()))).fetchone()
 if row: notification_delivery.queue(c,row["id"],email,kind)
 audit(c,"notification_created","system",{"email":email,"kind":kind,"title":title})

def promote_waitlist(c,sid="S2"):
 nxt=c.execute("SELECT email FROM bookings WHERE session_id=? AND status='waitlist' ORDER BY ts,email LIMIT 1",(sid,)).fetchone()
 if not nxt: return None
 c.execute("UPDATE bookings SET status='booked',ts=? WHERE email=? AND session_id=?",(int(time.time()),nxt["email"],sid))
 setv(c,"occupied",int(sval(c,"occupied","0"))+1)
 notify(c,nxt["email"],"waitlist_promoted","Вы в программе","Освободилось место. Бронь подтверждена автоматически.")
 audit(c,"waitlist_promoted","system",{"email":nxt["email"],"session_id":sid})
 return nxt["email"]

def commercial(c):
 kinds={r["kind"]:r["n"] for r in c.execute("SELECT kind,COUNT(*) n FROM events GROUP BY kind")}
 regs=c.execute("SELECT COUNT(*) n FROM registrations").fetchone()["n"]
 checkins=c.execute("SELECT COUNT(*) n FROM checkins").fetchone()["n"]
 leads=c.execute("SELECT COUNT(*) n FROM leads WHERE status='new'").fetchone()["n"]
 replay=c.execute("SELECT COUNT(*) n FROM journeys WHERE replay=1").fetchone()["n"]
 wait=c.execute("SELECT COUNT(*) n FROM bookings WHERE status='waitlist'").fetchone()["n"]
 booked=c.execute("SELECT COUNT(*) n FROM bookings WHERE status='booked'").fetchone()["n"]
 return {
  "registrations":regs,"attendance":checkins,"booked":booked,"waitlist":wait,
  "voluntary_leads":leads,"post_event_replay":replay,
  "attendance_rate":round(checkins/regs*100,1) if regs else 0,
  "lead_rate":round(leads/checkins*100,1) if checkins else 0,
  "event_counts":kinds
 }

def state(c,email=None):
 d={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM state")}
 d.update(commercial(c))
 d["checkins"]=d["attendance"]; d["leads"]=d["voluntary_leads"]; d["post_event"]=d["post_event_replay"]
 d["questions"]=c.execute("SELECT COUNT(*) n FROM questions").fetchone()["n"]
 d["program"]=[dict(r) for r in c.execute("SELECT * FROM program_items ORDER BY start,venue")]
 d["speakers"]=[dict(r) for r in c.execute("SELECT * FROM speakers ORDER BY name")]
 d["partners"]=[dict(r) for r in c.execute("SELECT * FROM partners ORDER BY name")]
 d["products"]=[dict(r) for r in c.execute("SELECT * FROM product_catalog ORDER BY id")]
 d["content_catalog"]=[dict(r) for r in c.execute("SELECT * FROM content_catalog ORDER BY id")]
 d["partner_packages"]=[dict(r) for r in c.execute("SELECT * FROM partner_packages ORDER BY id")]
 d["studio_episodes"]=[dict(r) for r in c.execute("SELECT e.*,s.name speaker_name,s.role speaker_role FROM studio_episodes e LEFT JOIN speakers s ON s.id=e.speaker_id ORDER BY e.id")]
 d["community_threads"]=[dict(r) for r in c.execute("SELECT t.*,COUNT(p.id) post_count FROM community_threads t LEFT JOIN community_posts p ON p.thread_id=t.id AND p.status IN ('published_demo','pending_moderation') GROUP BY t.id ORDER BY t.id")]
 d["learning_tracks"]=[dict(r) for r in c.execute("SELECT * FROM learning_tracks ORDER BY id")]
 d["learning_steps"]=[dict(r) for r in c.execute("SELECT * FROM learning_steps ORDER BY track_id,step_no")]
 d["session_speakers"]=[dict(r) for r in c.execute("SELECT ss.item_id,s.id,s.name,s.role,s.org,s.kind FROM session_speakers ss JOIN speakers s ON s.id=ss.speaker_id ORDER BY ss.item_id,s.name")]
 d["appointment_slots"]=[dict(r) for r in c.execute("SELECT a.*,p.name partner_name FROM appointment_slots a LEFT JOIN partners p ON p.id=a.partner_id ORDER BY a.start")]
 d["venue_state"]=[dict(r) for r in c.execute("SELECT venue,capacity,occupied,status,next_change,updated FROM venue_state ORDER BY venue")]
 d["stream_state"]=[dict(r) for r in c.execute("SELECT item_id,status,health,delay_sec,updated FROM stream_state ORDER BY item_id")]
 d["incidents"]=[dict(r) for r in c.execute("SELECT id,venue,severity,title,status,recovery,ts,resolved FROM incidents ORDER BY id DESC LIMIT 20")]
 d["staff_assignments"]=[dict(r) for r in c.execute("SELECT id,staff_name,role,venue,shift_start,shift_end,status,updated FROM staff_assignments ORDER BY venue,role")]
 d["speaker_readiness"]=[dict(r) for r in c.execute("SELECT r.speaker_id,r.item_id,r.status,r.checkin,r.briefed,r.mic,r.slides,r.updated,s.name,p.title,p.start,p.venue FROM speaker_readiness r JOIN speakers s ON s.id=r.speaker_id JOIN program_items p ON p.id=r.item_id ORDER BY p.start,s.name")]
 d["ops_broadcasts"]=[dict(r) for r in c.execute("SELECT id,audience,venue,title,body,status,ts FROM ops_broadcasts ORDER BY id DESC LIMIT 12")]
 if email:
  d["takeaways"]=[dict(r) for r in c.execute("SELECT id,session_id,note,source,ts FROM takeaways WHERE email=? ORDER BY id DESC LIMIT 8",(email,))]
  d["meeting_items"]=[dict(r) for r in c.execute("SELECT id,target,slot,place,status,ts FROM meetings WHERE requester=? ORDER BY id DESC LIMIT 8",(email,))]
  d["mutual_meetings"]=[dict(r) for r in c.execute("SELECT id,requester,target_email,target_name,slot,place,status,requester_ok,target_ok,ts FROM mutual_meetings WHERE requester=? OR target_email=? ORDER BY id DESC LIMIT 12",(email,email))]
  d["product_interests"]=[dict(r) for r in c.execute("SELECT id,track,context,consent_version,status,ts FROM product_interests WHERE email=? ORDER BY id DESC LIMIT 8",(email,))]
  d["followups"]=[dict(r) for r in c.execute("SELECT day,track,status,ts FROM followups WHERE email=? ORDER BY day,id",(email,))]
  d["activity_bookings"]=[dict(r) for r in c.execute("SELECT b.item_id,b.status,p.start,p.end,p.venue,p.title,p.format FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.email=? ORDER BY p.start",(email,))]
  d["appointment_bookings"]=[dict(r) for r in c.execute("SELECT b.slot_id,b.status,a.item_id,a.start,a.end,p.name partner_name FROM appointment_bookings b JOIN appointment_slots a ON a.id=b.slot_id LEFT JOIN partners p ON p.id=a.partner_id WHERE b.email=? ORDER BY a.start",(email,))]
  d["appointment_history"]=[dict(r) for r in c.execute("SELECT action,from_slot,to_slot,ts FROM appointment_history WHERE email=? ORDER BY id DESC LIMIT 10",(email,))]
  d["session_attendance"]=[dict(r) for r in c.execute("SELECT a.item_id,a.status,a.checkin_ts,a.checkout_ts,a.source,p.title,p.venue,p.track FROM session_attendance a JOIN program_items p ON p.id=a.item_id WHERE a.email=? ORDER BY a.checkin_ts DESC",(email,))]
  d["partner_engagement"]=[dict(r) for r in c.execute("SELECT partner,kind,ref_id,consent,ts FROM partner_engagement WHERE email=? ORDER BY id DESC LIMIT 12",(email,))]
  d["challenges"]=[dict(r) for r in c.execute("SELECT challenge_id,status,days_required,started,verified,reward FROM challenges WHERE email=?",(email,))]
  d["challenge_actions"]=[dict(r) for r in c.execute("SELECT challenge_id,action_id,label,status,ts FROM challenge_actions WHERE email=? ORDER BY action_id",(email,))]
  d["topic_subscriptions"]=[dict(r) for r in c.execute("SELECT topic,status,ts FROM topic_subscriptions WHERE email=? ORDER BY topic",(email,))]
  d["expert_follows"]=[dict(r) for r in c.execute("SELECT f.speaker_id,f.status,f.ts,s.name,s.role,s.org FROM expert_follows f JOIN speakers s ON s.id=f.speaker_id WHERE f.email=? ORDER BY s.name",(email,))]
  d["learning_enrollments"]=[dict(r) for r in c.execute("SELECT e.track_id,e.status,e.current_step,e.started,e.updated,t.title,t.duration_days,t.topic,(SELECT COUNT(*) FROM learning_steps ls WHERE ls.track_id=e.track_id) total_steps FROM learning_enrollments e JOIN learning_tracks t ON t.id=e.track_id WHERE e.email=? ORDER BY e.updated DESC",(email,))]
  d["community_posts"]=[dict(r) for r in c.execute("SELECT id,thread_id,body,status,ts FROM community_posts WHERE email=? ORDER BY id DESC LIMIT 12",(email,))]
  rel="registered"
  if c.execute("SELECT 1 FROM checkins WHERE ticket='DEMO-2027-001'").fetchone(): rel="attended"
  if c.execute("SELECT 1 FROM journeys WHERE email=? AND (replay=1 OR club=1)",(email,)).fetchone(): rel="continuing"
  if c.execute("SELECT 1 FROM product_interests WHERE email=?",(email,)).fetchone(): rel="consented_interest"
  d["relationship_stage"]=rel
 p=c.execute("SELECT status,name FROM placements WHERE id=1").fetchone()
 d["placement_status"]=p["status"] if p else "contracted"
 row=c.execute("SELECT status,version FROM cms WHERE id='A-014'").fetchone()
 d["cms_status"]=row["status"]; d["cms_version"]=row["version"]
 if email:
  b=c.execute("SELECT status FROM bookings WHERE email=? AND session_id='S2'",(email,)).fetchone()
  d["my_booking"]=b["status"] if b else None
  n=c.execute("SELECT id,kind,title,body,seen,ts FROM notifications WHERE email=? ORDER BY id DESC LIMIT 5",(email,))
  d["notifications"]=[dict(x) for x in n]
  pr=c.execute("SELECT intent,interests,networking,visibility FROM attendee_profiles WHERE email=?",(email,)).fetchone()
  d["profile"]=dict(pr) if pr else None
  pp=c.execute("SELECT content,event,network,partner FROM passport WHERE email=?",(email,)).fetchone()
  d["passport"]=dict(pp) if pp else {"content":0,"event":0,"network":0,"partner":0}
  d["meetings"]=c.execute("SELECT COUNT(*) n FROM meetings WHERE requester=? AND status IN ('requested','confirmed')",(email,)).fetchone()["n"]
 d["server_time"]=int(time.time())
 return d

def reset_demo(c,actor):
 for t in ("checkins","leads","registrations","bookings","questions","journeys","notifications","events","meetings","session_feedback","takeaways","product_interests","followups","topic_subscriptions","expert_follows","learning_enrollments","community_posts"):
  c.execute("DELETE FROM "+t)
 for k,v in {"session_time":"11:00","session_room":"Лекторий","live_state":"scheduled","occupied":"116","capacity":"120","phase":"before","change_seq":"0","gift_issued":"0","demo_step":"0"}.items(): setv(c,k,v)
 setv(c,"demo_run",int(sval(c,"demo_run","0"))+1)
 c.execute("UPDATE placements SET status='contracted',leads=0,ts=? WHERE id=1",(int(time.time()),))
 c.execute("UPDATE deliverables SET status='contracted',evidence='',updated=?",(int(time.time()),))
 c.execute("UPDATE passport SET content=0,event=0,network=0,partner=0,updated=?",(int(time.time()),))
 c.execute("UPDATE cms SET status='medical_review',version=1,updated=? WHERE id='A-014'",(int(time.time()),))
 c.execute("INSERT OR REPLACE INTO registrations(email,status,ts) VALUES('participant@demo.ru','confirmed',?)",(int(time.time()),))
 audit(c,"demo_reset",actor,{"run":sval(c,"demo_run")})

def run_demo_step(c,step,actor):
 now=int(time.time())
 if step==1:
  setv(c,"occupied",120); setv(c,"capacity",120); setv(c,"phase","during")
  audit(c,"venue_full",actor,{"occupied":120,"capacity":120})
 elif step==2:
  for e in ("participant2@demo.ru","participant3@demo.ru"):
   c.execute("INSERT OR REPLACE INTO registrations(email,status,ts) VALUES(?,'confirmed',?)",(e,now))
   c.execute("INSERT OR REPLACE INTO bookings(email,session_id,status,ts) VALUES(?,'S2','waitlist',?)",(e,now))
   audit(c,"booking_waitlist",e,{"session_id":"S2"})
 elif step==3:
  setv(c,"occupied",119); audit(c,"seat_released",actor,{"session_id":"S2"})
  promote_waitlist(c,"S2")
 elif step==4:
  setv(c,"session_time","11:30"); setv(c,"session_room","Зал «Практика»"); setv(c,"change_seq",int(sval(c,"change_seq","0"))+1)
  for e in ("participant@demo.ru","participant2@demo.ru","participant3@demo.ru"):
   notify(c,e,"schedule_changed","Изменение программы","«Как читать исследования» перенесена на 11:30 · зал «Практика».")
  audit(c,"schedule_changed",actor,{"time":"11:30","room":"Зал «Практика»"})
 elif step==5:
  setv(c,"live_state","pause"); audit(c,"live_state",actor,{"state":"pause"})
 elif step==6:
  setv(c,"live_state","live"); audit(c,"live_state",actor,{"state":"live"})
 elif step==7:
  setv(c,"live_state","replay"); setv(c,"phase","after"); audit(c,"live_state",actor,{"state":"replay"})
 elif step==8:
  c.execute("INSERT OR IGNORE INTO checkins(ticket,ts,staff) VALUES('DEMO-2027-001',?,'staff@demo.ru')",(now,))
  audit(c,"checkin","staff@demo.ru",{"ticket":"DEMO-2027-001"})
 elif step==9:
  c.execute("UPDATE placements SET status='active',ts=? WHERE id=1",(now,))
  c.execute("UPDATE deliverables SET status='delivered',evidence='demo_run:event:placement_active',updated=? WHERE id IN ('PL-01','PL-02')",(now,))
  audit(c,"placement_active","partner@demo.ru",{"placement_id":1})
 elif step==10:
  c.execute("INSERT INTO leads(kind,status,ts) VALUES('materials','new',?)",(now,))
  c.execute("UPDATE placements SET leads=leads+1 WHERE id=1")
  c.execute("UPDATE deliverables SET status='delivered',evidence='demo_run:event:voluntary_lead',updated=? WHERE id='PL-04'",(now,))
  audit(c,"voluntary_lead","participant@demo.ru",{"kind":"materials","consent":True,"recipient":"demo_partner"})
 elif step==11:
  c.execute("INSERT OR REPLACE INTO journeys(email,attended,replay,club,updated) VALUES('participant@demo.ru',1,1,0,?)",(now,))
  c.execute("UPDATE deliverables SET status='delivered',evidence='demo_run:event:journey_replay',updated=? WHERE id='PL-03'",(now,))
  audit(c,"journey_attended","participant@demo.ru",{}); audit(c,"journey_replay","participant@demo.ru",{})
 else:
  raise ValueError("bad_step")
 setv(c,"demo_step",step)

def auth(h):
 c=conn()
 try: return authenticate_headers(c,h.headers)
 finally: c.close()

def body(h):
 n=int(h.headers.get("Content-Length","0") or 0); return json.loads(h.rfile.read(n) or b"{}")

class H(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=ROOT,**kw)
 def cors(self):
  self.send_header("Access-Control-Allow-Origin","https://sostoyanie-promomed-preview.onrender.com")
  self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type, X-Step-Up-Token, X-Correlation-ID")
  self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
 def out(self,obj,status=200):
  b=json.dumps(obj,ensure_ascii=False).encode(); set_response_status(status); self.send_response(status)
  self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Cache-Control","no-store"); self.cors()
  self.send_header("X-Correlation-ID",getattr(self,"_correlation_id",""))
  self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
 def do_OPTIONS(self):
  self.send_response(204); self.cors(); self.end_headers()
 def do_GET(self):
  p=urlparse(self.path).path; a=auth(self)
  if p=="/health":
   ds=db_status(); ms=migration_status()
   return self.out({"ok":True,"app":"sostoyanie-v20-integration","authority":ds["backend"],"durable":ds["durable"],"golden_demo":True,"migrations_pending":ms["pending"]})
  if p=="/ready":
   ds=db_status(); ms=migration_status(); ready=bool(ds["durable"] and not ms["pending"])
   return self.out({"ready":ready,"database":ds,"migrations":ms},200 if ready else 503)
  ic=conn()
  try:
   ir=integration_get(self.path,a,ic)
   if ir is not None:
    ic.commit()
    return self.out(ir["payload"],ir["status"])
  finally: ic.close()
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
     "learning_steps":c.execute("SELECT COUNT(*) n FROM learning_steps").fetchone()["n"]
    },
    "journey":["studio","expert","topic_hub","community","event","replay","learning_track"],
    "guardrails":["community moderation","medical/editorial disclosure","no personalized treatment advice","explicit follow and subscription actions"],
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
   partner_desk=[dict(r) for r in c.execute("SELECT pr.name partner,a.id slot_id,a.start,a.end,p.venue,p.title,COUNT(CASE WHEN b.status='booked' THEN 1 END) booked,COUNT(CASE WHEN b.status='waitlist' THEN 1 END) waitlist,a.capacity FROM appointment_slots a JOIN program_items p ON p.id=a.item_id LEFT JOIN partners pr ON pr.id=a.partner_id LEFT JOIN appointment_bookings b ON b.slot_id=a.id GROUP BY pr.name,a.id,a.start,a.end,p.venue,p.title,a.capacity ORDER BY a.start")]
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
    rec=authenticate_password(c,email,pw)
    if not rec: return self.out({"error":"invalid_credentials"},401)
    token=create_session(c,rec[2],rec[0],rec[1]); c.commit()
    return self.out({"token":token,"role":rec[0],"name":rec[1]})
   finally: c.close()
  pc=conn()
  try:
   pir=integration_public_post(self.path,data,self.headers,pc)
   if pir is not None:
    pc.commit()
    return self.out(pir["payload"],pir["status"])
  finally: pc.close()
  a=auth(self)
  if not a: return self.out({"error":"unauthorized"},401)
  role,name,email=a
  with LOCK:
   c=conn()
   try:
    ir=integration_post(self.path,data,a,c,self.headers)
    if ir is not None:
     c.commit()
     return self.out(ir["payload"],ir["status"])
    if p=="/api/demo/reset":
     if role not in ("sales","organizer"): return self.out({"error":"forbidden"},403)
     reset_demo(c,email)
    elif p=="/api/demo/next":
     if role not in ("sales","organizer"): return self.out({"error":"forbidden"},403)
     cur=int(sval(c,"demo_step","0")); nxt=cur+1
     if nxt>=len(DEMO_STEPS): return self.out({"error":"demo_complete","dashboard":commercial(c)},409)
     run_demo_step(c,nxt,email)
    elif p=="/api/follow-expert":
     if role!="participant": return self.out({"error":"forbidden"},403)
     speaker_id=str(data.get("speaker_id",""))[:20]; action=str(data.get("action","follow"))
     speaker=c.execute("SELECT id,name FROM speakers WHERE id=?",(speaker_id,)).fetchone()
     if not speaker: return self.out({"error":"speaker_not_found"},404)
     if action=="unfollow":
      c.execute("DELETE FROM expert_follows WHERE email=? AND speaker_id=?",(email,speaker_id)); audit(c,"expert_unfollowed",email,{"speaker_id":speaker_id})
     else:
      c.execute("INSERT INTO expert_follows(email,speaker_id,status,ts) VALUES(?,?,'active',?) ON CONFLICT(email,speaker_id) DO UPDATE SET status='active',ts=excluded.ts",(email,speaker_id,int(time.time())))
      notify(c,email,"expert_followed","Вы подписались на эксперта",speaker["name"]+" · новые материалы и эфиры появятся в вашем маршруте.")
      audit(c,"expert_followed",email,{"speaker_id":speaker_id})
    elif p=="/api/subscribe-topic":
     if role!="participant": return self.out({"error":"forbidden"},403)
     topic=str(data.get("topic",""))[:120].strip(); action=str(data.get("action","subscribe"))
     allowed={r["topic"] for r in c.execute("SELECT DISTINCT topic FROM community_threads")}
     if topic not in allowed: return self.out({"error":"topic_not_found"},404)
     if action=="unsubscribe":
      c.execute("DELETE FROM topic_subscriptions WHERE email=? AND topic=?",(email,topic)); audit(c,"topic_unsubscribed",email,{"topic":topic})
     else:
      c.execute("INSERT INTO topic_subscriptions(email,topic,status,ts) VALUES(?,?,'active',?) ON CONFLICT(email,topic) DO UPDATE SET status='active',ts=excluded.ts",(email,topic,int(time.time())))
      notify(c,email,"topic_subscribed","Тема добавлена в ваш маршрут",topic+" · Studio, материалы, события и обсуждения будут собираться вместе.")
      audit(c,"topic_subscribed",email,{"topic":topic})
    elif p=="/api/community-post":
     if role!="participant": return self.out({"error":"forbidden"},403)
     thread_id=str(data.get("thread_id",""))[:20]; text=str(data.get("body","")).strip()[:800]
     thread=c.execute("SELECT id,title FROM community_threads WHERE id=? AND status='open'",(thread_id,)).fetchone()
     if not thread: return self.out({"error":"thread_not_found"},404)
     if len(text)<8: return self.out({"error":"post_too_short"},400)
     c.execute("INSERT INTO community_posts(thread_id,email,body,status,ts) VALUES(?,?,?,'pending_moderation',?)",(thread_id,email,text,int(time.time())))
     notify(c,email,"community_post","Вопрос отправлен на модерацию",thread["title"]+" · после проверки он появится в обсуждении.")
     audit(c,"community_post_submitted",email,{"thread_id":thread_id})
    elif p=="/api/learning":
     if role!="participant": return self.out({"error":"forbidden"},403)
     track_id=str(data.get("track_id",""))[:20]; action=str(data.get("action","enroll"))
     track=c.execute("SELECT id,title FROM learning_tracks WHERE id=?",(track_id,)).fetchone()
     if not track: return self.out({"error":"learning_track_not_found"},404)
     total=c.execute("SELECT COUNT(*) n FROM learning_steps WHERE track_id=?",(track_id,)).fetchone()["n"]
     if action=="enroll":
      c.execute("INSERT INTO learning_enrollments(email,track_id,status,current_step,started,updated) VALUES(?,?,'active',0,?,?) ON CONFLICT(email,track_id) DO UPDATE SET status='active',updated=excluded.updated",(email,track_id,int(time.time()),int(time.time())))
      notify(c,email,"learning_enrolled","Маршрут начат",track["title"]+" · прогресс сохраняется в профиле.")
      audit(c,"learning_enrolled",email,{"track_id":track_id})
     elif action=="advance":
      row=c.execute("SELECT current_step,status FROM learning_enrollments WHERE email=? AND track_id=?",(email,track_id)).fetchone()
      if not row: return self.out({"error":"learning_not_enrolled"},409)
      new_step=min(total,int(row["current_step"])+1)
      status="completed" if total and new_step>=total else "active"
      c.execute("UPDATE learning_enrollments SET current_step=?,status=?,updated=? WHERE email=? AND track_id=?",(new_step,status,int(time.time()),email,track_id))
      if status=="completed": notify(c,email,"learning_completed","Маршрут завершён",track["title"]+" · материалы и replay остаются в вашем профиле.")
      audit(c,"learning_advanced",email,{"track_id":track_id,"current_step":new_step,"total_steps":total,"status":status})
     else: return self.out({"error":"bad_action"},400)
    elif p=="/api/move-session":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     t=str(data.get("time","11:30")); room=str(data.get("room","Лекторий"))[:80]
     setv(c,"session_time",t); setv(c,"session_room",room); setv(c,"change_seq",int(sval(c,"change_seq","0"))+1)
     for e in ("participant@demo.ru","participant2@demo.ru","participant3@demo.ru"): notify(c,e,"schedule_changed","Изменение программы",f"Новая площадка: {t} · {room}.")
     audit(c,"schedule_changed",email,{"time":t,"room":room})
    elif p=="/api/live":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     v=str(data.get("state","live"))
     if v not in ("scheduled","live","pause","ended","replay"): return self.out({"error":"bad_state"},400)
     setv(c,"live_state",v); audit(c,"live_state",email,{"state":v})
    elif p=="/api/checkin":
     if role!="staff": return self.out({"error":"forbidden"},403)
     ticket=str(data.get("ticket","DEMO-2027-001"))
     try: c.execute("INSERT INTO checkins(ticket,ts,staff) VALUES(?,?,?)",(ticket,int(time.time()),email)); audit(c,"checkin",email,{"ticket":ticket}); result="valid"
     except sqlite3.IntegrityError: result="duplicate"
     c.commit(); d=state(c,email); d["scan_result"]=result; return self.out(d,200 if result=="valid" else 409)
    elif p=="/api/register":
     if role!="participant": return self.out({"error":"forbidden"},403)
     c.execute("INSERT OR REPLACE INTO registrations(email,status,ts) VALUES(?,'confirmed',?)",(email,int(time.time()))); audit(c,"registration",email,{})
    elif p=="/api/booking":
     if role!="participant": return self.out({"error":"forbidden"},403)
     sid=str(data.get("session_id","S2")); action=str(data.get("action","book"))
     if action=="cancel":
      old=c.execute("SELECT status FROM bookings WHERE email=? AND session_id=?",(email,sid)).fetchone(); c.execute("DELETE FROM bookings WHERE email=? AND session_id=?",(email,sid))
      if old and old["status"]=="booked":
       setv(c,"occupied",max(0,int(sval(c,"occupied","0"))-1)); promote_waitlist(c,sid)
      audit(c,"booking_cancelled",email,{"session_id":sid})
     else:
      existing=c.execute("SELECT status FROM bookings WHERE email=? AND session_id=?",(email,sid)).fetchone()
      if not existing:
       status="booked" if int(sval(c,"occupied","0"))<int(sval(c,"capacity","120")) else "waitlist"
       c.execute("INSERT INTO bookings(email,session_id,status,ts) VALUES(?,?,?,?)",(email,sid,status,int(time.time())))
       if status=="booked": setv(c,"occupied",int(sval(c,"occupied","0"))+1)
       audit(c,"booking_"+status,email,{"session_id":sid})
    elif p=="/api/activity-booking":
     if role!="participant": return self.out({"error":"forbidden"},403)
     item_id=str(data.get("item_id",""))[:20]; action=str(data.get("action","book"))
     item=c.execute("SELECT * FROM program_items WHERE id=?",(item_id,)).fetchone()
     if not item: return self.out({"error":"program_item_not_found"},404)
     if action=="cancel":
      old=c.execute("SELECT status FROM activity_bookings WHERE email=? AND item_id=?",(email,item_id)).fetchone()
      c.execute("DELETE FROM activity_bookings WHERE email=? AND item_id=?",(email,item_id))
      if old and old["status"]=="booked":
       waiter=c.execute("SELECT email FROM activity_bookings WHERE item_id=? AND status='waitlist' ORDER BY ts,email LIMIT 1",(item_id,)).fetchone()
       if waiter:
        c.execute("UPDATE activity_bookings SET status='booked',ts=? WHERE email=? AND item_id=?",(int(time.time()),waiter["email"],item_id))
        notify(c,waiter["email"],"activity_promoted","Освободилось место",item["start"]+" · "+item["venue"]+" · "+item["title"])
        audit(c,"activity_waitlist_promoted",waiter["email"],{"item_id":item_id})
      audit(c,"activity_cancelled",email,{"item_id":item_id})
     else:
      conflict=c.execute("SELECT p.id,p.start,p.end,p.title,p.venue FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.email=? AND b.status='booked' AND p.id<>? AND p.start<? AND p.end>?",(email,item_id,item["end"],item["start"])).fetchone()
      if conflict: return self.out({"error":"schedule_conflict","conflict":dict(conflict),"requested":{"id":item["id"],"start":item["start"],"end":item["end"],"title":item["title"],"venue":item["venue"]}},409)
      current=c.execute("SELECT COUNT(*) n FROM activity_bookings WHERE item_id=? AND status='booked'",(item_id,)).fetchone()["n"]
      status="booked" if current<int(item["capacity"]) else "waitlist"
      c.execute("INSERT INTO activity_bookings(email,item_id,status,ts) VALUES(?,?,?,?) ON CONFLICT(email,item_id) DO UPDATE SET status=excluded.status,ts=excluded.ts",(email,item_id,status,int(time.time())))
      audit(c,"activity_"+status,email,{"item_id":item_id,"venue":item["venue"],"format":item["format"]})
      notify(c,email,"activity_"+status,"Запись в программу",item["start"]+" · "+item["venue"]+" · "+item["title"])
    elif p=="/api/challenge":
     if role!="participant": return self.out({"error":"forbidden"},403)
     cid=str(data.get("challenge_id","health30"))[:40]; action=str(data.get("action","start"))
     if action=="start":
      reward="Гарантированный partner benefit после подтверждения условий; не связан с покупкой лекарства"
      c.execute("INSERT INTO challenges(email,challenge_id,status,days_required,started,verified,reward) VALUES(?,?,'active',30,?,0,?) ON CONFLICT(email,challenge_id) DO UPDATE SET status='active',started=excluded.started,reward=excluded.reward",(email,cid,int(time.time()),reward))
      for aid,label in [("01_platform","Подписка на СОСТОЯНИЕ"),("02_promomed","Выбранный публичный канал Промомед"),("03_partner","Выбранный канал партнёра"),("04_content","Контент / эфир в течение маршрута"),("05_day30","Финальная проверка на 30-й день")]:
       c.execute("INSERT OR IGNORE INTO challenge_actions(email,challenge_id,action_id,label,status,ts) VALUES(?,?,?,?,'planned',?)",(email,cid,aid,label,int(time.time())))
      audit(c,"challenge_started",email,{"challenge_id":cid,"days":30})
      notify(c,email,"challenge_started","30 дней СОСТОЯНИЯ","Подписки и действия подтверждаются по опубликованным правилам. Награда не зависит от покупки лекарств.")
     elif action=="check":
      aid=str(data.get("action_id",""))[:40]
      row=c.execute("SELECT 1 FROM challenge_actions WHERE email=? AND challenge_id=? AND action_id=?",(email,cid,aid)).fetchone()
      if not row: return self.out({"error":"challenge_action_not_found"},404)
      c.execute("UPDATE challenge_actions SET status='confirmed_demo',ts=? WHERE email=? AND challenge_id=? AND action_id=?",(int(time.time()),email,cid,aid))
      audit(c,"challenge_action_confirmed",email,{"challenge_id":cid,"action_id":aid})
     elif action=="verify_demo":
      remaining=c.execute("SELECT COUNT(*) n FROM challenge_actions WHERE email=? AND challenge_id=? AND status!='confirmed_demo'",(email,cid)).fetchone()["n"]
      if remaining: return self.out({"error":"challenge_incomplete","remaining":remaining},409)
      c.execute("UPDATE challenges SET status='completed',verified=? WHERE email=? AND challenge_id=?",(int(time.time()),email,cid))
      audit(c,"challenge_completed",email,{"challenge_id":cid})
     else: return self.out({"error":"bad_action"},400)
    elif p=="/api/appointment-booking":
     if role!="participant": return self.out({"error":"forbidden"},403)
     slot_id=str(data.get("slot_id",""))[:20]
     slot=c.execute("SELECT a.*,p.title,p.venue FROM appointment_slots a JOIN program_items p ON p.id=a.item_id WHERE a.id=?",(slot_id,)).fetchone()
     if not slot: return self.out({"error":"slot_not_found"},404)
     conflict=c.execute("SELECT 1 FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.email=? AND b.status='booked' AND p.start<? AND p.end>?",(email,slot["end"],slot["start"])).fetchone()
     if conflict: return self.out({"error":"schedule_conflict"},409)
     used=c.execute("SELECT COUNT(*) n FROM appointment_bookings WHERE slot_id=? AND status='booked'",(slot_id,)).fetchone()["n"]
     status="booked" if used<int(slot["capacity"]) else "waitlist"
     c.execute("INSERT INTO appointment_bookings(email,slot_id,status,ts) VALUES(?,?,?,?) ON CONFLICT(email,slot_id) DO UPDATE SET status=excluded.status,ts=excluded.ts",(email,slot_id,status,int(time.time())))
     audit(c,"appointment_"+status,email,{"slot_id":slot_id,"item_id":slot["item_id"]})
     partner_name=c.execute("SELECT pr.name FROM appointment_slots a JOIN partners pr ON pr.id=a.partner_id WHERE a.id=?",(slot_id,)).fetchone()
     c.execute("INSERT INTO partner_engagement(email,partner,kind,ref_id,consent,ts) VALUES(?,?,?,?,0,?)",(email,partner_name["name"] if partner_name else "partner","appointment_"+status,slot_id,int(time.time())))
     notify(c,email,"appointment_"+status,"Запись к партнёру",slot["start"]+" · "+slot["venue"]+" · "+slot["title"])
    elif p=="/api/replay":
     item_id=str(data.get("item_id","P05"))[:20]
     item=c.execute("SELECT id,title,venue,track,partner,replay FROM program_items WHERE id=?",(item_id,)).fetchone()
     if not item: return self.out({"error":"program_item_not_found"},404)
     chapters=[dict(r) for r in c.execute("SELECT offset_sec,title,kind FROM replay_chapters WHERE item_id=? ORDER BY offset_sec",(item_id,))]
     broadcast=c.execute("SELECT * FROM media_broadcasts WHERE item_id=? ORDER BY updated_at DESC LIMIT 1",(item_id,)).fetchone()
     transcript_segments=[]; approved_takeaways=[]; transcript_status="not_available"
     if broadcast:
      job=c.execute("SELECT * FROM transcript_jobs WHERE media_id=? ORDER BY updated_at DESC LIMIT 1",(broadcast["id"],)).fetchone()
      if job:
       transcript_segments=[dict(r) for r in c.execute("SELECT start_ms,end_ms,speaker,text,source_hash FROM transcript_segments WHERE job_id=? ORDER BY start_ms",(job["id"],))]
       approved_takeaways=[dict(r) for r in c.execute("SELECT start_ms,end_ms,text,reviewed_by,reviewed_at FROM generated_takeaways WHERE job_id=? AND state='approved' ORDER BY start_ms",(job["id"],))]
       transcript_status=job["state"]
     if role=="participant":
      c.execute("INSERT OR IGNORE INTO journeys(email,updated) VALUES(?,?)",(email,int(time.time())))
      c.execute("UPDATE journeys SET replay=1,updated=? WHERE email=?",(int(time.time()),email)); audit(c,"replay_opened",email,{"item_id":item_id})
     c.commit(); return self.out({
      "item":dict(item),"chapters":chapters,
      "media":dict(broadcast) if broadcast else None,
      "transcript_segments":transcript_segments,
      "approved_takeaways":approved_takeaways,
      "transcript_status":transcript_status,
      "transcript_notice":"Транскрипт и тезисы публикуются только после source-lineage и human review.",
      "related":["A-014","next_live_demo"]
     })
    elif p=="/api/session-attendance":
     if role not in ("participant","staff","organizer"): return self.out({"error":"forbidden"},403)
     item_id=str(data.get("item_id",""))[:20]; action=str(data.get("action","checkin"))
     item=c.execute("SELECT id,title,venue,track,partner FROM program_items WHERE id=?",(item_id,)).fetchone()
     if not item: return self.out({"error":"program_item_not_found"},404)
     target=email
     if role in ("staff","organizer") and data.get("email"): target=str(data.get("email"))[:160].lower()
     if action=="checkin":
      c.execute("INSERT INTO session_attendance(email,item_id,status,checkin_ts,checkout_ts,source) VALUES(?,?,'present',?,NULL,?) ON CONFLICT(email,item_id) DO UPDATE SET status='present',checkin_ts=excluded.checkin_ts,source=excluded.source",(target,item_id,int(time.time()),role))
      audit(c,"session_checkin",email,{"target":target,"item_id":item_id})
     elif action=="checkout":
      c.execute("UPDATE session_attendance SET status='completed',checkout_ts=? WHERE email=? AND item_id=?",(int(time.time()),target,item_id))
      audit(c,"session_checkout",email,{"target":target,"item_id":item_id})
     else:return self.out({"error":"bad_action"},400)
     c.execute("INSERT INTO partner_engagement(email,partner,kind,ref_id,consent,ts) VALUES(?,?,?,?,0,?)",(target,item["partner"],"session_"+action,item_id,int(time.time())))
    elif p=="/api/appointment-manage":
     if role!="participant": return self.out({"error":"forbidden"},403)
     action=str(data.get("action","cancel")); slot_id=str(data.get("slot_id",""))[:20]
     row=c.execute("SELECT b.status,a.start,a.end,a.item_id FROM appointment_bookings b JOIN appointment_slots a ON a.id=b.slot_id WHERE b.email=? AND b.slot_id=?",(email,slot_id)).fetchone()
     if not row: return self.out({"error":"appointment_not_found"},404)
     if action=="cancel":
      was_booked=row["status"]=="booked"
      c.execute("UPDATE appointment_bookings SET status='cancelled',ts=? WHERE email=? AND slot_id=?",(int(time.time()),email,slot_id))
      c.execute("INSERT INTO appointment_history(email,slot_id,action,from_slot,to_slot,ts) VALUES(?,?, 'cancel', ?, NULL, ?)",(email,slot_id,slot_id,int(time.time())))
      if was_booked:
       waiter=c.execute("SELECT email FROM appointment_bookings WHERE slot_id=? AND status='waitlist' ORDER BY ts LIMIT 1",(slot_id,)).fetchone()
       if waiter:
        c.execute("UPDATE appointment_bookings SET status='booked',ts=? WHERE email=? AND slot_id=?",(int(time.time()),waiter["email"],slot_id))
        notify(c,waiter["email"],"appointment_promoted","Освободилось место","Ваша запись к партнёру подтверждена.")
        audit(c,"appointment_waitlist_promoted",waiter["email"],{"slot_id":slot_id})
      audit(c,"appointment_cancelled",email,{"slot_id":slot_id})
     elif action=="reschedule":
      to_slot=str(data.get("to_slot",""))[:20]
      target=c.execute("SELECT * FROM appointment_slots WHERE id=?",(to_slot,)).fetchone()
      if not target: return self.out({"error":"slot_not_found"},404)
      conflict=c.execute("SELECT p.id,p.title,p.start,p.end,p.venue FROM activity_bookings b JOIN program_items p ON p.id=b.item_id WHERE b.email=? AND b.status='booked' AND p.start<? AND p.end>?",(email,target["end"],target["start"])).fetchone()
      if conflict:return self.out({"error":"schedule_conflict","conflict":dict(conflict),"requested":{"slot_id":to_slot,"start":target["start"],"end":target["end"]}},409)
      used=c.execute("SELECT COUNT(*) n FROM appointment_bookings WHERE slot_id=? AND status='booked'",(to_slot,)).fetchone()["n"]
      if used>=int(target["capacity"]): return self.out({"error":"slot_full"},409)
      was_booked=row["status"]=="booked"
      c.execute("UPDATE appointment_bookings SET status='cancelled',ts=? WHERE email=? AND slot_id=?",(int(time.time()),email,slot_id))
      if was_booked:
       waiter=c.execute("SELECT email FROM appointment_bookings WHERE slot_id=? AND status='waitlist' ORDER BY ts LIMIT 1",(slot_id,)).fetchone()
       if waiter:
        c.execute("UPDATE appointment_bookings SET status='booked',ts=? WHERE email=? AND slot_id=?",(int(time.time()),waiter["email"],slot_id))
        notify(c,waiter["email"],"appointment_promoted","Освободилось место","Ваша запись к партнёру подтверждена.")
      c.execute("INSERT INTO appointment_bookings(email,slot_id,status,ts) VALUES(?,?,'booked',?) ON CONFLICT(email,slot_id) DO UPDATE SET status='booked',ts=excluded.ts",(email,to_slot,int(time.time())))
      c.execute("INSERT INTO appointment_history(email,slot_id,action,from_slot,to_slot,ts) VALUES(?,?, 'reschedule', ?, ?, ?)",(email,to_slot,slot_id,to_slot,int(time.time())))
      notify(c,email,"appointment_rescheduled","Запись перенесена",target["start"]+"–"+target["end"])
      audit(c,"appointment_rescheduled",email,{"from":slot_id,"to":to_slot})
     else: return self.out({"error":"bad_action"},400)
    elif p=="/api/staff-assignment":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     action=str(data.get("action","update"))
     if action=="update":
      sid=int(data.get("id",0)); venue=str(data.get("venue",""))[:80]; status=str(data.get("status","on_shift"))[:20]
      c.execute("UPDATE staff_assignments SET venue=?,status=?,updated=? WHERE id=?",(venue,status,int(time.time()),sid))
      audit(c,"staff_assignment_updated",email,{"id":sid,"venue":venue,"status":status})
     else:return self.out({"error":"bad_action"},400)
    elif p=="/api/speaker-readiness":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     speaker_id=str(data.get("speaker_id",""))[:20]; item_id=str(data.get("item_id",""))[:20]; field=str(data.get("field","status"))
     allowed={"status","checkin","briefed","mic","slides"}
     if field not in allowed:return self.out({"error":"bad_field"},400)
     value=data.get("value")
     if field=="status": c.execute("UPDATE speaker_readiness SET status=?,updated=? WHERE speaker_id=? AND item_id=?",(str(value)[:20],int(time.time()),speaker_id,item_id))
     else: c.execute("UPDATE speaker_readiness SET "+field+"=?,updated=? WHERE speaker_id=? AND item_id=?",(1 if value else 0,int(time.time()),speaker_id,item_id))
     audit(c,"speaker_readiness_updated",email,{"speaker_id":speaker_id,"item_id":item_id,"field":field,"value":value})
    elif p=="/api/broadcast":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     audience=str(data.get("audience","participants"))[:40]; venue=str(data.get("venue","all"))[:80]; title=str(data.get("title","Обновление события"))[:120]; msg=str(data.get("body",""))[:300]
     c.execute("INSERT INTO ops_broadcasts(audience,venue,title,body,status,ts) VALUES(?,?,?,?, 'sent', ?)",(audience,venue,title,msg,int(time.time())))
     targets=("participant@demo.ru","participant2@demo.ru","participant3@demo.ru") if audience in ("participants","all") else ()
     for t in targets: notify(c,t,"ops_broadcast",title,msg)
     audit(c,"ops_broadcast_sent",email,{"audience":audience,"venue":venue,"title":title})
    elif p=="/api/venue-state":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     venue=str(data.get("venue",""))[:80]; occ=max(0,int(data.get("occupied",0))); cap=max(1,int(data.get("capacity",1))); status=str(data.get("status","open"))[:20]; nxt=str(data.get("next_change",""))[:120]
     if occ>cap:return self.out({"error":"occupied_exceeds_capacity"},409)
     c.execute("INSERT INTO venue_state(venue,capacity,occupied,status,next_change,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(venue) DO UPDATE SET capacity=excluded.capacity,occupied=excluded.occupied,status=excluded.status,next_change=excluded.next_change,updated=excluded.updated",(venue,cap,occ,status,nxt,int(time.time())))
     audit(c,"venue_state_updated",email,{"venue":venue,"occupied":occ,"capacity":cap,"status":status})
    elif p=="/api/incident":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     action=str(data.get("action","create"))
     if action=="create":
      venue=str(data.get("venue","Главная сцена"))[:80]; sev=str(data.get("severity","medium"))[:20]; title=str(data.get("title","Операционный инцидент"))[:160]; rec=str(data.get("recovery","Проверить и восстановить"))[:240]
      c.execute("INSERT INTO incidents(venue,severity,title,status,recovery,ts,resolved) VALUES(?,?,?,'open',?,?,0)",(venue,sev,title,rec,int(time.time())))
      audit(c,"incident_opened",email,{"venue":venue,"severity":sev,"title":title})
     elif action=="resolve":
      iid=int(data.get("id",0)); c.execute("UPDATE incidents SET status='resolved',resolved=? WHERE id=?",(int(time.time()),iid)); audit(c,"incident_resolved",email,{"id":iid})
     else:return self.out({"error":"bad_action"},400)
    elif p=="/api/stream-control":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     iid=str(data.get("item_id","P01"))[:20]; status=str(data.get("status","live"))[:20]; health=str(data.get("health","ok"))[:20]; delay=max(0,int(data.get("delay_sec",3)))
     c.execute("INSERT INTO stream_state(item_id,status,health,delay_sec,updated) VALUES(?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET status=excluded.status,health=excluded.health,delay_sec=excluded.delay_sec,updated=excluded.updated",(iid,status,health,delay,int(time.time())))
     audit(c,"stream_control",email,{"item_id":iid,"status":status,"health":health,"delay_sec":delay})
    elif p=="/api/venue":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     occ=max(0,int(data.get("occupied",0))); cap=max(1,int(data.get("capacity",120))); room=str(data.get("room","Лекторий"))[:80]
     if occ>cap: return self.out({"error":"occupied_exceeds_capacity"},409)
     setv(c,"occupied",occ); setv(c,"capacity",cap); setv(c,"session_room",room); setv(c,"change_seq",int(sval(c,"change_seq","0"))+1)
     audit(c,"venue_updated",email,{"occupied":occ,"capacity":cap,"room":room})
    elif p=="/api/placement":
     if role!="partner": return self.out({"error":"forbidden"},403)
     status=str(data.get("status","active"))
     if status not in ("contracted","active","ended"): return self.out({"error":"bad_status"},400)
     c.execute("UPDATE placements SET status=?,ts=? WHERE id=1",(status,int(time.time()))); audit(c,"placement_"+status,email,{})
    elif p=="/api/journey":
     if role!="participant": return self.out({"error":"forbidden"},403)
     action=str(data.get("action","replay")); c.execute("INSERT OR IGNORE INTO journeys(email,updated) VALUES(?,?)",(email,int(time.time())))
     if action not in ("attended","replay","club"): return self.out({"error":"bad_action"},400)
     c.execute("UPDATE journeys SET "+action+"=1,updated=? WHERE email=?",(int(time.time()),email)); audit(c,"journey_"+action,email,{})
    elif p=="/api/profile":
     if role!="participant": return self.out({"error":"forbidden"},403)
     intent=str(data.get("intent","Понять полезное для себя"))[:120]; interests=str(data.get("interests","сон,наука,движение"))[:240]
     networking=1 if data.get("networking",True) else 0; visibility=str(data.get("visibility","event_only"))
     if visibility not in ("private","event_only","matches_only"): return self.out({"error":"bad_visibility"},400)
     c.execute("INSERT INTO attendee_profiles(email,intent,interests,networking,visibility,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET intent=excluded.intent,interests=excluded.interests,networking=excluded.networking,visibility=excluded.visibility,updated=excluded.updated",(email,intent,interests,networking,visibility,int(time.time())))
     audit(c,"profile_updated",email,{"intent":intent,"networking":bool(networking),"visibility":visibility})
    elif p=="/api/meeting":
     if role!="participant": return self.out({"error":"forbidden"},403)
     target=str(data.get("target","Участник с похожими интересами"))[:120]; slot=str(data.get("slot","14:20"))[:20]; place=str(data.get("place","Клуб СОСТОЯНИЯ"))[:80]
     c.execute("INSERT INTO meetings(requester,target,slot,place,status,ts) VALUES(?,?,?,?, 'requested',?)",(email,target,slot,place,int(time.time())))
     c.execute("UPDATE passport SET network=1,updated=? WHERE email=?",(int(time.time()),email))
     notify(c,email,"meeting_requested","Встреча запрошена",slot+" · "+place)
     audit(c,"meeting_requested",email,{"target":target,"slot":slot,"place":place})
    elif p=="/api/mutual-meeting":
     if role!="participant": return self.out({"error":"forbidden"},403)
     action=str(data.get("action","request"))
     if action=="request":
      target_email=str(data.get("target_email","participant2@demo.ru")).lower()[:120]
      if target_email==email: return self.out({"error":"self_meeting"},409)
      target_name=str(data.get("target_name","Участник"))[:120]; slot=str(data.get("slot","14:20"))[:20]; place=str(data.get("place","Клуб СОСТОЯНИЯ"))[:80]
      overlap=c.execute("SELECT 1 FROM mutual_meetings WHERE requester=? AND slot=? AND status IN ('requested','confirmed')",(email,slot)).fetchone()
      if overlap: return self.out({"error":"meeting_slot_conflict"},409)
      c.execute("INSERT INTO mutual_meetings(requester,target_email,target_name,slot,place,status,requester_ok,target_ok,ts) VALUES(?,?,?,?,?,'requested',1,0,?)",(email,target_email,target_name,slot,place,int(time.time())))
      notify(c,target_email,"meeting_invite","Новый запрос на встречу",slot+" · "+place+" · взаимное подтверждение")
      audit(c,"mutual_meeting_requested",email,{"target_email":target_email,"slot":slot})
     else:
      mid=int(data.get("id",0))
      row=c.execute("SELECT * FROM mutual_meetings WHERE id=?",(mid,)).fetchone()
      if not row or email not in (row["requester"],row["target_email"]): return self.out({"error":"meeting_not_found"},404)
      if action=="accept":
       if email!=row["target_email"]: return self.out({"error":"target_confirmation_required"},403)
       c.execute("UPDATE mutual_meetings SET target_ok=1,status='confirmed' WHERE id=?",(mid,))
       notify(c,row["requester"],"meeting_confirmed","Встреча подтверждена",row["slot"]+" · "+row["place"])
       notify(c,row["target_email"],"meeting_confirmed","Встреча подтверждена",row["slot"]+" · "+row["place"])
       audit(c,"mutual_meeting_confirmed",email,{"id":mid})
      elif action=="cancel":
       c.execute("UPDATE mutual_meetings SET status='cancelled' WHERE id=?",(mid,)); audit(c,"mutual_meeting_cancelled",email,{"id":mid})
      else: return self.out({"error":"bad_action"},400)
    elif p=="/api/takeaway":
     if role!="participant": return self.out({"error":"forbidden"},403)
     note=str(data.get("note",""))[:240].strip()
     if not note: return self.out({"error":"note_required"},422)
     sid=str(data.get("session_id","S2"))[:30]; source=str(data.get("source","session"))[:40]
     c.execute("INSERT INTO takeaways(email,session_id,note,source,ts) VALUES(?,?,?,?,?)",(email,sid,note,source,int(time.time())))
     audit(c,"takeaway_saved",email,{"session_id":sid,"source":source})
     notify(c,email,"takeaway_saved","Сохранено в «Мои выводы»","Вернитесь к мысли после события — она останется рядом с записью и источниками.")
    elif p=="/api/meeting-action":
     if role!="participant": return self.out({"error":"forbidden"},403)
     mid=int(data.get("id",0)); action=str(data.get("action","cancel"))
     row=c.execute("SELECT status,target,slot,place FROM meetings WHERE id=? AND requester=?",(mid,email)).fetchone()
     if not row: return self.out({"error":"meeting_not_found"},404)
     if action not in ("accept_demo","cancel"): return self.out({"error":"bad_action"},400)
     status="confirmed" if action=="accept_demo" else "cancelled"
     c.execute("UPDATE meetings SET status=? WHERE id=?",(status,mid))
     notify(c,email,"meeting_"+status,"Встреча "+("подтверждена" if status=="confirmed" else "отменена"),row["slot"]+" · "+row["place"])
     audit(c,"meeting_"+status,email,{"id":mid,"target":row["target"]})
    elif p=="/api/feedback":
     if role!="participant": return self.out({"error":"forbidden"},403)
     rating=max(1,min(5,int(data.get("rating",5)))); useful=1 if data.get("useful",True) else 0; comment=str(data.get("comment",""))[:300]
     c.execute("INSERT INTO session_feedback(email,session_id,rating,useful,comment,ts) VALUES(?,?,?,?,?,?)",(email,str(data.get("session_id","S2")),rating,useful,comment,int(time.time())))
     audit(c,"session_feedback",email,{"rating":rating,"useful":bool(useful)})
    elif p=="/api/passport":
     if role!="participant": return self.out({"error":"forbidden"},403)
     dimension=str(data.get("dimension","content"))
     if dimension not in ("content","event","network","partner"): return self.out({"error":"bad_dimension"},400)
     c.execute("UPDATE passport SET "+dimension+"=1,updated=? WHERE email=?",(int(time.time()),email))
     audit(c,"passport_"+dimension,email,{})
    elif p=="/api/product-interest":
     if role!="participant": return self.out({"error":"forbidden"},403)
     if data.get("consent") is not True: return self.out({"error":"consent_required"},422)
     track=str(data.get("track","metabolic_health"))[:80]; context=str(data.get("context","official_product_information"))[:120]
     consent_version=str(data.get("consent_version","product-interest-v1"))[:40]
     now=int(time.time())
     c.execute("INSERT INTO product_interests(email,track,context,consent_version,status,ts) VALUES(?,?,?,?, 'requested',?)",(email,track,context,consent_version,now))
     c.execute("INSERT INTO consent_records(email,purpose,consent_version,granted,source,business_ref,ts) VALUES(?,?,?,?,?,?,?)",(email,"product_interest",consent_version,1,"participant_action",track,now))
     notify(c,email,"product_interest_saved","Интерес сохранён","Мы сохранили запрос на официальный материал. Это не медицинская рекомендация и не назначение.")
     audit(c,"product_interest",email,{"track":track,"context":context,"consent_version":consent_version})
    elif p=="/api/followup-enroll":
     if role!="participant": return self.out({"error":"forbidden"},403)
     track=str(data.get("track","metabolic_health"))[:80]
     for day in (1,7,30):
      c.execute("INSERT INTO followups(email,day,track,status,ts) VALUES(?,?,?,'planned',?)",(email,day,track,int(time.time())))
     audit(c,"followup_30d_enrolled",email,{"track":track,"days":[1,7,30]})
     notify(c,email,"followup_enrolled","30-дневный маршрут включён","Материалы и события будут продолжать выбранную тему без автоматических медицинских назначений.")
    elif p=="/api/lead":
     if role!="participant": return self.out({"error":"forbidden"},403)
     if data.get("consent") is not True: return self.out({"error":"consent_required"},422)
     kind=str(data.get("kind","materials")); now=int(time.time())
     c.execute("INSERT INTO leads(kind,status,ts) VALUES(?,'new',?)",(kind,now))
     c.execute("INSERT INTO consent_records(email,purpose,consent_version,granted,source,business_ref,ts) VALUES(?,?,?,?,?,?,?)",(email,"partner_lead",str(data.get("consent_version","lead-v1"))[:40],1,"participant_action",kind,now))
     c.execute("UPDATE placements SET leads=leads+1 WHERE id=1"); audit(c,"voluntary_lead",email,{"kind":kind,"consent":True})
    elif p=="/api/question":
     if role!="participant": return self.out({"error":"forbidden"},403)
     text=str(data.get("text","Как отличать корреляцию от причинности?"))[:500]; c.execute("INSERT INTO questions(text,status,ts) VALUES(?,'review',?)",(text,int(time.time()))); audit(c,"question_submitted",email,{})
    elif p=="/api/cms":
     if role!="editor": return self.out({"error":"forbidden"},403)
     status=str(data.get("status","approved")); c.execute("UPDATE cms SET status=?,version=version+1,updated=? WHERE id='A-014'",(status,int(time.time()))); audit(c,"cms_status",email,{"status":status})
    elif p=="/api/phase":
     if role!="organizer": return self.out({"error":"forbidden"},403)
     v=str(data.get("phase","during")); setv(c,"phase",v); audit(c,"phase_changed",email,{"phase":v})
    else: return self.out({"error":"not_found"},404)
    c.commit(); return self.out(state(c,email))
   finally: c.close()
 def log_message(self,fmt,*args): print(fmt%args,flush=True)

H.do_GET=http_handler_trace(H.do_GET)
H.do_POST=http_handler_trace(H.do_POST)

if __name__=="__main__":
 configure_observability(); init(); port=int(os.environ.get("PORT","10000")); print("SOSTOYANIE v2.0 integration authority listening",port,flush=True); ThreadingHTTPServer(("0.0.0.0",port),H).serve_forever()
