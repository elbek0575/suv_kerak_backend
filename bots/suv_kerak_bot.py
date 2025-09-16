# bots/suv_kerak_bot.py
import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.types import Update, Message, ContentType
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web
from asgiref.sync import async_to_sync
from dotenv import load_dotenv
from django.db import connection
from django.utils import timezone
import json, re, time, requests
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponseNotAllowed
from datetime import datetime
import secrets, string
from django.contrib.auth.hashers import make_password, check_password
import logging


# 🔐 Ташқи ўзгарувчиларни юклаймиз
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/aiogram-bot-webhook/"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://xxxx.ngrok-free.app
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ✅ Bot ва Dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

logger = logging.getLogger(__name__)

# 📍 Геолокацияга жавоб бериш (v3)
@dp.message(F.content_type == ContentType.LOCATION)  # yoki: @dp.message(lambda m: m.location is not None)
async def handle_location(message: Message):
    lat = message.location.latitude
    lng = message.location.longitude
    text = f"📍 Мижоз координаталари:\n<code>{lat}</code>, <code>{lng}</code>"

    # 1-уриниш: reply
    try:
        await message.reply(text)
    except TelegramBadRequest as e:
        # "message to be replied not found" ва шунга ўхшаш хатоларда fallback
        logging.exception("sendMessage failed, reply javob bukdi.")
        await message.answer(text)
    except Exception:
        # ҳар қандай кутилмаган хатода ҳам fallback
        logging.exception("sendMessage failed? replysiz javob buldi.")
        await message.answer(text)
        
# 🔧 AIOHTTP сервер
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

async def on_shutdown(app):
    await bot.delete_webhook()

@dp.message(F.text == "/start")
async def cmd_start(msg: Message):
    await msg.answer("Ассалому алайкум! SUV KERAK боти тайёр.")



async def _process_update(body_text: str) -> None:
    update = Update.model_validate_json(body_text)
    session = AiohttpSession()  # аргументсиз
    # ⬇️ Бу ерда parse_mode берилади — конструкторда ЭМАС
    bot_defaults = DefaultBotProperties(parse_mode=ParseMode.HTML)
    async with Bot(token=BOT_TOKEN, session=session, default=bot_defaults) as bot:
        await dp.feed_update(bot, update)


