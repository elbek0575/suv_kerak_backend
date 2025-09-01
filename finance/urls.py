from django.urls import path
from .views import courier_stock_move, courier_stock_balance

urlpatterns = [
    path("courier/stock/move", courier_stock_move),
    path("courier/stock/balance", courier_stock_balance),
]
