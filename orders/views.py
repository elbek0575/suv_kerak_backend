# orders/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import connection
from datetime import date
import json
from datetime import datetime
from django.utils import timezone
from zoneinfo import ZoneInfo
from accounts.models import Business
from .models import Buyurtma
from decimal import Decimal, InvalidOperation
import os, requests

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

# Босс фойдаланувчи буюртма яратиш функцияси
@csrf_exempt
@require_POST
def create_buyurtma(request):
    """
    Кириш:
      - business_id: int (шарт)
      - client_tg_id: int | str (ихтиёрий)
      - client_tel_num: str (шарт)
      - suv_soni: int (>0) (шарт)
      - lat: float (шарт)
      - lng: float (шарт)
      - location_accuracy, location_source (ихтиёрий)
    Чиқиш: яратилган буюртма маълумоти + манзил (reverse-geocode)
    """
    # 1) Payload
    if request.content_type and "application/json" in request.content_type.lower():
        data = json.loads(request.body.decode("utf-8") or "{}")
    else:
        data = request.POST.dict()

    # 2) Мажбурий майдонлар
    try:
        business_id = int(data.get("business_id") or 0)
    except ValueError:
        business_id = 0
    client_tg_id = data.get("client_tg_id")
    client_tel_num = _normalize_phone(data.get("client_tel_num", ""))

    try:
        suv_soni = int(data.get("suv_soni") or 0)
    except ValueError:
        suv_sони = 0

    lat_in = data.get("lat")
    lng_in = data.get("lng")
    acc = data.get("location_accuracy")
    src = (data.get("location_source") or "manual").lower()

    if not business_id:
        return JsonResponse({"detail": "business_id талаб қилинади."}, status=400)
    if not client_tel_num:
        return JsonResponse({"detail": "Буюртмачи телефон рақами талаб қилинади."}, status=400)
    if suv_soni <= 0:
        return JsonResponse({"detail": "Сув сони 1 дан катта бўлсин."}, status=400)
    if lat_in is None or lng_in is None:
        return JsonResponse({"detail": "lat/lng талаб қилинади."}, status=400)

    # 3) Lat/Lng валидация
    try:
        lat = Decimal(str(lat_in)); lng = Decimal(str(lng_in))
    except InvalidOperation:
        return JsonResponse({"detail": "lat/lng формат нотўғри."}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({"detail": "lat/lng диапазони нотўғри."}, status=400)

    # 4) Бизнес бор-йўқ
    if not Business.objects.filter(id=business_id).exists():
        return JsonResponse({"detail": "Бундай business_id мавжуд эмас."}, status=404)

    # 5) Сана/вақт — Тошкент
    now = timezone.now()
    now_uz = timezone.localtime(now, UZ_TZ) if UZ_TZ else timezone.localtime(now)
    sana = now_uz.date()
    vaqt = now_uz.time().replace(microsecond=0)

    # 6) Reverse-geocode: координата -> манзил
    manzil = reverse_geocode(lat, lng) or ""

    # 7) Сақлаш
    obj = Buyurtma.objects.create(
        business_id=business_id,
        sana=sana, vaqt=vaqt,
        client_tg_id=(int(client_tg_id) if str(client_tg_id).isdigit() else None),
        client_tel_num=client_tel_num,
        suv_soni=suv_soni,
        manzil=manzil,
        buyurtma_statusi="pending",
        pay_status=_default_pay_status(),
        lat=lat, lng=lng,
        location_accuracy=(int(acc) if acc else None),
        location_source=src if src in {"tg", "manual", "geocode"} else "manual",
    )

    return JsonResponse({
        "message": "Буюртма муваффақиятли яратилди.",
        "buyurtma_id": obj.id,
        "status": obj.buyurtma_statusi,
        "pay_status": obj.pay_status,
        "sana": str(obj.sana),
        "vaqt": str(obj.vaqt),
        "manzil": obj.manzil,                       # reverse-geocode натижаси
        "coords": {
            "lat": float(obj.lat),
            "lng": float(obj.lng),
            "source": obj.location_source,
            "accuracy": obj.location_accuracy,
        }
    }, status=201)
    
    
def reverse_geocode(lat: Decimal, lng: Decimal) -> str | None:
    """Lat/Lng -> манзил. Аввал Google, бўлмаса OSM Nominatim."""
    # 1) Google Geocoding
    key = os.getenv("GOOGLE_MAPS_KEY")
    if key:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"latlng": f"{lat},{lng}", "key": key, "language": "uz"},
            timeout=6,
        )
        js = r.json()
        if js.get("status") == "OK" and js.get("results"):
            return js["results"][0]["formatted_address"]

    # 2) OSM Nominatim (fallback)
    r = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": float(lat), "lon": float(lng), "format": "jsonv2", "accept-language": "uz"},
        headers={"User-Agent": "suv-kerak/1.0"},
        timeout=6,
    )
    if r.ok:
        jj = r.json()
        return jj.get("display_name")
    return None

