"""
URL configuration for suv_kerak project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# suv_kerak/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils import translation
from bots.suv_kerak_bot import telegram_aiogram_webhook

def lang_page(request):
    return render(request, "lang.html")   # templates/lang.html

# (ихтиёрий) тезкор GET-алмаштириш: /lang/uz ёки /lang/ru
def switch_language(request, code):
    next_url = request.META.get("HTTP_REFERER", "/admin/")
    if code in dict(settings.LANGUAGES):
        translation.activate(code)
        resp = redirect(next_url)
        resp.set_cookie(settings.LANGUAGE_COOKIE_NAME, code)
        return resp
    return redirect(next_url)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("finance/", include("finance.urls")),
    path("i18n/", include("django.conf.urls.i18n")),  # POST /i18n/setlang/
    path("lang/", lang_page, name="lang_page"),       # форма саҳифаси
    path("lang/<str:code>/", switch_language, name="switch_language"),  # GET: /lang/uz    
    path("accounts/", include("accounts.urls")),
    path('orders/', include('orders.urls')),
    path("aiogram-bot-webhook/", telegram_aiogram_webhook, name="tg_webhook_alias"),
]

