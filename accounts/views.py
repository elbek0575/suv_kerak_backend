# accounts/views.py
from typing import List, Dict, Any, Optional
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.db import connection, transaction        # ✅ Django connection
from datetime import datetime
import json, re, time, requests
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import secrets, string


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


# Ихтиёрий: 4 тилда Босс логин хабарлари
_AUTH_MSG = {
    "bad_input": {
        "uz":     "ID ва парол талаб қилинади. MSG",
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


@csrf_exempt
def boss_login(request):
    """
    POST /accounts/boss/login/
    Body (JSON|form): { "boss_user_id": <int>|"<int>", "password": "<str>" }
    Query ҳам қабул қилади: ?boss_user_id=...&password=...
    """
    # --- Robust parsing ---
    raw_bytes = request.body or b""
    ct = request.headers.get("Content-Type") or ""
    raw_text = raw_bytes.decode("utf-8", errors="ignore")

    # Диагностика (логларда кўриш учун)
    print("🧪 boss_login CT=", ct, "CL=", request.headers.get("Content-Length"),
          "len(body)=", len(raw_bytes), " preview=", raw_text[:120])

    data = {}

    # 1) Агар JSON деб келса — JSON сифатида
    if "application/json" in ct:
        try:
            data = json.loads(raw_text) if raw_text.strip() else {}
        except Exception:
            data = {}

    # 2) Айрим клиентлар CT нотўғри қўяди — барибир уринб кўрамиз
    if not data and raw_text.strip().startswith("{"):
        try:
            data = json.loads(raw_text)
        except Exception:
            pass

    # 3) form-data / x-www-form-urlencoded
    if not data and request.POST:
        data = request.POST.dict()

    # --- Кирувчи параметрлар (алиаслар билан) ---
    raw_id = (
        data.get("boss_user_id") or data.get("id")
        or request.GET.get("boss_user_id") or request.GET.get("id") or ""
    )
    raw_pw = (data.get("password") or request.GET.get("password") or "").strip()

    if not raw_id or not raw_pw:
        audit_log("Кириш муваффақиятсиз", request, actor_id=None, status=400,
                  meta={"reason": "bad_input",
                        "ct": ct, "len_body": len(raw_bytes), "preview": raw_text[:120]})
        return JsonResponse({"detail": "ID ва парол талаб қилинади."},
                            status=400, json_dumps_params={"ensure_ascii": False})

    try:
        chat_id = int(str(raw_id).strip())
    except Exception:
        audit_log("Кириш муваффақиятсиз", request, actor_id=None, status=400,
                  meta={"reason": "bad_id_format", "raw_id": raw_id})
        return JsonResponse({"detail": "ID нотўғри форматда."},
                            status=400, json_dumps_params={"ensure_ascii": False})

    # --- Фойдаланувчини оламиз ---
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, name, COALESCE(lang,'uz'), password "
            "FROM public.accounts_business WHERE id=%s LIMIT 1",
            [chat_id],
        )
        row = cur.fetchone()

    if not row:
        audit_log("Кириш муваффақиятсиз", request, actor_id=chat_id, status=401,
                  meta={"reason": "user_not_found"})
        return JsonResponse({"detail": "ID ёки парол нотўғри."},
                            status=401, json_dumps_params={"ensure_ascii": False})

    _id, name, lang, hashed = row

    # --- Парол текшириш ---
    if not (hashed and check_password(raw_pw, hashed)):
        audit_log("Кириш муваффақиятсиз", request, actor_id=chat_id, status=401,
                  meta={"reason": "bad_password"})
        return JsonResponse({"detail": "ID ёки парол нотўғри."},
                            status=401, json_dumps_params={"ensure_ascii": False})

    now = timezone.now()
    with connection.cursor() as cur:
        cur.execute("""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='accounts_business' AND column_name='last_seen_at'
              ) THEN
                UPDATE public.accounts_business SET last_seen_at = %s WHERE id = %s;
              ELSE
                UPDATE public.accounts_business SET created_at = %s WHERE id = %s;
              END IF;
            END$$;
        """, [now, chat_id, now, chat_id])

    audit_log("Кириш муваффақиятли", request, actor_id=chat_id, status=200)

    return JsonResponse(
        {"ok": True, "detail": "Муваффақиятли кирдингиз.", "id": chat_id,
         "name": name, "lang": lang, "last_active_at": now.isoformat()},
        json_dumps_params={"ensure_ascii": False}
    )
 

# Сув нархини белгилашда давр қиймати   
PERIOD_MAP = {
    # Бир ойда / Бир йилда учун қисқа-лунда инглизча қийматлар
    "bir_oyda": "monthly",
    "bir_yilda": "yearly",
}


# Сув нархини белгилашда ёрдамчи функция   
def _normalize_end(v: Optional[Any]) -> Optional[int]:
    """
    'Чексиз' учун Python None қайтариб, JSONBда null сақлаймиз.
    Қолган ҳолларда бутун сонга мослаштирамиз.
    """
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"", "inf", "infinite", "∞", "cheksiz", "чексиз"}:
            return None
        # рақамли матн бўлса
        if s.isdigit():
            return int(s)
        raise ValueError("end not valid")
    if isinstance(v, (int, float)):
        return int(v)
    raise ValueError("end not valid")

