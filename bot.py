import os
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiohttp import web
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Логирование
logging.basicConfig(level=logging.INFO)

# Получаем переменные окружения
API_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Проверка токена
if not API_TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не установлена")

# Инициализация бота
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Авторизация в Google Sheets
creds_dict = json.loads(GOOGLE_CREDS_JSON)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(credentials)

# Подключение к таблице
sheet_url = "https://docs.google.com/spreadsheets/d/1jDxPfl10qTiKrHW9mdvbY9voinMV872IYrs3iHK56Gg"
spreadsheet = client.open_by_url(sheet_url)
worksheet = spreadsheet.sheet1  # используем первый лист

# Обработка команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username or "-"
    worksheet.append_row([str(user_id), full_name, username])
    await message.answer("👋 Привет! Ты успешно записан в таблицу!")

# Запуск веб-сервера (webhook handler)
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    setup_application(app, dp)
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    main()
