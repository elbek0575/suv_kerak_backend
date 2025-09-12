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


@csrf_exempt
def telegram_webhook(request):
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
            send(already_registered_text(lang, chat_id, phone))
            return JsonResponse({"ok": True, "already": True})

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
    return JsonResponse({"ok": True})


WEEKDAY_UZ_ABBR = ["du", "se", "ch", "pa", "ju", "sh", "ya"]

def _normalize_phone(raw: str) -> str:
    if not raw: return ""
    s = re.sub(r"[^\d+]", "", str(raw))
    if not s: return ""
    if not s.startswith("+") and s.startswith("998"):
        s = "+" + s
    return s

def _make_password(user_id: int) -> str:
    now = datetime.now()
    return f"{str(user_id)[:2]}{now.day:02d}{WEEKDAY_UZ_ABBR[now.weekday()]}"

def _send_tg_message(chat_id: int, text: str) -> tuple[bool, str]:
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
    try:
        # --- lang ни оламиз (дефолт: uz)
        if payload:
            data = {}
            lang = "uz"
        else:
            data = request.POST.dict() or (json.loads(request.body.decode("utf-8")) if request.body else {})
            lang = (data.get("lang") or "uz").strip()

        # Рухсат этилган тиллар
        allowed_langs = {"uz", "uz_lat", "ru", "en"}
        if lang not in allowed_langs:
            lang = "uz"

        # --- аввал ID дубликат текшируви
        with connection.cursor() as cur:
            tg_id = None
            if payload:
                parts = [p.strip() for p in payload.split("/") if p.strip()]
                if len(parts) >= 1:
                    tg_id = int(parts[0])
            else:
                tg_id = int(data.get("tg_id") or 0)

            if tg_id:
                cur.execute("SELECT 1 FROM public.accounts_business WHERE id=%s", [tg_id])
                if cur.fetchone():
                    # мавжуд бўлса — чиқиб кетамиз
                    return JsonResponse({"ok": True, "already": True, "id": tg_id})

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
