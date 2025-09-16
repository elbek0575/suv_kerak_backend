# accounts/views.py
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import connection               # ✅ Django connection
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

@csrf_exempt
def boss_login(request):
    """
    POST /accounts/boss/login/
    Body: { "boss_user_id": <int>, "password": "<str>" }
    """
    # 1) Кирувчи JSON
    try:
        data = json.loads((request.body or b"").decode("utf-8") or "{}")
    except Exception:
        data = {}
    raw_id = data.get("boss_user_id")
    raw_pw = data.get("password")

    # Кирувчи валидация
    if raw_id is None or not raw_pw:
        audit_log("Кириш муваффақиятсиз", request, actor_id=None, status=400,
                  meta={"reason": "bad_input"})
        return JsonResponse({"detail": "ID ва парол талаб қилинади."},
                            status=400, json_dumps_params={"ensure_ascii": False})

    try:
        chat_id = int(str(raw_id).strip())
    except Exception:
        audit_log("Кириш муваффақиятсиз", request, actor_id=None, status=400,
                  meta={"reason": "bad_id_format", "raw_id": raw_id})
        return JsonResponse({"detail": "ID нотўғри форматда."},
                            status=400, json_dumps_params={"ensure_ascii": False})

    # 2) Фойдаланувчини олиш
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, name, COALESCE(lang,'uz'), password "
            "FROM public.accounts_business WHERE id=%s LIMIT 1",
            [chat_id],
        )
        row = cur.fetchone()

    if not row:
        # user enumeration’ни олдини олиш учун 401
        audit_log("Кириш муваффақиятсиз", request, actor_id=chat_id, status=401,
                  meta={"reason": "user_not_found"})
        return JsonResponse({"detail": "ID ёки парол нотўғри."},
                            status=401, json_dumps_params={"ensure_ascii": False})

    _id, name, lang, hashed = row

    # 3) Паролни текшириш
    if not (hashed and check_password(raw_pw, hashed)):
        audit_log("Кириш муваффақиятсиз", request, actor_id=chat_id, status=401,
                  meta={"reason": "bad_password"})
        return JsonResponse({"detail": "ID ёки парол нотўғри."},
                            status=401, json_dumps_params={"ensure_ascii": False})

    # 4) Охирги фаол вақтни янгилаш (last_seen_at бор бўлса шуни, бўлмаса created_at’ни)
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

    # 5) Муваффақият — аудит
    audit_log("Кириш муваффақиятли", request, actor_id=chat_id, status=200)

    return JsonResponse(
        {
            "ok": True,
            "detail": "Муваффақиятли кирдингиз.",
            "id": chat_id,
            "name": name,
            "lang": lang,
            "last_active_at": now.isoformat(),
        },
        json_dumps_params={"ensure_ascii": False}
    )
