from django.shortcuts import render
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.core.exceptions import ValidationError

from accounts.models import Business
from .models import CourierWaterBottleBalance


def _latest_balance(business, kuryer_id):
    last = (CourierWaterBottleBalance.objects
            .filter(business=business, kuryer_id=kuryer_id, status="ok")
            .order_by("-grated").first())
    return {
        "water_balance": last.water_balance if last else 0,
        "bottle_balance": last.bottle_balance if last else 0,
    }


@csrf_exempt
@require_http_methods(["POST"])
def courier_stock_move(request):
    """
    Кирим/чиқим ёзиш:
    {
      "business_id": 1,
      "sana": "2025-09-01",
      "vaqt": "12:40:00",
      "boss_id": 7001,
      "boss_name": "Шерали ака",

      "kuryer_id": 9001,
      "kuryer_name": "Жамшид ака",

      "client_tg_id": null,
      "client_tel_num": "99890xxxxxxx",
      "buyurtma_num": 12345,

      "operation": "in_from_boss" | "sell_to_client" | "return_empty" | "adjustment",
      "income": 10,     // dona
      "expense": 0      // dona
    }
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "JSON нотўғри."}, status=400)

    required = ["business_id", "sana", "vaqt", "boss_id", "boss_name",
                "kuryer_id", "kuryer_name", "operation"]
    missing = [k for k in required if not body.get(k)]
    if missing:
        return JsonResponse({"detail": f"Мажбурий майдон(лар) йўқ: {', '.join(missing)}"}, status=400)

    try:
        business = Business.objects.get(id=body["business_id"])
    except Business.DoesNotExist:
        return JsonResponse({"detail": "Business топилмади."}, status=404)

    rec = CourierWaterBottleBalance(
        business=business,
        sana=body["sana"],
        vaqt=body["vaqt"],

        boss_id=body["boss_id"],
        boss_name=body["boss_name"],

        client_tg_id=body.get("client_tg_id"),
        client_tel_num=body.get("client_tel_num"),
        buyurtma_num=body.get("buyurtma_num"),

        kuryer_id=body["kuryer_id"],
        kuryer_name=body["kuryer_name"],

        operation=body["operation"],
        income=int(body.get("income") or 0),
        expense=int(body.get("expense") or 0),
        status="ok",
    )

    try:
        rec.full_clean()   # clean() валидациясини ишга туширади
        rec.save()         # save() балансларни автоматика ҳисоблайди
    except ValidationError as ve:
        return JsonResponse({"detail": ve.message_dict if hasattr(ve, "message_dict") else ve.messages}, status=400)

    return JsonResponse({
        "detail": "Қайд сақланди.",
        "id": rec.id,
        "operation": rec.operation,
        "delta": rec.income - rec.expense,
        "balances": {
            "water_balance": rec.water_balance,
            "bottle_balance": rec.bottle_balance
        },
        "grated": rec.grated.isoformat(),
    }, status=201)


@require_http_methods(["GET"])
def courier_stock_balance(request):
    """
    Параметрлар (query): ?business_id=1&kuryer_id=9001
    """
    business_id = request.GET.get("business_id")
    kuryer_id = request.GET.get("kuryer_id")
    if not business_id or not kuryer_id:
        return JsonResponse({"detail": "business_id ва kuryer_id талаб қилинади."}, status=400)
    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        return JsonResponse({"detail": "Business топилмади."}, status=404)

    bal = _latest_balance(business, kuryer_id)
    return JsonResponse({"balances": bal})

