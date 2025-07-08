import os
import json
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web

import gspread
from oauth2client.service_account import ServiceAccountCredentials

ADMINS = [769063484]
DRIVERS = {
    "Еремин": 111111111,
    "Уранов": 222222222,
    "Новиков": 333333333
}

# 🔐 Google Sheets credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds_raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
with open("creds.json", "w") as f:
    json.dump(json.loads(creds_raw), f)
credentials = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(credentials)
sheet = client.open("Falcontrans Docs").sheet1

# 🚀 Telegram Bot
bot_token = os.getenv("API_TOKEN")
bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

class UploadState(StatesGroup):
    waiting_photo = State()
    waiting_number = State()
    waiting_driver = State()

class DocumentState(StatesGroup):
    choosing_application = State()
    sending_documents = State()

applications = {}  # {driver_id: [{"number": "123", "photo": file_id}]}
current_upload = {}

@dp.message(F.text == "/start")
async def start_handler(msg: types.Message, state: FSMContext):
    if msg.from_user.id in ADMINS:
        await msg.answer("Отправь фото заявки!")
        await state.set_state(UploadState.waiting_photo)
    else:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=name)] for name in DRIVERS.keys()],
            resize_keyboard=True
        )
        await msg.answer("Выбери свою фамилию:", reply_markup=kb)

@dp.message(UploadState.waiting_photo, F.photo)
async def photo_received(msg: types.Message, state: FSMContext):
    file_id = msg.photo[-1].file_id
    current_upload[msg.from_user.id] = {"photo": file_id}
    await msg.answer("Теперь введи номер заявки:")
    await state.set_state(UploadState.waiting_number)

@dp.message(UploadState.waiting_number)
async def number_received(msg: types.Message, state: FSMContext):
    current_upload[msg.from_user.id]["number"] = msg.text
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for name in DRIVERS.keys()],
        resize_keyboard=True
    )
    await msg.answer("Кому заявка?", reply_markup=kb)
    await state.set_state(UploadState.waiting_driver)

@dp.message(UploadState.waiting_driver)
async def driver_chosen(msg: types.Message, state: FSMContext):
    driver = msg.text
    data = current_upload.get(msg.from_user.id)
    if driver not in DRIVERS:
        await msg.answer("Неверная фамилия. Попробуй ещё раз.")
        return
    driver_id = DRIVERS[driver]
    applications.setdefault(driver_id, []).append(data)
    await bot.send_photo(chat_id=driver_id, photo=data["photo"], caption=f"Заявка №{data['number']}")
    await msg.answer("Заявка отправлена водителю ✅")
    sheet.append_row([data['number'], driver])
    await state.clear()

@dp.message(F.text.in_(DRIVERS.keys()))
async def driver_selected(msg: types.Message, state: FSMContext):
    driver_id = msg.from_user.id
    if driver_id not in applications or not applications[driver_id]:
        await msg.answer("Нет активных заявок. Введите номер вручную:")
        await state.set_state(DocumentState.choosing_application)
        return

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=app["number"])] for app in applications[driver_id]],
        resize_keyboard=True
    )
    await msg.answer("Выбери номер заявки или введи вручную:", reply_markup=kb)
    await state.set_state(DocumentState.choosing_application)

@dp.message(DocumentState.choosing_application)
async def application_chosen(msg: types.Message, state: FSMContext):
    await state.update_data(selected_number=msg.text)
    await msg.answer("Отправь документы (фото):")
    await state.set_state(DocumentState.sending_documents)

@dp.message(DocumentState.sending_documents, F.photo)
async def docs_received(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_id = ADMINS[0]
    await bot.send_photo(chat_id=admin_id, photo=msg.photo[-1].file_id,
                         caption=f"📄 Документ по заявке! №{data['selected_number']} от {msg.from_user.full_name}")
    await msg.answer("Спасибо! Документы отправлены ✅")
    await state.clear()

@dp.message()
async def fallback(msg: types.Message):
    await msg.answer("Напиши /start чтобы начать")

# 🌐 Webhook
async def on_startup(app):
    webhook_url = os.getenv("WEBHOOK_URL")
    await bot.set_webhook(webhook_url)

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()
app.router.add_post("/webhook", dp.handler)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host="0.0.0.0", port=8080)
