import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# Настройка логгирования
logging.basicConfig(level=logging.INFO)

# Переменные среды
ADMINS = ["769063484"]  # Telegram ID админа
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Проверка переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных среды")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=ParseMode.HTML)
dp = Dispatcher()

# Google Sheets авторизация
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(eval(GOOGLE_CREDS), scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open("Falcontrans Docs").sheet1

# Память водителей и заявок
drivers = ["Ерёмин", "Уранов", "Новиков"]
driver_zayavki = {}

# Обработка /start
@dp.message(F.text == "/start")
async def start(message: Message):
    if str(message.from_user.id) in ADMINS:
        await message.answer("👋 Привет, админ! Отправь фото заявки.")
    else:
        builder = InlineKeyboardBuilder()
        for name in drivers:
            builder.button(text=name, callback_data=f"driver_{name}")
        await message.answer("Выбери свою фамилию:", reply_markup=builder.as_markup())

# Обработка фото от админа
@dp.message(F.photo)
async def handle_photo(message: Message):
    if str(message.from_user.id) not in ADMINS:
        return

    file_id = message.photo[-1].file_id
    await message.answer("✏️ Напиши номер заявки:")
    dp["pending_photo"] = file_id
    dp["admin_id"] = message.from_user.id

# Получение номера заявки
@dp.message(F.text.regexp(r"^\d+$"))
async def handle_zayavka_number(message: Message):
    if str(message.from_user.id) not in ADMINS or "pending_photo" not in dp:
        return

    number = message.text
    file_id = dp.pop("pending_photo")
    builder = InlineKeyboardBuilder()
    for d in drivers:
        builder.button(text=d, callback_data=f"assign_{number}_{d}")
    await message.answer("Кому отправить заявку?", reply_markup=builder.as_markup())
    dp["pending_zayavka"] = {"file_id": file_id, "number": number}

# Назначение заявки водителю
@dp.callback_query(F.data.startswith("assign_"))
async def assign_zayavka(callback: CallbackQuery):
    _, number, driver = callback.data.split("_")
    data = dp.pop("pending_zayavka", None)
    if data:
        driver_zayavki.setdefault(driver, {})[number] = data["file_id"]
        await callback.message.answer(f"✅ Заявка {number} отправлена {driver}")
        # Сохраняем в таблицу
        sheet.append_row([datetime.now().isoformat(), driver, number])
    await callback.answer()

# Водитель выбрал себя
@dp.callback_query(F.data.startswith("driver_"))
async def driver_menu(callback: CallbackQuery):
    name = callback.data.split("_")[1]
    dp[name] = callback.from_user.id  # Связка имени и user_id
    zayavki = driver_zayavki.get(name, {})
    if not zayavki:
        await callback.message.answer("Нет заявок. Введите вручную номер заявки:")
        dp["manual_driver"] = name
        return

    builder = InlineKeyboardBuilder()
    for num in zayavki:
        builder.button(text=num, callback_data=f"zayavka_{num}_{name}")
    builder.button(text="Ввести вручную", callback_data=f"manual_{name}")
    await callback.message.answer("📋 Ваши заявки:", reply_markup=builder.as_markup())
    await callback.answer()

# Выбор заявки
@dp.callback_query(F.data.startswith("zayavka_"))
async def choose_zayavka(callback: CallbackQuery):
    _, number, driver = callback.data.split("_")
    await callback.message.answer("📸 Отправь документы по заявке:")
    dp["current_doc"] = {"number": number, "driver": driver, "user_id": callback.from_user.id}
    await callback.answer()

# Ввод вручную
@dp.callback_query(F.data.startswith("manual_"))
async def manual_zayavka(callback: CallbackQuery):
    driver = callback.data.split("_")[1]
    dp["manual_driver"] = driver
    await callback.message.answer("✏️ Введите номер заявки вручную:")
    await callback.answer()

# Ввод номера вручную
@dp.message(F.text)
async def manual_entry(message: Message):
    if "manual_driver" in dp:
        driver = dp.pop("manual_driver")
        number = message.text.strip()
        dp["current_doc"] = {"number": number, "driver": driver, "user_id": message.from_user.id}
        await message.answer("📸 Отправь документы по заявке:")

# Приём документов
@dp.message(F.document | F.photo)
async def handle_docs(message: Message):
    if "current_doc" not in dp:
        return
    data = dp.pop("current_doc")
    number = data["number"]
    driver = data["driver"]
    admin_id = ADMINS[0]
    await message.answer("✅ Спасибо, документы получены!")

    # Пересылаем админу
    caption = f"Документы по заявке {number} от {driver}"
    if message.document:
        await bot.send_document(admin_id, message.document.file_id, caption=caption)
    elif message.photo:
        await bot.send_photo(admin_id, message.photo[-1].file_id, caption=caption)

# Запуск сервера
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, port=8080)
