# accounts/views.py
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import connection               # ✅ Django connection
from datetime import datetime
import json, re, time, requests

# helpers (Ёрдамчи функциялар)
LANG_MAP = {
    "uz": "uz",          # ўзбек (кирилл)
    "ru": "ru",
    "en": "en",
    "uz_lat": "uz_lat",  # ўзбек (лотин)    
}

def start_text(lang: str) -> str:
    texts = {
        "uz": (
            "Рўйхатдан ўтиш учун қуйидаги форматда юборинг:\n"
            "/reg ФИШ; Вилоят; Шаҳар ёки туман; Телефон; [Промкод]; [Тил]\n\n"
            "Тил вариантлари: uz | ru | en | uz_lat\n"
            "Масалан:\n/reg Камол Камолов; Қашқадарё вилояти; Косон; +998901234567; AGT-001; uz"
        ),
        "ru": (
            "Чтобы зарегистрироваться, отправьте в таком формате:\n"
            "/reg ФИО; Область; Город/район; Телефон; [Промокод]; [Язык]\n\n"
            "Языки: uz | ru | en | uz_lat\n"
            "Пример:\n/reg Камол Камолов; Кашкадарьинская область; Косон; +998901234567; AGT-001; ru"
        ),
        "en": (
            "To register, send in this format:\n"
            "/reg Full name; Region; City/District; Phone; [Promocode]; [Lang]\n\n"
            "Languages: uz | ru | en | uz_lat\n"
            "Example:\n/reg Kamol Kamolov; Qashqadaryo region; Koson; +998901234567; AGT-001; en"
        ),
        "uz_lat": (
            "Ro'yxatdan o'tish uchun quyidagi formatda yuboring:\n"
            "/reg FISH; Viloyat; Shahar yoki tuman; Telefon; [Promkod]; [Til]\n\n"
            "Tilllar: uz | ru | en | uz_lat\n"
            "Masalan:\n/reg Kamol Kamolov; Qashqadaryo viloyati; Koson; +998901234567; AGT-001; uz_lat"
        ),
    }
    return texts.get(lang, texts["uz"])


def already_registered_text(lang: str, chat_id: int, phone: str | None = None) -> str:
    phone_line = f"📞 <code>{phone}</code>\n" if phone else ""
    texts = {
        "uz": (
            "Сиз аввал рўйхатдан ўтгансиз ✅\n"
            f"ID: <code>{chat_id}</code>\n"
            f"{phone_line}"
            "Паролни унутган бўлсангиз, иловага кириб "
            "“Хавфсизлик → Паролни ўзгартириш” бўлими орқали янгиланг."
        ),
        "ru": (
            "Вы уже зарегистрированы ✅\n"
            f"ID: <code>{chat_id}</code>\n"
            f"{phone_line}"
            "Если вы забыли пароль, откройте приложение и смените его в разделе "
            "«Безопасность → Сменить пароль»."
        ),
        "en": (
            "You are already registered ✅\n"
            f"ID: <code>{chat_id}</code>\n"
            f"{phone_line}"
            "If you forgot your password, open the app and change it under "
            "“Security → Change password”."
        ),
        "uz_lat": (
            "Siz avval ro'yxatdan o'tgansiz ✅\n"
            f"ID: <code>{chat_id}</code>\n"
            f"{phone_line}"
            "Parolni unutgan bo'lsangiz, ilovaga kirib "
            "“Xavfsizlik → Parolni o‘zgartirish” bo‘limi orqali yangilang."
        ),
    }
    return texts.get(lang, texts["uz"])


def parse_lang_and_promkod(parts: list[str]) -> tuple[list[str], str | None, str | None]:
    """Oxiridagi til kodini ajratib oladi; undan oldingi element promkod bo'lishi mumkin."""
    lang = None
    prom = None
    if parts and parts[-1].lower() in LANG_MAP:
        lang = LANG_MAP[parts[-1].lower()]
        parts = parts[:-1]
    if len(parts) >= 5 and parts[4]:
        prom = parts[4]
    return parts, lang, prom

