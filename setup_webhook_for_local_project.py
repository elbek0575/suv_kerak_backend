import requests
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

print("NGROK_URL =", os.getenv("WEBHOOK_HOST"))

TOKEN = os.getenv("BOT_TOKEN")
NGROK_URL = (os.getenv("WEBHOOK_HOST") or "").strip().rstrip("/")
webhook_url = f"{NGROK_URL}/webhook/"

print("TOKEN:", TOKEN)
print(f".env файлдаги WEBHOOK_HOST қиймати {NGROK_URL}")
print("Webhook URL:", webhook_url)

url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
response = httpx.post(url, json={"url": webhook_url})

print("Статус код:", response.status_code)
print("Ответ сервера:", response.json())