# Сув нархини белгилашда ёрдамчи функция
def _validate_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    start/end/price майдонларини текшириш, сортлаш ва ихчамлаш.
    """
    cleaned = []
    for r in rules:
        try:
            start = int(r["start"])
            end   = _normalize_end(r.get("end"))
            price = int(r["price"])
        except Exception:
            raise ValueError("Rule item is invalid. Need {start:int, end:int|null, price:int}")

        if start < 0 or price < 0:
            raise ValueError("start/price must be non-negative")

        if end is not None and end < start:
            raise ValueError("end must be >= start (or null for infinite)")

        cleaned.append({"start": start, "end": end, "price": price})

    # start бўйича сортлаймиз ва кесишмасликни текширамиз
    cleaned.sort(key=lambda x: x["start"])
    for i in range(1, len(cleaned)):
        prev = cleaned[i-1]
        cur  = cleaned[i]
        prev_end = prev["end"]
        if prev_end is None:
            raise ValueError("Infinite (null) end must be the last rule only")
        if cur["start"] <= prev_end:
            raise ValueError("Rules must not overlap: each next.start must be > previous.end")

    return cleaned

# Сув нархини белгилаш функцияси
@csrf_exempt
@require_http_methods(["POST"])
def set_business_prices(request):
    """
    POST /accounts/set-business-prices

    JSON мисол (скринга мос):
    {
      "business_id": 1,
      "bir_oyda": true,          // ёки "bir_yilda": true (иккаласи бир вақтда true бўлмасин)
      "rules": [
        {"start": 0,   "end": 100, "price": 10000},
        {"start": 101, "end": 300, "price": 9000},
        {"start": 301, "end": 500, "price": 8000},
        {"start": 501, "end": null, "price": 7500}   // ЧЕКСИЗ → null
      ]
    }
    Қайтаради:
    {
      "status": "ok",
      "period": "monthly" | "yearly",
      "rules": [...],
      "business_id": 1
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "detail": "JSON noto‘g‘ri"}, status=400)

    business_id = payload.get("business_id")
    bir_oyda    = bool(payload.get("bir_oyda"))
    bir_yilda   = bool(payload.get("bir_yilda"))
    rules       = payload.get("rules", [])

    if not business_id:
        return JsonResponse({"status": "error", "detail": "business_id talab qilinadi"}, status=400)

    # Давр танлови: фақат бири true бўлсин
    if bir_oyda == bir_yilda:
        return JsonResponse({"status": "error", "detail": "Bir davrni tanlang: faqat bir_oyda yoki bir_yilda"}, status=400)

    period_key = "bir_oyda" if bir_oyda else "bir_yilda"
    period_val = PERIOD_MAP[period_key]  # 'monthly' ёки 'yearly'

    try:
        cleaned_rules = _validate_rules(rules)
    except ValueError as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=400)

    # JSONB учун Python объектини dump қиламиз
    rules_json = json.dumps(cleaned_rules, ensure_ascii=False)

    # Бевосита SQL орқали accounts_business’ни янгилаймиз
    # (Моделингизда майдонлар ҳозирча йўқ бўлгани учун шу йўл қулай)
    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE public.accounts_business
                   SET narxlar_diap_davri = %s,
                       service_price_rules = %s
                 WHERE id = %s
                """,
                [period_val, rules_json, business_id],
            )
            if cur.rowcount == 0:
                return JsonResponse({"status": "error", "detail": "business not found"}, status=404)

    return JsonResponse({
        "status": "ok",
        "period": period_val,
        "rules": cleaned_rules,
        "business_id": business_id,
    }, status=200)