def unknown_command_text(lang: str) -> str:
    texts = {
        "uz": (            
            "Бу бот “SUV KERAK” иловасида рўйхатдан ўтиш амалларини бажаради. "
            "Агар сиз сув тарқатиш фаолияти билан шуғуллансангиз, Google Play ёки App Store'дан "
            "тегишли иловаларни юклаб олинг ва ботдан фойдаланинг.\n\n"
            "Илова 3 турдаги фойдаланувчилар учун:\n"
            "• <b>BOSS</b> — бизнес эгаси иловаси\n"
            "• <b>MENEDJER</b> — иш бошқарувчи иловаси\n"
            "• <b>COURIER</b> — сув тарқатувчи курьер иловаси\n\n"
            "Тегишли иловани юклаб олинг ва рўйхатдан ўтинг.\n"
            "Саволларингиз бўлса, /savol командасидан кейин саволингизни ва контактингизни қолдиринг — "
            "ходимларимиз алоқага чиқишади ва имкон қадар жавоб беришади.\n\n"
            "Батафсил: <a href=\"https://hisob.uz\">hisob.uz</a>\n\n"
            "Тижорат сиздан, ҳисоби биздан.\n"
            "Такомиллаштиришда давом этамиз.\n\n__________________________________________\n\n\n"
                    
            "Bu bot “SUV KERAK” ilovasida ro‘yxatdan o‘tish amallarini bajaradi. "
            "Agar siz suv tarqatish faoliyati bilan shug‘ullansangiz, Google Play yoki App Store’dan "
            "tegishli ilovalarni yuklab oling va botdan foydalaning.\n\n"
            "Ilova 3 turdagi foydalanuvchilar uchun:\n"
            "• <b>BOSS</b> — biznes egasi ilovasi\n"
            "• <b>MENEDJER</b> — ish boshqaruvchi ilovasi\n"
            "• <b>COURIER</b> — suv tarqatuvchi kuryer ilovasi\n\n"
            "Tegishli ilovani yuklab oling va ro‘yxatdan o‘ting.\n"
            "Savollaringiz bo‘lsa, /savol komandasi dan keyin savolingizni va kontaktingizni qoldiring — "
            "xodimlarimiz aloқа qiladi va imkon qadar javob beradi.\n\n"
            "Batafsil: <a href=\"https://hisob.uz\">hisob.uz</a>\n\n"
            "Tijorat sizdan, hisobi bizdan.\n"            
            "Takomillashtirishda davom etamiz.\n\n____________________________________________________\n\n\n"
                
            "Этот бот выполняет шаги регистрации в приложении «SUV KERAK». "
            "Если вы занимаетесь доставкой воды, скачайте соответствующие приложения в Google Play или App Store "
            "и пользуйтесь ботом.\n\n"
            "Приложение для 3 типов пользователей:\n"
            "• <b>BOSS</b> — приложение владельца бизнеса\n"
            "• <b>MENEDJER</b> — приложение управляющего (менеджера)\n"
            "• <b>COURIER</b> — приложение курьера по доставке воды\n\n"
            "Скачайте нужное приложение и пройдите регистрацию.\n"
            "Если есть вопросы, отправьте команду /savol, затем напишите свой вопрос и контакт — "
            "наши сотрудники свяжутся с вами и ответят.\n\n"
            "Подробнее: <a href=\"https://hisob.uz\">hisob.uz</a>\n\n"
            "Бизнес — с вас, учёт — с нас.\n"
            "Мы продолжаем улучшать сервис.\n\n____________________________________________________\n\n\n"
                
            "This bot handles registration steps for the “SUV KERAK” app. "
            "If you work in water delivery, download the relevant apps from Google Play or the App Store "
            "and use the bot.\n\n"
            "The app supports 3 user types:\n"
            "• <b>BOSS</b> — business owner app\n"
            "• <b>MENEDJER</b> — manager app\n"
            "• <b>COURIER</b> — courier app for water delivery\n\n"
            "Download the appropriate app and register.\n"
            "If you have questions, use /savol and then send your question and contact details — "
            "our team will reach out and reply.\n\n"
            "More details: <a href=\"https://hisob.uz\">hisob.uz</a>\n\n"
            "Business is yours, accounting is ours.\n"
            "We keep improving.\n\n____________________________________________________\n\n\n"
        ),
    }
    return texts.get(lang, texts["uz"])

