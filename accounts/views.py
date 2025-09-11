# accounts/views.py
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import connection               # ✅ Django connection
from datetime import datetime
import json, re, time, requests

@csrf_exempt
def telegram_webhook(request):
    data = json.loads(request.body.decode("utf-8") or "{}")
    msg  = data.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()

    def send(txt):
        requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": txt, "parse_mode": "HTML"},
            timeout=10,
        )

    if not chat_id:
        return JsonResponse({"ok": True})

    # /start — қўлланма
    if text.lower().startswith("/start"):
        send("Ro'yxatdan o'tish uchun bu formatda yuboring:\n"
             "/reg ФИШ; Вилоят; Шаҳар ёки туман; Телефон; [Промкод]\n\n"
             "Masalan:\n/reg Элбек Йўлдошев; Андижон вилояти; Андижон; +998901234567; AGT-001")
        return JsonResponse({"ok": True})

    # /reg ... — рўйхатдан ўтказиш
    if text.startswith("/reg "):
        parts = [p.strip() for p in text[5:].split(";")]
        if len(parts) < 4:
            send("Format xato. To'g'ri ko'rinishi:\n"
                 "/reg ФИШ; Вилоят; Шаҳар ёки туман; Телефон; [Промкод]")
            return JsonResponse({"ok": True})

        payload = {
            "tg_id": chat_id,
            "full_name": parts[0],
            "viloyat": parts[1],
            "shahar_yoki_tuman": parts[2],
            "phone": parts[3],
        }
        if len(parts) >= 5 and parts[4]:
            payload["promkod"] = parts[4]

        # O'z backend endpoint’ingizni chaqiramiz
        url = f"{settings.BACKEND_BASE_URL}/accounts/boss/register/"
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                j = resp.json()
                send(f"Ro'yxatdan o'tdingiz ✅\nID: <code>{j['id']}</code>\nParol: <code>{j['password']}</code>")
            else:
                send(f"Xatolik: {resp.text}")
        except Exception as e:
            send(f"Server bilan ulanishda xatolik: {e}")
        return JsonResponse({"ok": True})

    # бошқа матнларга жавоб
    send("Buyruq noma'lum. /start deb yozing.")
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
        # --- input
        tg_id = full_name = viloyat = nomi = phone = promkod = None
        if payload:
            parts = [p.strip() for p in payload.split("/") if p.strip()]
            if len(parts) < 5:
                return JsonResponse({"detail": "Маълумот етарли эмас (payload)."}, status=400)
            tg_id, full_name, viloyat, nomi, phone = int(parts[0]), parts[1], parts[2], parts[3], parts[4]
            promkod = parts[5] if len(parts) >= 6 and parts[5] else None
        else:
            data = request.POST.dict() or (json.loads(request.body.decode("utf-8")) if request.body else {})
            tg_id    = int(data.get("tg_id"))
            full_name= (data.get("full_name") or "").strip()
            viloyat  = (data.get("viloyat") or "").strip()
            nomi     = (data.get("shahar_yoki_tuman") or "").strip()
            phone    = (data.get("phone") or "").strip()
            promkod  = (data.get("promkod") or None) or None

        if not all([tg_id, full_name, viloyat, nomi, phone]):
            return JsonResponse({"detail": "Маълумотлар тўлиқ эмас."}, status=400)

        phone_norm = _normalize_phone(phone)

        # --- DB (Django connection)
        with connection.cursor() as cur:
            # 1) geo_listдан turi
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

            turi = row[0]                 # 'шаҳар' ёки 'туман'
            shahar = nomi if turi == "шаҳар" else None
            tuman  = nomi if turi == "туман" else None

            # 2) промкод бўлса — агент
            agent_name = None
            if promkod:
                cur.execute("SELECT id, agent_name FROM public.agent_account WHERE agent_promkod=%s LIMIT 1", [promkod])
                a = cur.fetchone()
                if not a:
                    return JsonResponse({"detail": "Промкод топилмади."}, status=400)
                agent_name = a[1]         # agent_name

            # 3) accounts_business UPSERT
            cur.execute("""
                INSERT INTO public.accounts_business
                    (id, name, viloyat, shaxar, tuman, boss_tel_num, agent_name, agent_promkod)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name,
                    viloyat=EXCLUDED.viloyat,
                    shaxar=EXCLUDED.shaxar,
                    tuman=EXCLUDED.tuman,
                    boss_tel_num=EXCLUDED.boss_tel_num,
                    agent_name=COALESCE(EXCLUDED.agent_name, public.accounts_business.agent_name),
                    agent_promkod=COALESCE(EXCLUDED.agent_promkod, public.accounts_business.agent_promkod)
                RETURNING id
            """, [tg_id, full_name, viloyat, shahar, tuman, phone_norm, agent_name, promkod])
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

        # --- Telegram хабар
        text_uz = (
            f"Ҳурматли фойдаланувчи, сиз <code>{tg_id}</code> ID рақами билан рўйхатдан ўтдингиз ✅\n\n"
            f"🛡 Сизнинг вақтинчалик паролингиз:\н🔑 <code>{password}</code>\n\n"
            f"🛡 Сизнинг контактингиз:\н📞 <code>{phone_norm}</code>\n\n"
            f"🛡 Сиз <code>BOSS (бизнесс эгаси)</code> фойдаланувчи турида рўйхатдан ўтдингиз.\n\n"
            f"Илованинг “Хавфсизлик → Паролни ўзгартириш” бўлими орқали ўз паролингизни янгилашни тавсия қиламиз."
        )
        ok, _ = _send_tg_message(tg_id, text_uz)

        return JsonResponse({"ok": True, "id": user_id, "password": password, "tg_sent": ok}, status=200)

    except Exception as e:
        return JsonResponse({"detail": f"Ички хатолик: {e}"}, status=500)