@csrf_exempt
def aiogram_webhook_view(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        body = (request.body or b"").decode("utf-8", errors="ignore")
        if not body.strip():
            logger.warning("Empty Telegram webhook body")
            return JsonResponse({"ok": True})

        # Диагностика учун қисқартириб логлаймиз (ихтиёрий)
        logger.info("Webhook body (trimmed): %s", body[:2048])

        # async қисмни sync’дан чақириш
        async_to_sync(_process_update)(body)

        # Telegram’га ҳар доим 200
        return JsonResponse({"ok": True})
    except Exception:
        logger.exception("❌ webhook top-level exception")
        return JsonResponse({"ok": True})



#Аудит назорат учун қайд логи
def audit_log(action: str,
              request,
              *,
              actor_id: int | None = None,
              status: int | None = None,
              object_type: str | None = None,
              object_id: int | None = None,
              meta: dict | None = None):
    try:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT")
        path = request.path
        method = request.method
        print(f"action {action}")
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.audit_log
                    (ts, actor_id, action, path, method, status, ip, user_agent, object_type, object_id, meta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                [timezone.now(), actor_id, action, path, method, status, ip, ua, object_type, object_id,
                 json.dumps(meta or {})]
            )
    except Exception:
        # лог ёзишдан хатолик сервисни тўхтатмасин
        pass


# helpers (Ёрдамчи функциялар)
LANG_MAP = {
    "uz": "uz",          # ўзбек (кирилл)
    "ru": "ru",
    "en": "en",
    "uz_lat": "uz_lat",  # ўзбек (лотин)    
}

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
    # if text.lower().startswith("/start"):
    #     send(unknown_command_text(lang))
    #     return JsonResponse({"ok": True})

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
        # if len(parts) < 4:
        #     # етмасада, мавжуд/lang бўйича старт хабарини юбориб қўямиз
        #     send(unknown_command_text(lang))
        #     return JsonResponse({"ok": True})

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
    BOSS (biznes egasi) foydalanuvchisini ro‘yxatdan o‘tkazish va unga Telegram xabarini yuborish.

    Kirish formatlari:
      1) payload (botdan keladigan qisqa format):
         "tg_id/full_name/viloyat/nomi/phone[/promkod]"
      2) JSON/POST (frontend yoki botdan JSON):
         {
           "tg_id": int,
           "full_name": str,
           "viloyat": str,
           "shahar_yoki_tuman": str,
           "phone": str,
           "promkod": str | null,      # ixtiyoriy
           "lang": "uz|uz_lat|ru|en"   # ixtiyoriy, default 'uz'
         }

    Asosiy qadamlari:
      • Tilni (lang) tekshirish: {'uz','uz_lat','ru','en'}; noto‘g‘ri bo‘lsa — 'uz'.
      • Dublikat ID bor-yo‘qligini tekshirish (accounts_business.id).
      • geo_list bo‘yicha 'nomi' shaharmi/tumanmi aniqlash.
      • Promkod kelsa — agent_account dan agentni topish.
      • accounts_business ga UPSERT:
          (id, name, viloyat, shaxar, tuman, boss_tel_num, agent_name, agent_promkod, lang)
      • Parolni `_make_password()` orqali yaratish va bazaga HASH (make_password) bilan saqlash.
      • Promkod bo‘lsa — agent_account.business_id JSONB ga biriktirish.
      • So‘ng foydalanuvchiga Telegram orqali tayyor matn yuborish.

    Qaytaradi:
      200 OK, JSON:
        - {"ok": True, "id": <int>, "password": <str>, "tg_sent": <bool>}
        - Agar avvaldan mavjud bo‘lsa: {"ok": True, "already": True, "id": tg_id, ...}

    Eslatma:
      • Telefon `_normalize_phone()` bilan tozalanadi.
      • Xabar matni Telegram’da HTML parse_mode bilan yuboriladi.

    Audit:
      • Muvaffaqiyatli ro‘yxatdan o‘tganida:  audit_log("reg_ok", request, actor_id=new_id, status=200)
      • Avvaldan ro‘yxatdan o‘tgan bo‘lsa:    audit_log("reg_already", request, actor_id=chat_id, status=200)
    """
    try:
        print("DBG:: ENTER register_boss, __file__=", __file__)

        # 1) JSON body’ni xavfsiz parse qilish
        data = {}
        try:
            raw = request.body or b""
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", errors="ignore")
            data = json.loads(raw or "{}")
        except Exception as e:
            print("DBG:: JSON parse error:", e)

        # 2) tg_id ni turli manbadan olish
        tg_id_in = (
            (data.get("tg_id") if isinstance(data, dict) else None)
            or request.GET.get("tg_id")
            or request.headers.get("X-Telegram-Id")
        )
        try:
            chat_id = int(tg_id_in)
        except Exception:
            return JsonResponse({"detail": "tg_id талаб қилинади."}, status=400)

        # 3) payload ва тилни йиғиш
        payload_text = (
            (data.get("payload") or "")
            or (request.POST.get("payload") if hasattr(request, "POST") else "")
            or (request.GET.get("payload") or "")
        ).strip()

        # Тилни топиш: payload охиридаги ;lang ёки Accept-Language
        _lang_from_payload = ""
        if ";" in payload_text:
            last_piece = payload_text.split(";")[-1].strip().lower()
            if last_piece in {"uz", "uz_lat", "ru", "en"}:
                _lang_from_payload = last_piece

        lang = _lang_from_payload or (request.headers.get("Accept-Language", "uz") or "uz").split(",")[0].strip().lower()
        if lang not in {"uz", "uz_lat", "ru", "en"}:
            lang = "uz"

        # 4) Олдиндан борми — текшириш (ўша қолсин)
        with connection.cursor() as cur:
            cur.execute("SELECT boss_tel_num FROM public.accounts_business WHERE id=%s LIMIT 1", [chat_id])
            row = cur.fetchone()

        if row:
            phone_existing = row[0] or ""
            msg = already_registered_text(lang, chat_id, phone_existing)
            audit_log("reg_already", request, actor_id=chat_id, status=200, meta={"phone": phone_existing})
            return JsonResponse(
                {"ok": True, "already": True, "id": chat_id, "phone": phone_existing, "lang": lang, "message": msg},
                json_dumps_params={"ensure_ascii": False}
            )

        # --- input parsing (payload ёки JSON)
        tg_id = full_name = viloyat = nomi = phone = promkod = None
        source = "payload" if payload_text else "json"

        if payload_text:
            rp = payload_text

            # "/reg" префиксини олдиради
            if rp.lower().startswith("/reg"):
                rp = rp[4:].strip()

            # 1) "ФИШ; Вилоят; Туман; Телефон; [til]; [promkod]" формати
            if ";" in rp:
                parts = [p.strip() for p in rp.split(";") if p.strip()]
                if len(parts) < 4:
                    return JsonResponse({"detail": "Маълумот етарли эмас (payload ;)"} , status=400)

                full_name, viloyat, nomi, phone = parts[0], parts[1], parts[2], parts[3]
                # 5-элемент тил бўлиши мумкин — юқорида ажратиб олганмиз
                # 6-элемент промкод бўлиши мумкин
                if len(parts) >= 6 and parts[5]:
                    promkod = parts[5]

                # tg_id payload’да берилмаса, чатдан олганимизни қўйямиз
                tg_id = chat_id

            else:
                # 2) "tg_id/full_name/viloyat/nomi/phone[/promkod]" формати
                parts = [p.strip() for p in rp.split("/") if p.strip()]
                if len(parts) < 5:
                    return JsonResponse({"detail": "Маълумот етарли эмас (payload /)"} , status=400)

                # Агар биринчи қиймат рақам бўлмаса — чатдан олганимизни қўйиб, ФИШдан бошлаймиз
                try:
                    tg_id = int(parts[0])
                    idx = 1
                except Exception:
                    tg_id = chat_id
                    idx = 0

                full_name = parts[idx]
                viloyat   = parts[idx + 1]
                nomi      = parts[idx + 2]
                phone     = parts[idx + 3]
                promkod   = parts[idx + 4] if len(parts) > idx + 4 and parts[idx + 4] else None

        else:
            # Тўлиқ JSON майдонлари
            try:
                tg_id     = int(data.get("tg_id"))
            except Exception:
                tg_id     = chat_id  # захира сифатида
            full_name = (data.get("full_name") or "").strip()
            viloyat   = (data.get("viloyat") or "").strip()
            nomi      = (data.get("shahar_yoki_tuman") or "").strip()
            phone     = (data.get("phone") or "").strip()
            promkod   = (data.get("promkod") or None) or None

        # Финал текширув
        if not all([tg_id, full_name, viloyat, nomi, phone]):
            return JsonResponse({"detail": "Маълумотлар тўлиқ эмас."}, status=400)

        phone_norm = _normalize_phone(phone)


        # --- DB (UPSERT logikasi)
        with connection.cursor() as cur:
            # 0) kerak bo‘lsa lang ustunini yaratib qo‘yamiz
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

            # 1) geo_list dan turini aniqlash
            cur.execute("""
                SELECT shaxar_yoki_tuman
                  FROM public.geo_list
                 WHERE lower(viloyat)=lower(%s)
                   AND lower(shaxar_yoki_tuman_nomi)=lower(%s)
                 LIMIT 1
            """, [viloyat.strip(), nomi.strip()])
            geo_row = cur.fetchone()
            print("geo_row", geo_row)
            if not geo_row:
                return JsonResponse({"detail": f"geo_list да топилмади: {viloyat} / {nomi}"}, status=404)

            turi = geo_row[0]
            shahar = nomi if turi == "шаҳар" else None
            tuman  = nomi if turi == "туман" else None

            # 2) promkod bo‘lsa — agent ma’lumotini olish
            agent_name = None
            if promkod:
                cur.execute("SELECT id, agent_name FROM public.agent_account WHERE agent_promkod=%s LIMIT 1", [promkod])
                a = cur.fetchone()
                if not a:
                    return JsonResponse({"detail": "Промкод топилмади."}, status=400)
                agent_name = a[1]

            # 3) accounts_business UPSERT — tilni ham saqlaymiz
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

            # 4) parolni yaratish va HASH saqlash
            password_raw = _make_password(user_id)
            password_hash = make_password(password_raw)
            cur.execute("UPDATE public.accounts_business SET password=%s WHERE id=%s", [password_hash, user_id])

            # 5) agent JSONB biriktirish (ixtiyoriy)
            if promkod:
                cur.execute("""
                    UPDATE public.agent_account
                       SET business_id = COALESCE(business_id, '{}'::jsonb)
                                         || jsonb_build_object(%s::text, %s::text)
                     WHERE agent_promkod=%s
                """, [full_name, str(tg_id), promkod])

        # ✅ AUDIT — muvaffaqiyatli ro‘yxatdan o‘tdi
        audit_log("reg_ok", request, actor_id=user_id, status=200,
                  meta={"phone": phone_norm, "lang": lang, "source": source, "promkod": promkod})

        # --- Telegram xabar (lang bo‘yicha)
        messages = {
            "uz": (
                f"Ҳурматли фойдаланувчи, сиз <code>{tg_id}</code> ID рақами билан рўйхатдан ўтдингиз ✅\n\n"
                f"🛡 Сизнинг вақтинчалик паролингиз:\n🔑 <code>{password_raw}</code>\n\n"
                f"🛡 Сизнинг контактингиз:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 Сиз <code>BOSS (бизнесс эгаси)</code> фойдаланувчи турида рўйхатдан ўтдингиз.\n\n"
                f"Илованинг “Хавфсизлик → Паролни ўзгартириш” бўлими орқали ўз паролингизни янгилашни тавсия қиламиз."
            ),
            "uz_lat": (
                f"Hurmatli foydalanuvchi, siz <code>{tg_id}</code> ID raqami bilan ro‘yxatdan o‘tdingiz ✅\n\n"
                f"🛡 Sizning vaqtinchalik parolingiz:\n🔑 <code>{password_raw}</code>\n\n"
                f"🛡 Sizning kontaktingiz:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 Siz <code>BOSS (biznes egasi)</code> foydalanuvchi turida ro‘yxatdan o‘tdingiz.\n\n"
                f"Ilovaning “Xavfsizlik → Parolni o‘zgartirish” bo‘limi orqali o‘z parolingizni yangilashingizni tavsiya qilamiz."
            ),
            "ru": (
                f"Уважаемый пользователь, Вы зарегистрировались с ID <code>{tg_id}</code> ✅\n\n"
                f"🛡 Ваш временный пароль:\n🔑 <code>{password_raw}</code>\n\n"
                f"🛡 Ваш контакт:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 Вы зарегистрированы как <code>BOSS (владелец бизнеса)</code>.\n\n"
                f"Рекомендуем изменить пароль в разделе «Безопасность → Сменить пароль»."
            ),
            "en": (
                f"Dear user, you have successfully registered with ID <code>{tg_id}</code> ✅\n\n"
                f"🛡 Your temporary password:\n🔑 <code>{password_raw}</code>\n\n"
                f"🛡 Your contact:\n📞 <code>{phone_norm}</code>\n\n"
                f"🛡 You are registered as <code>BOSS (business owner)</code>.\n\n"
                f"We recommend changing your password in the app section “Security → Change Password”."
            ),
        }
        text_to_send = messages.get(lang, messages["uz"])

        sent_ok, _meta = _send_tg_message(tg_id, text_to_send)

        return JsonResponse(
            {"ok": True, "id": user_id, "password": password_raw, "tg_sent": sent_ok},
            status=200,
            json_dumps_params={"ensure_ascii": False},
        )

    except Exception as e:
        return JsonResponse({"detail": f"Ички хатолик: {e}"}, status=500)
    
# Паролни алмаштириш хабари    
VERIFY_CODE_TTL_SECONDS = 180  # 3 дақиқа
MAX_CODE_ATTEMPTS = 5

def _forgot_code_text(lang: str, code: str) -> str:
    msgs = {
        "uz":     f"Паролни янгилаш учун 4 хонали код: <code>{code}</code>\nКод 3 дақиқа давомида амал қилади. Иловадаги “Вақтинчалик код киритиш” саҳифасига шу кодни киритинг.",
        "uz_lat": f"Parolni yangilash uchun 4 xonali kod: <code>{code}</code>\nKod 3 daqiqa amal qiladi. Ilovadagi “Vaqtinchalik kod kiritish” sahifasiga shu kodni kiriting.",
        "ru":     f"Код для смены пароля: <code>{code}</code>\nКод действует 3 минуты. Введите его в приложении на странице «Временный код».",
        "en":     f"Password reset code: <code>{code}</code>\nThe code is valid for 3 minutes. Enter it in the app on the “Temporary code” page.",
    }
    return msgs.get(lang, msgs["uz"])

def _forgot_password_text(lang: str, password: str) -> str:
    msgs = {
        "uz":     f"Сиз паролни янгиладингиз.\nВақтинчалик парол: <code>{password}</code>\n\nИлованинг “Хавфсизлик → Паролни ўзгартириш” бўлими орқали ўз паролингизни янгилан.",
        "uz_lat": f"Siz parolni yangiladingiz.\nVaqtinchalik parol: <code>{password}</code>\n\nIlovaning “Xavfsizlik → Parolni o‘zgartirish” bo‘limi orqali o‘z parolingizni yangilang.",
        "ru":     f"Вы обновили пароль.\nВременный пароль: <code>{password}</code>\n\nРекомендуем сменить его в разделе «Безопасность → Смена пароля».",
        "en":     f"Your password was reset.\nTemporary password: <code>{password}</code>\n\nPlease change it in “Security → Change password”.",
    }
    return msgs.get(lang, msgs["uz"])

#код юбориш эндпоинти
@csrf_exempt
def forgot_boss_password_start(request):
    """
    Body: { "id": <int> }  ёки  { "boss_tel_num": "<str>" } (alias: "phone")
    Query: ?id=... ёки ?boss_tel_num=... ҳам ишлайди.
    """
    # --- Robust parsing ---
    raw_text = (request.body or b"").decode("utf-8", errors="ignore")
    data = {}
    try:
        data = json.loads(raw_text) if raw_text.strip() else {}
    except Exception:
        # JSON бўлмаса, POST формадан оламиз
        pass
    # Форм-датадан ҳам ўқиб қўямиз (JSON келмаган бўлса)
    if not data and request.POST:
        data = request.POST.dict()

    raw_id    = data.get("id") or request.GET.get("id")
    raw_phone = (
        data.get("boss_tel_num") or data.get("phone")
        or request.GET.get("boss_tel_num") or request.GET.get("phone")
    )

    chat_id = None
    lang = "uz"
    boss_phone = ""

    if not (raw_id or raw_phone):
        audit_log("fp_start_fail", request, actor_id=None, status=400,
                  meta={"reason": "id_or_phone_required", "raw_preview": raw_text[:512]})
        return JsonResponse({"detail": "id ёки boss_tel_num талаб қилинади."}, status=400)

    with connection.cursor() as cur:
        if raw_id:
            try:
                chat_id = int(str(raw_id).strip())
            except Exception:
                audit_log("fp_start_fail", request, actor_id=None, status=400,
                          meta={"reason": "bad_id_format", "raw_id": raw_id})
                return JsonResponse({"detail": "id нотўғри форматда."}, status=400)

            # Eslatma: бу ерда id — business.id (Telegram chat_id эмас!)
            cur.execute(
                """
                SELECT id, COALESCE(lang,'uz'), COALESCE(boss_tel_num,'')
                FROM public.accounts_business WHERE id=%s LIMIT 1
                """,
                [chat_id]
            )
            row = cur.fetchone()
            if not row:
                audit_log("fp_start_fail", request, actor_id=chat_id, status=404,
                          meta={"reason": "user_not_found_by_id"})
                return JsonResponse({"detail": "Фойдаланувчи топилмади."}, status=404)
            chat_id, lang, boss_phone = row

        else:
            phone = _normalize_phone(raw_phone) if "_normalize_phone" in globals() \
                    else _normalize_phone_fallback(raw_phone)
            cur.execute(
                """
                SELECT id, COALESCE(lang,'uz'), COALESCE(boss_tel_num,'')
                FROM public.accounts_business WHERE boss_tel_num=%s
                """,
                [phone]
            )
            rows = cur.fetchall()
            if not rows:
                audit_log("fp_start_fail", request, actor_id=None, status=404,
                          meta={"reason": "user_not_found_by_phone", "phone": phone})
                return JsonResponse({"detail": "Ушбу телефон бўйича ҳисоб топилмади."}, status=404)
            if len(rows) > 1:
                audit_log("fp_start_fail", request, actor_id=None, status=409,
                          meta={"reason": "multiple_accounts_for_phone", "phone": phone})
                return JsonResponse({"detail": "Бу телефонга бир нечта ҳисоб бор. Илтимос ID киритинг."}, status=409)
            chat_id, lang, boss_phone = rows[0]       

    # 4 хонали код
    code = "".join(secrets.choice(string.digits) for _ in range(4))
    expires_at = timezone.now() + timezone.timedelta(seconds=VERIFY_CODE_TTL_SECONDS)

    # базада сақлаш
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE public.accounts_business "
            "SET reset_code=%s, reset_code_expires_at=%s, reset_code_attempts=0 "
            "WHERE id=%s",
            [code, expires_at, chat_id]
        )

    # ❗️АУДИТ: муваффақиятли старт (код базада сақланди)
    audit_log("fp_start", request, actor_id=chat_id, status=200,
              meta={"expires_in": VERIFY_CODE_TTL_SECONDS})

    # Телеграмга вақтинчалик кодни юбориш (телеграмга кетмаса ҳам 200 берaсиз — лекин аудитинизда белгилаб қўйинг)
    send_text = _forgot_code_text(lang, code)
    sent, meta = _send_tg_message(chat_id, send_text)

    # (ихтиёрий) агар телеграм юбориш омадсиз бўлса, алоҳида аудит ёзуви:
    if not sent:
        audit_log("fp_start_warn", request, actor_id=chat_id, status=200,
                  meta={"reason": "telegram_send_failed", "tg_meta": meta})

    return JsonResponse(
        {
            "ok": True,
            "id": chat_id,
            "boss_tel_num": boss_phone,
            "lang": lang,
            "telegram": {"sent": sent},
            "expires_in": VERIFY_CODE_TTL_SECONDS,
            "postmen_msg": meta
        },
        json_dumps_params={"ensure_ascii": False}
    )

def _normalize_phone_fallback(raw: str) -> str:
    """
    Телефон рақамини нормаллаштириш: фақат рақам ва '+' қолдирамиз,
    Ўзбекистон форматида бўлса +998 префиксни қўйиб қўямиз.
    """
    if not raw:
        return ""
    s = "".join(ch for ch in str(raw) if ch.isdigit() or ch == "+")
    # allaqachon + bilan bo'lsa — qaytaramiz
    if s.startswith("+"):
        return s
    # 998 bilan boshlangan bo'lsa — +998... ga aylantiramiz
    if s.startswith("998"):
        return "+" + s
    # 00 bilan boshlansa (xalqaro) → 00 ni olib tashlab qaytaramiz
    if s.startswith("00") and len(s) > 2:
        s = s[2:]
        if s.startswith("998"):
            return "+" + s
    return s


# Паролни алмаштириш хабарини юбориш ва саклаш функцияси
@csrf_exempt
def forgot_boss_password_verify(request):
    """
    Body: { "id": <int>, "code": "1234" }  ёки  { "boss_tel_num": "<str>", "code": "1234" }
    """
    try:
        data = json.loads((request.body or b"").decode("utf-8") or "{}")
    except Exception:
        data = {}

    code = (data.get("code") or "").strip()
    if not (code.isdigit() and len(code) == 4):
        # аудит: код формати хатто
        audit_log("fp_verify_fail", request, actor_id=None, status=400,
                  meta={"reason": "bad_code_format", "code": code})
        return JsonResponse({"detail": _code_err("uz", "wrong")}, status=400)  # тил номаълум, uz'га фоллбек

    raw_id    = data.get("id") or request.GET.get("id")
    raw_phone = data.get("boss_tel_num") or data.get("phone") \
             or request.GET.get("boss_tel_num") or request.GET.get("phone")

    chat_id = None
    lang = "uz"

    with connection.cursor() as cur:
        if raw_id:
            try:
                chat_id = int(str(raw_id).strip())
            except Exception:
                audit_log("fp_verify_fail", request, actor_id=None, status=400,
                          meta={"reason": "bad_id_format", "raw_id": raw_id})
                return JsonResponse({"detail": "id нотўғри форматда."}, status=400)

            cur.execute(
                "SELECT COALESCE(lang,'uz'), reset_code, reset_code_expires_at, reset_code_attempts "
                "FROM public.accounts_business WHERE id=%s LIMIT 1",
                [chat_id],
            )
            row = cur.fetchone()
            if not row:
                audit_log("fp_verify_fail", request, actor_id=chat_id, status=404,
                          meta={"reason": "user_not_found_by_id"})
                return JsonResponse({"detail": "Фойдаланувчи топилмади."}, status=404)
            lang, db_code, exp_at, attempts = row

        elif raw_phone:
            phone = _normalize_phone(raw_phone) if "_normalize_phone" in globals() \
                    else _normalize_phone_fallback(raw_phone)
            cur.execute(
                "SELECT id, COALESCE(lang,'uz'), reset_code, reset_code_expires_at, reset_code_attempts "
                "FROM public.accounts_business WHERE boss_tel_num=%s",
                [phone],
            )
            rows = cur.fetchall()
            if not rows:
                audit_log("fp_verify_fail", request, actor_id=None, status=404,
                          meta={"reason": "user_not_found_by_phone", "phone": phone})
                return JsonResponse({"detail": "Ушбу телефон бўйича ҳисоб топилмади."}, status=404)
            if len(rows) > 1:
                audit_log("fp_verify_fail", request, actor_id=None, status=409,
                          meta={"reason": "multiple_accounts_for_phone", "phone": phone})
                return JsonResponse({"detail": "Бу телефонга бир нечта ҳисоб бор. Илтимос ID киритинг."}, status=409)
            chat_id, lang, db_code, exp_at, attempts = rows[0]
        else:
            audit_log("fp_verify_fail", request, actor_id=None, status=400,
                      meta={"reason": "id_or_phone_required"})
            return JsonResponse({"detail": "id ёки boss_tel_num талаб қилинади."}, status=400)

    # --- текширишлар
    now = timezone.now()
    if not db_code:
        audit_log("fp_verify_fail", request, actor_id=chat_id, status=400,
                  meta={"reason": "no_code"})
        return JsonResponse({"detail": _code_err(lang, "no_code")}, status=400)

    if exp_at and now > exp_at:
        # ✅ Сиз сўраган аудит: expired
        audit_log("fp_verify_fail", request, actor_id=chat_id, status=410,
                  meta={"reason": "expired"})
        return JsonResponse({"detail": _code_err(lang, "expired")}, status=410)

    if attempts is not None and attempts >= MAX_CODE_ATTEMPTS:
        audit_log("fp_verify_fail", request, actor_id=chat_id, status=429,
                  meta={"reason": "too_many"})
        return JsonResponse({"detail": _code_err(lang, "too_many")}, status=429)

    if code != db_code:
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE public.accounts_business "
                "SET reset_code_attempts = COALESCE(reset_code_attempts,0) + 1 "
                "WHERE id=%s",
                [chat_id],
            )
        # ✅ Сиз сўраган аудит: wrong_code
        audit_log("fp_verify_fail", request, actor_id=chat_id, status=400,
                  meta={"reason": "wrong_code"})
        return JsonResponse({"detail": _code_err(lang, "wrong")}, status=400)

    # --- Код тўғри — вақтинчалик парол яратиб, хэшлаш ва сақлаш
    temp_password = _make_password(chat_id)
    hashed = make_password(temp_password)

    with connection.cursor() as cur:
        cur.execute(
            "UPDATE public.accounts_business "
            "SET password=%s, reset_code=NULL, reset_code_expires_at=NULL, reset_code_attempts=0 "
            "WHERE id=%s",
            [hashed, chat_id],
        )

    # Ботга вақтинчалик паролни юбориш
    msg = _forgot_password_text(lang, temp_password)
    sent, meta = _send_tg_message(chat_id, msg)

    # ✅ Сиз сўраган аудит: verify_ok
    audit_log("fp_verify_ok", request, actor_id=chat_id, status=200,
              meta={"telegram_sent": bool(sent)})

    # (ихтиёрий) агар телеграм юбориш омадсиз бўлса, истасак алоҳида warn лог қўйишимиз мумкин:
    audit_log("fp_verify_warn", request, actor_id=chat_id, status=200,
              meta={"reason": "telegram_send_failed", "tg_meta": meta})

    resp = {
        "ok": True,
        "id": chat_id,
        "telegram": {"sent": sent},
    }
    if getattr(settings, "DEBUG", False):
        resp["__dev_password_preview"] = temp_password  # фақат DEVда
    return JsonResponse(resp, json_dumps_params={"ensure_ascii": False})


# 4 тилли хатлик хабарлари
_CODE_ERRORS = {
    "no_code": {
        "uz":     "Код сўралмаган ёки бекор қилинган.",
        "uz_lat": "Kod so'ralmagan yoki bekor qilingan.",
        "ru":     "Код не запрашивался или был отменён.",
        "en":     "The code was not requested or has been canceled.",
    },
    "expired": {
        "uz":     "Код муддати тугаган. Яна код сўранг.",
        "uz_lat": "Kod muddati tugagan. Yana kod so'rang.",
        "ru":     "Срок действия кода истёк. Запросите новый.",
        "en":     "The code has expired. Please request a new one.",
    },
    "too_many": {
        "uz":     "Уринишлар сони чекланган. Яна код сўранг.",
        "uz_lat": "Urinishlar soni cheklangan. Yana kod so'rang.",
        "ru":     "Превышен лимит попыток. Запросите новый код.",
        "en":     "Too many attempts. Please request a new code.",
    },
    "wrong": {
        "uz":     "Вақтинчалик код нотўғри.",
        "uz_lat": "Vaqtinchalik kod noto'g'ri.",
        "ru":     "Временный код неверный.",
        "en":     "Incorrect temporary code.",
    },
}

def _code_err(lang: str, key: str) -> str:
    lang = lang if lang in {"uz", "uz_lat", "ru", "en"} else "uz"
    return _CODE_ERRORS[key][lang]


# Ихтиёрий: 4 тилда Босс логин хабарлари
_AUTH_MSG = {
    "bad_input": {
        "uz":     "ID ва парол талаб қилинади.",
        "uz_lat": "ID va parol talab qilinadi.",
        "ru":     "Требуются ID и пароль.",
        "en":     "ID and password are required.",
    },
    "invalid": {
        "uz":     "ID ёки парол нотўғри.",
        "uz_lat": "ID yoki parol noto'g'ri.",
        "ru":     "Неверный ID или пароль.",
        "en":     "Invalid ID or password.",
    },
    "ok": {
        "uz":     "Сиз тизимга муваффақиятли кирдингиз.",
        "uz_lat": "Siz tizimga muvaffaqiyatli kirdingiz.",
        "ru":     "Вы успешно вошли.",
        "en":     "Signed in successfully.",
    }
}

def _t(lang: str, key: str) -> str:
    lang = lang if lang in {"uz","uz_lat","ru","en"} else "uz"
    return _AUTH_MSG[key][lang]