# Вебхук суровига жавоб берувчи функция
@csrf_exempt
def telegram_webhook(request):
    """
    Telegram webhook view for the “SUV KERAK” bot.

    Қисқача
    -------
    Telegram’dan келган update’ларни (POST /webhook/) қабул қилади, chat_id ва матнни ажратади,
    фойдаланувчининг тилини accounts_business.lang дан олади ва буйруққа қараб жавоб юборади.

    Қўллаб-қувватланадиган буйруқлар
    --------------------------------
    • /start
        Фойдаланувчига умумий маълумот/йўриқнома хабарини юборади (unknown_command_text(lang)).
        (Эслатма: логикангизда start_text() ўрнига unknown_command_text() юборилади.)

    • /reg <FISH>; <Viloyat>; <Shahar/Tuman>; <Telefon>; [Promkod]; [Til]
        Агар фойдаланувчи олдин рўйхатдан ўтган бўлса — already_registered_text(lang, chat_id, phone) юборилади.
        Акс ҳолда бекендга {BACKEND_BASE_URL}/accounts/boss/register/ га JSON payload юборилади ва
        қайтган ID/парол фойдаланувчига етказилади.

        Мисоллар:
          /reg Аюбов Элбек; Қашқадарё вилояти; Косон; +998991112233; uz
          /reg Аюбов Элбек; Қашқадарё вилояти; Косон; +998991112233; ABC123; uz_lat

        Изоҳ:
          parse_lang_and_promkod(raw_parts) ёрдамчи функцияси массив охиридан тил ва промкодни ажратиб қайтаради.
          Тил келмаса, базадаги lang ёки "uz" қўлланади.

    • Бошқа матнлар
        unknown_command_text(lang) юборилади.

    Кирувчи маълумот (Telegram Update JSON)
    ---------------------------------------
    {
      "message": {
        "chat": {"id": <int>},
        "text": "<str>"
      }
    }

    Четдан боғлиқликлар
    -------------------
    • settings.TELEGRAM_BOT_TOKEN — Telegram’га sendMessage юбориш учун
    • settings.BACKEND_BASE_URL   — бекенд API’сига /accounts/boss/register/ POST қилиш учун

    Қайтариладиган жавоб
    --------------------
    JsonResponse({"ok": True}) — муваффақиятли ишловдан сўнг 200 статус билан.
    (Webhook талабига кўра Telegram 2xx кутади; кодингизда хатолик қолса ҳам 200 қайтариш тавсия этилади.)

    Параметрлар
    -----------
    request : django.http.HttpRequest
        Telegram’dan келган POST сўров.

    Қайдлар
    -------
    • Тил accounts_business(lang) дан chat_id бўйича аниқланади.
    • send() ичида Telegram’га HTML parse_mode билан хабар юборилади.
    """
    # ... функция давоми ...

    data = json.loads(request.body.decode("utf-8") or "{}")
    msg  = data.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()

    def send(txt: str):
        requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": txt, "parse_mode": "HTML"},
            timeout=10,
        )

    if not chat_id:
        return JsonResponse({"ok": True})

    # --- lang'ni bazadan олиш (курсор очиб)
    with connection.cursor() as cur:
        cur.execute("SELECT lang FROM public.accounts_business WHERE id=%s LIMIT 1", [chat_id])
        row = cur.fetchone()
    lang = (row[0] if row and row[0] else "uz")

    # /start — 4 тилда
    if text.lower().startswith("/start"):
        send(unknown_command_text(lang))
        return JsonResponse({"ok": True})

    # /reg — рўйхатдан ўтказиш
    if text.lower().startswith("/reg"):
        # 0) аввалдан бор-ёқлигини текшириш
        with connection.cursor() as cur:
            cur.execute("SELECT boss_tel_num FROM public.accounts_business WHERE id=%s LIMIT 1", [chat_id])
            row = cur.fetchone()

        if row:
            phone = row[0]
            msg = already_registered_text(lang, chat_id, phone)  # ✅ матнни оламиз
            send(msg)            
            print("DBG:: already branch, chat_id=", chat_id)

            return JsonResponse(
            {
                "ok": True,
                "already": True,
                "id": chat_id,
                "phone": phone,
                "lang": lang,
                "message": msg,# ✅ Постманга ҳам тўлиқ матн
                "probe": "register_boss_api_v3" 
            },
            json_dumps_params={"ensure_ascii": False}  # ✅ Кириллни нормал қайтариш
        )

        # 1) тил ва промкодни парс қилиш
        raw_parts = [p.strip() for p in text[5:].split(";")]
        parts, lang_param, promkod = parse_lang_and_promkod(raw_parts)  # sizdagi ёрдамчи функция
        if len(parts) < 4:
            # етмасада, мавжуд/lang бўйича старт хабарини юбориб қўямиз
            send(start_text(lang))
            return JsonResponse({"ok": True})

        payload = {
            "tg_id": chat_id,
            "full_name": parts[0],
            "viloyat": parts[1],
            "shahar_yoki_tuman": parts[2],
            "phone": parts[3],
            # тилни бекендга ҳам узатамиз: келган бўлса — шу, бўлмаса мавжуд/lang
            "lang": (lang_param or lang),
        }
        if promkod:
            payload["promkod"] = promkod

        url = f"{settings.BACKEND_BASE_URL}/accounts/boss/register/"
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                j = resp.json()
                send(
                    "Ro'yxatdan o'tdingiz ✅\n"
                    f"ID: <code>{j['id']}</code>\n"
                    f"Parol: <code>{j['password']}</code>"
                )
            else:
                send(f"Xatolik: {resp.text}")
        except Exception as e:
            send(f"Server bilan ulanishda xatolik: {e}")

        return JsonResponse({"ok": True})

    send(unknown_command_text(lang))
    return JsonResponse({"ok": True, "created": True, "id": chat_id, "probe": "register_boss_api_v3"})


