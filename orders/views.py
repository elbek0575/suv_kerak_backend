# orders/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection
from datetime import date

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
