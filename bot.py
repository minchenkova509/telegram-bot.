import os
import logging
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import setup_application
from aiohttp import web
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Логгинг
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 8080))

if not all([BOT_TOKEN, GOOGLE_CREDENTIALS_JSON, WEBHOOK_URL]):
    raise RuntimeError("Не заданы переменные окружения!")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
gc = gspread.authorize(credentials)

@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Бот успешно запущен и подключен к Google Sheets!")

async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    logging.info("Webhook установлен")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    logging.info("Webhook удален")

# Создаем веб-приложение
app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)
app.router.add_post(WEBHOOK_PATH, dp.webhook_handler(bot))

# Запускаем сервер
if __name__ == "__main__":
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