WEEKDAY_UZ_ABBR = ["du", "se", "ch", "pa", "ju", "sh", "ya"]

def _normalize_phone(raw: str) -> str:
    """
    Телефон рақамини нормализация қилади.

    Нима қилади:
      - Матндан рақамлар ва '+' ни сақлаб қолади.
      - Агар рақам '998' билан бошланса ва бошида '+' бўлмаса → '+998…'га айлантиради.

    Параметрлар:
      raw (str): Фойдаланувчи киритган телефон (эркин форматда).

    Қайтарилади:
      str: Нормаллашган телефон (масалан, '+998991234567'); хато/бўш бўлса — бўш сатри.
    """
    
    if not raw: return ""
    s = re.sub(r"[^\d+]", "", str(raw))
    if not s: return ""
    if not s.startswith("+") and s.startswith("998"):
        s = "+" + s
    return s

def _make_password(user_id: int) -> str:
    """
    Вақтинчалик парол яратади (қисқа, инсон ўқийдиган формат).

    Формула:
      <IDнинг илк 2 рақами><кун DD><айни минут ва секунднинг охирги 1 тадан ракамлари MS><ҳафта куни қисқартмаси>

    Масалан:
      user_id=74213, сана 12-кун, жумa ('Ju') → '7412Ju'

    Эслатма:
      WEEKDAY_UZ_ABBR индекси 0–6 (душ–як) бўйича ишлайди.

    Параметрлар:
      user_id (int): Фойдаланувчи (Telegram) ID’и.

    Қайтарилади:
      str: Генерация қилинган вақтинчалик парол.
    """
    now = datetime.now()
    id2 = str(user_id).rjust(2, "0")[:2]           # IDнинг илк 2 рақами (кам бўлса 0 билан тўлдирамиз)
    day = f"{now.day:02d}"                          # кун DD
    m_last = str(now.minute)[-1]                    # минутнинг охирги рақами
    s_last = str(now.second)[-1]                    # секунднинг охирги рақами
    wd = WEEKDAY_UZ_ABBR[now.weekday()]            # ҳафта куни qisqartma

    return f"{id2}{day}{m_last}{s_last}{wd}"

