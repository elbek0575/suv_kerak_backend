# accounts/urls.py
from django.urls import re_path, path
from .views import boss_login, set_business_prices

urlpatterns = [       
    re_path(r"^boss/login/?$", boss_login, name="boss_login"),
    re_path(r"^set-business-prices/?$", set_business_prices, name="set_business_prices"),    
]
