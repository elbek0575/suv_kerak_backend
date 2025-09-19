# orders/views.py
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.db import transaction, connection, IntegrityError, transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from datetime import date
import json
from datetime import datetime
from django.utils.dateparse import parse_date
from django.utils import timezone
from zoneinfo import ZoneInfo
from accounts.models import Business
from finance.models import Transaction
from .models import Buyurtma
from decimal import Decimal, InvalidOperation
import os, requests, re
import logging


logger = logging.getLogger("orders")

# Боссни асосий менюсида статискик маълумотларни кайтарувчи эндпоент
@require_GET
def main_menu_stats(request):
    try:
        boss_id = int(request.GET.get("boss_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "boss_id нотўғри ёки келмади."}, status=400)

    today = date.today()

    with connection.cursor() as cur:
        # 1) Тизим ҳисоби (user_boss → boss_id)
        cur.execute("""
            SELECT tizimdagi_balance
            FROM public.business_system_account
            WHERE business_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, [boss_id])
        row = cur.fetchone()
        tizim_balans = float(row[0]) if row else 0.0
        
        # 2) Бугунги бажарилган буюртмалар (delivered)
        cur.execute("""
            SELECT COUNT(*)
            FROM public.buyurtmalar
            WHERE sana = %s
              AND business_id = %s
              AND buyurtma_statusi = 'delivered'
        """, [today, boss_id])
        bugungi_bajarilgan_soni = cur.fetchone()[0]

        # 3) Бугунги бажарилмаган буюртмалар (on_way, accepted)
        cur.execute("""
            SELECT COUNT(*)
            FROM public.buyurtmalar
            WHERE sana = %s
              AND business_id = %s
              AND buyurtma_statusi IN ('on_way','accepted')
        """, [today, boss_id])
        bugungi_bajarilmagan_soni = cur.fetchone()[0]

    return JsonResponse({
        "boss_id": boss_id,
        "business_id": boss_id,
        "tizim_hisobi_balans": tizim_balans,
        "bugungi_bajarilgan_buyurtmalar_soni": bugungi_bajarilgan_soni,
        "bugungi_bajarilmagan_buyurtmalar_soni": bugungi_bajarilmagan_soni,
    })
    
try:
    from zoneinfo import ZoneInfo
    UZ_TZ = ZoneInfo("Asia/Tashkent")
except Exception:
    UZ_TZ = None

def _normalize_phone(raw: str) -> str:
    if not raw:
        return ""
    s = "".join(ch for ch in str(raw) if ch.isdigit() or ch == "+")
    if s and not s.startswith("+") and s.startswith("998"):
        s = "+" + s
    return s

def _default_pay_status() -> str:
    # Моделда “pend_pay” бор-ёқлигини текшириб, бўлмаса 'none' билан қўямиз.
    allowed = {c[0] for c in Buyurtma.PAY_STATUS}
    return "pend_pay" if "pend_pay" in allowed else "none"

def _extract_lat_lng(data: dict | str):
    """
    Lat/Lng’ни турли форматдан ўқиб беради.
    Қўллаб-quvvatlayди:
      1) {"lat": 39.041069, "lng": 65.584425}
      2) {"coords": "39.041069, 65.584425"}  # ёки: "latlng", "location", "point", "geo", "coord"
      3) Бутун боди бир қатор матн бўлса: "39.041069, 65.584425"
    Қайтаради: (lat, lng) | (None, None)
    """
    # 1) Оддий майдонлар
    if isinstance(data, dict):
        lat = data.get("lat") or data.get("latitude")
        lng = data.get("lng") or data.get("lon") or data.get("long") or data.get("longitude")
        if lat is not None and lng is not None:
            try:
                return float(lat), float(lng)
            except Exception:
                pass

        # 2) Бир қаторли вариантни излаш
        for k in ("coords", "latlng", "location", "point", "geo", "coord"):
            if k in data and data[k]:
                line = str(data[k])
                break
        else:
            line = None
    else:
        # JSON эмас, бутун боди — матн бўлган ҳолат
        line = str(data or "")

    if line:
        # "39.041069, 65.584425" каби: лат, лонг (қавс/бўшлиқ/қўшимча белгиларга чидамли)
        m = re.search(r'(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)', line)
        if m:
            lat_s, lng_s = m.group(1), m.group(2)
            try:
                return float(lat_s), float(lng_s)
            except Exception:
                pass

    return None, None

# --- 🆕 ORDER NUMBER GENERATOR ---
def _format_segment(n: int, min_width: int = 2) -> str:
    """
    Сегментни камида 2 разрядгача 0 билан тўлдириб беради.
    Агар сон 2 разряддан катта бўлса, ўз ҳолича қолади (масалан: 128 → "128").
    """
    s = str(int(n))
    result = s.zfill(min_width) if len(s) < min_width else s
    #print(f"Икки разрядли сигмент {result}")
    return result


def _next_order_num(suv_soni: int) -> str:
    """
    Йил/ой/кун кесимидаги ЖАМИ СУВ (бутилка) сонини ҳисоблайди.
    Олдинги buyurtmalar'dаги suv_soni суммасини олади ва
    жорий suv_soni'ни қўшиб сегментларни беради.
    База мутлақо бўш бўлса — "01-01-01".
    """
    suv_soni = int(suv_soni or 0)
    if suv_soni <= 0:
        suv_soni = 1  # хавфсизлик учун

    now_uz = timezone.localtime(timezone.now())
    today   = now_uz.date()
    y_start = today.replace(month=1, day=1)
    m_start = today.replace(day=1)

    with transaction.atomic():
        # Бир вақтда фақат битта воркер санаши учун advisory lock
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ["buyurtma_order_num"])

        # База мутлақо бўшми?
        total_all = Buyurtma.objects.only("id").count()
        if total_all == 0:
            return "01-01-01"

        # 🔢 Олдинги бутилка жами (order эмас, aynan suv_soni суммаси)
        y_sum = Buyurtma.objects.filter(sana__gte=y_start, sana__lte=today)\
                 .aggregate(total=Coalesce(Sum("suv_soni"), 0))["total"]
        m_sum = Buyurtma.objects.filter(sana__gte=m_start, sana__lte=today)\
                 .aggregate(total=Coalesce(Sum("suv_soni"), 0))["total"]
        d_sum = Buyurtma.objects.filter(sana=today)\
                 .aggregate(total=Coalesce(Sum("suv_soni"), 0))["total"]

        # Жорий buyurtma бутилкаларини қўшамиз
        y_count = int(y_sum) + suv_soni
        m_count = int(m_sum) + suv_soni
        d_count = int(d_sum) + suv_soni

        # Формат: камида 2 разряд (масалан 03-03-03)
        return f"{_format_segment(y_count, 2)}-{_format_segment(m_count, 2)}-{_format_segment(d_count, 2)}"
    
    
# ------------------------------
# Бизнесс ҳудудни текшириш (PostGIS)
# ------------------------------
def _within_business_area(business_id: int, lat: float, lng: float) -> bool:
    # Business’dan viloyat’ни оламиз
    viloyat = Business.objects.filter(id=business_id).values_list("viloyat", flat=True).first()
    if not viloyat:
        print(f"[AREA] business_id={business_id} uchun viloyat topilmadi")
        return False

    # 1) Энг яқин марказгача масофани ҳисоблаш (метрда), кейин кмга айлантирамиз
    sql = """
    SELECT
      g.shaxar_yoki_tuman_nomi,
      g.radius_km,
      ST_Distance(
        g.center_geog,
        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
      ) AS dist_m
    FROM public.geo_list g
    WHERE g.viloyat = %s
    ORDER BY dist_m ASC
    LIMIT 1;
    """

    with connection.cursor() as cur:
        # Eslatma: MakePoint(lng, lat)
        cur.execute(sql, [float(lng), float(lat), viloyat])
        row = cur.fetchone()

    if not row:
        print(f"[AREA] viloyat='{viloyat}' uchun geo_list topilmadi")
        return False

    name, radius_km, dist_m = row
    dist_km = float(dist_m) / 1000.0
    radius_km = float(radius_km or 0)
    ok = dist_km <= radius_km

    # 🔎 Консолга дебаг чиқиши:
    print(
        f"[AREA] biz_id={business_id} viloyat={viloyat} "
        f"target=({lat:.6f},{lng:.6f}) nearest='{name}' "
        f"dist_km={dist_km:.3f} radius_km={radius_km:.0f} => ok={ok}"
    )

    return ok

# ------------------------------
# Бизнесс ID бўйича йил ва ой бошидан буюртма сонини санаш
# ------------------------------
def _inc_month_year_counters(business_id: int, suv_soni: int) -> int:
    """
    public.accounts_business.oy_bosh_sotil_suv_soni ва
    public.accounts_business.yil_bosh_sotil_suv_soni ни атомар равишда oshiradi.
    NULL -> 0 ҳисобланади, keyin + suv_soni қилади.
    Қайтарилади: update қилинган қаторлар сони (0 ёки 1).
    """
    suv_soni = int(suv_soni or 0)
    if suv_soni <= 0:
        return 0
    return Business.objects.filter(id=business_id).update(
        oy_bosh_sotil_suv_soni = Coalesce(F("oy_bosh_sotil_suv_soni"), 0) + suv_soni,
        yil_bosh_sotil_suv_soni = Coalesce(F("yil_bosh_sotil_suv_soni"), 0) + suv_soni,
    )

# ------------------------------
# Буюртмада сумма {ammount}ни аниклаш
# ------------------------------
def _calc_amount_for_order(business_id: int, suv_soni: int) -> tuple[Decimal, str, int, int]:
    """
    business_id ва suv_soni бўйича сумма (amount)ни ҳисоблайди.
    Кайтарилади: (amount, period, counter_value, unit_price)

    period: 'monthly' | 'yearly'
    counter_value: narx tanlashда ишлатилган ҳисоблагич қиймати (ой/йил бошидан)
    unit_price: танланган диапазон бўйича 1 сув нархи
    """
    suv_soni = int(suv_soni or 0)
    if suv_soni <= 0:
        raise ValueError("suv_soni > 0 бўлиши керак")

    # 🔒 бизнес қаторини қулфлаб ўқимоқдамиз (атомар ҳисоб)
    biz = (
        Business.objects
        .select_for_update()
        .only("narxlar_diap_davri", "oy_bosh_sotil_suv_soni", "yil_bosh_sotil_suv_soni", "service_price_rules")
        .get(id=business_id)
    )

    period = (biz.narxlar_diap_davri or "").strip().lower()
    if period not in {"monthly", "yearly"}:
        # конфиг йўқ/нотўғри бўлса — 0 сўм
        return Decimal("0"), period or "monthly", 0, 0

    counter_value = int(biz.oy_bosh_sotil_suv_soni or 0) if period == "monthly" \
                    else int(biz.yil_bosh_sotil_suv_soni or 0)

    # JSONB -> Python list[dict]
    rules = biz.service_price_rules or []
    # хавфсизлик: start бўйича сортлаймиз
    try:
        rules = sorted(rules, key=lambda r: int(r.get("start", 0)))
    except Exception:
        rules = []

    unit_price = 0
    for r in rules:
        try:
            start = int(r.get("start", 0))
            end_raw = r.get("end", None)
            end = None if end_raw is None else int(end_raw)
            price = int(r.get("price", 0))
        except Exception:
            continue

        if counter_value >= start and (end is None or counter_value <= end):
            unit_price = price
            break

    # агар ҳеч бири тўғри келмаса, охирги қоида end=null бўлса шуни, акс ҳолда 0 оламиз
    if unit_price == 0 and rules:
        last = rules[-1]
        if last.get("end") is None:
            try:
                unit_price = int(last.get("price", 0))
            except Exception:
                unit_price = 0

    amount = Decimal(str(unit_price)) * Decimal(str(suv_soni))
    return amount, period, counter_value, unit_price


# ------------------------------
# Буюртма яратиш
# ------------------------------
@csrf_exempt
@require_POST
def create_buyurtma(request):
    # 1) Payload
    if request.content_type and "application/json" in request.content_type.lower():
        data = json.loads((request.body or b"").decode("utf-8") or "{}")
    else:
        data = request.POST.dict()

    # 2) Локализация хабарлари ва тил
    _msg = {
        "out_of_area": {
            "uz":     "Юборилган локация фаолият юритиш ҳудудидан ташқарида. Локация нотўғри.",
            "uz_lat": "Yuborilgan lokatsiya faoliyat yuritish hududidan tashqarida. Lokatsiya noto‘g‘ri.",
            "ru":     "Отправленная локация вне зоны деятельности. Некорректная локация.",
            "en":     "The sent location is outside the service area. Invalid location.",
        },
        "check_failed": {
            "uz":     "Локацияни текширишда носозлик. Кейинроқ яна уриниб кўринг.",
            "uz_lat": "Lokatsiyani tekshirishda nosozlik. Keyinroq yana urinib ko‘ring.",
            "ru":     "Сбой при проверке локации. Попробуйте позже.",
            "en":     "Failed to verify location. Please try again later.",
        },
    }
    lang = (str(data.get("lang") or "уз")).lower()
    if lang not in {"uz", "uz_lat", "ru", "en"}:
        lang = "uz"

    # 3) Мажбурий майдонлар
    try:
        business_id = int(data.get("business_id") or 0)
    except ValueError:
        business_id = 0
    client_tg_id = data.get("client_tg_id")
    client_tel_num = _normalize_phone(data.get("client_tel_num", ""))

    try:
        suv_soni = int(data.get("suv_soni") or 0)
    except ValueError:
        suv_soni = 0

    # 4) Координата парс
    lat_in, lng_in = _extract_lat_lng(data)    
    try:
        lat_f = float(lat_in); lng_f = float(lng_in)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "lat/lng формат нотўғри."}, status=400)
  
    # 5) Асосий валидациялар
    if not business_id:
        return JsonResponse({"detail": "business_id талаб қилинади."}, status=400)
    if not client_tel_num:
        return JsonResponse({"detail": "Буюртмачи телефон рақами талаб қилинади."}, status=400)
    if suv_soni <= 0:
        return JsonResponse({"detail": "Сув сони 1 дан катта бўлсин."}, status=400)
    if lat_in is None or lng_in is None:
        return JsonResponse({"detail": "lat/lng координаталари талаб қилинади."}, status=400)

    # 6) Хизмат ҳудуди текшируви (бир марта)
    try:
        ok = _within_business_area(business_id, lat_f, lng_f)
    except Exception:
        return JsonResponse({"detail": _msg["check_failed"][lang]}, status=500)
    if not ok:
        return JsonResponse({"detail": _msg["out_of_area"][lang]}, status=400)

    # 7) Диапазон ва Decimal га конверт (сақлаш учун)
    try:
        lat = Decimal(str(lat_f)); lng = Decimal(str(lng_f))
    except InvalidOperation:
        return JsonResponse({"detail": "lat/lng формат нотўғри."}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({"detail": "lat/lng кординаталар диапазони нотўғри."}, status=400)

    if not Business.objects.filter(id=business_id).exists():
        return JsonResponse({"detail": "Бундай business_id мавжуд эмас."}, status=404)

    # 8) Қолган майдонлар
    acc = data.get("location_accuracy")
    src = (data.get("location_source") or "manual").lower()
    manzil = (data.get("manzil") or "").strip()    
        # 🆕 Izoh (several possible keys: "manzil_izoh" or "izoh")
    manzil_izoh = (data.get("manzil_izoh") or data.get("izoh") or "")
    manzil_izoh = manzil_izoh.strip() or None

    now_uz = timezone.localtime(timezone.now())
    
    attempt = 0
    last_err = None
    while attempt < 5:
        attempt += 1
        order_num = _next_order_num(suv_soni)
        print(f"Ордер рақами {order_num}")
        try:
            with transaction.atomic():
                # 🆕 1) (ammount) Буюртма суммасини ҳисоблаш
                amount, period, used_counter, unit_price = _calc_amount_for_order(business_id, suv_soni)
                obj = Buyurtma.objects.create(
                    business_id=business_id,
                    sana=now_uz.date(),
                    vaqt=now_uz.time().replace(microsecond=0),
                    client_tg_id=(int(client_tg_id) if str(client_tg_id).isdigit() else None),
                    client_tel_num=client_tel_num,
                    suv_soni=suv_soni,
                    manzil=manzil,
                    manzil_izoh=manzil_izoh,
                    buyurtma_statusi="pending",
                    pay_status=_default_pay_status(),
                    lat=lat,
                    lng=lng,
                    location_accuracy=(int(acc) if acc else None),
                    location_source=src if src in {"tg", "manual", "geocode"} else "manual",
                    order_num=order_num,  # 🆕
                    amount=amount, # Буюртма суммаси
                )
                
                 # 🆕 Ой/Йил бошидан сотилган сув сонини increment қиламиз (Автомар)
                updated = _inc_month_year_counters(business_id, suv_soni)
                if updated == 0:
                    logger.warning("Business %s topilmadi, counters yangilanmadi", business_id)
                    
                logger.info("Price calc: period=%s, counter=%s -> unit=%s, amount=%s",
                            period, used_counter, unit_price, str(amount))
                
            break  # муваффақиятли яратилди
        except IntegrityError as e:
            # Масалан, order_num unique бузилса — яна бир марта уринамиз
            last_err = e
            continue
    #print("attempt сигментида қўшилган разряд сони-", attempt, "та")        
    if attempt >= 5 and last_err:
        return JsonResponse(
            {"detail": "Ички рақамни яратишда муаммо. Илтимос, яна уриниб кўринг."},
            status=500
        )
        
    return JsonResponse({
        "message": "Буюртма муваффақиятли яратилди.",
        "buyurtma_id": obj.id,
        "order_num": obj.order_num,  # 🆕 клиентга ҳам берамиз
        "status": obj.buyurtma_statusi,
        "pay_status": obj.pay_status,
        "sana": str(obj.sana),
        "vaqt": str(obj.vaqt),
        "manzil": obj.manzil,
        "suv_soni": suv_soni,
        "suv_narxi": unit_price,
        "tulov_summasi":amount,
        "coords": {
            "lat": float(obj.lat),
            "lng": float(obj.lng),
            "source": obj.location_source,
            "accuracy": obj.location_accuracy,             
        }
    }, status=201)
    
# ------------------------------
# Бажарилмаган буюртмаларни рўйхатини қайтариш учун ёрдамчи функция
# ------------------------------    
def _human_pay_status(code: str) -> str:
    return "Онлайн тўланди" if (code or "").lower() == "completed_online" else "Тўланмаган"

# ------------------------------
# Бажарилмаган буюртмаларни рўйхатини қайтариш учун ёрдамчи функция
# ------------------------------   
def _point_wkt(lat, lng):
    try:
        return f"POINT ({float(lng)} {float(lat)})"
    except Exception:
        return None

# ------------------------------
# Бажарилмаган буюртмаларни рўйхатини қайтариш учун онлайн туловлар маълумотларини кайтарувчи ёрдамчи функция
# ------------------------------ 
def _human_pay_status(code: str) -> str:
    return "Онлайн тўланди" if (code or "").lower() == "completed_online" else "Тўланмаган"

# ------------------------------
# Бажарилмаган буюртмаларни рўйхатини қайтариш учун онлайн туловлар саналарини форматловчи ёрдамчи функция
# ------------------------------ 
def _fmt_dt(dt):
    """ updated_at ни сана/вақтга форматлаймиз (UZ local time). """
    if not dt:
        return "", ""
    dt = timezone.localtime(dt)
    return dt.strftime("%d.%m.%y"), dt.strftime("%H:%M")


# ------------------------------
# Бажарилмаган буюртмаларни рўйхатини қайтарувчи функция
# ------------------------------   
@csrf_exempt
@require_http_methods(["GET", "POST"])
def list_pending_orders(request):
    """
    Кириш: business_id (GET query ёки POST JSON)
    Чиқиш: скриндаги жадвал учун руйхат
    """
    # 1) business_id оламиз (GET ёки JSON)
    if request.method == "GET":
        business_id = request.GET.get("business_id")
    else:
        try:
            import json
            payload = json.loads((request.body or b"").decode("utf-8") or "{}")
        except Exception:
            payload = {}
        business_id = payload.get("business_id")
    print(f"business_id= {business_id}")
    try:
        business_id = int(business_id)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "business_id талаб қилинади (integer)."}, status=400)

    # 2) pending буюртмаларни оламиз (охиргилари аввал)
    qs = (Buyurtma.objects
          .filter(business_id=business_id, buyurtma_statusi="pending")
          .order_by("-sana", "-vaqt"))

    rows = []
    total_suv_soni = 0

    for o in qs:
        buyurtma_sanasi = o.sana.strftime("%d.%m.%y") if o.sana else ""
        buyurtma_vaqti  = o.vaqt.strftime("%H:%M")   if o.vaqt else ""
        
        # 🔹 Тулув статуси (онлайн ёки йўқ)
        human_status = _human_pay_status(o.pay_status)

        # 🔹 Агар онлайн тўлов бўлса, transactions’дан тўловлар рўйхатини оламиз
        payments = []
        if human_status == "Онлайн тўланди":
            # order_num = transactions.order_id билан боғланяпти
            tx_qs = (Transaction.objects
                     .filter(order_id=o.order_num)
                     .order_by("-updated_at")
                     .values("updated_at", "amount", "order_id"))

            for tx in tx_qs:
                p_date, p_time = _fmt_dt(tx["updated_at"])
                payments.append({
                    "pay_date": p_date,                   # дд.мм.гг
                    "pay_time": p_time,                   # чч.мм
                    "amount":   str(tx["amount"]),        # decimal -> str
                    "order_id": tx["order_id"],
                })

        rows.append({
            "buyurtma_sanasi":   buyurtma_sanasi,                  # дд.мм.гг
            "buyurtma_vaqti":    buyurtma_vaqti,                   # чч.мм
            "izoh":              (o.manzil_izoh or ""),            # манзил изоҳ
            "buyurtmachi_id":    o.client_tg_id,                   # telegram id
            "buyurtma_id_raqami": o.order_num,                     # ичкий рақам
            "suv_soni":          int(o.suv_soni or 0),
            "location":          _point_wkt(o.lat, o.lng),         # "POINT (lng lat)"
            "tulov_statusi":     _human_pay_status(o.pay_status),  # Онлайн тўланди / Тўланмаган
            # 🆕 Онлайн бўлса — ҳар бир тўлов алоҳида объект сифатида
            "online_payments":    payments,                   # [] ёки [{pay_date,...}, ...]
        })
        total_suv_soni += int(o.suv_soni or 0)

    return JsonResponse({
        "business_id": business_id,
        "count": len(rows),
        "suv_soni_jami": total_suv_soni,
        "items": rows,
    }, status=200)
    