def _send_tg_message(chat_id: int, text: str) -> tuple[bool, str]:
    """
    Telegram'га sendMessage юбориш (rate-limit’ни инобатга олган ҳолда).

    Нима қилади:
      - settings.TELEGRAM_BOT_TOKEN орқали /sendMessage қилади.
      - 429 (Too Many Requests) бўлса, `retry_after` га қараб 1 марта кейинроқ қайта уринади.
      - Истисно зарур ҳолларда истисно ташламайди — (False, сабаб) қайтаради.

    Параметрлар:
      chat_id (int): Қабул қилувчи чат ID’и.
      text (str): Юбориладиган хабар (HTML parse_mode).

    Қайтарилади:
      tuple[bool, str]:
        - 1-элемент: муваффақият (True/False)
        - 2-элемент: Telegram жавоби матни ёки сабаб ('NO_TOKEN', 'REQUEST_ERROR: …', ва ҳ.к.)

    Эслатма:
      `disable_web_page_preview=True` — ҳавола превьюлари ўчирилган.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        return False, "NO_TOKEN"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    for attempt in range(2):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                retry = (r.json().get("parameters", {}) or {}).get("retry_after", 2)
                time.sleep(int(retry)); continue
            return (r.status_code == 200 and r.json().get("ok") is True), r.text
        except requests.RequestException as e:
            if attempt == 0: time.sleep(2); continue
            return False, f"REQUEST_ERROR: {e}"
    return False, "UNKNOWN_ERROR"

@csrf_exempt
def register_boss(request: HttpRequest, payload: str = ""):
    """
    BOSS (бизнес эгаси) фойдаланувчисини рўйхатдан ўтказиш ва унга Telegram хабарини юбориш.

    Кириш форматлари:
      1) payload (ботдан келadigan қисқа формат):
         "tg_id/full_name/viloyat/nomi/phone[/promkod]"
      2) JSON/POST (frontend ёки ботдан JSON):
         {
           "tg_id": int,
           "full_name": str,
           "viloyat": str,
           "shahar_yoki_tuman": str,
           "phone": str,
           "promkod": str | null,      # ихтиёрий
           "lang": "uz|uz_lat|ru|en"   # ихтиёрий, дефолт 'uz'
         }

    Асосий қадамлар:
      • Тилни (lang) текшириш: {'uz','uz_lat','ru','en'}; нотўғри бўлса — 'uz'.
      • Дубликат ID бор-йўқлигини текшириш (accounts_business.id).
      • geo_list бўйича 'nomi' шаҳarmi/туманми аниқлаш.
      • Промкод келса — agent_account’дан агентни топиш.
      • accounts_business’га UPSERT:
          - (id, name, viloyat, shaxar, tuman, boss_tel_num, agent_name, agent_promkod, lang)
          - агар lang устуни йўқ бўлса, динамик тарзда қўшилади (+ индекс).
      • Паролни `_make_password()` орқали янгилаш.
      • Агар промкод бўлса — agent_account.business_id JSONBга бириктириш.
      • Сўнг фойдаланувчига Telegram орқали 4 тилдан бирида тайёр матн юбориш.

    Қайтарилади:
      200 OK, JSON:
        - {"ok": True, "id": <int>, "password": <str>, "tg_sent": <bool>}
        - Агар аввалдан мавжуд бўлса: {"ok": True, "already": True, "id": tg_id}
      4xx — валидация/маълумот топилмади (масалан, geo_list).
      500 — ички хатолик (истисно ушланиб, detail қайтарилади).

    Изоҳ:
      • Телефон `_normalize_phone()` билан тозаланади.
      • Хабар матни HTML parse_mode’да юборилади.
    """
    try:
        print("DBG:: ENTER register_boss, __file__=", __file__)

        # 1) JSON body'ни хавфсиз парс қилиш
        data = {}  # <-- аввал инициализация
        try:
            raw = request.body or b""
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="ignore")
            data = json.loads(raw or "{}")
        except Exception as e:
            print("DBG:: JSON parse error:", e)

        # 2) tg_id ни турли манбадан олиш
        tg_id = (
            (data.get("tg_id") if isinstance(data, dict) else None)
            or request.GET.get("tg_id")
            or request.headers.get("X-Telegram-Id")
        )
        try:
            chat_id = int(tg_id)
        except Exception:
            return JsonResponse({"detail": "tg_id талаб қилинади."}, status=400)

        # 3) payload ва тил
        text = (data.get("payload") or "").strip()
        lang = (text.split(";")[-1].strip() if ";" in text else "") or request.headers.get("Accept-Language", "uz")
        if lang not in {"uz", "ru", "en", "uz_lat"}:
            lang = "uz"

        # 4) аввалдан рўйхатдан ўтган-ўтмаганини текшириш
        with connection.cursor() as cur:
            cur.execute("SELECT boss_tel_num FROM public.accounts_business WHERE id=%s LIMIT 1", [chat_id])
            row = cur.fetchone()

        if row:
            phone = row[0] or ""
            msg = already_registered_text(lang, chat_id, phone)  # 🔹 тўлиқ хабар
            print("DBG:: register_boss already; id=", chat_id)

            return JsonResponse(
                {
                    "ok": True,
                    "already": True,
                    "id": chat_id,
                    "phone": phone,
                    "lang": lang,
                    "message": msg,
                    "probe": "register_boss_v5"
                },
                json_dumps_params={"ensure_ascii": False}
            )


        # --- input парсинг
        tg_id = full_name = viloyat = nomi = phone = promkod = None
        if payload:
            parts = [p.strip() for p in payload.split("/") if p.strip()]
            if len(parts) < 5:
                return JsonResponse({"detail": "Маълумот етарли эмас (payload)."}, status=400)
            tg_id, full_name, viloyat, nomi, phone = int(parts[0]), parts[1], parts[2], parts[3], parts[4]
            promkod = parts[5] if len(parts) >= 6 and parts[5] else None
        else:
            tg_id     = int(data.get("tg_id"))
            full_name = (data.get("full_name") or "").strip()
            viloyat   = (data.get("viloyat") or "").strip()
            nomi      = (data.get("shahar_yoki_tuman") or "").strip()
            phone     = (data.get("phone") or "").strip()
            promkod   = (data.get("promkod") or None) or None

        if not all([tg_id, full_name, viloyat, nomi, phone]):
            return JsonResponse({"detail": "Маълумотлар тўлиқ эмас."}, status=400)

        phone_norm = _normalize_phone(phone)

        # --- DB (UPSERT логикаси)
        with connection.cursor() as cur:
            # 0) Керак бўлса lang устунини яратиб қўямиз
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema='public' AND table_name='accounts_business' AND column_name='lang'
                    ) THEN
                        ALTER TABLE public.accounts_business ADD COLUMN lang varchar(10);
                        CREATE INDEX IF NOT EXISTS idx_business_lang ON public.accounts_business(lang);
                    END IF;
                END $$;
            """)

            # 1) geo_listдан турини аниқлаш
            cur.execute("""
                SELECT shaxar_yoki_tuman
                    FROM public.geo_list
                    WHERE lower(viloyat)=lower(%s)
                    AND lower(shaxar_yoki_tuman_nomi)=lower(%s)
                    LIMIT 1
            """, [viloyat.strip(), nomi.strip()])
            row = cur.fetchone()
            if not row:
                return JsonResponse({"detail": f"geo_list да топилмади: {viloyat} / {nomi}"}, status=404)

            turi = row[0]
            shahar = nomi if turi == "шаҳар" else None
            tuman  = nomi if turi == "туман" else None

            # 2) промкод бўлса — агент
            agent_name = None
            if promkod:
                cur.execute("SELECT id, agent_name FROM public.agent_account WHERE agent_promkod=%s LIMIT 1", [promkod])
                a = cur.fetchone()
                if not a:
                    return JsonResponse({"detail": "Промкод топилмади."}, status=400)
                agent_name = a[1]

            # 3) accounts_business UPSERT — ТИЛНИ ҲАМ САҚЛАЙМИЗ
            cur.execute("""
                INSERT INTO public.accounts_business
                    (id, name, viloyat, shaxar, tuman, boss_tel_num, agent_name, agent_promkod, lang)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name,
                    viloyat=EXCLUDED.viloyat,
                    shaxar=EXCLUDED.shaxar,
                    tuman=EXCLUDED.tuman,
                    boss_tel_num=EXCLUDED.boss_tel_num,
                    agent_name=COALESCE(EXCLUDED.agent_name, public.accounts_business.agent_name),
                    agent_promkod=COALESCE(EXCLUDED.agent_promkod, public.accounts_business.agent_promkod),
                    lang=EXCLUDED.lang
                RETURNING id
            """, [tg_id, full_name, viloyat, shahar, tuman, phone_norm, agent_name, promkod, lang])
            user_id = int(cur.fetchone()[0])

            # 4) парол
            password = _make_password(user_id)
            cur.execute("UPDATE public.accounts_business SET password=%s WHERE id=%s", [password, user_id])

            # 5) агент JSONB бириктириш
            if promkod:
                cur.execute("""
                    UPDATE public.agent_account
                        SET business_id = COALESCE(business_id, '{}'::jsonb)
                                            || jsonb_build_object(%s::text, %s::text)
                        WHERE agent_promkod=%s
                """, [full_name, str(tg_id), promkod])

        # --- Telegram хабар (сақланган/lang’дан фойдаланамиз)
        messages = {
            "uz": (
                f"Ҳурматли фойдаланувчи, сиз <code>{tg_id}</code> ID рақами билан рўйхатдан ўтдингиз ✅\n\n"
                f"🛡 Сизнинг вақтинчалик паролингиз:\n🔑 <code>{password}</code>\n\n"
                f"🛡 Сизнинг контактингиз:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 Сиз <code>BOSS (бизнесс эгаси)</code> фойдаланувчи турида рўйхатдан ўтдингиз.\n\n"
                f"Илованинг “Хавфсизлик → Паролни ўзгартириш” бўлими орқали ўз паролингизни янгилашни тавсия қиламиз."
            ),
            "uz_lat": (
                f"Hurmatli foydalanuvchi, siz <code>{tg_id}</code> ID raqami bilan ro‘yxatdan o‘tdingiz ✅\n\n"
                f"🛡 Sizning vaqtinchalik parolingiz:\n🔑 <code>{password}</code>\n\n"
                f"🛡 Sizning kontaktingiz:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 Siz <code>BOSS (biznes egasi)</code> foydalanuvchi turida ro‘yxatdan o‘tdingiz.\n\n"
                f"Ilovaning “Xavfsizlik → Parolni o‘zgartirish” bo‘limi orqali o‘z parolingizni yangilashingizni tavsiya qilamiz."
            ),
            "ru": (
                f"Уважаемый пользователь, Вы зарегистрировались с ID <code>{tg_id}</code> ✅\n\n"
                f"🛡 Ваш временный пароль:\n🔑 <code>{password}</code>\n\n"
                f"🛡 Ваш контакт:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 Вы зарегистрированы как <code>BOSS (владелец бизнеса)</code>.\n\n"
                f"Рекомендуем изменить пароль в разделе «Безопасность → Сменить пароль»."
            ),
            "en": (
                f"Dear user, you have successfully registered with ID <code>{tg_id}</code> ✅\n\n"
                f"🛡 Your temporary password:\n🔑 <code>{password}</code>\n\n"
                f"🛡 Your contact:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 You are registered as <code>BOSS (business owner)</code>.\n\n"
                f"We recommend changing your password in the app section “Security → Change Password”."
            ),
        }
        text = messages.get(lang, messages["uz"])

        ok, _ = _send_tg_message(tg_id, text)
        return JsonResponse({"ok": True, "id": user_id, "password": password, "tg_sent": ok}, status=200)

    except Exception as e:
        return JsonResponse({"detail": f"Ички хатолик: {e}"}, status=500)
# Паролни алмаштириш хабари    
def _forgot_password_text(lang: str, password: str) -> str:
    # 4 тилда тайёр хабар (ихтиёрий, истаса узгартиришингиз мумкин)
    msgs = {
        "uz":  f"Сиз илова орқали паролни янгиладингиз.\nВақтинчалик парол: <code>{password}</code>\n\nИлованинг “Хавфсизлик → Паролни ўзгартириш” бўлими орқали ўз паролингизни янгилашни тавсия қиламиз.",
        "uz_lat": f"Siz ilova orqali parolni yangiladingiz.\nVaqtinchalik parol: <code>{password}</code>\n\nIlovaning “Xavfsizlik → Parolni o'zgartirish” bo'limi orqali o'z parolingizni yangilashingizni tavsiya qilamiz.",
        "ru":  f"Вы обновили пароль через приложение.\nВременный пароль: <code>{password}</code>\n\nРекомендуем сменить его в разделе «Безопасность → Смена пароля».",
        "en":  f"You have reset your password in the app.\nTemporary password: <code>{password}</code>\n\nPlease change it in “Security → Change password”.",
    }
    return msgs.get(lang, msgs["uz"])

# Паролни алмаштириш хабарини юбориш ва саклаш функцияси
@csrf_exempt
def forgot_boss_password(request):
    """
    POST /accounts/boss/forgot-password/
    Body (JSON): { "id": <chat_id:int> }
    """
    # --- Кирувчи маълумот
    try:
        data = json.loads((request.body or b"").decode("utf-8") or "{}")
    except Exception:
        data = {}
    chat_id = data.get("id") or request.GET.get("id")
    try:
        chat_id = int(chat_id)
    except Exception:
        return JsonResponse({"detail": "id талаб қилинади."}, status=400)

    # --- Фойдаланувчи мавжудми ва тили
    with connection.cursor() as cur:
        cur.execute("SELECT lang FROM public.accounts_business WHERE id=%s LIMIT 1", [chat_id])
        row = cur.fetchone()
    if not row:
        return JsonResponse({"detail": "Фойдаланувчи топилмади."}, status=404)

    lang = row[0] or "uz"

    # --- Янгидан парол тузиш ва базада сақлаш
    new_password = _make_password(chat_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE public.accounts_business SET password=%s WHERE id=%s",
            [new_password, chat_id]
        )

    # --- Хабарни юбориш
    msg = _forgot_password_text(lang, new_password)
    ok, meta = _send_tg_message(chat_id, msg)

    return JsonResponse(
        {
            "ok": True,
            "id": chat_id,
            "password": new_password,   # истасангиз, жавобдан олиб ташлашингиз мумкин
            "telegram": {"sent": ok},
            "telegram": {"sent": meta},
        },
        json_dumps_params={"ensure_ascii": False}
    )
